pplication configuration - all values sourced from environment variables."""

import os
import logging
from functools import lru_cache
from typing import List, Optional

logger = logging.getLogger(__name__)


class Settings:
    """
    Central configuration.  All secrets must be supplied via environment
    variables; there are NO hardcoded credential defaults.
    """

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    TITLE: str = "AI Galaxy API"
    VERSION: str = "3.0.0"
    DESCRIPTION: str = "Production-ready AI demo portfolio platform"

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = os.getenv(
        "PGVECTOR_URL", "postgresql://localhost:5432/postgres"
    )
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "portfolio")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    # No default - must be set in every environment.
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_HOST_AUTH_METHOD: str = os.getenv(
        "POSTGRES_HOST_AUTH_METHOD", "scram-sha-256"
    )

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # ------------------------------------------------------------------
    # Authentication - no defaults; must be supplied at runtime
    # ------------------------------------------------------------------
    FULL_PASSWORD: str = os.getenv("FULL_PASSWORD", "")
    ADMIN_KEY: str = os.getenv("ADMIN_KEY", "")

    # API keys: comma-separated list supplied via a single env var.
    API_KEYS: List[str] = [
        k.strip()
        for k in os.getenv("API_KEYS", "").split(",")
        if k.strip()
    ]

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "text-embedding-3-large"
    )
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")

    # ------------------------------------------------------------------
    # Feature flags
    # ------------------------------------------------------------------
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    ENABLE_CACHING: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    ENABLE_LOGGING: bool = os.getenv("ENABLE_LOGGING", "true").lower() == "true"
    ENABLE_SECURITY_HEADERS: bool = (
        os.getenv("ENABLE_SECURITY_HEADERS", "true").lower() == "true"
    )
    ENABLE_RATE_LIMITING: bool = (
        os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
    )

    # ------------------------------------------------------------------
    # Rate limiting
    # RATE_LIMIT_REQUESTS is used by SecurityManager for IP-based limits
    # on demo endpoints.  Full-API limits are enforced separately.
    # ------------------------------------------------------------------
    RATE_LIMIT_REQUESTS: int = int(
        os.getenv("RATE_LIMIT_REQUESTS_DEMO", "100")
    )
    RATE_LIMIT_REQUESTS_FULL: int = int(
        os.getenv("RATE_LIMIT_REQUESTS_FULL", "1000")
    )
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------
    MAX_CONNECTIONS: int = int(os.getenv("MAX_CONNECTIONS", "10"))
    TIMEOUT_SECONDS: int = int(os.getenv("TIMEOUT_SECONDS", "30"))

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------
    PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9090"))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @classmethod
    def validate(cls) -> None:
        """Raise if any required secret is missing or any value is out of range."""
        missing = [
            name
            for name, attr in [
                ("FULL_PASSWORD", cls.FULL_PASSWORD),
                ("ADMIN_KEY", cls.ADMIN_KEY),
                ("POSTGRES_PASSWORD", cls.POSTGRES_PASSWORD),
            ]
            if not attr
        ]
        if missing:
            raise RuntimeError(
                f"Required environment variable(s) not set: {', '.join(missing)}. "
                "Refusing to start."
            )

        if cls.RATE_LIMIT_REQUESTS < 1:
            raise ValueError("RATE_LIMIT_REQUESTS_DEMO must be at least 1")
        if cls.RATE_LIMIT_REQUESTS_FULL < 1:
            raise ValueError("RATE_LIMIT_REQUESTS_FULL must be at least 1")

        if not cls.OPENAI_API_KEY:
            logger.warning(
                "OPENAI_API_KEY is not set - AI features will be unavailable."
            )


# Validate and expose a module-level singleton so other modules can do:
#   from .config import settings
Settings.validate()
settings = Settings()


# ------------------------------------------------------------------
# Cached accessors (kept for backwards compatibility)
# ------------------------------------------------------------------

@lru_cache(maxsize=None)
def get_database_url() -> str:
    return settings.DATABASE_URL


@lru_cache(maxsize=None)
def get_redis_url() -> Optional[str]:
    """Return the Redis URL, or None if Redis is not configured."""
    url = settings.REDIS_URL
    return url if url else None


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
        logger.warning("openai package is not installed; AI features unavailable.")
        return None
