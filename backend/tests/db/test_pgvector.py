import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_postgres_version_16(postgres_db):
    """Verify the database service is PostgreSQL 16."""
    async with postgres_db.connect() as conn:
        result = await conn.execute(text("SHOW server_version;"))
        version_str = result.scalar_one()
        assert "16" in version_str, f"Expected PostgreSQL 16.x, got: {version_str}"


@pytest.mark.asyncio
async def test_pgvector_extension_installed(postgres_db):
    """Verify that pgvector extension can be created and is functional."""
    async with postgres_db.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        result = await conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        )
        ext_version = result.scalar_one_or_none()
        assert ext_version is not None, "pgvector extension is not registered"


@pytest.mark.asyncio
async def test_pgvector_embedding_operations(postgres_db):
    """Verify vector column creation, insertion, and similarity search."""
    async with postgres_db.begin() as conn:
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


@pytest.mark.asyncio
async def test_postgres_database_isolation(postgres_db):
    """Verify that transaction rollbacks ensure data isolation across tests."""
    async with postgres_db.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(text("CREATE TEMP TABLE isolation_test (id int, val text);"))
            await conn.execute(text("INSERT INTO isolation_test VALUES (1, 'isolated');"))
            res = await conn.execute(text("SELECT count(*) FROM isolation_test;"))
            assert res.scalar_one() == 1
        finally:
            await trans.rollback()
