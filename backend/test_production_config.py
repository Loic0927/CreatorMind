import pytest

from backend.config import ConfigurationError, PRODUCTION_REQUIRED_ENV, validate_runtime_environment
from backend.main import health_check
from backend.storage.instagram_repository import InstagramRepositoryError, get_instagram_repository


def _clear_production_variables(monkeypatch):
    for name in PRODUCTION_REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)


def test_production_requires_database_url(monkeypatch):
    _clear_production_variables(monkeypatch)
    monkeypatch.setenv("POSTBRIDGE_ENV", "production")

    with pytest.raises(ConfigurationError) as failure:
        validate_runtime_environment()

    assert "POSTBRIDGE_DATABASE_URL" in str(failure.value)


def test_production_requires_mobile_oauth_return_uri(monkeypatch):
    for name in PRODUCTION_REQUIRED_ENV:
        monkeypatch.setenv(name, "configured-placeholder")
    monkeypatch.setenv("POSTBRIDGE_ENV", "production")
    monkeypatch.delenv("POSTBRIDGE_INSTAGRAM_APP_RETURN_URI")

    with pytest.raises(ConfigurationError) as failure:
        validate_runtime_environment()

    assert "POSTBRIDGE_INSTAGRAM_APP_RETURN_URI" in str(failure.value)
    assert "configured-placeholder" not in str(failure.value)


def test_production_repository_never_uses_json_fallback(monkeypatch):
    monkeypatch.setenv("POSTBRIDGE_ENV", "production")
    monkeypatch.delenv("POSTBRIDGE_DATABASE_URL", raising=False)

    with pytest.raises(InstagramRepositoryError) as failure:
        get_instagram_repository()

    assert str(failure.value) == "PostBridge database configuration is required in production."


def test_configuration_error_does_not_include_environment_values(monkeypatch):
    _clear_production_variables(monkeypatch)
    monkeypatch.setenv("POSTBRIDGE_ENV", "production")
    secret = "must-not-appear-in-errors"
    monkeypatch.setenv("POSTBRIDGE_INSTAGRAM_CLIENT_SECRET", secret)

    with pytest.raises(ConfigurationError) as failure:
        validate_runtime_environment()

    assert secret not in str(failure.value)


def test_health_response_is_public_and_contains_no_configuration():
    assert health_check() == {"status": "ok"}
