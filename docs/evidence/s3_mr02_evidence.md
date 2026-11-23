# S3-MR02 Safe CSV Import Evidence

## Scope

- Added authenticated `POST /api/v1/spending/imports` using the existing FinEx response envelope.
- Added bounded CSV parsing, required-column/date/amount validation, row quarantine, description masking, formula-safe text handling, and per-user persistence.
- Preserved existing spending route paths and response behavior.

## Safety limits

- Maximum upload: 5 MiB.
- Maximum records: 10,000.
- Maximum field length: 4,096 characters.
- Formula-like description and category values receive a leading apostrophe before persistence/export.
- Imported records are persisted under the authenticated principal's user ID.

## Verification

Run from `backend/`:

```text
python -m ruff check .
python -m pytest -q
```

Verification on the corrected PR head:

```text
Backend Quality Gates:
Ruff lint — passed
Ruff format check — passed
Mypy — passed
PostgreSQL migration round-trip — passed
Full backend pytest — 2,848 passed, 9 deselected, 5 xfailed, 2 xpassed
Coverage — 84.54% (required: 70%)

Backend Postgres Tests:
Postgres-marked tests — passed
Full backend pytest — 2,857 passed, 5 xfailed, 2 xpassed
Coverage — 85.95% (required: 70%)
```

The CSV import tests are included in both full backend runs. They cover the authenticated
endpoint, user-scoped persistence, upload/row/field limits, malformed rows, masking,
and formula escaping.
