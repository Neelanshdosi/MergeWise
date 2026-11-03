import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from ..auth.dependencies import AuthenticatedUser, get_current_user
from ..services.github import GitHubClient, GitHubRateLimitError
from ..services.profiler import build_user_profile
from ..services.viability import check_issue_viability
from ..ranker.heuristic import rank_viable_issues
from mergewise_features.schemas import (
    UserSkillProfile,
    ColdStartQuestionnaire,
    IssueMetadata,
    ScoredIssueCandidate,
    ViabilityRejectionReason,
    PipelineStats,
    ResourceRateLimit,
)
from mergewise_features import DEV_DEPENDENCY_STOP_LIST, is_stopped_dependency

logger = logging.getLogger("mergewise.routers.recommendations")
router = APIRouter(prefix="/api", tags=["Recommendations"])

# In-memory caches to guarantee page never blanks
_USER_COLD_START_STORE: Dict[str, ColdStartQuestionnaire] = {}
_LAST_GOOD_PROFILE_STORE: Dict[str, UserSkillProfile] = {}
_LAST_GOOD_RECOMMENDATIONS_STORE: Dict[str, List[ScoredIssueCandidate]] = {}
_LAST_GOOD_STATS_STORE: Dict[str, PipelineStats] = {}

MAX_SEARCH_CALLS_PER_REQUEST = 8


class RecommendationsResponse(BaseModel):
    is_cold_start: bool = False
    profile: Optional[UserSkillProfile] = None
    recommendations: List[ScoredIssueCandidate] = []
    total_evaluated: int = 0
    total_viable: int = 0
    rejected_stats: Dict[str, int] = {}
    pipeline_stats: PipelineStats


@router.get("/profile", response_model=UserSkillProfile)
async def get_user_skill_profile(
    user: AuthenticatedUser = Depends(get_current_user),
    refresh: bool = Query(False, description="Force refresh bypass cache for profile"),
):
    """Fetches or builds the user's skill profile from GitHub activity."""
    token = await user.get_github_token()
    client = GitHubClient(token=token)

    username = user.claims.get("github_username") or user.claims.get("username")
    if (not username or username == "developer") and token:
        try:
            gh_user = await client.get_user_profile(force_refresh=refresh)
            if gh_user and "login" in gh_user:
                username = gh_user.get("login")
        except Exception:
            pass

    cold_start_answers = _USER_COLD_START_STORE.get(user.user_id)
    try:
        profile = await build_user_profile(client, username=username or "developer", cold_start_answers=cold_start_answers)
        _LAST_GOOD_PROFILE_STORE[user.user_id] = profile
        return profile
    except Exception as e:
        logger.warning(f"Failed to build fresh profile for {user.user_id}: {e}")
        if user.user_id in _LAST_GOOD_PROFILE_STORE:
            return _LAST_GOOD_PROFILE_STORE[user.user_id]
        return UserSkillProfile(username=username or "developer")


