from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig
from trading_bot.data_collector import CandleCsvStore
from trading_bot.demo.data_pack import seed_demo_data_pack


@dataclass(frozen=True)
class LocalDemoCheck:
    name: str
    status: str
    reason: str
    next_action: str


@dataclass(frozen=True)
class LocalDemoReport:
    status: str
    generated_at_utc: str
    seeded_demo_data: bool
    candle_rows: int
    paper_trades: int
    report_count: int
    live_locked: bool
    summary: str
    checks: list[LocalDemoCheck] = field(default_factory=list)


def build_local_demo_report(
    config: BotConfig,
    seed_demo_if_needed: bool = False,
    candles_per_pair: int = 180,
) -> LocalDemoReport:
    seeded = False
    candle_rows = _count_candle_rows(config)
    if seed_demo_if_needed and candle_rows == 0:
        seed_demo_data_pack(config, candles_per_pair=candles_per_pair)
        seeded = True
        candle_rows = _count_candle_rows(config)

    root = Path(config.data_root)
    paper_trades = _count_csv_rows(root / "paper", "trades.csv")
    report_count = len(list(root.rglob("*.json"))) if root.exists() else 0
    live_locked = not config.live_enabled and not config.approved_live
    checks = [
        LocalDemoCheck(
            "local_web",
            "PASS",
            "orchestrator runs on localhost when started",
            "Double-click start-bot-web.cmd jika browser belum terbuka",
        ),
        LocalDemoCheck(
            "config_safe",
            "PASS" if live_locked else "FAIL",
            "live disabled and approval off" if live_locked else "live flag or approval is enabled",
            "Pastikan live_enabled=false dan approved_live=false",
        ),
        LocalDemoCheck(
            "demo_candles",
            "PASS" if candle_rows > 0 else "TODO",
            f"candle rows={candle_rows}",
            "Klik Demo Data",
        ),
        LocalDemoCheck(
            "paper_trades",
            "PASS" if paper_trades > 0 else "TODO",
            f"paper trades={paper_trades}",
            "Klik Jalankan Siklus atau Evidence Campaign",
        ),
        LocalDemoCheck(
            "reports_available",
            "PASS" if report_count > 0 else "TODO",
            f"json reports={report_count}",
            "Klik Evidence Campaign atau Buat Dashboard",
        ),
        LocalDemoCheck(
            "pnl_monitor",
            "PASS" if paper_trades > 0 else "TODO",
            "P/L Visual Monitor has paper trades" if paper_trades > 0 else "P/L monitor waits for paper trades",
            "Lihat panel P/L Visual Monitor",
        ),
    ]
    blockers = [check for check in checks if check.status == "FAIL"]
    todos = [check for check in checks if check.status == "TODO"]
    status = "READY_FOR_LOCAL_DEMO" if not blockers and not todos else "LOCAL_DEMO_INCOMPLETE"
    return LocalDemoReport(
        status=status,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        seeded_demo_data=seeded,
        candle_rows=candle_rows,
        paper_trades=paper_trades,
        report_count=report_count,
        live_locked=live_locked,
        summary="local paper/demo path is ready" if status == "READY_FOR_LOCAL_DEMO" else f"{len(todos) + len(blockers)} demo item(s) need attention",
        checks=checks,
    )


def save_local_demo_report(report: LocalDemoReport, root: str | Path) -> Path:
    path = Path(root) / "demo" / "local_demo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _count_csv_rows(root: Path, filename: str) -> int:
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob(filename):
        if path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            total += sum(1 for _ in csv.DictReader(handle))
    return total


def _count_candle_rows(config: BotConfig) -> int:
    store = CandleCsvStore(config.data_root)
    total = 0
    for symbol in config.symbols:
        for timeframe in config.timeframes:
            total += len(store.load(symbol, timeframe))
    return total
