"""Web interface for the HA Log Debugger AI application."""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from .models import Recommendation, HealthStatus, LogEntry
from .database import Database

logger = logging.getLogger(__name__)


class WebInterface:
    """FastAPI web interface for the application."""
    
    def __init__(self, database: Database, log_monitor=None, ai_analyzer=None):
        self.app = FastAPI(title="HA Log Debugger AI", version="1.0.0")
        self.database = database
        self.log_monitor = log_monitor
        self.ai_analyzer = ai_analyzer
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory="static"), name="static")
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            """Serve the main HTML page."""
            with open("static/index.html", "r") as f:
                return HTMLResponse(content=f.read())
        
        @self.app.get("/api/health")
        async def health_check() -> HealthStatus:
            """Get application health status."""
            try:
                # Check database
                stats = await self.database.get_stats()
                db_connected = True
            except Exception:
                stats = {"total_recommendations": 0}
                db_connected = False
            
            # Check AI service
            ai_available = False
            if self.ai_analyzer:
                try:
                    ai_available = await self.ai_analyzer.test_connection()
                except Exception:
                    ai_available = False
            
            # Check log monitor
            log_monitor_active = self.log_monitor is not None
            
            return HealthStatus(
                status="healthy" if db_connected else "unhealthy",
                log_monitor_active=log_monitor_active,
                ai_service_available=ai_available,
                database_connected=db_connected,
                last_log_entry=datetime.now(),  # This would be tracked in real implementation
                recommendations_count=stats.get("total_recommendations", 0)
            )
        
        @self.app.get("/api/recommendations")
        async def get_recommendations(
            limit: int = 50,
            resolved: Optional[bool] = None
        ) -> List[Recommendation]:
            """Get recommendations from the database."""
            try:
                return await self.database.get_recommendations(limit=limit, resolved=resolved)
            except Exception as e:
                logger.error(f"Error fetching recommendations: {e}")
                raise HTTPException(status_code=500, detail="Failed to fetch recommendations")
        
        @self.app.post("/api/recommendations/{recommendation_id}/resolve")
        async def resolve_recommendation(recommendation_id: int):
            """Mark a recommendation as resolved."""
            try:
                success = await self.database.mark_resolved(recommendation_id)
                if success:
                    return {"message": "Recommendation marked as resolved"}
                else:
                    raise HTTPException(status_code=404, detail="Recommendation not found")
            except Exception as e:
                logger.error(f"Error resolving recommendation: {e}")
                raise HTTPException(status_code=500, detail="Failed to resolve recommendation")
        
        @self.app.get("/api/logs/recent")
        async def get_recent_logs(
            lines: int = 100, 
            level: Optional[str] = None,
            component: Optional[str] = None,
            source: str = "file"
        ) -> List[dict]:
            """Get recent log entries from file or database."""
            try:
                if source == "database":
                    # Get logs from database with filtering support
                    entries = await self.database.get_logs(
                        limit=lines, 
                        level_filter=level, 
                        component_filter=component
                    )
                else:
                    # Get logs from file (existing behavior)
                    if not self.log_monitor:
                        raise HTTPException(status_code=503, detail="Log monitor not available")
                    entries = await self.log_monitor.read_recent_logs(lines=lines)
                    
                    # Apply client-side filtering if specified
                    if level:
                        entries = [e for e in entries if e.level.value == level]
                    if component:
                        entries = [e for e in entries if e.component == component]
                
                return [
                    {
                        "timestamp": entry.timestamp.isoformat(),
                        "level": entry.level.value,
                        "component": entry.component,
                        "message": entry.message
                    }
                    for entry in entries
                ]
            except Exception as e:
                logger.error(f"Error fetching recent logs: {e}")
                raise HTTPException(status_code=500, detail="Failed to fetch recent logs")
        
        @self.app.get("/api/stats")
        async def get_stats():
            """Get application statistics."""
            try:
                db_stats = await self.database.get_stats()
                return {
                    "database": db_stats,
                    "log_monitor_active": self.log_monitor is not None,
                    "ai_service_available": self.ai_analyzer is not None
                }
            except Exception as e:
                logger.error(f"Error fetching stats: {e}")
                raise HTTPException(status_code=500, detail="Failed to fetch statistics")
        
        @self.app.post("/api/analyze")
        async def trigger_analysis():
            """Manually trigger log analysis."""
            if not self.log_monitor or not self.ai_analyzer:
                raise HTTPException(status_code=503, detail="Required services not available")
            
            try:
                # Get recent warning/error logs
                recent_logs = await self.log_monitor.read_recent_logs(lines=50)
                error_logs = [
                    log for log in recent_logs 
                    if log.level.value in ["WARNING", "ERROR", "CRITICAL"]
                ]
                
                if not error_logs:
                    return {"message": "No warnings or errors found to analyze"}
                
                # Analyze with AI
                recommendations = await self.ai_analyzer.analyze_log_entries(error_logs)
                
                # Store recommendations
                stored_count = 0
                for rec in recommendations:
                    try:
                        await self.database.store_recommendation(rec)
                        stored_count += 1
                    except Exception as e:
                        logger.error(f"Failed to store recommendation: {e}")
                
                return {
                    "message": f"Analysis complete. {stored_count} new recommendations generated.",
                    "analyzed_logs": len(error_logs),
                    "recommendations_generated": len(recommendations)
                }
            
            except Exception as e:
                logger.error(f"Error during manual analysis: {e}")
                raise HTTPException(status_code=500, detail="Analysis failed")


# Response models for API documentation
class RecommendationResponse(BaseModel):
    recommendations: List[Recommendation]


class StatsResponse(BaseModel):
    database: dict
    log_monitor_active: bool
    ai_service_available: bool


class AnalysisResponse(BaseModel):
    message: str
    analyzed_logs: int
    recommendations_generated: int