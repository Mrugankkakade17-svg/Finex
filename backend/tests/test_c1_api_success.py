from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1 import c1


@pytest.mark.asyncio
async def test_create_portfolio_success():
    portfolio = {
        "portfolio_id": "portfolio-123",
        "user_id": "user-123",
        "name": "My Retirement Fund",
        "type": "MANUAL",
        "base_currency": "USD",
        "status": "ACTIVE",
        "created_at": datetime(2026, 8, 10, 12, 30, 0),
    }

    payload = SimpleNamespace(
        name="My Retirement Fund",
        type="MANUAL",
        base_currency="USD",
    )

    mock_db = SimpleNamespace(
        commit=AsyncMock(),
    )

    mock_service = SimpleNamespace(
        create_user_portfolio=AsyncMock(return_value=portfolio),
    )

    with patch.object(
        c1,
        "C1Repository",
        return_value=SimpleNamespace(),
    ):
        with patch.object(
            c1,
            "C1Service",
            return_value=mock_service,
        ):
            result = await c1.create_portfolio(
                payload=payload,
                x_user_id="user-123",
                x_correlation_id="correlation-123",
                db=mock_db,
            )

    mock_service.create_user_portfolio.assert_awaited_once_with(
        user_id="user-123",
        name="My Retirement Fund",
        p_type="MANUAL",
        currency="USD",
    )

    mock_db.commit.assert_awaited_once()

    assert result.data.portfolio_id == "portfolio-123"
    assert result.data.user_id == "user-123"
    assert result.data.name == "My Retirement Fund"
    assert result.data.type == "MANUAL"
    assert result.data.base_currency == "USD"
    assert result.data.status == "ACTIVE"
    assert result.data.created_at == "2026-08-10T12:30:00Z"

    assert result.meta.correlationId == "correlation-123"
    assert result.meta.dataStatus == "LIVE"
