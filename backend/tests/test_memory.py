"""
Phase 4: Firestore Memory Service Tests
Full suite including:
- Outcome recording, profile persistence, and Firestore error handling
- Document ID safety without slashes
- Recommendations telemetry logging for Phase 5 evaluation
- Dynamic skill weights: bounded steps (+/-0.05 max), time decay (60-day half-life), total clamp [-0.3, +0.3]
- "Why these results" note generation from real outcome history
- 200 outcome read cap
- User data deletion (clearing root doc, recursive subcollections, and in-memory caches)
- Post-deletion blank slate recommendation test
- Base score isolation for offline evaluation
- Strict tenant isolation: user A cannot access or mutate user B's data
- Real Firestore emulator read/write verification
"""
import asyncio
import math
import os
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.memory import (
    record_outcome,
    get_user_outcomes,
    get_outcome_for_issue,
    delete_outcome,
    save_user_profile,
    load_user_profile,
    log_shown_recommendations,
    derive_skill_weights_and_excluded_issues,
    calculate_time_decay,
    delete_all_user_data,
    make_outcome_doc_id,
    VALID_OUTCOMES,
    OutcomeType,
    POSITIVE_OUTCOMES,
    NEGATIVE_OUTCOMES,
)
from mergewise_features.schemas import (
    UserSkillProfile,
    IssueMetadata,
    CandidateFeatureVector,
    ScoredIssueCandidate,
)
from mergewise_features.extractor import score_candidate_issue, compute_feature_vector
from app.ranker.heuristic import rank_viable_issues
from app.routers.recommendations import (
    _LAST_GOOD_PROFILE_STORE,
    _LAST_GOOD_RECOMMENDATIONS_STORE,
    _LAST_GOOD_STATS_STORE,
    clear_user_recommendations_cache,
)
from app.agent.gemini import _PLAN_CACHE, clear_user_plan_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client():
    """Returns a mock AsyncFirestoreClient with plumbed collection/document/subcollection chain."""
    client = MagicMock()

    def _make_col(col_name):
        col = MagicMock()
        def _make_doc(doc_id):
            doc = MagicMock()
            doc.set = AsyncMock(return_value=None)
            doc.get = AsyncMock()
            doc.delete = AsyncMock(return_value=None)

            async def _empty_collections():
                if False:
                    yield None
            doc.collections = MagicMock(return_value=_empty_collections())

            def _make_sub_col(sub_name):
                sub = MagicMock()
                sub_doc = MagicMock()
                sub_doc.set = AsyncMock(return_value=None)
                sub_doc.get = AsyncMock()
                sub_doc.delete = AsyncMock(return_value=None)
                sub.document = MagicMock(return_value=sub_doc)
                sub.order_by = MagicMock(return_value=sub)
                sub.where = MagicMock(return_value=sub)
                sub.limit = MagicMock(return_value=sub)
                sub.get = AsyncMock(return_value=[])

                async def _empty_list_docs():
                    if False:
                        yield None
                sub.list_documents = MagicMock(return_value=_empty_list_docs())
                return sub

            doc.collection = MagicMock(side_effect=_make_sub_col)
            return doc
        col.document = MagicMock(side_effect=_make_doc)
        return col

    client.collection = MagicMock(side_effect=_make_col)
    return client


# ---------------------------------------------------------------------------
# 1. Outcome constants and validation
# ---------------------------------------------------------------------------

def test_valid_outcomes_set():
    assert "attempted" in VALID_OUTCOMES
    assert "pr_opened" in VALID_OUTCOMES
    assert "merged" in VALID_OUTCOMES
    assert "skipped" in VALID_OUTCOMES
    assert "too_hard" in VALID_OUTCOMES
    assert "abandoned" in VALID_OUTCOMES
    assert "viewed_plan" in VALID_OUTCOMES


def test_positive_and_negative_partition():
    assert POSITIVE_OUTCOMES == {"attempted", "pr_opened", "merged"}
    assert NEGATIVE_OUTCOMES == {"skipped", "too_hard", "abandoned"}
    assert POSITIVE_OUTCOMES.isdisjoint(NEGATIVE_OUTCOMES)
    assert OutcomeType.VIEWED_PLAN in VALID_OUTCOMES


