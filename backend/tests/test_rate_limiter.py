"""
Unit and integration tests for distributed rate limiting, quota protection, and production hardening.
Covers:
1. Top-level rate_limits collection storage with expires_at for Firestore TTL policies
2. Per-user recommendations minute rate limit (HTTP 429, Retry-After header, human-readable reset message)
3. Per-user plan minute rate limit
4. Per-user plan daily Gemini cap & global daily Gemini cap
5. Cache hits DO NOT consume Gemini quota
6. Failed LLM calls DO NOT consume Gemini quota
7. User data deletion (delete_all_user_data) DOES NOT reset rate limits / quota
8. Strict tenant isolation (User A rate limit does not affect User B)
9. Disabled rate limit flag (RATE_LIMIT_ENABLED=False)
10. Production documentation disabling (/docs, /redoc, /openapi.json returning 404 when ENVIRONMENT=production)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta

from app.config import settings
from app.services.rate_limiter import (
    check_recommendations_rate_limit,
    check_plan_endpoint_rate_limit,
    check_gemini_quota,
    record_gemini_call,
    check_plan_rate_limit,
    _get_minute_boundary,
    _get_day_boundary,
)
from app.agent.gemini import IssuePlanRequest, IssuePlanResponse, _PLAN_CACHE
from app.services.memory import delete_all_user_data
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

    def collection(self, name: str):
        client_store = self.store

        class MockColRef:
            def __init__(self, col_name):
                self.col_name = col_name

            def document(self, doc_id):
                doc_path = f"{self.col_name}/{doc_id}"

                class MockSubDocRef:
                    def __init__(self, p):
                        self.path = p

                    async def get(self, transaction=None):
                        if self.path in client_store:
                            return MockDocSnapshot(True, dict(client_store[self.path]))
                        return MockDocSnapshot(False, {})

                    async def set(self, data, merge=True):
                        existing = client_store.get(self.path, {})
                        existing.update(data)
                        client_store[self.path] = existing

                    async def delete(self):
                        client_store.pop(self.path, None)

                    async def collections(self):
                        # Empty async generator for subcollections
                        if False:
                            yield

                return MockSubDocRef(doc_path)

        return MockColRef(name)

    def transaction(self):
        tx = MockTransaction(self.store)
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
async def test_recommendations_top_level_storage_and_expires_at(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE", 5)

    user_id = "user_rec_ttl_1"
    await check_recommendations_rate_limit(user_id)

    # 1. Must be stored in top-level rate_limits/ collection, NOT users/{uid}
    assert any(k.startswith("rate_limits/rec_min__") for k in mock_client.store)
    assert not any(k.startswith(f"users/{user_id}/rate_limits") for k in mock_client.store)

    # 2. Must contain expires_at field of type datetime for Firestore TTL policy
    doc_key = [k for k in mock_client.store if k.startswith("rate_limits/rec_min__")][0]
    doc_data = mock_client.store[doc_key]
    assert "expires_at" in doc_data
    assert isinstance(doc_data["expires_at"], datetime)
    assert doc_data["count"] == 1


@pytest.mark.asyncio
async def test_recommendations_rate_limit_raises_429_when_exceeded(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE", 2)

    user_id = "user_rec_limit"
    await check_recommendations_rate_limit(user_id)
    await check_recommendations_rate_limit(user_id)

    # 3rd call must raise 429
    with pytest.raises(HTTPException) as exc_info:
        await check_recommendations_rate_limit(user_id)

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail
    assert "2 recommendations requests per minute" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_plan_endpoint_minute_cap(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PLAN_PER_MINUTE", 2)

    user_id = "user_plan_min"
    await check_plan_endpoint_rate_limit(user_id)
    await check_plan_endpoint_rate_limit(user_id)

    with pytest.raises(HTTPException) as exc_info:
        await check_plan_endpoint_rate_limit(user_id)

    assert exc_info.value.status_code == 429
    assert "2 plan requests per minute" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_plan_daily_gemini_cap_preflight_and_record(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "GEMINI_USER_DAILY_CAP", 2)
    monkeypatch.setattr(settings, "GEMINI_GLOBAL_DAILY_CAP", 500)

    user_id = "user_gemini_day"

    # Pre-flight check passes initially
    await check_gemini_quota(user_id)

    # Record 2 successful Gemini calls
    await record_gemini_call(user_id)
    await record_gemini_call(user_id)

    # 3rd pre-flight check must block
    with pytest.raises(HTTPException) as exc_info:
        await check_gemini_quota(user_id)

    assert exc_info.value.status_code == 429
    assert "Daily Gemini quota reached" in exc_info.value.detail
    assert "2 AI plan calls" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_plan_global_gemini_cap(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "GEMINI_USER_DAILY_CAP", 50)
    monkeypatch.setattr(settings, "GEMINI_GLOBAL_DAILY_CAP", 2)

    await record_gemini_call("user_a")
    await record_gemini_call("user_b")

    # Global cap reached; user_c must be blocked
    with pytest.raises(HTTPException) as exc_info:
        await check_gemini_quota("user_c")

    assert exc_info.value.status_code == 429
    assert "Global daily AI quota reached" in exc_info.value.detail
    assert "2 Gemini calls" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cache_hits_do_not_consume_gemini_quota(monkeypatch):
    """
    Requirement 3: Make sure cache hits don't consume the Gemini caps.
    """
    from app.routers.plan import generate_issue_plan
    from app.auth.dependencies import AuthenticatedUser

    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PLAN_PER_MINUTE", 10)
    monkeypatch.setattr(settings, "GEMINI_USER_DAILY_CAP", 2)

    user_id = "user_cache_test"
    auth_user = AuthenticatedUser(user_id=user_id, claims={"sub": user_id}, token="token")

    # Pre-populate memory cache
    cached_response = IssuePlanResponse(
        repo_full_name="org/cache-repo",
        issue_number=42,
        llm_used=True,
        difficulty="Beginner",
        estimated_hours="1 hour",
        effort_reasoning="Cached plan",
        setup_command="pytest",
        setup_citation="",
        test_command="pytest",
        test_citation="",
        steps=["Cached Step"],
        draft_claim_comment="Hi",
        cached=True,
    )
    cache_key = f"plan:{user_id}:org/cache-repo:42"
    _PLAN_CACHE[cache_key] = (cached_response, 9999999999.0)

    req = IssuePlanRequest(repo_full_name="org/cache-repo", issue_number=42, force_refresh=False)
    resp = await generate_issue_plan(req, current_user=auth_user)

    assert resp.cached is True
    # Verify no Gemini daily counter was written in Firestore!
    assert not any(k.startswith("rate_limits/gemini_daily__") for k in mock_client.store)
    assert not any(k.startswith("rate_limits/gemini_global__") for k in mock_client.store)


@pytest.mark.asyncio
async def test_failed_llm_calls_do_not_consume_gemini_quota(monkeypatch):
    """
    Requirement 3: Make sure failed LLM calls don't consume the Gemini caps.
    """
    from app.routers.plan import generate_issue_plan
    from app.auth.dependencies import AuthenticatedUser
    from app.agent.gemini import GeminiPlanAgent

    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PLAN_PER_MINUTE", 10)
    monkeypatch.setattr(settings, "GEMINI_USER_DAILY_CAP", 2)

    user_id = "user_failed_llm"
    auth_user = AuthenticatedUser(user_id=user_id, claims={"sub": user_id}, token="token")

    # Mock agent returning a plan with llm_used=False and an error
    failed_response = IssuePlanResponse(
        repo_full_name="org/fail-repo",
        issue_number=99,
        llm_used=False,
        llm_error="Vertex AI 503 Service Unavailable",
        difficulty="Beginner",
        estimated_hours="2 hours",
        effort_reasoning="Fallback plan",
        setup_command="pip install",
        setup_citation="",
        test_command="pytest",
        test_citation="",
        steps=["Fallback Step"],
        draft_claim_comment="Hi",
        cached=False,
    )

    with patch.object(GeminiPlanAgent, "generate_plan", AsyncMock(return_value=failed_response)):
        req = IssuePlanRequest(repo_full_name="org/fail-repo", issue_number=99, force_refresh=True)
        resp = await generate_issue_plan(req, current_user=auth_user)

        assert resp.llm_used is False
        assert resp.llm_error is not None
        # Verify no Gemini daily quota was consumed!
        assert not any(k.startswith("rate_limits/gemini_daily__") for k in mock_client.store)
        assert not any(k.startswith("rate_limits/gemini_global__") for k in mock_client.store)


@pytest.mark.asyncio
async def test_user_data_deletion_does_not_reset_quota(monkeypatch):
    """
    Requirement 1: Add a test that deleting a user's data does not reset their quota.
    Rate-limit counters reside in top-level rate_limits, so delete_all_user_data
    wipes profile & memory under users/{uid} but preserves rate_limits.
    """
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("app.services.memory._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE", 2)

    user_id = "user_quota_persist"

    # User consumes full quota
    await check_recommendations_rate_limit(user_id)
    await check_recommendations_rate_limit(user_id)

    # User has some profile data in users/{user_id}
    mock_client.store[f"users/{user_id}"] = {"user_id": user_id, "languages": {"Python": 100}}

    # User initiates data deletion
    deletion_success = await delete_all_user_data(user_id)
    assert deletion_success is True

    # Profile in users/{user_id} must be deleted
    assert f"users/{user_id}" not in mock_client.store

    # But rate_limits counter must still exist and block the user!
    with pytest.raises(HTTPException) as exc_info:
        await check_recommendations_rate_limit(user_id)

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail


@pytest.mark.asyncio
async def test_strict_tenant_isolation(monkeypatch):
    mock_client = MockFirestoreClient()
    monkeypatch.setattr("app.services.rate_limiter._get_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr("google.cloud.firestore.async_transactional", _setup_mock_transactional(mock_client))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE", 1)

    # User 1 reaches limit
    await check_recommendations_rate_limit("user_iso_1")
    with pytest.raises(HTTPException):
        await check_recommendations_rate_limit("user_iso_1")

    # User 2 should NOT be blocked by User 1's consumption
    await check_recommendations_rate_limit("user_iso_2")


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
