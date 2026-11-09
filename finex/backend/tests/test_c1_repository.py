from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.c1_repository import C1Repository


@pytest.mark.asyncio
async def test_create_portfolio():
    session = AsyncMock()

    row = {
        "portfolio_id": "portfolio-123",
        "user_id": "user-123",
        "name": "My Portfolio",
        "type": "MANUAL",
        "base_currency": "USD",
        "status": "ACTIVE",
        "created_at": datetime.now(),
    }

    mock_row = MagicMock()
    mock_row._mapping = row

    result = MagicMock()
    result.fetchone.return_value = mock_row

    session.execute.return_value = result

    repository = C1Repository(session)

    portfolio = await repository.create_portfolio(
        user_id="user-123",
        name="My Portfolio",
        p_type="MANUAL",
        currency="USD",
    )

    assert portfolio["portfolio_id"] == "portfolio-123"
    assert portfolio["user_id"] == "user-123"
    assert portfolio["name"] == "My Portfolio"
    assert portfolio["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_create_portfolio_fails_when_no_row():
    session = AsyncMock()

    result = MagicMock()
    result.fetchone.return_value = None

    session.execute.return_value = result

    repository = C1Repository(session)

    with pytest.raises(RuntimeError, match="Failed to create portfolio"):
        await repository.create_portfolio(
            user_id="user-123",
            name="My Portfolio",
            p_type="MANUAL",
            currency="USD",
        )


@pytest.mark.asyncio
async def test_get_portfolio_by_id_found():
    session = AsyncMock()

    row = {
        "portfolio_id": "portfolio-123",
        "user_id": "user-123",
        "name": "My Portfolio",
        "type": "MANUAL",
        "base_currency": "USD",
        "status": "ACTIVE",
        "created_at": datetime.now(),
    }

    mock_row = MagicMock()
    mock_row._mapping = row

    result = MagicMock()
    result.fetchone.return_value = mock_row

    session.execute.return_value = result

    repository = C1Repository(session)

    portfolio = await repository.get_portfolio_by_id(
        portfolio_id="portfolio-123",
        user_id="user-123",
    )

    assert portfolio is not None
    assert portfolio["portfolio_id"] == "portfolio-123"
    assert portfolio["user_id"] == "user-123"


@pytest.mark.asyncio
async def test_get_portfolio_by_id_not_found():
    session = AsyncMock()

    result = MagicMock()
    result.fetchone.return_value = None

    session.execute.return_value = result

    repository = C1Repository(session)

    portfolio = await repository.get_portfolio_by_id(
        portfolio_id="missing-portfolio",
        user_id="user-123",
    )

    assert portfolio is None
