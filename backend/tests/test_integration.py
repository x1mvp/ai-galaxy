"""
Integration tests for the entire application.
"""

import pytest
from fastapi.testclient import TestClient

def test_all_health_endpoints(test_client):
    """Test that all service health endpoints are accessible"""
    services = [
        ("/CRM/health", "CRM"),
        ("/Fraud/health", "Fraud Detection"),
        ("/Clinical/health", "Clinical Analytics"),
        ("/NLP/health", "NLP Classification")
    ]

    for endpoint, service_name in services:
        response = test_client.get(endpoint)
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == service_name
        assert data["status"] == "healthy"

def test_root_endpoint(test_client):
    """Test root endpoint returns service information"""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "endpoints" in data
