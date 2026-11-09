"""Optional cloud DDL utility; native development does not need Databricks.

No credentials belong in source. This command never connects unless explicitly
invoked with --execute and all three local configuration values are present.
Revoking an old embedded token must be performed in the issuing account.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

DDL_DIR = Path(__file__).resolve().parents[1] / "data" / "ddl"


def configuration() -> dict[str, str]:
    fields = {
        "server_hostname": "DATABRICKS_SERVER_HOSTNAME",
        "http_path": "DATABRICKS_HTTP_PATH",
        "access_token": "DATABRICKS_TOKEN",
    }
    values = {name: os.environ.get(variable, "").strip() for name, variable in fields.items()}
    missing = [variable for name, variable in fields.items() if not values[name]]
    if missing:
        raise ValueError("Missing local configuration: " + ", ".join(missing))
    return values


def split_statements(sql_text: str) -> list[str]:
    """Split the repository's simple, semicolon-ended DDL statements."""
    statements, current = [], []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        current.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(current).rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []
    if current:
        statements.append("\n".join(current).strip())
    return statements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicitly run cloud DDL")
    args = parser.parse_args()
    if not args.execute:
        print("Cloud DDL disabled. Use native fixture providers for local development.")
        return 0
    settings = configuration()
    from databricks import sql

    with sql.connect(**settings) as connection:
        with connection.cursor() as cursor:
            for path in sorted(DDL_DIR.glob("*.sql")):
                for statement in split_statements(path.read_text(encoding="utf-8")):
                    cursor.execute(statement)
                print(f"Completed {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
