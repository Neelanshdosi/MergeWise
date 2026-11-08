"""
Router for User Contributions, Funnel Metrics, and Outcome Suggestions.
Public data only. Uses existing GitHub token fetched on demand from Clerk.
"""
import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from ..auth.dependencies import AuthenticatedUser, get_current_user
from ..services.github import GitHubClient, GitHubRateLimitError
from ..services.memory import get_user_outcomes, _get_client, OutcomeType
from mergewise_features import DEV_DEPENDENCY_STOP_LIST, is_stopped_dependency

logger = logging.getLogger("mergewise.routers.contributions")
router = APIRouter(prefix="/api", tags=["Contributions"])

# In-memory per-user cache for contributions: user_id -> (data_dict, expires_at_timestamp)
_CONTRIBUTIONS_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes


class ContributionItem(BaseModel):
    repo: str
    number: int
    title: str
    state: str  # "merged" | "open" | "closed"
    created_at: Optional[str] = None
    merged_at: Optional[str] = None
    url: str
    stars: int = 0
    repo_owner_avatar_url: Optional[str] = None
    via_mergewise: bool = False


class ContributionsSummary(BaseModel):
    merged_count: int = 0
    open_count: int = 0
    closed_count: int = 0
    repo_count: int = 0


class ContributionsResponse(BaseModel):
    summary: ContributionsSummary
    items: List[ContributionItem] = []
    rate_limit_notice: Optional[str] = None


class FunnelMetricsResponse(BaseModel):
    shown: int = 0
    plan_viewed: int = 0
    attempted: int = 0
    pr_opened: int = 0
    merged: int = 0


class OutcomeSuggestion(BaseModel):
    repo: str
    issue_number: int
    pr_number: int
    pr_title: str
    pr_url: str
    suggested_outcome: str  # "merged" or "pr_opened"


def clear_user_contributions_cache(user_id: str) -> None:
    """Evicts in-memory contributions cache for the given user."""
    _CONTRIBUTIONS_CACHE.pop(user_id, None)


def parse_repo_from_url(repo_url: Optional[str], html_url: Optional[str] = None) -> str:
    """Extracts 'owner/repo' from api or html GitHub URLs."""
    if repo_url:
        match = re.search(r"repos/([^/]+/[^/]+)", repo_url)
        if match:
            return match.group(1)
    if html_url:
        match = re.search(r"github\.com/([^/]+/[^/]+)", html_url)
        if match:
            return match.group(1)
    return ""


def extract_referenced_issues_from_body(body: Optional[str]) -> List[int]:
    """
    Extracts referenced issue numbers from PR body via Fixes/Closes/Resolves #N syntax.
    Handles: Fix #123, Fixes #123, Fixed #123, Close #123, Closes #123, Closed #123,
    Resolve #123, Resolves #123, Resolved #123, case-insensitively.
    """
    if not body:
        return []
    # Regex matches keyword followed by optional owner/repo prefix and #number
    pattern = r"(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+(?:[\w.-]+/[\w.-]+)?#(\d+)"
    matches = re.findall(pattern, body, re.IGNORECASE)
    numbers: List[int] = []
    for m in matches:
        try:
            numbers.append(int(m))
        except ValueError:
            continue
    return numbers


def classify_pr_state(item: Dict[str, Any]) -> str:
    """
    Classifies PR as 'merged', 'open', or 'closed' using pull_request.merged_at.
    """
    pr_data = item.get("pull_request") or {}
    merged_at = pr_data.get("merged_at")
    if merged_at:
        return "merged"
    item_state = item.get("state")
    if item_state == "open":
        return "open"
    return "closed"


