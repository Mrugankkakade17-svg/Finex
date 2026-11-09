"""
Standard API response envelope for FinEx.

Every endpoint in this codebase must return one of:
- SuccessEnvelope: for 2xx responses
- ErrorEnvelope: for 4xx/5xx responses

This is the single shared contract the frontend (React + Flutter) teams
code against. Do not invent a different response shape in a router.
"""

from datetime import datetime, timezone
from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

# TypeVar lets Meta/SuccessEnvelope wrap ANY data type (dict, list, a User, etc.)
T = TypeVar("T")

DataStatus = Literal["LIVE", "DELAYED", "END_OF_DAY", "CACHED", "UNAVAILABLE"]


class Meta(BaseModel):
    """Metadata attached to every successful response."""

    correlationId: str = Field(..., description="Unique ID for this request, used to trace logs.")
    apiVersion: str = Field(default="v1", description="API version that served this response.")
    dataAsOf: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of when the underlying data was accurate, or null.",
    )
    dataStatus: DataStatus = Field(
        default="LIVE",
        description="Freshness of the data behind this response.",
    )


class SuccessEnvelope(BaseModel, Generic[T]):
    """Standard shape for every successful (2xx) response."""

    success: bool = True
    message: str = "Success"
    data: T
    meta: Meta


class FieldError(BaseModel):
    """A single field-level validation error."""

    field: str
    code: str


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Stable machine-readable error code, e.g. USER_NOT_FOUND.")
    message: str = Field(..., description="Safe, user-readable message. Never leak internals here.")
    fieldErrors: List[FieldError] = Field(default_factory=list)
    correlationId: str


class ErrorEnvelope(BaseModel):
    """Standard shape for every failed (4xx/5xx) response."""

    success: bool = False
    message: str  # Human-readable error message
    error_code: str  # Flattened for easy client access
    error: ErrorDetail


def utc_now_iso() -> str:
    """Helper: current UTC time as ISO-8601 string, used for dataAsOf when needed."""
    return datetime.now(timezone.utc).isoformat()
