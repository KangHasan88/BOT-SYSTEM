from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.observability import read_audit_events
from trading_bot.post_trade import load_paper_trades


@dataclass(frozen=True)
class PaperStabilityConfig:
    min_days: int = 14
    min_trades: int = 20
    max_critical_errors: int = 0
    max_rejected_order_pct: float = 35.0
    max_stop_loss_pct: float = 60.0


@dataclass(frozen=True)
class PaperStabilityReport:
    symbol: str
    timeframe: str
    status: str
    observed_days: int
    trade_count: int
    order_count: int
    rejected_order_count: int
    rejected_order_pct: float
    stop_loss_count: int
    stop_loss_pct: float
    net_pnl: float
    critical_error_count: int
    generated_at_utc: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def evaluate_paper_stability(
    root: str | Path,
    symbol: str,
    timeframe: str,
    config: PaperStabilityConfig | None = None,
) -> PaperStabilityReport:
    root_path = Path(root)
    qa_config = config or PaperStabilityConfig()
    trades = load_paper_trades(root_path, symbol, timeframe)
    orders = _load_csv(_paper_dir(root_path, symbol, timeframe) / "orders.csv")
    account_rows = _load_csv(_paper_dir(root_path, symbol, timeframe) / "account.csv")
    days = _observed_days(trades, orders, account_rows)
    critical_errors = [
        event
        for event in read_audit_events(root_path)
        if event.level.upper() in {"ERROR", "CRITICAL"}
    ]

    rejected_orders = [order for order in orders if order.get("status", "").upper() == "REJECTED"]
    stop_loss_trades = [trade for trade in trades if "stop" in trade.exit_reason.lower()]
    order_count = len(orders)
    trade_count = len(trades)
    rejected_order_pct = _pct(len(rejected_orders), order_count)
    stop_loss_pct = _pct(len(stop_loss_trades), trade_count)
    blockers: list[str] = []
    warnings: list[str] = []

    if days < qa_config.min_days:
        blockers.append(f"observed_days {days} < required {qa_config.min_days}")
    if trade_count < qa_config.min_trades:
        blockers.append(f"trade_count {trade_count} < required {qa_config.min_trades}")
    if len(critical_errors) > qa_config.max_critical_errors:
        blockers.append(
            f"critical_error_count {len(critical_errors)} > allowed {qa_config.max_critical_errors}"
        )
    if rejected_order_pct > qa_config.max_rejected_order_pct:
        warnings.append(
            f"rejected_order_pct {rejected_order_pct:.2f}% > review threshold "
            f"{qa_config.max_rejected_order_pct:.2f}%"
        )
    if stop_loss_pct > qa_config.max_stop_loss_pct:
        warnings.append(
            f"stop_loss_pct {stop_loss_pct:.2f}% > review threshold {qa_config.max_stop_loss_pct:.2f}%"
        )

    return PaperStabilityReport(
        symbol=symbol,
        timeframe=timeframe,
        status="PAPER_STABLE" if not blockers else "BLOCKED",
        observed_days=days,
        trade_count=trade_count,
        order_count=order_count,
        rejected_order_count=len(rejected_orders),
        rejected_order_pct=rejected_order_pct,
        stop_loss_count=len(stop_loss_trades),
        stop_loss_pct=stop_loss_pct,
        net_pnl=sum(trade.net_pnl for trade in trades),
        critical_error_count=len(critical_errors),
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        blockers=blockers,
        warnings=warnings,
    )


def save_paper_stability_report(report: PaperStabilityReport, root: str | Path) -> Path:
    path = (
        Path(root)
        / "qa"
        / "paper_stability"
        / report.symbol.replace("/", "_")
        / report.timeframe
        / "report.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _paper_dir(root: Path, symbol: str, timeframe: str) -> Path:
    return root / "paper" / symbol.replace("/", "_") / timeframe


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _observed_days(
    trades: list[object],
    orders: list[dict[str, str]],
    account_rows: list[dict[str, str]],
) -> int:
    days: set[str] = set()
    for trade in trades:
        days.add(_date_from_ms(trade.entry_time_ms))
        days.add(_date_from_ms(trade.exit_time_ms))
    for order in orders:
        if order.get("open_time_ms"):
            days.add(_date_from_ms(int(order["open_time_ms"])))
    for row in account_rows:
        if row.get("open_time_ms"):
            days.add(_date_from_ms(int(row["open_time_ms"])))
    return len(days)


def _date_from_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()


def _pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return (part / whole) * 100.0
