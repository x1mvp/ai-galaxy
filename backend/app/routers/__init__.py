"""
app/routers/__init__.py

Routers package initialization.
Exports all router modules for easy import in main application.
"""

from .crm import router as crm_router
from .fraud import router as fraud_router
from .clinical import router as clinical_router
from .nlp import router as nlp_router

__all__ = ["crm_router", "fraud_router", "clinical_router", "nlp_router"]
