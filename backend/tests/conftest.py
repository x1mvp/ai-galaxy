"""
tests/conftest.py  — single authoritative conftest for the entire suite.

Fixes applied (vs the submitted version)
─────────────────────────────────────────
C1  os.environ assignments were at the bottom of the file — app modules
    can be imported before TESTING/secrets are set. Moved to lines 1-10,
    before every other import.

C2  import os was missing entirely — os.environ raised NameError at
    module load, preventing pytest from collecting any tests.

H1  test_client was session-scoped here but function-scoped in the previous
    conftest — two definitions cause silent fixture shadowing. Consolidated
    into one file; session scope retained (app is stateless across tests).

H2  build_test_app() imported routers inside the function body, potentially
    before the model mock was applied. Now uses app.main.app directly —
    the TESTING guard in model_manager.load() handles CI safely.

H3  NLP router was replaced with a stub that only had GET /health, making
    POST /NLP/demo and POST /NLP/full return 404 in every test. Replaced
    with the real NLP router — mock handles the model, no .onnx needed.

M1  No autouse mock fixture — model mock from the previous conftest was
    silently dropped. Re-added as session-scoped autouse so every test
    in the suite is covered automatically.
"""

# =============================================================================
# FIX C1 + C2 — os.environ assignments FIRST, before every other import.
#
# Python executes module-level statements top-to-bottom at collection time.
# Any import below this block that touches app.* will trigger config.py and
# nlp.py — both of which check TESTING and secrets. If these lines come
# after the imports, the guards fire before the vars are set → crash.
# =============================================================================
import os  # FIX C2: was missing entirely → NameError on os.environ

# FIX C1: must be set before any `from app.*` import anywhere in this file
os.environ["TESTING"]           = "true"
os.environ["FULL_PASSWORD"]     = "test"
os.environ["ADMIN_KEY"]         = "test"
os.environ["POSTGRES_PASSWORD"] = "test"
os.environ["PGVECTOR_URL"]      = "postgresql://localhost:5432/test"
os.environ["REDIS_URL"]         = "redis://localhost:6379/0"
os.environ["ONNX_MODEL_PATH"]   = "/nonexistent/bert.onnx"

# =============================================================================
# Standard imports — safe now that env vars are in place
# =============================================================================
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport


# =============================================================================
# FIX M1 — Autouse model mock (was missing from the submitted file).
#
# session scope: one mock for the whole run — cheaper than function scope.
# autouse=True: every test gets this automatically with no decorator needed.
#
# Patches both locations where model_manager may be bound:
#   - app.nlp.model_manager          (the singleton in nlp.py)
#   - app.routers.nlp.model_manager  (the reference in the router module)
# =============================================================================
@pytest.fixture(scope="session", autouse=True)
def _patch_model_manager():
    """
    Replace model_manager with a deterministic MagicMock for the entire
    test session. Any test that needs to assert on specific predict() values
    can access this fixture by name and override .predict.return_value.
    """
    mock = MagicMock()
    mock.is_loaded = True
    mock.request_count = 0
    # FIX M1 from nlp.py audit: use "prob" key, not "score"
    mock.predict.return_value = [
        {"label": "Technology", "prob": 0.91},
        {"label": "Finance",    "prob": 0.72},
        {"label": "Healthcare", "prob": 0.55},
        {"label": "Legal",      "prob": 0.41},
        {"label": "Marketing",  "prob": 0.28},
    ]
    mock.get_stats.return_value = {
        "model_loaded": True,
        "uptime": 42.0,
        "request_count": 0,
        "cache_info": {"currsize": 0, "maxsize": 1000, "hits": 0, "misses": 0},
    }

    with patch("app.nlp.model_manager", mock), \
         patch("app.routers.nlp.model_manager", mock, create=True):
        yield mock


# =============================================================================
# FIX H1 + H2 + H3 — Single session-scoped TestClient using the real app.
#
# H1: was defined twice (session here, function in old conftest) → shadowing.
#     This is now the only definition.
# H2: build_test_app() imported routers inside the function body — timing
#     issue with mock application. Now uses app.main.app directly; the
#     TESTING guard in model_manager.load() makes it safe in CI.
# H3: NLP router was replaced by a stub with only GET /health — POST /NLP/demo
#     and POST /NLP/full returned 404 silently. Real router used instead;
#     mock.predict() returns the deterministic data above.
# =============================================================================
@pytest.fixture(scope="session")
def test_client(_patch_model_manager):
    """
    Session-scoped sync TestClient for the full application.

    Depends on _patch_model_manager so the mock is guaranteed to be active
    before the app is imported and the lifespan context runs.

    Usage:
        def test_health(test_client):
            r = test_client.get("/healthz")
            assert r.status_code == 200
    """
    from app.main import app  # imported here so env vars and mock are in place
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


# =============================================================================
# Async TestClient — for tests that use pytest-asyncio
# =============================================================================
@pytest_asyncio.fixture(scope="function")
async def async_client(_patch_model_manager):
    """
    Function-scoped async client for async route tests.

    Uses pytest_asyncio.fixture (not pytest.fixture) — required for
    async fixtures in pytest-asyncio >= 0.21.

    Usage:
        @pytest.mark.asyncio
        async def test_nlp(async_client):
            r = await async_client.post("/NLP/demo", json={"text": "hello"})
            assert r.status_code == 200
    """
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# =============================================================================
# Shared test-data fixtures
# =============================================================================
@pytest.fixture
def nlp_payload():
    return {"text": "The central bank raised interest rates by 25 basis points."}


@pytest.fixture
def crm_payload():
    return {"query": "enterprise SaaS prospects in fintech"}


@pytest.fixture
def clinical_payload():
    return {"systolic_bp": 145, "age": 62}


@pytest.fixture
def fraud_payload():
    return {}  # Fraud demo generates its own synthetic event


# =============================================================================
# Smoke-test helpers — assert basic contract on every endpoint
# =============================================================================
DEMO_ENDPOINTS = [
    ("POST", "/CRM/demo",      {"query": "test leads"}),
    ("POST", "/Fraud/demo",    {}),
    ("POST", "/Clinical/demo", {"systolic_bp": 130, "age": 55}),
    ("POST", "/NLP/demo",      {"text": "hello world"}),
]

HEALTH_ENDPOINTS = [
    ("GET", "/healthz",        None),
    ("GET", "/",               None),
    ("GET", "/NLP/health",     None),
]
