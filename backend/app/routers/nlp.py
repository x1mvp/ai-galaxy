# app/routers/nlp.py
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import asyncio
import logging

from app.nlp import model_manager

logger = logging.getLogger(__name__)
router = APIRouter()


class TextPredictionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Input text for analysis")
    return_probabilities: bool = Field(default=True, description="Include probability scores")
    
    @validator('text')
    def validate_text(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty or whitespace only')
        return v.strip()


class BatchPredictionRequest(BaseModel):
    texts: List[str] = Field(..., min_items=1, max_items=100, description="Batch of texts")
    return_probabilities: bool = Field(default=True, description="Include probability scores")
    
    @validator('texts')
    def validate_texts(cls, v):
        if not all(text.strip() for text in v):
            raise ValueError('All texts must be non-empty')
        return [text.strip() for text in v]


class PredictionResponse(BaseModel):
    label: str
    probability: Optional[float] = None
    processing_time_ms: Optional[float] = None


class ModelStatsResponse(BaseModel):
    model_loaded: bool
    model_name: str
    uptime: float
    request_count: int
    avg_response_time: float
    cache_hit_rate: float
    memory_usage: Optional[Dict[str, str]] = None


def get_model_manager():
    """Dependency to ensure model is loaded"""
    if not model_manager.is_loaded:
        raise HTTPException(
            status_code=503, 
            detail="NLP service is currently loading - please try again"
        )
    return model_manager


@router.post("/predict", response_model=PredictionResponse)
async def predict_text(
    request: TextPredictionRequest,
    model: Any = Depends(get_model_manager)
) -> PredictionResponse:
    """Single text prediction with detailed response"""
    import time
    start_time = time.time()
    
    try:
        result = model.predict(request.text)
        
        # Handle both single result and list formats
        if isinstance(result, list):
            result = result[0]
        
        processing_time = (time.time() - start_time) * 1000
        
        return PredictionResponse(
            label=result["label"],
            probability=result["prob"] if request.return_probabilities else None,
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/predict/batch", response_model=List[PredictionResponse])
async def predict_batch(
    request: BatchPredictionRequest,
    background_tasks: BackgroundTasks,
    model: Any = Depends(get_model_manager)
) -> List[PredictionResponse]:
    """Batch prediction with async processing"""
    import time
    start_time = time.time()
    
    try:
        # Process in chunks to avoid memory issues
        chunk_size = model.batch_size or 16
        results = []
        
        for i in range(0, len(request.texts), chunk_size):
            chunk = request.texts[i:i + chunk_size]
            chunk_results = model.predict(chunk)
            
            for j, result in enumerate(chunk_results):
                processing_time = ((time.time() - start_time) * 1000) / (i + j + 1)
                
                results.append(PredictionResponse(
                    label=result["label"],
                    probability=result["prob"] if request.return_probabilities else None,
                    processing_time_ms=processing_time
                ))
        
        # Log batch processing in background
        background_tasks.add_task(
            logger.info,
            f"Processed batch of {len(request.texts)} texts in {(time.time() - start_time)*1000:.2f}ms"
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Batch prediction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")


@router.get("/stats", response_model=ModelStatsResponse)
async def get_model_stats(model: Any = Depends(get_model_manager)) -> ModelStatsResponse:
    """Get comprehensive model statistics"""
    try:
        stats = model.get_stats()
        cache_info = stats["cache_info"]
        
        return ModelStatsResponse(
            model_loaded=stats["model_loaded"],
            model_name=stats.get("model_name", "unknown"),
            uptime=stats["uptime"],
            request_count=stats["request_count"],
            avg_response_time=stats.get("avg_inference_time", 0.0),
            cache_hit_rate=cache_info["hit_rate"],
            memory_usage=stats.get("memory_info")
        )
        
    except Exception as e:
        logger.error(f"Stats retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


@router.post("/reload")
async def reload_model(background_tasks: BackgroundTasks) -> Dict[str, str]:
    """Reload model with background processing"""
    try:
        # Perform reload in background to avoid blocking
        def reload_task():
            model_manager.unload()
            model_manager.load()
            logger.info("Model reloaded successfully")
        
        background_tasks.add_task(reload_task)
        
        return {
            "status": "reloading",
            "message": "Model reload started in background"
        }
        
    except Exception as e:
        logger.error(f"Model reload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Model reload failed: {str(e)}")


@router.get("/health")
async def nlp_health_check() -> Dict[str, Any]:
    """Detailed NLP service health check"""
    try:
        health = model_manager.health_check()
        return health
    except Exception as e:
        logger.error(f"NLP health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "reason": str(e),
            "timestamp": asyncio.get_running_loop().time()
        }
