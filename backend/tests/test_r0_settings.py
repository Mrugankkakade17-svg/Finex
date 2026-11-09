import pytest

from app.config.settings import AppEnv, Settings
from app.core.exceptions import ConfigurationError


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "prod",
        "debug": False,
        "api_base_url": "https://api.finex.example",
        "allowed_origins": ["https://app.finex.example"],
        "secret_key": "s" * 32,
        "llm_provider": "none",
        "market_data_provider": "mock",
    }
    values.update(overrides)
    return Settings(**values)


def production_settings_without_origins(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "prod",
        "debug": False,
        "api_base_url": "https://api.finex.example",
        "secret_key": "s" * 32,
        "llm_provider": "none",
        "market_data_provider": "mock",
    }
    values.update(overrides)
    return Settings(**values)


def test_environment_alias_and_local_defaults_are_safe() -> None:
    settings = Settings(app_env="development")

    assert settings.app_env == AppEnv.DEV
    assert settings.allowed_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    assert settings.allow_credentials is True


def test_allowed_origins_accept_csv_and_json_list() -> None:
    csv_settings = Settings(allowed_origins="http://localhost:3000, https://app.finex.example/")
    json_settings = Settings(
        allowed_origins='["http://localhost:3000", "https://app.finex.example/"]'
    )

    assert csv_settings.allowed_origins[-1] == "https://app.finex.example"
    assert json_settings.allowed_origins[-1] == "https://app.finex.example"


def test_credentialed_wildcard_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="Wildcard ALLOWED_ORIGINS"):
        Settings(allowed_origins=["*"], allow_credentials=True)


def test_production_requires_https_and_explicit_secret() -> None:
    with pytest.raises(ConfigurationError, match="API_BASE_URL must use HTTPS"):
        production_settings(api_base_url="http://api.finex.example")

    with pytest.raises(ConfigurationError, match="SECRET_KEY must be explicitly configured"):
        production_settings(secret_key="short")

    with pytest.raises(ConfigurationError, match="non-placeholder value"):
        production_settings(secret_key="REPLACE_WITH_A_LOCAL_SECRET_FOR_AUTH_TESTING")


def test_production_requires_explicit_allowed_origins() -> None:
    with pytest.raises(ConfigurationError, match="ALLOWED_ORIGINS must be explicitly set"):
        production_settings_without_origins()


def test_production_rejects_debug_and_wildcard() -> None:
    with pytest.raises(ConfigurationError, match="DEBUG must be false"):
        production_settings(debug=True)

    with pytest.raises(ConfigurationError, match="Wildcard ALLOWED_ORIGINS"):
        production_settings(allowed_origins=["*"], allow_credentials=False)


def test_redacted_configuration_never_returns_secret_values() -> None:
    settings = Settings(secret_key="do-not-log", openai_api_key="do-not-log-me")

    redacted = settings.redacted_dict()

    assert redacted["secret_key"] == "[REDACTED]"
    assert redacted["openai_api_key"] == "[REDACTED]"
