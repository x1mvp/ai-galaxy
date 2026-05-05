# backend/app/__init__.py
"""x1mvp Portfolio API Application"""

__version__ = "3.0.0"
__title__ = "x1mvp Portfolio API"
__description__ = "AI-powered data engineering portfolio with real-time demos"


"""
x1mvp Portfolio - FastAPI application factory.
Owns:
  - Logging configuration (file + stream, directory created safely)
  - FastAPI app creation and middleware
  - Lifespan (model load/unload)
  - Router registration
  - Health endpoints

Fixes applied vs the live version in the repo:
  BUG 1 - SyntaxError: module docstring opening triple-quote was missing.
           The file began with plain text, then a bare closing triple-quote
           which Python read as an OPENING triple-quote, turning all the
           code below into one giant unterminated string.
  BUG 2 - model_manager referenced in lifespan() but never imported.
           Added: from app.nlp import model_manager
  BUG 3 - root() returned version as a string literal "app.version"
           instead of the FastAPI attribute app.version.
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

# BUG 2 FIX: import at top level - safe because model_manager.load()
# checks TESTING=true and skips file-existence validation in CI.
from app.nlp import model_manager


# =============================================================================
# Logging
# =============================================================================
def _configure_logging() -> None:
    log_dir = Path(__file__).parent / "logs"
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
# Lifespan - defined before FastAPI() to avoid NameError
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting up - loading model")
    model_manager.load()
    yield
    logger.info("Shutting down - unloading model")
    model_manager.unload()


# =============================================================================
# Application
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
# Exception handlers - on app instance, not router
# APIRouter has no exception_handler() method.
# =============================================================================
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error", "detail": str(exc)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "Service unavailable", "detail": str(exc)},
    )


# =============================================================================
# Middleware
# =============================================================================
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://x1mvp.github.io,http://localhost:3000,http://localhost:8080",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


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
# Health endpoints - required for Cloud Run startup + liveness probes
# =============================================================================
@app.get("/healthz", tags=["Health"])
async def health_check() -> dict:
    loop = asyncio.get_running_loop()
    return {
        "status": "healthy",
        "version": app.version,
        "services": ["crm", "fraud", "clinical", "nlp"],
        "uptime": loop.time(),
    }


@app.get("/", tags=["Health"])
async def root() -> dict:
    return {
        "message": "x1mvp Portfolio API",
        "version": app.version,   # BUG 3 FIX: was the string "app.version"
        "docs": "/docs",
        "health": "/healthz",
        "endpoints": ["/CRM", "/Fraud", "/Clinical", "/NLP"],
    }


logger.info("FastAPI application configured - ready to serve")
