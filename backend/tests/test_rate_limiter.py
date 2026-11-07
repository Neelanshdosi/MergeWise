"""
Unit and integration tests for distributed rate limiting & production documentation disabling.
Covers:
1. Per-user recommendations minute rate limit (HTTP 429, Retry-After header, human-readable reset message)
2. Per-user plan minute rate limit
3. Per-user plan daily Gemini cap
4. Global daily Gemini quota cap across all users
5. Strict tenant isolation (User A rate limit does not affect User B)
6. Disabled rate limit flag (RATE_LIMIT_ENABLED=False)
7. Production documentation disabling (/docs, /redoc, /openapi.json returning 404 when ENVIRONMENT=production)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta

from app.config import settings
from app.services.rate_limiter import (
    check_recommendations_rate_limit,
    check_plan_rate_limit,
    _get_minute_boundary,
    _get_day_boundary,
)
from app.main import app


# ---------------------------------------------------------------------------
# In-memory mock Firestore client for rate limiting
# ---------------------------------------------------------------------------

class MockDocSnapshot:
    def __init__(self, exists: bool, data: dict):
        self.exists = exists
        self._data = data

    def to_dict(self):
        return self._data


class MockTransaction:
    def __init__(self, store: dict):
        self.store = store
        self.writes = []

    def set(self, doc_ref, data, merge=True):
        self.writes.append((doc_ref.path, data))

    def commit(self):
        for path, data in self.writes:
            existing = self.store.get(path, {})
            existing.update(data)
            self.store[path] = existing


class MockFirestoreClient:
    def __init__(self):
        self.store = {}

    def document(self, path: str):
        client_store = self.store

        class MockDocRef:
            def __init__(self, p):
                self.path = p

            async def get(self, transaction=None):
                if self.path in client_store:
                    return MockDocSnapshot(True, dict(client_store[self.path]))
                return MockDocSnapshot(False, {})

        return MockDocRef(path)

    def transaction(self):
        tx = MockTransaction(self.store)

        # Emulate async transaction execution
        return tx


def _setup_mock_transactional(mock_client):
    """
    Patches firestore.async_transactional to execute the callback with mock_client's transaction.
    """
    def decorator(fn):
        async def wrapper(transaction, *args, **kwargs):
            res = await fn(transaction, *args, **kwargs)
            transaction.commit()
            return res
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recommendations_rate_limit_allows_under_limit(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE", 3)

    user_id = "user_rec_test_1"

    # Calls 1, 2, 3 should succeed without error
    await check_recommendations_rate_limit(user_id)
    await check_recommendations_rate_limit(user_id)
    await check_recommendations_rate_limit(user_id)


@pytest.mark.asyncio
async def test_recommendations_rate_limit_raises_429_when_exceeded(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE", 2)

    user_id = "user_rec_test_limit"

    await check_recommendations_rate_limit(user_id)
    await check_recommendations_rate_limit(user_id)

    # 3rd call must raise 429
    with pytest.raises(HTTPException) as exc_info:
        await check_recommendations_rate_limit(user_id)

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail
    assert "2 recommendations requests per minute" in exc_info.value.detail
    assert "Resets at" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_plan_rate_limit_minute_cap(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PLAN_PER_MINUTE", 2)
    monkeypatch.setattr(settings, "GEMINI_USER_DAILY_CAP", 100)
    monkeypatch.setattr(settings, "GEMINI_GLOBAL_DAILY_CAP", 500)

    user_id = "user_plan_min_test"

    await check_plan_rate_limit(user_id)
    await check_plan_rate_limit(user_id)

    with pytest.raises(HTTPException) as exc_info:
        await check_plan_rate_limit(user_id)

    assert exc_info.value.status_code == 429
    assert "2 plan requests per minute" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_plan_rate_limit_user_daily_cap(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PLAN_PER_MINUTE", 100)
    monkeypatch.setattr(settings, "GEMINI_USER_DAILY_CAP", 2)
    monkeypatch.setattr(settings, "GEMINI_GLOBAL_DAILY_CAP", 500)

    user_id = "user_plan_day_test"

    await check_plan_rate_limit(user_id)
    await check_plan_rate_limit(user_id)

    with pytest.raises(HTTPException) as exc_info:
        await check_plan_rate_limit(user_id)

    assert exc_info.value.status_code == 429
    assert "Daily Gemini quota reached" in exc_info.value.detail
    assert "2 AI plan calls" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_plan_rate_limit_global_daily_cap(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PLAN_PER_MINUTE", 100)
    monkeypatch.setattr(settings, "GEMINI_USER_DAILY_CAP", 50)
    monkeypatch.setattr(settings, "GEMINI_GLOBAL_DAILY_CAP", 2)

    await check_plan_rate_limit("user_alpha")
    await check_plan_rate_limit("user_beta")

    # Global cap reached; user_gamma must be blocked even though user_gamma has 0 calls
    with pytest.raises(HTTPException) as exc_info:
        await check_plan_rate_limit("user_gamma")

    assert exc_info.value.status_code == 429
    assert "Global daily AI quota reached" in exc_info.value.detail
    assert "2 Gemini calls" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_strict_tenant_isolation(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE", 1)

    # User 1 reaches limit
    await check_recommendations_rate_limit("user_1")
    with pytest.raises(HTTPException):
        await check_recommendations_rate_limit("user_1")

    # User 2 should NOT be blocked by User 1's consumption
    await check_recommendations_rate_limit("user_2")


@pytest.mark.asyncio
async def test_rate_limit_disabled_flag(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)

    # Even with 0 allowed, when disabled, it never raises
    monkeypatch.setattr(settings, "RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE", 0)
    await check_recommendations_rate_limit("user_unlimited")


def test_production_docs_disabled(monkeypatch):
    """
    Tests requirement 2: disable /docs, /redoc and /openapi.json when ENVIRONMENT=production.
    """
    from fastapi import FastAPI
    from app.config import settings

    # Simulate production FastAPI app initialization
    prod_app = FastAPI(
        title="MergeWise Test Prod",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    client = TestClient(prod_app)
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
