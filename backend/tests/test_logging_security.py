import io
import logging
from app.logging_config import setup_logging, SensitiveDataRedactor, sanitize_text


def test_sanitize_text_direct():
    raw_github_oauth = "Received token gho_1234567890abcdef123456 for authentication"
    sanitized = sanitize_text(raw_github_oauth)
    assert "gho_1234567890abcdef123456" not in sanitized
    assert "[REDACTED_GITHUB_TOKEN]" in sanitized

    raw_pat = "User provided PAT github_pat_11AABBCCDD1234567890_xyz"
    assert "github_pat_" not in sanitize_text(raw_pat)
    assert "[REDACTED_GITHUB_TOKEN]" in sanitize_text(raw_pat)

    raw_bearer = "Header: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.xyz123"
    sanitized_bearer = sanitize_text(raw_bearer)
    assert "eyJhbGci" not in sanitized_bearer
    assert "Bearer [REDACTED_BEARER_TOKEN]" in sanitized_bearer

    raw_clerk_secret = "Using Clerk secret sk_live_9876543210abcdef123456"
    assert "sk_live_" not in sanitize_text(raw_clerk_secret)
    assert "[REDACTED_CLERK_SECRET]" in sanitize_text(raw_clerk_secret)


def test_logging_filter_prevents_token_leakage():
    # Setup a dedicated test logger with our redactor
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(SensitiveDataRedactor())

    test_logger = logging.getLogger("test_security_logger")
    test_logger.setLevel(logging.INFO)
    test_logger.addHandler(handler)

    leak_candidate_1 = "User login successful: gho_SuperSecretGitHubToken99999"
    leak_candidate_2 = "Sending request with Bearer ghp_PersonalAccessToken88888"

    test_logger.info(leak_candidate_1)
    test_logger.warning(leak_candidate_2)

    logged_output = log_stream.getvalue()

    # Assert raw tokens are NEVER present in output
    assert "SuperSecretGitHubToken99999" not in logged_output
    assert "PersonalAccessToken88888" not in logged_output
    assert "[REDACTED_GITHUB_TOKEN]" in logged_output
