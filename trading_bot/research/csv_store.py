from __future__ import annotations

import csv
from pathlib import Path

from trading_bot.research.dataset import PatternOutcomeRow


FIELDNAMES = [
    "symbol",
    "timeframe",
    "open_time_ms",
    "pattern",
    "direction",
    "score",
    "entry_price",
    "horizon_candles",
    "max_favorable_pct",
    "max_adverse_pct",
    "close_return_pct",
    "outcome_label",
    "manual_label",
    "reason",
]


class ResearchDatasetCsvStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, rows: list[PatternOutcomeRow], symbol: str, timeframe: str) -> Path:
        path = self.root / "research" / "pattern_outcomes" / symbol.replace("/", "_") / f"{timeframe}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: getattr(row, field) for field in FIELDNAMES})
        return path
