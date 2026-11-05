"""
Phase 4: Firestore Memory Service
Persists user skill profiles, issue outcome tracking, and recommendations telemetry to Firestore.
Reads project/database IDs exclusively from env vars:
  - GCP_PROJECT_ID
  - FIRESTORE_DATABASE_ID (default: "(default)")
Never creates any collections/databases; they must already exist.
"""
import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from google.cloud import firestore
from google.cloud.firestore import AsyncClient
from google.api_core.exceptions import GoogleAPIError, NotFound

from ..config import settings

logger = logging.getLogger("mergewise.memory")

# ---------------------------------------------------------------------------
# Outcome constants
# ---------------------------------------------------------------------------
class OutcomeType:
    ATTEMPTED = "attempted"
    PR_OPENED = "pr_opened"
    MERGED = "merged"
    SKIPPED = "skipped"
    TOO_HARD = "too_hard"
    ABANDONED = "abandoned"
    VIEWED_PLAN = "viewed_plan"

VALID_OUTCOMES = {
    OutcomeType.ATTEMPTED,
    OutcomeType.PR_OPENED,
    OutcomeType.MERGED,
    OutcomeType.SKIPPED,
    OutcomeType.TOO_HARD,
    OutcomeType.ABANDONED,
    OutcomeType.VIEWED_PLAN,
}

# Positive signals used in memory weight updates
POSITIVE_OUTCOMES = {OutcomeType.PR_OPENED, OutcomeType.MERGED, OutcomeType.ATTEMPTED}
NEGATIVE_OUTCOMES = {OutcomeType.SKIPPED, OutcomeType.TOO_HARD, OutcomeType.ABANDONED}


# ---------------------------------------------------------------------------
# Safe document ID generator
# ---------------------------------------------------------------------------
def make_outcome_doc_id(repo_full_name: str, issue_number: int) -> str:
    """
    Safely encodes repo_full_name and issue_number into a valid Firestore doc ID.
    Replaces '/' with '__' and formats as 'owner__repo__issueNumber'.
    Never contains forward slashes.
    """
    safe_repo = repo_full_name.strip().replace("/", "__")
    return f"{safe_repo}__{issue_number}"


# ---------------------------------------------------------------------------
# Firestore client singleton (lazy, one per process)
# ---------------------------------------------------------------------------
_fs_client: Optional[AsyncClient] = None
_fs_lock = asyncio.Lock()


async def _get_client() -> AsyncClient:
    """Returns the singleton async Firestore client, creating it on first call."""
    global _fs_client
    if _fs_client is not None:
        return _fs_client

    async with _fs_lock:
        if _fs_client is not None:
            return _fs_client

        project_id = settings.GCP_PROJECT_ID
        database_id = getattr(settings, "FIRESTORE_DATABASE_ID", None) or "(default)"

        if not project_id:
            raise ValueError(
                "GCP_PROJECT_ID environment variable is required for Firestore memory."
            )

        logger.info(
            f"Initializing Firestore async client: project={project_id}, database={database_id}"
        )
        _fs_client = firestore.AsyncClient(
            project=project_id,
            database=database_id,
        )
        return _fs_client


# ---------------------------------------------------------------------------
# Profile persistence
# ---------------------------------------------------------------------------

