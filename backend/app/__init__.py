# empty – just marks the folder as a Python package
"""
x1mvp Portfolio - Unified Backend API
Production-ready data engineering portfolio with AI-powered demos

Version: 3.0.0
Last Updated: 2026-01-15
Author: x1mvp
License: MIT
"""

# ============================================================================
# PACKAGE METADATA
# ============================================================================

__title__ = "x1mvp Portfolio API"
__description__ = "AI-powered data engineering portfolio with real-time demos"
__version__ = "3.0.0"
__author__ = "x1mvp"
__author_email__ = "contact@x1mvp.dev"
__license__ = "MIT"
__copyright__ = f"Copyright 2026 {__author__}"
__url__ = "https://x1mvp.dev"
__docs_url__ = "https://docs.x1mvp.dev"
__repository_url__ = "https://github.com/x1mvp/portfolio"
__keywords__ = [
    "data-engineering", "machine-learning", "fastapi", "portfolio",
    "ai", "nlp", "fraud-detection", "clinical-risk", "vector-search"
]

# ============================================================================
# VERSION AND COMPATIBILITY
# ============================================================================

# Semantic versioning components
__major_version__ = 3
__minor_version__ = 0
__patch_version__ = 0
__version_info__ = (__major_version__, __minor_version__, __patch_version__)

# Python version requirements
__python_requires__ = ">=3.9"

# Supported Python versions
__supported_versions__ = ["3.9", "3.10", "3.11", "3.12"]

# ============================================================================
# IMPORT CONFIGURATION
# ============================================================================

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add package root to Python path for imports
package_root = Path(__file__).parent.absolute()
if str(package_root) not in sys.path:
    sys.path.insert(0, str(package_root))

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

import logging

# Configure package logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(package_root, 'logs', 'package.log'),
            encoding='utf-8'
        )
    ]
)

package_logger = logging.getLogger(__name__)
package_logger.info(f"🚀 {__title__} v{__version__} initialized")

# ============================================================================
# SERVICE MODULES
# ============================================================================

try:
    # Import service modules for unified API
    from . import crm
    from . import fraud
    from . import clinical
    from . import nlp
    
    # Core modules
    from .core import config, security, monitoring
    from .core.middleware import (
        RequestLoggingMiddleware,
        SecurityMiddleware,
        MetricsMiddleware
    )
    
    # Utility modules
    from .utils import helpers, validators
    
    SERVICE_MODULES = {
        'crm': crm,
        'fraud': fraud,
        'clinical': clinical,
        'nlp': nlp
    }
    
    CORE_MODULES = {
        'config': config,
        'security': security,
        'monitoring': monitoring
    }
    
    package_logger.info("✅ All service modules imported successfully")
    
except ImportError as e:
    package_logger.warning(f"⚠️ Some modules not available: {e}")
    SERVICE_MODULES = {}
    CORE_MODULES = {}

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    
    # Initialize FastAPI application
    app = FastAPI(
        title=__title__,
        description=__description__,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure based on environment
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"]
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure based on environment
    )
    
    # Include service routers
    for service_name, service_module in SERVICE_MODULES.items():
        if hasattr(service_module, 'router'):
            app.include_router(
                service_module.router,
                prefix=f"/api/v1/{service_name}",
                tags=[service_module.__name__.split('.')[-1].title()]
            )
            package_logger.info(f"✅ {service_name} router included")
    
    package_logger.info("🎯 FastAPI application configured")
    
except ImportError as e:
    package_logger.error(f"❌ FastAPI configuration failed: {e}")
    app = None

# ============================================================================
# ENVIRONMENT AND CONFIGURATION
# ============================================================================

def get_environment() -> str:
    """Get current environment"""
    return os.getenv("ENVIRONMENT", "development")

def get_config() -> Dict[str, Any]:
    """Get package configuration"""
    return {
        "package": {
            "name": __title__,
            "version": __version__,
            "description": __description__,
            "author": __author__,
            "license": __license__
        },
        "environment": get_environment(),
        "python_version": sys.version,
        "supported_python_versions": __supported_versions__,
        "services": list(SERVICE_MODULES.keys()),
        "core_modules": list(CORE_MODULES.keys()),
        "fastapi_available": app is not None
    }

def is_development() -> bool:
    """Check if running in development mode"""
    return get_environment() == "development"

def is_production() -> bool:
    """Check if running in production mode"""
    return get_environment() == "production"

# ============================================================================
# HEALTH CHECK
# ============================================================================

