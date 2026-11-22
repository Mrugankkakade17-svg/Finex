from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.config.settings import Settings
from app.main import create_app
from app.repositories.alert_repository import AlertRepository
from app.repositories.spending_repository import SpendingRepository
from app.routers import alerts as alerts_router
from app.routers import spending as spending_router
from app.schemas.sprint6_ai_alerts import AlertRule


def test_spending_transactions_are_persisted_and_principal_scoped(tmp_path: Path) -> None:
    db_path = tmp_path / "spending.sqlite3"
    repository = SpendingRepository(db_path)
    repository.settings = Settings(app_persistence="sqlite")

    first = repository.list_transactions("user-a")
    second = repository.list_transactions("user-b")
    assert [transaction.transaction_id for transaction in first] == [
        "tx-001",
        "tx-002",
        "tx-003",
        "tx-004",
    ]
    assert [transaction.transaction_id for transaction in second] == [
        "tx-001",
        "tx-002",
        "tx-003",
        "tx-004",
    ]

    corrected = repository.correct_category("user-a", "tx-001", "Dining")
    assert corrected is not None
    assert corrected.category == "Dining"
    assert repository.correct_category("user-b", "tx-001", "Travel") is not None

    user_a_transactions = repository.list_transactions("user-a")
    user_b_transactions = repository.list_transactions("user-b")
    assert (
        next(tx for tx in user_a_transactions if tx.transaction_id == "tx-001").category == "Dining"
    )
    assert (
        next(tx for tx in user_b_transactions if tx.transaction_id == "tx-001").category == "Travel"
    )
    with repository._sqlite_connection() as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO spending_transactions (
                    user_id, transaction_id, date, description_masked,
                    amount, category, is_user_corrected
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                ("user-a", "tx-a-only", "2026-10-25", "LOCAL STORE", "12.00", "Shopping"),
            )
    assert repository.correct_category("user-b", "tx-a-only", "Travel") is None

    restarted_repository = SpendingRepository(db_path)
    restarted_repository.settings = Settings(app_persistence="sqlite")
    restarted_user_a = restarted_repository.list_transactions("user-a")
    restarted_user_b = restarted_repository.list_transactions("user-b")
    assert next(tx for tx in restarted_user_a if tx.transaction_id == "tx-001").category == "Dining"
    assert next(tx for tx in restarted_user_b if tx.transaction_id == "tx-001").category == "Travel"
    assert (
        next(tx for tx in restarted_user_a if tx.transaction_id == "tx-a-only").category
        == "Shopping"
    )
    assert all(tx.transaction_id != "tx-a-only" for tx in restarted_user_b)


def test_alerts_are_persisted_and_principal_scoped(tmp_path: Path) -> None:
    db_path = tmp_path / "alerts.sqlite3"
    repository = AlertRepository(db_path)
    repository.settings = Settings(app_persistence="sqlite")

    created = repository.create_rule(
        "user-a",
        AlertRule(
            rule_id="rule-a",
            rule_name="Test alert",
            condition_type="PRICE_THRESHOLD",
            target_symbol_or_goal="AAPL",
            comparison_operator="GT",
            threshold_value=250.0,
            cooldown_minutes=60,
            is_active=True,
            created_at="2026-10-01T12:00:00Z",
        ),
    )
    assert created.rule_id == "rule-a"
    assert any(rule.rule_id == "rule-a" for rule in repository.list_rules("user-a"))
    assert all(rule.rule_id != "rule-a" for rule in repository.list_rules("user-b"))

    notifications = repository.list_notifications("user-a")
    assert notifications
    exclusive_notification_id = "notif-user-a-only"
    with repository._sqlite_connection() as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO alerts (
                    user_id, notification_id, rule_id, title, body,
                    severity, created_at, is_read
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    "user-a",
                    exclusive_notification_id,
                    "rule-a",
                    "User A only",
                    "Private notification",
                    "INFO",
                    "2026-10-02T12:00:00Z",
                ),
            )

    marked = repository.mark_read("user-a", exclusive_notification_id)
    assert marked is not None
    assert marked.is_read is True
    assert repository.mark_read("user-b", exclusive_notification_id) is None

    restarted_repository = AlertRepository(db_path)
    restarted_repository.settings = Settings(app_persistence="sqlite")
    assert any(rule.rule_id == "rule-a" for rule in restarted_repository.list_rules("user-a"))
    assert all(rule.rule_id != "rule-a" for rule in restarted_repository.list_rules("user-b"))
    restarted_notifications = restarted_repository.list_notifications("user-a")
    persisted_notification = next(
        item
        for item in restarted_notifications
        if item.notification_id == exclusive_notification_id
    )
    assert persisted_notification.is_read is True
    assert restarted_repository.mark_read("user-b", exclusive_notification_id) is None

    assert repository.delete_rule("user-a", "rule-a") is True
    assert repository.delete_rule("user-b", "rule-a") is False


