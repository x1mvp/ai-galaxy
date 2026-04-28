
app/nlp.py - NLP model manager and router.

Production-ready multi-label text classification with BERT ONNX.
"""

from __future__ import annotations

import os
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache

import numpy as np

# Import only when needed (avoid import errors in test environments)
try:
    import onnxruntime as ort
    from transformers import AutoTokenizer
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    ort = None
    AutoTokenizer = None

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/nlp",
    tags=["NLP Classification"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
        503: {"description": "Service unavailable"}
    }
)

# =============================================================================
# MODEL CONFIGURATION (Testing-safe version)
# =============================================================================
class ModelConfig:
    """Centralized configuration for NLP model with testing support"""
    
    MODEL_PATH = Path(os.getenv("ONNX_MODEL_PATH", "/app/models/bert.onnx"))
    TOKENIZER_PATH = Path(os.getenv("TOKENIZER_PATH", "/app/models/tokenizer"))
    TOKENIZER_NAME = str(os.getenv("TOKENIZER_NAME", "distilbert-base-uncased"))
    
    # Model parameters
    MAX_LENGTH: int = int(os.getenv("NLP_MAX_LENGTH", "512"))
    NUM_LABELS: int = int(os.getenv("NUM_LABELS", "5"))
    
    # Performance settings
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "32"))
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "100"))
    
    # Cache settings
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # seconds
    CACHE_SIZE: int = int(os.getenv("CACHE_SIZE", "1000"))
    
    # Labels configuration
    LABELS = [
        "Technology", "Finance", "Healthcare",
        "Legal", "Marketing", "Science", "Politics", "Sports",
        "spam", "news", "tech", "entertainment", "education"
    ]
    
    # Threshold settings
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.1"))
    TOP_K: int = int(os.getenv("TOP_K", "5"))
    
    # Demo mode settings
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"

    @classmethod
    def validate(cls) -> None:
        """
        Check that the ONNX model file exists on disk.

        Skipped automatically when TESTING=true (CI / unit tests).
        Only called from ModelManager.load() - never at module level.
        """
        if os.getenv("TESTING", "false").lower() == "true":
            # CI runners don't have the model file - skip the check entirely.
            logger.info("TESTING=true: skipping model file validation")
            return

        if not cls.MODEL_PATH.exists():
            raise RuntimeError(
                f"ONNX model not found at {cls.MODEL_PATH}. "
                "See README for model conversion steps."
            )

        if not cls.TOKENIZER_PATH.exists() and not ONNX_AVAILABLE:
            # If tokenizer path doesn't exist but we can download from hub, that's ok
            pass

# =============================================================================
# DATA MODELS
# =============================================================================
class TextPayload(BaseModel):
    """Request payload for text classification"""
    
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=10000,
        description="Text to classify (1-10,000 characters)"
    )
    
    @field_validator('text')
    @classmethod
    def validate_text(cls, v):
        """Validate input text"""
        if not v or not v.strip():
            raise ValueError("Text cannot be empty")
        
        # Check for potentially malicious content
        if len(v) > 10000:
            raise ValueError("Text too long (max 10,000 characters)")
        
        # Remove excessive whitespace
        v = ' '.join(v.split())
        return v

class PredictionResult(BaseModel):
    """Single prediction result"""
    
    label: str = Field(..., description="Predicted label")
    prob: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    
    @field_validator('prob')
    @classmethod
    def round_probability(cls, v):
        """Round probability to 3 decimal places"""
        return round(v, 3)

class ClassificationResponse(BaseModel):
    """API response for classification"""
    
    demo: bool = Field(..., description="Whether this is a demo response")
    predictions: List[PredictionResult] = Field(..., description="Classification results")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    processing_time: Optional[float] = Field(None, description="Processing time in ms")

class HealthResponse(BaseModel):
    """Health check response"""
    
    status: str = Field(..., description="Service status")
    model_loaded: bool = Field(..., description="Whether model is loaded")
    cache_size: int = Field(..., description="Current cache size")
    uptime: float = Field(..., description="Service uptime in seconds")
    version: str = Field(..., description="API version")

# =============================================================================
# MODEL MANAGER (Testing-safe implementation)
# =============================================================================
class ModelManager:
    """
    Owns the ONNX session and tokenizer lifecycle.
    load() / unload() are called by the FastAPI lifespan hook - never at
    import time and never during test collection.
    """

    def __init__(self) -> None:
        self._session: Any = None
        self._tokenizer: Any = None
        self.is_loaded: bool = False
        self.cache: Dict[str, Any] = {}
        self.start_time = time.time()
        self.request_count = 0

    def load(self) -> None:
        """
        Validate config, then load the ONNX session and tokenizer.
        Called once at server startup by the lifespan context manager.
        """
        ModelConfig.validate()   # - only called here, never at module level

        if os.getenv("TESTING", "false").lower() == "true":
            # In test mode validate() already returned early above.
            # Mark as loaded so route handlers don't raise "model not ready".
            self.is_loaded = True
            logger.info("TESTING=true: model marked as loaded (mock mode)")
            return

        if not ONNX_AVAILABLE:
            raise RuntimeError("ONNX dependencies not available")

        try:
            logger.info(f"Loading ONNX model from {ModelConfig.MODEL_PATH}")
            
            # Configure ONNX Runtime providers
            providers = ["CPUExecutionProvider"]
            if hasattr(ort, 'get_device') and ort.get_device() == "GPU":
                providers.insert(0, "CUDAExecutionProvider")
            
            # Create optimized session options
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 4
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            self._session = ort.InferenceSession(
                str(ModelConfig.MODEL_PATH),
                providers=providers,
                sess_options=opts
            )
            
            # Load tokenizer (from path or hub)
            if ModelConfig.TOKENIZER_PATH.exists():
                logger.info(f"Loading tokenizer from {ModelConfig.TOKENIZER_PATH}")
                self._tokenizer = AutoTokenizer.from_pretrained(str(ModelConfig.TOKENIZER_PATH))
            else:
                logger.info(f"Loading tokenizer from hub: {ModelConfig.TOKENIZER_NAME}")
                self._tokenizer = AutoTokenizer.from_pretrained(ModelConfig.TOKENIZER_NAME)
            
            self.is_loaded = True
            logger.info("- Model and tokenizer loaded successfully")

        except Exception as exc:
            logger.error(f"- Failed to load model: {exc}")
            raise RuntimeError(f"Failed to load NLP model: {exc}") from exc

    def unload(self) -> None:
        """Release model resources. Called at server shutdown."""
        self._session = None
        self._tokenizer = None
        self.is_loaded = False
        logger.info("Model unloaded")

    def predict(self, text: str) -> List[Dict[str, Any]]:
        """
        Run inference and return top-5 category scores.
        Falls back to deterministic mock scores when TESTING=true.
        """
        if os.getenv("TESTING", "false").lower() == "true":
            # Deterministic mock - lets unit tests assert on real values
            # without needing the model file.
            return [
                {"label": "Technology", "score": 0.91},
                {"label": "Finance",    "score": 0.72},
                {"label": "Healthcare", "score": 0.55},
                {"label": "Legal",      "score": 0.41},
                {"label": "Marketing",  "score": 0.28},
            ]

        if not self.is_loaded or self._session is None:
            raise RuntimeError("Model is not loaded. Call load() first.")

        try:
            inputs = self._tokenizer(
                text,
                return_tensors="np",
                max_length=ModelConfig.MAX_LENGTH,
                truncation=True,
                padding=True,
            )
            outputs = self._session.run(
                None,
                {k: v for k, v in inputs.items()},
            )

            logits = outputs[0][0]
            exp_logits = np.exp(logits - np.max(logits))
            scores = exp_logits / exp_logits.sum()

            results = [
                {"label": label, "score": float(score)}
                for label, score in zip(ModelConfig.LABELS[:len(scores)], scores)
            ]
            return sorted(results, key=lambda x: x["score"], reverse=True)[:ModelConfig.TOP_K]
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise RuntimeError(f"Prediction failed: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """Get model statistics"""
        return {
            "model_loaded": self.is_loaded,
            "cache_size": len(self.cache),
            "uptime": time.time() - self.start_time,
            "request_count": self.request_count,
            "model_path": str(ModelConfig.MODEL_PATH),
            "tokenizer": ModelConfig.TOKENIZER_NAME,
            "max_length": ModelConfig.MAX_LENGTH,
            "labels": ModelConfig.LABELS,
            "demo_mode": ModelConfig.DEMO_MODE
        }

# =============================================================================
# GLOBAL SINGLETON
# =============================================================================
model_manager = ModelManager()

# =============================================================================
# MIDDLEWARE AND DEPENDENCIES
# =============================================================================
def get_current_time() -> float:
    """Get current timestamp for metrics"""
    return time.time()

# =============================================================================
# API ENDPOINTS
# =============================================================================
@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check service health and model status"
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for monitoring and load balancers.
    Returns service status and model information.
    """
    try:
        stats = model_manager.get_stats()
        
        return HealthResponse(
            status="healthy" if stats["model_loaded"] else "unhealthy",
            model_loaded=stats["model_loaded"],
            cache_size=stats["cache_size"],
            uptime=stats["uptime"],
            version="3.0.0"
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            model_loaded=False,
            cache_size=0,
            uptime=0.0,
            version="3.0.0"
        )
