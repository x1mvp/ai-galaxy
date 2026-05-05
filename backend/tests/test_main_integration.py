# tests/test_main_integration.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

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
        assert "uptime" in data  # Should use get_running_loop().time()
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
        # Test ValueError handler
        response = client.post("/NLP/predict", json={
            "text": "",  # Empty text should trigger validation error
            "return_probabilities": True
        })
        
        assert response.status_code == 400
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


class TestLifespanIntegration:
    """Test lifespan context manager integration"""
    
    @pytest.mark.asyncio
    async def test_lifespan_model_loading(self):
        """Test that lifespan properly loads/unloads models"""
        from app.main import lifespan
        from app.nlp import model_manager
        
        # Reset manager state
        model_manager.unload()
        assert not model_manager.is_loaded
        
        # Test lifespan context manager
        async with lifespan(app):
            assert model_manager.is_loaded
        
        # Model should be unloaded after lifespan
        assert not model_manager.is_loaded
    
    @pytest.mark.asyncio
    async def test_lifespan_error_handling(self):
        """Test lifespan error handling"""
        from app.main import lifespan
        from app.nlp import model_manager
        
        # Mock model loading to fail
        with patch.object(model_manager, 'load', side_effect=Exception("Load failed")):
            async with lifespan(app):
                # Should handle load failure gracefully
                pass
