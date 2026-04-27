<<<<<<< HEAD
﻿"""tests/conftest.py — minimal fixtures using real routers."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def build_test_app() -> FastAPI:
    app = FastAPI(title="Test App", version="3.0.0")

    from app.routers import crm, fraud, clinical
    app.include_router(crm.router, prefix="/CRM")
    app.include_router(fraud.router, prefix="/Fraud")
    app.include_router(clinical.router, prefix="/Clinical")

    # Stub NLP health without loading transformers
    from fastapi import APIRouter
    nlp_stub = APIRouter()

    @nlp_stub.get("/health")
    async def nlp_health():
        return {"service": "NLP Classification", "status": "healthy",
                "model_loaded": True}

    app.include_router(nlp_stub, prefix="/NLP")

    @app.get("/")
    async def root():
        return {"message": "Test API", "version": "3.0.0",
                "endpoints": ["/CRM", "/Fraud", "/Clinical", "/NLP"]}

    @app.get("/healthz")
    async def healthz():
        return {"status": "healthy", "version": "3.0.0",
                "services": ["crm", "fraud", "clinical", "nlp"]}

    return app


@pytest.fixture(scope="session")
def test_client():
    app = build_test_app()
    with TestClient(app) as client:
        yield client
=======
"""
tests/conftest.py

Shared pytest fixtures for the entire test suite.
"""

from __future__ import annotations

import os

# Set environment variables BEFORE any app code is imported
os.environ["TESTING"] = "true"
os.environ["ONNX_MODEL_PATH"] = "/nonexistent/bert.onnx"

import pytest
from unittest.mock import MagicMock, patch

# Remove or comment out this line if it's causing issues
# pytest_plugins = ["asyncio"]

@pytest.fixture(autouse=True)
def mock_model_manager():
    """Replace model_manager with a MagicMock for every test automatically."""
    mock = MagicMock()
    mock.is_loaded = True
    mock.predict.return_value = [
        {"label": "Technology", "score": 0.91},
        {"label": "Finance", "score": 0.72},
        {"label": "Healthcare", "score": 0.55},
        {"label": "Legal", "score": 0.41},
        {"label": "Marketing", "score": 0.28},
    ]

    with patch("app.nlp.model_manager", mock), \
         patch("app.routers.nlp.model_manager", mock, create=True):
        yield mock

@pytest.fixture
def test_client(mock_model_manager):
    """Provides a FastAPI TestClient with the full app."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

@pytest.fixture
async def async_client(mock_model_manager):
    """Async version of test_client for tests that use pytest-asyncio."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

@pytest.fixture
def sample_nlp_payload():
    return {"text": "The central bank raised interest rates by 25 basis points."}

@pytest.fixture
def sample_crm_payload():
    return {
        "company_size": "Large",
        "industry": "Technology",
        "contact_role": "Decision Maker",
        "budget_range": "High",
        "timeline": "Immediate",
        "engagement_score": 80
    }

@pytest.fixture
def sample_clinical_payload():
    return {
        "age": 45,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "heart_rate": 72,
        "glucose": 95,
        "cholesterol": 190,
        "bmi": 24.5,
        "smoking_status": "Never",
        "exercise_frequency": "Moderate"
    }
>>>>>>> eced1bb985ecd4aa5dd6dd7b1e59addd4a4b9e4b
