import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth.dependencies import AuthenticatedUser, get_current_user

logger = logging.getLogger("mergewise.routers.auth")
router = APIRouter(prefix="/api", tags=["Auth"])
auth_router = router


class UserProfileResponse(BaseModel):
    user_id: str
    github_username: Optional[str] = None
    has_github_token: bool = False
    authorized_party: Optional[str] = None
    issuer: Optional[str] = None
    auth_status: str = "authenticated"


@router.get("/me", response_model=UserProfileResponse)
async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Returns verified Clerk user session metadata and checks on-demand
    GitHub OAuth token availability from Clerk.
    """
    claims = user.claims
    token = await user.get_github_token()
    has_token = bool(token)

    # Extract GitHub username from Clerk claims if present
    # Clerk commonly stores this in user claims or custom session tokens
    github_username = None
    if "github_username" in claims:
        github_username = claims["github_username"]
    elif "username" in claims:
        github_username = claims["username"]

    return UserProfileResponse(
        user_id=user.user_id,
        github_username=github_username,
        has_github_token=has_token,
        authorized_party=claims.get("azp"),
        issuer=claims.get("iss"),
        auth_status="authenticated",
    )
