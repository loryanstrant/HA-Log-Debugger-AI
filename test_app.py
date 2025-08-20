#!/usr/bin/env python3
"""Test script to validate the HA Log Debugger AI application."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import Database
from src.log_monitor import LogMonitor
from src.models import LogEntry, LogLevel
from src.web_interface import WebInterface

async def test_basic_functionality():
    """Test basic functionality of all components."""
    print("🧪 Testing HA Log Debugger AI components...")
    
    # Test database
    print("  📄 Testing database...")
    with tempfile.TemporaryDirectory() as temp_dir:
        db = Database(f"{temp_dir}/test.db")
        await db.initialize()
        
        # Test storing a recommendation
        from src.models import Recommendation
        from datetime import datetime
        
        rec = Recommendation(
            log_entry_hash="test123",
            issue_summary="Test issue",
            recommendation="Test recommendation",
            severity="MEDIUM",
            created_at=datetime.now(),
            resolved=False
        )
        
        rec_id = await db.store_recommendation(rec)
        print(f"    ✅ Stored recommendation with ID: {rec_id}")
        
        # Test retrieving recommendations
        recommendations = await db.get_recommendations()
        print(f"    ✅ Retrieved {len(recommendations)} recommendations")
    
    # Test log monitor (without file watching)
    print("  📊 Testing log monitor...")
    log_monitor = LogMonitor("/tmp/nonexistent.log")
    
    # Test log parsing
    test_line = "2024-08-20 12:00:00 ERROR (MainThread) [test.component] Test error message"
    entry = log_monitor._parse_log_line(test_line)
    
    if entry:
        print(f"    ✅ Parsed log entry: {entry.level} - {entry.message[:50]}...")
    else:
        print("    ❌ Failed to parse log entry")
        return False
    
    # Test web interface initialization
    print("  🌐 Testing web interface...")
    try:
        web_interface = WebInterface(db)
        print("    ✅ Web interface initialized successfully")
    except Exception as e:
        print(f"    ❌ Web interface initialization failed: {e}")
        return False
    
    print("✅ All basic tests passed!")
    return True

async def main():
    """Main test function."""
    success = await test_basic_functionality()
    if success:
        print("\n🎉 Application components are working correctly!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))