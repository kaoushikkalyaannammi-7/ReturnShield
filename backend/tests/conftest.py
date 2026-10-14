"""Pytest configuration for ReturnShield test suite."""
import sys
import os
from pathlib import Path

# Add project root and backend directory to sys.path
root_dir = Path(__file__).parent.parent.parent
backend_dir = root_dir / "backend"

sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(backend_dir))
