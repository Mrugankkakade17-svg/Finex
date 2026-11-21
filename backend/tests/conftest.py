import os

import pytest
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from app.repositories.onboarding_repository import onboarding_repository
from app.repositories.risk_repository import risk_repository
from app.repositories.user_repository import user_repository


@pytest.fixture(autouse=True)
def reset_in_memory_repositories():
    """Reset in-memory repositories before every test."""

    # Reset users
    if hasattr(user_repository, "_users"):
        user_repository._users.clear()

    if hasattr(user_repository, "_next_id"):
        user_repository._next_id = 1

    # Reset onboarding
    if hasattr(onboarding_repository, "_onboarding"):
        onboarding_repository._onboarding.clear()

    # Reset risk assessments
    if hasattr(risk_repository, "_assessments"):
        risk_repository._assessments.clear()

    if hasattr(risk_repository, "_next_assessment_id"):
        risk_repository._next_assessment_id = 1

    yield


@pytest.fixture
def postgres_db():
    """Provides an isolated async engine when DATABASE_URL is set; skips otherwise."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is not set; skipping PostgreSQL test")

    engine = create_async_engine(database_url)
    try:
        yield engine
    finally:
        engine.sync_engine.dispose()
