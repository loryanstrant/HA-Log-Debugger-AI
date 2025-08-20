#!/usr/bin/env python3
"""Entry point for the HA Log Debugger AI application."""

import sys
from pathlib import Path

# Add src to path for relative imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())