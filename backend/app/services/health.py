import asyncio
import datetime
import logging
import statistics
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from .github import GitHubClient

logger = logging.getLogger("mergewise.health")


class RepoHealthReport(BaseModel):
    repo_full_name: str
    has_contributing_guide: bool = False
    contributing_guide_path: Optional[str] = None
    pushed_at: Optional[str] = None
    days_since_last_push: Optional[int] = None
    days_since_last_push_human: str = "insufficient data"
    median_response_time_hours: Optional[float] = None
    response_time_human: str = "insufficient data"
    first_time_pr_merge_rate_pct: Optional[float] = None
    first_time_pr_merge_rate_human: str = "insufficient data"
    sampled_issues_count: int = 0
    sampled_prs_count: int = 0
    overall_badge: str = "insufficient data"
    summary: str = ""
    api_errors: Dict[str, str] = Field(default_factory=dict)


def _parse_iso(iso_str: Optional[str]) -> Optional[datetime.datetime]:
    if not iso_str:
        return None
    try:
        clean_str = iso_str.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(clean_str)
    except Exception:
        return None


async def analyze_repo_health(
    repo_full_name: str,
    gh_client: GitHubClient,
) -> RepoHealthReport:
    """
    Measures real repository responsiveness:
    - Median time to first maintainer response on the last ~20 issues/PRs.
    - Merge rate of PRs from first-time contributors.
    - CONTRIBUTING guide presence across .md, .rst, .txt, and no-extension in root, .github/, and docs/.
    - Days since last push from repo details.
    Strictly distinguishes API errors from 'insufficient data' (clean response with <2 samples).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    report = RepoHealthReport(repo_full_name=repo_full_name)

    # 1. Fetch Repository Details (Pushed At & Default Branch)
    try:
        repo_details = await gh_client.get_repo_details(repo_full_name)
        if repo_details and isinstance(repo_details, dict):
            pushed_at_str = repo_details.get("pushed_at")
            if pushed_at_str:
                report.pushed_at = pushed_at_str
                pushed_dt = _parse_iso(pushed_at_str)
                if pushed_dt:
                    days_ago = max(0, (now - pushed_dt).days)
                    report.days_since_last_push = days_ago
                    if days_ago == 0:
                        report.days_since_last_push_human = "pushed today"
                    elif days_ago == 1:
                        report.days_since_last_push_human = "pushed 1 day ago"
                    else:
                        report.days_since_last_push_human = f"pushed {days_ago} days ago"
                else:
                    report.days_since_last_push_human = "insufficient data"
            else:
                report.days_since_last_push_human = "insufficient data"
        else:
            report.api_errors["repo_details"] = "Empty or invalid response from repository details API"
            report.days_since_last_push_human = "error: empty response from repository API"
    except httpx.HTTPStatusError as hse:
        status_code = hse.response.status_code
        err_msg = f"HTTP {status_code}: {hse.response.text[:120].strip()}"
        logger.error(f"Error fetching repo details for {repo_full_name}: {err_msg}")
        report.api_errors["repo_details"] = err_msg
        report.days_since_last_push_human = f"error: {err_msg}"
    except Exception as e:
        logger.error(f"Error fetching repo details for {repo_full_name}: {e}")
        report.api_errors["repo_details"] = str(e)
        report.days_since_last_push_human = f"error: {str(e)}"

    # 2. Check CONTRIBUTING presence across .md, .rst, .txt, and no extension
    try:
        comm_profile = await gh_client.get_community_profile(repo_full_name)
        if comm_profile and isinstance(comm_profile, dict):
            files_obj = comm_profile.get("files", {}) or {}
            contrib_obj = files_obj.get("contributing")
            if contrib_obj and isinstance(contrib_obj, dict):
                report.has_contributing_guide = True
                html_url = contrib_obj.get("html_url", "")
                report.contributing_guide_path = (
                    html_url.split(f"{repo_full_name}/blob/")[-1]
                    if f"{repo_full_name}/blob/" in html_url
                    else "CONTRIBUTING.md"
                )
    except Exception as e:
        logger.debug(f"Community profile check failed for {repo_full_name}: {e}")

    if not report.has_contributing_guide:
        # Check standard locations concurrently (at most 4 paths, not 20 sequential!)
        candidate_paths = [
            "CONTRIBUTING.md",
            ".github/CONTRIBUTING.md",
            "docs/CONTRIBUTING.md",
            "docs/contributing.md",
        ]
        async def check_path(p: str):
            try:
                c = await gh_client.get_file_content(repo_full_name, p)
                return p, c
            except Exception:
                return p, None

        results = await asyncio.gather(*[check_path(p) for p in candidate_paths])
        for path, content in results:
            if content:
                report.has_contributing_guide = True
                report.contributing_guide_path = path
                break

    # 3. Analyze Issues Sample for Median Time to First Maintainer Response
    try:
        # Fetch sample of up to 50 issues and PRs
        issues_sample = await gh_client.get_recent_issues_sample(repo_full_name, limit=50)
        report.sampled_issues_count = len(issues_sample)
        repo_owner = repo_full_name.split("/")[0].strip().lower() if "/" in repo_full_name else ""

        # Candidates with comments: include both issues and pull requests
        candidates_with_comments = [
            item for item in issues_sample
            if item.get("comments", 0) > 0 and item.get("comments_url")
        ]

        async def fetch_item_response_time(item):
            item_author = str((item.get("user") or {}).get("login") or "").strip().lower()
            created_dt = _parse_iso(item.get("created_at"))
            comments_url = item.get("comments_url")
            if not created_dt or not comments_url:
                return None
            try:
                comments = await gh_client.get_issue_comments(comments_url)
                for c in comments:
                    c_user = c.get("user") or {}
                    c_author = str(c_user.get("login") or "").strip().lower()
                    c_association = str(c.get("author_association") or "").strip().upper()

                    # Any comment by OWNER, MEMBER, or COLLABORATOR (or matching repo owner)
                    is_maintainer = (
                        c_association in ("OWNER", "MEMBER", "COLLABORATOR")
                        or (repo_owner and c_author == repo_owner)
                    )
                    if c_author and c_author != item_author and is_maintainer:
                        c_created_dt = _parse_iso(c.get("created_at"))
                        if c_created_dt and c_created_dt >= created_dt:
                            return (c_created_dt - created_dt).total_seconds() / 3600.0
            except Exception as e:
                logger.debug(f"Failed fetching comments for {comments_url}: {e}")
            return None

        # Sample initial candidates (first 6)
        initial_candidates = candidates_with_comments[:6]
        sampled_times = await asyncio.gather(*[fetch_item_response_time(it) for it in initial_candidates])
        response_durations_hours = [t for t in sampled_times if t is not None]

        # If fewer than 2 samples, widen the sample across remaining candidates from the 50 issues and PRs
        if len(response_durations_hours) < 2 and len(candidates_with_comments) > 6:
            logger.debug(
                f"Only {len(response_durations_hours)} response time samples found in first 6 candidates for {repo_full_name}. "
                f"Widening sample across {min(len(candidates_with_comments) - 6, 14)} additional issues/PRs."
            )
            widened_candidates = candidates_with_comments[6:20]
            widened_times = await asyncio.gather(*[fetch_item_response_time(it) for it in widened_candidates])
            response_durations_hours.extend([t for t in widened_times if t is not None])

        logger.debug(
            f"Response time samples for {repo_full_name} ({len(response_durations_hours)} collected): "
            f"{[round(t, 2) for t in response_durations_hours]}"
        )

        if len(response_durations_hours) >= 2:
            median_hours = statistics.median(response_durations_hours)
            report.median_response_time_hours = round(median_hours, 1)
            if median_hours < 1.0:
                report.response_time_human = f"{round(median_hours * 60)} minutes"
            elif median_hours < 24.0:
                report.response_time_human = f"{round(median_hours, 1)} hours"
            else:
                days = round(median_hours / 24.0, 1)
                report.response_time_human = f"{days} days"
        else:
            report.response_time_human = "insufficient data"
    except Exception as e:
        logger.error(f"Error fetching issues sample for {repo_full_name}: {e}")
        report.api_errors["issues_sample"] = str(e)
        report.response_time_human = f"error: {str(e)}"

    # 4. Analyze Pull Requests Sample for Outside-Contributor Merge Rate
    try:
        pulls_sample = await gh_client.get_recent_pulls_sample(repo_full_name, limit=50, state="closed")
        report.sampled_prs_count = len(pulls_sample)
        repo_owner = repo_full_name.split("/")[0].strip().lower() if "/" in repo_full_name else ""

        first_time_prs = []
        for p in pulls_sample:
            pr_num = p.get("number")
            user = p.get("user") or {}
            user_type = str(user.get("type", "")).strip().lower()
            user_login = str(user.get("login", "")).strip().lower()
            author_assoc = str(p.get("author_association") or "NONE").strip().upper()

            # Confirm how merged status is determined:
            # GitHub list-pulls endpoint returns merged_at (timestamp string when merged, null otherwise).
            # A PR is merged if merged_at is not null, or if merged is True.
            merged_at_val = p.get("merged_at")
            is_merged = bool(
                (merged_at_val is not None and str(merged_at_val).strip() != "" and str(merged_at_val).lower() != "none")
                or p.get("merged") is True
            )

            # Exclude bots (user.type == 'Bot', '[bot]' in login, ends with '-bot', or association MANNEQUIN)
            is_bot = (
                user_type == "bot"
                or "[bot]" in user_login
                or user_login.endswith("-bot")
                or author_assoc == "MANNEQUIN"
            )

            # Exclude PRs by the repo owner
            is_owner = (
                (repo_owner and user_login == repo_owner)
                or author_assoc == "OWNER"
            )

            logger.debug(
                f"PR #{pr_num}: user={user_login} (type={user_type}), assoc={author_assoc}, "
                f"is_bot={is_bot}, is_owner={is_owner}, merged={is_merged}, merged_at={merged_at_val}"
            )

            if is_bot or is_owner:
                continue

            # First-time contributor author associations
            if author_assoc in ("FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"):
                first_time_prs.append((p, is_merged))

        total_ft = len(first_time_prs)
        logger.debug(
            f"Sampled first-time PR numbers and merged flags for {repo_full_name}: "
            f"{[{'pr': p.get('number'), 'merged': is_m} for p, is_m in first_time_prs]}"
        )

        if total_ft >= 5:
            merged_count = sum(1 for _, is_m in first_time_prs if is_m)
            pct = round((merged_count / total_ft) * 100.0, 1)
            report.first_time_pr_merge_rate_pct = pct
            report.first_time_pr_merge_rate_human = f"{int(pct)}% ({merged_count}/{total_ft} PRs merged)"
        else:
            report.first_time_pr_merge_rate_pct = None
            if total_ft > 0:
                report.first_time_pr_merge_rate_human = f"insufficient data ({total_ft}/5 PRs sampled)"
            else:
                report.first_time_pr_merge_rate_human = "insufficient data"
    except Exception as e:
        logger.error(f"Error fetching pulls sample for {repo_full_name}: {e}")
        report.api_errors["pulls_sample"] = str(e)
        report.first_time_pr_merge_rate_human = f"error: {str(e)}"

    # 5. Formulate Overall Badge & Summary
    has_errors = bool(report.api_errors)
    has_good_response = (
        report.median_response_time_hours is not None
        and report.median_response_time_hours <= 48.0
    )
    has_recent_push = (
        report.days_since_last_push is not None
        and report.days_since_last_push <= 30
    )
    has_good_merge_rate = (
        report.first_time_pr_merge_rate_pct is not None
        and report.first_time_pr_merge_rate_pct >= 50.0
    )

    if has_errors and report.days_since_last_push is None:
        report.overall_badge = "API Error"
        report.summary = f"GitHub API error occurred during evaluation: {', '.join(report.api_errors.values())}"
    elif has_good_response and has_recent_push and has_good_merge_rate:
        report.overall_badge = "Highly Responsive"
        report.summary = (
            f"Active repository ({report.days_since_last_push_human}) with fast maintainer replies "
            f"(median {report.response_time_human}) and high welcome rate for outside-contributor PRs "
            f"({report.first_time_pr_merge_rate_human})."
        )
    elif has_recent_push and (has_good_response or report.has_contributing_guide):
        report.overall_badge = "Active"
        guide_note = f"a contributing guide at {report.contributing_guide_path}" if report.has_contributing_guide else "community activity"
        report.summary = f"Active repository ({report.days_since_last_push_human}) with {guide_note}."
    elif report.days_since_last_push is not None and report.days_since_last_push > 90:
        report.overall_badge = "Needs Caution"
        report.summary = (
            f"Repository has had no pushes in {report.days_since_last_push} days. "
            f"Maintainer response time is {report.response_time_human}."
        )
    else:
        report.overall_badge = "Insufficient Data"
        report.summary = "Insufficient historical activity to evaluate maintainer responsiveness reliably."

    return report
