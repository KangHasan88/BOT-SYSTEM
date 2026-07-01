from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trading_bot.config import BotConfig
from trading_bot.data_collector import Candle, CandleCsvStore, timeframe_to_ms
from trading_bot.ops import run_research_cycle
from trading_bot.research import generate_database_learning_snapshot, save_database_learning_snapshot
from trading_bot.storage import default_database_path, import_runtime_data


@dataclass(frozen=True)
class DemoDataPackResult:
    candle_rows: int
    cycle_candles_seen: int
    paper_trades: int
    database_rows: int
    learning_report_path: str
    dashboard_path: str


def seed_demo_data_pack(
    config: BotConfig,
    candles_per_pair: int = 180,
    initial_equity: float = 1_000.0,
) -> DemoDataPackResult:
    if candles_per_pair < 80:
        raise ValueError("candles_per_pair must be at least 80 for demo learning")

    store = CandleCsvStore(config.data_root)
    total_rows = 0
    for symbol_index, symbol in enumerate(config.symbols):
        for timeframe_index, timeframe in enumerate(config.timeframes):
            candles = _demo_candles(symbol, timeframe, candles_per_pair, symbol_index, timeframe_index)
            store.upsert_many(candles)
            total_rows += len(candles)

    cycle = run_research_cycle(
        config,
        sync_latest=False,
        limit=candles_per_pair,
        initial_equity=initial_equity,
        min_notional=1.0,
    )
    database = import_runtime_data(config.data_root, default_database_path(config.data_root))
    learning = generate_database_learning_snapshot(
        default_database_path(config.data_root),
        symbols=list(config.symbols),
        timeframes=list(config.timeframes),
        limit=candles_per_pair,
    )
    learning_path = save_database_learning_snapshot(learning, config.data_root)
    return DemoDataPackResult(
        candle_rows=total_rows,
        cycle_candles_seen=cycle.candles_seen,
        paper_trades=cycle.paper_trades,
        database_rows=database.total_rows,
        learning_report_path=str(learning_path),
        dashboard_path=cycle.dashboard_path,
    )


def _demo_candles(
    symbol: str,
    timeframe: str,
    count: int,
    symbol_index: int,
    timeframe_index: int,
) -> list[Candle]:
    step_ms = timeframe_to_ms(timeframe)
    start_ms = 1_717_200_000_000 + timeframe_index * 10_000_000
    base_price = 64_000.0 if symbol.startswith("BTC") else 3_200.0
    base_price += symbol_index * 250.0 + timeframe_index * 75.0
    candles: list[Candle] = []
    for index in range(count):
        wave = ((index % 24) - 12) / 12
        trend = index * (base_price * 0.00035)
        open_price = base_price + trend + wave * (base_price * 0.004)
        close_bias = ((index % 7) - 3) * (base_price * 0.00045)
        close_price = max(1.0, open_price + close_bias)
        high = max(open_price, close_price) * (1.002 + (index % 5) * 0.0004)
        low = min(open_price, close_price) * (0.998 - (index % 3) * 0.0003)
        volume = 10 + symbol_index * 4 + timeframe_index * 2 + (index % 11)

        if index in {55, 111, 149}:
            high *= 1.012
            close_price = min(close_price, high * 0.988)
            volume *= 2.5
        if index in {72, 128, 166}:
            low *= 0.988
            close_price = max(close_price, low * 1.014)
            volume *= 2.3

        open_time_ms = start_ms + index * step_ms
        candles.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time_ms=open_time_ms,
                open=round(open_price, 8),
                high=round(high, 8),
                low=round(low, 8),
                close=round(close_price, 8),
                volume=round(volume, 8),
                close_time_ms=open_time_ms + step_ms - 1,
                source="demo_pack",
            )
        )
    return candles
