# backend/app/routers/nlp.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

# Fix: Import from correct location
from app.nlp import model_manager
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

class TextPredictionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    return_probabilities: bool = Field(default=True)

class PredictionResponse(BaseModel):
    label: str
    probability: Optional[float] = None

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
    model = Depends(get_model_manager)
) -> PredictionResponse:
    """Single text prediction"""
    try:
        result = model.predict(request.text)
        
        # Handle both single result and list formats
        if isinstance(result, list):
            result = result[0]
        
        return PredictionResponse(
            label=result["label"],
            probability=result["prob"] if request.return_probabilities else None
        )
        
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
