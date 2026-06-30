from __future__ import annotations

from dataclasses import dataclass

from trading_bot.alerts import AlertOutbox, build_daily_report_alert
from trading_bot.backtest import BacktestConfig, run_event_backtest
from trading_bot.config import BotConfig
from trading_bot.dashboard import save_review_dashboard
from trading_bot.data_collector.binance_public import BinancePublicKlineClient
from trading_bot.data_collector.context_store import MarketContextCsvStore
from trading_bot.data_collector.csv_store import CandleCsvStore
from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.data_collector.service import MarketDataCollector
from trading_bot.feature_engine import FeatureCsvStore, RegimeCsvStore, build_features, classify_regimes
from trading_bot.observability import JsonlAuditLogger
from trading_bot.paper import PaperConfig, PaperCsvStore, run_paper_session
from trading_bot.pattern_analyzer import PatternCsvStore, detect_price_action_patterns
from trading_bot.post_trade import generate_post_trade_report, save_post_trade_report
from trading_bot.research import ResearchDatasetCsvStore, build_pattern_outcome_dataset
from trading_bot.reports.daily_journal import generate_daily_market_journal, save_daily_market_journal
from trading_bot.reports.quality import save_quality_report
from trading_bot.reports.walk_forward import save_walk_forward_report
from trading_bot.safety import read_kill_switch
from trading_bot.strategy import SignalCsvStore, generate_conservative_signals
from trading_bot.validation import WalkForwardConfig, run_walk_forward_validation


@dataclass(frozen=True)
class CycleResult:
    symbols_processed: int
    timeframes_processed: int
    candles_seen: int
    paper_trades: int
    alerts_written: int
    dashboard_path: str


def run_research_cycle(
    config: BotConfig,
    sync_latest: bool = False,
    limit: int = 500,
    initial_equity: float = 1_000.0,
    min_notional: float = 1.0,
) -> CycleResult:
    candle_store = CandleCsvStore(config.data_root)
    collector = MarketDataCollector(
        store=candle_store,
        client=BinancePublicKlineClient(),
        context_store=MarketContextCsvStore(config.data_root),
    )
    total_candles = 0
    total_paper_trades = 0
    total_alerts = 0
    processed_pairs = 0
    logger = JsonlAuditLogger(config.data_root)
    logger.write(
        "cycle_start",
        "research cycle started",
        sync_latest=sync_latest,
        limit=limit,
        symbols=list(config.symbols),
        timeframes=list(config.timeframes),
    )
    kill_switch = read_kill_switch(config.data_root)
    if kill_switch.active:
        logger.write("cycle_blocked", "kill switch is active", level="CRITICAL", reason=kill_switch.reason)
        return CycleResult(
            symbols_processed=0,
            timeframes_processed=0,
            candles_seen=0,
            paper_trades=0,
            alerts_written=0,
            dashboard_path=str(save_review_dashboard(config.data_root)),
        )

    for symbol in config.symbols:
        try:
            if sync_latest:
                collector.capture_market_context(symbol)
        except Exception as exc:  # noqa: BLE001 - operational runner must log and continue.
            logger.write("market_context_error", str(exc), level="ERROR", symbol=symbol)

        for timeframe in config.timeframes:
            logger.write("pair_start", "processing market pair", symbol=symbol, timeframe=timeframe)
            try:
                if sync_latest:
                    collector.sync_latest(symbol, timeframe, limit=limit)

                candles = candle_store.load(symbol, timeframe)
                total_candles += len(candles)
                processed_pairs += 1

                quality = collector.quality_report(symbol, timeframe)
                save_quality_report(quality, config.data_root)

                features = build_features(candles)
                FeatureCsvStore(config.data_root).write(features)
                regimes = classify_regimes(features)
                RegimeCsvStore(config.data_root).write(regimes, symbol, timeframe)
                patterns = detect_price_action_patterns(candles)
                PatternCsvStore(config.data_root).write(patterns, symbol, timeframe)
                research_rows = build_pattern_outcome_dataset(candles, patterns)
                ResearchDatasetCsvStore(config.data_root).write(research_rows, symbol, timeframe)
                signals = generate_conservative_signals(features, regimes)
                SignalCsvStore(config.data_root).write(signals, symbol, timeframe)

                metadata = _metadata(symbol, min_notional)
                paper = run_paper_session(
                    candles,
                    metadata=metadata,
                    config=PaperConfig(
                        initial_equity=initial_equity,
                        entry_windows_wib=config.entry_windows_wib,
                        timezone="Asia/Jakarta",
                        enforce_entry_windows=True,
                    ),
                )
                PaperCsvStore(config.data_root).write(paper)
                post_trade = generate_post_trade_report(paper.trades, symbol, timeframe)
                save_post_trade_report(post_trade, config.data_root)
                total_paper_trades += len(paper.trades)

                backtest = run_event_backtest(
                    candles,
                    metadata=metadata,
                    config=BacktestConfig(initial_equity=initial_equity),
                )
                walk_forward = run_walk_forward_validation(
                    candles,
                    metadata=metadata,
                    config=WalkForwardConfig(initial_equity=initial_equity),
                )
                save_walk_forward_report(walk_forward, config.data_root, symbol, timeframe)
                journal = generate_daily_market_journal(candles, paper, backtest)
                save_daily_market_journal(journal, config.data_root)
                alert = build_daily_report_alert(journal)
                AlertOutbox(config.data_root).write(alert)
                total_alerts += 1
                logger.write(
                    "pair_complete",
                    "market pair processed",
                    symbol=symbol,
                    timeframe=timeframe,
                    candles=len(candles),
                    paper_trades=len(paper.trades),
                    review_status=journal.review_status,
                )
            except Exception as exc:  # noqa: BLE001 - keep scheduled cycle alive and auditable.
                logger.write(
                    "pair_error",
                    str(exc),
                    level="ERROR",
                    symbol=symbol,
                    timeframe=timeframe,
                )
                continue

    dashboard_path = save_review_dashboard(config.data_root)
    logger.write(
        "cycle_complete",
        "research cycle completed",
        symbols_processed=len(config.symbols),
        timeframes_processed=processed_pairs,
        candles_seen=total_candles,
        paper_trades=total_paper_trades,
        alerts_written=total_alerts,
        dashboard_path=str(dashboard_path),
    )
    return CycleResult(
        symbols_processed=len(config.symbols),
        timeframes_processed=processed_pairs,
        candles_seen=total_candles,
        paper_trades=total_paper_trades,
        alerts_written=total_alerts,
        dashboard_path=str(dashboard_path),
    )


def _metadata(symbol: str, min_notional: float) -> SymbolMetadata:
    base, quote = symbol.split("/")
    return SymbolMetadata(
        symbol=symbol,
        base_asset=base,
        quote_asset=quote,
        min_notional=min_notional,
        price_precision=8,
        quantity_precision=8,
        taker_fee_pct=0.10,
        maker_fee_pct=0.10,
        source="cycle",
    )
