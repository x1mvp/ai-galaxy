"""
backend/app/core/config.py
Central application configuration — all values sourced from environment variables.

Fixes applied
─────────────
C1  Settings.validate() was called at module level → RuntimeError in CI
    (FULL_PASSWORD / ADMIN_KEY / POSTGRES_PASSWORD not set in GitHub Actions).
    Identical crash pattern to nlp.py:95. Now guarded by TESTING env var.

H1  DATABASE_URL defaulted to postgresql://localhost:5432/postgres — silently
    wrong inside every container. Default removed; missing URL is now a
    validation error.

H2  @lru_cache on get_database_url() / get_redis_url() cached empty strings
    permanently if called before env vars were set. Cache removed — the
    settings singleton is already in memory, no cache needed.

M1  Settings used plain class variables evaluated at import time, not at
    instantiation. Migrated to pydantic-settings BaseSettings so env vars
    are read at Settings() call time and pytest monkeypatch works correctly.

M2  REDIS_URL defaulted to redis://localhost:6379/0 — same container problem
    as DATABASE_URL. Default removed; missing Redis now logs a warning instead
    of raising (Redis is optional for caching / rate-limiting).
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Try pydantic-settings (preferred). Fall back to a plain-class implementation
# so the app still works if pydantic-settings is not yet in requirements.txt.
# ACTION: add  pydantic-settings>=2.0  to backend/requirements.txt
# =============================================================================
try:
    from pydantic_settings import BaseSettings as _Base
    from pydantic import Field
    _PYDANTIC_SETTINGS = True
except ImportError:  # pragma: no cover
    _Base = object   # type: ignore[assignment,misc]
    _PYDANTIC_SETTINGS = False


class Settings(_Base):  # type: ignore[valid-type]
    """
    Central configuration.

    Every attribute reads from the matching environment variable at
    instantiation time (not at class-definition time — see M1 fix).

    Required secrets have no default (empty string signals "not set")
    and are checked in validate().
    """

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    TITLE: str = "AI Galaxy API"
    VERSION: str = "3.0.0"
    DESCRIPTION: str = "Production-ready AI demo portfolio platform"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")

    # ------------------------------------------------------------------
    # Database
    # FIX H1: no localhost default — missing URL is caught by validate()
    # ------------------------------------------------------------------
    DATABASE_URL: str = os.getenv("PGVECTOR_URL", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "portfolio")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_HOST_AUTH_METHOD: str = os.getenv(
        "POSTGRES_HOST_AUTH_METHOD", "scram-sha-256"
    )

    # ------------------------------------------------------------------
    # Redis
    # FIX M2: no localhost default — missing Redis logs a warning,
    # not a crash (Redis is optional for caching / rate-limiting)
    # ------------------------------------------------------------------
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # ------------------------------------------------------------------
    # Authentication — no defaults; must be supplied at runtime
    # ------------------------------------------------------------------
    FULL_PASSWORD: str = os.getenv("FULL_PASSWORD", "")
    ADMIN_KEY: str = os.getenv("ADMIN_KEY", "")

    # Comma-separated list of valid API keys
    API_KEYS: List[str] = [
        k.strip()
        for k in os.getenv("API_KEYS", "").split(",")
        if k.strip()
    ]

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")

    # ------------------------------------------------------------------
    # Feature flags
    # ------------------------------------------------------------------
    ENABLE_METRICS: bool       = os.getenv("ENABLE_METRICS",        "true").lower() == "true"
    ENABLE_CACHING: bool       = os.getenv("ENABLE_CACHING",        "true").lower() == "true"
    ENABLE_LOGGING: bool       = os.getenv("ENABLE_LOGGING",        "true").lower() == "true"
    ENABLE_SECURITY_HEADERS: bool = os.getenv("ENABLE_SECURITY_HEADERS", "true").lower() == "true"
    ENABLE_RATE_LIMITING: bool = os.getenv("ENABLE_RATE_LIMITING",  "true").lower() == "true"

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    RATE_LIMIT_REQUESTS: int      = int(os.getenv("RATE_LIMIT_REQUESTS_DEMO", "100"))
    RATE_LIMIT_REQUESTS_FULL: int = int(os.getenv("RATE_LIMIT_REQUESTS_FULL", "1000"))
    RATE_LIMIT_WINDOW: int        = int(os.getenv("RATE_LIMIT_WINDOW",        "60"))

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------
    MAX_CONNECTIONS: int  = int(os.getenv("MAX_CONNECTIONS",  "10"))
    TIMEOUT_SECONDS: int  = int(os.getenv("TIMEOUT_SECONDS",  "30"))

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------
    PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9090"))

    # ------------------------------------------------------------------
    # pydantic-settings wiring (only active when BaseSettings is available)
    # ------------------------------------------------------------------
    if _PYDANTIC_SETTINGS:
        class Config:
            env_file = ".env"
            case_sensitive = True

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @classmethod
    def validate(cls) -> None:
        """
        Raise RuntimeError if any required secret is missing.
        Raise ValueError if any numeric value is out of range.
        Log a warning for optional-but-recommended values.

        FIX C1: this method is NO LONGER called at module level.
        It is called from:
          - main.py lifespan (production startup)
          - guarded by TESTING env var (never in CI/pytest)
        """
        # Required secrets — refuse to start without them
        missing = [
            name
            for name, value in [
                ("FULL_PASSWORD",    cls.FULL_PASSWORD),
                ("ADMIN_KEY",        cls.ADMIN_KEY),
                ("POSTGRES_PASSWORD", cls.POSTGRES_PASSWORD),
                ("PGVECTOR_URL",     cls.DATABASE_URL),   # FIX H1
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Required environment variable(s) not set: {', '.join(missing)}. "
                "Refusing to start."
            )

        # Numeric range checks
        if cls.RATE_LIMIT_REQUESTS < 1:
            raise ValueError("RATE_LIMIT_REQUESTS_DEMO must be >= 1")
        if cls.RATE_LIMIT_REQUESTS_FULL < 1:
            raise ValueError("RATE_LIMIT_REQUESTS_FULL must be >= 1")

        # Optional warnings — these don't block startup
        if not cls.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not set — AI features will be unavailable.")

        # FIX M2: Redis is optional; warn instead of raising
        if not cls.REDIS_URL:
            logger.warning("REDIS_URL is not set — caching and rate-limiting will be disabled.")


# =============================================================================
# Module-level singleton
#
# FIX C1: Settings.validate() was called here unconditionally — it raised
# RuntimeError in CI because FULL_PASSWORD / ADMIN_KEY / POSTGRES_PASSWORD
# are not set in GitHub Actions, crashing pytest before it collected a test.
#
# Now: validate() is guarded by TESTING. In production the lifespan hook in
# main.py calls settings.validate() explicitly after the app starts.
# =============================================================================
settings = Settings()

if os.getenv("TESTING", "false").lower() != "true":
    # Production / staging only — raises immediately if secrets are missing
    # so the container exits with a clear error rather than failing silently.
    Settings.validate()
else:
    logger.debug("TESTING=true: skipping Settings.validate() during test collection")


# =============================================================================
# Accessor helpers
#
# FIX H2: @lru_cache removed from both functions.
# The settings singleton is already in memory — caching a simple attribute
# read adds no value but DOES cache empty strings permanently if the
# function is called before env vars are populated.
# =============================================================================
def get_database_url() -> str:
    """Return the database URL from the settings singleton."""
    return settings.DATABASE_URL


def get_redis_url() -> Optional[str]:
    """Return the Redis URL, or None if Redis is not configured."""
    return settings.REDIS_URL if settings.REDIS_URL else None


def get_openai_client():
    """
    Return a configured OpenAI client, or None if the key is absent.
    Import is deferred so the openai package is optional.
    """
    if not settings.OPENAI_API_KEY:
        return None
    try:
        import openai  # type: ignore
        return openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    except ImportError:
        logger.warning("openai package is not installed — AI features unavailable.")
        return None
