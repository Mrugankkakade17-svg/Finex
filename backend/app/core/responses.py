from typing import Any, Optional

from fastapi.responses import JSONResponse

from app.schemas.envelope import (
    DataStatus,
    ErrorDetail,
    ErrorEnvelope,
    FieldError,
    Meta,
    SuccessEnvelope,
)


class APIResponse:
    """Compatibility layer that returns the FinEx v1 response envelope."""

    @staticmethod
    def success(
        message: str = "Success",
        data: Any = None,
        status_code: int = 200,
        correlation_id: str = "unknown",
        data_as_of: Optional[str] = None,
        data_status: DataStatus = "LIVE",
    ):
        envelope = SuccessEnvelope(
            message=message,
            data=data,
            meta=Meta(
                correlationId=correlation_id,
                apiVersion="v1",
                dataAsOf=data_as_of,
                dataStatus=data_status,
            ),
        )

        return JSONResponse(
            status_code=status_code,
            content=envelope.model_dump(),
        )

    @staticmethod
    def error(
        message: str,
        error_code: str,
        status_code: int = 400,
        correlation_id: str = "unknown",
        field_errors: Optional[list[FieldError]] = None,
    ):
        envelope = ErrorEnvelope(
            message=message,
            error_code=error_code,
            error=ErrorDetail(
                code=error_code,
                message=message,
                fieldErrors=field_errors or [],
                correlationId=correlation_id,
            ),
        )

        content = envelope.model_dump()

        # Keep the legacy FastAPI "detail" field for
        # compatibility with existing profile/router tests.
        content["detail"] = message

        return JSONResponse(
            status_code=status_code,
            content=content,
        )
