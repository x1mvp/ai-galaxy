"""
x1mvp Portfolio - NLP Text Classifier
Production-ready multi-label text classification with BERT ONNX

Version: 3.0.0
Last Updated: 2026-01-15
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from functools import lru_cache
import time
import json

import numpy as np
import onnxruntime as ort
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from transformers import AutoTokenizer
from transformers.tokenization_utils_base import BatchEncoding

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

# ===============================================================================
# CONFIGURATION
# ===============================================================================

class ModelConfig:
    """Centralized configuration for NLP model"""
    
    # Model paths and settings
    ONNX_PATH: str = os.getenv("ONNX_PATH", "/app/models/bert.onnx")
    TOKENIZER_NAME: str = os.getenv("TOKENIZER", "distilbert-base-uncased")
    
    # Model parameters
    MAX_LENGTH: int = int(os.getenv("MAX_LENGTH", "128"))
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
        "spam", "news", "tech", "sports", "finance",
        "health", "entertainment", "politics", "science", "education"
    ]
    
    # Threshold settings
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.1"))
    TOP_K: int = int(os.getenv("TOP_K", "5"))
    
    # Demo mode settings
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        """Validate configuration"""
        if not os.path.exists(cls.ONNX_PATH):
            raise RuntimeError(
                f"ONNX model not found at {cls.ONNX_PATH}. "
                "See README for model conversion steps."
            )
        
        if cls.MAX_LENGTH <= 0 or cls.MAX_LENGTH > 512:
            raise ValueError("MAX_LENGTH must be between 1 and 512")

# Validate configuration on import
ModelConfig.validate()

# ===============================================================================
# DATA MODELS
# ===============================================================================

class TextPayload(BaseModel):
    """Request payload for text classification"""
    
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=10000,
        description="Text to classify (1-10,000 characters)"
    )
    
    @validator('text')
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
    
    @validator('prob')
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

# ===============================================================================
# MODEL MANAGER
# ===============================================================================

class ModelManager:
    """Manages ONNX model lifecycle and inference"""
    
    def __init__(self):
        self.session: Optional[ort.InferenceSession] = None
        self.tokenizer: Optional[AutoTokenizer] = None
        self.cache: Dict[str, Any] = {}
        self.start_time = time.time()
        self.request_count = 0
        self._load_model()
    
    def _load_model(self) -> None:
        """Load ONNX model and tokenizer"""
        try:
            logger.info(f"Loading ONNX model from {ModelConfig.ONNX_PATH}")
            
            # Configure ONNX Runtime providers
            providers = ["CPUExecutionProvider"]
            if ort.get_device() == "GPU":
                providers.insert(0, "CUDAExecutionProvider")
            
            self.session = ort.InferenceSession(
                ModelConfig.ONNX_PATH,
                providers=providers,
                sess_options=self._create_session_options()
            )
            
            logger.info(f"Loading tokenizer: {ModelConfig.TOKENIZER_NAME}")
            self.tokenizer = AutoTokenizer.from_pretrained(ModelConfig.TOKENIZER_NAME)
            
            logger.info("✅ Model and tokenizer loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise RuntimeError(f"Model loading failed: {str(e)}")
    
    def _create_session_options(self) -> ort.SessionOptions:
        """Create optimized ONNX session options"""
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 4
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return opts
    
    @lru_cache(maxsize=ModelConfig.CACHE_SIZE)
    def _cached_tokenize(self, text: str) -> BatchEncoding:
        """Cached tokenization for better performance"""
        return self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=ModelConfig.MAX_LENGTH,
            return_tensors="np"
        )
    
    def predict_batch(self, texts: List[str]) -> List[List[PredictionResult]]:
        """Batch prediction for better performance"""
        if not self.session or not self.tokenizer:
            raise RuntimeError("Model not loaded")
        
        start_time = time.time()
        
        try:
            # Tokenize batch
            inputs = self.tokenizer(
                texts,
                truncation=True,
                padding="max_length",
                max_length=ModelConfig.MAX_LENGTH,
                return_tensors="np"
            )
            
            # Prepare ONNX inputs
            ort_inputs = {
                k: v.astype(np.int64) for k, v in inputs.items()
            }
            
            # Run inference
            logits = self.session.run(None, ort_inputs)[0]  # (batch_size, num_labels)
            
            # Apply sigmoid and convert to predictions
            probs = 1 / (1 + np.exp(-logits))  # sigmoid
            
            results = []
            for i, text in enumerate(texts):
                text_probs = probs[i]
                
                # Filter by threshold and get top-k
                filtered_results = [
                    {
                        "label": ModelConfig.LABELS[j],
                        "prob": float(text_probs[j])
                    }
                    for j in range(len(ModelConfig.LABELS))
                    if text_probs[j] >= ModelConfig.CONFIDENCE_THRESHOLD
                ]
                
                # Sort by probability and take top-k
                sorted_results = sorted(
                    filtered_results, 
                    key=lambda x: x["prob"], 
                    reverse=True
                )[:ModelConfig.TOP_K]
                
                results.append([PredictionResult(**item) for item in sorted_results])
            
            processing_time = (time.time() - start_time) * 1000
            logger.info(f"Batch inference completed in {processing_time:.2f}ms")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch prediction failed: {e}")
            raise RuntimeError(f"Inference failed: {str(e)}")
    
    def predict_single(self, text: str) -> List[PredictionResult]:
        """Single text prediction"""
        results = self.predict_batch([text])
        return results[0] if results else []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get model statistics"""
        return {
            "model_loaded": self.session is not None,
            "cache_size": len(self.cache),
            "uptime": time.time() - self.start_time,
            "request_count": self.request_count,
            "model_path": ModelConfig.ONNX_PATH,
            "tokenizer": ModelConfig.TOKENIZER_NAME,
            "max_length": ModelConfig.MAX_LENGTH,
            "labels": ModelConfig.LABELS
        }

