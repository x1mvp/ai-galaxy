
Tests for CRM module endpoints.
"""

import pytest
from fastapi.testclient import TestClient

def test_crm_health(test_client):
    """Test CRM health endpoint"""
    response = test_client.get("/CRM/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CRM"
    assert data["status"] == "healthy"

def test_lead_scoring(test_client):
    """Test lead scoring endpoint"""
    payload = {
        "company_size": "Large",
        "industry": "Technology",
        "contact_role": "Decision Maker",
        "budget_range": "High",
        "timeline": "Immediate",
        "engagement_score": 80
    }
    
    response = test_client.post("/CRM/lead-score", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "lead_score" in data
    assert data["lead_score"]["lead_score"] >= 0
    assert data["lead_score"]["lead_score"] <= 100
