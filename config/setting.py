# config/settings.py
from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Model configuration
    model_name: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    task: str = "sentiment-analysis"
    max_length: int = 512
    batch_size: int = 16
    cache_dir: Optional[str] = None
    
    # Performance settings
    device: Optional[str] = None
    enable_quantization: bool = False
    enable_fp16: bool = True
    
    # Monitoring and logging
    log_level: str = "INFO"
    enable_metrics: bool = True
    metrics_port: int = 8000
    
    # Security
    trust_remote_code: bool = False
    
    class Config:
        env_file = ".env"
        env_prefix = "NLP_"


settings = Settings()
