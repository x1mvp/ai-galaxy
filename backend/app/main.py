# backend/app/main.py
"""
AI Galaxy - FastAPI Application Factory
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

# Windows-compatible imports
try:
    from app.nlp import model_manager
    from app.core.config import settings
except ImportError as e:
    print(f"Import error: {e}")
    print("Current directory:", os.getcwd())
    print("Python path:", sys.path)
    raise

# =============================================================================
# Logging - Windows compatible
# =============================================================================
def _configure_logging() -> None:
    # Windows-compatible path handling
    log_dir = Path(__file__).parent.parent.parent / "logs"
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
    try:
        model_manager.load()
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
    
    yield
    logger.info("Shutting down - unloading model")
    try:
        model_manager.unload()
        logger.info("Model unloaded successfully")
    except Exception as e:
        logger.error(f"Failed to unload model: {e}")


# =============================================================================
# App
# =============================================================================
app = FastAPI(
    title="AI Galaxy Portfolio API",
    description="AI-powered galaxy portfolio with real-time demos",
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


@app.exception_handler(ImportError)
async def import_error_handler(request: Request, exc: ImportError):
    return JSONResponse(
        status_code=500,
        content={"error": "Service configuration error", "detail": "Required modules not available"},
    )


# =============================================================================
# Middleware Stack
# =============================================================================
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://x1mvp.github.io,http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Custom middleware
try:
    from app.middleware import SecurityHeadersMiddleware, RequestLoggingMiddleware, PerformanceMiddleware
    
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(PerformanceMiddleware)
    
    logger.info("✅ Custom middleware stack enabled")
    
except ImportError as e:
    logger.warning(f"⚠️  Custom middleware not available: {e}")

# Rate limiting
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
    from app.routers import crm, fraud, clinical, nlp

    app.include_router(crm.router, prefix="/CRM", tags=["CRM"])
    app.include_router(fraud.router, prefix="/Fraud", tags=["Fraud Detection"])
    app.include_router(clinical.router, prefix="/Clinical", tags=["Clinical"])
    app.include_router(nlp.router, prefix="/NLP", tags=["NLP"])

    logger.info("All four service routers registered")

except ImportError as exc:
    logger.error("Failed to import routers: %s", exc)


# =============================================================================
# Health endpoints
# =============================================================================
@app.get("/healthz", tags=["Health"])
async def health_check():
    """Liveness probe - Windows compatible"""
    try:
        loop = asyncio.get_running_loop()
        uptime = loop.time()
    except RuntimeError:
        # Fallback for older Python versions
        import time
        uptime = time.time()
    
    return {
        "status": "healthy",
        "version": app.version,
        "services": ["crm", "fraud", "clinical", "nlp"],
        "uptime": uptime,
        "platform": "windows"
    }


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - satisfies startup probe"""
    return {
        "message": "AI Galaxy Portfolio API",
        "version": app.version,
        "docs": "/docs",
        "health": "/healthz",
        "endpoints": ["/CRM", "/Fraud", "/Clinical", "/NLP"],
        "platform": "windows"
    }


logger.info("FastAPI application configured - ready to serve")
