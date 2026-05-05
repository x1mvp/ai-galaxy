# backend/app/core/config.py
from pydantic import BaseSettings, Field, validator
from typing import List, Optional
import os


class Settings(BaseSettings):
    # FastAPI settings
    app_title: str = "x1mvp Portfolio API"
    app_version: str = "3.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    
    # CORS settings
    allowed_origins: List[str] = Field(
        default=["https://x1mvp.github.io", "http://localhost:3000", "http://localhost:8080"],
        env="ALLOWED_ORIGINS"
    )
    
    @validator('allowed_origins', pre=True)
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    # Logging settings
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_to_file: bool = Field(default=False, env="LOG_TO_FILE")
    
    # NLP settings
    nlp_model_name: str = Field(default="cardiffnlp/twitter-roberta-base-sentiment-latest", env="NLP_MODEL_NAME")
    nlp_batch_size: int = Field(default=16, env="NLP_BATCH_SIZE")
    nlp_max_length: int = Field(default=512, env="NLP_MAX_LENGTH")
    nlp_device: Optional[str] = Field(default=None, env="NLP_DEVICE")
    
    # Performance settings
    max_request_size: int = Field(default=10_000_000, env="MAX_REQUEST_SIZE")
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
