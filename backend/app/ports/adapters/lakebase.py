import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

load_dotenv()

# Lakebase Postgres URL format for our async engine
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/finex_dev"
)

# Create the async engine that connects to the database
engine = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)

# Set up the session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

# Base class for our Alembic models
Base = declarative_base()


# Dependency to get the database session in our FastAPI routes
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
