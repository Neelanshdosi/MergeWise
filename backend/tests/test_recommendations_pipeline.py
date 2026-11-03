from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
import pytest

from app.auth.dependencies import AuthenticatedUser
from app.routers.recommendations import get_recommended_issues
from mergewise_features.schemas import UserSkillProfile, ViabilityRejectionReason


def _create_mock_issue(idx: int, state: str = "open", assigned: bool = False, is_pr: bool = False) -> dict:
    return {
        "id": 1000 + idx,
        "number": idx,
        "title": f"Issue #{idx}: Sample bug in backend",
        "state": state,
        "body": f"Description for sample issue #{idx} with reproduction steps.",
        "html_url": f"https://github.com/test-org/repo-{idx % 3}/issues/{idx}",
        "url": f"https://api.github.com/repos/test-org/repo-{idx % 3}/issues/{idx}",
        "comments_url": f"https://api.github.com/repos/test-org/repo-{idx % 3}/issues/{idx}/comments",
        "repository_url": f"https://api.github.com/repos/test-org/repo-{idx % 3}",
        "assignee": {"login": f"dev_{idx}"} if assigned else None,
        "assignees": [{"login": f"dev_{idx}"}] if assigned else [],
        "labels": [{"name": "good first issue"}, {"name": "python"}],
        "pull_request": {"url": "..."} if is_pr else None,
        "comments": idx % 3,
    }


@pytest.mark.asyncio
async def test_pipeline_with_30_mock_issues_at_least_5_survive():
    """
    Test requirement 7: Mock search returning 30 issues:
    - 5 closed
    - 5 already assigned
    - 5 with competing open PRs
    - 3 with recent claim comments
    - 12 completely viable issues
    Asserts: pipeline processes 30 issues and at least 5 viable issues survive.
    """
    mock_issues = []
    # 0..4: closed
    for i in range(5):
        mock_issues.append(_create_mock_issue(i, state="closed"))
    # 5..9: assigned
    for i in range(5, 10):
        mock_issues.append(_create_mock_issue(i, assigned=True))
    # 10..29: open & unassigned (20 issues)
    for i in range(10, 30):
        mock_issues.append(_create_mock_issue(i))

    now = datetime.now(timezone.utc)

    # Function returning comments: for issues 10, 11, 12, return claim comments
    async def mock_get_comments(comments_url: str, **kwargs):
        for claimed_idx in (10, 11, 12):
            if f"/{claimed_idx}/comments" in comments_url:
                return [{
                    "created_at": (now - timedelta(days=2)).isoformat(),
                    "body": "I'll take this and submit a PR soon!",
                    "user": {"login": f"claim_user_{claimed_idx}"},
                }]
        return []

    # Function returning timeline: for issues 13, 14, 15, 16, 17, return open competing PR
    async def mock_get_timeline(issue_url: str, **kwargs):
        for pr_idx in (13, 14, 15, 16, 17):
            if f"/{pr_idx}" in issue_url:
                return [{
                    "event": "cross-referenced",
                    "source": {
                        "issue": {
                            "number": 900 + pr_idx,
                            "pull_request": {"url": "pr_url"},
                            "state": "open",
                        }
                    }
                }]
        return []

    # Build mock user and profile
    mock_user = AuthenticatedUser(
        user_id="user_test_pipeline",
        claims={"sub": "user_test_pipeline", "username": "testdev", "github_username": "testdev"},
    )

    mock_profile = UserSkillProfile(
        username="testdev",
        primary_languages={"Python": 0.5, "JavaScript": 0.5},
        topics=["cli", "api"],
        total_commits=20,
    )

    with patch("app.routers.recommendations.GitHubClient") as MockClientClass, \
         patch("app.routers.recommendations.build_user_profile", new_callable=AsyncMock) as mock_build_profile:

        from mergewise_features.schemas import ResourceRateLimit

        mock_client = MockClientClass.return_value
        mock_client.search_single_query = AsyncMock(return_value=mock_issues)
        mock_client.get_issue_comments = AsyncMock(side_effect=mock_get_comments)
        mock_client.get_issue_timeline = AsyncMock(side_effect=mock_get_timeline)
        mock_client.get_repo_details = AsyncMock(return_value={"stargazers_count": 500, "open_issues_count": 10, "pushed_at": now.isoformat()})
        mock_client.get_repo_manifest_frameworks = AsyncMock(return_value=[])
        mock_client.rate_limits = {
            "search": ResourceRateLimit(resource="search", remaining=28, limit=30, is_limited=False),
            "core": ResourceRateLimit(resource="core", remaining=4990, limit=5000, is_limited=False),
        }
        mock_build_profile.return_value = mock_profile

        response = await get_recommended_issues(user=mock_user, refresh=True)

        assert response.is_cold_start is False
        assert response.pipeline_stats.candidates_fetched == 30

        # Verify rejection stats
        assert response.pipeline_stats.rejected_by_reason[ViabilityRejectionReason.CLOSED.value] == 5
        assert response.pipeline_stats.rejected_by_reason[ViabilityRejectionReason.ALREADY_ASSIGNED.value] == 5
        assert response.pipeline_stats.rejected_by_reason[ViabilityRejectionReason.CLAIMED_IN_COMMENTS.value] == 3
        assert response.pipeline_stats.rejected_by_reason[ViabilityRejectionReason.COMPETING_OPEN_PR.value] == 5

        # Total viable issues that passed: 12 (issues 18 to 29)
        assert response.pipeline_stats.passed_viability >= 5
        assert len(response.recommendations) == 5

        # Verify all 5 recommendations are verified viable and have reasons
        for rec in response.recommendations:
            assert rec.viability_verified is True
            assert len(rec.one_line_reason) > 0
            assert rec.score > 0


