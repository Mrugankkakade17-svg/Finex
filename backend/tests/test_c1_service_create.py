from unittest.mock import AsyncMock

import pytest

from app.services.c1_service import C1Service


@pytest.mark.asyncio
async def test_create_user_portfolio():
    repository = AsyncMock()

    expected_portfolio = {
        "portfolio_id": "portfolio-123",
        "user_id": "user-123",
        "name": "My Portfolio",
        "type": "MANUAL",
        "base_currency": "USD",
        "status": "ACTIVE",
    }

    repository.create_portfolio.return_value = expected_portfolio

    service = C1Service(repository)

    result = await service.create_user_portfolio(
        user_id="user-123",
        name="My Portfolio",
        p_type="MANUAL",
        currency="USD",
    )

    assert result == expected_portfolio

    repository.create_portfolio.assert_awaited_once_with(
        "user-123",
        "My Portfolio",
        "MANUAL",
        "USD",
    )
