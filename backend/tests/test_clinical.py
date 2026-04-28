""
Tests for Clinical Analytics module endpoints.
"""

import pytest
from fastapi.testclient import TestClient

def test_clinical_health(test_client):
    """Test Clinical analytics health endpoint"""
    response = test_client.get("/Clinical/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Clinical Analytics"
    assert data["status"] == "healthy"

def test_clinical_assessment(test_client):
    """Test clinical risk assessment endpoint"""
    payload = {
        "age": 45,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "heart_rate": 72,
        "glucose": 95,
        "cholesterol": 190,
        "bmi": 24.5,
        "smoking_status": "Never",
        "exercise_frequency": "Moderate"
    }
    
    response = test_client.post("/Clinical/assess", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "assessment" in data
    assert "recommendations" in data
    assert data["assessment"]["cardiovascular_risk"] >= 0.0
    assert data["assessment"]["cardiovascular_risk"] <= 1.0
