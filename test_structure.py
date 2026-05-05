# test_structure.py
#!/usr/bin/env python3
"""Test the project structure and imports"""

import os
import sys

def test_imports():
    """Test that all modules can be imported correctly"""
    
    # Add backend to path
    backend_path = os.path.join(os.getcwd(), "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    
    try:
        # Test main app import
        from app.main import app
        print("✅ FastAPI app imports successfully")
        
        # Test individual components
        from app.nlp import model_manager
        print("✅ Model manager imports successfully")
        
        from app.middleware import PerformanceMiddleware
        print("✅ Middleware imports successfully")
        
        from app.routers import crm_router, fraud_router, clinical_router, nlp_router
        print("✅ All routers import successfully")
        
        from app.core.config import settings
        print("✅ Configuration imports successfully")
        
        print("\n🎉 All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
