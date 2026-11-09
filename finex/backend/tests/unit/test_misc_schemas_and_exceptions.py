"""
Unit tests for schemas and custom exceptions.
"""

from app.exceptions.custom_exceptions import (
    AppException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.schemas.google_callback import GoogleCallbackRequest, LogoutRequest
from app.schemas.health import HealthData
from app.schemas.response import APIResponse
from app.schemas.user import UserResponse


def test_custom_exceptions():
    e1 = AppException(message="base err", error_code="ERR", status_code=500)
    assert e1.status_code == 500
    assert e1.message == "base err"

    e2 = NotFoundException()
    assert e2.status_code == 404

    e3 = BadRequestException()
    assert e3.status_code == 400

    e4 = UnauthorizedException()
    assert e4.status_code == 401

    e5 = ForbiddenException()
    assert e5.status_code == 403


def test_schemas():
    cb = GoogleCallbackRequest(id_token="mock:test@finex.com:Test")
    assert cb.id_token == "mock:test@finex.com:Test"

    lo = LogoutRequest(refresh_token="ref-123")
    assert lo.refresh_token == "ref-123"

    hd = HealthData(status="ok", service="finex", version="1.0", environment="dev")
    assert hd.status == "ok"

    resp = APIResponse(success=True, message="ok", data={"a": 1})
    assert resp.success is True
    assert resp.data == {"a": 1}

    ur = UserResponse(id=1, email="test@finex.com", name="Name")
    assert ur.id == 1
