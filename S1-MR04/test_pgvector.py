import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/finex_test"


@pytest.fixture
def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_version_16(database_url: str):
    """Verify the database service is PostgreSQL 16."""
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SHOW server_version;"))
            version_str = result.scalar_one()
            assert "16" in version_str, f"Expected PostgreSQL 16.x, got: {version_str}"
    finally:
        await engine.dispose()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pgvector_extension_installed(database_url: str):
    """Verify that pgvector extension can be created and is functional."""
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            result = await conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
            )
            ext_version = result.scalar_one_or_none()
            assert ext_version is not None, "pgvector extension is not registered"
    finally:
        await engine.dispose()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pgvector_embedding_operations(database_url: str):
    """Verify vector column creation, insertion, and similarity search."""
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(
                text(
                    """
                    CREATE TEMP TABLE test_embeddings (
                        id serial PRIMARY KEY,
                        label text NOT NULL,
                        embedding vector(3) NOT NULL
                    );
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO test_embeddings (label, embedding) VALUES
                    ('vector_a', '[1.0, 0.0, 0.0]'),
                    ('vector_b', '[0.0, 1.0, 0.0]'),
                    ('vector_c', '[0.9, 0.1, 0.0]');
                    """
                )
            )

            # Cosine distance (<=>): vector_c should be closest to vector_a
            query = text(
                """
                SELECT label, embedding <=> '[1.0, 0.0, 0.0]' AS distance
                FROM test_embeddings
                ORDER BY distance ASC;
                """
            )
            rows = (await conn.execute(query)).fetchall()
            assert len(rows) == 3
            assert rows[0][0] == "vector_a"
            assert round(float(rows[0][1]), 4) == 0.0
            assert rows[1][0] == "vector_c"
            assert rows[2][0] == "vector_b"
    finally:
        await engine.dispose()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_database_isolation(database_url: str):
    """Verify that transaction rollbacks ensure data isolation across tests."""
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                await conn.execute(text("CREATE TEMP TABLE isolation_test (id int, val text);"))
                await conn.execute(text("INSERT INTO isolation_test VALUES (1, 'isolated');"))
                res = await conn.execute(text("SELECT count(*) FROM isolation_test;"))
                assert res.scalar_one() == 1
            finally:
                await trans.rollback()
    finally:
        await engine.dispose()