def get_package_health() -> Dict[str, Any]:
    """Get comprehensive package health status"""
    health_status = {
        "status": "healthy",
        "package": {
            "name": __title__,
            "version": __version__,
            "python_version": sys.version,
            "environment": get_environment()
        },
        "modules": {
            "total_services": len(SERVICE_MODULES),
            "available_services": list(SERVICE_MODULES.keys()),
            "total_core": len(CORE_MODULES),
            "available_core": list(CORE_MODULES.keys())
        },
        "dependencies": {
            "fastapi": app is not None,
            "logging": True,
            "sys_path_configured": str(package_root) in sys.path
        },
        "timestamp": __import__('datetime').datetime.utcnow().isoformat() + "Z"
    }
    
    # Check for any issues
    issues = []
    if not app:
        issues.append("FastAPI not available")
    if not SERVICE_MODULES:
        issues.append("No service modules available")
    
    if issues:
        health_status["status"] = "degraded"
        health_status["issues"] = issues
    
    return health_status

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_service_info(service_name: str) -> Optional[Dict[str, Any]]:
    """Get information about a specific service"""
    service = SERVICE_MODULES.get(service_name)
    if service and hasattr(service, '__doc__'):
        return {
            "name": service_name,
            "description": service.__doc__,
            "module": service.__name__,
            "has_router": hasattr(service, 'router'),
            "file_path": getattr(service, '__file__', 'Unknown')
        }
    return None

def list_all_services() -> List[Dict[str, Any]]:
    """List all available services"""
    services = []
    for service_name in SERVICE_MODULES:
        info = get_service_info(service_name)
        if info:
            services.append(info)
    return services

def get_version_info() -> Dict[str, Any]:
    """Get detailed version information"""
    return {
        "semantic": __version__,
        "components": {
            "major": __major_version__,
            "minor": __minor_version__,
            "patch": __patch_version__
        },
        "full": ".".join(map(str, __version_info__)),
        "build": os.getenv("BUILD_VERSION", "dev"),
        "commit": os.getenv("COMMIT_HASH", "unknown"),
        "built_at": os.getenv("BUILD_DATE", "unknown")
    }

# ============================================================================
# PACKAGE INITIALIZATION
# ============================================================================

def initialize_package() -> None:
    """Initialize package components"""
    try:
        # Create necessary directories
        os.makedirs(package_root / "logs", exist_ok=True)
        os.makedirs(package_root / "temp", exist_ok=True)
        
        # Log initialization
        package_logger.info(f"📦 Package initialized: {__title__} v{__version__}")
        package_logger.info(f"🌍 Environment: {get_environment()}")
        package_logger.info(f"🐍 Python: {sys.version}")
        package_logger.info(f"📂 Package root: {package_root}")
        
        # Log available services
        if SERVICE_MODULES:
            package_logger.info(f"🔧 Available services: {', '.join(SERVICE_MODULES.keys())}")
        
        # Check critical dependencies
        critical_deps = {
            "fastapi": "Web framework",
            "uvicorn": "ASGI server",
            "pydantic": "Data validation"
        }
        
        for dep, description in critical_deps.items():
            try:
                __import__(dep)
                package_logger.info(f"✅ {dep} ({description}) available")
            except ImportError:
                package_logger.warning(f"⚠️ {dep} ({description}) not available")
                
    except Exception as e:
        package_logger.error(f"❌ Package initialization failed: {e}")
        raise

# Auto-initialize package
initialize_package()

# ============================================================================
# PUBLIC API
# ============================================================================

# Define what gets imported with `from package import *`
__all__ = [
    # Package metadata
    "__title__",
    "__version__",
    "__author__",
    "__description__",
    "__license__",
    
    # Version information
    "__version_info__",
    "__python_requires__",
    "__supported_versions__",
    
    # Main application
    "app",
    
    # Service modules
    "crm",
    "fraud", 
    "clinical",
    "nlp",
    "SERVICE_MODULES",
    "CORE_MODULES",
    
    # Utility functions
    "get_environment",
    "get_config",
    "is_development",
    "is_production",
    "get_package_health",
    "get_service_info",
    "list_all_services",
    "get_version_info"
]

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Print package information when run directly
    print(f"""
🚀 {__title__}
📋 Version: {__version__}
👤 Author: {__author__}
📄 License: {__license__}
🌐 Environment: {get_environment()}
📁 Package Root: {package_root}
🔗 Documentation: {__docs_url__}
📦 Repository: {__repository_url__}

💡 Available Services: {', '.join(SERVICE_MODULES.keys())}
⚡ FastAPI Available: {'Yes' if app else 'No'}
    """)
    
    # Show health status
    health = get_package_health()
    print(f"🏥 Health Status: {health['status']}")
    if 'issues' in health:
        print("⚠️ Issues:")
        for issue in health['issues']:
            print(f"  - {issue}")

# ============================================================================
# CLEANUP HANDLING
# ============================================================================

import atexit

def cleanup():
    """Cleanup function called on package exit"""
    try:
        package_logger.info("🧹 Package cleanup initiated")
        
        # Clean up resources
        if app:
            package_logger.info("📋 FastAPI app cleanup completed")
        
        package_logger.info("✅ Package cleanup completed")
        
    except Exception as e:
        package_logger.error(f"❌ Cleanup failed: {e}")

# Register cleanup function
atexit.register(cleanup)
