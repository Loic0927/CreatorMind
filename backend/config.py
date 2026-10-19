"""Runtime configuration checks that do not expose secret values."""

import os


def csv_environment(name: str, default: str = "") -> list[str]:
    """Return a clean comma-separated environment list."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


PRODUCTION_REQUIRED_ENV = (
    "POSTBRIDGE_DATABASE_URL",
    "POSTBRIDGE_INSTAGRAM_CLIENT_ID",
    "POSTBRIDGE_INSTAGRAM_CLIENT_SECRET",
    "POSTBRIDGE_INSTAGRAM_REDIRECT_URI",
    "POSTBRIDGE_INSTAGRAM_APP_RETURN_URI",
    "POSTBRIDGE_TOKEN_ENCRYPTION_KEY",
    "POSTBRIDGE_OAUTH_STATE_SECRET",
    "POSTBRIDGE_ALLOWED_HOSTS",
    "POSTBRIDGE_CORS_ALLOWED_ORIGINS",
    "POSTBRIDGE_AUTH_SECRET",
    "POSTBRIDGE_SMTP_HOST",
    "POSTBRIDGE_EMAIL_FROM",
    "FRONTEND_BASE_URL",
)


class ConfigurationError(RuntimeError):
    """A safe configuration error containing variable names, never values."""


def is_production() -> bool:
    return os.getenv("POSTBRIDGE_ENV", "development").strip().lower() == "production"


def validate_runtime_environment() -> None:
    if not is_production():
        return
    missing = [name for name in PRODUCTION_REQUIRED_ENV if not os.getenv(name)]
    if missing:
        raise ConfigurationError(
            "Production configuration is incomplete; missing: " + ", ".join(missing)
        )
