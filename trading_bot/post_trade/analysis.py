from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo


class TradeLike(Protocol):
    symbol: str
    timeframe: str
    entry_time_ms: int
    exit_time_ms: int
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    net_pnl: float
    exit_reason: str


@dataclass(frozen=True)
class TradeSummary:
    trade_count: int
    win_count: int
    loss_count: int
    win_rate_pct: float
    total_net_pnl: float
    average_net_pnl: float
    best_trade_pnl: float
    worst_trade_pnl: float
    exit_reason_counts: dict[str, int]
    best_entry_hour_wib: int | None
    worst_entry_hour_wib: int | None


@dataclass(frozen=True)
class PostTradeReport:
    symbol: str
    timeframe: str
    summary: TradeSummary
    recommendations: list[str]


def generate_post_trade_report(
    trades: list[TradeLike],
    symbol: str = "",
    timeframe: str = "",
    timezone_name: str = "Asia/Jakarta",
) -> PostTradeReport:
    if not trades:
        return PostTradeReport(
            symbol=symbol,
            timeframe=timeframe,
            summary=TradeSummary(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, {}, None, None),
            recommendations=["collect more paper trades before changing strategy"],
        )

    ordered = sorted(trades, key=lambda trade: trade.entry_time_ms)
    symbol = symbol or ordered[0].symbol
    timeframe = timeframe or ordered[0].timeframe
    net_pnls = [trade.net_pnl for trade in ordered]
    wins = [trade for trade in ordered if trade.net_pnl > 0]
    losses = [trade for trade in ordered if trade.net_pnl < 0]
    exit_counts = Counter(trade.exit_reason for trade in ordered)
    hourly_pnl = _hourly_pnl(ordered, timezone_name)

    summary = TradeSummary(
        trade_count=len(ordered),
        win_count=len(wins),
        loss_count=len(losses),
        win_rate_pct=(len(wins) / len(ordered)) * 100,
        total_net_pnl=sum(net_pnls),
        average_net_pnl=sum(net_pnls) / len(net_pnls),
        best_trade_pnl=max(net_pnls),
        worst_trade_pnl=min(net_pnls),
        exit_reason_counts=dict(exit_counts),
        best_entry_hour_wib=_best_hour(hourly_pnl),
        worst_entry_hour_wib=_worst_hour(hourly_pnl),
    )
    return PostTradeReport(
        symbol=symbol,
        timeframe=timeframe,
        summary=summary,
        recommendations=_recommend(summary),
    )


def save_post_trade_report(report: PostTradeReport, root: str | Path) -> Path:
    symbol = report.symbol.replace("/", "_") if report.symbol else "UNKNOWN"
    timeframe = report.timeframe or "unknown"
    path = Path(root) / "post_trade" / symbol / f"{timeframe}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path


def _hourly_pnl(trades: list[TradeLike], timezone_name: str) -> dict[int, float]:
    zone = ZoneInfo(timezone_name)
    buckets: dict[int, float] = defaultdict(float)
    for trade in trades:
        hour = datetime.fromtimestamp(trade.entry_time_ms / 1000, tz=zone).hour
        buckets[hour] += trade.net_pnl
    return dict(buckets)


def _best_hour(hourly_pnl: dict[int, float]) -> int | None:
    if not hourly_pnl:
        return None
    return max(hourly_pnl.items(), key=lambda item: item[1])[0]


def _worst_hour(hourly_pnl: dict[int, float]) -> int | None:
    if not hourly_pnl:
        return None
    return min(hourly_pnl.items(), key=lambda item: item[1])[0]


def _recommend(summary: TradeSummary) -> list[str]:
    recommendations: list[str] = []
    if summary.trade_count < 20:
        recommendations.append("collect at least 20 paper trades before promoting strategy")
    if summary.win_rate_pct < 45 and summary.trade_count:
        recommendations.append("test stricter entry filter; win rate below conservative threshold")
    if summary.exit_reason_counts.get("STOP_LOSS", 0) > summary.win_count:
        recommendations.append("review stop placement and session filter; stop losses dominate wins")
    if summary.worst_entry_hour_wib is not None:
        recommendations.append(f"consider blocking or reviewing entry hour {summary.worst_entry_hour_wib:02d}:00 WIB")
    if summary.total_net_pnl <= 0 and summary.trade_count:
        recommendations.append("strategy iteration required; total paper PnL is not positive")
    if not recommendations:
        recommendations.append("continue paper observation; no immediate strategy change required")
    return recommendations
