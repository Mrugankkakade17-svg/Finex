"""Bounded, validated CSV imports for user-scoped spending transactions."""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config.settings import get_settings
from app.schemas.sprint5_privacy_spending import SpendingUploadSummary

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000
MAX_FIELD_CHARS = 4_096
REQUIRED_COLUMNS = ("date", "description", "amount", "category")
_FORMULA_PREFIX = re.compile(r"^[\s\x00-\x1f]*[=+@\-]")


def _mask_description(raw: str) -> str:
    masked = re.sub(r"\b\d{4,16}\b", "****", raw)
    masked = re.sub(r"#[A-Za-z0-9]+", "#***", masked)
    return masked.strip()


class CSVImportError(ValueError):
    """A CSV file cannot be safely processed."""


def _safe_text(value: str) -> str:
    """Prevent spreadsheet formula execution when imported text is exported later."""
    cleaned = value.strip()
    if _FORMULA_PREFIX.match(cleaned):
        return "'" + cleaned
    return cleaned


def _parse_rows(content: bytes) -> tuple[list[dict[str, Any]], int]:
    if not content:
        raise CSVImportError("The uploaded CSV is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise CSVImportError("CSV exceeds the 5 MiB upload limit.")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVImportError("CSV must use UTF-8 encoding.") from exc

    reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
    headers = [header.strip().lower() for header in (reader.fieldnames or [])]
    if len(headers) != len(set(headers)) or any(not header for header in headers):
        raise CSVImportError("CSV headers must be unique and non-empty.")
    missing = set(REQUIRED_COLUMNS) - set(headers)
    if missing:
        raise CSVImportError("CSV must include date, description, amount, and category columns.")

    imported: list[dict[str, Any]] = []
    quarantined = 0
    try:
        for row_number, raw in enumerate(reader, start=1):
            if row_number > MAX_ROWS:
                raise CSVImportError(f"CSV exceeds the {MAX_ROWS:,} row limit.")
            if None in raw or any(value is None for value in raw.values()):
                quarantined += 1
                continue
            values = {key.strip().lower(): value for key, value in raw.items()}
            if any(len(value) > MAX_FIELD_CHARS for value in values.values()):
                quarantined += 1
                continue
            try:
                transaction_date = date.fromisoformat(values["date"].strip())
                amount = Decimal(values["amount"].strip())
                description = _safe_text(values["description"])
                category = _safe_text(values["category"])
                if not amount.is_finite() or not description or not category or len(category) > 50:
                    raise ValueError("invalid transaction")
                imported.append(
                    {
                        "transaction_id": str(uuid4()),
                        "date": transaction_date,
                        "description_masked": _mask_description(description),
                        "amount": amount,
                        "category": category,
                    }
                )
            except (ValueError, InvalidOperation, KeyError):
                quarantined += 1
    except csv.Error as exc:
        raise CSVImportError("CSV formatting is invalid.") from exc
    return imported, quarantined


def _persist(user_id: str, transactions: list[dict[str, Any]], settings: Any) -> None:
    if not transactions:
        return
    if settings.app_persistence == "postgresql":
        from sqlalchemy import create_engine, text

        url = settings.app_database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
        engine = create_engine(url)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """INSERT INTO finex.spending_transactions
                        (user_id, transaction_id, date, description_masked, amount, category)
                        VALUES (:user_id, :transaction_id, :date, :description_masked,
                                :amount, :category)"""
                    ),
                    [{**item, "user_id": user_id} for item in transactions],
                )
        finally:
            engine.dispose()
    else:
        database_path = Path(settings.local_db_path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database_path)) as connection:
            with connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS spending_transactions (
                        user_id TEXT NOT NULL, transaction_id TEXT NOT NULL,
                        date TEXT NOT NULL, description_masked TEXT NOT NULL,
                        amount TEXT NOT NULL, category TEXT NOT NULL,
                        is_user_corrected INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (user_id, transaction_id)
                    )"""
                )
                connection.executemany(
                    """INSERT INTO spending_transactions
                    (user_id, transaction_id, date, description_masked, amount, category)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            user_id,
                            row["transaction_id"],
                            row["date"].isoformat(),
                            row["description_masked"],
                            str(row["amount"]),
                            row["category"],
                        )
                        for row in transactions
                    ],
                )


def import_spending_csv(
    content: bytes,
    filename: str,
    user_id: str,
    settings: Any | None = None,
) -> SpendingUploadSummary:
    """Validate, sanitize, and persist valid rows under the authenticated user."""
    if not user_id:
        raise ValueError("user_id is required")
    transactions, quarantined = _parse_rows(content)
    _persist(user_id, transactions, settings or get_settings())
    return SpendingUploadSummary(
        upload_id=str(uuid4()),
        filename=filename[:255],
        total_rows_imported=len(transactions),
        quarantined_rows=quarantined,
        total_spend_amount=sum((row["amount"] for row in transactions), Decimal("0")),
        categories_detected=sorted({row["category"] for row in transactions}),
    )
