"""Tests for NLP Classification Service"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.nlp import TextPayload, PredictionResult

client = TestClient(app)

class TestNLPEndpoints:
    """Test NLP classification endpoints"""
    
    def test_demo_endpoint_success(self):
        """Test demo endpoint returns valid response"""
        payload = {"text": "This is a test message"}
        response = client.post("/nlp/demo", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["demo"] is True
        assert "predictions" in data
        assert len(data["predictions"]) > 0
    
    def test_full_endpoint_success(self):
        """Test full endpoint with mocked model"""
        with patch('app.nlp.model_manager') as mock_manager:
            mock_manager.predict_single.return_value = [
                PredictionResult(label="tech", prob=0.8)
            ]
            
            payload = {"text": "Technology news and updates"}
            response = client.post("/nlp/full", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data["demo"] is False
            assert len(data["predictions"]) == 1
    
    def test_text_validation_empty(self):
        """Test validation of empty text"""
        payload = {"text": ""}
        response = client.post("/nlp/demo", json=payload)
        
        assert response.status_code == 422
    
    def test_text_validation_too_long(self):
        """Test validation of text that's too long"""
        payload = {"text": "x" * 10001}
        response = client.post("/nlp/demo", json=payload)
        
        assert response.status_code == 422
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/nlp/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "model_loaded" in data
