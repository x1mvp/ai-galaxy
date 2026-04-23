"""Enhanced configuration with complete environment variable handling"""
import os
from functools import lru_cache
from typing import Optional

class Settings:
    """Configuration class with complete environment variable support"""
    
    # Base Configuration
    TITLE: str = "AI Galaxy API"
    VERSION: str = "3.0.0"
    DESCRIPTION: str = "Production-ready AI demo portfolio platform"
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("PGVECTOR_URL", "postgresql://localhost:5432/postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "portfolio")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")
    POSTGRES_HOST_AUTH_METHOD: str = os.getenv("POSTGRES_HOST_AUTH_METHOD", "trust")
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # Authentication
    FULL_PASSWORD: str = os.getenv(" FULL_PASSWORD", "galaxy2026")
    ADMIN_KEY: str = os.getenv("ADMIN_KEY", "admin123")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")
    
    # Feature Flags
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    ENABLE_CACHING: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    ENABLE_LOGGING: bool = os.getenv("ENABLE_LOGGING", "true").lower() == "true"
    ENABLE_SECURITY_HEADERS: bool = os.getenv("ENABLE_SECURITY_HEADERS", "true").lower() == "true"
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_DEMO: int = int(os.getenv("RATE_LIMIT_REQUESTS_DEMO", "100"))
    RATE_LIMIT_REQUESTS_FULL: int = int(os.getenv("RATE_LIMIT_REQUESTS_FULL", "1000"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    
    # Performance
    MAX_CONNECTIONS: int = int(os.getenv("MAX_CONNECTIONS", "10"))
    TIMEOUT_SECONDS: int = int(os.getenv("TIMEOUT_SECONDS", "30"))
    
    # Monitoring
    PROMETRICS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9090"))
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration"""
        if not cls.FULL_PASSWORD:
            raise ValueError("FULL_PASSWORD is required")
        
        if not cls.OPENAI_API_KEY and cls.ENABLE_CACHING:
            print("Warning: OPENAI_API_KEY not set but caching is enabled")
        
        if cls.RATE_LIMIT_REQUESTS_DEMO < 1:
            raise ValueError("RATE_LIMIT_REQUESTS_DEMO must be at least 1")
        
        if cls.RATE_LIMIT_REQUESTS_FULL < 1:
            raise ValueError("RATE_LIMIT_REQUESTS_FULL must be at least 1")

# Validate configuration on import
Settings.validate()

@lru_cache(maxsize=None)
def get_database_url() -> str:
    """Get database URL with validation"""
    return Settings.DATABASE_URL

@lru_cache(maxsize=None)
def get_redis_url() -> Optional[str]:
    """Get Redis URL if enabled"""
    return Settings.REDIS_URL if Settings.REDIS_DB > 0 else None

@lru_cache(maxsize=None)
def get_openai_client() -> Optional[str]:
    """Get OpenAI API key if configured"""
    return Settings.OPENAI_API_KEY or None
