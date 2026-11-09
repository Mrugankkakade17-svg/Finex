# backend/app/repositories/c1_repository.py

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class C1Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_portfolio(
        self,
        user_id: str,
        name: str,
        p_type: str,
        currency: str,
    ) -> Dict[str, Any]:
        """Creates a new portfolio in the operational store."""
        portfolio_id = str(uuid.uuid4())

        # Use parameterized SQL to strictly enforce security.
        query = text(
            """
            INSERT INTO portfolio.portfolios (
                portfolio_id,
                user_id,
                name,
                type,
                base_currency,
                status,
                created_at
            )
            VALUES (
                :p_id,
                :u_id,
                :name,
                :type,
                :currency,
                'ACTIVE',
                NOW()
            )
            RETURNING
                portfolio_id,
                user_id,
                name,
                type,
                base_currency,
                status,
                created_at
            """
        )

        result = await self.session.execute(
            query,
            {
                "p_id": portfolio_id,
                "u_id": user_id,
                "name": name,
                "type": p_type,
                "currency": currency,
            },
        )

        row = result.fetchone()

        if row is None:
            raise RuntimeError("Failed to create portfolio")

        return dict(row._mapping)

    async def get_portfolio_by_id(
        self,
        portfolio_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetches a portfolio while ensuring cross-user data isolation."""
        query = text(
            """
            SELECT
                portfolio_id,
                user_id,
                name,
                type,
                base_currency,
                status,
                created_at
            FROM portfolio.portfolios
            WHERE portfolio_id = :p_id
              AND user_id = :u_id
              AND status = 'ACTIVE'
            """
        )

        result = await self.session.execute(
            query,
            {
                "p_id": portfolio_id,
                "u_id": user_id,
            },
        )

        row = result.fetchone()

        return dict(row._mapping) if row else None
