import logging
import re
import sys

# Regex patterns matching sensitive tokens
GITHUB_TOKEN_REGEX = re.compile(r"(gho_[a-zA-Z0-9_]{10,}|ghp_[a-zA-Z0-9_]{10,}|github_pat_[a-zA-Z0-9_]{10,})")
BEARER_TOKEN_REGEX = re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{10,}", re.IGNORECASE)
CLERK_SECRET_REGEX = re.compile(r"(sk_(?:live|test)_[a-zA-Z0-9_]{10,})")


def sanitize_text(text: str) -> str:
    """Masks all sensitive credential tokens in a string."""
    if not isinstance(text, str):
        return text
    text = GITHUB_TOKEN_REGEX.sub("[REDACTED_GITHUB_TOKEN]", text)
    text = BEARER_TOKEN_REGEX.sub(r"\1[REDACTED_BEARER_TOKEN]", text)
    text = CLERK_SECRET_REGEX.sub("[REDACTED_CLERK_SECRET]", text)
    return text


class SensitiveDataRedactor(logging.Filter):
    """
    Logging filter that intercepts all log records and redacts GitHub OAuth tokens,
    Bearer headers, and Clerk secret keys to prevent accidental leaks.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: sanitize_text(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_text(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configures root logger with the sensitive data redaction filter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to avoid duplicates
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
        )
        root_logger.addHandler(handler)

    # Attach filter to all handlers
    redactor = SensitiveDataRedactor()
    for handler in root_logger.handlers:
        handler.addFilter(redactor)

    logger = logging.getLogger("mergewise")
    logger.addFilter(redactor)
    return logger
