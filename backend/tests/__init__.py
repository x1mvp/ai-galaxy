# backend/tests/__init__.py
"""
Test suite for x1mvp Portfolio API
"""

import os
import sys

# Add backend to path for imports
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

__version__ = "3.0.0"
