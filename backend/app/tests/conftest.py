ckend/tests/conftest.py
import os
import pytest
from unittest.mock import MagicMock, patch

# Tell ModelConfig.validate() to skip the file-existence check
os.environ["TESTING"] = "true"


@pytest.fixture(autouse=True)
def mock_model_manager():
    """
    Patch model_manager so tests never need the real bert.onnx file.
    autouse=True means every test gets this automatically - no decorator needed.
    """
    mock_manager = MagicMock()
    mock_manager.is_loaded = True
    mock_manager.predict.return_value = [
        {"label": "Technology", "score": 0.91},
        {"label": "Finance",    "score": 0.72},
        {"label": "Healthcare", "score": 0.55},
        {"label": "Legal",      "score": 0.41},
        {"label": "Marketing",  "score": 0.28},
    ]

    with patch("app.nlp.model_manager", mock_manager):
        yield mock_manager


@pytest.fixture
def test_client():
    """
    FastAPI TestClient with lifespan disabled so startup never calls
    model_manager.load() against a missing file.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
