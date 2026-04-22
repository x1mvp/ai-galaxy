"""
x1mvp Portfolio - Clinical Risk Predictor
Production-ready medical risk assessment with XGBoost and SHAP explainability

Version: 3.0.0
Last Updated: 2026-01-15
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge
from sklearn.preprocessing import StandardScaler

# Configure logging
logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/clinical",
    tags=["Clinical Risk Predictor"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
        503: {"description": "Service unavailable"}
    }
)

# ===============================================================================
# CONFIGURATION & MODELS
# ===============================================================================

@dataclass
class RiskAssessment:
    """Risk assessment result data model"""
    
    risk_score: float
    risk_level: str
    confidence: float
    prediction_time_ms: float
    timestamp: str
    patient_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

@dataclass
class SHAPExplanation:
    """SHAP explanation data model"""
    
    features: List[str]
    values: List[float]
    base_value: float
    feature_importance: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

class ClinicalConfig:
    """Configuration for clinical risk predictor"""
    
    # Model configuration
    MODEL_PATH: str = os.getenv("MODEL_PATH", "/app/models/xgboost_model.pkl")
    SHAP_PATH: str = os.getenv("SHAP_PATH", "/app/models/shap_explainer.pkl")
    SCALER_PATH: str = os.getenv("SCALER_PATH", "/app/models/scaler.pkl")
    
    # Feature configuration
    FEATURE_NAMES: List[str] = [
        "age", "systolic_bp", "diastolic_bp", "cholesterol", "bmi"
    ]
    
    # Risk thresholds
    RISK_THRESHOLDS: Dict[str, float] = {
        "low": 0.3,
        "moderate": 0.6,
        "high": 0.8
    }
    
    # Clinical ranges for validation
    CLINICAL_RANGES: Dict[str, Tuple[float, float]] = {
        "age": (0.0, 120.0),
        "systolic_bp": (70.0, 250.0),
        "diastolic_bp": (40.0, 150.0),
        "cholesterol": (100.0, 500.0),
        "bmi": (10.0, 50.0)
    }
    
    # Performance configuration
    ENABLE_CACHING: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
    
    # Monitoring configuration
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    PREDICTION_LOGGING: bool = os.getenv("PREDICTION_LOGGING", "true").lower() == "true"

# Global configuration
CONFIG = ClinicalConfig()

# ===============================================================================
# PYDANTIC MODELS
# ===============================================================================

class Vitals(BaseModel):
    """Patient vitals data model with comprehensive validation"""
    
    age: float = Field(
        ..., 
        ge=0.0, 
        le=120.0,
        description="Patient age in years"
    )
    systolic_bp: float = Field(
        ..., 
        ge=70.0, 
        le=250.0,
        description="Systolic blood pressure in mmHg"
    )
    diastolic_bp: float = Field(
        ..., 
        ge=40.0, 
        le=150.0,
        description="Diastolic blood pressure in mmHg"
    )
    cholesterol: float = Field(
        ..., 
        ge=100.0, 
        le=500.0,
        description="Total cholesterol in mg/dL"
    )
    bmi: float = Field(
        ..., 
        ge=10.0, 
        le=50.0,
        description="Body Mass Index (BMI)"
    )
    
    # Optional additional vitals
    heart_rate: Optional[float] = Field(
        None, 
        ge=30.0, 
        le=200.0,
        description="Heart rate in beats per minute"
    )
    glucose: Optional[float] = Field(
        None, 
        ge=50.0, 
        le=400.0,
        description="Blood glucose in mg/dL"
    )
    
    # Patient metadata
    patient_id: Optional[str] = Field(None, description="Patient identifier")
    gender: Optional[str] = Field(None, description="Patient gender (M/F/Other)")
    
    @validator('diastolic_bp')
    def validate_blood_pressure(cls, v, values):
        """Ensure diastolic is less than systolic"""
        if 'systolic_bp' in values and v >= values['systolic_bp']:
            raise ValueError('Diastolic blood pressure must be less than systolic')
        return v
    
    @validator('bmi')
    def validate_bmi_calculation(cls, v, values):
        """Validate BMI is reasonable for age"""
        if 'age' in values and values['age'] < 18 and v > 35:
            raise ValueError('BMI seems unusually high for age')
        return v
    
    @validator('cholesterol')
    def validate_cholesterol_age_relationship(cls, v, values):
        """Validate cholesterol is reasonable for age"""
        if 'age' in values and values['age'] < 25 and v > 300:
            raise ValueError('Cholesterol level seems high for young patient')
        return v
    
    def to_array(self) -> np.ndarray:
        """Convert vitals to numpy array for prediction"""
        return np.array([[
            self.age, self.systolic_bp, self.diastolic_bp, 
            self.cholesterol, self.bmi
        ]])

class RiskAssessmentResponse(BaseModel):
    """Risk assessment response model"""
    
    demo: bool = Field(..., description="Whether this is a demo response")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Risk score (0-1)")
    risk_level: str = Field(..., description="Risk level category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence")
    assessment: Optional[str] = Field(None, description="Clinical assessment")
    recommendations: Optional[List[str]] = Field(None, description="Clinical recommendations")
    shap: Optional[SHAPExplanation] = Field(None, description="SHAP explanation")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")

class DemoResponse(BaseModel):
    """Demo response model"""
    
    demo: bool = Field(..., description="Demo flag")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Demo risk score")
    explanation: str = Field(..., description="Demo explanation")
    sample_vitals: Optional[Vitals] = Field(None, description="Sample vitals for demo")

# ===============================================================================
# METRICS COLLECTION
# ===============================================================================

# Prometheus metrics
PREDICTIONS_TOTAL = Counter(
    'clinical_predictions_total',
    'Total clinical risk predictions',
    ['endpoint', 'risk_level']
)

PREDICTION_DURATION = Histogram(
    'clinical_prediction_duration_seconds',
    'Clinical prediction duration in seconds'
)

SHAP_COMPUTATION_TIME = Histogram(
    'clinical_shap_computation_time_seconds',
    'SHAP computation time in seconds'
)

RISK_SCORE_DISTRIBUTION = Histogram(
    'clinical_risk_score_distribution',
    'Distribution of predicted risk scores'
)

ACTIVE_MODELS = Gauge(
    'clinical_active_models',
    'Number of active clinical models'
)

# ===============================================================================
# MODEL MANAGER
# ===============================================================================

class ClinicalModelManager:
    """Manages clinical prediction models and SHAP explainers"""
    
    def __init__(self):
        self.model = None
        self.explainer = None
        self.scaler = None
        self.feature_names = CONFIG.FEATURE_NAMES
        self.prediction_count = 0
        self.redis_client: Optional[redis.Redis] = None
        self._load_models()
    
    def _load_models(self):
        """Load ML models with comprehensive error handling"""
        try:
            # Load main prediction model
            model_path = Path(CONFIG.MODEL_PATH)
            if not model_path.exists():
                raise FileNotFoundError(f"Model not found at {CONFIG.MODEL_PATH}")
            
            self.model = joblib.load(model_path)
            logger.info(f"✅ Loaded prediction model from {CONFIG.MODEL_PATH}")
            
            # Load SHAP explainer
            explainer_path = Path(CONFIG.SHAP_PATH)
            if not explainer_path.exists():
                raise FileNotFoundError(f"SHAP explainer not found at {CONFIG.SHAP_PATH}")
            
            self.explainer = joblib.load(explainer_path)
            logger.info(f"✅ Loaded SHAP explainer from {CONFIG.SHAP_PATH}")
            
            # Load scaler if available
            scaler_path = Path(CONFIG.SCALER_PATH)
            if scaler_path.exists():
                self.scaler = joblib.load(scaler_path)
                logger.info(f"✅ Loaded scaler from {CONFIG.SCALER_PATH}")
            
            # Validate model compatibility
            self._validate_models()
            
            ACTIVE_MODELS.inc()
            
        except Exception as e:
            logger.error(f"❌ Failed to load models: {e}")
            raise RuntimeError(f"Model loading failed: {str(e)}")
    
    def _validate_models(self):
        """Validate model compatibility and configuration"""
        if self.model is None:
            raise ValueError("Prediction model not loaded")
        
        if self.explainer is None:
            raise ValueError("SHAP explainer not loaded")
        
        # Check feature compatibility
        if hasattr(self.model, 'n_features_in_'):
            expected_features = self.model.n_features_in_
            actual_features = len(self.feature_names)
            
            if expected_features != actual_features:
                raise ValueError(
                    f"Feature mismatch: model expects {expected_features}, "
                    f"but configured {actual_features} features"
                )
        
        logger.info("✅ Model validation completed")
    
    def _preprocess_features(self, vitals: Vitals) -> np.ndarray:
        """Preprocess features with scaling if available"""
        features = vitals.to_array()
        
        if self.scaler is not None:
            features = self.scaler.transform(features)
        
        return features
    
    def _calculate_risk_level(self, risk_score: float) -> str:
        """Calculate risk level category"""
        if risk_score < CONFIG.RISK_THRESHOLDS["low"]:
            return "low"
        elif risk_score < CONFIG.RISK_THRESHOLDS["moderate"]:
            return "moderate"
        elif risk_score < CONFIG.RISK_THRESHOLDS["high"]:
            return "high"
        else:
            return "very_high"
    
    def _generate_clinical_assessment(self, risk_score: float, vitals: Vitals) -> str:
        """Generate clinical assessment based on risk and vitals"""
        risk_level = self._calculate_risk_level(risk_score)
        
        assessments = {
            "low": f"Low risk patient with stable vitals. Current risk score: {risk_score:.3f}.",
            "moderate": f"Moderate risk patient requiring monitoring. Current risk score: {risk_score:.3f}.",
            "high": f"High risk patient requiring immediate attention. Current risk score: {risk_score:.3f}.",
            "very_high": f"Very high risk patient requiring urgent medical intervention. Current risk score: {risk_score:.3f}."
        }
        
        base_assessment = assessments.get(risk_level, assessments["moderate"])
        
        # Add specific concerns based on vitals
        concerns = []
        
        if vitals.systolic_bp > 140:
            concerns.append("elevated systolic blood pressure")
        if vitals.diastolic_bp > 90:
            concerns.append("elevated diastolic blood pressure")
        if vitals.cholesterol > 240:
            concerns.append("high cholesterol")
        if vitals.bmi > 30:
            concerns.append("obesity")
        if vitals.age > 65:
            concerns.append("advanced age")
        
        if concerns:
            base_assessment += f" Notable concerns: {', '.join(concerns)}."
        
        return base_assessment
    
    def _generate_recommendations(self, risk_level: str, vitals: Vitals) -> List[str]:
        """Generate clinical recommendations based on risk level and vitals"""
        recommendations = []
        
        if risk_level in ["high", "very_high"]:
            recommendations.extend([
                "Schedule immediate follow-up with healthcare provider",
                "Consider urgent medical evaluation",
                "Implement continuous monitoring"
            ])
        elif risk_level == "moderate":
            recommendations.extend([
                "Schedule follow-up within 1-2 weeks",
                "Implement lifestyle modifications",
                "Increase monitoring frequency"
            ])
        else:  # low
            recommendations.extend([
                "Maintain regular check-ups",
                "Continue healthy lifestyle",
                "Monitor vital signs periodically"
            ])
        
        # Add specific recommendations based on vitals
        if vitals.systolic_bp > 140:
            recommendations.append("Initiate blood pressure management")
        if vitals.cholesterol > 240:
            recommendations.append("Implement cholesterol-lowering interventions")
        if vitals.bmi > 30:
            recommendations.append("Refer to nutritionist for weight management")
        if vitals.age > 65:
            recommendations.append("Consider geriatric specialist consultation")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    async def predict_risk(self, vitals: Vitals) -> Tuple[RiskAssessment, SHAPExplanation]:
        """Perform comprehensive risk prediction with SHAP explanation"""
        start_time = time.time()
        
        try:
            # Preprocess features
            features = self._preprocess_features(vitals)
            
            # Make prediction
            prediction_start = time.time()
            probabilities = self.model.predict_proba(features)
            prediction_time = (time.time() - prediction_start) * 1000
            
            risk_score = float(probabilities[0, 1])
            risk_level = self._calculate_risk_level(risk_score)
            
            # Calculate confidence (simplified - could be more sophisticated)
            confidence = max(probabilities[0, 0], probabilities[0, 1])
            
            # Generate SHAP explanation
            shap_start = time.time()
            shap_values = self.explainer.shap_values(features)[0]
            shap_time = (time.time() - shap_start) * 1000
            
            # Create SHAP explanation object
            shap_explanation = SHAPExplanation(
                features=self.feature_names,
                values=shap_values.tolist(),
                base_value=float(self.explainer.expected_value),
                feature_importance={
                    feature: float(value) 
                    for feature, value in zip(self.feature_names, shap_values)
                }
            )
            
            # Create risk assessment
            assessment = RiskAssessment(
                risk_score=risk_score,
                risk_level=risk_level,
                confidence=confidence,
                prediction_time_ms=prediction_time + shap_time,
                timestamp=datetime.utcnow().isoformat() + "Z",
                patient_id=vitals.patient_id
            )
            
            # Update metrics
            self.prediction_count += 1
            if CONFIG.ENABLE_METRICS:
                PREDICTIONS_TOTAL.labels(endpoint="full", risk_level=risk_level).inc()
                PREDICTION_DURATION.observe((time.time() - start_time))
                SHAP_COMPUTATION_TIME.observe(shap_time / 1000)
                RISK_SCORE_DISTRIBUTION.observe(risk_score)
            
            total_time = (time.time() - start_time) * 1000
            logger.info(
                f"Risk prediction completed: score={risk_score:.3f}, "
                f"level={risk_level}, time={total_time:.2f}ms"
            )
            
            return assessment, shap_explanation
            
        except Exception as e:
            logger.error(f"Risk prediction failed: {e}")
            raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
    
    async def generate_demo_prediction(self, vitals: Vitals) -> DemoResponse:
        """Generate demo prediction with realistic risk score"""
        # Generate realistic risk score based on vitals
        base_risk = 0.1
        
        # Adjust risk based on vitals
        if vitals.age > 65:
            base_risk += 0.2
        if vitals.systolic_bp > 140:
            base_risk += 0.15
        if vitals.cholesterol > 240:
            base_risk += 0.1
        if vitals.bmi > 30:
            base_risk += 0.1
        
        # Add some randomness
        risk_score = min(max(base_risk + np.random.normal(0, 0.1), 0.0), 1.0)
        risk_level = self._calculate_risk_level(risk_score)
        
        # Generate sample vitals for demonstration
        sample_vitals = Vitals(
            age=np.random.uniform(25, 75),
            systolic_bp=np.random.uniform(110, 160),
            diastolic_bp=np.random.uniform(70, 100),
            cholesterol=np.random.uniform(180, 280),
            bmi=np.random.uniform(20, 35)
        )
        
        return DemoResponse(
            demo=True,
            risk_score=round(risk_score, 3),
            explanation=f"Demo risk assessment with simulated {risk_level} risk. "
                       f"This is for demonstration purposes only.",
            sample_vitals=sample_vitals
        )
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information and statistics"""
        return {
            "model_type": type(self.model).__name__,
            "feature_count": len(self.feature_names),
            "feature_names": self.feature_names,
            "risk_thresholds": CONFIG.RISK_THRESHOLDS,
            "prediction_count": self.prediction_count,
            "model_loaded": self.model is not None,
            "explainer_loaded": self.explainer is not None,
            "scaler_loaded": self.scaler is not None,
            "clinical_ranges": CONFIG.CLINICAL_RANGES
        }

