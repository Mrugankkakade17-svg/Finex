from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.core.exceptions import FinExException
from app.core.responses import APIResponse
from app.schemas.envelope import FieldError


async def finex_exception_handler(
    request: Request,
    exc: Exception,
):
    if not isinstance(exc, FinExException):
        raise exc

    return APIResponse.error(
        message=exc.message,
        error_code=exc.error_code,
        status_code=exc.status_code,
        correlation_id=request.state.correlation_id,
    )


async def http_exception_handler(
    request: Request,
    exc: Exception,
):
    if not isinstance(exc, HTTPException):
        raise exc

    error_code = "HTTP_ERROR"

    if exc.status_code == 401:
        error_code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        error_code = "FORBIDDEN"
    elif exc.status_code == 404:
        error_code = "NOT_FOUND"
    elif exc.status_code == 400:
        error_code = "BAD_REQUEST"

    message = exc.detail if isinstance(exc.detail, str) else "HTTP request failed"

    return APIResponse.error(
        message=message,
        error_code=error_code,
        status_code=exc.status_code,
        correlation_id=request.state.correlation_id,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    field_errors: list[FieldError] = []

    for error in exc.errors():
        location = error.get("loc", [])
        field = str(location[-1]) if location else "unknown"

        error_type = error.get("type", "")

        if error_type == "value_error.email":
            code = "INVALID_FORMAT"
        elif error_type == "missing":
            code = "REQUIRED"
        elif error_type == "string_too_short":
            code = "TOO_SHORT"
        elif error_type == "string_too_long":
            code = "TOO_LONG"
        elif error_type == "int_parsing":
            code = "INVALID_FORMAT"
        else:
            code = "INVALID_FORMAT"

        field_errors.append(
            FieldError(
                field=field,
                code=code,
            )
        )

    return APIResponse.error(
        message="Request validation failed",
        error_code="VALIDATION_ERROR",
        status_code=422,
        correlation_id=request.state.correlation_id,
        field_errors=field_errors,
    )
