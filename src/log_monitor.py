"""Log monitoring service for Home Assistant logs."""

import asyncio
import logging
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .models import LogEntry, LogLevel

logger = logging.getLogger(__name__)


class LogFileHandler(FileSystemEventHandler):
    """File system event handler for log file changes."""
    
    def __init__(self, log_monitor: 'LogMonitor'):
        self.log_monitor = log_monitor
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path == str(self.log_monitor.log_file_path):
            asyncio.run_coroutine_threadsafe(
                self.log_monitor._process_new_lines(),
                self.log_monitor.loop
            )


class LogMonitor:
    """Monitors Home Assistant log files for new entries."""
    
    def __init__(self, 
                 log_file_path: str = "/config/home-assistant.log",
                 callback: Optional[Callable[[LogEntry], None]] = None):
        self.log_file_path = Path(log_file_path)
        self.callback = callback
        self.observer = None
        self.last_position = 0
        self.loop = None
        
        # Regex patterns for parsing log entries
        self.log_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?)\s+'  # timestamp with optional milliseconds
            r'(\w+)\s+'                                               # log level
            r'\((\w+)\)\s+'                                          # thread
            r'\[([^\]]+)\]\s+'                                       # component
            r'(.+)'                                                  # message
        )
        
        # Alternative pattern for logs without component
        self.simple_log_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?)\s+'  # timestamp with optional milliseconds
            r'(\w+)\s+'                                               # log level
            r'(.+)'                                                  # message
        )
    
    async def start(self):
        """Start monitoring the log file."""
        self.loop = asyncio.get_running_loop()
        
        # Ensure log file exists
        if not self.log_file_path.exists():
            logger.warning(f"Log file not found: {self.log_file_path}")
            return
        
        # Get initial file position
        self.last_position = self.log_file_path.stat().st_size
        
        # Set up file watcher
        self.observer = Observer()
        event_handler = LogFileHandler(self)
        self.observer.schedule(event_handler, str(self.log_file_path.parent), recursive=False)
        self.observer.start()
        
        logger.info(f"Started monitoring log file: {self.log_file_path}")
    
    async def stop(self):
        """Stop monitoring the log file."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Stopped log monitoring")
    
    async def _process_new_lines(self):
        """Process new lines added to the log file."""
        try:
            current_size = self.log_file_path.stat().st_size
            
            if current_size < self.last_position:
                # File was truncated or rotated
                self.last_position = 0
            
            if current_size == self.last_position:
                return
            
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                f.seek(self.last_position)
                new_lines = f.readlines()
                self.last_position = f.tell()
            
            for line in new_lines:
                line = line.strip()
                if line:
                    entry = self._parse_log_line(line)
                    if entry and self.callback:
                        # Process all log levels (INFO, DEBUG, WARNING, ERROR, CRITICAL)
                        await self.callback(entry)
        
        except Exception as e:
            logger.error(f"Error processing log lines: {e}")
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string with optional milliseconds."""
        if '.' in timestamp_str:
            # Format with milliseconds
            return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
        else:
            # Format without milliseconds
            return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    
    def _parse_log_line(self, line: str) -> Optional[LogEntry]:
        """Parse a log line into a LogEntry object."""
        try:
            # Try main pattern first
            match = self.log_pattern.match(line)
            if match:
                timestamp_str, level_str, thread, component, message = match.groups()
                timestamp = self._parse_timestamp(timestamp_str)
                
                try:
                    level = LogLevel(level_str.upper())
                except ValueError:
                    level = LogLevel.INFO
                
                return LogEntry(
                    timestamp=timestamp,
                    level=level,
                    component=component,
                    message=message.strip(),
                    raw_line=line
                )
            
            # Try simple pattern
            match = self.simple_log_pattern.match(line)
            if match:
                timestamp_str, level_str, message = match.groups()
                timestamp = self._parse_timestamp(timestamp_str)
                
                try:
                    level = LogLevel(level_str.upper())
                except ValueError:
                    level = LogLevel.INFO
                
                return LogEntry(
                    timestamp=timestamp,
                    level=level,
                    component=None,
                    message=message.strip(),
                    raw_line=line
                )
            
        except Exception as e:
            logger.debug(f"Failed to parse log line: {line} - {e}")
        
        return None
    
    def generate_log_hash(self, log_entry: LogEntry) -> str:
        """Generate a hash for a log entry to avoid duplicate processing."""
        content = f"{log_entry.level.value}:{log_entry.component}:{log_entry.message}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def read_recent_logs(self, lines: int = 100) -> list[LogEntry]:
        """Read recent log entries from the file."""
        if not self.log_file_path.exists():
            return []
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            entries = []
            for line in recent_lines:
                line = line.strip()
                if line:
                    entry = self._parse_log_line(line)
                    if entry:
                        entries.append(entry)
            
            return entries
        
        except Exception as e:
            logger.error(f"Error reading recent logs: {e}")
            return []