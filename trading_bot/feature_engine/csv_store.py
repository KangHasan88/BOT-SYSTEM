from __future__ import annotations

import csv
from pathlib import Path

from trading_bot.feature_engine.features import FeatureRow


FIELDNAMES = [
    "symbol",
    "timeframe",
    "open_time_ms",
    "close",
    "ema_fast",
    "ema_slow",
    "rsi",
    "atr",
    "volume_sma",
    "body_pct",
    "upper_wick_pct",
    "lower_wick_pct",
    "range_pct",
    "volume_spike_ratio",
]


class FeatureCsvStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path_for(self, symbol: str, timeframe: str) -> Path:
        return self.root / "features" / symbol.replace("/", "_") / f"{timeframe}.csv"

    def write(self, rows: list[FeatureRow]) -> Path | None:
        if not rows:
            return None

        symbol = rows[0].symbol
        timeframe = rows[0].timeframe
        path = self.path_for(symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize(getattr(row, field)) for field in FIELDNAMES})

        return path


def _serialize(value: object) -> object:
    return "" if value is None else value
