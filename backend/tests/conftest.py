import os

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.repositories.onboarding_repository import onboarding_repository
from app.repositories.postgres_user_repository import postgres_user_repository
from app.repositories.risk_repository import risk_repository
from app.repositories.user_repository import user_repository
from app.services.auth_service import login_tracker


@pytest.fixture(autouse=True)
def reset_in_memory_repositories():
    """Reset in-memory repositories and rate-limit trackers before every test."""

    # Reset users
    if hasattr(user_repository, "_users"):
        user_repository._users.clear()

    if hasattr(user_repository, "_next_id"):
        user_repository._next_id = 1

    if hasattr(postgres_user_repository, "_memory_users"):
        postgres_user_repository._memory_users.clear()

    login_tracker.clear()

    # Reset onboarding
    if hasattr(onboarding_repository, "_onboarding"):
        onboarding_repository._onboarding.clear()

    # Reset risk assessments
    if hasattr(risk_repository, "_assessments"):
        risk_repository._assessments.clear()

    if hasattr(risk_repository, "_next_assessment_id"):
        risk_repository._next_assessment_id = 1

    yield


@pytest_asyncio.fixture
async def postgres_db():
    """Provide an async engine when DATABASE_URL is set; otherwise skip PostgreSQL tests."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for PostgreSQL contract tests")

    engine = async_engine_from_config(
        {"sqlalchemy.url": database_url},
        prefix="sqlalchemy.",
    )
    try:
        yield engine
    finally:
        await engine.dispose()