# Global model manager
model_manager = ClinicalModelManager()

# ===============================================================================
# API ENDPOINTS
# ===============================================================================

def get_authentication(pwd: str = Header(..., alias="X-API-Key")) -> bool:
    """API key authentication"""
    if pwd != os.getenv("API_PASSWORD", "clinical2026"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

@router.post(
    "/demo",
    response_model=RiskAssessmentResponse,
    summary="Demo Risk Assessment",
    description="Generate demo risk assessment without actual ML prediction",
    tags=["Demo"]
)
async def demo_risk_assessment(
    vitals: Vitals,
    _: bool = Depends(get_authentication)
) -> RiskAssessmentResponse:
    """
    Demo endpoint for risk assessment.
    Returns simulated results without using actual ML models.
    """
    try:
        start_time = time.time()
        
        # Generate demo prediction
        demo_result = await model_manager.generate_demo_prediction(vitals)
        
        # Create mock SHAP explanation for demo
        mock_shap = SHAPExplanation(
            features=CONFIG.FEATURE_NAMES,
            values=[np.random.uniform(-0.5, 0.5) for _ in CONFIG.FEATURE_NAMES],
            base_value=0.5,
            feature_importance={
                feature: np.random.uniform(-0.5, 0.5) 
                for feature in CONFIG.FEATURE_NAMES
            }
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return RiskAssessmentResponse(
            demo=True,
            risk_score=demo_result.risk_score,
            risk_level=model_manager._calculate_risk_level(demo_result.risk_score),
            confidence=0.85,  # Mock confidence for demo
            assessment=f"Demo assessment for {model_manager._calculate_risk_level(demo_result.risk_score)} risk",
            recommendations=["This is a demo - consult actual healthcare provider"],
            shap=mock_shap,
            metadata={
                "demo_mode": True,
                "sample_vitals": demo_result.sample_vitals.dict() if demo_result.sample_vitals else None
            },
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"Demo assessment failed: {e}")
        raise HTTPException(status_code=500, detail="Demo assessment failed")

@router.post(
    "/full",
    response_model=RiskAssessmentResponse,
    summary="Full Risk Assessment",
    description="Complete clinical risk assessment with ML prediction and SHAP explanation",
    tags=["Assessment"]
)
async def full_risk_assessment(
    vitals: Vitals,
    _: bool = Depends(get_authentication)
) -> RiskAssessmentResponse:
    """
    Full risk assessment using machine learning prediction
    with SHAP explainability and clinical recommendations.
    """
    try:
        # Perform prediction
        assessment, shap_explanation = await model_manager.predict_risk(vitals)
        
        # Generate clinical assessment and recommendations
        clinical_assessment = model_manager._generate_clinical_assessment(
            assessment.risk_score, vitals
        )
        recommendations = model_manager._generate_recommendations(
            assessment.risk_level, vitals
        )
        
        return RiskAssessmentResponse(
            demo=False,
            risk_score=assessment.risk_score,
            risk_level=assessment.risk_level,
            confidence=assessment.confidence,
            assessment=clinical_assessment,
            recommendations=recommendations,
            shap=shap_explanation,
            metadata={
                "model_version": "3.0.0",
                "prediction_timestamp": assessment.timestamp,
                "patient_id": vitals.patient_id,
                "feature_count": len(CONFIG.FEATURE_NAMES)
            },
            processing_time_ms=assessment.prediction_time_ms
        )
        
    except Exception as e:
        logger.error(f"Full assessment failed: {e}")
        raise HTTPException(status_code=500, detail="Risk assessment failed")

@router.get(
    "/health",
    summary="Health Check",
    description="Check clinical predictor service health",
    tags=["Health"]
)
async def health_check() -> Dict[str, Any]:
    """Health check for clinical predictor service"""
    try:
        model_info = model_manager.get_model_info()
        
        # Test prediction with sample data
        test_vitals = Vitals(
            age=45.0, systolic_bp=120.0, diastolic_bp=80.0,
            cholesterol=200.0, bmi=25.0
        )
        
        test_assessment, _ = await model_manager.predict_risk(test_vitals)
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "clinical_risk_predictor",
            "version": "3.0.0",
            "model_info": model_info,
            "test_prediction": {
                "risk_score": test_assessment.risk_score,
                "risk_level": test_assessment.risk_level
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )

@router.get(
    "/model/info",
    summary="Model Information",
    description="Get detailed information about the clinical prediction model",
    tags=["Information"]
)
async def get_model_info() -> Dict[str, Any]:
    """Get comprehensive model information"""
    try:
        model_info = model_manager.get_model_info()
        
        # Add additional statistics
        model_info.update({
            "service_version": "3.0.0",
            "api_version": "v1",
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "configuration": {
                "risk_thresholds": CONFIG.RISK_THRESHOLDS,
                "clinical_ranges": CONFIG.CLINICAL_RANGES,
                "feature_names": CONFIG.FEATURE_NAMES,
                "caching_enabled": CONFIG.ENABLE_CACHING
            },
            "performance": {
                "prediction_count": model_manager.prediction_count,
                "average_prediction_time": "Not tracked",
                "model_accuracy": "Not available"
            }
        })
        
        return model_info
        
    except Exception as e:
        logger.error(f"Model info failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get model info")

@router.post(
    "/batch/assess",
    summary="Batch Risk Assessment",
    description="Assess risk for multiple patients",
    tags=["Batch Processing"]
)
async def batch_risk_assessment(
    vitals_list: List[Vitals],
    _: bool = Depends(get_authentication)
) -> List[RiskAssessmentResponse]:
    """
    Batch risk assessment for multiple patients.
    Maximum 50 patients per batch.
    """
    try:
        if len(vitals_list) > 50:
            raise HTTPException(
                status_code=400, 
                detail="Batch size too large (max 50 patients)"
            )
        
        results = []
        for vitals in vitals_list:
            assessment, shap_explanation = await model_manager.predict_risk(vitals)
            
            clinical_assessment = model_manager._generate_clinical_assessment(
                assessment.risk_score, vitals
            )
            recommendations = model_manager._generate_recommendations(
                assessment.risk_level, vitals
            )
            
            results.append(
                RiskAssessmentResponse(
                    demo=False,
                    risk_score=assessment.risk_score,
                    risk_level=assessment.risk_level,
                    confidence=assessment.confidence,
                    assessment=clinical_assessment,
                    recommendations=recommendations,
                    shap=shap_explanation,
                    metadata={
                        "patient_id": vitals.patient_id,
                        "batch_index": len(results)
                    },
                    processing_time_ms=assessment.prediction_time_ms
                )
            )
        
        return results
        
    except Exception as e:
        logger.error(f"Batch assessment failed: {e}")
        raise HTTPException(status_code=500, detail="Batch assessment failed")

# ===============================================================================
# UTILITY ENDPOINTS
# ===============================================================================

@router.get(
    "/stats",
    summary="Service Statistics",
    description="Get clinical predictor service statistics",
    tags=["Monitoring"]
)
async def get_service_stats() -> Dict[str, Any]:
    """Get service statistics and performance metrics"""
    try:
        return {
            "service": "clinical_risk_predictor",
            "version": "3.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "model_info": model_manager.get_model_info(),
            "configuration": {
                "risk_thresholds": CONFIG.RISK_THRESHOLDS,
                "feature_count": len(CONFIG.FEATURE_NAMES),
                "caching_enabled": CONFIG.ENABLE_CACHING
            },
            "statistics": {
                "total_predictions": model_manager.prediction_count,
                "active_models": ACTIVE_MODELS._value.get() or 0
            }
        }
        
    except Exception as e:
        logger.error(f"Stats endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

# ===============================================================================
# EXCEPTION HANDLERS
# ===============================================================================

@router.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging"""
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail} - "
        f"Request: {request.method} {request.url.path}"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": request.url.path
        }
    )

@router.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(
        f"Unhandled exception: {str(exc)} - "
        f"Request: {request.method} {request.url.path}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )

# ===============================================================================
# VALIDATION UTILITY
# ===============================================================================

def validate_vitals_ranges(vitals: Vitals) -> List[str]:
    """Validate vitals against clinical ranges and return warnings"""
    warnings = []
    
    for feature, (min_val, max_val) in CONFIG.CLINICAL_RANGES.items():
        value = getattr(vitals, feature)
        if value < min_val or value > max_val:
            warnings.append(
                f"{feature.replace('_', ' ').title()} ({value}) "
                f"outside normal range ({min_val}-{max_val})"
            )
    
    return warnings

# Export for testing
__all__ = [
    "router",
    "ClinicalModelManager",
    "RiskAssessment",
    "SHAPExplanation",
    "Vitals",
    "validate_vitals_ranges"
]
