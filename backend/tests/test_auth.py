import time
from unittest.mock import patch
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.auth.clerk import verify_clerk_token

client = TestClient(app)

# Generate an in-memory RSA keypair for testing
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()
TEST_KID = "test_clerk_key_1"


def create_test_jwt(
    sub: str = "user_test_123",
    iss: str = None,
    azp: str = None,
    exp_offset: int = 3600,
    kid: str = TEST_KID,
) -> str:
    now = int(time.time())
    actual_iss = iss if iss is not None else settings.CLERK_ISSUER
    actual_azp = azp if azp is not None else settings.CLERK_AUTHORIZED_PARTIES[0]
    payload = {
        "sub": sub,
        "iss": actual_iss,
        "azp": actual_azp,
        "iat": now,
        "exp": now + exp_offset,
        "github_username": "octocat",
    }
    return jwt.encode(
        payload,
        _private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


@pytest.fixture(autouse=True)
def mock_jwks_cache():
    """Mock the JWKS cache so tests don't make real outbound HTTP requests."""
    with patch("app.auth.clerk.fetch_jwks") as mock_fetch:
        mock_fetch.return_value = {TEST_KID: _public_key}
        yield mock_fetch


@pytest.mark.asyncio
async def test_valid_clerk_jwt():
    token = create_test_jwt()
    claims = await verify_clerk_token(token)
    assert claims["sub"] == "user_test_123"
    assert claims["github_username"] == "octocat"
    assert claims["azp"] in settings.CLERK_AUTHORIZED_PARTIES


@pytest.mark.asyncio
async def test_expired_jwt_raises_401():
    token = create_test_jwt(exp_offset=-100)  # Expired 100 seconds ago
    with pytest.raises(Exception) as excinfo:
        await verify_clerk_token(token)
    assert excinfo.value.status_code == 401
    assert "expired" in excinfo.value.detail.lower()


@pytest.mark.asyncio
async def test_invalid_azp_raises_401():
    token = create_test_jwt(azp="https://malicious-site.com")
    with pytest.raises(Exception) as excinfo:
        await verify_clerk_token(token)
    assert excinfo.value.status_code == 401
    assert "authorized party (azp)" in excinfo.value.detail


@pytest.mark.asyncio
async def test_missing_kid_raises_401():
    # Encode token without kid header
    now = int(time.time())
    token = jwt.encode(
        {"sub": "user_123", "iat": now, "exp": now + 3600},
        _private_key,
        algorithm="RS256",
    )
    with pytest.raises(Exception) as excinfo:
        await verify_clerk_token(token)
    assert excinfo.value.status_code == 401
    assert "kid" in excinfo.value.detail.lower()


def test_api_me_endpoint_success():
    token = create_test_jwt()
    with patch("app.auth.dependencies.fetch_user_github_oauth_token") as mock_token_fetch:
        mock_token_fetch.return_value = "gho_mock_token_123456789"
        response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user_test_123"
    assert data["github_username"] == "octocat"
    assert data["has_github_token"] is True
    assert data["auth_status"] == "authenticated"


def test_api_me_unauthorized_without_header():
    response = client.get("/api/me")
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]
