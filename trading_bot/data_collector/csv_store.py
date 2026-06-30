from __future__ import annotations

import csv
from pathlib import Path

from trading_bot.data_collector.models import Candle


FIELDNAMES = [
    "symbol",
    "timeframe",
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time_ms",
    "source",
]


class CandleCsvStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path_for(self, symbol: str, timeframe: str) -> Path:
        safe_symbol = symbol.replace("/", "_")
        return self.root / safe_symbol / f"{timeframe}.csv"

    def load(self, symbol: str, timeframe: str) -> list[Candle]:
        path = self.path_for(symbol, timeframe)
        if not path.exists():
            return []

        with path.open("r", newline="", encoding="utf-8") as handle:
            rows = csv.DictReader(handle)
            candles = [self._row_to_candle(row) for row in rows]

        candles.sort(key=lambda candle: candle.open_time_ms)
        return candles

    def upsert_many(self, candles: list[Candle]) -> int:
        if not candles:
            return 0

        symbol = candles[0].symbol
        timeframe = candles[0].timeframe
        for candle in candles:
            candle.validate()
            if candle.symbol != symbol or candle.timeframe != timeframe:
                raise ValueError("all candles in one upsert must share symbol and timeframe")

        existing = {candle.key(): candle for candle in self.load(symbol, timeframe)}
        before_count = len(existing)

        for candle in candles:
            existing[candle.key()] = candle

        merged = sorted(existing.values(), key=lambda candle: candle.open_time_ms)
        self._write(symbol, timeframe, merged)
        return len(existing) - before_count

    def _write(self, symbol: str, timeframe: str, candles: list[Candle]) -> None:
        path = self.path_for(symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            for candle in candles:
                writer.writerow(
                    {
                        "symbol": candle.symbol,
                        "timeframe": candle.timeframe,
                        "open_time_ms": candle.open_time_ms,
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "volume": candle.volume,
                        "close_time_ms": candle.close_time_ms or "",
                        "source": candle.source,
                    }
                )

    def _row_to_candle(self, row: dict[str, str]) -> Candle:
        close_time = row.get("close_time_ms") or ""
        return Candle(
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            open_time_ms=int(row["open_time_ms"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            close_time_ms=int(close_time) if close_time else None,
            source=row.get("source") or "unknown",
        )
