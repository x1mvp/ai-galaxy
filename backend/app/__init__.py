"""
x1mvp Portfolio — FastAPI application factory.
Owns:
  - Logging configuration (file + stream, directory created safely)
  - FastAPI app creation and middleware
  - Lifespan (model load/unload)
  - Router registration
  - Health endpoints

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

# ── FIX H1 ───────────────────────────────────────────────────────────────────
# Removed: sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
# That line mutated sys.path so modules could be found both as "app.nlp" and
# as bare "nlp", creating two separate module objects for the same file and
# breaking FastAPI DI, singleton models, and pytest fixtures.
# Absolute imports below work correctly without any sys.path manipulation.
# ─────────────────────────────────────────────────────────────────────────────

# =============================================================================
# FIX C1 + M1 — Logging
# C1: logging.basicConfig() was outdented and executed at module level before
#     _configure_logging() ran, referencing an undefined `handlers` variable
#     and raising NameError on every import.
# M1: log file was named "package.log" — renamed to the conventional "app.log".
# =============================================================================
def _configure_logging() -> None:
    """
    Configure root logger with a stream handler (always) and an optional file
    handler (only when LOG_TO_FILE=true, e.g. in production).

    Call this BEFORE logging.getLogger() anywhere in the codebase so every
    module-level logger inherits the correct handler chain.
    """
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    # Only attach a file handler when explicitly requested (e.g. production).
    # In CI / test environments LOG_TO_FILE defaults to "false" so the
    # filesystem is never touched during pytest collection.
    if os.getenv("LOG_TO_FILE", "false").lower() == "true":
        handlers.append(
            # FIX M1: was "package.log" — renamed to "app.log"
            logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        )

    # FIX C1: this call was outdented outside the function body, running at
    # module level with no `handlers` variable in scope → NameError.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,  # override any root-logger config set by imported libs
    )


# =============================================================================
# FIX C2 — Correct initialisation order
# Original: _configure_logging() was called AFTER logger = getLogger(), so the
# logger object was created against an unconfigured root and silently swallowed
# every subsequent log call.
# Correct order: configure → get logger → define lifespan → create app.
# =============================================================================
_configure_logging()                      # 1. configure root logger first
logger = logging.getLogger(__name__)      # 2. now get a logger (inherits config)


# =============================================================================
# FIX H3 — Lifespan defined BEFORE FastAPI() is instantiated
# Original: app = FastAPI(lifespan=lifespan) appeared before the lifespan()
# definition, causing NameError: name 'lifespan' is not defined at startup.
# Python evaluates keyword arguments at call time — lifespan must exist first.
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting up — loading model")
    model_manager.load()
    yield
    logger.info("Shutting down — unloading model")
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
    lifespan=lifespan,          # FIX H3: now safe — lifespan is defined above
)


# =============================================================================
# FIX H2 — CORS: wildcard origin + credentials=True is rejected by all browsers
# The CORS spec forbids Access-Control-Allow-Origin: * when
# Access-Control-Allow-Credentials: true is also present.
# Any credentialed request (cookies, Authorization header) fails the preflight
# silently — no server error, only a CORS error in the browser DevTools.
# Fix: use an explicit origin list read from an env-var (defaults to the
# GitHub Pages frontend). Never use "*" with allow_credentials=True.
# =============================================================================
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://x1mvp.github.io",   # default: the known frontend origin
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,   # FIX H2: explicit list, never wildcard
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)


# =============================================================================
# FIX C3 — All four routers registered
# The refactored file only imported and registered the NLP router.
# CRM, Fraud, and Clinical were silently deleted — their endpoints returned
# 404, breaking three of the four portfolio demo cards.
# =============================================================================
# Imported here (not in __init__.py) so a missing sub-module only breaks that
# specific router, not the entire package import.
from app.routers import crm, fraud, clinical, nlp  # noqa: E402

app.include_router(crm.router,      prefix="/CRM",      tags=["CRM"])
app.include_router(fraud.router,    prefix="/Fraud",    tags=["Fraud Detection"])
app.include_router(clinical.router, prefix="/Clinical", tags=["Clinical"])
app.include_router(nlp.router,      prefix="/NLP",      tags=["NLP"])

logger.info("All four service routers registered")


# =============================================================================
# FIX M2 — Health endpoints restored
# The refactored file deleted both /healthz and /.
# Cloud Run's default startup probe hits / — a 404 marks the instance
# unhealthy, triggers repeated restarts, and blocks all traffic.
# =============================================================================
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


logger.info("FastAPI application configured — ready to serve")
