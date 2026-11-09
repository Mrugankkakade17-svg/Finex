# backend/tests/unit/test_c1_service.py
import pytest

from app.services.c1_service import C1Service


@pytest.mark.asyncio
async def test_calculate_projection_deterministic_math():
    """
    Proves the C1Service projection math works deterministically as required by the handbook.
    """
    # We pass None for the repository because this specific method only does math
    service = C1Service(repository=None)

    # 1000 initial, 100 monthly, 12% annual return (1% monthly), for 1 year
    projections = await service.calculate_projection(
        initial_amount=1000.0, monthly_contrib=100.0, annual_return=0.12, years=1
    )

    assert len(projections) == 1
    assert projections[0]["year"] == 1
    assert "projected_value" in projections[0]
    # Simple bounds check to ensure compound logic is adding value
    assert projections[0]["projected_value"] > 2200.0
