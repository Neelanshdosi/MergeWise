from typing import Any, Dict, Optional
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from .clerk import verify_clerk_token, fetch_user_github_oauth_token


class AuthenticatedUser(BaseModel):
    user_id: str
    claims: Dict[str, Any]

    async def get_github_token(self) -> Optional[str]:
        return await fetch_user_github_oauth_token(self.user_id)


async def get_current_user(
    authorization: Optional[str] = Header(None, description="Bearer <clerk_session_jwt>")
) -> AuthenticatedUser:
    """Dependency extracting and validating Clerk JWT from Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must follow 'Bearer <token>' format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    claims = await verify_clerk_token(token)
    user_id = claims["sub"]
    return AuthenticatedUser(user_id=user_id, claims=claims)


async def get_current_user_optional(
    authorization: Optional[str] = Header(None, description="Bearer <clerk_session_jwt>")
) -> Optional[AuthenticatedUser]:
    """Optional dependency that returns AuthenticatedUser if valid token provided, else None."""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except Exception:
        return None
