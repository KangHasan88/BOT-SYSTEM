from __future__ import annotations

import csv
from pathlib import Path

from trading_bot.paper.models import PaperSessionResult


class PaperCsvStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, result: PaperSessionResult) -> tuple[Path, Path, Path]:
        base = self.root / "paper" / result.symbol.replace("/", "_") / result.timeframe
        base.mkdir(parents=True, exist_ok=True)
        orders_path = base / "orders.csv"
        trades_path = base / "trades.csv"
        account_path = base / "account.csv"

        _write_dataclass_rows(orders_path, result.orders)
        _write_dataclass_rows(trades_path, result.trades)
        _write_dataclass_rows(account_path, result.account_snapshots)

        return orders_path, trades_path, account_path


def _write_dataclass_rows(path: Path, rows: list[object]) -> None:
    fieldnames = list(rows[0].__dict__.keys()) if rows else []
    if not fieldnames:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)
