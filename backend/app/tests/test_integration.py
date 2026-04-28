
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

def test_healthz_endpoint(test_client):
    """Test healthz endpoint for monitoring"""
    response = test_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data
    assert len(data["services"]) == 4

def test_docs_accessible(test_client):
    """Test that documentation endpoints are accessible"""
    # Test Swagger UI
    response = test_client.get("/docs")
    assert response.status_code == 200
    
    # Test ReDoc
    response = test_client.get("/redoc")
    assert response.status_code == 200
    
    # Test OpenAPI schema
    response = test_client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "paths" in data
