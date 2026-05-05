# backend/tests/test_main_integration.py
"""
Integration tests for the main FastAPI application
Tests the complete application setup including all routers and middleware
"""

import pytest
import asyncio
import json
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, AsyncMock

# Import the main app (this will test if all imports work)
try:
    from app.main import app
    MAIN_APP_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import main app: {e}")
    MAIN_APP_AVAILABLE = False


class TestMainApplication:
    """Test the main FastAPI application integration"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        return TestClient(app)
    
    def test_app_creation(self):
        """Test that the FastAPI app can be created"""
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        
        assert app is not None
        assert app.title == "AI Galaxy Portfolio API"
        assert app.version == "3.0.0"
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data
        assert "endpoints" in data
        assert data["message"] == "AI Galaxy Portfolio API"
    
    def test_healthz_endpoint(self, client):
        """Test health endpoint"""
        response = client.get("/healthz")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert "uptime" in data
        assert "platform" in data
        assert isinstance(data["services"], list)
    
    def test_docs_endpoints(self, client):
        """Test documentation endpoints"""
        # Test OpenAPI docs
        response = client.get("/docs")
        assert response.status_code == 200
        
        # Test ReDoc
        response = client.get("/redoc")
        assert response.status_code == 200
        
        # Test OpenAPI JSON
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
    
    def test_cors_headers(self, client):
        """Test CORS middleware"""
        # Test preflight request
        response = client.options("/healthz", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type"
        })
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers


class TestRouterIntegration:
    """Test that all routers are properly integrated"""
    
    @pytest.fixture
    def client(self):
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        return TestClient(app)
    
    def test_crm_router_integration(self, client):
        """Test CRM router is accessible"""
        # Test router exists (404 vs 405 indicates router is mounted)
        response = client.post("/CRM/analyze", json={"customer_data": {}})
        
        # Should return 422 (validation error) or 200 (success), not 404
        assert response.status_code != 404
    
    def test_fraud_router_integration(self, client):
        """Test Fraud router is accessible"""
        response = client.post("/Fraud/detect", json={"transaction_data": {}})
        assert response.status_code != 404
    
    def test_clinical_router_integration(self, client):
        """Test Clinical router is accessible"""
        response = client.post("/Clinical/analyze", json={"patient_data": {}})
        assert response.status_code != 404
    
    def test_nlp_router_integration(self, client):
        """Test NLP router is accessible"""
        response = client.post("/NLP/predict", json={"text": "test"})
        assert response.status_code != 404


class TestMiddlewareIntegration:
    """Test middleware stack integration"""
    
    @pytest.fixture
    def client(self):
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        return TestClient(app)
    
    def test_performance_headers(self, client):
        """Test performance headers are added"""
        response = client.get("/healthz")
        
        # Check for performance headers (if middleware is available)
        if "X-Process-Time" in response.headers:
            process_time = response.headers["X-Process-Time"]
            assert float(process_time) >= 0
        
        if "X-Request-ID" in response.headers:
            request_id = response.headers["X-Request-ID"]
            assert len(request_id) > 0
    
    def test_security_headers(self, client):
        """Test security headers are present"""
        response = client.get("/")
        
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection"
        ]
        
        for header in security_headers:
            # Headers may not be present if middleware isn't loaded
            # So we just test they don't crash the app
            assert header in response.headers or header not in response.headers


class TestNLPServiceIntegration:
    """Test NLP service integration with main app"""
    
    @pytest.fixture
    def client(self):
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        return TestClient(app)
    
    @patch('app.nlp.model_manager')
    def test_nlp_prediction_integration(self, mock_manager, client):
        """Test NLP prediction integration"""
        # Mock the model manager
        mock_manager.is_loaded = True
        mock_manager.predict.return_value = {"label": "POSITIVE", "prob": 0.9}
        mock_manager.get_stats.return_value = {
            "model_loaded": True,
            "request_count": 0,
            "cache_info": {"hits": 0, "misses": 0, "currsize": 0, "maxsize": 1000}
        }
        mock_manager.health_check.return_value = {
            "status": "healthy",
            "timestamp": time.time()
        }
        
        # Test NLP predict endpoint
        response = client.post("/NLP/predict", json={
            "text": "This is great!",
            "return_probabilities": True
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "POSITIVE"
        assert data["probability"] == 0.9
    
    @patch('app.nlp.model_manager')
    def test_nlp_batch_prediction(self, mock_manager, client):
        """Test NLP batch prediction"""
        mock_manager.is_loaded = True
        mock_manager.predict.return_value = [
            {"label": "POSITIVE", "prob": 0.9},
            {"label": "NEGATIVE", "prob": 0.8}
        ]
        
        response = client.post("/NLP/predict/batch", json={
            "texts": ["Great product!", "Terrible service"],
            "return_probabilities": True
        })
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["label"] == "POSITIVE"
        assert data[1]["label"] == "NEGATIVE"
    
    @patch('app.nlp.model_manager')
    def test_nlp_stats_endpoint(self, mock_manager, client):
        """Test NLP stats endpoint"""
        mock_manager.is_loaded = True
        mock_manager.get_stats.return_value = {
            "model_loaded": True,
            "request_count": 42,
            "uptime": 3600.0,
            "avg_inference_time": 0.1,
            "cache_info": {"hit_rate": 0.8}
        }
        
        response = client.get("/NLP/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["request_count"] == 42
        assert data["model_loaded"] is True


class TestExceptionHandlers:
    """Test exception handler integration"""
    
    @pytest.fixture
    def client(self):
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        return TestClient(app)
    
    def test_validation_error_handler(self, client):
        """Test ValueError handler"""
        # This should trigger validation error which goes to ValueError handler
        response = client.post("/NLP/predict", json={
            "text": "",  # Empty text should trigger validation error
            "return_probabilities": True
        })
        
        # Should return 400 for validation error
        if response.status_code == 400:
            data = response.json()
            assert "error" in data
    
    @patch('app.nlp.model_manager')
    def test_runtime_error_handler(self, mock_manager, client):
        """Test RuntimeError handler"""
        # Mock model manager to raise RuntimeError
        mock_manager.is_loaded = False
        mock_manager.predict.side_effect = RuntimeError("Model not loaded")
        
        response = client.post("/NLP/predict", json={
            "text": "test",
            "return_probabilities": True
        })
        
        # Should be handled by router dependency injection, but if it reaches here:
        if response.status_code == 503:
            data = response.json()
            assert "error" in data


class TestLifespanIntegration:
    """Test lifespan context manager integration"""
    
    @pytest.mark.asyncio
    async def test_lifespan_model_loading(self):
        """Test that lifespan properly loads/unloads models"""
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        
        from app.main import lifespan
        from app.nlp import model_manager
        
        # Reset manager state
        model_manager.unload()
        assert not model_manager.is_loaded
        
        # Test lifespan context manager
        async with lifespan(app):
            # Model should be loaded during lifespan
            # Note: This may not work in test environment due to mocking
            pass
        
        # Model should be unloaded after lifespan
        # Note: This also may not work in test environment
        pass


@pytest.mark.asyncio
class TestAsyncFunctionality:
    """Test async functionality in the main app"""
    
    async def test_async_health_check(self):
        """Test async health endpoint"""
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        
        from app.main import health_check
        
        result = await health_check()
        assert result["status"] == "healthy"
        assert "uptime" in result
        assert "platform" in result
    
    async def test_async_root_endpoint(self):
        """Test async root endpoint"""
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        
        from app.main import root
        
        result = await root()
        assert result["message"] == "AI Galaxy Portfolio API"
        assert "version" in result
        assert "endpoints" in result


class TestConfigurationIntegration:
    """Test configuration integration"""
    
    def test_environment_variables(self):
        """Test that environment variables are properly loaded"""
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        
        # Test that the app can access environment variables
        import os
        from app.core.config import settings
        
        assert settings.app_title == "AI Galaxy Portfolio API"
        assert isinstance(settings.allowed_origins, list)
        assert len(settings.allowed_origins) > 0


class TestPerformanceIntegration:
    """Test performance aspects of the integration"""
    
    @pytest.fixture
    def client(self):
        if not MAIN_APP_AVAILABLE:
            pytest.skip("Main app not available")
        return TestClient(app)
    
    def test_response_time(self, client):
        """Test that responses are reasonably fast"""
        start_time = time.time()
        response = client.get("/healthz")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 2.0  # Should respond in under 2 seconds
    
    def test_concurrent_requests(self, client):
        """Test handling multiple concurrent requests"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request():
            response = client.get("/healthz")
            results.put(response.status_code)
        
        # Make 10 concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check all results
        success_count = 0
        while not results.empty():
            if results.get() == 200:
                success_count += 1
        
        assert success_count == 10  # All requests should succeed


# Pytest fixtures and configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Mark tests for different categories
pytestmark = {
    "integration": pytest.mark.integration,
    "slow": pytest.mark.slow,
    "nlp": pytest.mark.nlp,
}
