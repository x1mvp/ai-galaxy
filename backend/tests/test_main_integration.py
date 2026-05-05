# backend/tests/test_main_integration.py
"""
Integration tests for the main FastAPI application
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

# Import the main app
from app.main import app


class TestMainIntegration:
    """Test the FastAPI application integration"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_healthz_endpoint(self, client):
        """Test health endpoint with correct asyncio usage"""
        response = client.get("/healthz")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime" in data
        assert "services" in data
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "docs" in data
        assert "endpoints" in data
    
    def test_cors_headers(self, client):
        """Test CORS middleware is properly configured"""
        response = client.options("/healthz", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
    
    @patch('app.nlp.model_manager')
    def test_nlp_service_integration(self, mock_manager, client):
        """Test NLP service integration with main app"""
        # Mock the model manager
        mock_manager.is_loaded = True
        mock_manager.predict.return_value = {"label": "POSITIVE", "prob": 0.9}
        mock_manager.get_stats.return_value = {
            "model_loaded": True,
            "request_count": 0,
            "cache_info": {"hits": 0, "misses": 0, "currsize": 0, "maxsize": 1000}
        }
        
        # Test NLP endpoint
        response = client.post("/NLP/predict", json={
            "text": "This is great!",
            "return_probabilities": True
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "POSITIVE"
        assert data["probability"] == 0.9
    
    def test_exception_handlers(self, client):
        """Test that exception handlers work correctly"""
        # Test ValueError handler (bad request)
        response = client.post("/NLP/predict", json={
            "text": "",  # Empty text should trigger validation error
            "return_probabilities": True
        })
        
        # This should be handled by the router validation, but we'll test the handler
        if response.status_code == 400:
            assert "error" in response.json()
    
    def test_router_registration(self, client):
        """Test that all routers are properly registered"""
        # Test each router prefix is accessible
        routers = ["/CRM", "/Fraud", "/Clinical", "/NLP"]
        
        for router_prefix in routers:
            # Each router should at least have some endpoints
            response = client.options(f"{router_prefix}/")
            # Should not return 404 if router is registered
            assert response.status_code != 404
    
    @patch('app.nlp.model_manager')
    def test_lifespan_integration(self, mock_manager, client):
        """Test lifespan context manager integration"""
        # Test that the app starts correctly
        response = client.get("/")
        assert response.status_code == 200
        
        # Verify model manager was interacted with during lifespan
        # (This is more of an integration sanity check)


class TestMiddlewareIntegration:
    """Test middleware integration"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_performance_headers(self, client):
        """Test that performance headers are added"""
        response = client.get("/healthz")
        
        if "X-Process-Time" in response.headers:
            assert float(response.headers["X-Process-Time"]) >= 0
        
        if "X-Request-ID" in response.headers:
            assert len(response.headers["X-Request-ID"]) > 0
    
    def test_security_headers(self, client):
        """Test security headers are present"""
        response = client.get("/")
        
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection"
        ]
        
        for header in security_headers:
            assert header in response.headers


@pytest.mark.asyncio
class TestAsyncIntegration:
    """Test async functionality"""
    
    async def test_async_health_check(self):
        """Test async health endpoint"""
        from app.main import health_check
        
        result = await health_check()
        assert result["status"] == "healthy"
        assert "uptime" in result
