"""Unit tests for S3-LI02 goal contributions, progress, edge dates, and zero-return math."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.schemas.sprint4_paper_goals import GoalContributionResponse, GoalResponse
from app.services.goal_service import (
    MONTHLY_CONTRIBUTION_FORMULA_SUMMARY,
    GoalService,
    calculate_required_monthly_contribution,
    months_between_dates,
    parse_iso_date,
)


def _sample_goal(
    *,
    target_amount: str = "12000.00",
    current_amount: str = "0.00",
    horizon_years: int = 1,
    monthly_contribution: str = "1000.00",
    annual_rate_pct: str = "0.0",
    target_date: date | None = None,
) -> GoalResponse:
    return GoalResponse(
        goal_id="goal-test-1",
        title="Emergency Reserve",
        target_amount=Decimal(target_amount),
        current_amount=Decimal(current_amount),
        horizon_years=horizon_years,
        monthly_contribution=Decimal(monthly_contribution),
        expected_annual_return_pct=Decimal(annual_rate_pct),
        projected_final_amount=Decimal(target_amount),
        shortfall_or_surplus=Decimal("0.00"),
        is_on_track=True,
        projections=[],
        target_date=target_date,
    )


def test_zero_return_required_monthly_contribution_closed_form() -> None:
    assert calculate_required_monthly_contribution(
        target_amount=Decimal("12000.00"),
        current_amount=Decimal("0.00"),
        months_remaining=12,
        annual_rate_pct=Decimal("0"),
    ) == Decimal("1000.00")
    assert calculate_required_monthly_contribution(
        target_amount=Decimal("5000.00"),
        current_amount=Decimal("1400.00"),
        months_remaining=12,
        annual_rate_pct=Decimal("0.0"),
    ) == Decimal("300.00")
    assert calculate_required_monthly_contribution(
        target_amount=Decimal("1000.00"),
        current_amount=Decimal("0.00"),
        months_remaining=3,
        annual_rate_pct=Decimal("0"),
    ) == Decimal("333.33")
    assert calculate_required_monthly_contribution(
        target_amount=Decimal("5000.00"),
        current_amount=Decimal("5000.00"),
        months_remaining=12,
        annual_rate_pct=Decimal("0"),
    ) == Decimal("0.00")


def test_zero_return_projections_have_zero_growth() -> None:
    service = GoalService()
    final_balance, projections, is_on_track = service.calculate_goal_projections(
        current_amount=Decimal("1000.00"),
        monthly_contribution=Decimal("250.00"),
        horizon_years=2,
        annual_rate_pct=Decimal("0"),
        target_amount=Decimal("7000.00"),
    )

    assert final_balance == Decimal("7000.00")
    assert is_on_track is True
    actual = [
        (p.year, p.projected_balance, p.contributions_total, p.growth_total) for p in projections
    ]
    assert actual == [
        (1, Decimal("4000.00"), Decimal("4000.00"), Decimal("0.00")),
        (2, Decimal("7000.00"), Decimal("7000.00"), Decimal("0.00")),
    ]


def test_positive_return_formula_matches_projection_compounding() -> None:
    service = GoalService()
    final_balance, _, _ = service.calculate_goal_projections(
        current_amount=Decimal("1000.00"),
        monthly_contribution=Decimal("100.00"),
        horizon_years=1,
        annual_rate_pct=Decimal("12.0"),
        target_amount=Decimal("2407.76"),
    )
    assert final_balance == Decimal("2407.76")

    required = calculate_required_monthly_contribution(
        target_amount=Decimal("2407.76"),
        current_amount=Decimal("1000.00"),
        months_remaining=12,
        annual_rate_pct=Decimal("12.0"),
    )
    assert required == Decimal("100.00")

    # Existing balance compounding alone already exceeds target
    assert calculate_required_monthly_contribution(
        target_amount=Decimal("1100.00"),
        current_amount=Decimal("1000.00"),
        months_remaining=12,
        annual_rate_pct=Decimal("12.0"),
    ) == Decimal("0.00")


@pytest.mark.parametrize(
    ("as_of_date", "target_date", "expected_months"),
    [
        (date(2026, 11, 28), date(2026, 11, 28), 0),  # same day
        (date(2026, 11, 28), date(2026, 11, 1), 0),  # past date
        (date(2026, 11, 1), date(2026, 11, 30), 0),  # same month, < 1 full month
        (date(2026, 12, 15), date(2027, 1, 14), 0),  # year boundary < 1 full month
        (date(2026, 12, 15), date(2027, 1, 15), 1),  # year boundary exact month
        (date(2026, 1, 31), date(2026, 2, 28), 1),  # month-end Jan -> Feb
        (date(2024, 2, 29), date(2025, 2, 28), 12),  # leap day -> non-leap Feb 28
        (date(2024, 2, 29), date(2028, 2, 29), 48),  # leap day -> next leap day
    ],
)
def test_edge_date_months_between_dates(
    as_of_date: date, target_date: date, expected_months: int
) -> None:
    assert months_between_dates(as_of_date, target_date) == expected_months


def test_edge_date_zero_months_remaining_with_shortfall_and_funded() -> None:
    assert (
        calculate_required_monthly_contribution(
            target_amount=Decimal("5000.00"),
            current_amount=Decimal("2000.00"),
            months_remaining=0,
            annual_rate_pct=Decimal("0"),
        )
        is None
    )
    assert calculate_required_monthly_contribution(
        target_amount=Decimal("5000.00"),
        current_amount=Decimal("5000.00"),
        months_remaining=0,
        annual_rate_pct=Decimal("6.0"),
    ) == Decimal("0.00")


def test_goal_progress_handles_empty_overdue_and_overfunded_states() -> None:
    service = GoalService()

    # Empty contributions, past-due target_date, zero-return
    overdue_goal = _sample_goal(
        target_amount="1000.00",
        current_amount="400.00",
        monthly_contribution="100.00",
        annual_rate_pct="0.0",
        target_date=date(2026, 10, 1),
    )
    overdue_progress = service.calculate_goal_progress(
        overdue_goal, [], as_of_date=date(2026, 11, 28)
    )
    assert overdue_progress.progress_pct == Decimal("40.00")
    assert overdue_progress.remaining_amount == Decimal("600.00")
    assert overdue_progress.surplus_amount == Decimal("0.00")
    assert overdue_progress.total_contributed == Decimal("0.00")
    assert overdue_progress.contributions_count == 0
    assert overdue_progress.last_contribution_date is None
    assert overdue_progress.months_remaining == 0
    assert overdue_progress.is_overdue is True
    assert overdue_progress.is_completed is False
    assert overdue_progress.required_monthly_contribution is None
    assert overdue_progress.monthly_contribution_gap is None
    assert overdue_progress.is_on_track is False
    assert overdue_progress.formula_summary == MONTHLY_CONTRIBUTION_FORMULA_SUMMARY

    # Same-day target_date, zero-return, already completed with surplus
    completed_goal = _sample_goal(
        target_amount="1000.00",
        current_amount="1250.00",
        monthly_contribution="50.00",
        annual_rate_pct="0.0",
        target_date=date(2026, 11, 28),
    )
    contributions = [
        GoalContributionResponse(
            contribution_id="c-1",
            goal_id="goal-test-1",
            amount=Decimal("250.00"),
            contribution_date=date(2024, 2, 29),
            note="Leap day deposit",
            created_at="2024-02-29T10:00:00+00:00",
        )
    ]
    completed_progress = service.calculate_goal_progress(
        completed_goal, contributions, as_of_date=date(2026, 11, 28)
    )
    assert completed_progress.progress_pct == Decimal("100.00")
    assert completed_progress.remaining_amount == Decimal("0.00")
    assert completed_progress.surplus_amount == Decimal("250.00")
    assert completed_progress.total_contributed == Decimal("250.00")
    assert completed_progress.contributions_count == 1
    assert completed_progress.last_contribution_date == date(2024, 2, 29)
    assert completed_progress.is_overdue is False
    assert completed_progress.is_completed is True
    assert completed_progress.required_monthly_contribution == Decimal("0.00")
    assert completed_progress.monthly_contribution_gap == Decimal("0.00")
    assert completed_progress.is_on_track is True


def test_invalid_inputs_are_rejected_explicitly() -> None:
    with pytest.raises(ValueError, match="calendar date"):
        parse_iso_date(datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc), "as_of_date")
    with pytest.raises(ValueError, match="ISO calendar date"):
        parse_iso_date("2026-02-29", "target_date")
    with pytest.raises(ValueError, match="target_amount"):
        calculate_required_monthly_contribution(Decimal("0"), Decimal("0"), 12, Decimal("0"))
    with pytest.raises(ValueError, match="current_amount"):
        calculate_required_monthly_contribution(Decimal("1000"), Decimal("-1"), 12, Decimal("0"))
    with pytest.raises(ValueError, match="months_remaining"):
        calculate_required_monthly_contribution(Decimal("1000"), Decimal("0"), -1, Decimal("0"))
    with pytest.raises(ValueError, match="annual_rate_pct"):
        calculate_required_monthly_contribution(Decimal("1000"), Decimal("0"), 12, Decimal("-0.5"))
    with pytest.raises(ValueError, match="finite"):
        calculate_required_monthly_contribution(Decimal("NaN"), Decimal("0"), 12, Decimal("0"))
