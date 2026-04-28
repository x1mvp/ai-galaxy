import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

@pytest.fixture
def test_client():
    app = FastAPI(title="Test App")
    
    # CRM endpoints
    @app.get("/CRM/health")
    async def crm_health():
        return {"service": "CRM", "status": "healthy"}
    
    @app.post("/CRM/lead-score")
    async def lead_score(payload: dict):
        return {
            "success": True,
            "lead_score": {
                "lead_score": 85,
                "tier": "Hot",
                "conversion_probability": 0.75,
                "recommended_action": "Immediate sales follow-up"
            },
            "factors": {
                "company_size": 30,
                "industry": 25,
                "contact_role": 15,
                "engagement_score": 8
            },
            "processing_time": 125.5
        }
    
    # Fraud endpoints
    @app.get("/Fraud/health")
    async def fraud_health():
        return {"service": "Fraud Detection", "status": "healthy"}
    
    @app.post("/Fraud/analyze")
    async def fraud_analyze(payload: dict):
        return {
            "transaction_safe": True,
            "risk_assessment": {
                "risk_score": 0.15,
                "risk_level": "Low",
                "flagged": False,
                "reasons": ["No significant risk factors"]
            },
            "recommendations": [
                "Process normally",
                "Standard monitoring",
                "No additional actions needed"
            ],
            "processing_time": 89.3
        }
    
    # Clinical endpoints
    @app.get("/Clinical/health")
    async def clinical_health():
        return {"service": "Clinical Analytics", "status": "healthy"}
    
    @app.post("/Clinical/assess")
    async def clinical_assess(payload: dict):
        return {
            "assessment": {
                "cardiovascular_risk": 0.12,
                "diabetes_risk": 0.08,
                "overall_risk": "Low",
                "risk_factors": ["Age 45", "Moderate exercise"]
            },
            "recommendations": [
                "Maintain current health regimen",
                "Regular check-ups",
                "Healthy lifestyle maintenance"
            ],
            "alert_level": "ROUTINE",
            "processing_time": 156.7
        }
    
    # NLP endpoints
    @app.get("/NLP/health")
    async def nlp_health():
        return {"service": "NLP Classification", "status": "healthy"}
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "Test API",
            "version": "3.0.0",
            "docs": "/docs",
            "health": "/healthz",
            "endpoints": ["/CRM", "/Fraud", "/Clinical", "/NLP"]
        }
    
    with TestClient(app) as client:
        yield client