async def save_user_profile(user_id: str, profile_data: Dict[str, Any]) -> bool:
    """
    Upserts a user skill profile document.
    Collection path: users/{user_id}
    Returns True on success, False on failure (never raises).
    """
    if not user_id:
        logger.warning("save_user_profile: empty user_id, skipping.")
        return False
    try:
        client = await _get_client()
        doc_ref = client.collection("users").document(user_id)
        payload = {
            **profile_data,
            "user_id": user_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await doc_ref.set(payload, merge=True)
        logger.info(f"Saved profile for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save profile for {user_id}: {e}")
        return False


async def load_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Loads a user skill profile document.
    Returns None if not found or on error.
    """
    if not user_id:
        return None
    try:
        client = await _get_client()
        doc_ref = client.collection("users").document(user_id)
        doc = await doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            logger.info(f"Loaded profile for user {user_id} (updated_at={data.get('updated_at')})")
            return data
        logger.debug(f"No profile document found for user {user_id}")
        return None
    except NotFound:
        logger.debug(f"Profile document not found for user {user_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to load profile for {user_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# Outcome tracking
# ---------------------------------------------------------------------------

async def record_outcome(
    user_id: str,
    repo_full_name: str,
    issue_number: int,
    issue_title: str,
    outcome: str,
    pr_url: Optional[str] = None,
    effort_label: Optional[str] = None,
    primary_language: Optional[str] = None,
    labels: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> bool:
    """
    Records one user outcome for a specific issue.
    Collection path: users/{user_id}/outcomes/{owner__repo__number}
    Valid outcomes: attempted, pr_opened, merged, skipped, too_hard, abandoned, viewed_plan.
    Returns True on success, False on failure (never raises).
    """
    if not user_id:
        logger.warning("record_outcome: empty user_id, skipping.")
        return False

    if outcome not in VALID_OUTCOMES:
        logger.warning(
            f"record_outcome: invalid outcome '{outcome}' for {user_id}. "
            f"Valid values: {sorted(VALID_OUTCOMES)}"
        )
        return False

    doc_id = make_outcome_doc_id(repo_full_name, issue_number)

    try:
        client = await _get_client()
        doc_ref = (
            client.collection("users")
            .document(user_id)
            .collection("outcomes")
            .document(doc_id)
        )
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "repo_full_name": repo_full_name,
            "issue_number": issue_number,
            "issue_title": issue_title or "",
            "outcome": outcome,
            "is_positive": outcome in POSITIVE_OUTCOMES,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if pr_url:
            payload["pr_url"] = pr_url
        if effort_label:
            payload["effort_label"] = effort_label
        if primary_language:
            payload["primary_language"] = primary_language
        if labels:
            payload["labels"] = labels
        if notes:
            payload["notes"] = notes[:500]

        await doc_ref.set(payload, merge=True)
        logger.info(
            f"Recorded outcome '{outcome}' for user {user_id} on {repo_full_name}#{issue_number}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to record outcome for {user_id} / {repo_full_name}#{issue_number}: {e}"
        )
        return False


async def get_user_outcomes(
    user_id: str,
    limit: int = 200,
    outcome_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches recent outcomes for a user, ordered by recorded_at descending.
    Strictly capped at most recent 200 outcomes per request.
    Optionally filtered to a specific outcome type.
    """
    if not user_id:
        return []
    # Hard cap at 200 outcomes
    effective_limit = min(max(1, limit), 200)
    try:
        client = await _get_client()
        col_ref = (
            client.collection("users")
            .document(user_id)
            .collection("outcomes")
        )
        if outcome_filter and outcome_filter in VALID_OUTCOMES:
            query = col_ref.where("outcome", "==", outcome_filter).order_by(
                "recorded_at", direction=firestore.Query.DESCENDING
            ).limit(effective_limit)
        else:
            query = col_ref.order_by("recorded_at", direction=firestore.Query.DESCENDING).limit(effective_limit)

        docs = await query.get()
        results = [doc.to_dict() for doc in docs if doc.exists]
        return results[:200]
    except Exception as e:
        logger.error(f"Failed to load outcomes for {user_id}: {e}")
        return []


async def get_outcome_for_issue(
    user_id: str,
    repo_full_name: str,
    issue_number: int,
) -> Optional[Dict[str, Any]]:
    """
    Returns the latest recorded outcome for a specific issue, or None.
    """
    if not user_id:
        return None
    doc_id = make_outcome_doc_id(repo_full_name, issue_number)
    try:
        client = await _get_client()
        doc_ref = (
            client.collection("users")
            .document(user_id)
            .collection("outcomes")
            .document(doc_id)
        )
        doc = await doc_ref.get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error(f"Failed to load outcome for {user_id}/{repo_full_name}#{issue_number}: {e}")
        return None


async def delete_outcome(
    user_id: str,
    repo_full_name: str,
    issue_number: int,
) -> bool:
    """
    Deletes a specific outcome record. Returns True on success.
    """
    if not user_id:
        return False
    doc_id = make_outcome_doc_id(repo_full_name, issue_number)
    try:
        client = await _get_client()
        doc_ref = (
            client.collection("users")
            .document(user_id)
            .collection("outcomes")
            .document(doc_id)
        )
        await doc_ref.delete()
        logger.info(f"Deleted outcome for {user_id}/{repo_full_name}#{issue_number}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete outcome for {user_id}/{repo_full_name}#{issue_number}: {e}")
        return False


# ---------------------------------------------------------------------------
# Recommendations Logging (Phase 4 requirement 2)
# ---------------------------------------------------------------------------

async def log_shown_recommendations(
    user_id: str,
    recommendations: List[Any],
    relaxation_stage: Optional[str] = None,
) -> bool:
    """
    Logs every issue shown to users/{uid}/recommendations/{id}
    Payload contains: repo, issue_number, rank, score, score_breakdown, shown_at, relaxation_stage.
    Needed for Phase 5 offline evaluation.
    """
    if not user_id or not recommendations:
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        client = await _get_client()
        batch = client.batch()
        col_ref = client.collection("users").document(user_id).collection("recommendations")

        for rank, rec in enumerate(recommendations, start=1):
            issue = getattr(rec, "issue", None)
            if not issue:
                continue
            repo_full_name = getattr(issue, "repo_full_name", "")
            issue_number = getattr(issue, "issue_number", 0)
            doc_id = make_outcome_doc_id(repo_full_name, issue_number)
            doc_ref = col_ref.document(doc_id)

            breakdown = getattr(rec, "score_breakdown", {}) or {}
            score = float(getattr(rec, "score", 0.0))

            payload = {
                "repo": repo_full_name,
                "issue_number": issue_number,
                "rank": rank,
                "score": score,
                "score_breakdown": breakdown,
                "shown_at": now_iso,
                "relaxation_stage": relaxation_stage or "Standard (90d)",
            }
            batch.set(doc_ref, payload, merge=True)

        await batch.commit()
        logger.info(f"Logged {len(recommendations)} recommendations for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to log recommendations for {user_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# Outcome Memory & Dynamic Skill Weighting (Phase 4 requirement 3 & 4)
# ---------------------------------------------------------------------------

def calculate_time_decay(recorded_at_str: Optional[str], half_life_days: float = 60.0) -> float:
    """
    Calculates exponential time decay factor with half-life ~60 days:
    decay = 2^(-days_diff / half_life_days) = exp(-ln(2) * days_diff / half_life_days)
    Returns float in range (0.0, 1.0].
    """
    if not recorded_at_str:
        return 1.0
    try:
        clean_str = recorded_at_str.replace("Z", "+00:00")
        recorded_dt = datetime.fromisoformat(clean_str)
        now = datetime.now(timezone.utc)
        diff_days = max(0.0, (now - recorded_dt).total_seconds() / 86400.0)
        return float(math.pow(0.5, diff_days / half_life_days))
    except Exception:
        return 1.0


def derive_skill_weights_and_excluded_issues(
    outcomes: List[Dict[str, Any]]
) -> Tuple[Dict[str, float], Set[str], Optional[str]]:
    """
    Processes historical user outcomes to produce:
    1. skill_weights: Dict[str, float] clamped per feature, bounded step (+/-0.05 max), total clamp [-0.3, +0.3]
    2. excluded_issues: Set[str] of "{repo_full_name}#{issue_number}" to never re-recommend.
       - skipped, attempted, pr_opened, merged, abandoned are excluded permanently.
       - too_hard is excluded if recorded within the last 30 days.
    3. why_note: Human-readable explanation of how memory influenced the recommendations.
    """
    excluded_issues: Set[str] = set()
    now = datetime.now(timezone.utc)
    raw_weights: Dict[str, float] = {}

    # Stats for constructing natural "Why these results" note
    skipped_langs: Dict[str, int] = {}
    boosted_langs: Dict[str, int] = {}
    too_hard_count = 0

    for out in outcomes:
        repo = out.get("repo_full_name", "")
        num = out.get("issue_number", 0)
        outcome_type = out.get("outcome", "")
        recorded_str = out.get("recorded_at")
        issue_key = f"{repo}#{num}"

        # 1. Determine Exclusion
        if outcome_type in (
            OutcomeType.SKIPPED,
            OutcomeType.ATTEMPTED,
            OutcomeType.PR_OPENED,
            OutcomeType.MERGED,
            OutcomeType.ABANDONED,
        ):
            excluded_issues.add(issue_key)
        elif outcome_type == OutcomeType.TOO_HARD:
            # Hide for 30 days
            is_within_30d = True
            if recorded_str:
                try:
                    dt = datetime.fromisoformat(recorded_str.replace("Z", "+00:00"))
                    if (now - dt).total_seconds() > 30 * 86400:
                        is_within_30d = False
                except Exception:
                    pass
            if is_within_30d:
                excluded_issues.add(issue_key)

        # 2. Determine Step Size per outcome
        # Merged/pr_opened boost (+0.05), attempted boost (+0.03)
        # too_hard/abandoned lower (-0.05), skipped lowers lightly (-0.02)
        # viewed_plan is neutral (+0.01)
        base_step = 0.0
        if outcome_type == OutcomeType.MERGED:
            base_step = 0.05
        elif outcome_type == OutcomeType.PR_OPENED:
            base_step = 0.05
        elif outcome_type == OutcomeType.ATTEMPTED:
            base_step = 0.03
        elif outcome_type == OutcomeType.VIEWED_PLAN:
            base_step = 0.01
        elif outcome_type == OutcomeType.TOO_HARD:
            base_step = -0.05
            too_hard_count += 1
        elif outcome_type == OutcomeType.ABANDONED:
            base_step = -0.05
        elif outcome_type == OutcomeType.SKIPPED:
            base_step = -0.02

        if base_step == 0.0:
            continue

        decay = calculate_time_decay(recorded_str, half_life_days=60.0)
        effective_delta = base_step * decay

        # Apply to keys: lang, repo, type
        lang = out.get("primary_language")
        if lang:
            lang_key = f"lang:{lang.lower()}"
            raw_weights[lang_key] = raw_weights.get(lang_key, 0.0) + effective_delta
            if base_step < 0:
                skipped_langs[lang] = skipped_langs.get(lang, 0) + 1
            else:
                boosted_langs[lang] = boosted_langs.get(lang, 0) + 1

        if repo:
            repo_key = f"repo:{repo.lower().strip()}"
            raw_weights[repo_key] = raw_weights.get(repo_key, 0.0) + effective_delta

        labels = out.get("labels") or []
        labels_lower = [l.lower() for l in labels]
        if any("bug" in l or "defect" in l for l in labels_lower):
            raw_weights["type:bug"] = raw_weights.get("type:bug", 0.0) + effective_delta
        elif any("doc" in l or "documentation" in l for l in labels_lower):
            raw_weights["type:docs"] = raw_weights.get("type:docs", 0.0) + effective_delta
        elif any("enhancement" in l or "feature" in l for l in labels_lower):
            raw_weights["type:enhancement"] = raw_weights.get("type:enhancement", 0.0) + effective_delta

    # Clamp all weights strictly to [-0.3, +0.3]
    skill_weights = {
        k: round(max(-0.3, min(0.3, v)), 4)
        for k, v in raw_weights.items()
    }

    # 3. Formulate truthful "Why these results" note
    why_notes: List[str] = []
    if skipped_langs and boosted_langs:
        top_skip_lang, skip_cnt = max(skipped_langs.items(), key=lambda x: x[1])
        top_boost_lang, _ = max(boosted_langs.items(), key=lambda x: x[1])
        why_notes.append(f"Skipped {skip_cnt} {top_skip_lang} issues, so weighting {top_boost_lang} higher.")
    elif skipped_langs:
        top_skip_lang, skip_cnt = max(skipped_langs.items(), key=lambda x: x[1])
        why_notes.append(f"Adjusted weights: lowered {top_skip_lang} after {skip_cnt} skipped issue{'s' if skip_cnt > 1 else ''}.")
    elif boosted_langs:
        top_boost_lang, boost_cnt = max(boosted_langs.items(), key=lambda x: x[1])
        why_notes.append(f"Boosted {top_boost_lang} based on your {boost_cnt} successful engagement{'s' if boost_cnt > 1 else ''}.")

    if too_hard_count > 0:
        why_notes.append(f"Hidden {too_hard_count} issue{'s' if too_hard_count > 1 else ''} marked 'too hard' for 30 days.")

    why_note_str = " ".join(why_notes) if why_notes else None
    return skill_weights, excluded_issues, why_note_str


# ---------------------------------------------------------------------------
# Delete User Data (GDPR / Clean Purge) (Phase 4 requirement 5)
# ---------------------------------------------------------------------------

async def delete_all_user_data(user_id: str) -> bool:
    """
    Completely purges all data belonging to user_id across the Firestore database:
    - Recursively deletes all collections and subcollections rooted at users/{user_id}
    - Clears all in-memory caches (recommendations, profile, plan caches)
    Ensures zero trace remains. Never accesses or stores GitHub tokens.
    """
    if not user_id:
        return False

    try:
        # 1. Clear in-memory caches for this user
        from ..routers.recommendations import clear_user_recommendations_cache
        from ..agent.gemini import clear_user_plan_cache

        clear_user_recommendations_cache(user_id)
        clear_user_plan_cache(user_id)

        # 2. Recursive delete on Firestore document users/{user_id}
        client = await _get_client()
        user_doc_ref = client.collection("users").document(user_id)

        async def _delete_subcollections_recursive(doc_ref: Any) -> None:
            # Query all immediate subcollections
            collections = [col async for col in doc_ref.collections()]
            for col in collections:
                sub_docs = [d async for d in col.list_documents()]
                for sub_doc in sub_docs:
                    await _delete_subcollections_recursive(sub_doc)
                    await sub_doc.delete()

        # Delete any known and dynamic subcollections recursively
        await _delete_subcollections_recursive(user_doc_ref)

        # 3. Delete root user document
        await user_doc_ref.delete()
        logger.info(f"Successfully purged all Firestore data and caches for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete all user data for {user_id}: {e}")
        return False
