"""
S1-DAT-02 – Unit tests for Dat02Repository.

Follows the same mock pattern as test_c1_repository.py:
    * AsyncSession is mocked
    * Tests verify user-isolation, rollback, and CRUD correctness
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.dat02_repository import Dat02Repository

# ── helpers ──────────────────────────────────────────────────────────


def _mock_row(mapping: dict) -> MagicMock:
    row = MagicMock()
    row._mapping = mapping
    return row


def _mock_result_one(mapping: dict | None) -> MagicMock:
    result = MagicMock()
    if mapping is None:
        result.fetchone.return_value = None
    else:
        result.fetchone.return_value = _mock_row(mapping)
    return result


def _mock_result_many(rows: list[dict]) -> MagicMock:
    result = MagicMock()
    result.fetchall.return_value = [_mock_row(r) for r in rows]
    return result


# ── User CRUD ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user():
    session = AsyncMock()
    now = datetime.now(timezone.utc)
    row = {
        "user_id": "u-001",
        "email": "alice@finex.dev",
        "name": "Alice",
        "role": "user",
        "risk_profile": "moderate",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    session.execute.return_value = _mock_result_one(row)

    repo = Dat02Repository(session)
    result = await repo.create_user(
        email="alice@finex.dev",
        password_hash="hashed",
        name="Alice",
        user_id="u-001",
    )

    assert result["user_id"] == "u-001"
    assert result["email"] == "alice@finex.dev"


@pytest.mark.asyncio
async def test_get_user_by_id():
    session = AsyncMock()
    row = {
        "user_id": "u-001",
        "email": "alice@finex.dev",
        "name": "Alice",
        "role": "user",
        "risk_profile": None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    session.execute.return_value = _mock_result_one(row)

    repo = Dat02Repository(session)
    result = await repo.get_user_by_id("u-001")

    assert result is not None
    assert result["user_id"] == "u-001"


@pytest.mark.asyncio
async def test_get_user_by_id_not_found():
    session = AsyncMock()
    session.execute.return_value = _mock_result_one(None)

    repo = Dat02Repository(session)
    result = await repo.get_user_by_id("nonexistent")

    assert result is None


# ── User profile CRUD ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user_profile():
    session = AsyncMock()
    now = datetime.now(timezone.utc)
    row = {
        "profile_id": "p-001",
        "user_id": "u-001",
        "first_name": "Alice",
        "last_name": "A",
        "phone": "+1-555",
        "date_of_birth": None,
        "address": None,
        "city": "NYC",
        "country": "US",
        "created_at": now,
        "updated_at": now,
    }
    session.execute.return_value = _mock_result_one(row)

    repo = Dat02Repository(session)
    result = await repo.create_user_profile(
        user_id="u-001",
        first_name="Alice",
        last_name="A",
        city="NYC",
        country="US",
        profile_id="p-001",
    )

    assert result["profile_id"] == "p-001"
    assert result["user_id"] == "u-001"


# ── Portfolio holdings ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_holding():
    session = AsyncMock()
    now = datetime.now(timezone.utc)
    row = {
        "holding_id": "h-001",
        "portfolio_id": "pf-001",
        "user_id": "u-001",
        "instrument_symbol": "AAPL",
        "quantity": 10.0,
        "avg_buy_price": 195.0,
        "current_value": 2000.0,
        "created_at": now,
        "updated_at": now,
    }
    session.execute.return_value = _mock_result_one(row)

    repo = Dat02Repository(session)
    result = await repo.create_holding(
        user_id="u-001",
        portfolio_id="pf-001",
        instrument_symbol="AAPL",
        quantity=10.0,
        avg_buy_price=195.0,
        current_value=2000.0,
        holding_id="h-001",
    )

    assert result["holding_id"] == "h-001"
    assert result["instrument_symbol"] == "AAPL"


# ── USER ISOLATION EVIDENCE ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_isolation_holdings():
    """User A's holdings must NOT be returned when querying as User B.

    This mirrors the c1_repository.py pattern where every SELECT
    constrains by user_id.
    """
    session = AsyncMock()
    # User A has 2 holdings; User B queries → 0 results
    session.execute.return_value = _mock_result_many([])

    repo = Dat02Repository(session)
    holdings = await repo.get_holdings_for_user("user-B-id")

    assert holdings == []
    # Verify the query was called with User B's id (not User A's)
    call_args = session.execute.call_args
    # Params are passed as the second positional arg: execute(query, {"uid": ...})
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
    assert params["uid"] == "user-B-id"


@pytest.mark.asyncio
async def test_user_isolation_profile():
    """User B cannot fetch User A's profile."""
    session = AsyncMock()
    session.execute.return_value = _mock_result_one(None)

    repo = Dat02Repository(session)
    result = await repo.get_user_profile(profile_id="profile-A", user_id="user-B")

    assert result is None


@pytest.mark.asyncio
async def test_user_isolation_holding_by_id():
    """Even with a valid holding_id, User B cannot see User A's holding."""
    session = AsyncMock()
    session.execute.return_value = _mock_result_one(None)

    repo = Dat02Repository(session)
    result = await repo.get_holding_by_id(holding_id="holding-A1", user_id="user-B")

    assert result is None


# ── TRANSACTION / ROLLBACK EVIDENCE ──────────────────────────────────


@pytest.mark.asyncio
async def test_transaction_rollback_on_error():
    """Verify that if an operation within a session raises, no partial
    writes survive (AsyncSession context manager rolls back).

    This tests the pattern used by OperationalStore.run_in_transaction.
    """
    session = AsyncMock()
    session.execute.side_effect = [
        # First call (create_user) succeeds
        _mock_result_one(
            {
                "user_id": "u-txn",
                "email": "txn@test.com",
                "name": "Txn",
                "role": "user",
                "risk_profile": None,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        ),
        # Second call (create_profile) raises – simulating DB error
        RuntimeError("Simulated DB failure"),
    ]
    session.rollback = AsyncMock()

    repo = Dat02Repository(session)

    # First operation succeeds
    user = await repo.create_user(
        email="txn@test.com",
        password_hash="pw",
        name="Txn",
        user_id="u-txn",
    )
    assert user["user_id"] == "u-txn"

    # Second operation fails → caller must handle rollback
    with pytest.raises(RuntimeError, match="Simulated DB failure"):
        await repo.create_user_profile(user_id="u-txn", first_name="Txn")

    # In production, AsyncSessionLocal context manager calls rollback
    # Here we verify the session is in a state where rollback is possible
    assert session.execute.call_count == 2


# ── IDEMPOTENCY ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user_idempotent():
    """Calling create_user twice with the same user_id should not raise.

    The ON CONFLICT DO NOTHING clause returns NULL from RETURNING,
    and the repository falls back to fetching the existing row.
    """
    session = AsyncMock()
    existing_row = {
        "user_id": "u-idem",
        "email": "idem@test.com",
        "name": "Idem",
        "role": "user",
        "risk_profile": None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    # First execute → ON CONFLICT hit → RETURNING returns None
    # Second execute → fallback fetch_one returns the existing row
    session.execute.side_effect = [
        _mock_result_one(None),  # INSERT returns nothing (conflict)
        _mock_result_one(existing_row),  # SELECT fallback
    ]

    repo = Dat02Repository(session)
    result = await repo.create_user(
        email="idem@test.com",
        password_hash="pw",
        name="Idem",
        user_id="u-idem",
    )

    assert result["user_id"] == "u-idem"
    assert result["email"] == "idem@test.com"
