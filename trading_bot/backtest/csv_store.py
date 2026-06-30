from __future__ import annotations

import csv
from pathlib import Path

from trading_bot.backtest.models import BacktestResult


class BacktestCsvStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, result: BacktestResult) -> tuple[Path, Path]:
        base = self.root / "backtests" / result.symbol.replace("/", "_") / result.timeframe
        base.mkdir(parents=True, exist_ok=True)
        trades_path = base / "trades.csv"
        equity_path = base / "equity.csv"

        with trades_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "symbol",
                    "timeframe",
                    "entry_time_ms",
                    "exit_time_ms",
                    "entry_price",
                    "exit_price",
                    "quantity",
                    "gross_pnl",
                    "fees",
                    "net_pnl",
                    "exit_reason",
                    "entry_signal_time_ms",
                    "exit_signal_time_ms",
                ],
            )
            writer.writeheader()
            for trade in result.trades:
                writer.writerow(trade.__dict__)

        with equity_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["open_time_ms", "equity"])
            writer.writeheader()
            for point in result.equity_curve:
                writer.writerow(point.__dict__)

        return trades_path, equity_path
