from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from trading_bot.reports.daily_journal import DailyMarketJournal


@dataclass(frozen=True)
class AlertMessage:
    kind: str
    severity: str
    title: str
    body: str
    created_at_utc: str


def build_daily_report_alert(journal: DailyMarketJournal) -> AlertMessage:
    severity = "warning" if journal.review_status in {"REVIEW_REQUIRED", "NO_DATA"} else "info"
    return AlertMessage(
        kind="daily_report",
        severity=severity,
        title=f"Daily report {journal.symbol or 'UNKNOWN'} {journal.timeframe or ''}".strip(),
        body=(
            f"date={journal.report_date_utc}; status={journal.review_status}; "
            f"regime={journal.dominant_regime}; candles={journal.candle_count}; "
            f"paper_pnl={journal.paper_net_pnl:.8f}; notes={' | '.join(journal.notes)}"
        ),
        created_at_utc=_now_utc(),
    )


def build_stop_alert(symbol: str, reason: str, equity: float | None = None) -> AlertMessage:
    equity_text = f"; equity={equity:.8f}" if equity is not None else ""
    return AlertMessage(
        kind="stop",
        severity="critical",
        title=f"Trading stopped for {symbol}",
        body=f"reason={reason}{equity_text}",
        created_at_utc=_now_utc(),
    )


def build_error_alert(component: str, error: str) -> AlertMessage:
    return AlertMessage(
        kind="error",
        severity="error",
        title=f"Bot error in {component}",
        body=error,
        created_at_utc=_now_utc(),
    )


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
