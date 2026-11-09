"""CORS policy helpers shared by the FastAPI application and tests."""

from typing import Any

from app.config.settings import AppEnv, Settings
from app.core.exceptions import CORSConfigurationError


def validate_cors_configuration(
    allowed_origins: list[str],
    allow_credentials: bool,
    app_env: AppEnv,
) -> None:
    """Reject unsafe CORS policy combinations before middleware is installed."""

    wildcard = "*" in allowed_origins
    if wildcard and allow_credentials:
        raise CORSConfigurationError(
            "Wildcard origin cannot be combined with credentialed browser requests."
        )
    if app_env in {AppEnv.UAT, AppEnv.PROD} and wildcard:
        raise CORSConfigurationError("Wildcard origin is forbidden in UAT and production.")
    if app_env in {AppEnv.UAT, AppEnv.PROD} and not allowed_origins:
        raise CORSConfigurationError(
            "At least one explicit allowed origin is required in UAT and production."
        )


def get_cors_middleware_kwargs(settings: Settings) -> dict[str, Any]:
    """Return validated Starlette CORSMiddleware configuration."""

    validate_cors_configuration(
        allowed_origins=settings.allowed_origins,
        allow_credentials=settings.allow_credentials,
        app_env=settings.app_env,
    )
    return {
        "allow_origins": settings.allowed_origins,
        "allow_credentials": settings.allow_credentials,
        "allow_methods": settings.cors_allow_methods,
        "allow_headers": settings.cors_allow_headers,
        "max_age": 600,
    }


def is_origin_allowed(origin: str, allowed_origins: list[str]) -> bool:
    """Return whether a normalized browser origin is allowed by the policy."""

    normalized = origin.strip().rstrip("/")
    if not normalized:
        return False
    return "*" in allowed_origins or normalized in {
        allowed_origin.strip().rstrip("/") for allowed_origin in allowed_origins
    }
