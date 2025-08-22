"""Main application entry point for HA Log Debugger AI."""

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from .database import Database
from .log_monitor import LogMonitor
from .ai_analyzer import AIAnalyzer
from .web_interface import WebInterface

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class HALogDebuggerAI:
    """Main application class."""
    
    def __init__(self):
        self.database = None
        self.log_monitor = None
        self.ai_analyzer = None
        self.web_interface = None
        self.running = False
        
        # Configuration from environment variables
        self.config = {
            "openai_endpoint_url": os.getenv("OPENAI_ENDPOINT_URL"),
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "model_name": os.getenv("MODEL_NAME", "gpt-3.5-turbo"),
            "ha_config_path": os.getenv("HA_CONFIG_PATH", "/config"),
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "web_port": int(os.getenv("WEB_PORT", 8080)),
            "tz": os.getenv("TZ", "UTC"),
            # New configuration options for log capture and AI analysis
            "capture_all_logs": os.getenv("CAPTURE_ALL_LOGS", "true").lower() == "true",
            "ai_analysis_levels": os.getenv("AI_ANALYSIS_LEVELS", "WARNING,ERROR,CRITICAL").split(","),
            "log_retention_days": int(os.getenv("LOG_RETENTION_DAYS", 30))
        }
        
        # Validate required configuration
        if not self.config["openai_endpoint_url"]:
            raise ValueError("OPENAI_ENDPOINT_URL environment variable is required")
        if not self.config["openai_api_key"]:
            raise ValueError("OPENAI_API_KEY environment variable is required")
    
    async def initialize(self):
        """Initialize all application components."""
        logger.info("Initializing HA Log Debugger AI...")
        
        # Initialize database
        self.database = Database()
        await self.database.initialize()
        logger.info("Database initialized")
        
        # Initialize AI analyzer
        self.ai_analyzer = AIAnalyzer(
            endpoint_url=self.config["openai_endpoint_url"],
            api_key=self.config["openai_api_key"],
            model_name=self.config["model_name"]
        )
        
        # Test AI connection
        try:
            ai_available = await self.ai_analyzer.test_connection()
            if ai_available:
                logger.info("AI service connection successful")
            else:
                logger.warning("AI service connection test failed")
        except Exception as e:
            logger.error(f"AI service connection error: {e}")
        
        # Initialize log monitor
        log_file_path = os.path.join(self.config["ha_config_path"], "home-assistant.log")
        self.log_monitor = LogMonitor(
            log_file_path=log_file_path,
            callback=self._process_log_entry
        )
        
        # Initialize web interface
        self.web_interface = WebInterface(
            database=self.database,
            log_monitor=self.log_monitor,
            ai_analyzer=self.ai_analyzer
        )
        
        logger.info("Application initialization complete")
    
    async def _process_log_entry(self, log_entry):
        """Process a new log entry from the monitor."""
        try:
            # Skip processing if capture_all_logs is disabled and this is not a critical level
            if not self.config["capture_all_logs"] and log_entry.level.value not in self.config["ai_analysis_levels"]:
                return
                
            # Generate hash for the log entry
            log_hash = self.log_monitor.generate_log_hash(log_entry)
            
            # Check if already processed
            if await self.database.is_log_processed(log_hash):
                return
            
            # Mark as processed (store all logs if capture_all_logs is enabled)
            await self.database.mark_log_processed(log_entry, log_hash)
            
            # Analyze with AI if the log level is in the configured analysis levels
            if log_entry.level.value in self.config["ai_analysis_levels"]:
                logger.info(f"Processing {log_entry.level.value} from {log_entry.component}: {log_entry.message[:100]}...")
                
                recommendations = await self.ai_analyzer.analyze_log_entries([log_entry])
                
                for recommendation in recommendations:
                    await self.database.store_recommendation(recommendation)
                    logger.info(f"Stored recommendation for {log_entry.component}: {recommendation.issue_summary}")
        
        except Exception as e:
            logger.error(f"Error processing log entry: {e}")
    
    async def start(self):
        """Start all application services."""
        logger.info("Starting HA Log Debugger AI services...")
        self.running = True
        
        # Start log monitoring
        await self.log_monitor.start()
        
        logger.info("All services started successfully")
    
    async def stop(self):
        """Stop all application services."""
        logger.info("Stopping HA Log Debugger AI services...")
        self.running = False
        
        if self.log_monitor:
            await self.log_monitor.stop()
        
        logger.info("All services stopped")
    
    def run_web_server(self):
        """Run the web server."""
        uvicorn.run(
            self.web_interface.app,
            host="0.0.0.0",
            port=self.config["web_port"],
            log_level=self.config["log_level"].lower()
        )


# Global application instance
app_instance = None


async def main():
    """Main application entry point."""
    global app_instance
    
    try:
        # Create and initialize application
        app_instance = HALogDebuggerAI()
        await app_instance.initialize()
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start services
        await app_instance.start()
        
        # Run web server in a separate task
        web_task = asyncio.create_task(
            asyncio.to_thread(app_instance.run_web_server)
        )
        
        logger.info(f"HA Log Debugger AI is running on port {app_instance.config['web_port']}")
        
        # Setup periodic cleanup task
        last_cleanup = datetime.now()
        cleanup_interval_hours = 24  # Run cleanup daily
        
        # Keep the application running
        while app_instance.running:
            await asyncio.sleep(60)  # Check every minute
            
            # Run daily cleanup if needed
            now = datetime.now()
            if (now - last_cleanup).total_seconds() >= cleanup_interval_hours * 3600:
                try:
                    deleted_count = await app_instance.database.cleanup_old_logs(
                        app_instance.config["log_retention_days"]
                    )
                    last_cleanup = now
                except Exception as e:
                    logger.error(f"Error during log cleanup: {e}")
        
        # Cancel web server task
        web_task.cancel()
        try:
            await web_task
        except asyncio.CancelledError:
            pass
    
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


async def shutdown():
    """Graceful shutdown handler."""
    global app_instance
    if app_instance:
        await app_instance.stop()


# FastAPI lifespan manager for uvicorn
@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan manager."""
    global app_instance
    
    if not app_instance:
        app_instance = HALogDebuggerAI()
        await app_instance.initialize()
        await app_instance.start()
    
    yield
    
    if app_instance:
        await app_instance.stop()


def create_app():
    """Create FastAPI app for uvicorn."""
    global app_instance
    
    if not app_instance:
        # This is a synchronous fallback - not ideal but needed for uvicorn
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        app_instance = HALogDebuggerAI()
        loop.run_until_complete(app_instance.initialize())
        loop.run_until_complete(app_instance.start())
    
    return app_instance.web_interface.app


if __name__ == "__main__":
    asyncio.run(main())