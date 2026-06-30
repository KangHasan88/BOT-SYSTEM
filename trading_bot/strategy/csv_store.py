from __future__ import annotations

import csv
from pathlib import Path

from trading_bot.strategy.signals import Signal


FIELDNAMES = [
    "symbol",
    "timeframe",
    "open_time_ms",
    "action",
    "confidence",
    "reason",
]


class SignalCsvStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path_for(self, symbol: str, timeframe: str) -> Path:
        return self.root / "signals" / symbol.replace("/", "_") / f"{timeframe}.csv"

    def write(self, signals: list[Signal], symbol: str, timeframe: str) -> Path:
        path = self.path_for(symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            for signal in signals:
                writer.writerow({field: getattr(signal, field) for field in FIELDNAMES})
        return path
