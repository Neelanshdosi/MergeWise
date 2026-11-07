import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import AuthenticatedUser, get_current_user
from ..services.github import GitHubClient
from ..agent.gemini import GeminiPlanAgent, IssuePlanRequest, IssuePlanResponse, _PLAN_CACHE
from ..services.memory import record_outcome, OutcomeType
from ..services.rate_limiter import (
    check_plan_endpoint_rate_limit,
    check_gemini_quota,
    record_gemini_call,
)

logger = logging.getLogger("mergewise.routers.plan")
router = APIRouter(prefix="/api", tags=["Plan"])


@router.post("/plan", response_model=IssuePlanResponse)
async def generate_issue_plan(
    req: IssuePlanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> IssuePlanResponse:
    """
    Generates a grounded implementation starter plan and polite claim comment
    for an open-source issue using Gemini tool-calling agent.
    Includes:
    - Strict Clerk JWT authentication
    - Distributed Firestore rate limiting (per-user minute limit, user daily cap, global daily cap)
    - Quota protection: cache hits and failed LLM calls DO NOT consume Gemini quota
    - Real maintainer responsiveness metrics
    - Cited setup and test commands
    - Strictly verified file paths
    - Realistic effort estimates (with UI override)
    - Prompt-injection security boundary
    """
    if not req.repo_full_name or "/" not in req.repo_full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repo_full_name must be in 'owner/repo' format"
        )

    user_id = current_user.user_id

    # 1. Enforce per-user endpoint rate limit (requests per minute)
    await check_plan_endpoint_rate_limit(user_id)

    # 2. Check daily Gemini quota (bypassed if issue plan is already cached in memory)
    cache_key = f"plan:{user_id}:{req.repo_full_name.lower().strip()}:{req.issue_number}"
    is_cached = (not req.force_refresh) and (cache_key in _PLAN_CACHE)
    if not is_cached:
        await check_gemini_quota(user_id)

    github_token: Optional[str] = None
    try:
        github_token = await current_user.get_github_token()
    except Exception as e:
        logger.warning(f"Could not retrieve GitHub OAuth token for {user_id}: {e}")

    gh_client = GitHubClient(token=github_token)
    agent = GeminiPlanAgent(target_repo=req.repo_full_name, gh_client=gh_client, user_id=user_id)

    plan_response = await agent.generate_plan(req)

    # 3. Only consume Gemini daily caps on actual successful LLM execution
    # (cache hits and failed LLM calls DO NOT consume Gemini quota)
    if plan_response.llm_used and not plan_response.llm_error and not plan_response.cached:
        await record_gemini_call(user_id)

    # Record viewed_plan outcome for authenticated user
    if current_user and current_user.user_id:
        asyncio.create_task(
            record_outcome(
                user_id=current_user.user_id,
                repo_full_name=req.repo_full_name,
                issue_number=req.issue_number,
                issue_title=req.title,
                outcome=OutcomeType.VIEWED_PLAN,
                labels=req.labels,
            )
        )

    return plan_response
