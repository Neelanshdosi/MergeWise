from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = Field(default="development")
    PORT: int = Field(default=8000)

    # CORS
    FRONTEND_URL: str = Field(default="http://localhost:3000")
    ALLOWED_ORIGINS: Optional[List[str]] = None
    GITHUB_TOKEN: Optional[str] = Field(default=None, description="Optional GitHub PAT for server-side rate limits")

    # Clerk Configuration
    CLERK_SECRET_KEY: str = Field(default="sk_test_placeholder")
    CLERK_PUBLISHABLE_KEY: str = Field(default="pk_test_placeholder")
    CLERK_ISSUER: str = Field(
        default="https://clerk.placeholder.com",
        description="Clerk instance issuer URL (e.g. https://clerk.yourdomain.com or https://verb-noun-00.clerk.accounts.dev)"
    )
    CLERK_JWKS_URL: Optional[str] = Field(
        default=None,
        description="Override for JWKS URL if different from {CLERK_ISSUER}/.well-known/jwks.json"
    )
    CLERK_AUTHORIZED_PARTIES: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Authorized parties (azp claim in Clerk JWT), e.g. frontend domain"
    )

    # AI & GCP Configuration
    GEMINI_MODEL_ID: Optional[str] = Field(
        default=None,
        description="Vertex AI Gemini model identifier. Read strictly from GEMINI_MODEL_ID with no hardcoded fallback."
    )
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Optional API key for Google GenAI client if not using Vertex ADC"
    )
    GCP_PROJECT_ID: Optional[str] = Field(default=None)
    GCP_LOCATION: str = Field(default="us-central1")
    FIRESTORE_DATABASE_ID: str = Field(
        default="(default)",
        description="Firestore database ID. Must already exist — never created by the app.",
    )

    def get_gemini_model_id(self) -> str:
        if not self.GEMINI_MODEL_ID:
            raise ValueError("GEMINI_MODEL_ID environment variable is required and has no default.")
        return self.GEMINI_MODEL_ID

    def get_allowed_origins(self) -> List[str]:
        origins = [self.FRONTEND_URL.rstrip("/")]
        if self.ALLOWED_ORIGINS:
            origins.extend([o.rstrip("/") for o in self.ALLOWED_ORIGINS])
        if self.ENVIRONMENT == "development":
            for dev_origin in ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3005", "http://127.0.0.1:3005"]:
                if dev_origin not in origins:
                    origins.append(dev_origin)
        return list(set(origins))

    def get_jwks_url(self) -> str:
        if self.CLERK_JWKS_URL:
            return self.CLERK_JWKS_URL
        return f"{self.CLERK_ISSUER.rstrip('/')}/.well-known/jwks.json"

    def get_clerk_secret_key(self) -> str:
        """
        Returns Clerk secret key. Resolves from GCP Secret Manager if running
        in GCP and secret path is specified or explicitly requested.
        """
        if self.CLERK_SECRET_KEY.startswith("projects/") or self.CLERK_SECRET_KEY == "secretmanager:clerk-secret-key":
            try:
                from google.cloud import secretmanager
                sm_client = secretmanager.SecretManagerServiceClient()
                secret_name = (
                    self.CLERK_SECRET_KEY
                    if self.CLERK_SECRET_KEY.startswith("projects/")
                    else f"projects/{self.GCP_PROJECT_ID}/secrets/clerk-secret-key/versions/latest"
                )
                response = sm_client.access_secret_version(name=secret_name)
                return response.payload.data.decode("UTF-8").strip()
            except Exception as e:
                import logging
                logging.getLogger("mergewise.config").error(f"Failed to fetch secret from Secret Manager: {e}")
        return self.CLERK_SECRET_KEY


settings = Settings()
