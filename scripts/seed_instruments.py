"""Idempotently seed the canonical market instrument master."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config.database import execute_write
from app.routers.market import INSTRUMENTS


def main() -> int:
    for instrument in INSTRUMENTS:
        execute_write(
            """MERGE INTO finex_dev.market.instruments AS target
               USING (SELECT :symbol AS symbol, :name AS name,
                             :instrument_type AS instrument_type, :exchange AS exchange,
                             :sector AS sector) AS source
               ON upper(target.symbol) = source.symbol AND upper(target.exchange) = source.exchange
               WHEN MATCHED THEN UPDATE SET
                 target.name = source.name,
                 target.instrument_type = source.instrument_type,
                 target.sector = source.sector,
                 target.is_active = true,
                 target.updated_at = current_timestamp()
               WHEN NOT MATCHED THEN INSERT
                 (symbol, name, instrument_type, exchange, sector, is_active, created_at, updated_at)
               VALUES
                 (source.symbol, source.name, source.instrument_type, source.exchange,
                  source.sector, true, current_timestamp(), current_timestamp())""",
            {
                "symbol": instrument.symbol,
                "name": instrument.name,
                "instrument_type": instrument.asset_class or "EQUITY",
                "exchange": instrument.exchange,
                "sector": None,
            },
        )
        print(f"Seeded {instrument.exchange}:{instrument.symbol}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
