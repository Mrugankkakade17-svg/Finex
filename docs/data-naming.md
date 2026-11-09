# FinEx Data Naming Conventions

**Task:** S1-DAT-01
**Owner:** Shivraj
**Reviewers:** Mitali, Palak

## Catalog Naming

Format: `finex_<environment>`

| Catalog | Purpose |
|---------|---------|
| `finex_dev` | Development |
| `finex_staging` | Staging / QA |
| `finex_prod` | Production |

## Schema Naming

Lowercase, single word, describes the data domain.

| Schema | Purpose |
|--------|---------|
| `core` | Operational, user-owned records |
| `market` | Market / financial instrument data |
| `analytics` | Computed / aggregated analytical data |
| `ai` | AI / RAG data (documents, embeddings, chat) |

## Table Naming

- snake_case
- Plural nouns (`users`, not `user`)
- No abbreviations unless industry standard (e.g. `pnl`)

## Column Naming

| Rule | Example |
|------|---------|
| Primary key | `<entity_singular>_id` | `user_id`, `portfolio_id` |
| Foreign key | `<referenced_entity_singular>_id` | `user_id` in `portfolios` |
| Timestamps | `created_at`, `updated_at` (UTC, TIMESTAMP type) |
| Booleans | prefix `is_` or `has_` | `is_active`, `has_profile` |
| Dates | `<event>_date` | `price_date`, `deadline` |
| Money/amounts | `_amount`, `_value`, `_price` | `total_amount`, `current_value` |

## Data Types

| Use | Instead of |
|-----|-----------|
| `STRING` | VARCHAR, TEXT |
| `BIGINT GENERATED ALWAYS AS IDENTITY` | manual UUID for internal PKs |
| `DOUBLE` | FLOAT |
| `TIMESTAMP` | DATETIME |
| `BOOLEAN` | INT flags (0/1) |

## Required Columns

- Every table: `created_at TIMESTAMP`
- Every mutable table (data that gets updated): `updated_at TIMESTAMP`
- Every user-owned table: `user_id BIGINT NOT NULL`

## Ownership / Isolation

- User-owned records always carry `user_id` to support row-level isolation.
- Immutable event/log tables (`transactions`, `alerts`, `market_news`) only need `created_at` (no `updated_at`).
