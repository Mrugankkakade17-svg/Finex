"""Sprint 8 Router: Final Release, UAT Handover, and Platform Operations."""

from datetime import datetime
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status

from app.schemas.sprint8_release_handover import (
    DisasterRecoveryDrill,
    HandoverSummary,
    ReleaseManifest,
    UATSignoffRecord,
    UATSignoffRequest,
)

router = APIRouter(prefix="/api/v1/release", tags=["Sprint 8 - Release & Handover"])

# In-memory store initialized with canonical Anand Sharma pilot signoff
_SIGNOFF_STORE: List[UATSignoffRecord] = [
    UATSignoffRecord(
        signoff_id="SIG-20261109-01",
        stakeholder_name="Anand Sharma",
        role="Primary Pilot Persona (Salaried Tech Professional)",
        decision="APPROVED",
        comments="Completed end-to-end journey from onboarding to risk questionnaire, paper orders, AI chat safety checks, and spending review. UI is responsive and fast.",
        signed_at=datetime.utcnow(),
        verified=True,
    ),
    UATSignoffRecord(
        signoff_id="SIG-20261109-02",
        stakeholder_name="Priya Patel",
        role="Product Compliance & Risk Lead",
        decision="APPROVED",
        comments="AI disclaimers and privacy data export/delete guarantees verified compliant with handbook rules.",
        signed_at=datetime.utcnow(),
        verified=True,
    ),
]


@router.get("/manifest", response_model=ReleaseManifest)
async def get_release_manifest():
    """Retrieve the official Golden Master release manifest and quality gates."""
    return ReleaseManifest()


@router.get("/uat-signoffs", response_model=List[UATSignoffRecord])
async def list_uat_signoffs():
    """List all stakeholder and pilot user UAT sign-offs."""
    return _SIGNOFF_STORE


@router.post("/uat-signoffs", response_model=UATSignoffRecord, status_code=status.HTTP_201_CREATED)
async def submit_uat_signoff(payload: UATSignoffRequest):
    """Submit a stakeholder UAT verification sign-off."""
    new_record = UATSignoffRecord(
        signoff_id=f"SIG-{uuid.uuid4().hex[:8].upper()}",
        stakeholder_name=payload.stakeholder_name,
        role=payload.role,
        decision=payload.decision.upper(),
        comments=payload.comments,
        signed_at=datetime.utcnow(),
        verified=payload.checklist_verified,
    )
    _SIGNOFF_STORE.append(new_record)
    return new_record


@router.get("/dr-drill", response_model=DisasterRecoveryDrill)
async def get_disaster_recovery_drill():
    """Check recent Disaster Recovery Drill metrics (RTO/RPO)."""
    return DisasterRecoveryDrill()


@router.get("/handover", response_model=HandoverSummary)
async def get_handover_summary():
    """Full platform handover package summary with runbook references and next roadmap."""
    manifest = ReleaseManifest()
    dr = DisasterRecoveryDrill()
    runbooks = [
        {"title": "Operator Daily Health Runbook", "path": "docs/runbooks/RUNBOOK-01-DAILY-HEALTH.md"},
        {"title": "Emergency Rollback Procedure", "path": "docs/runbooks/RUNBOOK-02-EMERGENCY-ROLLBACK.md"},
        {"title": "Database Point-In-Time Restore", "path": "docs/runbooks/RUNBOOK-03-DATABASE-PITR.md"},
        {"title": "Feature Flag Kill Switch Protocols", "path": "docs/runbooks/RUNBOOK-04-FEATURE-FLAGS.md"},
    ]
    roadmap = [
        "v1.1: Live Broker API Integration (Zerodha Kite & Upstox sandboxes)",
        "v1.1: Automated Recurring SIP execution simulation",
        "v1.2: Multi-currency & Sovereign Gold Bond (SGB) tracking",
        "v1.2: Fine-tuned Local LLM via quantized Ollama service",
    ]
    return HandoverSummary(
        release=manifest,
        uat_signoffs=_SIGNOFF_STORE,
        recovery_drill=dr,
        runbook_guides=runbooks,
        next_roadmap=roadmap,
    )