@pytest.mark.asyncio
async def test_rate_limit_returns_partial_results_and_renders_profile():
    """
    Test requirement 7: When rate limit is encountered:
    - Does NOT crash or blank the page
    - Returns partial results from prior query
    - Profile still renders
    - Rate limit notice is attached with reset time
    """
    from app.services.github import GitHubRateLimitError
    from mergewise_features.schemas import ResourceRateLimit

    # Query 1 returns 3 viable issues
    query1_issues = [_create_mock_issue(100 + i) for i in range(3)]

    call_count = 0
    async def mock_search_with_rate_limit(query: str, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return query1_issues
        # Query 2 encounters rate limit
        raise GitHubRateLimitError(resource="search", reset_epoch=1730000000, remaining=0)

    mock_user = AuthenticatedUser(
        user_id="user_test_ratelimit",
        claims={"sub": "user_test_ratelimit", "username": "limitdev"},
    )
    mock_profile = UserSkillProfile(
        username="limitdev",
        primary_languages={"Python": 1.0},
        total_commits=10,
    )

    with patch("app.routers.recommendations.GitHubClient") as MockClientClass, \
         patch("app.routers.recommendations.build_user_profile", new_callable=AsyncMock) as mock_build_profile:

        mock_client = MockClientClass.return_value
        mock_client.search_single_query = AsyncMock(side_effect=mock_search_with_rate_limit)
        mock_client.get_issue_comments = AsyncMock(return_value=[])
        mock_client.get_issue_timeline = AsyncMock(return_value=[])
        mock_client.get_repo_details = AsyncMock(return_value={"stargazers_count": 500, "open_issues_count": 10, "pushed_at": datetime.now(timezone.utc).isoformat()})
        mock_client.get_repo_manifest_frameworks = AsyncMock(return_value=[])
        mock_client.rate_limits = {
            "search": ResourceRateLimit(resource="search", remaining=0, limit=30, is_limited=True, reset_time="14:45 UTC"),
            "core": ResourceRateLimit(resource="core", remaining=4950, limit=5000, is_limited=False),
        }
        mock_build_profile.return_value = mock_profile

        response = await get_recommended_issues(user=mock_user, refresh=True)

        # 1. Page does not blank - profile still renders
        assert response.profile is not None
        assert response.profile.username == "limitdev"

        # 2. Rate limit notice is present
        assert response.pipeline_stats.rate_limit_notice is not None
        assert "SEARCH" in response.pipeline_stats.rate_limit_notice.upper() or "rate limit" in response.pipeline_stats.rate_limit_notice.lower()

        # 3. Partial results from query 1 survived
        assert len(response.recommendations) == 3
        for rec in response.recommendations:
            assert rec.viability_verified is True


@pytest.mark.asyncio
async def test_search_remaining_27_does_not_raise_rate_limit_and_returns_16_viable_issues():
    """
    Test requirement 4:
    With search headers remaining=27, limit=30 and core limit=4977/5000:
    - 18 mock candidates fetched (1 closed, 1 assigned, 16 viable)
    - Verify NO rate-limit error is raised
    - Verify 16 viable issues pass and top 5 are ranked and returned
    - Verify pipeline_stats.rate_limit_notice is None (no false banner)
    - Verify search_rate_limit.is_limited is False in stats
    """
    import httpx
    from app.services.github import GitHubClient, GitHubRateLimitError
    from mergewise_features.schemas import ResourceRateLimit

    # 1. Verify GitHubClient._record_rate_limit directly on headers
    client = GitHubClient(token="mock_token")
    search_resp = httpx.Response(
        status_code=200,
        headers={
            "x-ratelimit-resource": "search",
            "x-ratelimit-remaining": "27",
            "x-ratelimit-limit": "30",
            "x-ratelimit-reset": "1730000000",
        },
        json={"items": []},
    )
    # Must NOT raise GitHubRateLimitError
    client._record_rate_limit(search_resp)
    assert client.rate_limits["search"].remaining == 27
    assert client.rate_limits["search"].limit == 30
    assert client.rate_limits["search"].is_limited is False

    core_resp = httpx.Response(
        status_code=200,
        headers={
            "x-ratelimit-resource": "core",
            "x-ratelimit-remaining": "4977",
            "x-ratelimit-limit": "5000",
            "x-ratelimit-reset": "1730000000",
        },
        json={},
    )
    client._record_rate_limit(core_resp)
    assert client.rate_limits["core"].remaining == 4977
    assert client.rate_limits["core"].limit == 5000
    assert client.rate_limits["core"].is_limited is False

    # 2. Build 18 mock candidates: 1 closed, 1 assigned, 16 viable
    mock_candidates = []
    mock_candidates.append(_create_mock_issue(1, state="closed"))
    mock_candidates.append(_create_mock_issue(2, assigned=True))
    for i in range(3, 19):  # 16 issues
        mock_candidates.append(_create_mock_issue(i, state="open", assigned=False))

    assert len(mock_candidates) == 18

    mock_user = AuthenticatedUser(
        user_id="user_test_27_rem",
        claims={"sub": "user_test_27_rem", "username": "validdev"},
    )
    mock_profile = UserSkillProfile(
        username="validdev",
        primary_languages={"Python": 1.0},
        total_commits=15,
    )

    with patch("app.routers.recommendations.GitHubClient") as MockClientClass, \
         patch("app.routers.recommendations.build_user_profile", new_callable=AsyncMock) as mock_build_profile:

        mock_instance = MockClientClass.return_value
        mock_instance.search_single_query = AsyncMock(return_value=mock_candidates)
        mock_instance.get_issue_comments = AsyncMock(return_value=[])
        mock_instance.get_issue_timeline = AsyncMock(return_value=[])
        mock_instance.get_repo_details = AsyncMock(return_value={"stargazers_count": 500, "open_issues_count": 10, "pushed_at": datetime.now(timezone.utc).isoformat()})
        mock_instance.get_repo_manifest_frameworks = AsyncMock(return_value=[])
        mock_instance.rate_limits = {
            "search": ResourceRateLimit(resource="search", remaining=27, limit=30, is_limited=False),
            "core": ResourceRateLimit(resource="core", remaining=4977, limit=5000, is_limited=False),
        }
        mock_build_profile.return_value = mock_profile

        response = await get_recommended_issues(user=mock_user, refresh=True)

        # 16 viable issues passed out of 18 candidates
        assert response.pipeline_stats.candidates_fetched == 18
        assert response.pipeline_stats.passed_viability == 16

        # Top 5 recommendations returned
        assert len(response.recommendations) == 5

        # No rate-limit notice/banner
        assert response.pipeline_stats.rate_limit_notice is None
        assert response.pipeline_stats.search_rate_limit.is_limited is False
        assert response.pipeline_stats.search_rate_limit.remaining == 27
        assert response.pipeline_stats.core_rate_limit.is_limited is False
        assert response.pipeline_stats.core_rate_limit.remaining == 4977


def test_resource_rate_limit_thresholds_and_guards():
    """
    Test requirement 1 & 2:
    Separate thresholds per resource:
    - search: raise ONLY at remaining=0 or actual 403/429 limit response
    - core: raise at small buffer remaining <= 50 or actual 403/429 limit response
    - Never compare against one shared threshold
    - Don't mark search as LIMITED unless remaining is 0 or actual limit response
    """
    import httpx
    from app.services.github import GitHubClient, GitHubRateLimitError

    client = GitHubClient(token="mock_token")

    # Search at remaining=27 -> NOT limited
    resp_search_27 = httpx.Response(
        status_code=200,
        headers={"x-ratelimit-resource": "search", "x-ratelimit-remaining": "27", "x-ratelimit-limit": "30"},
        json={},
    )
    client._record_rate_limit(resp_search_27)
    assert client.rate_limits["search"].is_limited is False
    assert client.rate_limits["search"].remaining == 27

    # Search at remaining=1 -> NOT limited (only at 0!)
    resp_search_1 = httpx.Response(
        status_code=200,
        headers={"x-ratelimit-resource": "search", "x-ratelimit-remaining": "1", "x-ratelimit-limit": "30"},
        json={},
    )
    client._record_rate_limit(resp_search_1)
    assert client.rate_limits["search"].is_limited is False

    # Search at remaining=0 -> LIMITED, raises GitHubRateLimitError
    resp_search_0 = httpx.Response(
        status_code=200,
        headers={"x-ratelimit-resource": "search", "x-ratelimit-remaining": "0", "x-ratelimit-limit": "30"},
        json={},
    )
    with pytest.raises(GitHubRateLimitError) as exc_info:
        client._record_rate_limit(resp_search_0)
    assert exc_info.value.resource == "search"
    assert client.rate_limits["search"].is_limited is True

    # Core at remaining=51 -> NOT limited
    resp_core_51 = httpx.Response(
        status_code=200,
        headers={"x-ratelimit-resource": "core", "x-ratelimit-remaining": "51", "x-ratelimit-limit": "5000"},
        json={},
    )
    client._record_rate_limit(resp_core_51)
    assert client.rate_limits["core"].is_limited is False

    # Core at remaining=50 -> LIMITED (buffer <= 50), raises GitHubRateLimitError
    resp_core_50 = httpx.Response(
        status_code=200,
        headers={"x-ratelimit-resource": "core", "x-ratelimit-remaining": "50", "x-ratelimit-limit": "5000"},
        json={},
    )
    with pytest.raises(GitHubRateLimitError) as exc_info:
        client._record_rate_limit(resp_core_50)
    assert exc_info.value.resource == "core"
    assert client.rate_limits["core"].is_limited is True

    # Actual 403 rate limit response -> raises GitHubRateLimitError
    resp_403_limit = httpx.Response(
        status_code=403,
        headers={"x-ratelimit-resource": "search", "x-ratelimit-remaining": "0"},
        text='{"message": "API rate limit exceeded for user"}',
    )
    with pytest.raises(GitHubRateLimitError) as exc_info:
        client._record_rate_limit(resp_403_limit)
    assert exc_info.value.resource == "search"


def test_score_variance_and_distinct_reasons():
    """
    Test requirement B.2, B.5 & B.6:
    Score must vary across issues (not all 65%).
    Reasons must be specific and distinct per issue based on actual matches.
    Score breakdown must be present.
    """
    from mergewise_features import UserSkillProfile, IssueMetadata
    from app.ranker.heuristic import rank_viable_issues

    profile = UserSkillProfile(
        username="expert_dev",
        primary_languages={"Python": 0.5, "JavaScript": 0.3, "TypeScript": 0.2},
        frameworks=["fastapi", "react", "pyspark"],
        topics=["api", "data"],
        total_commits=100,
        activity_last_1m=10,
    )

    candidates = [
        # Issue 1: Python + FastAPI + pyspark + stars 15k + code snippet + pushed 2d ago
        IssueMetadata(
            issue_url="https://api.github.com/repos/org1/repo1/issues/1",
            repo_full_name="org1/repo1",
            title="FastAPI route crash with pyspark dataframe",
            body="Bug reproduction:\n```python\nimport fastapi\n```\nDetails here.",
            primary_language="Python",
            labels=["good first issue", "bug"],
            stars=15000,
            body_length=450,
            has_code_snippet=True,
            days_since_push=2,
            repo_topics=["api", "fastapi"],
            repo_frameworks=["fastapi", "pyspark"],
        ),
        # Issue 2: JavaScript + React + stars 800 + pushed 15d ago
        IssueMetadata(
            issue_url="https://api.github.com/repos/org2/repo2/issues/2",
            repo_full_name="org2/repo2",
            title="React component state mismatch",
            body="Occurs during re-rendering in UI.",
            primary_language="JavaScript",
            labels=["good first issue"],
            stars=800,
            body_length=220,
            has_code_snippet=False,
            days_since_push=15,
            repo_topics=["react", "ui"],
            repo_frameworks=["react"],
        ),
        # Issue 3: TypeScript + help wanted + stars 50k + pushed 4d ago
        IssueMetadata(
            issue_url="https://api.github.com/repos/org3/repo3/issues/3",
            repo_full_name="org3/repo3",
            title="Add typed response schema generator",
            body="We need a TypeScript generator function.",
            primary_language="TypeScript",
            labels=["help wanted"],
            stars=50000,
            body_length=600,
            has_code_snippet=False,
            days_since_push=4,
            repo_topics=["typescript"],
        ),
        # Issue 4: Python without matching frameworks + low stars + pushed 45d ago
        IssueMetadata(
            issue_url="https://api.github.com/repos/org4/repo4/issues/4",
            repo_full_name="org4/repo4",
            title="Fix typo in CLI help text",
            body="Just a typo fix in arg parser documentation.",
            primary_language="Python",
            labels=["documentation"],
            stars=45,
            body_length=120,
            has_code_snippet=False,
            days_since_push=45,
        ),
        # Issue 5: JavaScript beginner issue + no stars + pushed 60d ago
        IssueMetadata(
            issue_url="https://api.github.com/repos/org5/repo5/issues/5",
            repo_full_name="org5/repo5",
            title="Update README badges",
            body="Update build badges and installation section.",
            primary_language="JavaScript",
            labels=["good first issue"],
            stars=12,
            body_length=95,
            has_code_snippet=False,
            days_since_push=60,
        ),
    ]

    ranked = rank_viable_issues(profile, candidates, top_k=5)

    assert len(ranked) == 5

    # 1. Verify score variance: all 5 scores must be distinct!
    scores = [r.score for r in ranked]
    assert len(set(scores)) == 5, f"Expected 5 distinct scores, got {scores}"

    # Verify scores are sorted descending
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]

    # 2. Verify reasons are specific and distinct
    reasons = [r.one_line_reason for r in ranked]
    assert len(set(reasons)) == 5, f"Expected 5 distinct reasons, got {reasons}"

    # Specific assertions on truthful content
    assert "pyspark" in ranked[0].one_line_reason or "fastapi" in ranked[0].one_line_reason
    assert "repo updated 2 days ago" in ranked[0].one_line_reason

    # 3. Verify score breakdown is attached to each candidate
    for r in ranked:
        assert r.score_breakdown is not None
        assert "language_familiarity" in r.score_breakdown
        assert "domain_framework_fit" in r.score_breakdown
        assert "repo_health_recency" in r.score_breakdown


