"""
x1mvp Portfolio - FastAPI Application Factory
Production-ready API with multiple service modules
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Configure logging BEFORE other imports
def _configure_logging() -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers = [logging.StreamHandler(sys.stdout)]

    if os.getenv("LOG_TO_FILE", "false").lower() == "true":
        handlers.append(
            logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

_configure_logging()
logger = logging.getLogger(__name__)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("🚀 Starting up — loading services")
    
    # Load models if available
    try:
        from app.routers.nlp import model_manager
        model_manager.load()
    except ImportError:
        logger.warning("NLP module not available, skipping model loading")
    except Exception as e:
        logger.error(f"Failed to load NLP model: {e}")
    
    yield
    logger.info("🛑 Shutting down — unloading models")
    
    try:
        from app.routers.nlp import model_manager
        model_manager.unload()
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Failed to unload NLP model: {e}")

# Create FastAPI app
app = FastAPI(
    title="x1mvp Portfolio API",
    description="AI-powered data engineering portfolio with real-time demos",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://x1mvp.github.io,http://localhost:3000,http://localhost:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)

# Import and register routers
try:
    from app.routers import crm, fraud, clinical, nlp
    
    app.include_router(crm.router, prefix="/CRM", tags=["CRM"])
    app.include_router(fraud.router, prefix="/Fraud", tags=["Fraud Detection"])
    app.include_router(clinical.router, prefix="/Clinical", tags=["Clinical"])
    app.include_router(nlp.router, prefix="/NLP", tags=["NLP"])
    
    logger.info("✅ All service routers registered")
    
except ImportError as e:
    logger.error(f"Failed to import some routers: {e}")
    logger.warning("Continuing with available routers")

# Health endpoints
@app.get("/healthz", tags=["Health"])
async def health_check():
    """Liveness probe used by Cloud Run and uptime monitors."""
    return {
        "status": "healthy",
        "version": app.version,
        "services": ["crm", "fraud", "clinical", "nlp"],
    }

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint — satisfies Cloud Run startup probe."""
    return {
        "message": "x1mvp Portfolio API",
        "version": app.version,
        "docs": "/docs",
        "health": "/healthz",
        "endpoints": ["/CRM", "/Fraud", "/Clinical", "/NLP"],
    }

logger.info("✅ FastAPI application configured")
