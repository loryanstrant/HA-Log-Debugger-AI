"""Data models for the HA Log Debugger AI application."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class LogLevel(str, Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEntry(BaseModel):
    """Represents a log entry from Home Assistant."""
    timestamp: datetime
    level: LogLevel
    component: Optional[str] = None
    message: str
    raw_line: str


class Recommendation(BaseModel):
    """Represents an AI-generated recommendation for a log issue."""
    id: Optional[int] = None
    log_entry_hash: str  # Hash of the original log entry
    issue_summary: str
    recommendation: str
    severity: str
    created_at: datetime
    resolved: bool = False


class AnalysisRequest(BaseModel):
    """Request model for AI analysis."""
    log_entries: list[LogEntry]


class AnalysisResponse(BaseModel):
    """Response model from AI analysis."""
    recommendations: list[Recommendation]


class HealthStatus(BaseModel):
    """Application health status."""
    status: str
    log_monitor_active: bool
    ai_service_available: bool
    database_connected: bool
    last_log_entry: Optional[datetime] = None
    recommendations_count: int = 0