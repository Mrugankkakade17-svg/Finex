"""
Router for Sprint 6: Smart Alert Rules, Evaluation, and In-App Notifications.
In-app notification center is the authoritative record; FCM delivery is best-effort.
"""

from typing import Dict, List
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from app.core.responses import APIResponse
from app.schemas.sprint6_ai_alerts import (
    AlertRuleCreate,
    AlertRule,
    NotificationItem,
)

router = APIRouter(prefix="/api/v1/alerts", tags=["Sprint 6 - Alerts & Notifications"])

_rules_db: Dict[str, AlertRule] = {
    "rule-001": AlertRule(
        rule_id="rule-001",
        rule_name="AAPL Price Above 200",
        condition_type="PRICE_THRESHOLD",
        target_symbol_or_goal="AAPL",
        comparison_operator="GT",
        threshold_value=200.0,
        cooldown_minutes=60,
        is_active=True,
        created_at="2026-10-01T12:00:00Z",
    )
}

_notifications_db: List[NotificationItem] = [
    NotificationItem(
        notification_id="notif-001",
        rule_id="rule-001",
        title="Simulated Price Alert",
        body="AAPL crossed threshold of $195.00 (Current: $195.50).",
        severity="INFO",
        created_at=datetime.now(timezone.utc).isoformat(),
        is_read=False,
    ),
    NotificationItem(
        notification_id="notif-002",
        rule_id=None,
        title="Welcome to FinEx Simulation",
        body="Your virtual paper portfolio has been initialized with $50,000.",
        severity="INFO",
        created_at=datetime.now(timezone.utc).isoformat(),
        is_read=True,
    ),
]


@router.get("/rules", summary="List configured smart alert rules")
def list_rules(request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    return APIResponse.success(
        message="Alert rules retrieved",
        data=[r.model_dump() for r in _rules_db.values()],
        correlation_id=correlation_id,
    )


@router.post("/rules", summary="Create a new alert rule")
def create_rule(rule_in: AlertRuleCreate, request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    rule_id = f"rule-{uuid4().hex[:8]}"

    rule = AlertRule(
        rule_id=rule_id,
        rule_name=rule_in.rule_name,
        condition_type=rule_in.condition_type,
        target_symbol_or_goal=rule_in.target_symbol_or_goal,
        comparison_operator=rule_in.comparison_operator,
        threshold_value=rule_in.threshold_value,
        cooldown_minutes=rule_in.cooldown_minutes,
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _rules_db[rule_id] = rule

    return APIResponse.success(
        message="Alert rule created",
        data=rule.model_dump(),
        correlation_id=correlation_id,
    )


@router.delete("/rules/{rule_id}", summary="Delete or deactivate an alert rule")
def delete_rule(rule_id: str, request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    if rule_id not in _rules_db:
        raise HTTPException(status_code=404, detail="Alert rule not found.")
    del _rules_db[rule_id]
    return APIResponse.success(
        message="Alert rule deleted",
        data={"rule_id": rule_id, "deleted": True},
        correlation_id=correlation_id,
    )


@router.get("/notifications", summary="List in-app notifications with unread counts")
def list_notifications(request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    unread = sum(1 for n in _notifications_db if not n.is_read)
    return APIResponse.success(
        message="Notifications retrieved",
        data={
            "unread_count": unread,
            "notifications": [n.model_dump() for n in _notifications_db],
        },
        correlation_id=correlation_id,
    )


@router.post("/notifications/{notif_id}/read", summary="Mark an in-app notification as read")
def mark_read(notif_id: str, request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    for n in _notifications_db:
        if n.notification_id == notif_id:
            n.is_read = True
            return APIResponse.success(
                message="Notification marked as read",
                data=n.model_dump(),
                correlation_id=correlation_id,
            )
    raise HTTPException(status_code=404, detail="Notification not found.")

