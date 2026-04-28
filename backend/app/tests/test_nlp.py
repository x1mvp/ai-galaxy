ests for NLP Classification Service"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.nlp import TextPayload, PredictionResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Fresh TestClient per test — prevents state bleed between tests."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers():
    """Valid API key headers for full-access endpoints."""
    return {"X-API-Key": "test-api-key"}


@pytest.fixture()
def mock_model_manager():
    """
    Patch model_manager at the module level where it is used (not where it is
    defined).  Yields the mock so individual tests can customise return values
    or assert call arguments.
    """
    with patch("app.nlp.model_manager") as mock_manager:
        mock_manager.predict_single.return_value = [
            PredictionResult(label="tech", prob=0.85),
            PredictionResult(label="science", prob=0.10),
        ]
        yield mock_manager


# ---------------------------------------------------------------------------
# Demo endpoint
# ---------------------------------------------------------------------------

class TestDemoEndpoint:
    """POST /nlp/demo — no auth required, rate-limited."""

    def test_success_returns_200_and_predictions(self, client):
        response = client.post("/nlp/demo", json={"text": "This is a test message"})

        assert response.status_code == 200
        data = response.json()
        assert data["demo"] is True
        assert isinstance(data["predictions"], list)
        assert len(data["predictions"]) > 0

    def test_prediction_schema(self, client):
        """Each prediction must have a string label and a float probability."""
        response = client.post("/nlp/demo", json={"text": "Sample text for testing"})

        assert response.status_code == 200
        for prediction in response.json()["predictions"]:
            assert isinstance(prediction["label"], str)
            assert isinstance(prediction["prob"], float)
            assert 0.0 <= prediction["prob"] <= 1.0

    def test_empty_text_returns_422(self, client):
        response = client.post("/nlp/demo", json={"text": ""})
        assert response.status_code == 422

    def test_text_too_long_returns_422(self, client):
        response = client.post("/nlp/demo", json={"text": "x" * 10_001})
        assert response.status_code == 422

    def test_missing_text_field_returns_422(self, client):
        response = client.post("/nlp/demo", json={})
        assert response.status_code == 422

    def test_whitespace_only_text_returns_422(self, client):
        """Whitespace-only input should be rejected the same as empty."""
        response = client.post("/nlp/demo", json={"text": "   "})
        assert response.status_code == 422

    def test_maximum_valid_text_length(self, client):
        """Text at exactly the length limit should succeed."""
        response = client.post("/nlp/demo", json={"text": "a" * 10_000})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Full endpoint
# ---------------------------------------------------------------------------

class TestFullEndpoint:
    """POST /nlp/full — requires API key authentication."""

    def test_success_with_valid_auth(self, client, auth_headers, mock_model_manager):
        payload = {"text": "Technology news and updates"}
        response = client.post("/nlp/full", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["demo"] is False
        assert len(data["predictions"]) == 2

        # Verify the model was called with the correct input.
        mock_model_manager.predict_single.assert_called_once_with(
            payload["text"]
        )

    def test_prediction_schema_on_full_endpoint(self, client, auth_headers, mock_model_manager):
        response = client.post(
            "/nlp/full", json={"text": "Some text"}, headers=auth_headers
        )
        assert response.status_code == 200
        for prediction in response.json()["predictions"]:
            assert isinstance(prediction["label"], str)
            assert isinstance(prediction["prob"], float)
            assert 0.0 <= prediction["prob"] <= 1.0

    def test_missing_api_key_returns_401_or_403(self, client):
        """Full endpoint must reject requests with no auth header."""
        response = client.post("/nlp/full", json={"text": "Some text"})
        assert response.status_code in (401, 403)

    def test_invalid_api_key_returns_401_or_403(self, client):
        response = client.post(
            "/nlp/full",
            json={"text": "Some text"},
            headers={"X-API-Key": "invalid-key"},
        )
        assert response.status_code in (401, 403)

    def test_model_error_returns_500(self, client, auth_headers, mock_model_manager):
        """Unhandled model exceptions should surface as 500, not leak tracebacks."""
        mock_model_manager.predict_single.side_effect = RuntimeError("GPU OOM")

        response = client.post(
            "/nlp/full", json={"text": "Some text"}, headers=auth_headers
        )
        assert response.status_code == 500

    def test_model_returns_empty_list(self, client, auth_headers, mock_model_manager):
        """An empty prediction list is a valid (if unusual) model response."""
        mock_model_manager.predict_single.return_value = []

        response = client.post(
            "/nlp/full", json={"text": "Some text"}, headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["predictions"] == []


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """GET /nlp/health"""

    def test_returns_200(self, client):
        assert client.get("/nlp/health").status_code == 200

    def test_response_schema(self, client):
        data = client.get("/nlp/health").json()
        assert "status" in data
        assert "model_loaded" in data

    def test_status_is_healthy_when_model_loaded(self, client, mock_model_manager):
        mock_model_manager.is_loaded = True

        data = client.get("/nlp/health").json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True

    def test_status_reflects_unloaded_model(self, client, mock_model_manager):
        """Health check must report degraded/unhealthy when the model is absent."""
        mock_model_manager.is_loaded = False

        data = client.get("/nlp/health").json()
        assert data["status"] != "healthy"
        assert data["model_loaded"] is False
