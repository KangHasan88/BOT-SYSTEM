from __future__ import annotations

import csv
from pathlib import Path

from trading_bot.feature_engine.regime import RegimeRow


FIELDNAMES = [
    "symbol",
    "timeframe",
    "open_time_ms",
    "regime",
    "trend",
    "volatility",
    "liquidity",
    "reason",
]


class RegimeCsvStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path_for(self, symbol: str, timeframe: str) -> Path:
        return self.root / "regimes" / symbol.replace("/", "_") / f"{timeframe}.csv"

    def write(self, rows: list[RegimeRow], symbol: str, timeframe: str) -> Path:
        path = self.path_for(symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: getattr(row, field) for field in FIELDNAMES})
        return path