def test_make_outcome_doc_id_has_no_slashes():
    doc_id = make_outcome_doc_id("facebook/react", 1234)
    assert "/" not in doc_id
    assert doc_id == "facebook__react__1234"

    doc_id_clean = make_outcome_doc_id("org//sub-repo", 99)
    assert "/" not in doc_id_clean
    assert doc_id_clean == "org____sub-repo__99"


# ---------------------------------------------------------------------------
# 2. record_outcome
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_outcome_success():
    mock_client = _make_mock_client()
    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await record_outcome(
            user_id="user_abc",
            repo_full_name="org/repo",
            issue_number=42,
            issue_title="Fix the bug",
            outcome=OutcomeType.ATTEMPTED,
            primary_language="Python",
        )
    assert result is True


@pytest.mark.asyncio
async def test_record_outcome_invalid_outcome_returns_false():
    mock_client = _make_mock_client()
    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await record_outcome(
            user_id="user_abc",
            repo_full_name="org/repo",
            issue_number=42,
            issue_title="Fix the bug",
            outcome="nonexistent_outcome",
        )
    assert result is False
    mock_client.collection.assert_not_called()


@pytest.mark.asyncio
async def test_record_outcome_empty_user_id_returns_false():
    mock_client = _make_mock_client()
    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await record_outcome(
            user_id="",
            repo_full_name="org/repo",
            issue_number=1,
            issue_title="Test",
            outcome=OutcomeType.SKIPPED,
        )
    assert result is False


@pytest.mark.asyncio
async def test_record_outcome_firestore_error_returns_false():
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    mock_sub = MagicMock()
    mock_sub_doc = MagicMock()
    mock_sub_doc.set = AsyncMock(side_effect=Exception("Firestore unavailable"))
    mock_sub.document = MagicMock(return_value=mock_sub_doc)
    mock_doc.collection = MagicMock(return_value=mock_sub)
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await record_outcome(
            user_id="user_x",
            repo_full_name="org/repo",
            issue_number=99,
            issue_title="Broken",
            outcome=OutcomeType.PR_OPENED,
        )
    assert result is False


@pytest.mark.asyncio
async def test_record_outcome_doc_id_encoding():
    captured_doc_ids = []
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()

    def capture_sub(sub_name):
        sub = MagicMock()
        def capture_id(doc_id):
            captured_doc_ids.append(doc_id)
            sd = MagicMock()
            sd.set = AsyncMock(return_value=None)
            return sd
        sub.document = MagicMock(side_effect=capture_id)
        return sub

    mock_doc.collection = MagicMock(side_effect=capture_sub)
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        await record_outcome(
            user_id="u1",
            repo_full_name="facebook/react",
            issue_number=100,
            issue_title="Test",
            outcome=OutcomeType.MERGED,
        )

    assert len(captured_doc_ids) == 1
    doc_id = captured_doc_ids[0]
    assert "/" not in doc_id
    assert "facebook__react" in doc_id
    assert "__100" in doc_id


# ---------------------------------------------------------------------------
# 3. get_user_outcomes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_outcomes_returns_list():
    mock_doc1 = MagicMock()
    mock_doc1.exists = True
    mock_doc1.to_dict = MagicMock(return_value={
        "user_id": "u1", "repo_full_name": "org/repo", "issue_number": 1,
        "issue_title": "Fix bug", "outcome": "merged", "is_positive": True,
        "recorded_at": "2026-11-01T00:00:00Z",
    })
    mock_sub = MagicMock()
    mock_sub.order_by = MagicMock(return_value=mock_sub)
    mock_sub.limit = MagicMock(return_value=mock_sub)
    mock_sub.get = AsyncMock(return_value=[mock_doc1])

    mock_doc = MagicMock()
    mock_doc.collection = MagicMock(return_value=mock_sub)
    mock_col = MagicMock()
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client = MagicMock()
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        results = await get_user_outcomes("u1")

    assert len(results) == 1
    assert results[0]["outcome"] == "merged"


