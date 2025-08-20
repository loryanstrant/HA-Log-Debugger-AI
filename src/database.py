"""Database operations for storing recommendations and log entries."""

import aiosqlite
import json
import logging
from datetime import datetime
from typing import List, Optional
from .models import Recommendation, LogEntry

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for the application."""
    
    def __init__(self, db_path: str = "/data/ha_log_debugger.db"):
        self.db_path = db_path
        
    async def initialize(self):
        """Initialize the database and create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            # Create recommendations table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_entry_hash TEXT NOT NULL,
                    issue_summary TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Create log entries table for tracking processed entries
            await db.execute("""
                CREATE TABLE IF NOT EXISTS processed_logs (
                    hash TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    level TEXT NOT NULL,
                    component TEXT,
                    message TEXT NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info("Database initialized successfully")
    
    async def store_recommendation(self, recommendation: Recommendation) -> int:
        """Store a recommendation in the database."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO recommendations (log_entry_hash, issue_summary, recommendation, severity, created_at, resolved)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                recommendation.log_entry_hash,
                recommendation.issue_summary,
                recommendation.recommendation,
                recommendation.severity,
                recommendation.created_at,
                recommendation.resolved
            ))
            await db.commit()
            return cursor.lastrowid
    
    async def get_recommendations(self, limit: int = 50, resolved: Optional[bool] = None) -> List[Recommendation]:
        """Get recommendations from the database."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            query = "SELECT * FROM recommendations"
            params = []
            
            if resolved is not None:
                query += " WHERE resolved = ?"
                params.append(resolved)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                
                recommendations = []
                for row in rows:
                    recommendations.append(Recommendation(
                        id=row['id'],
                        log_entry_hash=row['log_entry_hash'],
                        issue_summary=row['issue_summary'],
                        recommendation=row['recommendation'],
                        severity=row['severity'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        resolved=bool(row['resolved'])
                    ))
                
                return recommendations
    
    async def mark_resolved(self, recommendation_id: int) -> bool:
        """Mark a recommendation as resolved."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE recommendations SET resolved = TRUE WHERE id = ?
            """, (recommendation_id,))
            await db.commit()
            return cursor.rowcount > 0
    
    async def is_log_processed(self, log_hash: str) -> bool:
        """Check if a log entry has already been processed."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM processed_logs WHERE hash = ?", (log_hash,)) as cursor:
                return await cursor.fetchone() is not None
    
    async def mark_log_processed(self, log_entry: LogEntry, log_hash: str):
        """Mark a log entry as processed."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO processed_logs (hash, timestamp, level, component, message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                log_hash,
                log_entry.timestamp,
                log_entry.level.value,
                log_entry.component,
                log_entry.message
            ))
            await db.commit()
    
    async def get_stats(self) -> dict:
        """Get database statistics."""
        async with aiosqlite.connect(self.db_path) as db:
            # Get total recommendations
            async with db.execute("SELECT COUNT(*) FROM recommendations") as cursor:
                total_recommendations = (await cursor.fetchone())[0]
            
            # Get unresolved recommendations
            async with db.execute("SELECT COUNT(*) FROM recommendations WHERE resolved = FALSE") as cursor:
                unresolved_recommendations = (await cursor.fetchone())[0]
            
            # Get processed logs count
            async with db.execute("SELECT COUNT(*) FROM processed_logs") as cursor:
                processed_logs = (await cursor.fetchone())[0]
            
            return {
                "total_recommendations": total_recommendations,
                "unresolved_recommendations": unresolved_recommendations,
                "processed_logs": processed_logs
            }