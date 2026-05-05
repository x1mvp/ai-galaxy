# backend/tests/__init__.py
"""Test suite for AI Galaxy API"""

import os
import sys

# Add backend to Python path for Windows compatibility
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

__version__ = "3.0.0"
