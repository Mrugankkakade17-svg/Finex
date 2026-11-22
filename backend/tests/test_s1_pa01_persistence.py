from pathlib import Path

from app.repositories.alert_repository import AlertRepository
from app.repositories.spending_repository import SpendingRepository
from app.schemas.sprint6_ai_alerts import AlertRule


def test_spending_transactions_are_persisted_and_principal_scoped(tmp_path: Path) -> None:
    repository = SpendingRepository(tmp_path / "spending.sqlite3")

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
    assert repository.correct_category("user-b", "tx-001", "Dining") is not None


def test_alerts_are_persisted_and_principal_scoped(tmp_path: Path) -> None:
    repository = AlertRepository(tmp_path / "alerts.sqlite3")

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
    marked = repository.mark_read("user-a", notifications[0].notification_id)
    assert marked is not None
    assert marked.is_read is True

    assert repository.mark_read("user-b", notifications[0].notification_id) is not None
    assert repository.delete_rule("user-a", "rule-a") is True
    assert repository.delete_rule("user-b", "rule-a") is False
