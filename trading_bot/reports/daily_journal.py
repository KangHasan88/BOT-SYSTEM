from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.backtest import BacktestResult, calculate_backtest_metrics
from trading_bot.data_collector.models import Candle
from trading_bot.feature_engine import build_features, classify_regimes
from trading_bot.paper import PaperSessionResult
from trading_bot.pattern_analyzer import detect_price_action_patterns
from trading_bot.strategy import generate_conservative_signals


@dataclass(frozen=True)
class DailyMarketJournal:
    symbol: str
    timeframe: str
    report_date_utc: str
    candle_count: int
    start_time_ms: int | None
    end_time_ms: int | None
    dominant_regime: str
    regime_counts: dict[str, int]
    pattern_counts: dict[str, int]
    signal_counts: dict[str, int]
    average_range_pct: float
    average_volume_ratio: float | None
    paper_trade_count: int
    paper_net_pnl: float
    backtest_recommendation: str | None
    backtest_reason: str | None
    review_status: str
    notes: list[str]


def generate_daily_market_journal(
    candles: list[Candle],
    paper_result: PaperSessionResult | None = None,
    backtest_result: BacktestResult | None = None,
) -> DailyMarketJournal:
    if not candles:
        return DailyMarketJournal(
            symbol="",
            timeframe="",
            report_date_utc=_date_from_ms(None),
            candle_count=0,
            start_time_ms=None,
            end_time_ms=None,
            dominant_regime="unknown",
            regime_counts={},
            pattern_counts={},
            signal_counts={},
            average_range_pct=0.0,
            average_volume_ratio=None,
            paper_trade_count=0,
            paper_net_pnl=0.0,
            backtest_recommendation=None,
            backtest_reason=None,
            review_status="NO_DATA",
            notes=["no candles available for journal"],
        )

    ordered = sorted(candles, key=lambda candle: candle.open_time_ms)
    latest_day = ordered[-1].open_time_ms // 86_400_000
    day_candles = [candle for candle in ordered if candle.open_time_ms // 86_400_000 == latest_day]
    symbol = day_candles[0].symbol
    timeframe = day_candles[0].timeframe

    features = build_features(day_candles)
    regimes = classify_regimes(features)
    patterns = detect_price_action_patterns(day_candles)
    signals = generate_conservative_signals(features, regimes)

    regime_counts = Counter(row.regime for row in regimes)
    pattern_counts = Counter(row.pattern for row in patterns)
    signal_counts = Counter(row.action for row in signals)
    volume_ratios = [row.volume_spike_ratio for row in features if row.volume_spike_ratio is not None]
    avg_volume_ratio = sum(volume_ratios) / len(volume_ratios) if volume_ratios else None
    avg_range_pct = sum(row.range_pct for row in features) / len(features) if features else 0.0

    backtest_recommendation = None
    backtest_reason = None
    if backtest_result is not None:
        metrics = calculate_backtest_metrics(backtest_result)
        backtest_recommendation = metrics.recommendation
        backtest_reason = metrics.reason

    paper_trades = _filter_paper_trades_for_day(paper_result, latest_day)
    paper_net_pnl = sum(trade.net_pnl for trade in paper_trades)
    notes = _build_notes(regime_counts, pattern_counts, signal_counts, paper_net_pnl, backtest_recommendation)

    return DailyMarketJournal(
        symbol=symbol,
        timeframe=timeframe,
        report_date_utc=_date_from_ms(day_candles[-1].open_time_ms),
        candle_count=len(day_candles),
        start_time_ms=day_candles[0].open_time_ms,
        end_time_ms=day_candles[-1].open_time_ms,
        dominant_regime=regime_counts.most_common(1)[0][0] if regime_counts else "unknown",
        regime_counts=dict(regime_counts),
        pattern_counts=dict(pattern_counts),
        signal_counts=dict(signal_counts),
        average_range_pct=avg_range_pct,
        average_volume_ratio=avg_volume_ratio,
        paper_trade_count=len(paper_trades),
        paper_net_pnl=paper_net_pnl,
        backtest_recommendation=backtest_recommendation,
        backtest_reason=backtest_reason,
        review_status=_review_status(signal_counts, pattern_counts, paper_net_pnl, backtest_recommendation),
        notes=notes,
    )


def save_daily_market_journal(journal: DailyMarketJournal, root: str | Path) -> Path:
    safe_symbol = journal.symbol.replace("/", "_") if journal.symbol else "UNKNOWN"
    timeframe = journal.timeframe or "unknown"
    path = Path(root) / "reports" / "daily" / safe_symbol / timeframe / f"{journal.report_date_utc}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(journal), indent=2), encoding="utf-8")
    return path


def _filter_paper_trades_for_day(
    paper_result: PaperSessionResult | None,
    day_bucket: int,
) -> list:
    if paper_result is None:
        return []
    return [trade for trade in paper_result.trades if trade.exit_time_ms // 86_400_000 == day_bucket]


def _build_notes(
    regime_counts: Counter,
    pattern_counts: Counter,
    signal_counts: Counter,
    paper_net_pnl: float,
    backtest_recommendation: str | None,
) -> list[str]:
    notes: list[str] = []
    if regime_counts:
        notes.append(f"dominant regime: {regime_counts.most_common(1)[0][0]}")
    if pattern_counts:
        top_pattern = pattern_counts.most_common(1)[0]
        notes.append(f"top pattern: {top_pattern[0]} ({top_pattern[1]})")
    if signal_counts.get("BUY_CANDIDATE", 0) == 0:
        notes.append("no buy candidates; preserve capital")
    if paper_net_pnl < 0:
        notes.append("paper result negative; review entry filter and stop behavior")
    if backtest_recommendation in {"REJECT", "NEEDS_FILTER"}:
        notes.append(f"backtest gate says {backtest_recommendation}")
    if not notes:
        notes.append("normal research day; continue paper observation")
    return notes


def _review_status(
    signal_counts: Counter,
    pattern_counts: Counter,
    paper_net_pnl: float,
    backtest_recommendation: str | None,
) -> str:
    if backtest_recommendation == "REJECT" or paper_net_pnl < 0:
        return "REVIEW_REQUIRED"
    if signal_counts.get("BUY_CANDIDATE", 0) > 0 and backtest_recommendation == "PAPER_CANDIDATE":
        return "PAPER_CANDIDATE"
    if pattern_counts and signal_counts.get("BUY_CANDIDATE", 0) == 0:
        return "OBSERVE_ONLY"
    return "NEUTRAL"


def _date_from_ms(open_time_ms: int | None) -> str:
    if open_time_ms is None:
        return datetime.now(timezone.utc).date().isoformat()
    return datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc).date().isoformat()