def test_repo_diversity_at_most_two_per_repo():
    """
    Test requirement B.3 & B.6:
    At most 2 issues from the same repository in the top 5.
    """
    from mergewise_features import UserSkillProfile, IssueMetadata
    from app.ranker.heuristic import rank_viable_issues

    profile = UserSkillProfile(
        username="testdev",
        primary_languages={"Python": 1.0},
    )

    candidates = [
        # 4 issues from popular/repo
        IssueMetadata(
            issue_url="https://api.github.com/repos/popular/repo/issues/1",
            repo_full_name="popular/repo",
            title="Issue 1",
            body="Reproduction 1 with details.",
            primary_language="Python",
            stars=10000,
        ),
        IssueMetadata(
            issue_url="https://api.github.com/repos/popular/repo/issues/2",
            repo_full_name="popular/repo",
            title="Issue 2",
            body="Reproduction 2 with details.",
            primary_language="Python",
            stars=10000,
        ),
        IssueMetadata(
            issue_url="https://api.github.com/repos/popular/repo/issues/3",
            repo_full_name="popular/repo",
            title="Issue 3",
            body="Reproduction 3 with details.",
            primary_language="Python",
            stars=10000,
        ),
        IssueMetadata(
            issue_url="https://api.github.com/repos/popular/repo/issues/4",
            repo_full_name="popular/repo",
            title="Issue 4",
            body="Reproduction 4 with details.",
            primary_language="Python",
            stars=10000,
        ),
        # 2 issues from other repos
        IssueMetadata(
            issue_url="https://api.github.com/repos/other1/repo/issues/5",
            repo_full_name="other1/repo",
            title="Issue 5",
            body="Reproduction 5 with details.",
            primary_language="Python",
            stars=5000,
        ),
        IssueMetadata(
            issue_url="https://api.github.com/repos/other2/repo/issues/6",
            repo_full_name="other2/repo",
            title="Issue 6",
            body="Reproduction 6 with details.",
            primary_language="Python",
            stars=4000,
        ),
    ]

    ranked = rank_viable_issues(profile, candidates, top_k=5, max_per_repo=2)

    assert len(ranked) >= 4
    # Count occurrences of popular/repo
    popular_count = sum(1 for r in ranked if r.issue.repo_full_name == "popular/repo")
    assert popular_count <= 2, f"Expected at most 2 issues from popular/repo, got {popular_count}"


