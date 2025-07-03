"""Pytest configuration file ensuring local package import works regardless of CWD."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    # Prepend so it has priority over any globally installed package version
    sys.path.insert(0, str(PROJECT_ROOT)) 