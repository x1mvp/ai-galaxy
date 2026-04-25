"""
x1mvp Portfolio - Unified Backend API
Production-ready data engineering portfolio with AI-powered demos

Version: 3.0.0
Author:  x1mvp
License: MIT
"""

# ============================================================================
# Package metadata — the ONLY thing that belongs in __init__.py.
#
# Everything else (logging, FastAPI app, module imports, filesystem ops,
# atexit handlers) has been moved to the modules that own those concerns:
#   - Logging setup      → app/core/config.py  (or app/main.py lifespan)
#   - FastAPI app        → app/main.py
#   - Service routers    → app/main.py (included via include_router)
#   - Health / utils     → app/core/monitoring.py
# ============================================================================

__title__              = "x1mvp Portfolio API"
__description__        = "AI-powered data engineering portfolio with real-time demos"
__version__            = "3.0.0"
__author__             = "x1mvp"
__author_email__       = "vamsimuttineni7@gmail.com"
__license__            = "MIT"
__copyright__          = f"Copyright 2026 {__author__}"
__url__                = "https://x1mvp.dev"
__docs_url__           = "https://docs.x1mvp.dev"
__repository_url__     = "https://github.com/x1mvp/portfolio"
__keywords__           = [
    "data-engineering", "machine-learning", "fastapi", "portfolio",
    "ai", "nlp", "fraud-detection", "clinical-risk", "vector-search",
]

# Semantic versioning
__major_version__      = 3
__minor_version__      = 0
__patch_version__      = 0
__version_info__       = (__major_version__, __minor_version__, __patch_version__)
__python_requires__    = ">=3.9"
__supported_versions__ = ["3.9", "3.10", "3.11", "3.12"]
