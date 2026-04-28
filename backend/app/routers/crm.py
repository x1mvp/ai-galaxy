<<< HEAD
-"""
=======
"""
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
app/routers/crm.py

CRM (Customer Relationship Management) module router.
Provides lead scoring, customer segmentation, and sales predictions.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["CRM"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

# Data Models
class LeadData(BaseModel):
    """Lead scoring input data"""
    company_size: str = Field(..., description="Company size (Small, Medium, Large, Enterprise)")
    industry: str = Field(..., description="Industry sector")
    contact_role: str = Field(..., description="Contact role (Decision Maker, Influencer, User)")
    budget_range: str = Field(..., description="Budget range")
    timeline: str = Field(..., description="Purchase timeline")
    engagement_score: int = Field(..., ge=0, le=100, description="Current engagement score")

class LeadScore(BaseModel):
    """Lead scoring result"""
    lead_score: int = Field(..., ge=0, le=100, description="Lead quality score")
    tier: str = Field(..., description="Lead tier (Hot, Warm, Cool)")
    conversion_probability: float = Field(..., ge=0.0, le=1.0)
    recommended_action: str = Field(..., description="Recommended next action")

class LeadScoringResponse(BaseModel):
    """Lead scoring API response"""
    success: bool
    lead_score: LeadScore
    factors: Dict[str, Any]
    processing_time: float

# Endpoints
<<<<<<< HEAD
@router.get("/health")
async def crm_health():
    """CRM service health check"""
    return {
        "service": "CRM",
        "status": "healthy",
        "features": ["lead_scoring", "customer_segmentation"],
        "version": "1.0.0"
    }

=======
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
@router.post("/lead-score", response_model=LeadScoringResponse)
async def score_lead(
    lead_data: LeadData,
    background_tasks: BackgroundTasks
) -> LeadScoringResponse:
    """
    Score a lead based on company and contact characteristics.
    Returns lead quality score and recommendations.
    """
    try:
        # Log request asynchronously
        background_tasks.add_task(
            logger.info, 
            f"Lead scoring request for {lead_data.industry} company"
        )
        
        # Simplified lead scoring logic
        base_score = 50
        
        # Company size factor
        size_scores = {"Small": 10, "Medium": 20, "Large": 30, "Enterprise": 40}
        base_score += size_scores.get(lead_data.company_size, 0)
        
        # Industry factor
        industry_scores = {
            "Technology": 25, "Finance": 20, "Healthcare": 15,
            "Manufacturing": 10, "Retail": 8, "Other": 5
        }
        base_score += industry_scores.get(lead_data.industry, 5)
        
        # Role factor
        role_scores = {"Decision Maker": 15, "Influencer": 10, "User": 5}
        base_score += role_scores.get(lead_data.contact_role, 0)
        
        # Budget and timeline factors
        if lead_data.budget_range in ["High", "Medium-High"]:
            base_score += 15
        elif lead_data.budget_range in ["Medium", "Medium-Low"]:
            base_score += 10
        
        if lead_data.timeline in ["Immediate", "1-3 months"]:
            base_score += 10
        elif lead_data.timeline in ["3-6 months"]:
            base_score += 5
        
        # Cap at 100
        lead_score = min(base_score + lead_data.engagement_score // 10, 100)
        
        # Determine tier
        if lead_score >= 80:
            tier = "Hot"
            conversion_probability = 0.7 + (lead_score - 80) * 0.03
            action = "Immediate sales follow-up, priority treatment"
        elif lead_score >= 60:
            tier = "Warm"
            conversion_probability = 0.4 + (lead_score - 60) * 0.015
            action = "Nurturing campaign, sales demo within 2 weeks"
        else:
            tier = "Cool"
            conversion_probability = 0.1 + lead_score * 0.005
            action = "Email nurturing, periodic check-ins"
        
        return LeadScoringResponse(
            success=True,
            lead_score=LeadScore(
                lead_score=lead_score,
                tier=tier,
                conversion_probability=min(conversion_probability, 1.0),
                recommended_action=action
            ),
            factors={
                "company_size": size_scores.get(lead_data.company_size, 0),
                "industry": industry_scores.get(lead_data.industry, 5),
                "contact_role": role_scores.get(lead_data.contact_role, 0),
                "engagement_score": lead_data.engagement_score
            },
            processing_time=125.5
        )
        
    except Exception as e:
        logger.error(f"Lead scoring failed: {e}")
        raise HTTPException(status_code=500, detail=f"Lead scoring failed: {str(e)}")
<<<<<<< HEAD
=======

@router.get("/health")
async def crm_health():
    """CRM service health check"""
    return {
        "service": "CRM",
        "status": "healthy",
        "features": ["lead_scoring", "customer_segmentation"],
        "version": "1.0.0"
    }
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
