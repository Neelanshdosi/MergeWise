import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import AuthenticatedUser, get_current_user_optional
from ..services.github import GitHubClient
from ..agent.gemini import GeminiPlanAgent, IssuePlanRequest, IssuePlanResponse

logger = logging.getLogger("mergewise.routers.plan")
router = APIRouter(prefix="/api", tags=["Plan"])


@router.post("/plan", response_model=IssuePlanResponse)
async def generate_issue_plan(
    req: IssuePlanRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> IssuePlanResponse:
    """
    Generates a grounded implementation starter plan and polite claim comment
    for an open-source issue using Gemini tool-calling agent.
    Includes:
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

    github_token: Optional[str] = None
    user_id = "guest"

    if current_user:
        user_id = current_user.user_id
        try:
            github_token = await current_user.get_github_token()
        except Exception as e:
            logger.warning(f"Could not retrieve GitHub OAuth token for {user_id}: {e}")

    gh_client = GitHubClient(token=github_token)
    agent = GeminiPlanAgent(target_repo=req.repo_full_name, gh_client=gh_client, user_id=user_id)

    return await agent.generate_plan(req)