@pytest.fixture
def authenticated_pa01_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[TestClient, SpendingRepository], None, None]:
    db_path = tmp_path / "authenticated-routes.sqlite3"
    spending_repository = SpendingRepository(db_path)
    spending_repository.settings = Settings(app_persistence="sqlite")
    alert_repository = AlertRepository(db_path)
    alert_repository.settings = Settings(app_persistence="sqlite")
    monkeypatch.setattr(spending_router, "spending_repository", spending_repository)
    monkeypatch.setattr(alerts_router, "alert_repository", alert_repository)

    application = create_app(Settings(app_persistence="sqlite", local_db_path=db_path))
    with TestClient(application) as client:
        yield client, spending_repository


def _authorization_headers(user_id: str) -> dict[str, str]:
    token = create_access_token({"sub": user_id, "user_id": user_id})
    return {"Authorization": f"Bearer {token}"}


def test_authenticated_spending_and_alert_routes_are_principal_scoped(
    authenticated_pa01_client: tuple[TestClient, SpendingRepository],
) -> None:
    client, spending_repository = authenticated_pa01_client
    user_a_headers = _authorization_headers("route-user-a")
    user_b_headers = _authorization_headers("route-user-b")

    spending_response = client.get("/api/v1/spending/transactions", headers=user_a_headers)
    assert spending_response.status_code == 200
    spending_payload = spending_response.json()
    assert spending_payload["success"] is True
    assert len(spending_payload["data"]) == 4
    assert spending_payload["meta"]["apiVersion"] == "v1"

    correction_response = client.post(
        "/api/v1/spending/correct-category",
        headers=user_a_headers,
        json={"transaction_id": "tx-001", "corrected_category": "Dining"},
    )
    assert correction_response.status_code == 200
    assert correction_response.json()["data"]["category"] == "Dining"

    spending_repository.list_transactions("route-user-a")
    with spending_repository._sqlite_connection() as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO spending_transactions (
                    user_id, transaction_id, date, description_masked,
                    amount, category, is_user_corrected
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    "route-user-a",
                    "tx-a-only",
                    "2026-10-25",
                    "LOCAL STORE",
                    "12.00",
                    "Shopping",
                ),
            )
    cross_user_correction = client.post(
        "/api/v1/spending/correct-category",
        headers=user_b_headers,
        json={"transaction_id": "tx-a-only", "corrected_category": "Travel"},
    )
    assert cross_user_correction.status_code == 404

    rules_response = client.get("/api/v1/alerts/rules", headers=user_a_headers)
    assert rules_response.status_code == 200
    rules_payload = rules_response.json()
    assert rules_payload["success"] is True
    assert rules_payload["meta"]["apiVersion"] == "v1"

    create_rule_response = client.post(
        "/api/v1/alerts/rules",
        headers=user_a_headers,
        json={
            "rule_name": "Route isolation test",
            "condition_type": "PRICE_THRESHOLD",
            "target_symbol_or_goal": "MSFT",
            "comparison_operator": "GT",
            "threshold_value": 400.0,
            "cooldown_minutes": 60,
        },
    )
    assert create_rule_response.status_code == 200
    created_rule_id = create_rule_response.json()["data"]["rule_id"]

    cross_user_delete = client.delete(
        f"/api/v1/alerts/rules/{created_rule_id}", headers=user_b_headers
    )
    assert cross_user_delete.status_code == 404
    user_a_rules = client.get("/api/v1/alerts/rules", headers=user_a_headers)
    assert user_a_rules.status_code == 200
    assert any(rule["rule_id"] == created_rule_id for rule in user_a_rules.json()["data"])
