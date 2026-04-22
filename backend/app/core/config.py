"""Application configuration"""

import os
from functools import lru_cache
from typing import List, Optional

class Settings:
    """Application settings"""
    
    # Basic configuration
    TITLE: str = "x1mvp Portfolio API"
    VERSION: str = "3.0.0"
    DESCRIPTION: str = "AI-powered data engineering portfolio"
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"
    
    # Security
    FULL_PASSWORD: str = os.getenv("FULL_PASSWORD", "galaxy2026")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    API_KEYS: List[str] = os.getenv("API_KEYS", "demo-key-123").split(",")
    
    # CORS
    ALLOWED_ORIGINS: List[str] = os.getenv(
        "ALLOWED_ORIGINS", 
        "http://localhost:3000,https://x1mvp.dev"
    ).split(",")
    ALLOWED_HOSTS: List[str] = os.getenv(
        "ALLOWED_HOSTS", 
        "localhost,127.0.0.1,x1mvp.dev,api.x1mvp.dev"
    ).split(",")
    
    # Rate limiting
    ENABLE_RATE_LIMITING: bool = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    
    # Features
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    
    # Performance
    MAX_REQUEST_SIZE: int = int(os.getenv("MAX_REQUEST_SIZE", "10485760"))  # 10MB
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings"""
    return Settings()

settings = get_settings()