@router.get("/contributions", response_model=ContributionsResponse)
async def get_user_contributions(
    user: AuthenticatedUser = Depends(get_current_user),
    refresh: bool = Query(False, description="Force bypass 15-minute contributions cache"),
):
    """
    Fetches the authenticated user's external open-source PR contributions.
    - Derives login securely from GET /user (never client-supplied)
    - Query: is:pr author:<login> -user:<login> (excludes user-owned repos)
    - Classifies merged / open / closed via pull_request.merged_at
    - Caches top 20 repo stars for 30 min
    - Caches user response for 15 minutes
    - Correlates with Firestore outcomes for 'via_mergewise' badge
    - Gracefully handles rate limits returning partial data with notice
    """
    now = time.time()
    if not refresh and user.user_id in _CONTRIBUTIONS_CACHE:
        cached_data, expires_at = _CONTRIBUTIONS_CACHE[user.user_id]
        if now < expires_at:
            return ContributionsResponse(**cached_data)

    token = await user.get_github_token()
    client = GitHubClient(token=token)

    # 1. Derive login strictly from GitHub /user endpoint
    login: Optional[str] = None
    try:
        user_profile = await client.get_user_profile(force_refresh=refresh)
        if isinstance(user_profile, dict):
            login = user_profile.get("login")
    except Exception as e:
        logger.warning(f"Could not fetch user profile for contributions: {e}")

    # Fallback to claims only if /user was completely unreachable
    if not login:
        login = user.claims.get("github_username") or user.claims.get("username")

    if not login or login == "developer":
        # No valid GitHub identity; return clean empty response
        empty_resp = ContributionsResponse(
            summary=ContributionsSummary(),
            items=[],
            rate_limit_notice=None,
        )
        return empty_resp

    # 2. Query GitHub search API for user's PRs excluding own repos
    search_query = f"is:pr author:{login} -user:{login}"
    search_url = "https://api.github.com/search/issues"
    params = {
        "q": search_query,
        "sort": "updated",
        "order": "desc",
        "per_page": 50,
    }

    raw_items: List[Dict[str, Any]] = []
    rate_limit_notice: Optional[str] = None

    try:
        data = await client.get(
            search_url,
            params=params,
            ttl_seconds=900,
            force_refresh=refresh,
        )
        if isinstance(data, dict):
            raw_items = data.get("items", [])
    except GitHubRateLimitError as rle:
        logger.warning(f"GitHub search rate limit exceeded fetching contributions for {login}: {rle.detail}")
        rate_limit_notice = rle.detail
        # If we have a stale cache, return it with the notice
        if user.user_id in _CONTRIBUTIONS_CACHE:
            cached_data, _ = _CONTRIBUTIONS_CACHE[user.user_id]
            cached_data_copy = dict(cached_data)
            cached_data_copy["rate_limit_notice"] = rate_limit_notice
            return ContributionsResponse(**cached_data_copy)
    except Exception as e:
        logger.error(f"Search API error for contributions {login}: {e}")

    # 3. Load user outcomes from Firestore to check 'via_mergewise'
    recorded_outcomes = await get_user_outcomes(user.user_id, limit=500)
    # Build set of (repo_lower, issue_number)
    outcome_lookup: Set[Tuple[str, int]] = set()
    for o in recorded_outcomes:
        repo_name = (o.get("repo") or "").lower().strip()
        issue_num = o.get("issue_number")
        if repo_name and isinstance(issue_num, int):
            outcome_lookup.add((repo_name, issue_num))

    # 4. Process items and determine unique repos for stars
    processed_items: List[ContributionItem] = []
    repo_counts: Dict[str, int] = {}
    repos_in_order: List[str] = []

    for item in raw_items:
        repo_full_name = parse_repo_from_url(item.get("repository_url"), item.get("html_url"))
        if not repo_full_name:
            continue

        # Strict check: guarantee own repo exclusion even if search index was stale
        if repo_full_name.lower().startswith(f"{login.lower()}/"):
            continue

        if repo_full_name not in repo_counts:
            repo_counts[repo_full_name] = 0
            repos_in_order.append(repo_full_name)
        repo_counts[repo_full_name] += 1

        pr_number = item.get("number", 0)
        title = item.get("title", "")
        pr_state = classify_pr_state(item)
        created_at = item.get("created_at")
        merged_at = (item.get("pull_request") or {}).get("merged_at")
        html_url = item.get("html_url", "")
        body = item.get("body") or ""

        # Default avatar based on repo owner
        owner = repo_full_name.split("/")[0] if "/" in repo_full_name else login
        owner_avatar_url = f"https://github.com/{owner}.png"

        # Check via_mergewise
        ref_issue_numbers = extract_referenced_issues_from_body(body)
        repo_lower = repo_full_name.lower()

        via_mw = False
        # Check direct PR match or any referenced issue in that repo
        if (repo_lower, pr_number) in outcome_lookup:
            via_mw = True
        else:
            for ref_num in ref_issue_numbers:
                if (repo_lower, ref_num) in outcome_lookup:
                    via_mw = True
                    break

        item_obj = ContributionItem(
            repo=repo_full_name,
            number=pr_number,
            title=title,
            state=pr_state,
            created_at=created_at,
            merged_at=merged_at,
            url=html_url,
            stars=0,
            repo_owner_avatar_url=owner_avatar_url,
            via_mergewise=via_mw,
        )
        processed_items.append(item_obj)

    # 5. Fetch repo stars for top 20 repos (cached 30 min in client.get_repo_details)
    top_20_repos = repos_in_order[:20]
    repo_stars_map: Dict[str, int] = {}
    repo_avatar_map: Dict[str, str] = {}

    for repo_name in top_20_repos:
        try:
            repo_info = await client.get_repo_details(repo_name)
            if isinstance(repo_info, dict):
                repo_stars_map[repo_name] = repo_info.get("stargazers_count", 0)
                owner_info = repo_info.get("owner") or {}
                if owner_info.get("avatar_url"):
                    repo_avatar_map[repo_name] = owner_info["avatar_url"]
        except GitHubRateLimitError as rle:
            logger.warning(f"Rate limit while fetching repo details for {repo_name}: {rle.detail}")
            if not rate_limit_notice:
                rate_limit_notice = rle.detail
            break
        except Exception as e:
            logger.warning(f"Could not load details for repo {repo_name}: {e}")

    # Apply stars and enhanced avatars back to items
    for item in processed_items:
        if item.repo in repo_stars_map:
            item.stars = repo_stars_map[item.repo]
        if item.repo in repo_avatar_map:
            item.repo_owner_avatar_url = repo_avatar_map[item.repo]

    # 6. Compute summary stats
    merged_cnt = sum(1 for it in processed_items if it.state == "merged")
    open_cnt = sum(1 for it in processed_items if it.state == "open")
    closed_cnt = sum(1 for it in processed_items if it.state == "closed")
    unique_repos_cnt = len(set(it.repo for it in processed_items))

    summary = ContributionsSummary(
        merged_count=merged_cnt,
        open_count=open_cnt,
        closed_count=closed_cnt,
        repo_count=unique_repos_cnt,
    )

    response_data = {
        "summary": summary.model_dump(),
        "items": [it.model_dump() for it in processed_items],
        "rate_limit_notice": rate_limit_notice,
    }

    # Cache for 15 minutes
    _CONTRIBUTIONS_CACHE[user.user_id] = (response_data, now + CACHE_TTL_SECONDS)

    return ContributionsResponse(**response_data)


