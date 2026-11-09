"""
S1-DAT-02 – Deterministic seed script for Lakebase/Postgres operational tables.

Usage:
    python scripts/seed_dat02.py [--schema finex]

Features:
    * Fixed UUIDs → deterministic, reproducible data
    * ON CONFLICT DO NOTHING → idempotent, safe to run repeatedly
    * Two distinct users (A / B) → enables user-isolation evidence
    * Reads DATABASE_URL from env → no hard-coded credentials

Requires:
    pip install psycopg2-binary   (or asyncpg for async)
"""

import argparse
import os
import sys

try:
    import psycopg2
except ImportError:
    print("psycopg2 not installed – run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


# ── Fixed seed UUIDs ─────────────────────────────────────────────────
USER_A_ID = "00000000-0000-4000-a000-000000000001"
USER_B_ID = "00000000-0000-4000-a000-000000000002"

PROFILE_A_ID = "a0000000-0000-4000-a000-000000000001"
PROFILE_B_ID = "a0000000-0000-4000-a000-000000000002"

HOLDING_A1_ID = "h0000000-0000-4000-a000-000000000001"
HOLDING_A2_ID = "h0000000-0000-4000-a000-000000000002"
HOLDING_B1_ID = "h0000000-0000-4000-a000-000000000003"

PORTFOLIO_A_ID = "p0000000-0000-4000-a000-000000000001"
PORTFOLIO_B_ID = "p0000000-0000-4000-a000-000000000002"


def get_connection(database_url: str):
    """Create a psycopg2 connection from a standard DATABASE_URL."""
    return psycopg2.connect(database_url)


def seed_users(cur, schema: str) -> None:
    cur.execute(
        f"""
        INSERT INTO {schema}.users
            (user_id, email, password_hash, name, role, risk_profile, is_active, created_at, updated_at)
        VALUES
            (%(uid)s, %(email)s, %(pw)s, %(name)s, %(role)s, %(risk)s, TRUE, NOW(), NOW())
        ON CONFLICT (user_id) DO NOTHING
        """,
        {"uid": USER_A_ID, "email": "alice@finex.dev", "pw": "hashed_pw_a", "name": "Alice A", "role": "user", "risk": "moderate"},
    )
    cur.execute(
        f"""
        INSERT INTO {schema}.users
            (user_id, email, password_hash, name, role, risk_profile, is_active, created_at, updated_at)
        VALUES
            (%(uid)s, %(email)s, %(pw)s, %(name)s, %(role)s, %(risk)s, TRUE, NOW(), NOW())
        ON CONFLICT (user_id) DO NOTHING
        """,
        {"uid": USER_B_ID, "email": "bob@finex.dev", "pw": "hashed_pw_b", "name": "Bob B", "role": "user", "risk": "aggressive"},
    )
    print("  ✓ users seeded")


def seed_profiles(cur, schema: str) -> None:
    cur.execute(
        f"""
        INSERT INTO {schema}.user_profiles
            (profile_id, user_id, first_name, last_name, phone, city, country, created_at, updated_at)
        VALUES
            (%(pid)s, %(uid)s, %(fn)s, %(ln)s, %(ph)s, %(city)s, %(country)s, NOW(), NOW())
        ON CONFLICT (profile_id) DO NOTHING
        """,
        {"pid": PROFILE_A_ID, "uid": USER_A_ID, "fn": "Alice", "ln": "Anderson", "ph": "+1-555-0001", "city": "New York", "country": "US"},
    )
    cur.execute(
        f"""
        INSERT INTO {schema}.user_profiles
            (profile_id, user_id, first_name, last_name, phone, city, country, created_at, updated_at)
        VALUES
            (%(pid)s, %(uid)s, %(fn)s, %(ln)s, %(ph)s, %(city)s, %(country)s, NOW(), NOW())
        ON CONFLICT (profile_id) DO NOTHING
        """,
        {"pid": PROFILE_B_ID, "uid": USER_B_ID, "fn": "Bob", "ln": "Brown", "ph": "+1-555-0002", "city": "London", "country": "UK"},
    )
    print("  ✓ user_profiles seeded")


def seed_holdings(cur, schema: str) -> None:
    holdings = [
        {"hid": HOLDING_A1_ID, "pid": PORTFOLIO_A_ID, "uid": USER_A_ID, "sym": "AAPL", "qty": 10.0, "price": 195.50, "cv": 2000.00},
        {"hid": HOLDING_A2_ID, "pid": PORTFOLIO_A_ID, "uid": USER_A_ID, "sym": "GOOGL", "qty": 5.0,  "price": 178.25, "cv": 900.00},
        {"hid": HOLDING_B1_ID, "pid": PORTFOLIO_B_ID, "uid": USER_B_ID, "sym": "MSFT",  "qty": 8.0,  "price": 410.00, "cv": 3300.00},
    ]
    for h in holdings:
        cur.execute(
            f"""
            INSERT INTO {schema}.portfolio_holdings
                (holding_id, portfolio_id, user_id, instrument_symbol, quantity, avg_buy_price, current_value, created_at, updated_at)
            VALUES
                (%(hid)s, %(pid)s, %(uid)s, %(sym)s, %(qty)s, %(price)s, %(cv)s, NOW(), NOW())
            ON CONFLICT (holding_id) DO NOTHING
            """,
            h,
        )
    print("  ✓ portfolio_holdings seeded")


def main():
    parser = argparse.ArgumentParser(description="Seed S1-DAT-02 Lakebase tables")
    parser.add_argument("--schema", default="finex", help="Postgres schema (default: finex)")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        print("  Example: postgresql://postgres:postgres@localhost:5432/finex_dev", file=sys.stderr)
        sys.exit(1)

    print(f"Seeding S1-DAT-02 tables in schema '{args.schema}'...")
    conn = get_connection(database_url)
    try:
        with conn.cursor() as cur:
            # Ensure schema exists
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {args.schema}")
            seed_users(cur, args.schema)
            seed_profiles(cur, args.schema)
            seed_holdings(cur, args.schema)
        conn.commit()
        print("Done — all seed data committed.")
    except Exception:
        conn.rollback()
        print("ERROR — transaction rolled back.", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
