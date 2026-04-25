"""NLP Service Configuration"""

import os
from typing import List
from dataclasses import dataclass

@dataclass
class NLPConfig:
    """Configuration for NLP classification service"""
    
    # Model configuration
    MODEL_VERSION: str = os.getenv("MODEL_VERSION", "v1.0")
    MODEL_PATH: str = os.getenv("MODEL_PATH", f"/app/models/bert_{MODEL_VERSION}.onnx")
    MODEL_HASH: str = os.getenv("MODEL_HASH", None)  # Optional model verification
    TOKENIZER_NAME: str = os.getenv("TOKENIZER_NAME", "distilbert-base-uncased")
    
    # Inference parameters
    MAX_LENGTH: int = int(os.getenv("MAX_LENGTH", "128"))
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "32"))
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.1"))
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
    TIMEOUT_SECONDS: int = int(os.getenv("TIMEOUT_SECONDS", "30"))
    
    # Labels for multi-label classification (organized by category)
    SPAM_LABELS: List[str] = ["spam"]
    CONTENT_LABELS: List[str] = ["news", "tech", "sports", "finance", "health"]
    ENTERTAINMENT_LABELS: List[str] = ["entertainment", "politics", "science", "education"]
    LABELS: List[str] = SPAM_LABELS + CONTENT_LABELS + ENTERTAINMENT_LABELS
    
    # Performance settings
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))
    CACHE_SIZE: int = int(os.getenv("CACHE_SIZE", "10000"))  # Max cache entries
    
    # Feature flags
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    ENABLE_BATCH: bool = os.getenv("ENABLE_BATCH", "true").lower() == "true"
    ENABLE_PROFILING: bool = os.getenv("ENABLE_PROFILING", "false").lower() == "true"
    
    # Logging configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    
    def __post_init__(self):
        """Validate configuration on initialization"""
        # Validate confidence threshold
        if self.CONFIDENCE_THRESHOLD < 0 or self.CONFIDENCE_THRESHOLD > 1:
            raise ValueError("CONFIDENCE_THRESHOLD must be between 0 and 1")
        
        # Validate numeric values
        if self.MAX_LENGTH <= 0:
            raise ValueError("MAX_LENGTH must be positive")
        
        if self.BATCH_SIZE <= 0:
            raise ValueError("BATCH_SIZE must be positive")
        
        if self.MAX_CONCURRENT_REQUESTS <= 0:
            raise ValueError("MAX_CONCURRENT_REQUESTS must be positive")
        
        if self.TIMEOUT_SECONDS <= 0:
            raise ValueError("TIMEOUT_SECONDS must be positive")
        
        if self.CACHE_TTL <= 0:
            raise ValueError("CACHE_TTL must be positive")
        
        if self.CACHE_SIZE <= 0:
            raise ValueError("CACHE_SIZE must be positive")
        
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.LOG_LEVEL.upper() not in valid_log_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {valid_log_levels}")
        
        # Validate tokenizer name is not empty
        if not self.TOKENIZER_NAME.strip():
            raise ValueError("TOKENIZER_NAME cannot be empty")
        
        # Ensure labels are unique
        if len(self.LABELS) != len(set(self.LABELS)):
            raise ValueError("LABELS must contain unique values")
    
    def get_config_summary(self) -> dict:
        """Get a summary of key configuration values (excluding sensitive data)"""
        return {
            "model_version": self.MODEL_VERSION,
            "tokenizer": self.TOKENIZER_NAME,
            "max_length": self.MAX_LENGTH,
            "batch_size": self.BATCH_SIZE,
            "confidence_threshold": self.CONFIDENCE_THRESHOLD,
            "num_labels": len(self.LABELS),
            "labels": self.LABELS,
            "cache_enabled": self.ENABLE_CACHE,
            "demo_mode": self.DEMO_MODE,
            "batch_enabled": self.ENABLE_BATCH,
            "metrics_enabled": self.ENABLE_METRICS
        }

# Global configuration instance
config = NLPConfig()
