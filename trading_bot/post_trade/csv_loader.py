from __future__ import annotations

import csv
from pathlib import Path

from trading_bot.paper.models import PaperTrade


def load_paper_trades(root: str | Path, symbol: str, timeframe: str) -> list[PaperTrade]:
    path = Path(root) / "paper" / symbol.replace("/", "_") / timeframe / "trades.csv"
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [_row_to_trade(row) for row in csv.DictReader(handle)]


def _row_to_trade(row: dict[str, str]) -> PaperTrade:
    return PaperTrade(
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        entry_time_ms=int(row["entry_time_ms"]),
        exit_time_ms=int(row["exit_time_ms"]),
        entry_price=float(row["entry_price"]),
        exit_price=float(row["exit_price"]),
        quantity=float(row["quantity"]),
        gross_pnl=float(row["gross_pnl"]),
        fees=float(row["fees"]),
        net_pnl=float(row["net_pnl"]),
        exit_reason=row["exit_reason"],
    )
