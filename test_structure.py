#!/usr/bin/env python3
# test_structure.py
"""
Test script for Windows - verifies project structure and imports
"""

import os
import sys
import traceback
from pathlib import Path

def test_windows_imports():
    """Test that all modules can be imported correctly on Windows"""
    
    print("🔍 Testing Windows-compatible imports...")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python version: {sys.version}")
    
    # Add backend to path (Windows compatible)
    backend_path = Path.cwd() / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    
    print(f"Backend path added: {backend_path}")
    print(f"Python path: {sys.path[:3]}...")  # Show first 3 entries
    
    try:
        # Test main app import
        print("\n📦 Testing main app import...")
        from app.main import app
        print("✅ FastAPI app imports successfully")
        
        # Test individual components
        print("\n🧠 Testing model manager...")
        from app.nlp import model_manager
        print("✅ Model manager imports successfully")
        
        print("\n🔧 Testing middleware...")
        from app.middleware import PerformanceMiddleware
        print("✅ Middleware imports successfully")
        
        print("\n🛣️  Testing routers...")
        from app.routers import crm_router, fraud_router, clinical_router, nlp_router
        print("✅ All routers import successfully")
        
        print("\n⚙️  Testing configuration...")
        from app.core.config import settings
        print("✅ Configuration imports successfully")
        
        print("\n🎉 All imports successful on Windows!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        
        # Debug: Check if directories exist
        print(f"\n📁 Directory check:")
        print(f"backend/app exists: {(Path.cwd() / 'backend' / 'app').exists()}")
        print(f"backend/app/main.py exists: {(Path.cwd() / 'backend' / 'app' / 'main.py').exists()}")
        
        return False

def test_windows_paths():
    """Test Windows path handling"""
    print("\n🛠️  Testing Windows path handling...")
    
    # Test path creation
    test_dir = Path.cwd() / "test_logs"
    test_dir.mkdir(exist_ok=True)
    print(f"✅ Test directory created: {test_dir}")
    
    # Test file creation
    test_file = test_dir / "test.txt"
    test_file.write_text("Windows test file", encoding="utf-8")
    print(f"✅ Test file created: {test_file}")
    
    # Clean up
    test_file.unlink()
    test_dir.rmdir()
    print("✅ Cleanup completed")

if __name__ == "__main__":
    print("🚀 Starting Windows structure test...")
    
    success = test_windows_imports()
    test_windows_paths()
    
    if success:
        print("\n🎊 All tests passed! Your Windows setup is ready!")
    else:
        print("\n💥 Some tests failed. Check the errors above.")
    
    sys.exit(0 if success else 1)
