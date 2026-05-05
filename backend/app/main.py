# backend/app/main.py
"""
x1mvp Portfolio - FastAPI Application Factory
Production-ready API with multiple service modules
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# Fix: Import from correct location
from app.nlp import model_manager
from app.core.config import settings

# =============================================================================
# Logging
# =============================================================================
def _configure_logging() -> None:
    log_dir = Path(__file__).parent.parent / "logs"  # Go up one level from app/
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if os.getenv("LOG_TO_FILE", "false").lower() == "true":
        handlers.append(
            logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        )

    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

_configure_logging()
logger = logging.getLogger(__name__)


# =============================================================================
# Lifespan
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting up - loading model")
    model_manager.load()   # no-op in CI because TESTING=true guard fires first
    yield
    logger.info("Shutting down - unloading model")
    model_manager.unload()


# =============================================================================
# App
# =============================================================================
app = FastAPI(
    title="x1mvp Portfolio API",
    description="AI-powered data engineering portfolio with real-time demos",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# =============================================================================
# Exception Handlers
# =============================================================================
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error", "detail": str(exc)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=503,
        content={"error": "Service unavailable", "detail": str(exc)},
    )


# =============================================================================
# Middleware Stack
# =============================================================================
# Get allowed origins from environment
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://x1mvp.github.io,http://localhost:3000,http://localhost:8080",
).split(",")

# 1. CORS middleware (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 2. TrustedHost middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# 3. Custom middleware
try:
    from app.middleware import SecurityHeadersMiddleware, RequestLoggingMiddleware, PerformanceMiddleware
    
    # Security headers first
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Request logging (outer layer)
    app.add_middleware(RequestLoggingMiddleware)
    
    # Performance monitoring (inner layer)
    app.add_middleware(PerformanceMiddleware)
    
    logger.info("✅ Custom middleware stack enabled")
    
except ImportError as e:
    logger.warning(f"⚠️  Custom middleware not available: {e}")

# 4. Rate limiting (optional)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    logger.info("✅ Rate limiting middleware enabled")
    
except ImportError as e:
    logger.warning(f"⚠️  Rate limiting dependencies not installed: {e}")


# =============================================================================
# Routers
# =============================================================================
try:
    from app.routers import crm, fraud, clinical, nlp  # noqa: E402

    app.include_router(crm.router,      prefix="/CRM",      tags=["CRM"])
    app.include_router(fraud.router,    prefix="/Fraud",    tags=["Fraud Detection"])
    app.include_router(clinical.router, prefix="/Clinical", tags=["Clinical"])
    app.include_router(nlp.router,      prefix="/NLP",      tags=["NLP"])

    logger.info("All four service routers registered")

except ImportError as exc:
    logger.error("Failed to import routers: %s", exc)


# =============================================================================
# Health endpoints
# =============================================================================
@app.get("/healthz", tags=["Health"])
async def health_check():
    """Liveness probe used by Cloud Run and uptime monitors."""
    loop = asyncio.get_running_loop()
    return {
        "status": "healthy",
        "version": app.version,
        "services": ["crm", "fraud", "clinical", "nlp"],
        "uptime": loop.time(),
    }


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - satisfies Cloud Run startup probe."""
    return {
        "message": "x1mvp Portfolio API",
        "version": app.version,
        "docs": "/docs",
        "health": "/healthz",
        "endpoints": ["/CRM", "/Fraud", "/Clinical", "/NLP"],
    }


logger.info("FastAPI application configured - ready to serve")