@pytest.mark.asyncio
async def test_get_user_outcomes_empty_user_id():
    result = await get_user_outcomes("")
    assert result == []


@pytest.mark.asyncio
async def test_get_user_outcomes_error_returns_empty():
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    mock_sub = MagicMock()
    mock_sub.order_by = MagicMock(return_value=mock_sub)
    mock_sub.limit = MagicMock(return_value=mock_sub)
    mock_sub.get = AsyncMock(side_effect=Exception("Firestore read timeout"))
    mock_doc.collection = MagicMock(return_value=mock_sub)
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        results = await get_user_outcomes("u1")
    assert results == []


@pytest.mark.asyncio
async def test_get_user_outcomes_capped_at_200():
    """Confirms get_user_outcomes caps query limit and results at 200."""
    captured_limit = []
    mock_sub = MagicMock()
    mock_sub.order_by = MagicMock(return_value=mock_sub)
    def capture_lim(lim):
        captured_limit.append(lim)
        return mock_sub
    mock_sub.limit = MagicMock(side_effect=capture_lim)
    mock_sub.get = AsyncMock(return_value=[])

    mock_doc = MagicMock()
    mock_doc.collection = MagicMock(return_value=mock_sub)
    mock_col = MagicMock()
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client = MagicMock()
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        await get_user_outcomes("u1", limit=500)

    assert len(captured_limit) == 1
    assert captured_limit[0] == 200


# ---------------------------------------------------------------------------
# 4. get_outcome_for_issue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_outcome_for_issue_found():
    expected = {
        "user_id": "u1", "repo_full_name": "org/repo", "issue_number": 7,
        "issue_title": "My issue", "outcome": "pr_opened", "is_positive": True,
        "recorded_at": "2026-11-02T00:00:00Z",
    }
    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.to_dict = MagicMock(return_value=expected)

    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    mock_sub = MagicMock()
    mock_sub_doc = MagicMock()
    mock_sub_doc.get = AsyncMock(return_value=mock_snapshot)
    mock_sub.document = MagicMock(return_value=mock_sub_doc)
    mock_doc.collection = MagicMock(return_value=mock_sub)
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await get_outcome_for_issue("u1", "org/repo", 7)

    assert result is not None
    assert result["outcome"] == "pr_opened"


@pytest.mark.asyncio
async def test_get_outcome_for_issue_not_found():
    mock_snapshot = MagicMock()
    mock_snapshot.exists = False

    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    mock_sub = MagicMock()
    mock_sub_doc = MagicMock()
    mock_sub_doc.get = AsyncMock(return_value=mock_snapshot)
    mock_sub.document = MagicMock(return_value=mock_sub_doc)
    mock_doc.collection = MagicMock(return_value=mock_sub)
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await get_outcome_for_issue("u1", "org/repo", 999)

    assert result is None


# ---------------------------------------------------------------------------
# 5. delete_outcome
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_outcome_success():
    mock_client = _make_mock_client()
    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await delete_outcome("u1", "org/repo", 42)
    assert result is True


@pytest.mark.asyncio
async def test_delete_outcome_error_returns_false():
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    mock_sub = MagicMock()
    mock_sub_doc = MagicMock()
    mock_sub_doc.delete = AsyncMock(side_effect=Exception("Firestore delete failed"))
    mock_sub.document = MagicMock(return_value=mock_sub_doc)
    mock_doc.collection = MagicMock(return_value=mock_sub)
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await delete_outcome("u1", "org/repo", 42)
    assert result is False


# ---------------------------------------------------------------------------
# 6. save_user_profile / load_user_profile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_user_profile_success():
    mock_client = _make_mock_client()
    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await save_user_profile("u1", {"username": "alice", "primary_languages": {"Python": 0.9}})
    assert result is True


@pytest.mark.asyncio
async def test_save_user_profile_empty_user_id():
    result = await save_user_profile("", {"username": "alice"})
    assert result is False


