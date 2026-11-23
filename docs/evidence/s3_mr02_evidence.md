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

Results on the feature branch:

```text
python -m ruff check .
All checks passed!

python -m pytest -q
2779 passed, 11 skipped, 13 xfailed, 2 xpassed
Coverage: 83.38% (required: 70%)
```

The dedicated CSV import tests also passed: `9 passed` (including the authenticated
endpoint, user-scoped persistence, limits, malformed rows, masking, and formula escaping).
