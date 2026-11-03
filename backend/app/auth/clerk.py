import logging
import time
from typing import Any, Dict, List, Optional
import httpx
import jwt
from fastapi import HTTPException, status
from jwt.algorithms import RSAAlgorithm

from ..config import settings

logger = logging.getLogger("mergewise.auth")

# Cache for JWKS public keys: kid -> (public_key, expires_at)
_JWKS_CACHE: Dict[str, Any] = {}
_JWKS_CACHE_EXPIRY: float = 0.0
JWKS_CACHE_TTL_SECONDS = 3600  # 1 hour


async def fetch_jwks(force_refresh: bool = False) -> Dict[str, Any]:
    """Fetches and caches Clerk JWKS public keys."""
    global _JWKS_CACHE, _JWKS_CACHE_EXPIRY
    now = time.time()

    if not force_refresh and _JWKS_CACHE and now < _JWKS_CACHE_EXPIRY:
        return _JWKS_CACHE

    jwks_url = settings.get_jwks_url()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            jwks_data = resp.json()

        new_cache = {}
        for key_dict in jwks_data.get("keys", []):
            kid = key_dict.get("kid")
            if kid:
                new_cache[kid] = RSAAlgorithm.from_jwk(key_dict)

        _JWKS_CACHE = new_cache
        _JWKS_CACHE_EXPIRY = now + JWKS_CACHE_TTL_SECONDS
        logger.info(f"Loaded {len(_JWKS_CACHE)} public keys from Clerk JWKS.")
        return _JWKS_CACHE
    except Exception as e:
        logger.error(f"Failed to fetch Clerk JWKS from {jwks_url}: {e}")
        if _JWKS_CACHE:
            logger.warning("Falling back to existing in-memory JWKS cache.")
            return _JWKS_CACHE
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable (JWKS failure)",
        )


async def verify_clerk_token(token: str) -> Dict[str, Any]:
    """
    Verifies a Clerk session JWT:
    - Validates RSA signature with Clerk JWKS
    - Validates expiration (exp)
    - Validates issuer (iss)
    - Validates authorized party (azp)
    """
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
        )

    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed JWT header: {e}",
        )

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT header missing 'kid' claim",
        )

    jwks = await fetch_jwks()
    public_key = jwks.get(kid)

    # Try force refresh if kid not found (e.g. key rotation)
    if not public_key:
        jwks = await fetch_jwks(force_refresh=True)
        public_key = jwks.get(kid)

    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Public key matching 'kid' not found in Clerk JWKS",
        )

    # Decode and verify signature + exp
    try:
        decoded_payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {e}",
        )

    # Validate Issuer (iss)
    expected_issuer = settings.CLERK_ISSUER.rstrip("/")
    token_issuer = decoded_payload.get("iss", "").rstrip("/")
    if expected_issuer and token_issuer != expected_issuer:
        # In development or testing with placeholder issuer, log warning instead of failing if not configured
        if settings.ENVIRONMENT != "development" or expected_issuer != "https://clerk.placeholder.com":
            logger.warning(f"JWT issuer mismatch: expected '{expected_issuer}', got '{token_issuer}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer (iss)",
            )

    # Validate Authorized Party (azp)
    token_azp = decoded_payload.get("azp")
    if token_azp:
        allowed_parties = [p.rstrip("/") for p in settings.CLERK_AUTHORIZED_PARTIES]
        allowed_parties.append(settings.FRONTEND_URL.rstrip("/"))
        if token_azp.rstrip("/") not in allowed_parties:
            logger.warning(f"JWT authorized party mismatch: '{token_azp}' not in {allowed_parties}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token authorized party (azp)",
            )

    # Validate subject (user ID)
    if not decoded_payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject (sub) claim",
        )

    return decoded_payload


async def fetch_user_github_oauth_token(user_id: str) -> Optional[str]:
    """
    Retrieves the user's GitHub OAuth access token from Clerk's Backend API on demand.
    Endpoint: GET /v1/users/{user_id}/oauth_access_tokens/oauth_github
    SECURITY: The returned token MUST NEVER be persisted to a database or written to logs.
    """
    secret_key = settings.get_clerk_secret_key()
    if not secret_key or secret_key == "sk_test_placeholder":
        logger.warning(f"Clerk secret key not configured; skipping GitHub token fetch for {user_id}")
        return None

    clerk_url = f"https://api.clerk.com/v1/users/{user_id}/oauth_access_tokens/oauth_github"
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(clerk_url, headers=headers)
            if resp.status_code == 404:
                logger.info(f"No GitHub OAuth connection found for user {user_id}")
                return None
            resp.raise_for_status()
            data = resp.json()

            # Clerk returns a list of OAuthAccessToken objects
            if isinstance(data, list) and len(data) > 0:
                raw_token = data[0].get("token")
                logger.info(f"Successfully retrieved GitHub OAuth token for user {user_id} (token present)")
                return raw_token

            logger.warning(f"Unexpected data format from Clerk OAuth tokens endpoint for user {user_id}")
            return None
    except httpx.HTTPStatusError as e:
        logger.error(f"Clerk API error fetching GitHub token for {user_id}: HTTP {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error communicating with Clerk backend API for {user_id}: {e}")
        return None
