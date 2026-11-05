import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth.dependencies import AuthenticatedUser, get_current_user
from ..services.memory import delete_all_user_data

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


class DeleteDataResponse(BaseModel):
    success: bool
    message: str


@router.delete("/me/data", response_model=DeleteDataResponse)
async def delete_my_data(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Purges the authenticated user's entire document tree in Firestore,
    including outcomes, recommendations log, and profile data.
    Stores no GitHub tokens. Uid is strictly derived from verified JWT.
    """
    success = await delete_all_user_data(user.user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to purge user data from database.",
        )
    return DeleteDataResponse(
        success=True,
        message="All personal profile data, issue outcomes, and recommendations history have been permanently deleted.",
    )
