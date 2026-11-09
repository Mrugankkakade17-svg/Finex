import pytest
from fastapi.testclient import TestClient

from app.config.cors import is_origin_allowed
from app.config.settings import Settings
from app.core.exceptions import ConfigurationError
from app.main import create_app


def local_settings() -> Settings:
    return Settings(
        app_env="local",
        allowed_origins=["http://localhost:3000", "https://trusted.finex.example"],
        allow_credentials=True,
    )


def test_explicit_origin_is_allowed_and_unknown_origin_is_denied() -> None:
    assert is_origin_allowed("https://trusted.finex.example", ["https://trusted.finex.example"])
    assert not is_origin_allowed(
        "https://untrusted.finex.example", ["https://trusted.finex.example"]
    )


def test_settings_rejects_wildcard_with_credentials() -> None:
    with pytest.raises(ConfigurationError, match="Wildcard ALLOWED_ORIGINS"):
        Settings(allowed_origins=["*"], allow_credentials=True)


def test_preflight_allows_only_configured_origin() -> None:
    client = TestClient(create_app(local_settings()))

    allowed = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://untrusted.finex.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert denied.status_code == 400
    assert denied.headers.get("access-control-allow-origin") is None
