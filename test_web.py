#!/usr/bin/env python3
"""Quick test of the web interface."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import Database
from src.web_interface import WebInterface
import uvicorn

async def test_web_interface():
    """Test the web interface startup."""
    print("🌐 Testing web interface startup...")
    
    # Initialize database
    db = Database("test-data/test.db")
    await db.initialize()
    
    # Create web interface
    web_interface = WebInterface(db)
    
    print("✅ Web interface ready!")
    print(f"📄 Static files should be served from: {Path('static').absolute()}")
    print(f"📊 Test config directory: {Path('test-config').absolute()}")
    
    return web_interface.app

if __name__ == "__main__":
    # Set test environment variables
    os.environ.setdefault("OPENAI_ENDPOINT_URL", "https://api.openai.com/v1")
    os.environ.setdefault("OPENAI_API_KEY", "test-key-for-demo")
    os.environ.setdefault("HA_CONFIG_PATH", "test-config")
    
    app = asyncio.run(test_web_interface())
    
    print("🚀 Starting web server on http://localhost:8080")
    print("   ℹ️  This is a test run - AI functionality won't work without valid API key")
    print("   🛑 Press Ctrl+C to stop")
    
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")