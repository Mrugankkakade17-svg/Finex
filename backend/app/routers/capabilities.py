"""Public, read-only page availability for the FinEx application."""

from fastapi import APIRouter, Request

from app.core.responses import APIResponse

router = APIRouter(prefix="/api/v1", tags=["Capabilities"])

# Values follow the current full-sprint acceptance ledger, not mere router
# registration. A route may exist for development before its user-facing slice
# has passed full acceptance.
CAPABILITIES: dict[str, bool] = {
    "login": True,
    "onboarding": True,
    "dashboard": True,
    "risk": True,
    "portfolio": True,
    "market": False,
    "watchlist": False,
    "paper_trading": False,
    "goals": False,
    "spending": False,
    "ai_assistant": False,
    "alerts": False,
    "operations": False,
    "release": False,
}


@router.get("/capabilities", summary="List user-facing feature availability")
def get_capabilities(request: Request):
    """Return stable feature keys so the UI can hide undelivered pages."""
    return APIResponse.success(
        message="Feature availability retrieved",
        data={"capabilities": CAPABILITIES.copy()},
        correlation_id=request.state.correlation_id,
    )