@router.post("/profile/cold-start", response_model=UserSkillProfile)
async def submit_cold_start(
    answers: ColdStartQuestionnaire,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Saves user cold-start preferences when GitHub activity is limited."""
    _USER_COLD_START_STORE[user.user_id] = answers
    token = await user.get_github_token()
    client = GitHubClient(token=token)
    username = user.claims.get("github_username") or user.claims.get("username")
    if (not username or username == "developer") and token:
        try:
            gh_user = await client.get_user_profile()
            if gh_user and "login" in gh_user:
                username = gh_user.get("login")
        except Exception:
            pass
    profile = await build_user_profile(client, username=username or "developer", cold_start_answers=answers)
    _LAST_GOOD_PROFILE_STORE[user.user_id] = profile
    return profile


def _pre_rank_candidate(
    item: Dict[str, Any],
    search_langs_lower: Set[str],
    top_framework: Optional[str] = None,
) -> float:
    """Fast initial scoring for candidate issue before expensive network calls."""
    score = 0.0
    labels = [l.get("name", "").lower() for l in item.get("labels", []) if isinstance(l, dict)]
    body = (item.get("body") or "").lower()
    title = (item.get("title") or "").lower()

    if any("good first issue" in l or "good-first-issue" in l for l in labels):
        score += 30.0
    if any("help wanted" in l or "help-wanted" in l for l in labels):
        score += 15.0

    for lang in search_langs_lower:
        if lang in labels or lang in body:
            score += 25.0
            break

    # Bonus if candidate text, title, or repo relates to the user's top manifest framework
    if top_framework:
        fw_clean = top_framework.lower().strip().lstrip("@").split("/")[0].replace("_", "-")
        repo_url = (item.get("repository_url") or "").lower()
        if fw_clean in body or fw_clean in title or fw_clean in repo_url:
            score += 20.0

    comments_count = item.get("comments", 0)
    if comments_count == 0:
        score += 20.0
    elif comments_count <= 2:
        score += 10.0
    elif comments_count > 10:
        score -= 15.0

    return score


@router.get("/recommendations", response_model=RecommendationsResponse)
async def get_recommended_issues(
    user: AuthenticatedUser = Depends(get_current_user),
    refresh: bool = Query(False, description="Force refresh bypass cache for issue search only"),
):
    """
    Finds and ranks 5 verified viable issues matching the user's skill profile.
    Guarantees:
    - Never blanks the page on rate limit (falls back to last good results with warning banner).
    - Capped at max 8 search queries.
    - Lazy relaxation: stops as soon as >= 5 viable issues are found.
    - Bypasses cache ONLY for search queries, preserving repo & manifest caches.
    """
    token = await user.get_github_token()
    client = GitHubClient(token=token)

    username = user.claims.get("github_username") or user.claims.get("username")
    if (not username or username == "developer") and token:
        try:
            # Keep profile cached (force_refresh=False) so issue refresh never burns Core API quota
            gh_user = await client.get_user_profile(force_refresh=False)
            if gh_user and "login" in gh_user:
                username = gh_user.get("login")
        except Exception:
            pass

    cold_start_answers = _USER_COLD_START_STORE.get(user.user_id)
    try:
        profile = await build_user_profile(client, username=username or "developer", cold_start_answers=cold_start_answers)
        _LAST_GOOD_PROFILE_STORE[user.user_id] = profile
    except Exception as e:
        logger.warning(f"Profile build fallback: {e}")
        profile = _LAST_GOOD_PROFILE_STORE.get(user.user_id) or UserSkillProfile(username=username or "developer")

    stats = PipelineStats(
        queries_run=[],
        candidates_fetched=0,
        passed_viability=0,
        rejected_by_reason={
            ViabilityRejectionReason.CLOSED.value: 0,
            ViabilityRejectionReason.ALREADY_ASSIGNED.value: 0,
            ViabilityRejectionReason.COMPETING_OPEN_PR.value: 0,
            ViabilityRejectionReason.CLAIMED_IN_COMMENTS.value: 0,
            ViabilityRejectionReason.NOT_ELIGIBLE.value: 0,
        },
        api_errors=0,
        relaxation_used=None,
        search_rate_limit=client.rate_limits["search"],
        core_rate_limit=client.rate_limits["core"],
        rate_limit_notice=None,
        calls_made=0,
    )

    if profile.is_cold_start and not profile.cold_start_answers:
        return RecommendationsResponse(
            is_cold_start=True,
            profile=profile,
            recommendations=[],
            total_evaluated=0,
            total_viable=0,
            rejected_stats=stats.rejected_by_reason,
            pipeline_stats=stats,
        )

    search_langs = list(profile.primary_languages.keys())[:3]
    if not search_langs:
        search_langs = ["Python", "JavaScript", "TypeScript"]

    labels_to_search = ['"good first issue"', '"help wanted"']
    now = datetime.now(timezone.utc)

    # Lazy relaxation stages (never all upfront!)
    relaxation_stages = [
        {"name": "Standard (90d)", "days": 90, "use_labels": True},
        {"name": "Widened date window (365d)", "days": 365, "use_labels": True},
        {"name": "All-time date window", "days": None, "use_labels": True},
        {"name": "Broadened newcomer search", "days": None, "use_labels": False},
    ]

    all_raw_candidates: List[Dict[str, Any]] = []
    seen_issue_ids: Set[int] = set()
    search_calls_count = 0
    hit_rate_limit = False

    # RULE 5: Extra domain query using user's top non-stop-list manifest framework (e.g. "bigquery")
    top_fw = next(
        (
            fw for fw in profile.frameworks
            if not is_stopped_dependency(fw)
        ),
        None
    )
    if top_fw and search_calls_count < MAX_SEARCH_CALLS_PER_REQUEST and not hit_rate_limit:
        fw_keyword = top_fw.lower().strip().lstrip("@").split("/")[0].replace("_", "-")
        if "bigquery" in fw_keyword:
            fw_keyword = "bigquery"
        elif "pyspark" in fw_keyword or "spark" in fw_keyword:
            fw_keyword = "spark"

        top_lang = search_langs[0].lower()
        date_clause_90 = f"updated:>={(now - timedelta(days=90)).strftime('%Y-%m-%d')}"
        domain_query = f'is:issue is:open no:assignee label:"good first issue" language:{top_lang} {fw_keyword} {date_clause_90}'

        stats.queries_run.append(domain_query)
        search_calls_count += 1
        stats.calls_made = search_calls_count

        logger.info(
            f"[GH-QUERY #{search_calls_count}/{MAX_SEARCH_CALLS_PER_REQUEST}] Domain Query '{domain_query}' | "
            f"Search Rem: {client.rate_limits['search'].remaining}"
        )

        try:
            items = await client.search_single_query(domain_query, limit=50, force_refresh=refresh)
            for item in items:
                item_id = item.get("id")
                if item_id and item_id not in seen_issue_ids:
                    seen_issue_ids.add(item_id)
                    all_raw_candidates.append(item)
        except GitHubRateLimitError as rle:
            logger.warning(f"Domain search rate limit: {rle.detail}")
            hit_rate_limit = True
            if len(all_raw_candidates) < 5:
                stats.rate_limit_notice = str(rle.detail)

    for stage_idx, stage in enumerate(relaxation_stages):
        if search_calls_count >= MAX_SEARCH_CALLS_PER_REQUEST or hit_rate_limit:
            break

        if stage_idx > 0 and not stats.relaxation_used:
            stats.relaxation_used = stage["name"]
            logger.info(f"Applying lazy relaxation stage {stage_idx}: {stage['name']}")

        date_clause = f"updated:>={(now - timedelta(days=stage['days'])).strftime('%Y-%m-%d')}" if stage["days"] else ""

        for lang in search_langs:
            if search_calls_count >= MAX_SEARCH_CALLS_PER_REQUEST or hit_rate_limit:
                break

            lang_clean = lang.lower()

            if stage["use_labels"]:
                for lbl in labels_to_search:
                    if search_calls_count >= MAX_SEARCH_CALLS_PER_REQUEST or hit_rate_limit:
                        break

                    q_parts = ["is:issue", "is:open", "no:assignee", f"label:{lbl}", f"language:{lang_clean}"]
                    if date_clause:
                        q_parts.append(date_clause)
                    query = " ".join(q_parts)

                    stats.queries_run.append(query)
                    search_calls_count += 1
                    stats.calls_made = search_calls_count

                    logger.info(
                        f"[GH-QUERY #{search_calls_count}/{MAX_SEARCH_CALLS_PER_REQUEST}] '{query}' | "
                        f"Search Rem: {client.rate_limits['search'].remaining} | "
                        f"Core Rem: {client.rate_limits['core'].remaining}"
                    )

                    try:
                        items = await client.search_single_query(query, limit=50, force_refresh=refresh)
                        for item in items:
                            item_id = item.get("id")
                            if item_id and item_id not in seen_issue_ids:
                                seen_issue_ids.add(item_id)
                                all_raw_candidates.append(item)
                        if len(all_raw_candidates) >= 50:
                            break
                    except GitHubRateLimitError as rle:
                        logger.warning(f"Search rate limit triggered on query: {query}: {rle.detail}")
                        hit_rate_limit = True
                        if len(all_raw_candidates) < 5:
                            stats.rate_limit_notice = str(rle.detail)
                        break
            else:
                q_parts = ["is:issue", "is:open", "no:assignee", f"language:{lang_clean}", "comments:0..3"]
                query = " ".join(q_parts)
                stats.queries_run.append(query)
                search_calls_count += 1
                stats.calls_made = search_calls_count

                logger.info(
                    f"[GH-QUERY #{search_calls_count}/{MAX_SEARCH_CALLS_PER_REQUEST}] '{query}' | "
                    f"Search Rem: {client.rate_limits['search'].remaining}"
                )

                try:
                    items = await client.search_single_query(query, limit=50, force_refresh=refresh)
                    for item in items:
                        item_id = item.get("id")
                        if item_id and item_id not in seen_issue_ids:
                            seen_issue_ids.add(item_id)
                            all_raw_candidates.append(item)
                    if len(all_raw_candidates) >= 50:
                        break
                except GitHubRateLimitError as rle:
                    logger.warning(f"Search rate limit triggered on relaxed query: {query}: {rle.detail}")
                    hit_rate_limit = True
                    if len(all_raw_candidates) < 5:
                        stats.rate_limit_notice = str(rle.detail)
                    break

        # Stop relaxation if we have accumulated at least 50 candidate issues to evaluate
        if len(all_raw_candidates) >= 50:
            break

    stats.candidates_fetched = len(all_raw_candidates)
    stats.search_rate_limit = client.rate_limits["search"]
    stats.core_rate_limit = client.rate_limits["core"]

    # --------------------------------------------------------------------------
    # FAST FILTER & PRE-RANKING (RULE 5: Limit timeline/comment calls to top 25)
    # --------------------------------------------------------------------------
    surviving_fast_candidates: List[Dict[str, Any]] = []

    for item in all_raw_candidates:
        if item.get("state") != "open":
            stats.rejected_by_reason[ViabilityRejectionReason.CLOSED.value] += 1
            continue
        if item.get("pull_request") is not None:
            stats.rejected_by_reason[ViabilityRejectionReason.NOT_ELIGIBLE.value] += 1
            continue
        if item.get("assignee") is not None or len(item.get("assignees") or []) > 0:
            stats.rejected_by_reason[ViabilityRejectionReason.ALREADY_ASSIGNED.value] += 1
            continue
        surviving_fast_candidates.append(item)

    search_langs_lower = {l.lower() for l in search_langs}
    surviving_fast_candidates.sort(
        key=lambda itm: _pre_rank_candidate(itm, search_langs_lower, top_framework=top_fw),
        reverse=True,
    )

    top_candidates_to_verify = surviving_fast_candidates[:25]
    logger.info(f"Verifying top {len(top_candidates_to_verify)} pre-ranked candidates with timeline and comments.")

    # --------------------------------------------------------------------------
    # DEEP VIABILITY CHECKS (RULE 4: API errors/timeouts do NOT count as rejections)
    # --------------------------------------------------------------------------
    viable_metadata_list: List[IssueMetadata] = []

    for item in top_candidates_to_verify:
        issue_url = item.get("url")
        comments_url = item.get("comments_url")

        comments = None
        timeline = None

        if comments_url:
            try:
                comments = await client.get_issue_comments(comments_url)
            except GitHubRateLimitError as rle:
                if len(viable_metadata_list) < 5:
                    stats.rate_limit_notice = str(rle.detail)
                stats.api_errors += 1
            except Exception as e:
                stats.api_errors += 1

        if issue_url:
            try:
                timeline = await client.get_issue_timeline(issue_url)
            except GitHubRateLimitError as rle:
                if len(viable_metadata_list) < 5:
                    stats.rate_limit_notice = str(rle.detail)
                stats.api_errors += 1
            except Exception as e:
                stats.api_errors += 1

        viability = check_issue_viability(
            issue_data=item,
            comments=comments or [],
            timeline_events=timeline or [],
        )

        if not viability.is_viable:
            reason_key = viability.rejection_reason.value if viability.rejection_reason else "OTHER"
            stats.rejected_by_reason[reason_key] = stats.rejected_by_reason.get(reason_key, 0) + 1
            logger.info(f"Issue #{item.get('number')} rejected: {viability.detail}")
            continue

        # --------------------------------------------------------------------------
        # QUALITY FILTERS (RULE B.4): drop no description, tracking/epic, inactive
        # --------------------------------------------------------------------------
        title = item.get("title", "")
        body_text = item.get("body") or ""
        clean_body = body_text.strip()
        if len(clean_body) < 20:
            stats.rejected_by_reason["NO_DESCRIPTION"] = stats.rejected_by_reason.get("NO_DESCRIPTION", 0) + 1
            logger.info(f"Issue #{item.get('number')} rejected: description too short ({len(clean_body)} chars)")
            continue

        title_lower = title.lower().strip()
        if (
            title_lower.startswith("[development]")
            or title_lower.startswith("[dev]")
            or title_lower.startswith("[wip]")
            or bool(re.search(r"\b(tracking|epic|roadmap|meta issue|umbrella)\b", title_lower))
        ):
            stats.rejected_by_reason["META_OR_TRACKING"] = stats.rejected_by_reason.get("META_OR_TRACKING", 0) + 1
            logger.info(f"Issue #{item.get('number')} rejected: tracking/epic title '{title}'")
            continue

        repo_url = item.get("repository_url", "")
        repo_parts = repo_url.split("/")
        repo_full_name = f"{repo_parts[-2]}/{repo_parts[-1]}" if len(repo_parts) >= 2 else "repo"

        # Fetch real repository metadata (cached 30 min) for stars and push recency
        repo_details = await client.get_repo_details(repo_full_name)
        stars = 0
        open_issues_count = 0
        repo_topics: List[str] = []
        days_since_push = None

        if repo_details and isinstance(repo_details, dict):
            stars = int(repo_details.get("stargazers_count", 0))
            open_issues_count = int(repo_details.get("open_issues_count", 0))
            repo_topics = repo_details.get("topics", []) or []
            pushed_at_str = repo_details.get("pushed_at")
            if pushed_at_str:
                try:
                    pushed_dt = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
                    days_since_push = max(0, (now - pushed_dt).days)
                except Exception:
                    pass

        # Quality filter: drop repos with no push in the last 90 days
        if days_since_push is not None and days_since_push > 90:
            stats.rejected_by_reason["INACTIVE_REPO"] = stats.rejected_by_reason.get("INACTIVE_REPO", 0) + 1
            logger.info(f"Issue #{item.get('number')} rejected: repo {repo_full_name} inactive ({days_since_push} days since push)")
            continue

        stats.passed_viability += 1

        labels = [lbl.get("name", "") for lbl in item.get("labels", []) if isinstance(lbl, dict)]

        issue_lang = None
        for lang in search_langs:
            if lang.lower() in [l.lower() for l in labels] or lang.lower() in body_text.lower():
                issue_lang = lang
                break
        if not issue_lang and search_langs:
            issue_lang = search_langs[0]

        # Fetch candidate repo's manifest dependencies for accurate matching (Rule 2)
        repo_frameworks = await client.get_repo_manifest_frameworks(repo_full_name, language=issue_lang)

        meta = IssueMetadata(
            issue_url=item.get("url", ""),
            repo_full_name=repo_full_name,
            issue_number=item.get("number", 0),
            title=title,
            body=body_text[:2000],
            primary_language=issue_lang,
            labels=labels,
            stars=stars,
            open_issues_count=open_issues_count,
            body_length=len(body_text),
            html_url=item.get("html_url", ""),
            repo_topics=repo_topics,
            days_since_push=days_since_push,
            repo_frameworks=repo_frameworks,
        )
        viable_metadata_list.append(meta)

    # Final ranking with shared feature extractor and repo diversity (max 2 per repo)
    ranked_recommendations = rank_viable_issues(profile, viable_metadata_list, top_k=5, max_per_repo=2)

    # RULE A: Clear rate limit notice and ensure is_limited=False when search remaining > 0
    if client.rate_limits["search"].remaining > 0:
        client.rate_limits["search"].is_limited = False
        stats.search_rate_limit = client.rate_limits["search"]
        if len(ranked_recommendations) >= 5 or len(viable_metadata_list) > 0:
            stats.rate_limit_notice = None

    # RULE 4: If empty due to rate limiting or partial run, fallback to last good results
    if not ranked_recommendations and user.user_id in _LAST_GOOD_RECOMMENDATIONS_STORE:
        logger.info(f"Using last good cached recommendations for {user.user_id}")
        ranked_recommendations = _LAST_GOOD_RECOMMENDATIONS_STORE[user.user_id]
        if not stats.rate_limit_notice:
            stats.rate_limit_notice = "Showing previously verified results while GitHub quota resets."
    elif ranked_recommendations:
        _LAST_GOOD_RECOMMENDATIONS_STORE[user.user_id] = ranked_recommendations

    _LAST_GOOD_STATS_STORE[user.user_id] = stats

    logger.info(
        f"[PIPELINE-COMPLETE] queries={len(stats.queries_run)}, fetched={stats.candidates_fetched}, "
        f"passed={stats.passed_viability}, returning={len(ranked_recommendations)}, "
        f"search_rem={stats.search_rate_limit.remaining if stats.search_rate_limit else 'N/A'}"
    )

    return RecommendationsResponse(
        is_cold_start=False,
        profile=profile,
        recommendations=ranked_recommendations,
        total_evaluated=stats.candidates_fetched,
        total_viable=len(ranked_recommendations),
        rejected_stats=stats.rejected_by_reason,
        pipeline_stats=stats,
    )