@pytest.mark.asyncio
async def test_quality_filters_in_pipeline():
    """
    Test requirement B.4 & B.6:
    Quality filters drop:
    - issues with no description
    - issues titled like '[DEVELOPMENT]' or 'tracking'/'epic'
    - repos with no push in the last 90 days
    """
    from app.routers.recommendations import get_recommended_issues
    from mergewise_features.schemas import ResourceRateLimit

    mock_candidates = [
        # 1. No description -> should be dropped
        {
            "id": 901,
            "number": 1,
            "title": "Valid title here",
            "body": "",  # Empty description
            "state": "open",
            "repository_url": "https://api.github.com/repos/test/repo1",
            "labels": [{"name": "good first issue"}],
        },
        # 2. Title like '[DEVELOPMENT]' -> should be dropped
        {
            "id": 902,
            "number": 2,
            "title": "[DEVELOPMENT] Build the new core",
            "body": "Long detailed description with reproduction and steps.",
            "state": "open",
            "repository_url": "https://api.github.com/repos/test/repo1",
            "labels": [{"name": "good first issue"}],
        },
        # 3. Title with 'tracking issue' -> should be dropped
        {
            "id": 903,
            "number": 3,
            "title": "Tracking issue for v3.0 release",
            "body": "Long detailed description with checklist and items.",
            "state": "open",
            "repository_url": "https://api.github.com/repos/test/repo1",
            "labels": [{"name": "good first issue"}],
        },
        # 4. Repo inactive > 90 days -> should be dropped
        {
            "id": 904,
            "number": 4,
            "title": "Valid bug report in old project",
            "body": "Detailed reproduction steps for a bug in python client.",
            "state": "open",
            "repository_url": "https://api.github.com/repos/test/inactive-repo",
            "labels": [{"name": "good first issue"}],
        },
        # 5. Clean, active issue -> should pass
        {
            "id": 905,
            "number": 5,
            "title": "Fix validation error in query builder",
            "body": "Here is a code snippet:\n```python\nquery.build()\n```",
            "state": "open",
            "repository_url": "https://api.github.com/repos/test/active-repo",
            "labels": [{"name": "good first issue"}],
        },
    ]

    async def mock_get_repo_details(repo_full_name: str):
        if "inactive-repo" in repo_full_name:
            # 120 days since push
            return {
                "stargazers_count": 250,
                "pushed_at": (datetime.now(timezone.utc) - timedelta(days=120)).isoformat(),
                "open_issues_count": 5,
            }
        else:
            # 5 days since push
            return {
                "stargazers_count": 3400,
                "pushed_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                "open_issues_count": 12,
            }

    mock_user = AuthenticatedUser(
        user_id="user_test_filters",
        claims={"sub": "user_test_filters", "username": "filterdev"},
    )
    mock_profile = UserSkillProfile(
        username="filterdev",
        primary_languages={"Python": 1.0},
    )

    with patch("app.routers.recommendations.GitHubClient") as MockClientClass, \
         patch("app.routers.recommendations.build_user_profile", new_callable=AsyncMock) as mock_build_profile:

        mock_instance = MockClientClass.return_value
        mock_instance.search_single_query = AsyncMock(return_value=mock_candidates)
        mock_instance.get_issue_comments = AsyncMock(return_value=[])
        mock_instance.get_issue_timeline = AsyncMock(return_value=[])
        mock_instance.get_repo_details = AsyncMock(side_effect=mock_get_repo_details)
        mock_instance.get_repo_manifest_frameworks = AsyncMock(return_value=[])
        mock_instance.rate_limits = {
            "search": ResourceRateLimit(resource="search", remaining=25, limit=30, is_limited=False),
            "core": ResourceRateLimit(resource="core", remaining=4950, limit=5000, is_limited=False),
        }
        mock_build_profile.return_value = mock_profile

        response = await get_recommended_issues(user=mock_user, refresh=True)

        # 4 bad issues dropped by quality filters:
        assert response.pipeline_stats.rejected_by_reason.get("NO_DESCRIPTION", 0) == 1
        assert response.pipeline_stats.rejected_by_reason.get("META_OR_TRACKING", 0) == 2
        assert response.pipeline_stats.rejected_by_reason.get("INACTIVE_REPO", 0) == 1

        # Only the clean issue (#5) survived
        assert response.pipeline_stats.passed_viability == 1
        assert len(response.recommendations) == 1
        rec = response.recommendations[0]
        assert rec.issue.issue_number == 5
        assert rec.issue.stars == 3400
        assert "repo updated" in rec.one_line_reason and "days ago" in rec.one_line_reason


