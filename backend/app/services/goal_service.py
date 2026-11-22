"""Goal projections and persistent user-owned goal operations."""

from decimal import Decimal
from uuid import uuid4

from app.repositories.goal_repo import GoalRepository, goal_repository
from app.schemas.sprint4_paper_goals import (
    GoalCreateRequest,
    GoalProjection,
    GoalResponse,
)


class GoalService:
    def __init__(self, repository: GoalRepository | None = None) -> None:
        self.repository = repository or goal_repository

    def calculate_goal_projections(
        self,
        current_amount: Decimal,
        monthly_contribution: Decimal,
        horizon_years: int,
        annual_rate_pct: Decimal,
        target_amount: Decimal,
    ) -> tuple[Decimal, list[GoalProjection], bool]:
        r_monthly = (annual_rate_pct / Decimal("100")) / Decimal("12")
        balance = current_amount
        total_contributions = current_amount
        projections: list[GoalProjection] = []

        for year in range(1, horizon_years + 1):
            for _ in range(12):
                balance = (balance + monthly_contribution) * (Decimal("1") + r_monthly)
                total_contributions += monthly_contribution

            growth = balance - total_contributions
            projections.append(
                GoalProjection(
                    year=year,
                    projected_balance=balance.quantize(Decimal("0.01")),
                    contributions_total=total_contributions.quantize(Decimal("0.01")),
                    growth_total=growth.quantize(Decimal("0.01")),
                )
            )

        final_balance = (
            projections[-1].projected_balance
            if projections
            else current_amount
        )
        return (
            final_balance,
            projections,
            final_balance >= target_amount,
        )

    def create_goal(self, user_id: str, goal_in: GoalCreateRequest) -> GoalResponse:
        final_balance, projections, is_on_track = self.calculate_goal_projections(
            current_amount=goal_in.current_amount,
            monthly_contribution=goal_in.monthly_contribution,
            horizon_years=goal_in.horizon_years,
            annual_rate_pct=goal_in.expected_annual_return_pct,
            target_amount=goal_in.target_amount,
        )
        goal = GoalResponse(
            goal_id=f"goal-{uuid4().hex[:8]}",
            title=goal_in.title,
            target_amount=goal_in.target_amount,
            current_amount=goal_in.current_amount,
            horizon_years=goal_in.horizon_years,
            monthly_contribution=goal_in.monthly_contribution,
            expected_annual_return_pct=goal_in.expected_annual_return_pct,
            projected_final_amount=final_balance,
            shortfall_or_surplus=(final_balance - goal_in.target_amount).quantize(
                Decimal("0.01")
            ),
            is_on_track=is_on_track,
            assumptions_statement=(
                "Deterministic model based on constant monthly compounding. "
                "No guarantee of future performance."
            ),
            projections=projections,
        )
        return self.repository.create_goal(user_id, goal)

    def list_goals(self, user_id: str) -> list[GoalResponse]:
        return self.repository.list_goals(user_id)

    def get_goal(self, user_id: str, goal_id: str) -> GoalResponse | None:
        return self.repository.get_goal(user_id, goal_id)


goal_service = GoalService()
