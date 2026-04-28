"""
x1mvp Portfolio - Clinical Analytics Router.
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

class PatientData(BaseModel):
    """Patient clinical data"""
    age: int = Field(..., ge=0, le=150)
    systolic_bp: int = Field(..., ge=0, le=300)
    diastolic_bp: int = Field(..., ge=0, le=200)
    heart_rate: int = Field(..., ge=0, le=300)
    glucose: float = Field(..., ge=0)
    cholesterol: float = Field(..., ge=0)
    bmi: float = Field(..., ge=0)
    smoking_status: str = Field(..., description="Never, Former, or Current")
    exercise_frequency: str = Field(..., description="None, Low, Moderate, or High")

class RiskScore(BaseModel):
    cardiovascular_risk: float = Field(..., ge=0.0, le=1.0)
    diabetes_risk: float = Field(..., ge=0.0, le=1.0)
    overall_risk: str
    risk_factors: List[str]

class ClinicalAssessmentResponse(BaseModel):
    assessment: RiskScore
    recommendations: List[str]
    alert_level: str
    processing_time: float

@router.get("/health")
async def clinical_health():
    """Clinical analytics service health check"""
    return {
        "service": "Clinical Analytics",
        "status": "healthy",
        "features": ["risk_assessment", "patient_analytics"],
        "version": "1.0.0"
    }

@router.post("/assess", response_model=ClinicalAssessmentResponse)
async def assess_patient_risk(
    patient: PatientData,
    background_tasks: BackgroundTasks
) -> ClinicalAssessmentResponse:
    """Assess patient clinical risk based on vital signs and lifestyle factors."""
    try:
        background_tasks.add_task(logger.info, f"Clinical assessment for patient age {patient.age}")

        risk_factors = []
        cv_risk = 0.0
        diabetes_risk = 0.0

        if patient.age >= 65:
            risk_factors.append("Advanced age")
            cv_risk += 0.2
            diabetes_risk += 0.15
        elif patient.age >= 45:
            cv_risk += 0.1
            diabetes_risk += 0.1

        if patient.systolic_bp >= 140 or patient.diastolic_bp >= 90:
            risk_factors.append("Hypertension")
            cv_risk += 0.25
        elif patient.systolic_bp >= 130 or patient.diastolic_bp >= 80:
            risk_factors.append("Elevated blood pressure")
            cv_risk += 0.15

        if patient.heart_rate > 100 or patient.heart_rate < 60:
            risk_factors.append("Abnormal heart rate")
            cv_risk += 0.1

        if patient.glucose >= 126:
            risk_factors.append("High blood glucose")
            diabetes_risk += 0.3
        elif patient.glucose >= 100:
            risk_factors.append("Elevated blood glucose")
            diabetes_risk += 0.2

        if patient.cholesterol >= 240:
            risk_factors.append("High cholesterol")
            cv_risk += 0.2
        elif patient.cholesterol >= 200:
            risk_factors.append("Borderline high cholesterol")
            cv_risk += 0.1

        if patient.bmi >= 30:
            risk_factors.append("Obesity")
            cv_risk += 0.15
            diabetes_risk += 0.2
        elif patient.bmi >= 25:
            risk_factors.append("Overweight")
            cv_risk += 0.1
            diabetes_risk += 0.1

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

        cv_risk = min(cv_risk, 1.0)
        diabetes_risk = min(diabetes_risk, 1.0)
        max_risk = max(cv_risk, diabetes_risk)

        if max_risk >= 0.7:
            overall_risk, alert_level = "High", "URGENT"
            recommendations = [
                "Immediate medical consultation required",
                "Comprehensive diagnostic testing recommended",
                "Lifestyle intervention program",
                "Regular monitoring essential"
            ]
        elif max_risk >= 0.4:
            overall_risk, alert_level = "Moderate", "ATTENTION"
            recommendations = [
                "Medical follow-up recommended",
                "Lifestyle modifications advised",
                "Preventive screening suggested",
                "Regular monitoring"
            ]
        else:
            overall_risk, alert_level = "Low", "ROUTINE"
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
                risk_factors=risk_factors or ["No significant risk factors identified"]
            ),
            recommendations=recommendations,
            alert_level=alert_level,
            processing_time=156.7
        )

    except Exception as e:
        logger.error(f"Clinical assessment failed: {e}")
        raise HTTPException(status_code=500, detail=f"Clinical assessment failed: {str(e)}")
