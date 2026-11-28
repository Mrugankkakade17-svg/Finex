"""Cash-flow service integration with persistent principal-scoped transactions."""

from decimal import Decimal
from pathlib import Path

import pytest

from app.config.settings import Settings
from app.repositories.spending_repository import SpendingRepository
from app.services.cashflow_service import get_cash_flow


def test_cash_flow_reads_only_the_requested_users_transactions(tmp_path: Path) -> None:
    repository = SpendingRepository(tmp_path / "cashflow.sqlite3")
    repository.settings = Settings(app_persistence="sqlite")
    repository.list_transactions("owner-a")
    repository.list_transactions("owner-b")
    with repository._sqlite_connection() as connection, connection:
        connection.execute(
            """
            INSERT INTO spending_transactions (
                user_id, transaction_id, date, description_masked,
                amount, category, is_user_corrected
            ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                "owner-a",
                "owner-a-income",
                "2026-10-25",
                "ACME PAYROLL",
                "500.00",
                "Income",
            ),
        )

    owner_a = get_cash_flow("owner-a", "2026-10-01", "2026-10-31", repository=repository)
    owner_b = get_cash_flow("owner-b", "2026-10-01", "2026-10-31", repository=repository)

    assert owner_a.income_total == Decimal("500.00")
    assert owner_a.transaction_count == 5
    assert owner_b.income_total == Decimal("0.00")
    assert owner_b.transaction_count == 4
    with pytest.raises(ValueError, match="user_id"):
        get_cash_flow(" ", "2026-10-01", "2026-10-31", repository=repository)
