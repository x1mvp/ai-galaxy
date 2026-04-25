"""Integration tests for NLP Classification Service.

These tests exercise the full request/response cycle against the real
application without mocking internals.  They do NOT require a live database
or GPU — they verify that the service starts correctly, routes are reachable,
and error handling works end-to-end.

Tests that need a real PostgreSQL instance are marked ``@pytest.mark.db``
and skipped by default in CI until a test database is configured.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Single TestClient for the whole module — integration tests share state."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers():
    return {"X-API-Key": "test-api-key"}


# ---------------------------------------------------------------------------
# Service startup
# ---------------------------------------------------------------------------

class TestServiceStartup:
    """Verify the app initialises cleanly and basic infrastructure is in place."""

    def test_health_endpoint_reachable(self, client):
        """Service must respond to health probes immediately after startup."""
        response = client.get("/nlp/health")
        assert response.status_code == 200

    def test_health_reports_model_loaded_after_lifespan(self, client):
        """The lifespan handler loads the model; health must reflect that."""
        data = client.get("/nlp/health").json()
        assert data["model_loaded"] is True
        assert data["status"] == "healthy"

    def test_openapi_schema_available(self, client):
        """FastAPI must serve its OpenAPI JSON (used by docs + client gen)."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema
        assert "/nlp/demo" in schema["paths"]
        assert "/nlp/full" in schema["paths"]
        assert "/nlp/health" in schema["paths"]

    def test_content_type_is_json(self, client):
        """All endpoints must return application/json, not HTML error pages."""
        response = client.get("/nlp/health")
        assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Demo endpoint — full stack, no mocks
# ---------------------------------------------------------------------------

class TestDemoEndpointIntegration:
    """End-to-end demo endpoint tests using the real stub model."""

    def test_returns_predictions_with_real_model(self, client):
        response = client.post("/nlp/demo", json={"text": "Cloud computing trends"})
        assert response.status_code == 200
        data = response.json()
        assert data["demo"] is True
        assert len(data["predictions"]) > 0

    def test_predictions_sum_to_approximately_one(self, client):
        """Stub model probabilities must be a valid distribution."""
        response = client.post("/nlp/demo", json={"text": "Machine learning advances"})
        probs = [p["prob"] for p in response.json()["predictions"]]
        assert abs(sum(probs) - 1.0) < 0.01

    def test_predictions_sorted_by_confidence(self, client):
        """Results should come back highest confidence first."""
        response = client.post("/nlp/demo", json={"text": "Sports highlights today"})
        probs = [p["prob"] for p in response.json()["predictions"]]
        assert probs == sorted(probs, reverse=True)

    def test_different_texts_produce_different_top_labels(self, client):
        """The stub model should not return identical results for all inputs."""
        r1 = client.post("/nlp/demo", json={"text": "a"})
        r2 = client.post("/nlp/demo", json={"text": "aa"})
        labels1 = [p["label"] for p in r1.json()["predictions"]]
        labels2 = [p["label"] for p in r2.json()["predictions"]]
        # At least the ordering should differ between distinct inputs.
        assert labels1 != labels2

    def test_unicode_text_handled_correctly(self, client):
        response = client.post("/nlp/demo", json={"text": "Bonjour le monde 🌍"})
        assert response.status_code == 200

    def test_special_characters_in_text(self, client):
        response = client.post(
            "/nlp/demo", json={"text": "SELECT * FROM users; DROP TABLE leads;"}
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Full endpoint — auth + real model
# ---------------------------------------------------------------------------

class TestFullEndpointIntegration:
    """End-to-end full endpoint tests — auth enforced, real model runs."""

    def test_authenticated_request_succeeds(self, client, auth_headers):
        response = client.post(
            "/nlp/full",
            json={"text": "Data engineering pipeline optimisation"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["demo"] is False
        assert isinstance(data["predictions"], list)

    def test_unauthenticated_request_blocked(self, client):
        response = client.post("/nlp/full", json={"text": "Some text"})
        assert response.status_code in (401, 403)

    def test_wrong_key_blocked(self, client):
        response = client.post(
            "/nlp/full",
            json={"text": "Some text"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code in (401, 403)

    def test_full_endpoint_demo_flag_is_false(self, client, auth_headers):
        response = client.post(
            "/nlp/full", json={"text": "Some text"}, headers=auth_headers
        )
        assert response.json()["demo"] is False

    def test_response_time_is_reasonable(self, client, auth_headers):
        """Stub model must respond well under 1 s (no GPU needed)."""
        import time
        start = time.perf_counter()
        client.post("/nlp/full", json={"text": "Performance check"}, headers=auth_headers)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s — stub model should be instant"


# ---------------------------------------------------------------------------
# Input validation — shared across both endpoints
# ---------------------------------------------------------------------------

class TestInputValidationIntegration:
    """Pydantic validation must fire before any model code runs."""

    @pytest.mark.parametrize("text,expected_status", [
        ("",        422),   # empty
        ("   ",     422),   # whitespace only
        ("x" * 10_001, 422),  # over limit
        ("x" * 10_000, 200),  # exactly at limit
        ("hello",   200),   # normal
    ])
    def test_demo_validation(self, client, text, expected_status):
        response = client.post("/nlp/demo", json={"text": text})
        assert response.status_code == expected_status

    def test_422_body_contains_detail(self, client):
        """Validation errors must include a human-readable detail field."""
        response = client.post("/nlp/demo", json={"text": ""})
        assert "detail" in response.json()

    def test_missing_body_returns_422(self, client):
        response = client.post("/nlp/demo")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Database-dependent tests (skipped until DB is configured in CI)
# ---------------------------------------------------------------------------

@pytest.mark.db
class TestDatabaseIntegration:
    """
    Tests that require a live PostgreSQL + pgvector instance.

    Skip these in CI by default:
        pytest tests/integration/ -m "not db"

    Enable them once TEST_DATABASE_URL is set in the environment:
        TEST_DATABASE_URL=postgresql+asyncpg://... pytest tests/integration/ -m db
    """

    def test_placeholder_db_connection(self):
        """Replace with real asyncpg connection test once DB is wired up."""
        pytest.skip("Database not configured — set TEST_DATABASE_URL to enable")

    def test_placeholder_vector_search(self):
        """Replace with pgvector similarity search round-trip test."""
        pytest.skip("Database not configured — set TEST_DATABASE_URL to enable")