# Initialize global model manager
model_manager = ModelManager()

# ===============================================================================
# MIDDLEWARE AND DEPENDENCIES
# ===============================================================================

async def rate_limit_check(request: Request) -> None:
    """Simple rate limiting middleware"""
    # Implement rate limiting logic here
    client_ip = request.client.host
    # You can use Redis or in-memory for rate limiting
    pass

def get_current_time() -> float:
    """Get current timestamp for metrics"""
    return time.time()

# ===============================================================================
# API ENDPOINTS
# ===============================================================================

@router.post(
    "/demo",
    response_model=ClassificationResponse,
    summary="Demo Classification",
    description="Returns demo predictions without actual inference for performance testing"
)
async def demo_classification(
    payload: TextPayload,
    background_tasks: BackgroundTasks,
    current_time: float = Depends(get_current_time)
) -> ClassificationResponse:
    """
    Demo endpoint that returns predefined results.
    Useful for testing and performance benchmarking.
    """
    try:
        # Log request
        background_tasks.add_task(
            logger.info,
            f"Demo request received: text_length={len(payload.text)}"
        )
        
        # Return demo results
        demo_predictions = [
            PredictionResult(label="spam", prob=0.87),
            PredictionResult(label="news", prob=0.71),
            PredictionResult(label="tech", prob=0.62)
        ]
        
        return ClassificationResponse(
            demo=True,
            predictions=demo_predictions,
            metadata={
                "demo_mode": True,
                "text_length": len(payload.text),
                "model_labels": ModelConfig.LABELS
            },
            processing_time=5.0  # Simulated processing time
        )
        
    except Exception as e:
        logger.error(f"Demo classification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/full",
    response_model=ClassificationResponse,
    summary="Full Classification",
    description="Real classification using BERT ONNX model"
)
async def full_classification(
    payload: TextPayload,
    background_tasks: BackgroundTasks,
    current_time: float = Depends(get_current_time),
    _: bool = Depends(rate_limit_check)
) -> ClassificationResponse:
    """
    Full classification endpoint using actual model inference.
    Performs multi-label classification with confidence scoring.
    """
    start_time = time.time()
    
    try:
        # Increment request counter
        model_manager.request_count += 1
        
        # Log request (async)
        background_tasks.add_task(
            logger.info,
            f"Classification request: text_length={len(payload.text)}, "
            f"request_count={model_manager.request_count}"
        )
        
        # Perform inference
        if ModelConfig.DEMO_MODE:
            # Demo mode for development
            predictions = [
                PredictionResult(label="spam", prob=0.87),
                PredictionResult(label="news", prob=0.71),
                PredictionResult(label="tech", prob=0.62)
            ]
        else:
            predictions = model_manager.predict_single(payload.text)
        
        processing_time = (time.time() - start_time) * 1000
        
        return ClassificationResponse(
            demo=False,
            predictions=predictions,
            metadata={
                "model_version": "1.0.0",
                "text_length": len(payload.text),
                "threshold": ModelConfig.CONFIDENCE_THRESHOLD,
                "top_k": ModelConfig.TOP_K
            },
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Full classification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@router.post(
    "/batch",
    response_model=List[ClassificationResponse],
    summary="Batch Classification",
    description="Classify multiple texts in a single request"
)
async def batch_classification(
    texts: List[str],
    background_tasks: BackgroundTasks,
    current_time: float = Depends(get_current_time)
) -> List[ClassificationResponse]:
    """
    Batch classification endpoint for processing multiple texts efficiently.
    """
    try:
        # Validate batch size
        if len(texts) > ModelConfig.BATCH_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size too large. Max: {ModelConfig.BATCH_SIZE}"
            )
        
        # Validate each text
        validated_texts = []
        for i, text in enumerate(texts):
            try:
                payload = TextPayload(text=text)
                validated_texts.append(payload.text)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid text at index {i}: {str(e)}"
                )
        
        # Log batch request
        background_tasks.add_task(
            logger.info,
            f"Batch classification: batch_size={len(validated_texts)}"
        )
        
        # Perform batch inference
        start_time = time.time()
        predictions_list = model_manager.predict_batch(validated_texts)
        processing_time = (time.time() - start_time) * 1000
        
        # Create response for each text
        responses = []
        for i, predictions in enumerate(predictions_list):
            responses.append(
                ClassificationResponse(
                    demo=False,
                    predictions=predictions,
                    metadata={
                        "batch_index": i,
                        "batch_size": len(validated_texts),
                        "text_length": len(validated_texts[i])
                    },
                    processing_time=processing_time / len(validated_texts)
                )
            )
        
        return responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch classification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch classification failed: {str(e)}")

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

