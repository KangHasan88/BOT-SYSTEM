from __future__ import annotations

import csv
from pathlib import Path

from trading_bot.data_collector.market_context import (
    OrderBookSnapshot,
    SymbolMetadata,
    TickerSnapshot,
)


class MarketContextCsvStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save_metadata(self, metadata: SymbolMetadata) -> Path:
        path = self.root / "metadata" / f"{metadata.symbol.replace('/', '_')}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "symbol",
                    "base_asset",
                    "quote_asset",
                    "min_notional",
                    "price_precision",
                    "quantity_precision",
                    "taker_fee_pct",
                    "maker_fee_pct",
                    "source",
                ],
            )
            writer.writeheader()
            writer.writerow(metadata.__dict__)
        return path

    def append_ticker(self, snapshot: TickerSnapshot) -> Path:
        snapshot.validate()
        path = self.root / "ticker" / f"{snapshot.symbol.replace('/', '_')}.csv"
        exists = path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "symbol",
                    "captured_at_ms",
                    "bid",
                    "ask",
                    "mid",
                    "spread",
                    "spread_pct",
                    "source",
                ],
            )
            if not exists:
                writer.writeheader()
            writer.writerow(
                {
                    "symbol": snapshot.symbol,
                    "captured_at_ms": snapshot.captured_at_ms,
                    "bid": snapshot.bid,
                    "ask": snapshot.ask,
                    "mid": snapshot.mid,
                    "spread": snapshot.spread,
                    "spread_pct": snapshot.spread_pct,
                    "source": snapshot.source,
                }
            )
        return path

    def append_order_book(self, snapshot: OrderBookSnapshot) -> Path:
        path = self.root / "order_book" / f"{snapshot.symbol.replace('/', '_')}.csv"
        exists = path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "symbol",
                    "captured_at_ms",
                    "best_bid",
                    "best_ask",
                    "bid_notional_top",
                    "ask_notional_top",
                    "imbalance_ratio",
                    "source",
                ],
            )
            if not exists:
                writer.writeheader()
            writer.writerow(
                {
                    "symbol": snapshot.symbol,
                    "captured_at_ms": snapshot.captured_at_ms,
                    "best_bid": snapshot.best_bid,
                    "best_ask": snapshot.best_ask,
                    "bid_notional_top": snapshot.bid_notional_top,
                    "ask_notional_top": snapshot.ask_notional_top,
                    "imbalance_ratio": snapshot.imbalance_ratio,
                    "source": snapshot.source,
                }
            )
        return path
