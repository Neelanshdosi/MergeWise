"""
Phase 6: Distributed Firestore Rate Limiter
Enforces per-user and global rate limits and quotas across Cloud Run instances.

Architecture & Security:
- All rate-limit counters reside in a top-level `rate_limits` collection (NOT in `users/{uid}`).
- Excluded from user-initiated data deletion (`delete_all_user_data`) because they contain no personal data
  and prevent quota-reset evasion.
- Every counter document contains an `expires_at` timestamp field for automatic Firestore TTL deletion.
- Gemini daily caps (per-user and global) are only consumed on successful LLM calls;
  cache hits and failed LLM calls NEVER consume Gemini caps.

Limits (configurable by environment variables):
1. /api/recommendations: Per-user requests per minute (RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE)
2. /api/plan: Per-user requests per minute (RATE_LIMIT_PLAN_PER_MINUTE)
3. Gemini daily per-user quota (GEMINI_USER_DAILY_CAP)
4. Gemini daily global quota across all users (GEMINI_GLOBAL_DAILY_CAP)
"""
import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from fastapi import HTTPException, status
from google.cloud import firestore

from ..config import settings
from .memory import _get_client

logger = logging.getLogger("mergewise.rate_limiter")


def _get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_minute_boundary(dt: datetime) -> Tuple[str, datetime]:
    """Returns the minute bucket key string (YYYY-MM-DDTHH-MM) and next minute boundary datetime."""
    minute_str = dt.strftime("%Y-%m-%dT%H-%M")
    next_min = (dt + timedelta(minutes=1)).replace(second=0, microsecond=0)
    return minute_str, next_min


