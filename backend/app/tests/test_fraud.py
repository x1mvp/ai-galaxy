"""
Tests for Fraud Detection module endpoints.
"""

import pytest
from fastapi.testclient import TestClient

def test_fraud_health(test_client):
    """Test Fraud detection health endpoint"""
    response = test_client.get("/Fraud/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Fraud Detection"
    assert data["status"] == "healthy"

def test_fraud_analysis(test_client):
    """Test fraud analysis endpoint"""
    payload = {
        "amount": 5000.0,
        "currency": "USD",
        "merchant_category": "retail",
        "location": "New York",
        "time_of_day": 14,
        "customer_age": 35,
        "account_age_days": 365,
        "transaction_frequency": 5
    }
    
    response = test_client.post("/Fraud/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "risk_assessment" in data
    assert data["risk_assessment"]["risk_score"] >= 0.0
    assert data["risk_assessment"]["risk_score"] <= 1.0
