# backend/tests/conftest.py
"""
Pytest configuration and fixtures for AI Galaxy API tests
"""

import os
import sys
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient

# Add backend to Python path for tests
current_dir = Path(__file__).parent
backend_dir = current_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Set testing environment
os.environ["TESTING"] = "true"

# Try to import app components
try:
    from app.main import app
    from app.nlp import model_manager
    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False
    app = None
    model_manager = None


@pytest.fixture(scope="session")
def test_config():
    """Test configuration settings"""
    return {
        "test_model_name": "distilbert-base-uncased-finetuned-sst-2-english",
        "test_batch_size": 4,
        "test_max_length": 128,
    }


@pytest.fixture
def mock_model_manager():
    """Mock model manager for testing"""
    mock_manager = Mock()
    mock_manager.is_loaded = True
    mock_manager.request_count = 0
    mock_manager.total_inference_time = 0.0
    mock_manager.error_count = 0
    mock_manager._start_time = 1234567890.0
    
    mock_manager.predict.return_value = {"label": "POSITIVE", "prob": 0.9}
    mock_manager.get_stats.return_value = {
        "model_loaded": True,
        "request_count": 0,
        "error_count": 0,
        "avg_inference_time": 0.1,
        "cache_info": {"hits": 0, "misses": 0, "hit_rate": 0.0}
    }
    mock_manager.health_check.return_value = {
        "status": "healthy",
        "timestamp": 1234567890.0
    }
    
    return mock_manager


@pytest.fixture
def client():
    """Test client for FastAPI app"""
    if not APP_AVAILABLE:
        pytest.skip("FastAPI app not available")
    return TestClient(app)


@pytest.fixture
def sample_text_data():
    """Sample text data for testing"""
    return {
        "positive": "This is an amazing product! I love it so much.",
        "negative": "This is terrible. I hate everything about it.",
        "neutral": "This is a product. It has features.",
        "short": "Great!",
        "long": "This is an exceptionally long piece of text that " * 20,
        "empty": "",
    }


@pytest.fixture
def sample_batch_data():
    """Sample batch data for testing"""
    return [
        "I love this product!",
        "This is terrible quality.",
        "It's okay, nothing special.",
        "Best purchase ever made!",
        "Would not recommend to anyone.",
    ]


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables for testing"""
    original_env = os.environ.copy()
    
    # Set test environment variables
    os.environ.update({
        "TESTING": "true",
        "LOG_LEVEL": "WARNING",  # Reduce log noise in tests
        "NLP_MODEL_NAME": "distilbert-base-uncased-finetuned-sst-2-english",
        "NLP_BATCH_SIZE": "4",
        "NLP_MAX_LENGTH": "128",
    })
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Custom pytest markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "nlp: marks tests that require NLP functionality"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


@pytest.fixture
def mock_transformers():
    """Mock transformers library for faster tests"""
    mock_pipeline = Mock()
    mock_pipeline.return_value = [{"label": "POSITIVE", "score": 0.9}]
    
    with pytest.mock.patch("transformers.pipeline", return_value=mock_pipeline):
        yield mock_pipeline


# Skip tests if dependencies are not available
def pytest_collection_modifyitems(config, items):
    """Skip tests based on available dependencies"""
    if not APP_AVAILABLE:
        skip_app = pytest.mark.skip(reason="FastAPI app not available")
        for item in items:
            if "main_integration" in item.nodeid or "test_main" in item.nodeid:
                item.add_marker(skip_app)
