"""
Tests for /api/contributions, /api/funnel, and /api/outcomes/suggest.
Verifies PR classification, own-repo exclusion, via_mergewise matching, caching, and rate limit handling.
"""
import time
from unittest.mock import AsyncMock, patch, MagicMock
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.routers.contributions import (
    clear_user_contributions_cache,
    extract_referenced_issues_from_body,
    classify_pr_state,
)
from app.services.github import GitHubRateLimitError

client = TestClient(app)

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()
TEST_KID = "test_contrib_key_1"


def create_test_jwt(sub: str = "user_contrib_test_1", github_username: str = "testdev") -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": settings.CLERK_ISSUER,
        "azp": settings.CLERK_AUTHORIZED_PARTIES[0],
        "iat": now,
        "exp": now + 3600,
        "github_username": github_username,
    }
    return jwt.encode(payload, _private_key, algorithm="RS256", headers={"kid": TEST_KID})


@pytest.fixture(autouse=True)
def mock_jwks_and_auth():
    with patch("app.auth.clerk.fetch_jwks", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {TEST_KID: _public_key}
        with patch("app.auth.dependencies.AuthenticatedUser.get_github_token", new_callable=AsyncMock) as mock_tok:
            mock_tok.return_value = "gho_test_token_contribs"
            yield mock_tok


def test_regex_extract_referenced_issues():
    assert extract_referenced_issues_from_body("Fixes #123 and closes #456") == [123, 456]
    assert extract_referenced_issues_from_body("This PR will resolve #789.") == [789]
    assert extract_referenced_issues_from_body("Fixed owner/repo#42 and closed #10") == [42, 10]
    assert extract_referenced_issues_from_body("Just some general text without any issue tag") == []
    assert extract_referenced_issues_from_body(None) == []


def test_classify_pr_state():
    merged_item = {
        "state": "closed",
        "pull_request": {"merged_at": "2026-05-12T10:00:00Z"},
    }
    assert classify_pr_state(merged_item) == "merged"

    open_item = {
        "state": "open",
        "pull_request": {"merged_at": None},
    }
    assert classify_pr_state(open_item) == "open"

    closed_item = {
        "state": "closed",
        "pull_request": {"merged_at": None},
    }
    assert classify_pr_state(closed_item) == "closed"


@pytest.mark.asyncio
async def test_contributions_classification_and_own_repo_exclusion():
    user_id = "user_contrib_cls"
    clear_user_contributions_cache(user_id)
    token = create_test_jwt(sub=user_id, github_username="johndoe")

    mock_search_items = [
        # Merged external PR
        {
            "repository_url": "https://api.github.com/repos/pallets/flask",
            "html_url": "https://github.com/pallets/flask/pull/101",
            "number": 101,
            "title": "Fix routing bug",
            "state": "closed",
            "pull_request": {"merged_at": "2026-04-01T12:00:00Z"},
            "created_at": "2026-03-28T09:00:00Z",
            "body": "Fixes #50 in flask core",
        },
        # Open external PR
        {
            "repository_url": "https://api.github.com/repos/encode/starlette",
            "html_url": "https://github.com/encode/starlette/pull/202",
            "number": 202,
            "title": "Add async middleware test",
            "state": "open",
            "pull_request": {"merged_at": None},
            "created_at": "2026-04-10T14:00:00Z",
            "body": "Closes #180",
        },
        # Closed unmerged external PR
        {
            "repository_url": "https://api.github.com/repos/fastapi/fastapi",
            "html_url": "https://github.com/fastapi/fastapi/pull/303",
            "number": 303,
            "title": "Docs improvement",
            "state": "closed",
            "pull_request": {"merged_at": None},
            "created_at": "2026-02-15T08:00:00Z",
            "body": "Just docs",
        },
        # Own-repo PR (must be excluded even if returned by search)
        {
            "repository_url": "https://api.github.com/repos/johndoe/my-private-tool",
            "html_url": "https://github.com/johndoe/my-private-tool/pull/5",
            "number": 5,
            "title": "Self PR",
            "state": "open",
            "pull_request": {"merged_at": None},
            "created_at": "2026-04-12T10:00:00Z",
            "body": "Self fix",
        },
    ]

    mock_outcomes = [
        # User recorded outcome for pallets/flask #50
        {"repo": "pallets/flask", "issue_number": 50, "outcome": "merged"},
    ]

    async def mock_gh_get(self, url, params=None, **kwargs):
        if "/user" in url and "repos" not in url:
            return {"login": "johndoe", "avatar_url": "https://avatars.github.com/u/999"}
        if "/search/issues" in url:
            return {"items": mock_search_items, "total_count": len(mock_search_items)}
        if "/repos/pallets/flask" in url:
            return {"stargazers_count": 65000, "owner": {"avatar_url": "https://github.com/pallets.png"}}
        if "/repos/encode/starlette" in url:
            return {"stargazers_count": 10500, "owner": {"avatar_url": "https://github.com/encode.png"}}
        if "/repos/fastapi/fastapi" in url:
            return {"stargazers_count": 75000, "owner": {"avatar_url": "https://github.com/fastapi.png"}}
        return {}

    with patch("app.services.github.GitHubClient.get", side_effect=mock_gh_get, autospec=True):
        with patch("app.routers.contributions.get_user_outcomes", new_callable=AsyncMock) as mock_get_outcomes:
            mock_get_outcomes.return_value = mock_outcomes

            response = client.get("/api/contributions", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
            data = response.json()

            summary = data["summary"]
            assert summary["merged_count"] == 1
            assert summary["open_count"] == 1
            assert summary["closed_count"] == 1
            assert summary["repo_count"] == 3

            items = data["items"]
            assert len(items) == 3

            # Check own repo was excluded
            repos = [it["repo"] for it in items]
            assert "johndoe/my-private-tool" not in repos

            # Check via_mergewise flag
            flask_pr = next(it for it in items if it["repo"] == "pallets/flask")
            assert flask_pr["via_mergewise"] is True
            assert flask_pr["state"] == "merged"
            assert flask_pr["stars"] == 65000

            starlette_pr = next(it for it in items if it["repo"] == "encode/starlette")
            assert starlette_pr["via_mergewise"] is False
            assert starlette_pr["state"] == "open"
            assert starlette_pr["stars"] == 10500


@pytest.mark.asyncio
async def test_contributions_caching():
    user_id = "user_contrib_cache"
    clear_user_contributions_cache(user_id)
    token = create_test_jwt(sub=user_id, github_username="alice")

    call_count = {"search": 0}

    async def mock_gh_get(self, url, params=None, **kwargs):
        if "/user" in url and "repos" not in url:
            return {"login": "alice"}
        if "/search/issues" in url:
            call_count["search"] += 1
            return {
                "items": [
                    {
                        "repository_url": "https://api.github.com/repos/psf/requests",
                        "html_url": "https://github.com/psf/requests/pull/1",
                        "number": 1,
                        "title": "Requests PR",
                        "state": "closed",
                        "pull_request": {"merged_at": "2026-01-01T00:00:00Z"},
                    }
                ]
            }
        return {"stargazers_count": 50000}

    with patch("app.services.github.GitHubClient.get", side_effect=mock_gh_get, autospec=True):
        with patch("app.routers.contributions.get_user_outcomes", new_callable=AsyncMock) as mock_get_outcomes:
            mock_get_outcomes.return_value = []

            # First call populates cache
            r1 = client.get("/api/contributions", headers={"Authorization": f"Bearer {token}"})
            assert r1.status_code == 200
            assert call_count["search"] == 1

            # Second call must hit memory cache (no additional search API call)
            r2 = client.get("/api/contributions", headers={"Authorization": f"Bearer {token}"})
            assert r2.status_code == 200
            assert call_count["search"] == 1
            assert r2.json()["items"][0]["repo"] == "psf/requests"


@pytest.mark.asyncio
async def test_contributions_rate_limit_graceful_notice():
    user_id = "user_contrib_rl"
    clear_user_contributions_cache(user_id)
    token = create_test_jwt(sub=user_id, github_username="bob")

    async def mock_gh_get(self, url, params=None, **kwargs):
        if "/user" in url and "repos" not in url:
            return {"login": "bob"}
        if "/search/issues" in url:
            raise GitHubRateLimitError(resource="search", reset_epoch=int(time.time() + 120), remaining=0)
        return {}

    with patch("app.services.github.GitHubClient.get", side_effect=mock_gh_get, autospec=True):
        with patch("app.routers.contributions.get_user_outcomes", new_callable=AsyncMock) as mock_get_outcomes:
            mock_get_outcomes.return_value = []

            resp = client.get("/api/contributions", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["rate_limit_notice"] is not None
            assert "rate limit reached" in data["rate_limit_notice"].lower()
            assert data["summary"]["merged_count"] == 0
            assert data["items"] == []


@pytest.mark.asyncio
async def test_funnel_counts():
    user_id = "user_funnel_test"
    token = create_test_jwt(sub=user_id)

    # Mock Firestore recommendations and outcomes
    mock_outcomes = [
        {"repo": "foo/bar", "issue_number": 1, "outcome": "viewed_plan"},
        {"repo": "foo/bar", "issue_number": 2, "outcome": "attempted"},
        {"repo": "baz/qux", "issue_number": 3, "outcome": "pr_opened"},
        {"repo": "alpha/beta", "issue_number": 4, "outcome": "merged"},
    ]

    mock_recs_docs = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]  # 5 shown

    mock_client = MagicMock()
    mock_recs_col = MagicMock()
    mock_recs_col.get = AsyncMock(return_value=mock_recs_docs)

    mock_user_doc = MagicMock()
    mock_user_doc.collection.return_value = mock_recs_col
    mock_client.collection.return_value.document.return_value = mock_user_doc

    with patch("app.routers.contributions._get_client", new_callable=AsyncMock) as mock_gc:
        mock_gc.return_value = mock_client
        with patch("app.routers.contributions.get_user_outcomes", new_callable=AsyncMock) as mock_out:
            mock_out.return_value = mock_outcomes

            resp = client.get("/api/funnel", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
            funnel = resp.json()
            assert funnel["shown"] == 5
            assert funnel["plan_viewed"] == 1
            assert funnel["attempted"] == 1
            assert funnel["pr_opened"] == 1
            assert funnel["merged"] == 1


@pytest.mark.asyncio
async def test_outcomes_suggest():
    user_id = "user_suggest_test"
    token = create_test_jwt(sub=user_id, github_username="suggester")

    mock_search_items = [
        {
            "repository_url": "https://api.github.com/repos/django/django",
            "html_url": "https://github.com/django/django/pull/999",
            "number": 999,
            "title": "Fix admin timezone issue",
            "state": "closed",
            "pull_request": {"merged_at": "2026-04-01T00:00:00Z"},
            "body": "Fixes #14522. Tests added.",
        }
    ]

    async def mock_gh_get(self, url, params=None, **kwargs):
        if "/user" in url:
            return {"login": "suggester"}
        if "/search/issues" in url:
            return {"items": mock_search_items}
        return {}

    with patch("app.services.github.GitHubClient.get", side_effect=mock_gh_get, autospec=True):
        with patch("app.routers.contributions.get_user_outcomes", new_callable=AsyncMock) as mock_out:
            # User has not recorded 14522
            mock_out.return_value = []

            resp = client.post("/api/outcomes/suggest", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
            suggestions = resp.json()
            assert len(suggestions) == 1
            assert suggestions[0]["repo"] == "django/django"
            assert suggestions[0]["issue_number"] == 14522
            assert suggestions[0]["pr_number"] == 999
            assert suggestions[0]["suggested_outcome"] == "merged"