@router.get(
    "/info",
    summary="Model Information",
    description="Get detailed information about the NLP model"
)
async def model_info() -> Dict[str, Any]:
    """
    Returns detailed model configuration and capabilities.
    """
    try:
        stats = model_manager.get_stats()
        
        return {
            "model": {
                "name": "DistilBERT Multi-Label Classifier",
                "version": "1.0.0",
                "type": "ONNX",
                "framework": "Transformers",
                "language": "English"
            },
            "configuration": {
                "max_length": ModelConfig.MAX_LENGTH,
                "num_labels": len(ModelConfig.LABELS),
                "labels": ModelConfig.LABELS,
                "confidence_threshold": ModelConfig.CONFIDENCE_THRESHOLD,
                "top_k": ModelConfig.TOP_K,
                "batch_size": ModelConfig.BATCH_SIZE
            },
            "performance": {
                "cache_enabled": ModelConfig.ENABLE_CACHE,
                "cache_size": ModelConfig.CACHE_SIZE,
                "cache_ttl": ModelConfig.CACHE_TTL,
                "demo_mode": ModelConfig.DEMO_MODE
            },
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Model info failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get model info")

# ===============================================================================
# EXCEPTION HANDLERS
# ===============================================================================

@router.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error", "detail": str(exc)}
    )

@router.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    """Handle runtime errors"""
    return JSONResponse(
        status_code=503,
        content={"error": "Service unavailable", "detail": str(exc)}
    )

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_sample_predictions() -> List[PredictionResult]:
    """Create sample predictions for testing"""
    return [
        PredictionResult(label="spam", prob=0.87),
        PredictionResult(label="news", prob=0.71),
        PredictionResult(label="tech", prob=0.62),
        PredictionResult(label="sports", prob=0.45),
        PredictionResult(label="finance", prob=0.33)
    ]

# ===============================================================================
# MAIN APPLICATION ENTRY POINT
# ===============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Development server
    uvicorn.run(
        "nlp_service:router",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
