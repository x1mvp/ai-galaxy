"""
x1mvp Portfolio — FastAPI application factory.

Owns:
  - Logging configuration (file + stream, directory created safely)
  - FastAPI app creation and middleware
  - Lifespan (model load/unload)
  - Router registration
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

from app.nlp import model_manager


# ============================================================================
# Logging — set up BEFORE anything else so every module gets a handler.
# The logs/ directory is created here (not in __init__.py) so it only
# happens when the app actually starts, never during test collection.
# ============================================================================

def _configure_logging() -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    # Only attach a file handler when explicitly requested (e.g. production).
    # In CI / test environments LOG_TO_FILE defaults to "false" so the
    # filesystem is never touched during pytest collection.
    if os.getenv("LOG_TO_FILE", "false").lower() == "true":
        handlers.append(
            logging.FileHandler(log_dir / "package.log", encoding="utf-8")
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,   # override any root-logger config set by imported libs
    )


_configure_logging()
logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("🚀 Starting up — loading model")
    model_manager.load()
    yield
    logger.info("🛑 Shutting down — unloading model")
    model_manager.unload()


# ============================================================================
# Application
# ============================================================================

app = FastAPI(
    title="x1mvp Portfolio API",
    description="AI-powered data engineering portfolio with real-time demos",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)


# ============================================================================
# Routers — imported here (not in __init__.py) so missing sub-modules only
# break the specific router, not the entire package import.
# ============================================================================

from app.router import router as nlp_router   # noqa: E402
app.include_router(nlp_router)

logger.info("✅ FastAPI application configured")
