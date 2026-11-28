"""Goal projections, contributions, progress, and documented monthly-contribution math.

Documented Monthly-Contribution Formula
-------------------------------------
Consistent with `calculate_goal_projections`, contributions are modelled as an
annuity-due (contribution added at the start of each month, then compounded for
that month) with monthly rate:

    r = (expected_annual_return_pct / 100) / 12

Over N remaining monthly periods starting from current balance P_0 toward target T:

1. Zero-return case (r == 0):
   - B_N = P_0 + N * M
   - If P_0 >= T, required monthly contribution M_req = 0.00.
   - If N == 0 and P_0 < T, M_req is None (no remaining monthly periods to amortize).
   - Otherwise, M_req = (T - P_0) / N, rounded to cents (ROUND_HALF_UP).

2. Positive-return case (r > 0):
   - B_N = P_0 * (1 + r)^N + M * (1 + r) * (((1 + r)^N - 1) / r)
   - If P_0 * (1 + r)^N >= T, M_req = 0.00 (current balance alone reaches target).
   - If N == 0 and P_0 < T, M_req is None.
   - Otherwise:
     M_req = (T - P_0 * (1 + r)^N) * r / ((1 + r) * ((1 + r)^N - 1))
     computed at 34-digit Decimal precision and rounded to cents (ROUND_HALF_UP).
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Sequence
from uuid import uuid4

from app.repositories.goal_repo import GoalRepository, goal_repository
from app.schemas.sprint4_paper_goals import (
    GoalContributionCreateRequest,
    GoalContributionRecordResponse,
    GoalContributionResponse,
    GoalCreateRequest,
    GoalProgressResponse,
    GoalProjection,
    GoalResponse,
    GoalUpdateRequest,
)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100.00")

ASSUMPTIONS_STATEMENT = (
    "Deterministic model based on constant monthly compounding. No guarantee of future performance."
)

MONTHLY_CONTRIBUTION_FORMULA_SUMMARY = (
    "Annuity-due monthly contribution formula matching projection compounding: "
    "for r = (annual_return_pct / 100) / 12 and N remaining months, "
    "if r == 0 then M = max(0, (target - current) / N); "
    "if r > 0 then M = max(0, (target - current * (1 + r)^N) * r / ((1 + r) * ((1 + r)^N - 1))); "
    "when N == 0 and current < target, required_monthly_contribution is null."
)


def parse_iso_date(value: date | str, field_name: str = "date") -> date:
    """Validate and return a calendar date, rejecting datetime objects."""
    if isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a calendar date, not a datetime.")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO calendar date (YYYY-MM-DD).") from exc
    raise ValueError(f"{field_name} must be a date or ISO date string.")


def _finite_decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a valid decimal.")
    try:
        parsed = Decimal(value) if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid decimal.") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be finite.")
    return parsed


def months_between_dates(as_of_date: date | str, target_date: date | str) -> int:
    """Return remaining full calendar months from as_of_date to target_date.

    Edge-date rules:
    - Same day or past target_date (target_date <= as_of_date): returns 0.
    - Same calendar month or < 1 full month remaining: returns 0.
    - Month-end alignment: when target_date falls on the last day of its month
      (e.g., Jan 31 -> Feb 28, or leap-day Feb 29 -> Feb 28 next year), the month
      boundary is treated as complete rather than penalizing shorter months.
    """
    start = parse_iso_date(as_of_date, "as_of_date")
    end = parse_iso_date(target_date, "target_date")
    if end <= start:
        return 0

    months = (end.year - start.year) * 12 + (end.month - start.month)
    target_month_end = calendar.monthrange(end.year, end.month)[1]
    if end.day < start.day and end.day != target_month_end:
        months -= 1
    return max(0, months)


def calculate_required_monthly_contribution(
    target_amount: Decimal,
    current_amount: Decimal,
    months_remaining: int,
    annual_rate_pct: Decimal,
) -> Decimal | None:
    """Compute required monthly contribution under the documented annuity-due formula.

    Returns Decimal("0.00") when already funded or projected to meet the target from
    existing balance alone, or None when months_remaining == 0 and a shortfall remains.
    """
    target = _finite_decimal(target_amount, "target_amount")
    current = _finite_decimal(current_amount, "current_amount")
    rate_pct = _finite_decimal(annual_rate_pct, "annual_rate_pct")

    if target <= 0:
        raise ValueError("target_amount must be positive.")
    if current < 0:
        raise ValueError("current_amount must be non-negative.")
    if isinstance(months_remaining, bool) or months_remaining < 0:
        raise ValueError("months_remaining must be a non-negative integer.")
    if rate_pct < 0:
        raise ValueError("annual_rate_pct must be non-negative.")

    if current >= target:
        return ZERO
    if months_remaining == 0:
        return None

    if rate_pct == 0:
        required = (target - current) / Decimal(months_remaining)
        return required.quantize(CENT, rounding=ROUND_HALF_UP)

    with localcontext() as ctx:
        ctx.prec = 34
        r_monthly = (rate_pct / Decimal("100")) / Decimal("12")
        one_plus_r = Decimal("1") + r_monthly
        growth_factor = one_plus_r**months_remaining
        fv_current = current * growth_factor
        if fv_current >= target:
            return ZERO
        annuity_due_factor = one_plus_r * (growth_factor - Decimal("1")) / r_monthly
        required = (target - fv_current) / annuity_due_factor
        return required.quantize(CENT, rounding=ROUND_HALF_UP)


class GoalService:
    """Application service for deterministic goal projections, contributions, and progress."""

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
        """Deterministic compound interest with regular start-of-month deposits."""
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
                    projected_balance=balance.quantize(CENT),
                    contributions_total=total_contributions.quantize(CENT),
                    growth_total=growth.quantize(CENT),
                )
            )

        final_balance = projections[-1].projected_balance if projections else current_amount
        return (
            final_balance,
            projections,
            final_balance >= target_amount,
        )

    def _build_goal_response(
        self,
        *,
        goal_id: str,
        title: str,
        target_amount: Decimal,
        current_amount: Decimal,
        horizon_years: int,
        monthly_contribution: Decimal,
        expected_annual_return_pct: Decimal,
        target_date: date | None,
    ) -> GoalResponse:
        final_balance, projections, is_on_track = self.calculate_goal_projections(
            current_amount=current_amount,
            monthly_contribution=monthly_contribution,
            horizon_years=horizon_years,
            annual_rate_pct=expected_annual_return_pct,
            target_amount=target_amount,
        )
        return GoalResponse(
            goal_id=goal_id,
            title=title,
            target_amount=target_amount,
            current_amount=current_amount,
            horizon_years=horizon_years,
            monthly_contribution=monthly_contribution,
            expected_annual_return_pct=expected_annual_return_pct,
            projected_final_amount=final_balance,
            shortfall_or_surplus=(final_balance - target_amount).quantize(CENT),
            is_on_track=is_on_track,
            assumptions_statement=ASSUMPTIONS_STATEMENT,
            projections=projections,
            target_date=target_date,
        )

    def create_goal(self, user_id: str, goal_in: GoalCreateRequest) -> GoalResponse:
        goal = self._build_goal_response(
            goal_id=f"goal-{uuid4().hex[:8]}",
            title=goal_in.title,
            target_amount=goal_in.target_amount,
            current_amount=goal_in.current_amount,
            horizon_years=goal_in.horizon_years,
            monthly_contribution=goal_in.monthly_contribution,
            expected_annual_return_pct=goal_in.expected_annual_return_pct,
            target_date=goal_in.target_date,
        )
        return self.repository.create_goal(user_id, goal)

    def list_goals(self, user_id: str) -> list[GoalResponse]:
        return self.repository.list_goals(user_id)

    def get_goal(self, user_id: str, goal_id: str) -> GoalResponse | None:
        return self.repository.get_goal(user_id, goal_id)

    def update_goal(
        self,
        user_id: str,
        goal_id: str,
        goal_in: GoalUpdateRequest,
    ) -> GoalResponse | None:
        existing = self.repository.get_goal(user_id, goal_id)
        if existing is None:
            return None

        fields = goal_in.model_fields_set
        target_date = goal_in.target_date if "target_date" in fields else existing.target_date
        updated = self._build_goal_response(
            goal_id=existing.goal_id,
            title=goal_in.title if goal_in.title is not None else existing.title,
            target_amount=(
                goal_in.target_amount
                if goal_in.target_amount is not None
                else existing.target_amount
            ),
            current_amount=(
                goal_in.current_amount
                if goal_in.current_amount is not None
                else existing.current_amount
            ),
            horizon_years=(
                goal_in.horizon_years
                if goal_in.horizon_years is not None
                else existing.horizon_years
            ),
            monthly_contribution=(
                goal_in.monthly_contribution
                if goal_in.monthly_contribution is not None
                else existing.monthly_contribution
            ),
            expected_annual_return_pct=(
                goal_in.expected_annual_return_pct
                if goal_in.expected_annual_return_pct is not None
                else existing.expected_annual_return_pct
            ),
            target_date=target_date,
        )
        return self.repository.update_goal(user_id, updated)

    def delete_goal(self, user_id: str, goal_id: str) -> bool:
        return self.repository.delete_goal(user_id, goal_id)

    def record_contribution(
        self,
        user_id: str,
        goal_id: str,
        contribution_in: GoalContributionCreateRequest,
        *,
        as_of_date: date | str | None = None,
    ) -> GoalContributionRecordResponse | None:
        """Record an owner-scoped contribution, update goal balance/projections, and summarize."""
        existing = self.repository.get_goal(user_id, goal_id)
        if existing is None:
            return None

        new_current = (existing.current_amount + contribution_in.amount).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        updated_goal = self._build_goal_response(
            goal_id=existing.goal_id,
            title=existing.title,
            target_amount=existing.target_amount,
            current_amount=new_current,
            horizon_years=existing.horizon_years,
            monthly_contribution=existing.monthly_contribution,
            expected_annual_return_pct=existing.expected_annual_return_pct,
            target_date=existing.target_date,
        )
        contribution = GoalContributionResponse(
            contribution_id=f"contrib-{uuid4().hex[:8]}",
            goal_id=existing.goal_id,
            amount=contribution_in.amount.quantize(CENT, rounding=ROUND_HALF_UP),
            contribution_date=contribution_in.contribution_date,
            note=contribution_in.note,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        stored = self.repository.add_contribution(
            user_id, existing.goal_id, contribution, updated_goal
        )
        if stored is None:
            return None

        contributions = self.repository.list_contributions(user_id, existing.goal_id)
        progress = self.calculate_goal_progress(updated_goal, contributions, as_of_date=as_of_date)
        return GoalContributionRecordResponse(
            contribution=stored,
            goal=updated_goal,
            progress=progress,
        )

    def list_contributions(
        self, user_id: str, goal_id: str
    ) -> list[GoalContributionResponse] | None:
        """List contributions for one user's goal, returning None if the goal does not exist."""
        existing = self.repository.get_goal(user_id, goal_id)
        if existing is None:
            return None
        return self.repository.list_contributions(user_id, goal_id)

    def calculate_goal_progress(
        self,
        goal: GoalResponse,
        contributions: Sequence[GoalContributionResponse],
        *,
        as_of_date: date | str | None = None,
    ) -> GoalProgressResponse:
        """Compute deterministic progress and required monthly contribution for a goal."""
        effective_as_of = (
            parse_iso_date(as_of_date, "as_of_date")
            if as_of_date is not None
            else datetime.now(timezone.utc).date()
        )
        target_amount = goal.target_amount
        current_amount = goal.current_amount
        remaining_amount = max(
            ZERO, (target_amount - current_amount).quantize(CENT, rounding=ROUND_HALF_UP)
        )
        surplus_amount = max(
            ZERO, (current_amount - target_amount).quantize(CENT, rounding=ROUND_HALF_UP)
        )
        is_completed = current_amount >= target_amount
        raw_pct = (
            ((current_amount / target_amount) * Decimal("100")).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            if target_amount > 0
            else HUNDRED
        )
        progress_pct = min(HUNDRED, max(ZERO, raw_pct))

        total_contributed = sum((item.amount for item in contributions), ZERO).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        last_contribution_date = max(
            (item.contribution_date for item in contributions), default=None
        )

        months_remaining = (
            months_between_dates(effective_as_of, goal.target_date)
            if goal.target_date is not None
            else goal.horizon_years * 12
        )
        is_overdue = (
            goal.target_date is not None and goal.target_date < effective_as_of and not is_completed
        )

        required_monthly = calculate_required_monthly_contribution(
            target_amount=target_amount,
            current_amount=current_amount,
            months_remaining=months_remaining,
            annual_rate_pct=goal.expected_annual_return_pct,
        )
        monthly_gap: Decimal | None = None
        if required_monthly is not None:
            monthly_gap = max(
                ZERO,
                (required_monthly - goal.monthly_contribution).quantize(
                    CENT, rounding=ROUND_HALF_UP
                ),
            )

        if is_completed:
            is_on_track = True
        elif required_monthly is None:
            is_on_track = False
        elif goal.target_date is not None:
            is_on_track = goal.monthly_contribution >= required_monthly
        else:
            is_on_track = goal.is_on_track

        return GoalProgressResponse(
            goal_id=goal.goal_id,
            title=goal.title,
            target_amount=target_amount,
            current_amount=current_amount,
            remaining_amount=remaining_amount,
            surplus_amount=surplus_amount,
            progress_pct=progress_pct,
            total_contributed=total_contributed,
            contributions_count=len(contributions),
            last_contribution_date=last_contribution_date,
            as_of_date=effective_as_of,
            target_date=goal.target_date,
            horizon_years=goal.horizon_years,
            months_remaining=months_remaining,
            is_overdue=is_overdue,
            is_completed=is_completed,
            configured_monthly_contribution=goal.monthly_contribution,
            expected_annual_return_pct=goal.expected_annual_return_pct,
            required_monthly_contribution=required_monthly,
            monthly_contribution_gap=monthly_gap,
            is_on_track=is_on_track,
            formula_summary=MONTHLY_CONTRIBUTION_FORMULA_SUMMARY,
            assumptions_statement=goal.assumptions_statement,
        )

    def get_goal_progress(
        self,
        user_id: str,
        goal_id: str,
        *,
        as_of_date: date | str | None = None,
    ) -> GoalProgressResponse | None:
        """Load one user's goal and contributions and return deterministic progress."""
        goal = self.repository.get_goal(user_id, goal_id)
        if goal is None:
            return None
        contributions = self.repository.list_contributions(user_id, goal_id)
        return self.calculate_goal_progress(goal, contributions, as_of_date=as_of_date)

    def list_goals_progress(
        self,
        user_id: str,
        *,
        as_of_date: date | str | None = None,
    ) -> list[GoalProgressResponse]:
        """Return deterministic progress summaries for all goals owned by user_id."""
        goals = self.repository.list_goals(user_id)
        return [
            self.calculate_goal_progress(
                goal,
                self.repository.list_contributions(user_id, goal.goal_id),
                as_of_date=as_of_date,
            )
            for goal in goals
        ]


goal_service = GoalService()
