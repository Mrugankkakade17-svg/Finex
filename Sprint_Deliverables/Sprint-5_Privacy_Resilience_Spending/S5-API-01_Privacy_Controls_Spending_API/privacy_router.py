"""
Router for Sprint 5: Privacy Controls, Consent Review, Data Export & Deletion Requests.
Enforces non-destructive audit history and explicit confirmation.
"""

from typing import Dict, List
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from app.core.responses import APIResponse
from app.schemas.sprint5_privacy_spending import (
    PrivacyActionRequest,
    PrivacyActionResponse,
    ConsentAuditRecord,
)

router = APIRouter(prefix="/api/v1/privacy", tags=["Sprint 5 - Privacy Controls"])

_audit_history: List[ConsentAuditRecord] = [
    ConsentAuditRecord(
        consent_version="v1.0",
        granted_at="2026-09-01T10:00:00Z",
        is_active=True,
    )
]

_privacy_requests: Dict[str, PrivacyActionResponse] = {}


@router.get("/consent", summary="Review current consent status and audit history")
def get_consent_status(request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    return APIResponse.success(
        message="Consent status retrieved",
        data={
            "current_consent_version": "v1.0",
            "is_consent_active": any(c.is_active for c in _audit_history),
            "audit_history": [c.model_dump() for c in _audit_history],
        },
        correlation_id=correlation_id,
    )


@router.post("/action", summary="Submit privacy action: EXPORT, DELETE, or REVOKE_CONSENT")
def handle_privacy_action(action_req: PrivacyActionRequest, request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))

    if not action_req.confirm_explicit:
        raise HTTPException(
            status_code=400,
            detail="Explicit user confirmation is mandatory for privacy lifecycle actions.",
        )

    req_id = f"priv-{uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    if action_req.action == "REVOKE_CONSENT":
        for rec in _audit_history:
            if rec.is_active:
                rec.is_active = False
                rec.revoked_at = now_iso
        msg = "Consent successfully revoked. Data collection paused."
        url = None
    elif action_req.action == "EXPORT":
        msg = "Data export bundle queued. Ready for secure download."
        url = f"/api/v1/privacy/export-bundle/{req_id}.json"
    else:  # DELETE
        msg = "Controlled account erasure requested. Retained under auditable quarantine per compliance rules."
        url = None

    response_data = PrivacyActionResponse(
        request_id=req_id,
        action=action_req.action,
        status="COMPLETED",
        requested_at=now_iso,
        message=msg,
        download_url=url,
    )
    _privacy_requests[req_id] = response_data

    return APIResponse.success(
        message="Privacy action recorded",
        data=response_data.model_dump(),
        correlation_id=correlation_id,
    )
