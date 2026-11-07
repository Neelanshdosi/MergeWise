"""
Phase 6: Distributed Firestore Rate Limiter
Enforces per-user and global rate limits and quotas across Cloud Run instances:
1. /api/recommendations: Per-user requests per minute (RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE)
2. /api/plan:
   - Per-user requests per minute (RATE_LIMIT_PLAN_PER_MINUTE)
   - Per-user daily Gemini quota (GEMINI_USER_DAILY_CAP)
   - Global daily Gemini quota (GEMINI_GLOBAL_DAILY_CAP)

Uses atomic Firestore transactions so counters remain consistent across scale-to-zero Cloud Run instances.
Returns HTTP 429 with clear human-readable reset messages and standard Retry-After headers.
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


async def check_recommendations_rate_limit(user_id: str) -> None:
    """
    Enforces per-user rate limit on /api/recommendations.
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
    doc_path = f"users/{user_id}/rate_limits/rec_min_{minute_str}"

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
                    "reset_at": next_min.isoformat(),
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
        # Fail open if Firestore has a transient read/write failure so user experience isn't broken
        logger.warning(f"Error checking recommendations rate limit in Firestore for {user_id}: {e}")
        return


async def check_plan_rate_limit(user_id: str) -> None:
    """
    Enforces per-user and global rate limits on /api/plan:
    1. Global daily cap across all users (GEMINI_GLOBAL_DAILY_CAP)
    2. Per-user daily cap (GEMINI_USER_DAILY_CAP)
    3. Per-user minute limit (RATE_LIMIT_PLAN_PER_MINUTE)

    Uses an atomic Firestore transaction across the 3 docs so no partial counters leak.
    Raises HTTPException(429) if any limit is exceeded.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    if not user_id:
        logger.warning("check_plan_rate_limit: missing user_id")
        return

    now = _get_utc_now()
    minute_str, next_min = _get_minute_boundary(now)
    day_str, next_day = _get_day_boundary(now)

    retry_after_min = max(1, math.ceil((next_min - now).total_seconds()))
    retry_after_day = max(1, math.ceil((next_day - now).total_seconds()))

    limit_min = settings.RATE_LIMIT_PLAN_PER_MINUTE
    limit_user_daily = settings.GEMINI_USER_DAILY_CAP
    limit_global_daily = settings.GEMINI_GLOBAL_DAILY_CAP

    doc_global_path = f"rate_limits/gemini_global_{day_str}"
    doc_user_day_path = f"users/{user_id}/rate_limits/gemini_daily_{day_str}"
    doc_user_min_path = f"users/{user_id}/rate_limits/plan_min_{minute_str}"

    try:
        client = await _get_client()
        ref_global = client.document(doc_global_path)
        ref_user_day = client.document(doc_user_day_path)
        ref_user_min = client.document(doc_user_min_path)

        @firestore.async_transactional
        async def _plan_tx(transaction):
            # Reads must all precede writes in Firestore transactions
            snap_global = await ref_global.get(transaction=transaction)
            snap_user_day = await ref_user_day.get(transaction=transaction)
            snap_user_min = await ref_user_min.get(transaction=transaction)

            count_global = snap_global.to_dict().get("count", 0) if snap_global.exists else 0
            count_user_day = snap_user_day.to_dict().get("count", 0) if snap_user_day.exists else 0
            count_user_min = snap_user_min.to_dict().get("count", 0) if snap_user_min.exists else 0

            # 1. Check Global Daily Cap
            if count_global >= limit_global_daily:
                return "global_daily", count_global

            # 2. Check User Daily Cap
            if count_user_day >= limit_user_daily:
                return "user_daily", count_user_day

            # 3. Check User Minute Limit
            if count_user_min >= limit_min:
                return "user_min", count_user_min

            # All passed — increment all 3 atomically
            now_iso = now.isoformat()
            transaction.set(
                ref_global,
                {
                    "count": count_global + 1,
                    "reset_at": next_day.isoformat(),
                    "updated_at": now_iso,
                },
                merge=True,
            )
            transaction.set(
                ref_user_day,
                {
                    "count": count_user_day + 1,
                    "user_id": user_id,
                    "reset_at": next_day.isoformat(),
                    "updated_at": now_iso,
                },
                merge=True,
            )
            transaction.set(
                ref_user_min,
                {
                    "count": count_user_min + 1,
                    "user_id": user_id,
                    "reset_at": next_min.isoformat(),
                    "updated_at": now_iso,
                },
                merge=True,
            )
            return "ok", count_user_min + 1

        transaction = client.transaction()
        result_status, current_count = await _plan_tx(transaction)

        if result_status == "global_daily":
            reset_iso = next_day.isoformat()
            logger.warning(
                f"Global Gemini daily cap reached: {current_count}/{limit_global_daily} on {day_str}. "
                f"Resets in {retry_after_day}s."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Global daily AI quota reached: MergeWise has reached its global daily cap "
                    f"of {limit_global_daily} Gemini calls. Resets at {reset_iso} (in {retry_after_day} seconds)."
                ),
                headers={"Retry-After": str(retry_after_day)},
            )

        elif result_status == "user_daily":
            reset_iso = next_day.isoformat()
            logger.warning(
                f"User {user_id} daily Gemini cap reached: {current_count}/{limit_user_daily} on {day_str}. "
                f"Resets in {retry_after_day}s."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Daily Gemini quota reached: You have reached your personal daily limit "
                    f"of {limit_user_daily} AI plan calls. Resets at {reset_iso} (in {retry_after_day} seconds)."
                ),
                headers={"Retry-After": str(retry_after_day)},
            )

        elif result_status == "user_min":
            reset_iso = next_min.isoformat()
            logger.warning(
                f"User {user_id} minute rate limit reached on plan: {current_count}/{limit_min} in {minute_str}. "
                f"Resets in {retry_after_min}s."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: You have reached the limit of {limit_min} plan requests "
                    f"per minute. Resets at {reset_iso} (in {retry_after_min} seconds)."
                ),
                headers={"Retry-After": str(retry_after_min)},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking plan rate limit in Firestore for {user_id}: {e}")
        return
