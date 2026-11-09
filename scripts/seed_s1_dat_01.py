"""Seed and reset the local S1-DAT-01 fixture adapter."""

import argparse
from typing import Any

from backend.app.fixtures.s1_dat_01 import S1Dat01FixtureProvider

S1Dat01FixtureStore = S1Dat01FixtureProvider


def reset_and_seed() -> dict[str, Any]:
    """Return a fresh deterministic local fixture snapshot."""
    return S1Dat01FixtureStore().reset_and_seed()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset and seed local S1-DAT-01 fixtures")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the isolated in-memory fixture adapter before seeding",
    )
    args = parser.parse_args()

    store = S1Dat01FixtureStore()
    if args.reset:
        records = store.reset_and_seed()
        operation = "reset and seed"
    else:
        records = store.seed()
        operation = "seed"

    scenarios = records["records"]["scenarios"]
    users = records["records"]["synthetic_users"]
    print(
        f"S1-DAT-01 {operation} passed: "
        f"{len(users)} synthetic users, {len(scenarios)} scenarios, "
        f"contract {records['fixture_contract_schema_version']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
