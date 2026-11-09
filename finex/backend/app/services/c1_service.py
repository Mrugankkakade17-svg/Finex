# backend/app/services/c1_service.py

from typing import Any, Dict, List

from app.repositories.c1_repository import C1Repository


class C1Service:
    def __init__(self, repository: C1Repository):
        self.repository = repository

    async def create_user_portfolio(
        self,
        user_id: str,
        name: str,
        p_type: str,
        currency: str,
    ) -> Dict[str, Any]:
        """
        Handles business logic for portfolio creation before saving to the operational store.
        """
        return await self.repository.create_portfolio(
            user_id,
            name,
            p_type,
            currency,
        )

    async def calculate_projection(
        self,
        initial_amount: float,
        monthly_contrib: float,
        annual_return: float,
        years: int,
    ) -> List[Dict[str, Any]]:
        """
        Deterministic math calculation for POR-04 projections.
        The AI is explicitly prohibited from guaranteeing returns or inventing this math.
        """
        rate_monthly = annual_return / 12.0
        months = years * 12
        current_val = initial_amount
        projections = []

        for month in range(1, months + 1):
            current_val = (current_val + monthly_contrib) * (1 + rate_monthly)

            # Record the projection at the end of each year
            if month % 12 == 0:
                projections.append(
                    {
                        "year": month // 12,
                        "projected_value": round(current_val, 2),
                    }
                )

        return projections
