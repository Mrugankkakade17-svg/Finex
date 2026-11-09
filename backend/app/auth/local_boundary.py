"""Shared pre-body and dependency boundary; forwarded headers are not identity."""

from ipaddress import ip_address

from fastapi import Request

from app.config.settings import AppEnv, Settings, get_settings
from app.core.exceptions import FinExException


def require_local_legacy_auth(request: Request) -> None:
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    if settings.app_env != AppEnv.LOCAL:
        raise FinExException(
            message="Historical identity compatibility APIs are available only locally.",
            error_code="LOCAL_PILOT_ONLY",
            status_code=403,
        )


def require_local_application(request: Request) -> None:
    settings: Settings = request.app.state.settings
    allowed = settings.app_env == AppEnv.LOCAL and settings.local_app_enabled
    peer = request.client.host if request.client else ""
    try:
        loopback = ip_address(peer).is_loopback
    except ValueError:
        loopback = peer == "testclient"  # In-process test transport, never a TCP address.
    origin = request.headers.get("Origin")
    if not allowed or not loopback or (origin and origin not in settings.allowed_origins):
        raise FinExException(
            message="This application requires opted-in loopback local development.",
            error_code="LOCAL_APPLICATION_ONLY",
            status_code=403,
        )
