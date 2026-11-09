from typing import Any, Optional

from databricks import sql

from app.config.logging import logger
from app.config.settings import get_settings

settings = get_settings()


def get_connection():
    """Create and return a Databricks SQL connection."""
    try:
        connection = sql.connect(
            server_hostname=settings.databricks_host.replace("https://", ""),
            http_path=f"/sql/1.0/warehouses/{settings.databricks_warehouse_id}",
            access_token=settings.databricks_token,
        )
        return connection
    except Exception as e:
        logger.error(f"Databricks connection failed: {str(e)}")
        raise


def execute_query(
    query: str,
    params: Optional[dict[str, Any]] = None,
):
    """Execute a SQL query and return results."""
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(query, params)

        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        rows = cursor.fetchall()

        return [dict(zip(columns, row)) for row in rows]

    finally:
        cursor.close()
        connection.close()


def execute_write(
    query: str,
    params: Optional[dict[str, Any]] = None,
):
    """Execute a write operation (INSERT, UPDATE, DELETE)."""
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(query, params)
        connection.commit()

    finally:
        cursor.close()
        connection.close()
