<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
app/routers/clinical.py

Clinical Analytics module router.
Provides patient risk assessment and medical data analysis.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Clinical"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

# Data Models
class PatientData(BaseModel):
    """Patient clinical data"""
    age: int = Field(..., ge=0, le=150, description="Patient age")
    systolic_bp: int = Field(..., ge=0, le=300, description="Systolic blood pressure")
    diastolic_bp: int = Field(..., ge=0, le=200, description="Diastolic blood pressure")
    heart_rate: int = Field(..., ge=0, le=300, description="Heart rate (bpm)")
    glucose: float = Field(..., ge=0, description="Blood glucose level")
    cholesterol: float = Field(..., ge=0, description="Total cholesterol")
    bmi: float = Field(..., ge=0, description="Body mass index")
    smoking_status: str = Field(..., description="Smoking status (Never, Former, Current)")
    exercise_frequency: str = Field(..., description="Exercise frequency (None, Low, Moderate, High)")

class RiskScore(BaseModel):
    """Clinical risk assessment"""
    cardiovascular_risk: float = Field(..., ge=0.0, le=1.0, description="Cardiovascular disease risk")
    diabetes_risk: float = Field(..., ge=0.0, le=1.0, description="Diabetes risk")
    overall_risk: str = Field(..., description="Overall risk level")
    risk_factors: List[str] = Field(..., description="Identified risk factors")

class ClinicalAssessmentResponse(BaseModel):
    """Clinical assessment API response"""
    assessment: RiskScore
    recommendations: List[str]
    alert_level: str
    processing_time: float

# Endpoints
<<<<<<< HEAD
@router.get("/health")
async def clinical_health():
    """Clinical analytics service health check"""
    return {
        "service": "Clinical Analytics",
        "status": "healthy",
        "features": ["risk_assessment", "patient_analytics"],
        "version": "1.0.0"
    }

=======
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
@router.post("/assess", response_model=ClinicalAssessmentResponse)
async def assess_patient_risk(
    patient: PatientData,
    background_tasks: BackgroundTasks
) -> ClinicalAssessmentResponse:
    """
    Assess patient clinical risk based on vital signs and lifestyle factors.
    Returns risk scores and medical recommendations.
    """
    try:
        background_tasks.add_task(
            logger.info,
            f"Clinical assessment for patient age {patient.age}"
        )
        
        risk_factors = []
        cv_risk = 0.0
        diabetes_risk = 0.0
        
        # Age-based risk
        if patient.age >= 65:
            risk_factors.append("Advanced age")
            cv_risk += 0.2
            diabetes_risk += 0.15
        elif patient.age >= 45:
            cv_risk += 0.1
            diabetes_risk += 0.1
        
        # Blood pressure risk
        if patient.systolic_bp >= 140 or patient.diastolic_bp >= 90:
            risk_factors.append("Hypertension")
            cv_risk += 0.25
        elif patient.systolic_bp >= 130 or patient.diastolic_bp >= 80:
            risk_factors.append("Elevated blood pressure")
            cv_risk += 0.15
        
        # Heart rate risk
        if patient.heart_rate > 100 or patient.heart_rate < 60:
            risk_factors.append("Abnormal heart rate")
            cv_risk += 0.1
        
        # Glucose risk
        if patient.glucose >= 126:
            risk_factors.append("High blood glucose")
            diabetes_risk += 0.3
        elif patient.glucose >= 100:
            risk_factors.append("Elevated blood glucose")
            diabetes_risk += 0.2
        
        # Cholesterol risk
        if patient.cholesterol >= 240:
            risk_factors.append("High cholesterol")
            cv_risk += 0.2
        elif patient.cholesterol >= 200:
            risk_factors.append("Borderline high cholesterol")
            cv_risk += 0.1
        
        # BMI risk
        if patient.bmi >= 30:
            risk_factors.append("Obesity")
            cv_risk += 0.15
            diabetes_risk += 0.2
        elif patient.bmi >= 25:
            risk_factors.append("Overweight")
            cv_risk += 0.1
            diabetes_risk += 0.1
        
        # Lifestyle risks
        if patient.smoking_status == "Current":
            risk_factors.append("Current smoker")
            cv_risk += 0.3
        elif patient.smoking_status == "Former":
            risk_factors.append("Former smoker")
            cv_risk += 0.1
        
        if patient.exercise_frequency == "None":
            risk_factors.append("Sedentary lifestyle")
            cv_risk += 0.15
            diabetes_risk += 0.1
        elif patient.exercise_frequency == "Low":
            cv_risk += 0.05
        
        # Cap risks at 1.0
        cv_risk = min(cv_risk, 1.0)
        diabetes_risk = min(diabetes_risk, 1.0)
        
        # Overall risk assessment
        max_risk = max(cv_risk, diabetes_risk)
        if max_risk >= 0.7:
            overall_risk = "High"
            alert_level = "URGENT"
            recommendations = [
                "Immediate medical consultation required",
                "Comprehensive diagnostic testing recommended",
                "Lifestyle intervention program",
                "Regular monitoring essential"
            ]
        elif max_risk >= 0.4:
            overall_risk = "Moderate"
            alert_level = "ATTENTION"
            recommendations = [
                "Medical follow-up recommended",
                "Lifestyle modifications advised",
                "Preventive screening suggested",
                "Regular monitoring"
            ]
        else:
            overall_risk = "Low"
            alert_level = "ROUTINE"
            recommendations = [
                "Maintain current health regimen",
                "Regular check-ups",
                "Healthy lifestyle maintenance",
                "Preventive care"
            ]
        
        return ClinicalAssessmentResponse(
            assessment=RiskScore(
                cardiovascular_risk=cv_risk,
                diabetes_risk=diabetes_risk,
                overall_risk=overall_risk,
                risk_factors=risk_factors if risk_factors else ["No significant risk factors identified"]
            ),
            recommendations=recommendations,
            alert_level=alert_level,
            processing_time=156.7
        )
        
    except Exception as e:
        logger.error(f"Clinical assessment failed: {e}")
        raise HTTPException(status_code=500, detail=f"Clinical assessment failed: {str(e)}")
<<<<<<< HEAD
=======

@router.get("/health")
async def clinical_health():
    """Clinical analytics service health check"""
    return {
        "service": "Clinical Analytics",
        "status": "healthy",
        "features": ["risk_assessment", "patient_analytics"],
        "version": "1.0.0"
    }
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
