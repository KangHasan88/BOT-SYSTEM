from __future__ import annotations

from trading_bot.data_collector.audit import build_quality_report, find_gaps
from trading_bot.data_collector.context_store import MarketContextCsvStore
from trading_bot.data_collector.csv_store import CandleCsvStore
from trading_bot.data_collector.market_context import (
    OrderBookSnapshot,
    SymbolMetadata,
    TickerSnapshot,
)
from trading_bot.data_collector.models import Candle, Gap, QualityReport, SyncResult


class MarketDataCollector:
    def __init__(
        self,
        store: CandleCsvStore,
        client,
        context_store: MarketContextCsvStore | None = None,
    ) -> None:
        self.store = store
        self.client = client
        self.context_store = context_store

    def sync_latest(self, symbol: str, timeframe: str, limit: int = 500) -> SyncResult:
        candles: list[Candle] = self.client.fetch_klines(symbol, timeframe, limit=limit)
        inserted = self.store.upsert_many(candles)
        total = len(self.store.load(symbol, timeframe))
        return SyncResult(
            symbol=symbol,
            timeframe=timeframe,
            fetched=len(candles),
            inserted_or_updated=inserted,
            total_after_sync=total,
        )

    def backfill(
        self,
        symbol: str,
        timeframe: str,
        start_time_ms: int,
        batches: int = 1,
        limit: int = 1000,
    ) -> SyncResult:
        if batches < 1:
            raise ValueError("batches must be >= 1")
        fetched_total = 0
        inserted_total = 0
        next_start = start_time_ms

        for _ in range(batches):
            candles: list[Candle] = self.client.fetch_klines(
                symbol,
                timeframe,
                limit=limit,
                start_time_ms=next_start,
            )
            if not candles:
                break

            fetched_total += len(candles)
            inserted_total += self.store.upsert_many(candles)
            next_start = candles[-1].open_time_ms + 1

            if len(candles) < limit:
                break

        total = len(self.store.load(symbol, timeframe))
        return SyncResult(
            symbol=symbol,
            timeframe=timeframe,
            fetched=fetched_total,
            inserted_or_updated=inserted_total,
            total_after_sync=total,
        )

    def audit_gaps(self, symbol: str, timeframe: str) -> list[Gap]:
        return find_gaps(self.store.load(symbol, timeframe))

    def quality_report(self, symbol: str, timeframe: str) -> QualityReport:
        return build_quality_report(self.store.load(symbol, timeframe), symbol, timeframe)

    def capture_market_context(self, symbol: str) -> tuple[SymbolMetadata, TickerSnapshot, OrderBookSnapshot]:
        if self.context_store is None:
            raise ValueError("context_store is required to capture market context")

        metadata = self.client.fetch_symbol_metadata(symbol)
        ticker = self.client.fetch_ticker_snapshot(symbol)
        order_book = self.client.fetch_order_book_snapshot(symbol)

        self.context_store.save_metadata(metadata)
        self.context_store.append_ticker(ticker)
        self.context_store.append_order_book(order_book)
        return metadata, ticker, order_book
