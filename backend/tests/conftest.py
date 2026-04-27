"""tests/conftest.py — minimal fixtures using real routers."""

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
