"""NLP Service Configuration"""

import os
from typing import List

class NLPConfig:
    """Configuration for NLP classification service"""
    
    # Model configuration
    MODEL_PATH: str = os.getenv("MODEL_PATH", "/app/models/bert.onnx")
    TOKENIZER_NAME: str = os.getenv("TOKENIZER_NAME", "distilbert-base-uncased")
    
    # Inference parameters
    MAX_LENGTH: int = int(os.getenv("MAX_LENGTH", "128"))
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "32"))
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.1"))
    
    # Labels for multi-label classification
    LABELS: List[str] = [
        "spam", "news", "tech", "sports", "finance",
        "health", "entertainment", "politics", "science", "education"
    ]
    
    # Performance settings
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))
    
    # Feature flags
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    ENABLE_BATCH: bool = os.getenv("ENABLE_BATCH", "true").lower() == "true"