def _get_day_boundary(dt: datetime) -> Tuple[str, datetime]:
    """Returns the day bucket key string (YYYY-MM-DD) and next midnight UTC boundary datetime."""
    day_str = dt.strftime("%Y-%m-%d")
    next_day = (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return day_str, next_day


def _make_safe_id(val: str) -> str:
    """Replaces slashes and colons so ID is safe for Firestore top-level doc paths."""
    return val.strip().replace("/", "__").replace(":", "__")


# ---------------------------------------------------------------------------
# 1. Recommendations Endpoint Rate Limiter
# ---------------------------------------------------------------------------

async def check_recommendations_rate_limit(user_id: str) -> None:
    """
    Enforces per-user rate limit on /api/recommendations.
    Stored in top-level collection: rate_limits/rec_min__{safe_uid}__{minute_str}
    Raises HTTPException(429) if exceeded.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    if not user_id:
        logger.warning("check_recommendations_rate_limit: missing user_id")
        return

    now = _get_utc_now()
    minute_str, next_min = _get_minute_boundary(now)
    retry_after = max(1, math.ceil((next_min - now).total_seconds()))
    limit = settings.RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE

    safe_uid = _make_safe_id(user_id)
    doc_path = f"rate_limits/rec_min__{safe_uid}__{minute_str}"

    try:
        client = await _get_client()
        doc_ref = client.document(doc_path)

        @firestore.async_transactional
        async def _tx(transaction):
            snap = await doc_ref.get(transaction=transaction)
            count = 0
            if snap.exists:
                data = snap.to_dict() or {}
                count = data.get("count", 0)

            if count >= limit:
                return False, count

            new_count = count + 1
            transaction.set(
                doc_ref,
                {
                    "count": new_count,
                    "user_id": user_id,
                    "type": "recommendations_minute",
                    "reset_at": next_min.isoformat(),
                    "expires_at": next_min,  # Native datetime for Firestore TTL policy
                    "updated_at": now.isoformat(),
                },
                merge=True,
            )
            return True, new_count

        transaction = client.transaction()
        allowed, current_count = await _tx(transaction)

        if not allowed:
            reset_time_iso = next_min.isoformat()
            logger.warning(
                f"Rate limit exceeded for user {user_id} on recommendations: "
                f"{current_count}/{limit} in minute {minute_str}. Resets in {retry_after}s."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: You have reached the limit of {limit} recommendations "
                    f"requests per minute. Resets at {reset_time_iso} (in {retry_after} seconds)."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking recommendations rate limit in Firestore for {user_id}: {e}")
        return


# ---------------------------------------------------------------------------
# 2. Plan Endpoint Minute Rate Limiter
# ---------------------------------------------------------------------------

async def check_plan_endpoint_rate_limit(user_id: str) -> None:
    """
    Enforces per-user requests-per-minute limit on /api/plan.
    Stored in top-level collection: rate_limits/plan_min__{safe_uid}__{minute_str}
    Raises HTTPException(429) if exceeded.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    if not user_id:
        logger.warning("check_plan_endpoint_rate_limit: missing user_id")
        return

    now = _get_utc_now()
    minute_str, next_min = _get_minute_boundary(now)
    retry_after = max(1, math.ceil((next_min - now).total_seconds()))
    limit = settings.RATE_LIMIT_PLAN_PER_MINUTE

    safe_uid = _make_safe_id(user_id)
    doc_path = f"rate_limits/plan_min__{safe_uid}__{minute_str}"

    try:
        client = await _get_client()
        doc_ref = client.document(doc_path)

        @firestore.async_transactional
        async def _tx(transaction):
            snap = await doc_ref.get(transaction=transaction)
            count = 0
            if snap.exists:
                data = snap.to_dict() or {}
                count = data.get("count", 0)

            if count >= limit:
                return False, count

            new_count = count + 1
            transaction.set(
                doc_ref,
                {
                    "count": new_count,
                    "user_id": user_id,
                    "type": "plan_minute",
                    "reset_at": next_min.isoformat(),
                    "expires_at": next_min,  # Native datetime for Firestore TTL policy
                    "updated_at": now.isoformat(),
                },
                merge=True,
            )
            return True, new_count

        transaction = client.transaction()
        allowed, current_count = await _tx(transaction)

        if not allowed:
            reset_time_iso = next_min.isoformat()
            logger.warning(
                f"Rate limit exceeded for user {user_id} on plan: "
                f"{current_count}/{limit} in minute {minute_str}. Resets in {retry_after}s."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: You have reached the limit of {limit} plan requests "
                    f"per minute. Resets at {reset_time_iso} (in {retry_after} seconds)."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking plan endpoint rate limit in Firestore for {user_id}: {e}")
        return


# ---------------------------------------------------------------------------
# 3. Gemini Quota Pre-Flight Check (Read Only - Does NOT consume)
# ---------------------------------------------------------------------------

async def check_gemini_quota(user_id: str) -> None:
    """
    Pre-flight check verifying user daily cap and global daily cap are not exceeded.
    Read-only: DOES NOT consume or increment quota.
    Raises HTTPException(429) if either cap is reached.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    if not user_id:
        return

    now = _get_utc_now()
    day_str, next_day = _get_day_boundary(now)
    retry_after_day = max(1, math.ceil((next_day - now).total_seconds()))

    limit_user_daily = settings.GEMINI_USER_DAILY_CAP
    limit_global_daily = settings.GEMINI_GLOBAL_DAILY_CAP

    safe_uid = _make_safe_id(user_id)
    doc_global_path = f"rate_limits/gemini_global__all__{day_str}"
    doc_user_day_path = f"rate_limits/gemini_daily__{safe_uid}__{day_str}"

    try:
        client = await _get_client()
        ref_global = client.document(doc_global_path)
        ref_user_day = client.document(doc_user_day_path)

        snap_global = await ref_global.get()
        count_global = snap_global.to_dict().get("count", 0) if snap_global.exists else 0
        if count_global >= limit_global_daily:
            reset_iso = next_day.isoformat()
            logger.warning(
                f"Global Gemini daily cap reached: {count_global}/{limit_global_daily} on {day_str}."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Global daily AI quota reached: MergeWise has reached its global daily cap "
                    f"of {limit_global_daily} Gemini calls. Resets at {reset_iso} (in {retry_after_day} seconds)."
                ),
                headers={"Retry-After": str(retry_after_day)},
            )

        snap_user = await ref_user_day.get()
        count_user = snap_user.to_dict().get("count", 0) if snap_user.exists else 0
        if count_user >= limit_user_daily:
            reset_iso = next_day.isoformat()
            logger.warning(
                f"User {user_id} daily Gemini cap reached: {count_user}/{limit_user_daily} on {day_str}."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Daily Gemini quota reached: You have reached your personal daily limit "
                    f"of {limit_user_daily} AI plan calls. Resets at {reset_iso} (in {retry_after_day} seconds)."
                ),
                headers={"Retry-After": str(retry_after_day)},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking Gemini quota in Firestore for {user_id}: {e}")
        return


# ---------------------------------------------------------------------------
# 4. Gemini Quota Consumption (Called ONLY on successful LLM calls)
# ---------------------------------------------------------------------------

async def record_gemini_call(user_id: str) -> None:
    """
    Atomically increments user daily Gemini counter and global daily Gemini counter.
    MUST ONLY be called when an LLM call actually completed successfully.
    Never called on cache hits or failed LLM calls.
    """
    if not settings.RATE_LIMIT_ENABLED or not user_id:
        return

    now = _get_utc_now()
    day_str, next_day = _get_day_boundary(now)

    safe_uid = _make_safe_id(user_id)
    doc_global_path = f"rate_limits/gemini_global__all__{day_str}"
    doc_user_day_path = f"rate_limits/gemini_daily__{safe_uid}__{day_str}"

    try:
        client = await _get_client()
        ref_global = client.document(doc_global_path)
        ref_user_day = client.document(doc_user_day_path)

        @firestore.async_transactional
        async def _record_tx(transaction):
            snap_global = await ref_global.get(transaction=transaction)
            snap_user = await ref_user_day.get(transaction=transaction)

            count_global = snap_global.to_dict().get("count", 0) if snap_global.exists else 0
            count_user = snap_user.to_dict().get("count", 0) if snap_user.exists else 0

            now_iso = now.isoformat()
            transaction.set(
                ref_global,
                {
                    "count": count_global + 1,
                    "type": "gemini_global_daily",
                    "reset_at": next_day.isoformat(),
                    "expires_at": next_day,  # Native datetime for Firestore TTL policy
                    "updated_at": now_iso,
                },
                merge=True,
            )
            transaction.set(
                ref_user_day,
                {
                    "count": count_user + 1,
                    "user_id": user_id,
                    "type": "gemini_user_daily",
                    "reset_at": next_day.isoformat(),
                    "expires_at": next_day,  # Native datetime for Firestore TTL policy
                    "updated_at": now_iso,
                },
                merge=True,
            )
            return count_user + 1, count_global + 1

        transaction = client.transaction()
        u_count, g_count = await _record_tx(transaction)
        logger.info(f"Recorded Gemini call for user {user_id}: user={u_count}, global={g_count}")

    except Exception as e:
        logger.warning(f"Error recording Gemini call quota in Firestore for {user_id}: {e}")


# Backwards compatibility alias
async def check_plan_rate_limit(user_id: str) -> None:
    """Combines endpoint minute limit and pre-flight quota check."""
    await check_plan_endpoint_rate_limit(user_id)
    await check_gemini_quota(user_id)
