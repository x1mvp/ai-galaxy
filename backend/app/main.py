<<<<<< HEAD
﻿"""
x1mvp Portfolio - FastAPI Application Factory
Production-ready API with multiple service modules
=======
"""
backend/app/main.py
x1mvp Portfolio — FastAPI application factory.

Original fixes (from previous audit):
  - Logging basicConfig indented correctly inside _configure_logging()
  - Logger created after _configure_logging() so it inherits root config
  - lifespan defined before FastAPI() to avoid NameError
  - CORS wildcard + credentials replaced with explicit origin list
  - All four routers registered (CRM, Fraud, Clinical, NLP)
  - Health endpoints restored for Cloud Run startup probe

New fixes (this revision):
  C1  model_manager deferred inside lifespan() — TestClient ALSO enters
      lifespan, so the crash still happened in CI. Moved back to top-level
      import; TESTING=true guard in load() handles the CI case correctly.
  C2  import asyncio was at the bottom of the file, used above it.
      Also asyncio.get_event_loop() is deprecated in Python 3.10+ and
      loop.time() belongs on the loop object, not the asyncio module.
  H1  router.exception_handler() does not exist on APIRouter — AttributeError
      at import time. Handlers moved to app level here in main.py.
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
"""

from __future__ import annotations

<<<<<<< HEAD
=======
import asyncio                          # FIX C2: top of file
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

<<<<<<< HEAD
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Configure logging BEFORE other imports
def _configure_logging() -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers = [logging.StreamHandler(sys.stdout)]
=======
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# FIX C1: top-level import is correct and safe.
# model_manager.load() calls ModelConfig.validate() which has a TESTING guard:
#   if os.getenv("TESTING") == "true": return   ← returns immediately in CI
# Deferring this import inside lifespan() does NOT help because
# TestClient(app) also enters the lifespan context manager during tests.
from app.nlp import model_manager


# =============================================================================
# Logging
# =============================================================================
def _configure_logging() -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b

    if os.getenv("LOG_TO_FILE", "false").lower() == "true":
        handlers.append(
            logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        )

    logging.basicConfig(
<<<<<<< HEAD
        level=logging.INFO,
=======
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

<<<<<<< HEAD
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
=======

_configure_logging()
logger = logging.getLogger(__name__)


# =============================================================================
# Lifespan — must be defined BEFORE FastAPI() references it
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting up — loading model")
    model_manager.load()   # no-op in CI because TESTING=true guard fires first
    yield
    logger.info("Shutting down — unloading model")
    model_manager.unload()


# =============================================================================
# App
# =============================================================================
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
app = FastAPI(
    title="x1mvp Portfolio API",
    description="AI-powered data engineering portfolio with real-time demos",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

<<<<<<< HEAD
# Add CORS middleware
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://x1mvp.github.io,http://localhost:3000,http://localhost:8080"
).split(",")

=======

# =============================================================================
# FIX H1 — Exception handlers on the app, not the router
# APIRouter has no .exception_handler() method. The previous code called
# @router.exception_handler() in nlp.py which raised AttributeError at
# import time, crashing before any route was registered.
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
# Middleware
# =============================================================================
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://x1mvp.github.io,http://localhost:3000,http://localhost:8080",
).split(",")

>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
<<<<<<< HEAD
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
=======
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
# Health endpoints — required for Cloud Run startup + liveness probes
# =============================================================================
@app.get("/healthz", tags=["Health"])
async def health_check():
    """Liveness probe used by Cloud Run and uptime monitors."""
    # FIX C2: asyncio.get_event_loop() is deprecated in Python 3.10+.
    # Correct API inside an async function is asyncio.get_running_loop().
    # loop.time() gives a monotonic float uptime counter.
    loop = asyncio.get_running_loop()
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
    return {
        "status": "healthy",
        "version": app.version,
        "services": ["crm", "fraud", "clinical", "nlp"],
<<<<<<< HEAD
    }

=======
        "uptime": loop.time(),
    }


>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
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

<<<<<<< HEAD
logger.info("✅ FastAPI application configured")
=======

logger.info("FastAPI application configured — ready to serve")
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