@router.get("/funnel", response_model=FunnelMetricsResponse)
async def get_user_funnel_metrics(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Returns user's open-source progression funnel counts from Firestore:
    shown, plan_viewed, attempted, pr_opened, merged.
    """
    shown_count = 0
    plan_viewed_count = 0
    attempted_count = 0
    pr_opened_count = 0
    merged_count = 0

    try:
        client = await _get_client()
        # Count recommendations shown
        recs_col = client.collection("users").document(user.user_id).collection("recommendations")
        recs_docs = await recs_col.get()
        shown_count = len(recs_docs)
    except Exception as e:
        logger.warning(f"Could not count recommendations for funnel {user.user_id}: {e}")

    try:
        outcomes = await get_user_outcomes(user.user_id, limit=500)
        for o in outcomes:
            ot = o.get("outcome")
            if ot == OutcomeType.VIEWED_PLAN:
                plan_viewed_count += 1
            elif ot == OutcomeType.ATTEMPTED:
                attempted_count += 1
            elif ot == OutcomeType.PR_OPENED:
                pr_opened_count += 1
            elif ot == OutcomeType.MERGED:
                merged_count += 1

        # In a funnel, actions imply earlier steps (e.g., if you attempted, you viewed the plan)
        # We also count issues where user viewed a plan even if they later updated status to attempted
        # To reflect true progression, shown is at least as large as the total outcomes
        total_engaged = attempted_count + pr_opened_count + merged_count + plan_viewed_count
        shown_count = max(shown_count, total_engaged)
    except Exception as e:
        logger.error(f"Failed to load outcomes for funnel {user.user_id}: {e}")

    return FunnelMetricsResponse(
        shown=shown_count,
        plan_viewed=plan_viewed_count,
        attempted=attempted_count,
        pr_opened=pr_opened_count,
        merged=merged_count,
    )


@router.post("/outcomes/suggest", response_model=List[OutcomeSuggestion])
async def get_outcome_suggestions(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Scans the user's PR contributions for referenced issues that have not yet been
    recorded in MergeWise outcomes. Returns suggestions for user confirmation.
    Applies nothing automatically without confirmation.
    """
    token = await user.get_github_token()
    client = GitHubClient(token=token)

    login = None
    try:
        gh_user = await client.get_user_profile()
        if isinstance(gh_user, dict):
            login = gh_user.get("login")
    except Exception:
        pass

    if not login:
        login = user.claims.get("github_username") or user.claims.get("username")
    if not login or login == "developer":
        return []

    # Query recent PRs
    search_query = f"is:pr author:{login} -user:{login}"
    search_url = "https://api.github.com/search/issues"
    raw_items: List[Dict[str, Any]] = []

    try:
        data = await client.get(
            search_url,
            params={"q": search_query, "sort": "updated", "order": "desc", "per_page": 30},
            ttl_seconds=900,
        )
        if isinstance(data, dict):
            raw_items = data.get("items", [])
    except Exception as e:
        logger.warning(f"Failed to search PRs for outcome suggestions: {e}")
        return []

    recorded = await get_user_outcomes(user.user_id, limit=500)
    existing_outcomes: Set[Tuple[str, int]] = {
        (o.get("repo", "").lower().strip(), o.get("issue_number"))
        for o in recorded
        if o.get("repo") and isinstance(o.get("issue_number"), int)
    }

    suggestions: List[OutcomeSuggestion] = []
    seen_suggestions: Set[Tuple[str, int]] = set()

    for item in raw_items:
        repo_name = parse_repo_from_url(item.get("repository_url"), item.get("html_url"))
        if not repo_name:
            continue
        pr_number = item.get("number", 0)
        body = item.get("body") or ""
        pr_state = classify_pr_state(item)
        suggested_outcome = "merged" if pr_state == "merged" else "pr_opened"
        title = item.get("title", "")
        html_url = item.get("html_url", "")

        ref_issues = extract_referenced_issues_from_body(body)
        for issue_num in ref_issues:
            key = (repo_name.lower(), issue_num)
            if key not in existing_outcomes and key not in seen_suggestions:
                seen_suggestions.add(key)
                suggestions.append(
                    OutcomeSuggestion(
                        repo=repo_name,
                        issue_number=issue_num,
                        pr_number=pr_number,
                        pr_title=title,
                        pr_url=html_url,
                        suggested_outcome=suggested_outcome,
                    )
                )

    return suggestions