@pytest.mark.asyncio
async def test_load_user_profile_found():
    expected = {"username": "alice", "primary_languages": {"Python": 0.9}, "user_id": "u1", "updated_at": "2026-11-01"}
    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.to_dict = MagicMock(return_value=expected)

    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get = AsyncMock(return_value=mock_snapshot)
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await load_user_profile("u1")

    assert result is not None
    assert result["username"] == "alice"


@pytest.mark.asyncio
async def test_load_user_profile_not_found():
    mock_snapshot = MagicMock()
    mock_snapshot.exists = False

    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get = AsyncMock(return_value=mock_snapshot)
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await load_user_profile("u1")
    assert result is None


@pytest.mark.asyncio
async def test_load_user_profile_error_returns_none():
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get = AsyncMock(side_effect=Exception("Network timeout"))
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        result = await load_user_profile("u1")
    assert result is None


def test_memory_service_never_calls_create_database():
    import inspect
    import app.services.memory as mem_module

    source = inspect.getsource(mem_module)
    assert "create_database" not in source
    assert "database_admin" not in source


# ---------------------------------------------------------------------------
# 7. Recommendations logging
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_shown_recommendations():
    mock_client = MagicMock()
    batch_mock = MagicMock()
    batch_mock.set = MagicMock()
    batch_mock.commit = AsyncMock()
    mock_client.batch = MagicMock(return_value=batch_mock)

    mock_col = MagicMock()
    mock_doc = MagicMock()
    mock_sub = MagicMock()
    mock_sub_doc = MagicMock()
    mock_sub.document = MagicMock(return_value=mock_sub_doc)
    mock_doc.collection = MagicMock(return_value=mock_sub)
    mock_col.document = MagicMock(return_value=mock_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    item1 = ScoredIssueCandidate(
        issue=IssueMetadata(
            issue_url="https://github.com/facebook/react/issues/1",
            repo_full_name="facebook/react",
            issue_number=1,
            title="Fix hydration",
        ),
        features=CandidateFeatureVector(),
        score=0.88,
        one_line_reason="Good match",
        score_breakdown={"language_familiarity": 0.3},
    )

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        success = await log_shown_recommendations(
            user_id="user_test_logging",
            recommendations=[item1],
            relaxation_stage="Standard (90d)",
        )

    assert success is True
    batch_mock.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 8. Time decay & dynamic skill weights
# ---------------------------------------------------------------------------

def test_calculate_time_decay_math():
    now_iso = datetime.now(timezone.utc).isoformat()
    assert abs(calculate_time_decay(now_iso, half_life_days=60.0) - 1.0) < 0.05

    d60_iso = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    assert abs(calculate_time_decay(d60_iso, half_life_days=60.0) - 0.5) < 0.05

    d120_iso = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    assert abs(calculate_time_decay(d120_iso, half_life_days=60.0) - 0.25) < 0.05


def test_derive_skill_weights_bounded_and_clamped():
    now = datetime.now(timezone.utc).isoformat()
    outcomes = [
        {"outcome": "merged", "primary_language": "Python", "labels": ["bug"], "repo_full_name": "psf/requests", "recorded_at": now}
        for _ in range(10)
    ]
    skill_weights, excluded, why_note = derive_skill_weights_and_excluded_issues(outcomes)
    assert skill_weights.get("lang:python") == 0.3
    assert skill_weights.get("type:bug") == 0.3
    assert skill_weights.get("repo:psf/requests") == 0.3
    assert "psf/requests#None" not in excluded or "psf/requests#" in str(excluded)


def test_derive_skill_weights_too_hard_downweighting_and_exclusion_window():
    recent = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()

    outcomes = [
        {"outcome": "too_hard", "repo_full_name": "org/repo1", "issue_number": 1, "primary_language": "Rust", "recorded_at": recent},
        {"outcome": "too_hard", "repo_full_name": "org/repo2", "issue_number": 2, "primary_language": "Rust", "recorded_at": old},
    ]
    skill_weights, excluded, why_note = derive_skill_weights_and_excluded_issues(outcomes)
    assert "org/repo1#1" in excluded
    assert "org/repo2#2" not in excluded
    assert skill_weights.get("lang:rust") < 0.0


def test_why_these_results_note_generation():
    now = datetime.now(timezone.utc).isoformat()
    outcomes = [
        {"outcome": "skipped", "primary_language": "JavaScript", "repo_full_name": "org/js-app", "issue_number": i, "recorded_at": now}
        for i in range(3)
    ] + [
        {"outcome": "merged", "primary_language": "Python", "repo_full_name": "org/py-app", "issue_number": 10, "recorded_at": now}
    ]
    _, _, note = derive_skill_weights_and_excluded_issues(outcomes)
    assert note is not None
    assert "JavaScript" in note
    assert "Python" in note


# ---------------------------------------------------------------------------
# 9. Ranking, base score isolation, and memory integration
# ---------------------------------------------------------------------------

def test_score_candidate_issue_uses_skill_weights_and_exposes_base_score():
    profile = UserSkillProfile(
        username="dev",
        primary_languages={"Python": 0.8},
        frameworks=["fastapi"],
    )
    issue = IssueMetadata(
        issue_url="https://github.com/tiangolo/fastapi/issues/100",
        repo_full_name="tiangolo/fastapi",
        issue_number=100,
        primary_language="Python",
        labels=["enhancement"],
        repo_frameworks=["fastapi"],
        stars=1000,
    )
    features = compute_feature_vector(profile, issue)

    # 1. Base scoring without skill weights
    base_res = score_candidate_issue(profile, issue, features)
    assert base_res.memory_adjustment == 0.0
    assert base_res.base_score == base_res.score
    assert base_res.breakdown["base_score"] == base_res.score

    # 2. Dynamic weights applied: boost Python
    boosted_res = score_candidate_issue(profile, issue, features, skill_weights={"lang:python": 0.15})
    assert boosted_res.score > base_res.score
    assert boosted_res.memory_adjustment == 0.15
    assert boosted_res.base_score == base_res.score
    assert boosted_res.breakdown["base_score"] == base_res.score

    # 3. Dynamic weights applied: penalize Python
    penalized_res = score_candidate_issue(profile, issue, features, skill_weights={"lang:python": -0.20})
    assert penalized_res.score < base_res.score
    assert penalized_res.memory_adjustment == -0.20
    assert penalized_res.base_score == base_res.score


def test_ranking_excludes_skipped_and_prioritizes_boosted():
    profile = UserSkillProfile(
        username="dev",
        primary_languages={"Python": 0.5, "Go": 0.5},
    )
    issues = [
        IssueMetadata(
            issue_url="https://github.com/org/py-repo/issues/1",
            repo_full_name="org/py-repo",
            issue_number=1,
            primary_language="Python",
            stars=500,
        ),
        IssueMetadata(
            issue_url="https://github.com/org/go-repo/issues/2",
            repo_full_name="org/go-repo",
            issue_number=2,
            primary_language="Go",
            stars=500,
        ),
    ]
    ranked = rank_viable_issues(profile, issues, top_k=2, skill_weights={"lang:go": 0.20, "lang:python": -0.10})
    assert len(ranked) == 2
    assert ranked[0].issue.primary_language == "Go"
    assert ranked[0].base_score is not None


# ---------------------------------------------------------------------------
# 10. User data deletion & blank state test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_all_user_data_removes_tree_and_caches():
    user_id = "user_to_purge"

    # Populate in-memory caches
    _LAST_GOOD_PROFILE_STORE[user_id] = UserSkillProfile(username="cached_user")
    _LAST_GOOD_RECOMMENDATIONS_STORE[user_id] = [
        ScoredIssueCandidate(
            issue=IssueMetadata(issue_url="url", repo_full_name="org/repo", issue_number=1),
            features=CandidateFeatureVector(),
            score=0.9,
            one_line_reason="Reason",
        )
    ]
    _PLAN_CACHE[f"plan:{user_id}:org/repo:1"] = (MagicMock(), 9999999999.0)

    # Mock client with collections and delete
    mock_client = MagicMock()
    mock_col = MagicMock()
    mock_user_doc = MagicMock()
    mock_user_doc.delete = AsyncMock()

    async def _mock_col_gen():
        sub_col = MagicMock()
        sub_doc = MagicMock()
        sub_doc.delete = AsyncMock()
        async def _mock_doc_gen():
            yield sub_doc
        sub_col.list_documents = MagicMock(return_value=_mock_doc_gen())
        async def _sub_empty():
            if False:
                yield None
        sub_doc.collections = MagicMock(return_value=_sub_empty())
        yield sub_col

    mock_user_doc.collections = MagicMock(return_value=_mock_col_gen())
    mock_col.document = MagicMock(return_value=mock_user_doc)
    mock_client.collection = MagicMock(return_value=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        res = await delete_all_user_data(user_id)

    assert res is True
    assert user_id not in _LAST_GOOD_PROFILE_STORE
    assert user_id not in _LAST_GOOD_RECOMMENDATIONS_STORE
    assert f"plan:{user_id}:org/repo:1" not in _PLAN_CACHE
    mock_user_doc.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_recommendation_request_after_deletion_starts_blank():
    """Verify that after deletion, fallback caches return empty rather than stale state."""
    user_id = "blank_state_user"

    _LAST_GOOD_PROFILE_STORE[user_id] = UserSkillProfile(username="stale_user")
    _LAST_GOOD_RECOMMENDATIONS_STORE[user_id] = [
        ScoredIssueCandidate(
            issue=IssueMetadata(issue_url="url", repo_full_name="org/repo", issue_number=10),
            features=CandidateFeatureVector(),
            score=0.95,
            one_line_reason="Stale result",
        )
    ]

    # Delete
    mock_client = _make_mock_client()
    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        await delete_all_user_data(user_id)

    # Next recommendation fetch cannot find cached profile or recommendations
    assert _LAST_GOOD_PROFILE_STORE.get(user_id) is None
    assert _LAST_GOOD_RECOMMENDATIONS_STORE.get(user_id) is None


# ---------------------------------------------------------------------------
# 11. Security & isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tenant_isolation_user_a_cannot_access_user_b():
    user_a = "user_tenant_a"
    user_b = "user_tenant_b"

    mock_client = MagicMock()
    accessed_paths = []

    def mock_col(col_name):
        c = MagicMock()
        def mock_doc(doc_id):
            accessed_paths.append(f"{col_name}/{doc_id}")
            d = MagicMock()
            d.delete = AsyncMock()
            d.get = AsyncMock(return_value=MagicMock(exists=False))
            d.set = AsyncMock()
            async def _empty():
                if False:
                    yield None
            d.collections = MagicMock(return_value=_empty())
            def mock_sub(sname):
                s = MagicMock()
                s.order_by = MagicMock(return_value=s)
                s.limit = MagicMock(return_value=s)
                s.get = AsyncMock(return_value=[])
                return s
            d.collection = MagicMock(side_effect=mock_sub)
            return d
        c.document = MagicMock(side_effect=mock_doc)
        return c

    mock_client.collection = MagicMock(side_effect=mock_col)

    with patch("app.services.memory._get_client", AsyncMock(return_value=mock_client)):
        await delete_all_user_data(user_a)
        await get_user_outcomes(user_a)

    for p in accessed_paths:
        assert user_b not in p
        assert user_a in p


# ---------------------------------------------------------------------------
# 12. Firestore emulator live test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_firestore_emulator_real_write_and_read():
    emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if not emulator_host:
        pytest.skip("FIRESTORE_EMULATOR_HOST not set (run with emulator:exec to execute)")

    from google.cloud import firestore as real_fs
    client = real_fs.AsyncClient(project="oss-match", database="(default)")

    try:
        user_id = "test_emulator_user_1"
        repo = "facebook/react"
        num = 9999
        doc_id = make_outcome_doc_id(repo, num)

        doc_ref = client.collection("users").document(user_id).collection("outcomes").document(doc_id)
        await doc_ref.set({
            "repo_full_name": repo,
            "issue_number": num,
            "outcome": "skipped",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })

        read_snap = await doc_ref.get()
        assert read_snap.exists is True
        assert read_snap.to_dict()["outcome"] == "skipped"

        await doc_ref.delete()
    finally:
        client.close()
