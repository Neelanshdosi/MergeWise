import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from mergewise_features.schemas import ViabilityRejectionReason

logger = logging.getLogger("mergewise.viability")

CLAIM_INTENT_PATTERN = re.compile(
    r"\b("
    r"i'll take this|"
    r"take this|"
    r"assigned to me|"
    r"assign to me|"
    r"assign me|"
    r"can i work on this|"
    r"can i take this|"
    r"working on (?:a|this) fix|"
    r"opening a pr|"
    r"i am working on it|"
    r"i'd like to work on this|"
    r"claim this issue|"
    r"claim this"
    r")\b",
    re.IGNORECASE,
)


class ViabilityResult(BaseModel):
    is_viable: bool
    rejection_reason: Optional[ViabilityRejectionReason] = None
    detail: str = ""


def check_issue_viability(
    issue_data: Dict[str, Any],
    comments: Optional[List[Dict[str, Any]]] = None,
    timeline_events: Optional[List[Dict[str, Any]]] = None,
    max_comment_age_days: int = 14,
) -> ViabilityResult:
    """
    Evaluates whether an open-source issue is realistically viable for a new contributor:
    1. Issue must be explicitly open.
    2. Truly unassigned (assignee is None and assignees array is empty).
    3. No linked or competing open Pull Request.
    4. No recent "I'll take this" or claim intent in comments within the last 14 days.
    """
    # 1. State check
    if issue_data.get("state") != "open":
        return ViabilityResult(
            is_viable=False,
            rejection_reason=ViabilityRejectionReason.CLOSED,
            detail="Issue is already closed.",
        )

    # 1b. Exclude if this is actually a Pull Request
    if issue_data.get("pull_request") is not None:
        return ViabilityResult(
            is_viable=False,
            rejection_reason=ViabilityRejectionReason.NOT_ELIGIBLE,
            detail="Item is a pull request, not an issue.",
        )

    # 2. Assignee check
    has_single_assignee = issue_data.get("assignee") is not None
    assignees_list = issue_data.get("assignees") or []
    if has_single_assignee or len(assignees_list) > 0:
        assigned_to = (
            issue_data.get("assignee", {}).get("login")
            if has_single_assignee
            else assignees_list[0].get("login", "someone")
        )
        return ViabilityResult(
            is_viable=False,
            rejection_reason=ViabilityRejectionReason.ALREADY_ASSIGNED,
            detail=f"Issue is already assigned to @{assigned_to}.",
        )

    # 3. Competing or Linked Pull Request check via timeline events
    if timeline_events:
        for event in timeline_events:
            event_type = event.get("event")
            # GitHub cross-referenced timeline event
            if event_type in ("cross-referenced", "connected"):
                source = event.get("source", {})
                issue_info = source.get("issue", {})
                if "pull_request" in issue_info and issue_info.get("state") == "open":
                    pr_num = issue_info.get("number", "PR")
                    return ViabilityResult(
                        is_viable=False,
                        rejection_reason=ViabilityRejectionReason.COMPETING_OPEN_PR,
                        detail=f"There is an open pull request (#{pr_num}) addressing this issue.",
                    )

    # 4. Recent Claim / Intent Comments
    if comments:
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=max_comment_age_days)

        for comment in comments:
            created_at_str = comment.get("created_at")
            if not created_at_str:
                continue
            try:
                # Parse ISO-8601 timestamp (e.g. 2026-10-25T14:32:00Z)
                comment_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except Exception:
                continue

            # Only evaluate comments within the active window
            if comment_dt >= cutoff_date:
                body = comment.get("body", "")
                user_login = comment.get("user", {}).get("login", "a contributor")
                if CLAIM_INTENT_PATTERN.search(body):
                    return ViabilityResult(
                        is_viable=False,
                        rejection_reason=ViabilityRejectionReason.CLAIMED_IN_COMMENTS,
                        detail=f"Claimed recently by @{user_login}: \"{body[:60]}...\"",
                    )

    # Passed all viability filters
    return ViabilityResult(
        is_viable=True,
        rejection_reason=None,
        detail="Verified unassigned with no active claims or competing PRs.",
    )
