from __future__ import annotations

import json
import csv
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from trading_bot.config import ConfigError, load_config
from trading_bot.observability import AuditEvent, read_audit_events
from trading_bot.safety import activate_kill_switch, clear_kill_switch, read_kill_switch
from trading_bot.storage import DatabaseStatus, load_database_status


ACTIONS: dict[str, tuple[str, ...]] = {
    "validate_config": ("validate-config", "--config", "{config}"),
    "seed_demo_data": ("seed-demo-data", "--config", "{config}", "--candles-per-pair", "{limit}"),
    "local_demo": ("local-demo-report", "--config", "{config}", "--seed-demo-if-needed"),
    "vps_demo": ("vps-demo-report", "--config", "{config}"),
    "import_runtime_db": ("import-runtime-db", "--config", "{config}"),
    "db_learning_report": ("db-learning-report", "--config", "{config}", "--limit", "{limit}"),
    "skill_loop": ("skill-loop-report", "--config", "{config}"),
    "pattern_memory": ("pattern-memory-report", "--config", "{config}", "--limit", "{limit}"),
    "learning_dashboard": ("learning-dashboard-report", "--config", "{config}"),
    "human_feedback": ("human-feedback-report", "--config", "{config}"),
    "fundamental": ("fundamental-report", "--config", "{config}"),
    "experiment_scoreboard": ("experiment-scoreboard", "--config", "{config}"),
    "build_dashboard": ("build-dashboard", "--config", "{config}"),
    "security_qa": ("security-qa-report", "--config", "{config}", "--env-file", ".env.example", "--scan-root", "."),
    "production_smoke": ("production-smoke-report", "--config", "{config}"),
    "incident_drill": ("incident-drill-report", "--config", "{config}"),
    "live_go_no_go": ("live-go-no-go-report", "--config", "{config}"),
    "live_evidence": ("live-evidence-report", "--config", "{config}"),
    "evidence_campaign": ("evidence-campaign-report", "--config", "{config}", "--seed-demo-if-needed"),
    "testnet_demo": ("testnet-demo-report", "--config", "{config}", "--environment", "testnet"),
    "paper_campaign": ("paper-campaign-report", "--config", "{config}"),
    "run_cycle": ("run-cycle", "--config", "{config}", "--sync-latest", "--limit", "{limit}"),
    "sync_btc_15m": ("sync-ohlcv", "--config", "{config}", "--symbol", "BTC/USDT", "--timeframe", "15m", "--limit", "{limit}"),
    "sync_eth_15m": ("sync-ohlcv", "--config", "{config}", "--symbol", "ETH/USDT", "--timeframe", "15m", "--limit", "{limit}"),
}


@dataclass(frozen=True)
class OrchestratorStatus:
    mode: str
    live_enabled: bool
    approved_live: bool
    data_root: str
    kill_switch_active: bool
    kill_switch_reason: str
    dashboard_path: str
    security_status: str
    go_no_go_decision: str
    production_smoke_status: str
    action_running: bool
    running_action: str


@dataclass(frozen=True)
class OrchestratorActivity:
    action: str
    status: str
    exit_code: int
    output: str
    created_at_utc: str


@dataclass(frozen=True)
class HealthSummary:
    data_status: str
    data_reason: str
    paper_status: str
    paper_reason: str
    readiness_status: str
    readiness_reason: str
    safety_status: str
    safety_reason: str


@dataclass(frozen=True)
class SetupCheck:
    name: str
    status: str
    reason: str
    next_action: str


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    plain_meaning: str
    watch_for: str
    related_action: str


@dataclass(frozen=True)
class ReportItem:
    category: str
    name: str
    status: str
    summary: str
    path: str
    updated_at_utc: str
    size_bytes: int


@dataclass(frozen=True)
class IncidentPanel:
    kill_switch_active: bool
    kill_switch_reason: str
    kill_switch_created_at_utc: str
    incident_status: str
    incident_generated_at_utc: str
    scenario_count: int
    scenario_summary: str


@dataclass(frozen=True)
class DatabasePanel:
    db_path: str
    exists: bool
    size_bytes: int
    updated_at_utc: str
    total_rows: int
    table_rows: dict[str, int]


@dataclass(frozen=True)
class TestnetDemoPanel:
    report_path: str
    exists: bool
    status: str
    environment: str
    generated_at_utc: str
    order_count: int
    live_guard_status: str
    live_guard_reason: str
    orders: list[dict]
    notes: list[str]


@dataclass(frozen=True)
class LiveEvidencePanel:
    report_path: str
    exists: bool
    status: str
    completion_pct: float
    generated_at_utc: str
    blocker_count: int
    summary: str
    blockers: list[str]
    items: list[dict]


@dataclass(frozen=True)
class LocalDemoPanel:
    report_path: str
    exists: bool
    status: str
    generated_at_utc: str
    candle_rows: int
    paper_trades: int
    report_count: int
    live_locked: bool
    summary: str
    checks: list[dict]


@dataclass(frozen=True)
class VpsDemoPanel:
    report_path: str
    exists: bool
    status: str
    generated_at_utc: str
    vps_config_path: str
    private_url: str
    tunnel_url: str
    live_locked: bool
    summary: str
    checks: list[dict]


@dataclass(frozen=True)
class PaperCampaignPanel:
    report_path: str
    exists: bool
    status: str
    generated_at_utc: str
    completion_pct: float
    pairs_checked: int
    stable_pair_count: int
    total_trade_count: int
    total_net_pnl: float
    summary: str
    blockers: list[str]
    pairs: list[dict]


@dataclass(frozen=True)
class SkillLoopPanel:
    report_path: str
    exists: bool
    status: str
    generated_at_utc: str
    candle_rows: int
    paper_trades: int
    paper_net_pnl: float
    learning_rows: int
    evidence_completion_pct: float
    paper_campaign_status: str
    summary: str
    guardrail: str
    experiment_candidates: list[str]
    steps: list[dict]


@dataclass(frozen=True)
class PatternMemoryPanel:
    report_path: str
    exists: bool
    status: str
    generated_at_utc: str
    row_count: int
    total_trades: int
    total_labels: int
    summary: str
    guardrail: str
    rows: list[dict]


@dataclass(frozen=True)
class LearningDashboardPanel:
    report_path: str
    exists: bool
    status: str
    generated_at_utc: str
    trend_count: int
    promising_count: int
    weak_count: int
    volume_spike_count: int
    average_evidence_score: float
    live_evidence_completion_pct: float
    paper_campaign_completion_pct: float
    summary: str
    guardrail: str
    trends: list[dict]


@dataclass(frozen=True)
class HumanFeedbackPanel:
    report_path: str
    exists: bool
    status: str
    generated_at_utc: str
    label_path: str
    total_labels: int
    pairs_labeled: int
    top_label: str
    summary: str
    guardrail: str
    allowed_labels: list[str]
    label_counts: dict[str, int]
    recent_labels: list[dict]
    lessons: list[dict]


@dataclass(frozen=True)
class FundamentalPanel:
    report_path: str
    exists: bool
    status: str
    generated_at_utc: str
    event_path: str
    total_events: int
    high_or_block_events: int
    top_risk: str
    color: str
    summary: str
    guardrail: str
    risk_counts: dict[str, int]
    category_counts: dict[str, int]
    events: list[dict]


@dataclass(frozen=True)
class ExperimentScoreboardPanel:
    report_path: str
    exists: bool
    status: str
    generated_at_utc: str
    registry_path: str
    experiment_count: int
    top_strategy: str
    summary: str
    guardrail: str
    rows: list[dict]


@dataclass(frozen=True)
class BeginnerStep:
    number: int
    title: str
    status: str
    plain_text: str
    help_text: str
    action_label: str


@dataclass(frozen=True)
class DemoWalkthroughStep:
    number: int
    title: str
    status: str
    goal: str
    action_label: str
    help_text: str


@dataclass(frozen=True)
class PnlTradeRow:
    symbol: str
    timeframe: str
    exit_time: str
    entry_price: float
    exit_price: float
    net_pnl: float
    exit_reason: str


@dataclass(frozen=True)
class DailyPnlRow:
    date: str
    trade_count: int
    net_pnl: float
    best_trade_pnl: float
    worst_trade_pnl: float
    result: str


@dataclass(frozen=True)
class PnlPanel:
    trade_count: int
    win_rate_pct: float
    net_pnl: float
    initial_equity: float
    latest_equity: float
    equity_change_pct: float
    best_trade_pnl: float
    worst_trade_pnl: float
    latest_trade: PnlTradeRow | None
    equity_points: list[float]
    daily_rows: list[DailyPnlRow]


@dataclass(frozen=True)
class MarketFeedRow:
    symbol: str
    timeframe: str
    candle_count: int
    latest_open_utc: str
    latest_close: float
    source: str
    status: str
    reason: str


@dataclass(frozen=True)
class MarketFeedPanel:
    rows: list[MarketFeedRow]


@dataclass(frozen=True)
class PaperExecutionRow:
    time_utc: str
    symbol: str
    timeframe: str
    action: str
    side: str
    status: str
    price: float
    quantity: float
    notional: float
    fee: float
    reason: str


@dataclass(frozen=True)
class PaperPositionSnapshot:
    time_utc: str
    equity: float
    day_start_equity: float
    open_positions: int
    trading_status: str
    status_reason: str


@dataclass(frozen=True)
class PaperExecutionPanel:
    order_count: int
    filled_count: int
    rejected_count: int
    latest_snapshot: PaperPositionSnapshot | None
    latest_rows: list[PaperExecutionRow]


def load_orchestrator_status(config_path: str | Path = "config/bot.sample.toml") -> OrchestratorStatus:
    config = load_config(Path(config_path))
    kill_switch = read_kill_switch(config.data_root)
    root = Path(config.data_root)
    return OrchestratorStatus(
        mode=config.mode,
        live_enabled=config.live_enabled,
        approved_live=config.approved_live,
        data_root=str(config.data_root),
        kill_switch_active=kill_switch.active,
        kill_switch_reason=kill_switch.reason,
        dashboard_path=str(root / "dashboard" / "index.html"),
        security_status=_json_value(root / "qa" / "security" / "report.json", "status", "MISSING"),
        go_no_go_decision=_json_value(root / "qa" / "live_go_no_go" / "report.json", "decision", "MISSING"),
        production_smoke_status=_json_value(root / "qa" / "production_smoke" / "report.json", "status", "MISSING"),
        action_running=_lock_path(root).exists(),
        running_action=_running_action(root),
    )


def load_market_feed_panel(config_path: str | Path = "config/bot.sample.toml") -> MarketFeedPanel:
    config = load_config(Path(config_path))
    root = Path(config.data_root)
    rows: list[MarketFeedRow] = []
    for symbol in config.symbols:
        for timeframe in config.timeframes:
            candle_rows = _read_candle_rows(root, symbol, timeframe)
            latest = candle_rows[-1] if candle_rows else {}
            latest_time = _format_ms(str(latest.get("open_time_ms", ""))) if latest else "-"
            latest_close = _safe_float(str(latest.get("close", "0"))) if latest else 0.0
            source = str(latest.get("source") or "-") if latest else "-"
            status = "OK" if candle_rows else "MISSING"
            reason = (
                f"latest candle from {source}"
                if candle_rows
                else "belum ada candle lokal; klik Jalankan Siklus atau Sinkron"
            )
            rows.append(
                MarketFeedRow(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_count=len(candle_rows),
                    latest_open_utc=latest_time,
                    latest_close=latest_close,
                    source=source,
                    status=status,
                    reason=reason,
                )
            )
    return MarketFeedPanel(rows)


def load_paper_execution_panel(config_path: str | Path = "config/bot.sample.toml", limit: int = 8) -> PaperExecutionPanel:
    config = load_config(Path(config_path))
    paper_root = Path(config.data_root) / "paper"
    rows = _load_paper_order_rows(paper_root)
    filled = sum(1 for row in rows if row.status == "FILLED")
    rejected = sum(1 for row in rows if row.status == "REJECTED")
    latest = sorted(rows, key=lambda row: row.time_utc, reverse=True)[:limit]
    return PaperExecutionPanel(
        order_count=len(rows),
        filled_count=filled,
        rejected_count=rejected,
        latest_snapshot=_load_latest_position_snapshot(paper_root),
        latest_rows=latest,
    )


def load_setup_wizard(config_path: str | Path = "config/bot.sample.toml") -> list[SetupCheck]:
    checks: list[SetupCheck] = []
    try:
        config = load_config(Path(config_path))
        root = Path(config.data_root)
        checks.append(SetupCheck("Config", "PASS", "file config valid", ""))
        checks.append(
            SetupCheck(
                "Live Guard",
                "PASS" if not config.live_enabled else "FAIL",
                "live nonaktif" if not config.live_enabled else "live wajib nonaktif",
                "Pastikan BOT_LIVE_ENABLED=false",
            )
        )
        checks.append(
            SetupCheck(
                "Data Root",
                "PASS" if root.exists() else "TODO",
                str(root),
                "Klik Demo Data atau Sinkron untuk membuat data",
            )
        )
        checks.append(
            SetupCheck(
                "Demo Data",
                "PASS" if list(root.glob("*/*.csv")) else "TODO",
                "sample candle tersedia" if list(root.glob("*/*.csv")) else "belum ada sample candle",
                "Klik Demo Data",
            )
        )
        checks.append(
            SetupCheck(
                "Security QA",
                "PASS" if _json_value(root / "qa" / "security" / "report.json", "status", "") == "PASSED" else "TODO",
                _json_value(root / "qa" / "security" / "report.json", "status", "missing"),
                "Klik Security QA",
            )
        )
        checks.append(
            SetupCheck(
                "Dashboard",
                "PASS" if (root / "dashboard" / "index.html").exists() else "TODO",
                str(root / "dashboard" / "index.html"),
                "Klik Buat Dashboard",
            )
        )
        checks.append(
            SetupCheck(
                "Database",
                "PASS" if (root / "bot.sqlite3").exists() else "TODO",
                str(root / "bot.sqlite3"),
                "Klik Import DB",
            )
        )
        checks.append(
            SetupCheck(
                "First Run",
                "PASS" if recent_activities(root, limit=1) else "TODO",
                "aktivitas orchestrator sudah ada" if recent_activities(root, limit=1) else "belum ada aksi UI",
                "Klik Validasi Config, lalu Jalankan Siklus",
            )
        )
    except (ConfigError, ValueError) as exc:
        checks.append(SetupCheck("Config", "FAIL", str(exc), "Perbaiki file config"))
    return checks


def load_report_browser(config_path: str | Path = "config/bot.sample.toml") -> list[ReportItem]:
    config = load_config(Path(config_path))
    root = Path(config.data_root)
    reports: list[ReportItem] = []
    reports.extend(_json_report_items(root / "backtests", "Backtest", "metrics.json"))
    reports.extend(_json_report_items(root / "validation" / "walk_forward", "Walk-Forward", "*.json"))
    reports.extend(_paper_report_items(root / "paper"))
    reports.extend(_json_report_items(root / "reports" / "daily", "Daily Journal", "*.json"))
    reports.extend(_json_report_items(root / "reports" / "learning", "Learning", "*.json"))
    reports.extend(_json_report_items(root / "execution" / "testnet_demo", "Testnet Demo", "*.json"))
    reports.extend(_json_report_items(root / "readiness", "Readiness", "*.json"))
    return sorted(reports, key=lambda item: item.updated_at_utc, reverse=True)


def load_incident_panel(config_path: str | Path = "config/bot.sample.toml") -> IncidentPanel:
    config = load_config(Path(config_path))
    root = Path(config.data_root)
    kill_switch = read_kill_switch(root)
    report = _read_json(root / "qa" / "incident_drill" / "report.json") or {}
    scenarios = report.get("scenarios", [])
    scenario_names = []
    if isinstance(scenarios, list):
        for scenario in scenarios:
            if isinstance(scenario, dict):
                scenario_names.append(f"{scenario.get('name', 'unknown')}={scenario.get('status', 'UNKNOWN')}")
    return IncidentPanel(
        kill_switch_active=kill_switch.active,
        kill_switch_reason=kill_switch.reason,
        kill_switch_created_at_utc=kill_switch.created_at_utc or "",
        incident_status=str(report.get("status", "MISSING")),
        incident_generated_at_utc=str(report.get("generated_at_utc", "")),
        scenario_count=len(scenario_names),
        scenario_summary=", ".join(scenario_names) if scenario_names else "belum ada laporan incident drill",
    )


def load_glossary_entries() -> list[GlossaryEntry]:
    return [
        GlossaryEntry("Paper/Demo", "Simulasi trading tanpa uang asli.", "Hasil bagus belum berarti boleh live.", "Paper Campaign"),
        GlossaryEntry("P/L", "Profit atau rugi dari trade demo/paper.", "Hijau belum cukup jika sample trade kecil.", "P/L Visual Monitor"),
        GlossaryEntry("Evidence", "Bukti kesiapan sebelum bot boleh direview untuk live.", "Jika belum 100%, real live tetap terkunci.", "Live Evidence"),
        GlossaryEntry("Evidence Score", "Skor prioritas review, bukan izin live.", "Score rendah berarti butuh data/paper tambahan.", "Learning Dashboard"),
        GlossaryEntry("BUTUH PAPER", "Pola masih perlu lebih banyak simulasi trade.", "Minimal 20 paper trade per pair/timeframe.", "Paper Campaign"),
        GlossaryEntry("Pattern Memory", "Catatan pola dan outcome paper yang pernah terjadi.", "Tambahkan label manual setelah review chart.", "Pattern Memory"),
        GlossaryEntry("Skill Loop", "Siklus belajar bot dari data, pola, trade, dan evidence.", "Tidak boleh otomatis membuka live order.", "Skill Loop"),
        GlossaryEntry("Kill Switch", "Rem darurat untuk memblokir aktivitas bot.", "Aktifkan jika ada error, rugi besar, atau market tidak normal.", "Kill Switch"),
        GlossaryEntry("Go/No-Go", "Keputusan siap/tidak siap untuk review live.", "NO_GO berarti jangan live.", "Live Go/No-Go"),
        GlossaryEntry("Volume Spike", "Volume tiba-tiba lebih besar dari rata-rata.", "Bisa sinyal penting, tapi perlu konfirmasi.", "Learning Dashboard"),
    ]


def load_database_panel(config_path: str | Path = "config/bot.sample.toml") -> DatabasePanel:
    config = load_config(Path(config_path))
    return _database_panel_from_status(load_database_status(config.data_root))


def load_testnet_demo_panel(config_path: str | Path = "config/bot.sample.toml") -> TestnetDemoPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "execution" / "testnet_demo" / "report.json"
    payload = _read_json(path) or {}
    orders = payload.get("orders", [])
    notes = payload.get("notes", [])
    return TestnetDemoPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        environment=str(payload.get("environment", "")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        order_count=len(orders) if isinstance(orders, list) else 0,
        live_guard_status=str(payload.get("live_guard_status", "MISSING")),
        live_guard_reason=str(payload.get("live_guard_reason", "")),
        orders=orders if isinstance(orders, list) else [],
        notes=notes if isinstance(notes, list) else [],
    )


def load_live_evidence_panel(config_path: str | Path = "config/bot.sample.toml") -> LiveEvidencePanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "readiness" / "live_evidence.json"
    payload = _read_json(path) or {}
    blockers = payload.get("blockers", [])
    items = payload.get("items", [])
    return LiveEvidencePanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        completion_pct=float(payload.get("completion_pct", 0) or 0),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        blocker_count=len(blockers) if isinstance(blockers, list) else 0,
        summary=str(payload.get("summary", "")),
        blockers=blockers if isinstance(blockers, list) else [],
        items=items if isinstance(items, list) else [],
    )


def load_local_demo_panel(config_path: str | Path = "config/bot.sample.toml") -> LocalDemoPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "demo" / "local_demo.json"
    payload = _read_json(path) or {}
    return LocalDemoPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        candle_rows=int(payload.get("candle_rows", 0) or 0),
        paper_trades=int(payload.get("paper_trades", 0) or 0),
        report_count=int(payload.get("report_count", 0) or 0),
        live_locked=bool(payload.get("live_locked", False)),
        summary=str(payload.get("summary", "Klik Local Demo untuk membuat report demo lokal.")),
        checks=list(payload.get("checks", [])) if isinstance(payload.get("checks", []), list) else [],
    )


def load_paper_campaign_panel(config_path: str | Path = "config/bot.sample.toml") -> PaperCampaignPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "qa" / "paper_campaign" / "report.json"
    payload = _read_json(path) or {}
    return PaperCampaignPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        completion_pct=float(payload.get("completion_pct", 0) or 0),
        pairs_checked=int(payload.get("pairs_checked", 0) or 0),
        stable_pair_count=int(payload.get("stable_pair_count", 0) or 0),
        total_trade_count=int(payload.get("total_trade_count", 0) or 0),
        total_net_pnl=float(payload.get("total_net_pnl", 0) or 0),
        summary=str(payload.get("summary", "Klik Paper Campaign untuk membuat tracker evidence.")),
        blockers=list(payload.get("blockers", [])) if isinstance(payload.get("blockers", []), list) else [],
        pairs=list(payload.get("pairs", [])) if isinstance(payload.get("pairs", []), list) else [],
    )


def load_vps_demo_panel(config_path: str | Path = "config/bot.sample.toml") -> VpsDemoPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "demo" / "vps_demo.json"
    payload = _read_json(path) or {}
    return VpsDemoPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        vps_config_path=str(payload.get("vps_config_path", "")),
        private_url=str(payload.get("private_url", "")),
        tunnel_url=str(payload.get("tunnel_url", "")),
        live_locked=bool(payload.get("live_locked", False)),
        summary=str(payload.get("summary", "Klik VPS Demo untuk membuat readiness report.")),
        checks=list(payload.get("checks", [])) if isinstance(payload.get("checks", []), list) else [],
    )


def load_skill_loop_panel(config_path: str | Path = "config/bot.sample.toml") -> SkillLoopPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "reports" / "learning" / "skill_loop.json"
    payload = _read_json(path) or {}
    return SkillLoopPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        candle_rows=int(payload.get("candle_rows", 0) or 0),
        paper_trades=int(payload.get("paper_trades", 0) or 0),
        paper_net_pnl=float(payload.get("paper_net_pnl", 0) or 0),
        learning_rows=int(payload.get("learning_rows", 0) or 0),
        evidence_completion_pct=float(payload.get("evidence_completion_pct", 0) or 0),
        paper_campaign_status=str(payload.get("paper_campaign_status", "MISSING")),
        summary=str(payload.get("summary", "Klik Skill Loop untuk membuat report pembelajaran.")),
        guardrail=str(payload.get("guardrail", "Research only. No live orders.")),
        experiment_candidates=list(payload.get("experiment_candidates", [])) if isinstance(payload.get("experiment_candidates", []), list) else [],
        steps=list(payload.get("steps", [])) if isinstance(payload.get("steps", []), list) else [],
    )


def load_pattern_memory_panel(config_path: str | Path = "config/bot.sample.toml") -> PatternMemoryPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "reports" / "learning" / "pattern_memory.json"
    payload = _read_json(path) or {}
    return PatternMemoryPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        row_count=int(payload.get("row_count", 0) or 0),
        total_trades=int(payload.get("total_trades", 0) or 0),
        total_labels=int(payload.get("total_labels", 0) or 0),
        summary=str(payload.get("summary", "Klik Pattern Memory untuk membuat review outcome pola.")),
        guardrail=str(payload.get("guardrail", "Review only. No live orders.")),
        rows=list(payload.get("rows", [])) if isinstance(payload.get("rows", []), list) else [],
    )


def load_learning_dashboard_panel(config_path: str | Path = "config/bot.sample.toml") -> LearningDashboardPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "reports" / "learning" / "learning_dashboard.json"
    payload = _read_json(path) or {}
    return LearningDashboardPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        trend_count=int(payload.get("trend_count", 0) or 0),
        promising_count=int(payload.get("promising_count", 0) or 0),
        weak_count=int(payload.get("weak_count", 0) or 0),
        volume_spike_count=int(payload.get("volume_spike_count", 0) or 0),
        average_evidence_score=float(payload.get("average_evidence_score", 0) or 0),
        live_evidence_completion_pct=float(payload.get("live_evidence_completion_pct", 0) or 0),
        paper_campaign_completion_pct=float(payload.get("paper_campaign_completion_pct", 0) or 0),
        summary=str(payload.get("summary", "Klik Learning Dashboard untuk membuat ringkasan belajar.")),
        guardrail=str(payload.get("guardrail", "Read-only research. No live execution.")),
        trends=list(payload.get("trends", [])) if isinstance(payload.get("trends", []), list) else [],
    )


def load_human_feedback_panel(config_path: str | Path = "config/bot.sample.toml") -> HumanFeedbackPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "reports" / "learning" / "human_feedback.json"
    payload = _read_json(path) or {}
    return HumanFeedbackPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        label_path=str(payload.get("label_path", Path(config.data_root) / "reports" / "learning" / "manual_labels.json")),
        total_labels=int(payload.get("total_labels", 0) or 0),
        pairs_labeled=int(payload.get("pairs_labeled", 0) or 0),
        top_label=str(payload.get("top_label", "-")),
        summary=str(payload.get("summary", "Klik Human Feedback setelah menambah label manual.")),
        guardrail=str(payload.get("guardrail", "Feedback is review-only. No live orders.")),
        allowed_labels=list(payload.get("allowed_labels", [])) if isinstance(payload.get("allowed_labels", []), list) else [],
        label_counts=dict(payload.get("label_counts", {})) if isinstance(payload.get("label_counts", {}), dict) else {},
        recent_labels=list(payload.get("recent_labels", [])) if isinstance(payload.get("recent_labels", []), list) else [],
        lessons=list(payload.get("lessons", [])) if isinstance(payload.get("lessons", []), list) else [],
    )


def load_fundamental_panel(config_path: str | Path = "config/bot.sample.toml") -> FundamentalPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "reports" / "fundamental" / "report.json"
    payload = _read_json(path) or {}
    return FundamentalPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        event_path=str(payload.get("event_path", Path(config.data_root) / "reports" / "fundamental" / "events.json")),
        total_events=int(payload.get("total_events", 0) or 0),
        high_or_block_events=int(payload.get("high_or_block_events", 0) or 0),
        top_risk=str(payload.get("top_risk", "LOW")),
        color=str(payload.get("color", "green")),
        summary=str(payload.get("summary", "Klik Fundamental untuk refresh event lane.")),
        guardrail=str(payload.get("guardrail", "Fundamental lane is review-only. No live orders.")),
        risk_counts=dict(payload.get("risk_counts", {})) if isinstance(payload.get("risk_counts", {}), dict) else {},
        category_counts=dict(payload.get("category_counts", {})) if isinstance(payload.get("category_counts", {}), dict) else {},
        events=list(payload.get("events", [])) if isinstance(payload.get("events", []), list) else [],
    )


def load_experiment_scoreboard_panel(config_path: str | Path = "config/bot.sample.toml") -> ExperimentScoreboardPanel:
    config = load_config(Path(config_path))
    path = Path(config.data_root) / "reports" / "learning" / "experiment_scoreboard.json"
    payload = _read_json(path) or {}
    return ExperimentScoreboardPanel(
        report_path=str(path),
        exists=path.exists(),
        status=str(payload.get("status", "MISSING")),
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        registry_path=str(payload.get("registry_path", Path(config.data_root) / "reports" / "learning" / "strategy_experiments.json")),
        experiment_count=int(payload.get("experiment_count", 0) or 0),
        top_strategy=str(payload.get("top_strategy", "-")),
        summary=str(payload.get("summary", "Klik Experiment Scoreboard untuk refresh registry eksperimen.")),
        guardrail=str(payload.get("guardrail", "Experiment registry is review-only. No live orders.")),
        rows=list(payload.get("rows", [])) if isinstance(payload.get("rows", []), list) else [],
    )


def load_pnl_panel(config_path: str | Path = "config/bot.sample.toml") -> PnlPanel:
    config = load_config(Path(config_path))
    root = Path(config.data_root) / "paper"
    trades = _load_paper_trade_rows(root)
    equity_series = _load_equity_series(root)
    equity_points = _aggregate_equity_points(equity_series, 48)
    win_count = sum(1 for trade in trades if trade.net_pnl > 0)
    net_pnl = sum(trade.net_pnl for trade in trades)
    initial_equity = sum(series[0] for series in equity_series if series)
    latest_equity = sum(series[-1] for series in equity_series if series)
    equity_change_pct = ((latest_equity - initial_equity) / initial_equity * 100) if initial_equity else 0.0
    return PnlPanel(
        trade_count=len(trades),
        win_rate_pct=(win_count / len(trades) * 100) if trades else 0.0,
        net_pnl=net_pnl,
        initial_equity=initial_equity,
        latest_equity=latest_equity,
        equity_change_pct=equity_change_pct,
        best_trade_pnl=max((trade.net_pnl for trade in trades), default=0.0),
        worst_trade_pnl=min((trade.net_pnl for trade in trades), default=0.0),
        latest_trade=trades[-1] if trades else None,
        equity_points=equity_points,
        daily_rows=_aggregate_daily_pnl_rows(trades),
    )


def load_demo_walkthrough(config_path: str | Path = "config/bot.sample.toml") -> list[DemoWalkthroughStep]:
    setup = {check.name: check for check in load_setup_wizard(config_path)}
    status = load_orchestrator_status(config_path)
    pnl = load_pnl_panel(config_path)
    live_evidence = load_live_evidence_panel(config_path)
    config = load_config(Path(config_path))
    campaign_path = Path(config.data_root) / "readiness" / "evidence_campaign.json"

    return [
        DemoWalkthroughStep(
            1,
            "Buka Web Lokal",
            "PASS",
            "Pastikan halaman ini bisa dibuka di browser.",
            "Buka 127.0.0.1:8000",
            "Kalau browser refused, jalankan start-bot-web.cmd dari root project.",
        ),
        DemoWalkthroughStep(
            2,
            "Cek Config",
            _walkthrough_status(setup.get("Config")),
            "Pastikan bot membaca config yang benar dan live tetap nonaktif.",
            "Klik Validasi Config",
            "Langkah ini belum trading. Ini hanya cek file config dan mode aman.",
        ),
        DemoWalkthroughStep(
            3,
            "Isi Data Demo",
            _walkthrough_status(setup.get("Demo Data")),
            "Siapkan candle, paper trade, dan laporan contoh agar panel tidak kosong.",
            "Klik Demo Data",
            "Data demo dipakai untuk belajar UI dan QA, bukan data real live account.",
        ),
        DemoWalkthroughStep(
            4,
            "Jalankan Evidence",
            "PASS" if campaign_path.exists() else "TODO",
            "Refresh bukti data quality, backtest, paper, readiness, dan live evidence.",
            "Klik Evidence Campaign",
            "Kalau status masih incomplete, itu normal sampai bukti paper cukup.",
        ),
        DemoWalkthroughStep(
            5,
            "Pantau P/L",
            "PASS" if pnl.trade_count > 0 else "TODO",
            "Lihat realized P/L demo, win rate, equity curve, dan trade terakhir.",
            "Lihat P/L Visual Monitor",
            "P/L di sini dari paper/demo. Warna hijau/merah membantu membaca hasil.",
        ),
        DemoWalkthroughStep(
            6,
            "Review Go Live",
            "PASS" if live_evidence.exists and live_evidence.status in {"READY", "READY_FOR_MANUAL_REVIEW"} else "TODO",
            "Baca blocker sebelum membahas live kecil dengan modal real.",
            "Klik Live Evidence",
            f"Mode sekarang {status.mode}. Real live tetap terkunci sampai owner approval dan semua gate lulus.",
        ),
    ]


def update_kill_switch_from_web(
    action: str,
    reason: str,
    config_path: str | Path = "config/bot.sample.toml",
) -> IncidentPanel:
    config = load_config(Path(config_path))
    if action == "activate":
        activate_kill_switch(config.data_root, reason)
    elif action == "clear":
        clear_kill_switch(config.data_root)
    else:
        raise ValueError(f"unsupported kill switch action: {action}")
    return load_incident_panel(config_path)


def load_health_summary(config_path: str | Path = "config/bot.sample.toml") -> HealthSummary:
    config = load_config(Path(config_path))
    root = Path(config.data_root)
    kill_switch = read_kill_switch(root)
    data_reports = _json_reports(root / "qa" / "data_quality_gate")
    blocked_data = [report for report in data_reports if report.get("status") == "BLOCKED"]
    paper_trades = _count_csv_rows(root / "paper", "trades.csv")
    paper_pnl = _sum_csv_float(root / "paper", "trades.csv", "net_pnl")
    go_no_go = _json_value(root / "qa" / "live_go_no_go" / "report.json", "decision", "MISSING")
    readiness = _json_value(root / "readiness" / "live_readiness.json", "status", "MISSING")
    security = _json_value(root / "qa" / "security" / "report.json", "status", "MISSING")

    return HealthSummary(
        data_status="BLOCKED" if blocked_data else "OK" if data_reports else "MISSING",
        data_reason=f"{len(blocked_data)} blocked report(s)" if blocked_data else f"{len(data_reports)} report(s)",
        paper_status="ACTIVE" if paper_trades else "NO_TRADES",
        paper_reason=f"trades={paper_trades}, net_pnl={paper_pnl:.8f}",
        readiness_status=go_no_go,
        readiness_reason=f"live_readiness={readiness}",
        safety_status="BLOCKED" if kill_switch.active or config.live_enabled else "SAFE",
        safety_reason=(
            f"kill_switch={kill_switch.active}, live_enabled={config.live_enabled}, security={security}"
        ),
    )


def run_orchestrator_action(
    action: str,
    config_path: str | Path = "config/bot.sample.toml",
    cwd: str | Path | None = None,
    timeout_seconds: int = 180,
    limit: int = 10,
) -> OrchestratorActivity:
    if action not in ACTIONS:
        raise ValueError(f"unsupported action: {action}")
    cwd_path = Path(cwd) if cwd is not None else Path.cwd()
    config = load_config(Path(config_path))
    root = Path(config.data_root)
    lock = _lock_path(root)
    if lock.exists():
        raise ValueError(f"another action is already running: {_running_action(root)}")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"action": action, "created_at_utc": _now_utc()}), encoding="utf-8")
    try:
        safe_limit = max(1, min(int(limit), 1000))
        command_args = [part.format(config=str(config_path), limit=str(safe_limit)) for part in ACTIONS[action]]
        completed = subprocess.run(
            [sys.executable, "-m", "trading_bot.cli", *command_args],
            cwd=str(cwd_path),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = (completed.stdout + completed.stderr).strip()
        activity = OrchestratorActivity(
            action=action,
            status="SUCCESS" if completed.returncode == 0 else "FAILED",
            exit_code=completed.returncode,
            output=output[-6000:],
            created_at_utc=_now_utc(),
        )
        _append_activity(root, activity)
        return activity
    finally:
        if lock.exists():
            lock.unlink()


def recent_activities(root: str | Path, limit: int = 10) -> list[OrchestratorActivity]:
    path = _activity_path(Path(root))
    if not path.exists():
        return []
    rows: list[OrchestratorActivity] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        if not line.strip():
            continue
        payload = json.loads(line)
        rows.append(OrchestratorActivity(**payload))
    return list(reversed(rows))


def recent_audit_events(
    root: str | Path,
    level: str = "",
    symbol: str = "",
    timeframe: str = "",
    limit: int = 30,
) -> list[AuditEvent]:
    events = read_audit_events(root)
    filtered: list[AuditEvent] = []
    level_filter = level.upper()
    for event in reversed(events):
        if level_filter and event.level.upper() != level_filter:
            continue
        if symbol and str(event.context.get("symbol", "")) != symbol:
            continue
        if timeframe and str(event.context.get("timeframe", "")) != timeframe:
            continue
        filtered.append(event)
        if len(filtered) >= limit:
            break
    return filtered


def build_orchestrator_page(
    status: OrchestratorStatus,
    activities: list[OrchestratorActivity] | None = None,
    audit_events: list[AuditEvent] | None = None,
    health: HealthSummary | None = None,
    setup_checks: list[SetupCheck] | None = None,
    reports: list[ReportItem] | None = None,
    glossary: list[GlossaryEntry] | None = None,
    incident: IncidentPanel | None = None,
    database: DatabasePanel | None = None,
    testnet_demo: TestnetDemoPanel | None = None,
    live_evidence: LiveEvidencePanel | None = None,
    local_demo: LocalDemoPanel | None = None,
    vps_demo: VpsDemoPanel | None = None,
    paper_campaign: PaperCampaignPanel | None = None,
    skill_loop: SkillLoopPanel | None = None,
    pattern_memory: PatternMemoryPanel | None = None,
    learning_dashboard: LearningDashboardPanel | None = None,
    human_feedback: HumanFeedbackPanel | None = None,
    fundamental: FundamentalPanel | None = None,
    experiment_scoreboard: ExperimentScoreboardPanel | None = None,
    pnl: PnlPanel | None = None,
    market_feed: MarketFeedPanel | None = None,
    paper_execution: PaperExecutionPanel | None = None,
    walkthrough: list[DemoWalkthroughStep] | None = None,
) -> str:
    activities = activities or []
    audit_events = audit_events or []
    health = health or HealthSummary("MISSING", "", "MISSING", "", "MISSING", "", "MISSING", "")
    setup_checks = setup_checks or []
    reports = reports or []
    glossary = glossary or load_glossary_entries()
    incident = incident or IncidentPanel(False, "", "", "MISSING", "", 0, "belum ada laporan incident drill")
    database = database or DatabasePanel("", False, 0, "", 0, {})
    testnet_demo = testnet_demo or TestnetDemoPanel("", False, "MISSING", "", "", 0, "MISSING", "", [], [])
    live_evidence = live_evidence or LiveEvidencePanel("", False, "MISSING", 0, "", 0, "", [], [])
    local_demo = local_demo or LocalDemoPanel("", False, "MISSING", "", 0, 0, 0, False, "", [])
    vps_demo = vps_demo or VpsDemoPanel("", False, "MISSING", "", "", "", "", False, "", [])
    paper_campaign = paper_campaign or PaperCampaignPanel("", False, "MISSING", "", 0, 0, 0, 0, 0, "", [], [])
    skill_loop = skill_loop or SkillLoopPanel("", False, "MISSING", "", 0, 0, 0, 0, 0, "MISSING", "", "Research only. No live orders.", [], [])
    pattern_memory = pattern_memory or PatternMemoryPanel("", False, "MISSING", "", 0, 0, 0, "", "Review only. No live orders.", [])
    learning_dashboard = learning_dashboard or LearningDashboardPanel("", False, "MISSING", "", 0, 0, 0, 0, 0, 0, 0, "", "Read-only research. No live execution.", [])
    human_feedback = human_feedback or HumanFeedbackPanel("", False, "MISSING", "", "", 0, 0, "-", "", "Feedback is review-only. No live orders.", [], {}, [], [])
    fundamental = fundamental or FundamentalPanel("", False, "MISSING", "", "", 0, 0, "LOW", "green", "", "Fundamental lane is review-only. No live orders.", {}, {}, [])
    experiment_scoreboard = experiment_scoreboard or ExperimentScoreboardPanel("", False, "MISSING", "", "", 0, "-", "", "Experiment registry is review-only. No live orders.", [])
    pnl = pnl or PnlPanel(0, 0, 0, 0, 0, 0, 0, 0, None, [], [])
    market_feed = market_feed or MarketFeedPanel([])
    paper_execution = paper_execution or PaperExecutionPanel(0, 0, 0, None, [])
    walkthrough = walkthrough or []
    action_buttons = "".join(_action_button(action, status.action_running) for action in ACTIONS)
    activity_html = _activity_html(activities)
    audit_html = _audit_html(audit_events)
    health_html = _health_html(health)
    setup_html = _setup_html(setup_checks)
    reports_html = _reports_html(reports)
    glossary_html = _glossary_html(glossary)
    incident_html = _incident_html(incident)
    database_html = _database_html(database)
    testnet_demo_html = _testnet_demo_html(testnet_demo)
    live_evidence_html = _live_evidence_html(live_evidence)
    local_demo_html = _local_demo_html(local_demo)
    vps_demo_html = _vps_demo_html(vps_demo)
    paper_campaign_html = _paper_campaign_html(paper_campaign)
    skill_loop_html = _skill_loop_html(skill_loop)
    pattern_memory_html = _pattern_memory_html(pattern_memory)
    learning_dashboard_html = _learning_dashboard_html(learning_dashboard)
    human_feedback_html = _human_feedback_html(human_feedback)
    fundamental_html = _fundamental_html(fundamental)
    experiment_scoreboard_html = _experiment_scoreboard_html(experiment_scoreboard)
    beginner_html = _beginner_control_room_html(status, health, live_evidence)
    getting_started_html = _getting_started_html(status)
    pnl_html = _pnl_panel_html(pnl)
    market_feed_html = _market_feed_html(market_feed)
    paper_execution_html = _paper_execution_html(paper_execution)
    walkthrough_html = _demo_walkthrough_html(walkthrough)
    safety_class = "danger" if status.live_enabled or status.kill_switch_active else "ok"
    live_text = "LIVE AKTIF" if status.live_enabled else "Live Nonaktif"
    kill_text = "AKTIF" if status.kill_switch_active else "Clear"
    current_action = status.running_action if status.action_running else "siap"
    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Orchestrator Bot Trading</title>
  <link rel="preconnect" href="https://fonts.bunny.net">
  <link href="https://fonts.bunny.net/css?family=inter:400,500,600,700,800" rel="stylesheet">
  <style>
    :root {{
      --primary-dark: #071a3d;
      --primary-light: #123b7a;
      --primary-soft: #eaf2ff;
      --page: #f6f8fb;
      --panel: #ffffff;
      --ink: #1e293b;
      --muted: #64748b;
      --line: #d8e2ee;
      --soft-line: #e3ebf5;
      --toolbar: #f1f5f9;
      --good: #15803d;
      --bad: #dc2626;
      --warn: #d97706;
      --focus: #123b7a;
      --shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--page); color: var(--ink); }}
    h1 {{ margin: 0; font-size: 24px; line-height: 1.2; letter-spacing: 0; font-weight: 800; }}
    .shell {{ max-width: 1280px; margin: 0 auto; padding: 24px 16px 28px; }}
    .board-header {{ background: var(--panel); border: 1px solid var(--soft-line); border-radius: 12px; box-shadow: var(--shadow); padding: 20px; margin-bottom: 18px; }}
    .board-title {{ display: flex; align-items: center; gap: 10px; padding-bottom: 15px; border-bottom: 1px solid var(--soft-line); }}
    .title-icon {{ width: 34px; height: 34px; border-radius: 9px; background: linear-gradient(135deg, #1e3a5f, #2d4a7c); display: inline-flex; align-items: center; justify-content: center; color: #fff; box-shadow: var(--shadow); }}
    .header-meta {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 10px; color: var(--muted); font-size: 12px; }}
    .board-toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
    .toolbar-group {{ display: flex; flex-wrap: wrap; align-items: center; gap: 4px; background: var(--toolbar); border-radius: 12px; padding: 4px; box-shadow: var(--shadow); }}
    .toolbar-divider {{ width: 1px; height: 24px; background: #cbd5e1; margin: 0 4px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--soft-line); border-radius: 12px; box-shadow: var(--shadow); padding: 15px; margin-bottom: 14px; }}
    .panel h2 {{ margin: 0 0 12px; font-size: 15px; font-weight: 800; color: #334155; }}
    .metric {{ min-height: 118px; display: flex; flex-direction: column; }}
    .metric > span {{ display: block; color: var(--muted); font-size: 12px; font-weight: 600; margin-bottom: 8px; }}
    .metric strong {{ display: block; font-size: 18px; font-weight: 800; overflow-wrap: anywhere; }}
    .metric-value-line {{ display: block; color: var(--text); }}
    .metric-note {{ display: block; margin-top: 5px; font-size: 12px; line-height: 1.35; font-weight: 800; }}
    .metric-note.delta-ok {{ color: var(--good); }}
    .metric-note.delta-danger {{ color: var(--bad); }}
    .metric-note.delta-flat {{ color: var(--muted); }}
    .metric-desc {{ margin-top: auto; padding-top: 10px; color: var(--muted); font-size: 11px; line-height: 1.35; font-weight: 600; }}
    .beginner-summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin-bottom: 12px; }}
    .beginner-chip {{ border: 1px solid var(--soft-line); border-radius: 10px; padding: 11px; background: #f8fafc; min-height: 72px; }}
    .beginner-chip span {{ display: block; color: var(--muted); font-size: 12px; font-weight: 700; margin-bottom: 6px; }}
    .beginner-chip strong {{ display: block; font-size: 16px; overflow-wrap: anywhere; }}
    .step-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px; }}
    .step-card {{ display: grid; grid-template-columns: 34px 1fr; gap: 10px; align-items: start; border: 1px solid var(--soft-line); border-radius: 10px; padding: 12px; background: #fff; min-height: 132px; }}
    .step-number {{ width: 30px; height: 30px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; color: #fff; background: var(--primary-light); font-size: 13px; font-weight: 800; }}
    .step-title {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; font-size: 13px; font-weight: 800; color: #334155; }}
    .step-copy {{ color: #475569; font-size: 12px; line-height: 1.45; min-height: 34px; }}
    .step-action {{ margin-top: 8px; color: var(--muted); font-size: 12px; font-weight: 700; }}
    .help-dot {{ width: 20px; height: 20px; border-radius: 999px; border: 1px solid var(--line); display: inline-flex; align-items: center; justify-content: center; color: #475569; font-size: 12px; font-weight: 800; background: #f8fafc; flex: none; }}
    .pnl-layout {{ display: grid; grid-template-columns: minmax(260px, 1fr) minmax(320px, 1.4fr); gap: 12px; align-items: stretch; }}
    .pnl-chart {{ width: 100%; min-height: 190px; border: 1px solid var(--soft-line); border-radius: 10px; background: #f8fafc; padding: 10px; }}
    .pnl-chart svg {{ width: 100%; height: 160px; display: block; }}
    .pnl-line {{ fill: none; stroke: var(--focus); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
    .pnl-fill {{ fill: rgba(18, 59, 122, 0.10); }}
    .pnl-zero {{ stroke: #cbd5e1; stroke-width: 1; stroke-dasharray: 4 4; }}
    .pnl-summary {{ border: 1px solid var(--soft-line); border-radius: 10px; background: #f8fafc; padding: 12px; margin-bottom: 12px; }}
    .pnl-summary-head {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 8px; font-weight: 800; }}
    .pnl-summary p {{ margin: 0 0 8px; color: #475569; font-size: 13px; line-height: 1.5; }}
    .pnl-table-wrap {{ overflow-x: auto; }}
    .pnl-table-wrap h3 {{ margin: 0 0 8px; font-size: 13px; color: #334155; }}
    .walkthrough {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
    .walk-step {{ min-height: 172px; border: 1px solid var(--soft-line); border-radius: 8px; background: #fff; padding: 12px; display: flex; flex-direction: column; gap: 8px; }}
    .walk-head {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .walk-title {{ display: flex; align-items: center; gap: 8px; min-width: 0; }}
    .walk-number {{ width: 28px; height: 28px; border-radius: 999px; background: var(--focus); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 800; flex: none; }}
    .walk-goal {{ color: #475569; font-size: 13px; line-height: 1.45; flex: 1; }}
    .walk-action {{ margin-top: auto; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .walk-action .btn {{ background: #f8fafc; border: 1px solid var(--soft-line); }}
    .start-guide {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; }}
    .start-card {{ border: 1px solid var(--soft-line); border-radius: 8px; background: #fff; padding: 12px; min-height: 158px; display: flex; flex-direction: column; gap: 8px; }}
    .start-card-head {{ display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 800; color: #334155; }}
    .start-index {{ width: 26px; height: 26px; border-radius: 999px; background: var(--focus); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800; flex: none; }}
    .start-copy {{ color: #475569; font-size: 13px; line-height: 1.45; flex: 1; }}
    .start-command {{ display: inline-block; width: fit-content; max-width: 100%; overflow-wrap: anywhere; color: #334155; background: #f1f5f9; border: 1px solid var(--soft-line); border-radius: 7px; padding: 5px 7px; font-size: 12px; font-weight: 800; }}
    .badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; line-height: 1.35; }}
    .ok {{ background: #dcfce7; color: var(--good); }}
    .danger {{ background: #fee2e2; color: var(--bad); }}
    .warn {{ background: #fef3c7; color: var(--warn); }}
    .actions {{ display: contents; }}
    .btn {{ display: inline-flex; align-items: center; gap: 7px; border: 0; border-radius: 8px; background: transparent; color: #334155; padding: 7px 10px; cursor: pointer; font-size: 13px; font-weight: 700; line-height: 1.2; transition: background .15s ease, color .15s ease, box-shadow .15s ease; }}
    .btn:hover {{ background: #fff; color: var(--focus); box-shadow: var(--shadow); }}
    .btn:disabled {{ opacity: .55; cursor: not-allowed; }}
    .btn-danger {{ color: #991b1b; }}
    .btn-danger:hover {{ color: #b91c1c; background: #fff; }}
    .btn svg, .title-icon svg {{ width: 16px; height: 16px; flex: none; }}
    pre {{ margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; line-height: 1.5; color: #334155; background: #f8fafc; border: 1px solid var(--soft-line); border-radius: 8px; padding: 10px; }}
    .activity {{ border-top: 1px solid var(--soft-line); padding-top: 10px; margin-top: 10px; }}
    .activity:first-child {{ border-top: 0; margin-top: 0; padding-top: 0; }}
    .filters {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 10px; }}
    select, input {{ border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; background: #fff; color: var(--ink); font: inherit; font-size: 13px; }}
    select:focus, input:focus {{ outline: 2px solid var(--primary-soft); border-color: var(--focus); }}
    .small {{ color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .data-table {{ width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; overflow: hidden; border: 1px solid var(--soft-line); border-radius: 10px; }}
    .data-table th {{ background: #f8fafc; color: #475569; font-size: 12px; text-transform: uppercase; letter-spacing: .02em; text-align: left; padding: 10px; border-bottom: 1px solid var(--soft-line); }}
    .data-table td {{ padding: 10px; border-bottom: 1px solid #edf2f7; vertical-align: top; color: #334155; }}
    .data-table tr:last-child td {{ border-bottom: 0; }}
    code {{ color: #334155; background: #f1f5f9; border-radius: 6px; padding: 2px 5px; font-size: 12px; }}
    @media (max-width: 720px) {{
      .shell {{ padding: 12px; }}
      .board-title {{ align-items: flex-start; }}
      .toolbar-group {{ width: 100%; }}
      .pnl-layout {{ grid-template-columns: 1fr; }}
      .walkthrough {{ grid-template-columns: 1fr; }}
      .data-table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="board-header">
      <div class="board-title">
        <div class="title-icon">{_svg_icon("board")}</div>
        <div>
          <h1>Orchestrator Bot Trading</h1>
          <div class="header-meta">
            <span>Mode: {escape(status.mode)}</span>
            <span>Data: {escape(status.data_root)}</span>
            <span>Live: {"aktif" if status.live_enabled else "nonaktif"}</span>
            <span>Aksi: {escape(current_action)}</span>
          </div>
        </div>
      </div>
      <div class="board-toolbar">
        <div class="toolbar-group">{action_buttons}</div>
      </div>
    </section>
    <section class="panel" id="mulai-di-sini">
      <h2>Mulai di Sini</h2>
      <div>{getting_started_html}</div>
      <p class="small">Menu ini adalah urutan instalasi dan langkah awal untuk menjalankan bot demo/paper di laptop.</p>
    </section>
    <section class="panel" id="control-room">
      <h2>Control Room Awam</h2>
      <div>{beginner_html}</div>
    </section>
    <section class="panel">
      <h2>Kamus Awam</h2>
      <div>{glossary_html}</div>
    </section>
    <section class="panel" id="demo-walkthrough">
      <h2>Demo Walkthrough</h2>
      <div>{walkthrough_html}</div>
      <p class="small">Ikuti urutan ini untuk demo lokal yang aman. Semua langkah tetap paper/demo dan read-only untuk live.</p>
    </section>
    <section class="panel" id="local-demo">
      <h2>Local Demo Readiness</h2>
      <div>{local_demo_html}</div>
      <p class="small">Panel ini memastikan demo lokal siap dipakai tanpa real-money live execution.</p>
    </section>
    <section class="panel">
      <h2>Private VPS Demo</h2>
      <div>{vps_demo_html}</div>
      <p class="small">Panel ini memeriksa kesiapan demo paper di VPS private lewat SSH tunnel/VPN only.</p>
    </section>
    <section class="panel">
      <h2>Paper Campaign</h2>
      <div>{paper_campaign_html}</div>
      <p class="small">Target campaign: minimal 14 hari, ideal 28 hari, dan minimal 20 paper trades sebelum live review.</p>
    </section>
    <section class="panel">
      <h2>Skill Loop</h2>
      <div>{skill_loop_html}</div>
      <p class="small">Loop ini hanya untuk riset dan improvement. Tidak ada auto-live dari hasil belajar.</p>
    </section>
    <section class="panel">
      <h2>Pattern Memory</h2>
      <div>{pattern_memory_html}</div>
      <p class="small">Memory ini membantu review pola, label manual, dan outcome paper. Bukan tombol order live.</p>
    </section>
    <section class="panel">
      <h2>Learning Dashboard</h2>
      <div>{learning_dashboard_html}</div>
      <p class="small">Dashboard ini merangkum trend pola, volume spike, dan evidence score untuk review awam.</p>
    </section>
    <section class="panel">
      <h2>Human Feedback</h2>
      <div>{human_feedback_html}</div>
      <p class="small">Label manusia menjadi bahan lesson dan eksperimen. Tidak ada auto-live dari feedback.</p>
    </section>
    <section class="panel">
      <h2>Fundamental/Event Lane</h2>
      <div>{fundamental_html}</div>
      <p class="small">Warna risiko fundamental membantu pause/review sebelum percaya sinyal teknikal.</p>
    </section>
    <section class="panel">
      <h2>Experiment Scoreboard</h2>
      <div>{experiment_scoreboard_html}</div>
      <p class="small">Score tinggi hanya boleh naik ke backtest/paper review, bukan langsung live.</p>
    </section>
    <section class="panel" id="market-feed">
      <h2>Market Data Feed</h2>
      <div>{market_feed_html}</div>
      <p class="small">Panel ini menunjukkan candle lokal terakhir. Klik Jalankan Siklus untuk mencoba sync candle terbaru sebelum analisa paper.</p>
    </section>
    <section class="panel" id="paper-execution">
      <h2>Paper Execution</h2>
      <div>{paper_execution_html}</div>
      <p class="small">Panel ini menunjukkan order simulasi paper: filled, rejected, open, close, dan alasannya. Ini tetap bukan order live.</p>
    </section>
    <section class="panel" id="pnl-monitor">
      <h2>P/L Visual Monitor</h2>
      <div class="filters">
        <button type="button" class="btn" id="pnl-refresh-now">{_svg_icon("refresh")}Refresh P/L</button>
        <span class="small" id="pnl-refresh-status">Auto refresh siap. Panel ini update tiap 15 detik.</span>
      </div>
      <div id="pnl-panel-body">{pnl_html}</div>
      <p class="small">Semua angka di panel ini berasal dari paper/demo trading, bukan uang asli.</p>
    </section>
    <section class="grid">
      {_metric("Mode", status.mode)}
      {_metric("Keamanan", f'<span class="badge {safety_class}">{escape(live_text)}</span>')}
      {_metric("Kill Switch", f'<span class="badge {"danger" if status.kill_switch_active else "ok"}">{escape(kill_text)}</span>')}
      {_metric("Go/No-Go", status.go_no_go_decision)}
      {_metric("Security QA", status.security_status)}
      {_metric("Production Smoke", status.production_smoke_status)}
      {_metric("Lock Aksi", current_action)}
    </section>
    <section class="panel">
      <h2>Status Bot</h2>
      <div class="grid">{health_html}</div>
    </section>
    <section class="panel">
      <h2>Setup Cepat</h2>
      <div>{setup_html}</div>
      <p class="small">Urutan awal yang disarankan: Validasi Config, Demo Data, Import DB, Learning DB, Security QA, lalu Buat Dashboard.</p>
    </section>
    <section class="panel">
      <h2>Browser Laporan</h2>
      <div>{reports_html}</div>
      <p class="small">Laporan ini read-only dari file lokal paper/research.</p>
    </section>
    <section class="panel">
      <h2>Database Lokal</h2>
      <div>{database_html}</div>
      <p class="small">SQLite ini arsip lokal untuk data harian, audit, dan aktivitas bot. Klik Import DB setelah sinkron/paper cycle.</p>
    </section>
    <section class="panel">
      <h2>Demo/Testnet Monitoring</h2>
      <div>{testnet_demo_html}</div>
      <p class="small">Panel ini read-only dari report demo/testnet. Tidak ada real live order di sini.</p>
    </section>
    <section class="panel" id="live-evidence">
      <h2>Live Evidence Gate</h2>
      <div>{live_evidence_html}</div>
      <p class="small">Gate ini mengunci real live sampai semua bukti paper, QA, testnet, dan owner review lengkap.</p>
    </section>
    <section class="panel">
      <h2>Kill Switch & Incident</h2>
      <div>{incident_html}</div>
      <div class="filters">
        <input id="kill-reason" placeholder="Alasan wajib untuk aktivasi">
        <button type="button" class="btn btn-danger" id="kill-activate">{_svg_icon("stop")}Aktifkan Kill Switch</button>
        <button type="button" class="btn" id="kill-clear">{_svg_icon("refresh")}Clear Kill Switch</button>
      </div>
      <p class="small">Kill switch memblokir siklus bot. Incident drill tersedia sebagai aksi aman di toolbar.</p>
    </section>
    <section class="panel">
      <h2>Aksi Aman</h2>
      <label class="small" for="limit">Limit candle</label>
      <input id="limit" type="number" min="1" max="1000" value="10" style="width:100px; margin:0 0 10px 8px;">
      <p class="small">Semua aksi berjalan di mode paper/research. Tidak ada tombol live buy/sell/order di UI ini.</p>
    </section>
    <section class="panel">
      <h2>Path</h2>
      <p>Root data: <strong>{escape(status.data_root)}</strong></p>
      <p>Dashboard statis: <strong>{escape(status.dashboard_path)}</strong></p>
    </section>
    <section class="panel">
      <h2>Aktivitas</h2>
      <div id="activity">{activity_html}</div>
    </section>
    <section class="panel">
      <h2>Timeline Audit</h2>
      <div class="filters">
        <select id="audit-level">
          <option value="">Semua Level</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>
        <input id="audit-symbol" placeholder="Simbol">
        <input id="audit-timeframe" placeholder="Timeframe">
        <button type="button" class="btn" id="audit-refresh">{_svg_icon("refresh")}Refresh</button>
      </div>
      <div id="audit">{audit_html}</div>
    </section>
  </main>
  <script>
    async function refresh() {{
      const res = await fetch('/api/status');
      if (res.ok) window.location.reload();
    }}
    for (const button of document.querySelectorAll('button[data-action]')) {{
      button.addEventListener('click', async () => {{
        button.disabled = true;
        button.textContent = 'Berjalan...';
        await fetch('/api/actions', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{action: button.dataset.action, limit: Number(document.getElementById('limit').value || 10)}})
        }});
        await refresh();
      }});
    }}
    for (const button of document.querySelectorAll('button[data-scroll]')) {{
      button.addEventListener('click', () => {{
        const target = document.getElementById(button.dataset.scroll);
        if (target) target.scrollIntoView({{behavior: 'smooth', block: 'start'}});
      }});
    }}
    async function loadAudit() {{
      const level = encodeURIComponent(document.getElementById('audit-level').value);
      const symbol = encodeURIComponent(document.getElementById('audit-symbol').value);
      const timeframe = encodeURIComponent(document.getElementById('audit-timeframe').value);
      const res = await fetch(`/api/audit?level=${{level}}&symbol=${{symbol}}&timeframe=${{timeframe}}`);
      if (!res.ok) return;
      const payload = await res.json();
      document.getElementById('audit').innerHTML = payload.html;
    }}
    document.getElementById('audit-refresh').addEventListener('click', loadAudit);
    async function refreshPnlPanel() {{
      const target = document.getElementById('pnl-panel-body');
      const status = document.getElementById('pnl-refresh-status');
      if (!target) return;
      try {{
        const res = await fetch('/api/pnl-html', {{cache: 'no-store'}});
        if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
        target.innerHTML = await res.text();
        if (status) status.textContent = `Auto refresh P/L terakhir: ${{new Date().toLocaleTimeString('id-ID')}}`;
      }} catch (error) {{
        if (status) status.textContent = `Auto refresh P/L gagal: ${{error.message || 'request error'}}`;
      }}
    }}
    const pnlRefreshButton = document.getElementById('pnl-refresh-now');
    if (pnlRefreshButton) pnlRefreshButton.addEventListener('click', refreshPnlPanel);
    async function postKillSwitch(action) {{
      const reason = document.getElementById('kill-reason').value;
      const res = await fetch('/api/kill-switch', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{action, reason}})
      }});
      if (!res.ok) {{
        const payload = await res.json().catch(() => ({{error: 'request gagal'}}));
        alert(payload.error || 'request gagal');
        return;
      }}
      window.location.reload();
    }}
    document.getElementById('kill-activate').addEventListener('click', () => postKillSwitch('activate'));
    document.getElementById('kill-clear').addEventListener('click', () => postKillSwitch('clear'));
    setInterval(() => fetch('/api/status').catch(() => null), 15000);
    setInterval(refreshPnlPanel, 15000);
    setInterval(loadAudit, 30000);
  </script>
</body>
</html>
"""


def serve_orchestrator(
    host: str = "127.0.0.1",
    port: int = 8000,
    config_path: str | Path = "config/bot.sample.toml",
) -> None:
    handler = _handler_factory(Path(config_path))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"orchestrator listening on http://{host}:{port}")
    server.serve_forever()


def _handler_factory(config_path: Path):
    class OrchestratorHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            try:
                parsed = urlparse(self.path)
                if parsed.path == "/api/status":
                    self._json_response(asdict(load_orchestrator_status(config_path)))
                    return
                if parsed.path == "/api/health":
                    self._json_response(asdict(load_health_summary(config_path)))
                    return
                if parsed.path == "/api/setup":
                    self._json_response({"checks": [asdict(row) for row in load_setup_wizard(config_path)]})
                    return
                if parsed.path == "/api/reports":
                    self._json_response({"reports": [asdict(row) for row in load_report_browser(config_path)]})
                    return
                if parsed.path == "/api/glossary":
                    self._json_response({"entries": [asdict(row) for row in load_glossary_entries()]})
                    return
                if parsed.path == "/api/incident":
                    self._json_response(asdict(load_incident_panel(config_path)))
                    return
                if parsed.path == "/api/database":
                    self._json_response(asdict(load_database_panel(config_path)))
                    return
                if parsed.path == "/api/testnet-demo":
                    self._json_response(asdict(load_testnet_demo_panel(config_path)))
                    return
                if parsed.path == "/api/live-evidence":
                    self._json_response(asdict(load_live_evidence_panel(config_path)))
                    return
                if parsed.path == "/api/local-demo":
                    self._json_response(asdict(load_local_demo_panel(config_path)))
                    return
                if parsed.path == "/api/vps-demo":
                    self._json_response(asdict(load_vps_demo_panel(config_path)))
                    return
                if parsed.path == "/api/paper-campaign":
                    self._json_response(asdict(load_paper_campaign_panel(config_path)))
                    return
                if parsed.path == "/api/skill-loop":
                    self._json_response(asdict(load_skill_loop_panel(config_path)))
                    return
                if parsed.path == "/api/pattern-memory":
                    self._json_response(asdict(load_pattern_memory_panel(config_path)))
                    return
                if parsed.path == "/api/learning-dashboard":
                    self._json_response(asdict(load_learning_dashboard_panel(config_path)))
                    return
                if parsed.path == "/api/human-feedback":
                    self._json_response(asdict(load_human_feedback_panel(config_path)))
                    return
                if parsed.path == "/api/fundamental":
                    self._json_response(asdict(load_fundamental_panel(config_path)))
                    return
                if parsed.path == "/api/experiment-scoreboard":
                    self._json_response(asdict(load_experiment_scoreboard_panel(config_path)))
                    return
                if parsed.path == "/api/pnl":
                    self._json_response(asdict(load_pnl_panel(config_path)))
                    return
                if parsed.path == "/api/pnl-html":
                    self._html_response(_pnl_panel_html(load_pnl_panel(config_path)))
                    return
                if parsed.path == "/api/walkthrough":
                    self._json_response([asdict(step) for step in load_demo_walkthrough(config_path)])
                    return
                if parsed.path == "/api/activity":
                    config = load_config(config_path)
                    rows = [asdict(row) for row in recent_activities(config.data_root)]
                    self._json_response({"activity": rows})
                    return
                if parsed.path == "/api/audit":
                    config = load_config(config_path)
                    params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
                    rows = recent_audit_events(
                        config.data_root,
                        level=params.get("level", ""),
                        symbol=params.get("symbol", ""),
                        timeframe=params.get("timeframe", ""),
                    )
                    self._json_response({
                        "events": [asdict(row) for row in rows],
                        "html": _audit_html(rows),
                    })
                    return
                status = load_orchestrator_status(config_path)
                activities = recent_activities(status.data_root)
                audit_events = recent_audit_events(status.data_root)
                health = load_health_summary(config_path)
                setup = load_setup_wizard(config_path)
                reports = load_report_browser(config_path)
                glossary = load_glossary_entries()
                incident = load_incident_panel(config_path)
                database = load_database_panel(config_path)
                testnet_demo = load_testnet_demo_panel(config_path)
                live_evidence = load_live_evidence_panel(config_path)
                local_demo = load_local_demo_panel(config_path)
                vps_demo = load_vps_demo_panel(config_path)
                paper_campaign = load_paper_campaign_panel(config_path)
                skill_loop = load_skill_loop_panel(config_path)
                pattern_memory = load_pattern_memory_panel(config_path)
                learning_dashboard = load_learning_dashboard_panel(config_path)
                human_feedback = load_human_feedback_panel(config_path)
                fundamental = load_fundamental_panel(config_path)
                experiment_scoreboard = load_experiment_scoreboard_panel(config_path)
                pnl = load_pnl_panel(config_path)
                market_feed = load_market_feed_panel(config_path)
                paper_execution = load_paper_execution_panel(config_path)
                walkthrough = load_demo_walkthrough(config_path)
                self._html_response(
                    build_orchestrator_page(
                        status,
                        activities,
                        audit_events,
                        health,
                        setup,
                        reports,
                        glossary,
                        incident,
                        database,
                        testnet_demo,
                        live_evidence,
                        local_demo,
                        vps_demo,
                        paper_campaign,
                        skill_loop,
                        pattern_memory,
                        learning_dashboard,
                        human_feedback,
                        fundamental,
                        experiment_scoreboard,
                        pnl,
                        market_feed,
                        paper_execution,
                        walkthrough,
                    )
                )
            except (ConfigError, ValueError, OSError) as exc:
                self._json_response({"error": str(exc)}, status=500)

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            try:
                parsed = urlparse(self.path)
                if parsed.path != "/api/actions":
                    if parsed.path == "/api/kill-switch":
                        length = int(self.headers.get("Content-Length", "0"))
                        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                        payload = json.loads(raw)
                        panel = update_kill_switch_from_web(
                            str(payload.get("action", "")),
                            str(payload.get("reason", "")),
                            config_path=config_path,
                        )
                        self._json_response(asdict(panel))
                        return
                    self._json_response({"error": "not found"}, status=404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                payload = json.loads(raw)
                activity = run_orchestrator_action(
                    str(payload.get("action", "")),
                    config_path=config_path,
                    limit=int(payload.get("limit", 10) or 10),
                )
                self._json_response(asdict(activity), status=200 if activity.exit_code == 0 else 400)
            except (json.JSONDecodeError, ValueError, ConfigError, subprocess.TimeoutExpired) as exc:
                self._json_response({"error": str(exc)}, status=400)

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib API
            return

        def _json_response(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html_response(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return OrchestratorHandler


def _append_activity(root: Path, activity: OrchestratorActivity) -> None:
    path = _activity_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(activity), separators=(",", ":")) + "\n")


def _activity_path(root: Path) -> Path:
    return root / "orchestrator" / "activity.jsonl"


def _lock_path(root: Path) -> Path:
    return root / "orchestrator" / "action.lock"


def _running_action(root: Path) -> str:
    path = _lock_path(root)
    if not path.exists():
        return ""
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("action", "unknown"))
    except json.JSONDecodeError:
        return "unknown"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_value(path: Path, key: str, default: str) -> str:
    if not path.exists():
        return default
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get(key, default))
    except json.JSONDecodeError:
        return "INVALID"


def _action_button(action: str, disabled: bool) -> str:
    icon = _action_icon(action)
    label = _action_label(action)
    title = _help_text_for(label) or label
    return (
        f'<button type="button" class="btn" data-action="{escape(action)}" {"disabled" if disabled else ""} '
        f'title="{escape(title)}">{icon}{escape(label)}</button>'
    )


def _action_icon(action: str) -> str:
    if "sync" in action:
        return _svg_icon("refresh")
    if "demo" in action:
        return _svg_icon("database")
    if "security" in action or "go_no_go" in action or "incident" in action or "testnet" in action or "evidence" in action:
        return _svg_icon("shield")
    if "dashboard" in action:
        return _svg_icon("chart")
    if "db" in action:
        return _svg_icon("database")
    if "smoke" in action or "validate" in action:
        return _svg_icon("check")
    return _svg_icon("play")


def _svg_icon(name: str) -> str:
    icons = {
        "board": '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/></svg>',
        "chart": '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm6 0V9a2 2 0 00-2-2h-2a2 2 0 00-2 2v10m6 0a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2h-2a2 2 0 00-2 2v14z"/></svg>',
        "check": '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>',
        "database": '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="7" ry="3" stroke-width="2"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5v6c0 1.657 3.134 3 7 3s7-1.343 7-3V5M5 11v6c0 1.657 3.134 3 7 3s7-1.343 7-3v-6"/></svg>',
        "play": '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-5.197-3.03A1 1 0 008 9.003v5.994a1 1 0 001.555.832l5.197-2.964a1 1 0 000-1.697z"/></svg>',
        "refresh": '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>',
        "shield": '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3l7 4v5c0 4.418-2.985 8.13-7 9-4.015-.87-7-4.582-7-9V7l7-4z"/></svg>',
        "stop": '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636l-12.728 12.728M12 22a10 10 0 110-20 10 10 0 010 20z"/></svg>',
    }
    return icons.get(name, icons["play"])


def _metric(label: str, value: object, note: str = "") -> str:
    title = _help_text_for(str(label))
    title_attr = f' title="{escape(title)}"' if title else ""
    note_html = f'<div class="metric-desc">{escape(note)}</div>' if note else ""
    return (
        f'<div class="panel metric"{title_attr}>'
        f"<span>{escape(str(label))}</span>"
        f"<strong>{value if str(value).startswith('<') else escape(str(value))}</strong>"
        f"{note_html}"
        "</div>"
    )


def _glossary_html(entries: list[GlossaryEntry]) -> str:
    rows = "".join(
        "<tr>"
        f"<td><strong>{escape(entry.term)}</strong></td>"
        f"<td>{escape(entry.plain_meaning)}</td>"
        f"<td>{escape(entry.watch_for)}</td>"
        f"<td>{escape(entry.related_action)}</td>"
        "</tr>"
        for entry in entries
    )
    return (
        '<table class="data-table">'
        "<thead><tr><th>Istilah</th><th>Arti Awam</th><th>Yang Dipantau</th><th>Aksi Terkait</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _activity_html(activities: list[OrchestratorActivity]) -> str:
    if not activities:
        return '<p class="small">Belum ada aktivitas orchestrator.</p>'
    return "".join(
        '<div class="activity">'
        f'<div><strong>{escape(row.action)}</strong> '
        f'<span class="badge {"ok" if row.status == "SUCCESS" else "danger"}">{escape(row.status)}</span></div>'
        f'<div class="small">{escape(row.created_at_utc)} | exit={row.exit_code}</div>'
        f"<pre>{escape(row.output)}</pre>"
        "</div>"
        for row in activities
    )


def _audit_html(events: list[AuditEvent]) -> str:
    if not events:
        return '<p class="small">Belum ada event audit.</p>'
    return "".join(
        '<div class="activity">'
        f'<div><strong>{escape(row.event)}</strong> '
        f'<span class="badge {_level_class(row.level)}">{escape(row.level)}</span></div>'
        f'<div class="small">{escape(row.created_at_utc)}'
        f'{_context_summary(row.context)}</div>'
        f"<pre>{escape(row.message)}</pre>"
        "</div>"
        for row in events
    )


def _health_html(health: HealthSummary) -> str:
    return "".join(
        [
            _health_card("Data", health.data_status, health.data_reason),
            _health_card("Paper", health.paper_status, health.paper_reason),
            _health_card("Kesiapan Live", health.readiness_status, health.readiness_reason),
            _health_card("Keamanan", health.safety_status, health.safety_reason),
        ]
    )


def _beginner_control_room_html(
    status: OrchestratorStatus,
    health: HealthSummary,
    live_evidence: LiveEvidencePanel,
) -> str:
    overall_status, overall_css = _beginner_overall_status(status, health, live_evidence)
    pnl_value = _paper_pnl_text(health.paper_reason)
    evidence_text = (
        f"{live_evidence.completion_pct:.2f}% siap"
        if live_evidence.exists
        else "belum ada evidence"
    )
    chips = (
        '<div class="beginner-summary">'
        + _beginner_chip("Kondisi Bot", overall_status, overall_css, "Ringkasan aman atau tidaknya bot saat ini.")
        + _beginner_chip("Mode Akun", "Demo/Paper" if not status.live_enabled else "Live Aktif", "ok" if not status.live_enabled else "danger", "Mode uang asli harus tetap terkunci sampai owner approve.")
        + _beginner_chip("P/L Demo", pnl_value, "ok" if not pnl_value.startswith("-") else "danger", "Profit/loss ini dari simulasi paper, bukan uang asli.")
        + _beginner_chip("Evidence Live", evidence_text, "warn" if live_evidence.blocker_count else "ok", "Persentase bukti kesiapan sebelum live review.")
        + "</div>"
    )
    steps = _beginner_steps(status, health, live_evidence)
    return chips + '<div class="step-grid">' + "".join(_beginner_step_html(step) for step in steps) + "</div>"


def _beginner_steps(
    status: OrchestratorStatus,
    health: HealthSummary,
    live_evidence: LiveEvidencePanel,
) -> list[BeginnerStep]:
    safety_ok = not status.live_enabled and not status.kill_switch_active
    data_ok = health.data_status == "OK"
    paper_ok = health.paper_status == "ACTIVE"
    evidence_ok = live_evidence.exists and live_evidence.blocker_count == 0
    return [
        BeginnerStep(
            1,
            "Cek Keamanan",
            "Aman" if safety_ok else "Stop",
            "Live masih terkunci dan kill switch clear." if safety_ok else "Ada safety lock yang perlu dicek.",
            "Pastikan bot tidak bisa order live sebelum semua bukti dan owner approval lengkap.",
            "Validasi Config",
        ),
        BeginnerStep(
            2,
            "Cek Data Market",
            "Aman" if data_ok else "Perlu Data",
            "Data candle bisa dipakai." if data_ok else "Data belum cukup atau ada blocker.",
            "Kalau data bolong, analisa bot tidak dipercaya untuk backtest atau paper.",
            "Evidence Campaign",
        ),
        BeginnerStep(
            3,
            "Cek Sinyal",
            "Pantau",
            "Bot membaca kondisi market dan sinyal konservatif.",
            "Sinyal bukan perintah live. Ini hanya kandidat yang harus lolos risiko dan paper.",
            "Jalankan Siklus",
        ),
        BeginnerStep(
            4,
            "Cek Risiko",
            "Aman" if health.safety_status == "SAFE" else "Stop",
            "Risk guard tidak melihat bahaya aktif." if health.safety_status == "SAFE" else "Risk guard meminta perhatian.",
            "Bot mengecek batas rugi, profit lock, kill switch, dan batas posisi.",
            "Risk / Security QA",
        ),
        BeginnerStep(
            5,
            "Demo Trade",
            "Aktif" if paper_ok else "Belum Ada",
            "Paper trade sudah punya aktivitas." if paper_ok else "Belum ada simulasi trade yang cukup.",
            "Demo trade memakai saldo virtual, bukan uang asli.",
            "Demo Data / Testnet Demo",
        ),
        BeginnerStep(
            6,
            "Pantau P/L",
            "Aktif" if paper_ok else "Menunggu",
            f"P/L demo sekarang { _paper_pnl_text(health.paper_reason) }.",
            "P/L ini dari trade paper. Detail chart akan masuk ke P/L Visual Monitor.",
            "Lihat Paper Reports",
        ),
        BeginnerStep(
            7,
            "Review Go Live",
            "Belum Siap" if not evidence_ok else "Siap Review",
            f"{live_evidence.blocker_count} blocker aktif." if live_evidence.exists else "Evidence belum dibuat.",
            "Real live baru boleh dibahas setelah paper, QA, testnet, dan owner approval lengkap.",
            "Live Evidence",
        ),
    ]


def _beginner_chip(label: str, value: str, css: str, help_text: str) -> str:
    return (
        f'<div class="beginner-chip" title="{escape(help_text)}">'
        f"<span>{escape(label)}</span>"
        f'<strong><span class="badge {css}">{escape(value)}</span></strong>'
        "</div>"
    )


def _beginner_step_html(step: BeginnerStep) -> str:
    css = _plain_status_class(step.status)
    return (
        f'<div class="step-card" title="{escape(step.help_text)}">'
        f'<div class="step-number">{step.number}</div>'
        "<div>"
        f'<div class="step-title"><span>{escape(step.title)}</span><span class="help-dot" title="{escape(step.help_text)}">?</span></div>'
        f'<span class="badge {css}">{escape(step.status)}</span>'
        f'<div class="step-copy">{escape(step.plain_text)}</div>'
        f'<div class="step-action">{escape(step.action_label)}</div>'
        "</div>"
        "</div>"
    )


def _getting_started_html(status: OrchestratorStatus) -> str:
    live_label = "Live terkunci" if not status.live_enabled and not status.approved_live else "Perlu cek live"
    steps = [
        (
            "Buka Folder Project",
            "Masuk ke folder bot di laptop. Ini lokasi file launcher dan config demo.",
            r"C:\Users\IT-MGR\Documents\Codex\2026-06-28\bro-2",
        ),
        (
            "Start Web Demo",
            "Double-click file ini untuk menyalakan dashboard lokal. Jika sudah hidup, langkah ini tidak perlu diulang.",
            "start-bot-web.cmd",
        ),
        (
            "Buka Browser Lokal",
            "Buka alamat dashboard. Semua tombol di sini aman untuk demo/paper dan tidak membuat order live.",
            "http://127.0.0.1:8000/",
        ),
        (
            "Ikuti Demo Walkthrough",
            "Lanjutkan urutan di panel Demo Walkthrough untuk validasi config, data demo, evidence, dan P/L.",
            "Demo Walkthrough",
        ),
        (
            "Pantau Profit/Loss",
            "Naik-turun saldo simulasi ada di panel P/L Visual Monitor: equity curve, net P/L, win rate, dan trade terakhir.",
            "P/L Visual Monitor",
        ),
        (
            "Auto-Repair Jika Mati",
            "Jika browser refused atau web mati, jalankan watchdog. Helper ini hanya menyalakan web demo, bukan order live.",
            "start-bot-watchdog.cmd",
        ),
        (
            "Pastikan Safety",
            f"Status saat ini: {live_label}. Real live tetap no-go sampai evidence dan approval manual lengkap.",
            "Live Evidence Gate",
        ),
    ]
    cards = []
    for index, (title, copy, command) in enumerate(steps, start=1):
        cards.append(
            '<div class="start-card" title="Langkah awal demo/paper">'
            + '<div class="start-card-head">'
            + f'<span class="start-index">{index}</span>'
            + f"<strong>{escape(title)}</strong>"
            + "</div>"
            + f'<div class="start-copy">{escape(copy)}</div>'
            + f'<code class="start-command">{escape(command)}</code>'
            + "</div>"
        )
    return '<div class="start-guide">' + "".join(cards) + "</div>"


def _beginner_overall_status(
    status: OrchestratorStatus,
    health: HealthSummary,
    live_evidence: LiveEvidencePanel,
) -> tuple[str, str]:
    if status.live_enabled or status.kill_switch_active or health.safety_status == "BLOCKED":
        return "Stop / Cek Dulu", "danger"
    if health.data_status in {"BLOCKED", "MISSING"} or not live_evidence.exists:
        return "Perlu Data", "warn"
    if live_evidence.blocker_count:
        return "Demo Aman", "warn"
    return "Siap Review", "ok"


def _paper_pnl_text(reason: str) -> str:
    marker = "net_pnl="
    if marker not in reason:
        return "0.00000000"
    value = reason.split(marker, 1)[1].split(",", 1)[0].strip()
    try:
        return f"{float(value):.8f}"
    except ValueError:
        return value or "0.00000000"


def _pnl_panel_html(panel: PnlPanel) -> str:
    pnl_css = "ok" if panel.net_pnl >= 0 else "danger"
    equity_delta_text = _equity_delta_text(panel)
    equity_delta_css = _equity_delta_css(panel)
    summary_html = _pnl_summary_html(panel)
    latest_trade = panel.latest_trade
    trade_rows = ""
    if latest_trade is not None:
        trade_rows = (
            "<tr>"
            f"<td>{escape(latest_trade.exit_time)}</td>"
            f"<td>{escape(latest_trade.symbol)}</td>"
            f"<td>{escape(latest_trade.timeframe)}</td>"
            f"<td>{latest_trade.entry_price:.8f}</td>"
            f"<td>{latest_trade.exit_price:.8f}</td>"
            f'<td><span class="badge {"ok" if latest_trade.net_pnl >= 0 else "danger"}">{latest_trade.net_pnl:.8f}</span></td>'
            f"<td>{escape(latest_trade.exit_reason)}</td>"
            "</tr>"
        )
    else:
        trade_rows = '<tr><td colspan="7">Belum ada trade paper.</td></tr>'
    daily_html = _daily_pnl_html(panel.daily_rows)
    return (
        summary_html
        +
        '<div class="pnl-layout">'
        '<div>'
        '<div class="grid">'
        + _metric(
            "Realized P/L Demo",
            f'<span class="badge {pnl_css}">{panel.net_pnl:.8f}</span>',
            "Total profit/rugi dari trade yang sudah selesai.",
        )
        + _metric(
            "Win Rate",
            f"{panel.win_rate_pct:.2f}%",
            "Persentase trade menang. Tinggi belum tentu aman jika loss lebih besar.",
        )
        + _metric("Trades", panel.trade_count, "Jumlah trade paper/demo yang sudah tercatat.")
        + _metric(
            "Equity Terakhir",
            f"{panel.latest_equity:.8f}",
            "Saldo simulasi terakhir. Ini yang paling dekat dengan kondisi akun demo.",
        )
        + _metric(
            "Equity Change",
            f'<span class="metric-value-line">{panel.equity_change_pct:.2f}%</span>'
            f'<span class="metric-note {equity_delta_css}">{escape(equity_delta_text)}</span>',
            "Persentase saldo naik/turun dari awal.",
        )
        + _metric(
            "Best/Worst Trade",
            f"{panel.best_trade_pnl:.8f} / {panel.worst_trade_pnl:.8f}",
            "Trade terbaik dan terburuk dari simulasi.",
        )
        + "</div>"
        "</div>"
        '<div class="pnl-chart" title="Garis ini menunjukkan naik-turun saldo demo/paper dari waktu ke waktu.">'
        + _equity_svg(panel.equity_points)
        + '<p class="small">Equity curve demo/paper. Naik berarti saldo simulasi bertambah, turun berarti saldo simulasi berkurang.</p>'
        "</div>"
        "</div>"
        '<div class="pnl-table-wrap">'
        "<h3>History P/L Harian</h3>"
        f"{daily_html}"
        "</div>"
        '<div class="pnl-table-wrap">'
        "<h3>Trade Terakhir</h3>"
        '<table class="data-table">'
        "<thead><tr><th>Waktu Exit</th><th>Symbol</th><th>TF</th><th>Entry</th><th>Exit</th><th>Net P/L</th><th>Alasan Exit</th></tr></thead>"
        f"<tbody>{trade_rows}</tbody></table></div>"
    )


def _market_feed_html(panel: MarketFeedPanel) -> str:
    if not panel.rows:
        return '<p class="small">Belum ada konfigurasi symbol/timeframe untuk dibaca.</p>'
    rows = []
    for row in panel.rows:
        css = "ok" if row.status == "OK" else "warn"
        close_text = f"{row.latest_close:.8f}" if row.latest_close else "-"
        rows.append(
            "<tr>"
            f"<td>{escape(row.symbol)}</td>"
            f"<td>{escape(row.timeframe)}</td>"
            f'<td><span class="badge {css}">{escape(row.status)}</span></td>'
            f"<td>{row.candle_count}</td>"
            f"<td>{escape(row.latest_open_utc)}</td>"
            f"<td>{close_text}</td>"
            f"<td>{escape(row.source)}</td>"
            f"<td>{escape(row.reason)}</td>"
            "</tr>"
        )
    return (
        '<div class="pnl-table-wrap">'
        '<table class="data-table">'
        "<thead><tr><th>Symbol</th><th>TF</th><th>Status</th><th>Candles</th><th>Candle Terakhir UTC</th><th>Close</th><th>Source</th><th>Arti</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _daily_pnl_html(rows: list[DailyPnlRow]) -> str:
    if not rows:
        return (
            '<table class="data-table">'
            '<thead><tr><th>Tanggal</th><th>Trades</th><th>Net P/L</th><th>Best</th><th>Worst</th><th>Hasil</th></tr></thead>'
            '<tbody><tr><td colspan="6">Belum ada history P/L harian.</td></tr></tbody></table>'
        )
    body = []
    for row in rows:
        css = "ok" if row.net_pnl > 0 else "danger" if row.net_pnl < 0 else "warn"
        body.append(
            "<tr>"
            f"<td>{escape(row.date)}</td>"
            f"<td>{row.trade_count}</td>"
            f'<td><span class="badge {css}">{row.net_pnl:.8f}</span></td>'
            f"<td>{row.best_trade_pnl:.8f}</td>"
            f"<td>{row.worst_trade_pnl:.8f}</td>"
            f"<td>{escape(row.result)}</td>"
            "</tr>"
        )
    return (
        '<table class="data-table">'
        '<thead><tr><th>Tanggal</th><th>Trades</th><th>Net P/L</th><th>Best</th><th>Worst</th><th>Hasil</th></tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def _paper_execution_html(panel: PaperExecutionPanel) -> str:
    snapshot = panel.latest_snapshot
    position_css = "warn" if snapshot and snapshot.open_positions else "ok"
    position_text = f"{snapshot.open_positions} terbuka" if snapshot else "belum ada"
    equity_text = f"{snapshot.equity:.8f}" if snapshot else "-"
    status_text = snapshot.trading_status if snapshot else "MISSING"
    status_reason = snapshot.status_reason if snapshot and snapshot.status_reason else "Belum ada snapshot akun paper."
    summary = (
        '<div class="grid">'
        + _metric("Paper Orders", panel.order_count, "Total order simulasi yang tercatat.")
        + _metric("Filled", f'<span class="badge ok">{panel.filled_count}</span>', "Order simulasi yang berhasil dieksekusi.")
        + _metric("Rejected", f'<span class="badge warn">{panel.rejected_count}</span>', "Order simulasi yang ditolak risk/session guard.")
        + _metric("Posisi Paper", f'<span class="badge {position_css}">{escape(position_text)}</span>', "Jumlah posisi simulasi yang masih terbuka.")
        + _metric("Equity Paper", equity_text, "Saldo simulasi terakhir dari account snapshot.")
        + _metric("Status Trading", escape(status_text), status_reason)
        + "</div>"
    )
    if not panel.latest_rows:
        return summary + '<p class="small">Belum ada order paper. Klik Jalankan Siklus setelah data market tersedia.</p>'
    rows = []
    for row in panel.latest_rows:
        css = "ok" if row.status == "FILLED" else "warn" if row.status == "REJECTED" else "danger"
        rows.append(
            "<tr>"
            f"<td>{escape(row.time_utc)}</td>"
            f"<td>{escape(row.symbol)}</td>"
            f"<td>{escape(row.timeframe)}</td>"
            f"<td>{escape(row.action)}</td>"
            f"<td>{escape(row.side)}</td>"
            f'<td><span class="badge {css}">{escape(row.status)}</span></td>'
            f"<td>{row.price:.8f}</td>"
            f"<td>{row.quantity:.8f}</td>"
            f"<td>{row.notional:.8f}</td>"
            f"<td>{row.fee:.8f}</td>"
            f"<td>{escape(row.reason)}</td>"
            "</tr>"
        )
    return (
        summary
        + '<div class="pnl-table-wrap">'
        + '<table class="data-table">'
        + "<thead><tr><th>Waktu</th><th>Symbol</th><th>TF</th><th>Aksi</th><th>Side</th><th>Status</th><th>Price</th><th>Qty</th><th>Notional</th><th>Fee</th><th>Alasan</th></tr></thead>"
        + f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _pnl_summary_html(panel: PnlPanel) -> str:
    status, css, summary, next_action = _pnl_plain_status(panel)
    equity_delta_text = _equity_delta_text(panel)
    currency_label = _pnl_currency_label(panel)
    return (
        '<div class="pnl-summary">'
        + '<div class="pnl-summary-head">'
        + "<span>Kesimpulan Awam</span>"
        + f'<span class="badge {css}">{escape(status)}</span>'
        + "</div>"
        + f"<p>{escape(summary)}</p>"
        + f"<p><strong>Hitungan saldo:</strong> {escape(equity_delta_text)}</p>"
        + f"<p><strong>Satuan:</strong> {escape(currency_label)}. Ini bukan Rupiah kecuali bot memang memakai pair IDR.</p>"
        + f"<p><strong>Aksi berikut:</strong> {escape(next_action)}</p>"
        + "</div>"
    )


def _pnl_plain_status(panel: PnlPanel) -> tuple[str, str, str, str]:
    if panel.trade_count == 0:
        return (
            "Belum Ada Trade",
            "warn",
            "Bot belum punya trade paper/demo untuk dibaca. Belum bisa dinilai profit atau loss.",
            "Klik Demo Data atau jalankan siklus paper dulu.",
        )
    if panel.equity_change_pct >= 0 and panel.net_pnl >= 0:
        return (
            "Profit Demo",
            "ok",
            f"Saldo demo naik {panel.equity_change_pct:.2f}% dari awal dan total realized P/L positif {panel.net_pnl:.8f}.",
            "Lanjut pantau, jangan naik ke real live sebelum evidence paper cukup.",
        )
    if panel.equity_change_pct < 0 and panel.net_pnl <= 0:
        return (
            "Loss Demo",
            "danger",
            f"Saldo demo turun {abs(panel.equity_change_pct):.2f}% dari awal dan total realized P/L negatif {panel.net_pnl:.8f}.",
            "Pause eksperimen ini, cek trade terakhir, risk guard, dan market regime.",
        )
    if panel.equity_change_pct < 0 and panel.net_pnl > 0:
        return (
            "Campuran / Perlu Review",
            "warn",
            f"Trade tertutup masih mencatat realized P/L positif {panel.net_pnl:.8f}, tapi saldo demo terakhir turun {abs(panel.equity_change_pct):.2f}% dari awal.",
            "Anggap belum aman. Review equity curve, fees, dan trade terakhir sebelum percaya strategi.",
        )
    return (
        "Campuran / Perlu Review",
        "warn",
        f"Saldo demo naik {panel.equity_change_pct:.2f}%, tapi realized P/L total masih negatif {panel.net_pnl:.8f}.",
        "Review data akun dan trade detail sebelum mengambil kesimpulan.",
    )


def _equity_delta_text(panel: PnlPanel) -> str:
    delta = panel.latest_equity - panel.initial_equity
    return f"{panel.latest_equity:.2f} - {panel.initial_equity:.2f} = {delta:+.2f} {_pnl_currency_code(panel)}"


def _equity_delta_css(panel: PnlPanel) -> str:
    delta = panel.latest_equity - panel.initial_equity
    if delta > 0:
        return "delta-ok"
    if delta < 0:
        return "delta-danger"
    return "delta-flat"


def _pnl_currency_label(panel: PnlPanel) -> str:
    code = _pnl_currency_code(panel)
    if code == "USDT":
        return "USDT, patokan dollar stablecoin"
    if code == "USD":
        return "USD / Dollar"
    if code == "IDR":
        return "IDR / Rupiah"
    return code


def _pnl_currency_code(panel: PnlPanel) -> str:
    if panel.latest_trade and "/" in panel.latest_trade.symbol:
        return panel.latest_trade.symbol.rsplit("/", 1)[1].upper()
    return "USDT"


def _demo_walkthrough_html(steps: list[DemoWalkthroughStep]) -> str:
    if not steps:
        return '<p class="small">Walkthrough belum tersedia.</p>'
    cards = []
    for step in steps:
        css = _report_status_class(step.status)
        cards.append(
            '<div class="walk-step" title="'
            + escape(step.help_text)
            + '">'
            + '<div class="walk-head">'
            + '<div class="walk-title">'
            + f'<span class="walk-number">{step.number}</span>'
            + f"<strong>{escape(step.title)}</strong>"
            + "</div>"
            + f'<span class="badge {css}">{escape(step.status)}</span>'
            + "</div>"
            + f'<div class="walk-goal">{escape(step.goal)}</div>'
            + '<div class="walk-action">'
            + _walkthrough_button(step)
            + "</div>"
            + "</div>"
        )
    return '<div class="walkthrough">' + "".join(cards) + "</div>"


def _walkthrough_button(step: DemoWalkthroughStep) -> str:
    action_by_step = {
        2: "validate_config",
        3: "seed_demo_data",
        4: "evidence_campaign",
        6: "live_evidence",
    }
    scroll_by_step = {
        1: "mulai-di-sini",
        5: "pnl-monitor",
    }
    if step.number in action_by_step:
        action = action_by_step[step.number]
        return (
            f'<button type="button" class="btn" data-action="{escape(action)}" '
            f'title="{escape(step.help_text)}">{_action_icon(action)}{escape(step.action_label.replace("Klik ", ""))}</button>'
        )
    if step.number in scroll_by_step:
        target = scroll_by_step[step.number]
        return (
            f'<button type="button" class="btn" data-scroll="{escape(target)}" '
            f'title="{escape(step.help_text)}">{_svg_icon("play")}{escape(step.action_label.replace("Lihat ", "").replace("Buka ", ""))}</button>'
        )
    return f'<span class="small">{escape(step.action_label)}</span>'


def _local_demo_html(panel: LocalDemoPanel) -> str:
    status_css = _report_status_class(panel.status)
    live_css = "ok" if panel.live_locked else "danger"
    check_rows = []
    for check in panel.checks:
        name = str(check.get("name", ""))
        status = str(check.get("status", ""))
        reason = str(check.get("reason", ""))
        next_action = str(check.get("next_action", ""))
        check_rows.append(
            "<tr>"
            f"<td>{escape(name)}</td>"
            f'<td><span class="badge {_report_status_class(status)}">{escape(status)}</span></td>'
            f"<td>{escape(reason)}</td>"
            f"<td>{escape(next_action)}</td>"
            "</tr>"
        )
    rows = "".join(check_rows) if check_rows else '<tr><td colspan="4">Belum ada report. Klik Local Demo.</td></tr>'
    return (
        '<div class="grid">'
        + _metric("Status Demo Lokal", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Live Lock", f'<span class="badge {live_css}">{"LOCKED" if panel.live_locked else "CHECK"}</span>')
        + _metric("Candle Demo", panel.candle_rows)
        + _metric("Paper Trades", panel.paper_trades)
        + _metric("Reports", panel.report_count)
        + _metric("Summary", escape(panel.summary))
        + "</div>"
        '<table class="data-table">'
        "<thead><tr><th>Check</th><th>Status</th><th>Alasan</th><th>Aksi Berikut</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _vps_demo_html(panel: VpsDemoPanel) -> str:
    status_css = _report_status_class(panel.status)
    live_css = "ok" if panel.live_locked else "danger"
    rows = []
    for check in panel.checks:
        name = str(check.get("name", ""))
        status = str(check.get("status", ""))
        reason = str(check.get("reason", ""))
        next_action = str(check.get("next_action", ""))
        rows.append(
            "<tr>"
            f"<td>{escape(name)}</td>"
            f'<td><span class="badge {_report_status_class(status)}">{escape(status)}</span></td>'
            f"<td>{escape(reason)}</td>"
            f"<td>{escape(next_action)}</td>"
            "</tr>"
        )
    table_rows = "".join(rows) if rows else '<tr><td colspan="4">Belum ada report. Klik VPS Demo.</td></tr>'
    return (
        '<div class="grid">'
        + _metric("Status VPS Demo", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Live Lock", f'<span class="badge {live_css}">{"LOCKED" if panel.live_locked else "CHECK"}</span>')
        + _metric("Private URL", escape(panel.private_url or "127.0.0.1:8000 di VPS"))
        + _metric("Tunnel URL", escape(panel.tunnel_url or "127.0.0.1:18000 di laptop"))
        + _metric("Config VPS", escape(panel.vps_config_path or "config/bot.vps.sample.toml"))
        + _metric("Summary", escape(panel.summary))
        + "</div>"
        '<table class="data-table">'
        "<thead><tr><th>Check</th><th>Status</th><th>Alasan</th><th>Aksi Berikut</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table>"
    )


def _paper_campaign_html(panel: PaperCampaignPanel) -> str:
    status_css = _report_status_class(panel.status)
    pnl_css = "ok" if panel.total_net_pnl >= 0 else "danger"
    rows = []
    for pair in panel.pairs:
        status = str(pair.get("status", ""))
        blockers = pair.get("blockers", [])
        blocker_text = "; ".join(str(item) for item in blockers) if isinstance(blockers, list) else str(blockers)
        rows.append(
            "<tr>"
            f"<td>{escape(str(pair.get('symbol', '')))}</td>"
            f"<td>{escape(str(pair.get('timeframe', '')))}</td>"
            f'<td><span class="badge {_report_status_class(status)}">{escape(status)}</span></td>'
            f"<td>{int(pair.get('observed_days', 0) or 0)} / {int(pair.get('target_days', 0) or 0)}</td>"
            f"<td>{int(pair.get('trade_count', 0) or 0)} / {int(pair.get('target_trades', 0) or 0)}</td>"
            f"<td>{float(pair.get('net_pnl', 0) or 0):.8f}</td>"
            f"<td>{escape(blocker_text or '-')}</td>"
            "</tr>"
        )
    table_rows = "".join(rows) if rows else '<tr><td colspan="7">Belum ada report. Klik Paper Campaign.</td></tr>'
    blocker_rows = "".join(f"<li>{escape(blocker)}</li>" for blocker in panel.blockers[:6])
    blockers = f"<ul>{blocker_rows}</ul>" if blocker_rows else '<p class="small">Belum ada blocker aktif di report.</p>'
    return (
        '<div class="grid">'
        + _metric("Status Campaign", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Completion", f"{panel.completion_pct:.2f}%")
        + _metric("Stable Pairs", f"{panel.stable_pair_count} / {panel.pairs_checked}")
        + _metric("Paper Trades", panel.total_trade_count)
        + _metric("Net P/L Paper", f'<span class="badge {pnl_css}">{panel.total_net_pnl:.8f}</span>')
        + _metric("Summary", escape(panel.summary))
        + "</div>"
        + blockers
        + '<table class="data-table">'
        + "<thead><tr><th>Symbol</th><th>TF</th><th>Status</th><th>Hari</th><th>Trades</th><th>Net P/L</th><th>Blocker</th></tr></thead>"
        + f"<tbody>{table_rows}</tbody></table>"
    )


def _skill_loop_html(panel: SkillLoopPanel) -> str:
    status_css = _report_status_class(panel.status)
    pnl_css = "ok" if panel.paper_net_pnl >= 0 else "danger"
    step_rows = []
    for step in panel.steps:
        status = str(step.get("status", ""))
        step_rows.append(
            "<tr>"
            f"<td>{escape(str(step.get('name', '')))}</td>"
            f'<td><span class="badge {_report_status_class(status)}">{escape(status)}</span></td>'
            f"<td>{escape(str(step.get('metric', '')))}</td>"
            f"<td>{escape(str(step.get('finding', '')))}</td>"
            f"<td>{escape(str(step.get('next_action', '')))}</td>"
            "</tr>"
        )
    rows = "".join(step_rows) if step_rows else '<tr><td colspan="5">Belum ada report. Klik Skill Loop.</td></tr>'
    candidates = "".join(f"<li>{escape(str(candidate))}</li>" for candidate in panel.experiment_candidates[:6])
    candidate_html = f"<ul>{candidates}</ul>" if candidates else '<p class="small">Belum ada kandidat eksperimen.</p>'
    return (
        '<div class="grid">'
        + _metric("Status Skill Loop", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Candles", panel.candle_rows)
        + _metric("Paper Trades", panel.paper_trades)
        + _metric("Paper Net P/L", f'<span class="badge {pnl_css}">{panel.paper_net_pnl:.8f}</span>')
        + _metric("Learning Rows", panel.learning_rows)
        + _metric("Evidence", f"{panel.evidence_completion_pct:.2f}%")
        + "</div>"
        + f'<p class="small">{escape(panel.guardrail)}</p>'
        + candidate_html
        + '<table class="data-table">'
        + "<thead><tr><th>Step</th><th>Status</th><th>Metric</th><th>Finding</th><th>Aksi Berikut</th></tr></thead>"
        + f"<tbody>{rows}</tbody></table>"
    )


def _pattern_memory_html(panel: PatternMemoryPanel) -> str:
    status_css = _report_status_class(panel.status)
    table_rows = []
    for row in panel.rows:
        grade = str(row.get("outcome_grade", ""))
        labels = row.get("labels", [])
        label_text = ", ".join(str(label) for label in labels) if isinstance(labels, list) else str(labels)
        pnl = float(row.get("total_net_pnl", 0) or 0)
        table_rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('symbol', '')))}</td>"
            f"<td>{escape(str(row.get('timeframe', '')))}</td>"
            f"<td>{escape(str(row.get('observation', '')))}</td>"
            f'<td><span class="badge {_report_status_class(grade)}">{escape(grade)}</span></td>'
            f"<td>{int(row.get('trade_count', 0) or 0)}</td>"
            f"<td>{float(row.get('win_rate_pct', 0) or 0):.2f}%</td>"
            f"<td>{pnl:.8f}</td>"
            f"<td>{escape(label_text or '-')}</td>"
            f"<td>{escape(str(row.get('next_action', '')))}</td>"
            "</tr>"
        )
    rows = "".join(table_rows) if table_rows else '<tr><td colspan="9">Belum ada report. Klik Pattern Memory.</td></tr>'
    return (
        '<div class="grid">'
        + _metric("Status Memory", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Rows", panel.row_count)
        + _metric("Trades", panel.total_trades)
        + _metric("Manual Labels", panel.total_labels)
        + _metric("Summary", escape(panel.summary))
        + "</div>"
        + f'<p class="small">{escape(panel.guardrail)}</p>'
        + '<table class="data-table">'
        + "<thead><tr><th>Symbol</th><th>TF</th><th>Observation</th><th>Grade</th><th>Trades</th><th>Win Rate</th><th>P/L</th><th>Labels</th><th>Aksi Berikut</th></tr></thead>"
        + f"<tbody>{rows}</tbody></table>"
    )


def _learning_dashboard_html(panel: LearningDashboardPanel) -> str:
    status_css = _report_status_class(panel.status)
    rows = []
    for trend in panel.trends:
        trend_status = str(trend.get("status", ""))
        volume_spike = "Ya" if bool(trend.get("volume_spike", False)) else "Tidak"
        pnl = float(trend.get("total_net_pnl", 0) or 0)
        pnl_css = "ok" if pnl >= 0 else "danger"
        rows.append(
            "<tr>"
            f"<td>{escape(str(trend.get('symbol', '')))}</td>"
            f"<td>{escape(str(trend.get('timeframe', '')))}</td>"
            f"<td>{escape(str(trend.get('observation', '')))}</td>"
            f"<td>{escape(str(trend.get('outcome_grade', '')))}</td>"
            f'<td><span class="badge {_report_status_class(trend_status)}">{escape(trend_status)}</span></td>'
            f"<td>{float(trend.get('evidence_score', 0) or 0):.2f}</td>"
            f"<td>{volume_spike}</td>"
            f"<td>{int(trend.get('trade_count', 0) or 0)}</td>"
            f"<td>{float(trend.get('win_rate_pct', 0) or 0):.2f}%</td>"
            f'<td><span class="badge {pnl_css}">{pnl:.8f}</span></td>'
            f"<td>{escape(str(trend.get('next_action', '')))}</td>"
            "</tr>"
        )
    table_rows = "".join(rows) if rows else '<tr><td colspan="11">Belum ada report. Klik Learning Dashboard.</td></tr>'
    return (
        '<div class="grid">'
        + _metric("Status Dashboard", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Trend", panel.trend_count)
        + _metric("Promising", panel.promising_count)
        + _metric("Perlu Review", panel.weak_count)
        + _metric("Volume Spike", panel.volume_spike_count)
        + _metric("Avg Evidence Score", f"{panel.average_evidence_score:.2f}")
        + "</div>"
        + f'<p class="small">{escape(panel.guardrail)}</p>'
        + '<table class="data-table">'
        + "<thead><tr><th>Symbol</th><th>TF</th><th>Observation</th><th>Grade</th><th>Status</th><th>Score</th><th>Volume Spike</th><th>Trades</th><th>Win Rate</th><th>P/L</th><th>Aksi Berikut</th></tr></thead>"
        + f"<tbody>{table_rows}</tbody></table>"
    )


def _human_feedback_html(panel: HumanFeedbackPanel) -> str:
    status_css = _report_status_class(panel.status)
    label_rows = []
    for label in panel.recent_labels:
        label_rows.append(
            "<tr>"
            f"<td>{escape(str(label.get('created_at_utc', '')))}</td>"
            f"<td>{escape(str(label.get('symbol', '')))}</td>"
            f"<td>{escape(str(label.get('timeframe', '')))}</td>"
            f"<td>{escape(str(label.get('label', '')))}</td>"
            f"<td>{escape(str(label.get('note', '')))}</td>"
            f"<td>{escape(str(label.get('reviewer', '')))}</td>"
            "</tr>"
        )
    recent_rows = "".join(label_rows) if label_rows else '<tr><td colspan="6">Belum ada label. Tambahkan via command add-feedback-label.</td></tr>'
    lesson_rows = []
    for lesson in panel.lessons:
        lesson_rows.append(
            "<tr>"
            f"<td>{escape(str(lesson.get('label', '')))}</td>"
            f"<td>{int(lesson.get('count', 0) or 0)}</td>"
            f"<td>{escape(str(lesson.get('lesson', '')))}</td>"
            f"<td>{escape(str(lesson.get('next_action', '')))}</td>"
            "</tr>"
        )
    lessons = "".join(lesson_rows) if lesson_rows else '<tr><td colspan="4">Belum ada lesson dari feedback.</td></tr>'
    allowed = ", ".join(panel.allowed_labels) if panel.allowed_labels else "-"
    return (
        '<div class="grid">'
        + _metric("Status Feedback", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Total Labels", panel.total_labels)
        + _metric("Pairs Labeled", panel.pairs_labeled)
        + _metric("Top Label", escape(panel.top_label))
        + _metric("Summary", escape(panel.summary))
        + "</div>"
        + f'<p class="small">{escape(panel.guardrail)}</p>'
        + f'<p class="small">Allowed labels: <code>{escape(allowed)}</code></p>'
        + '<table class="data-table">'
        + "<thead><tr><th>Label</th><th>Count</th><th>Lesson</th><th>Aksi Berikut</th></tr></thead>"
        + f"<tbody>{lessons}</tbody></table>"
        + '<div style="height:10px"></div>'
        + '<table class="data-table">'
        + "<thead><tr><th>Waktu</th><th>Symbol</th><th>TF</th><th>Label</th><th>Note</th><th>Reviewer</th></tr></thead>"
        + f"<tbody>{recent_rows}</tbody></table>"
    )


def _fundamental_html(panel: FundamentalPanel) -> str:
    status_css = _report_status_class(panel.status)
    risk_css = {
        "green": "ok",
        "yellow": "warn",
        "orange": "warn",
        "red": "danger",
    }.get(panel.color, "ok")
    event_rows = []
    for event in panel.events:
        event_risk = str(event.get("risk", "LOW"))
        event_color = "danger" if event_risk == "BLOCK" else "warn" if event_risk in {"HIGH", "MEDIUM"} else "ok"
        event_rows.append(
            "<tr>"
            f"<td>{escape(str(event.get('event_time_utc', '')))}</td>"
            f"<td>{escape(str(event.get('symbol', '')))}</td>"
            f"<td>{escape(str(event.get('category', '')))}</td>"
            f'<td><span class="badge {event_color}">{escape(event_risk)}</span></td>'
            f"<td>{escape(str(event.get('title', '')))}</td>"
            f"<td>{escape(str(event.get('source', '')))}</td>"
            f"<td>{escape(str(event.get('note', '')))}</td>"
            "</tr>"
        )
    rows = "".join(event_rows) if event_rows else '<tr><td colspan="7">Belum ada event manual. Default demo dianggap clear.</td></tr>'
    return (
        '<div class="grid">'
        + _metric("Status Fundamental", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Risk Color", f'<span class="badge {risk_css}">{escape(panel.top_risk)} / {escape(panel.color)}</span>')
        + _metric("Total Events", panel.total_events)
        + _metric("High/Block", panel.high_or_block_events)
        + _metric("Summary", escape(panel.summary))
        + "</div>"
        + f'<p class="small">{escape(panel.guardrail)}</p>'
        + '<table class="data-table">'
        + "<thead><tr><th>Waktu Event</th><th>Symbol</th><th>Kategori</th><th>Risk</th><th>Judul</th><th>Source</th><th>Note</th></tr></thead>"
        + f"<tbody>{rows}</tbody></table>"
    )


def _experiment_scoreboard_html(panel: ExperimentScoreboardPanel) -> str:
    status_css = _report_status_class(panel.status)
    rows = []
    for row in panel.rows:
        recommendation = str(row.get("recommendation", "NEEDS_EVIDENCE"))
        rec_css = "ok" if recommendation == "PAPER_CANDIDATE" else "danger" if recommendation == "REJECTED" else "warn"
        rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('strategy_id', '')))}</td>"
            f"<td>{escape(str(row.get('version', '')))}</td>"
            f"<td>{escape(str(row.get('status', '')))}</td>"
            f"<td>{float(row.get('total_score', 0) or 0):.2f}</td>"
            f'<td><span class="badge {rec_css}">{escape(recommendation)}</span></td>'
            f"<td>{escape(str(row.get('hypothesis', '')))}</td>"
            f"<td>{escape(str(row.get('source', '')))}</td>"
            "</tr>"
        )
    table_rows = "".join(rows) if rows else '<tr><td colspan="7">Belum ada eksperimen strategi. Tambahkan ide dari review pattern/feedback.</td></tr>'
    return (
        '<div class="grid">'
        + _metric("Status Scoreboard", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Experiments", panel.experiment_count)
        + _metric("Top Strategy", escape(panel.top_strategy))
        + _metric("Summary", escape(panel.summary))
        + "</div>"
        + f'<p class="small">{escape(panel.guardrail)}</p>'
        + '<table class="data-table">'
        + "<thead><tr><th>Strategy</th><th>Version</th><th>Status</th><th>Score</th><th>Rekomendasi</th><th>Hipotesis</th><th>Source</th></tr></thead>"
        + f"<tbody>{table_rows}</tbody></table>"
    )


def _walkthrough_status(check: SetupCheck | None) -> str:
    if check is None:
        return "TODO"
    return "PASS" if check.status == "PASS" else "TODO"


def _equity_svg(points: list[float]) -> str:
    if not points:
        return '<svg viewBox="0 0 420 160" role="img" aria-label="Belum ada equity curve"><text x="18" y="84" fill="#64748b" font-size="14">Belum ada equity curve.</text></svg>'
    width = 420
    height = 160
    pad = 14
    min_value = min(points)
    max_value = max(points)
    span = max(max_value - min_value, 1e-9)
    coords = []
    for index, value in enumerate(points):
        x = pad + (index / max(len(points) - 1, 1)) * (width - pad * 2)
        y = height - pad - ((value - min_value) / span) * (height - pad * 2)
        coords.append((x, y))
    line = " ".join(f"{x:.2f},{y:.2f}" for x, y in coords)
    fill = f"{pad},{height - pad} " + line + f" {width - pad},{height - pad}"
    zero_y = height - pad - ((points[0] - min_value) / span) * (height - pad * 2)
    return (
        '<svg viewBox="0 0 420 160" role="img" aria-label="Equity curve demo">'
        f'<polyline class="pnl-fill" points="{fill}"></polyline>'
        f'<line class="pnl-zero" x1="{pad}" y1="{zero_y:.2f}" x2="{width - pad}" y2="{zero_y:.2f}"></line>'
        f'<polyline class="pnl-line" points="{line}"></polyline>'
        f'<text x="{pad}" y="18" fill="#64748b" font-size="12">Start {points[0]:.2f}</text>'
        f'<text x="{width - 112}" y="18" fill="#64748b" font-size="12">Now {points[-1]:.2f}</text>'
        "</svg>"
    )


def _health_card(label: str, status: str, reason: str) -> str:
    css = "danger" if status in {"BLOCKED", "NO_GO"} else "warn" if status in {"MISSING", "NO_TRADES"} else "ok"
    return (
        '<div class="panel metric">'
        f"<span>{escape(label)}</span>"
        f'<strong><span class="badge {css}">{escape(status)}</span></strong>'
        f'<div class="small">{escape(reason)}</div>'
        "</div>"
    )


def _setup_html(checks: list[SetupCheck]) -> str:
    if not checks:
        return '<p class="small">Checklist setup belum tersedia.</p>'
    rows = []
    for check in checks:
        css = "ok" if check.status == "PASS" else "danger" if check.status == "FAIL" else "warn"
        rows.append(
            "<tr>"
            f"<td>{escape(check.name)}</td>"
            f'<td><span class="badge {css}">{escape(check.status)}</span></td>'
            f"<td>{escape(check.reason)}</td>"
            f"<td>{escape(check.next_action)}</td>"
            "</tr>"
        )
    return (
        '<table class="data-table">'
        "<thead><tr><th>Check</th><th>Status</th><th>Alasan</th><th>Berikutnya</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _reports_html(reports: list[ReportItem]) -> str:
    if not reports:
        return '<p class="small">Belum ada laporan. Jalankan Backtest, Walk-Forward, Paper, atau Daily Journal terlebih dahulu.</p>'
    rows = []
    for report in reports[:20]:
        css = _report_status_class(report.status)
        rows.append(
            "<tr>"
            f"<td>{escape(report.category)}</td>"
            f"<td>{escape(report.name)}</td>"
            f'<td><span class="badge {css}">{escape(report.status)}</span></td>'
            f"<td>{escape(report.summary)}</td>"
            f"<td><code>{escape(report.path)}</code></td>"
            f"<td>{escape(report.updated_at_utc)}</td>"
            "</tr>"
        )
    return (
        '<table class="data-table">'
        "<thead><tr><th>Tipe</th><th>Nama</th><th>Status</th><th>Ringkasan</th><th>Path</th><th>Update</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _incident_html(panel: IncidentPanel) -> str:
    kill_css = "danger" if panel.kill_switch_active else "ok"
    incident_css = _report_status_class(panel.incident_status)
    return (
        '<div class="grid">'
        + _metric("Kill Switch", f'<span class="badge {kill_css}">{"ACTIVE" if panel.kill_switch_active else "CLEAR"}</span>')
        + _metric("Alasan Kill", panel.kill_switch_reason or "-")
        + _metric("Incident Drill", f'<span class="badge {incident_css}">{escape(panel.incident_status)}</span>')
        + _metric("Skenario", f"{panel.scenario_count}: {panel.scenario_summary}")
        + "</div>"
    )


def _database_html(panel: DatabasePanel) -> str:
    if not panel.exists:
        return (
            '<p class="small">Database belum ada. Klik Import DB untuk membuat '
            f'<code>{escape(panel.db_path or "work/market_data/bot.sqlite3")}</code>.</p>'
        )
    rows = []
    for table, count in panel.table_rows.items():
        rows.append(
            "<tr>"
            f"<td>{escape(table)}</td>"
            f"<td>{count}</td>"
            "</tr>"
        )
    table_html = (
        '<table class="data-table">'
        "<thead><tr><th>Tabel</th><th>Rows</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    return (
        '<div class="grid">'
        + _metric("Total Rows", panel.total_rows)
        + _metric("Ukuran DB", f"{panel.size_bytes} bytes")
        + _metric("Update", panel.updated_at_utc or "-")
        + "</div>"
        + f"<p class=\"small\">Path: <code>{escape(panel.db_path)}</code></p>"
        + table_html
    )


def _database_panel_from_status(status: DatabaseStatus) -> DatabasePanel:
    return DatabasePanel(
        db_path=status.db_path,
        exists=status.exists,
        size_bytes=status.size_bytes,
        updated_at_utc=status.updated_at_utc,
        total_rows=status.total_rows,
        table_rows={table.table: table.rows for table in status.tables},
    )


def _testnet_demo_html(panel: TestnetDemoPanel) -> str:
    if not panel.exists:
        return (
            '<p class="small">Belum ada report demo/testnet. Klik '
            '<strong>Testnet Demo</strong> untuk membuat simulasi akun demo.</p>'
        )
    status_css = "ok" if panel.status == "PASSED" else "danger" if panel.status == "FAILED" else "warn"
    live_guard_css = "ok" if panel.live_guard_status == "PASS" else "danger"
    rows = []
    for order in panel.orders:
        if not isinstance(order, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{escape(str(order.get('order_id', '')))}</td>"
            f"<td>{escape(str(order.get('symbol', '')))}</td>"
            f"<td>{escape(str(order.get('side', '')))}</td>"
            f"<td>{escape(str(order.get('order_type', '')))}</td>"
            f"<td>{escape(str(order.get('quantity', '')))}</td>"
            f"<td>{escape(str(order.get('status', '')))}</td>"
            f"<td>{escape(str(order.get('source', '')))}</td>"
            "</tr>"
        )
    order_table = (
        '<table class="data-table">'
        "<thead><tr><th>Order ID</th><th>Symbol</th><th>Side</th><th>Type</th><th>Qty</th><th>Status</th><th>Source</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    notes = "".join(f"<li>{escape(str(note))}</li>" for note in panel.notes)
    return (
        '<div class="grid">'
        + _metric("Status Demo", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Environment", panel.environment or "-")
        + _metric("Orders", panel.order_count)
        + _metric("Live Guard", f'<span class="badge {live_guard_css}">{escape(panel.live_guard_status)}</span>')
        + "</div>"
        + f'<p class="small">Generated: {escape(panel.generated_at_utc or "-")}</p>'
        + f'<p class="small">Live guard reason: {escape(panel.live_guard_reason or "-")}</p>'
        + order_table
        + (f'<ul class="small">{notes}</ul>' if notes else "")
        + f'<p class="small">Path: <code>{escape(panel.report_path)}</code></p>'
    )


def _live_evidence_html(panel: LiveEvidencePanel) -> str:
    if not panel.exists:
        return (
            '<p class="small">Belum ada live evidence report. Klik '
            '<strong>Live Evidence</strong> untuk membuat checklist kesiapan live.</p>'
        )
    status_css = _report_status_class(panel.status)
    blocker_rows = "".join(
        "<tr>"
        f"<td>{escape(str(blocker))}</td>"
        "</tr>"
        for blocker in panel.blockers[:10]
    )
    blocker_table = (
        '<table class="data-table">'
        "<thead><tr><th>Blocker</th></tr></thead>"
        "<tbody>"
        + (blocker_rows or "<tr><td>Tidak ada blocker aktif.</td></tr>")
        + "</tbody></table>"
    )
    item_rows = []
    for item in panel.items:
        if not isinstance(item, dict):
            continue
        item_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('name', '')))}</td>"
            f'<td><span class="badge {_report_status_class(str(item.get("status", "")))}">{escape(str(item.get("status", "")))}</span></td>'
            f"<td>{escape(str(item.get('reason', '')))}</td>"
            f"<td>{escape(str(item.get('next_action', '')))}</td>"
            "</tr>"
        )
    item_table = (
        '<table class="data-table">'
        "<thead><tr><th>Evidence</th><th>Status</th><th>Alasan</th><th>Aksi Berikutnya</th></tr></thead>"
        "<tbody>"
        + "".join(item_rows[:20])
        + "</tbody></table>"
    )
    return (
        '<div class="grid">'
        + _metric("Status Evidence", f'<span class="badge {status_css}">{escape(panel.status)}</span>')
        + _metric("Completion", f"{panel.completion_pct:.2f}%")
        + _metric("Blockers", panel.blocker_count)
        + _metric("Generated", panel.generated_at_utc or "-")
        + "</div>"
        + f'<p class="small">{escape(panel.summary or "report available")}</p>'
        + blocker_table
        + item_table
        + f'<p class="small">Path: <code>{escape(panel.report_path)}</code></p>'
    )


def _json_report_items(root: Path, category: str, pattern: str) -> list[ReportItem]:
    if not root.exists():
        return []
    items: list[ReportItem] = []
    for path in root.rglob(pattern):
        payload = _read_json(path)
        if payload is None:
            items.append(_report_item(category, path, "INVALID", "invalid JSON"))
            continue
        status = _report_status(payload)
        summary = _report_summary(payload)
        items.append(_report_item(category, path, status, summary))
    return items


def _paper_report_items(root: Path) -> list[ReportItem]:
    if not root.exists():
        return []
    items: list[ReportItem] = []
    for path in root.rglob("*.csv"):
        row_count = _csv_row_count(path)
        status = "ACTIVE" if row_count else "EMPTY"
        items.append(_report_item("Paper", path, status, f"rows={row_count}"))
    return items


def _report_item(category: str, path: Path, status: str, summary: str) -> ReportItem:
    stat = path.stat()
    return ReportItem(
        category=category,
        name=_report_name(path),
        status=status,
        summary=summary,
        path=str(path),
        updated_at_utc=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        size_bytes=stat.st_size,
    )


def _report_name(path: Path) -> str:
    parts = list(path.parts)
    if len(parts) >= 3:
        return " / ".join(parts[-3:])
    return path.name


def _report_status(payload: dict) -> str:
    for key in ("recommendation", "review_status", "status", "decision"):
        value = payload.get(key)
        if value:
            return str(value)
    return "AVAILABLE"


def _report_summary(payload: dict) -> str:
    keys = [
        "reason",
        "trade_count",
        "total_test_trades",
        "paper_trade_count",
        "paper_net_pnl",
        "total_return_pct",
        "average_test_return_pct",
        "max_drawdown_pct",
        "review_status",
    ]
    parts = []
    for key in keys:
        if key in payload and payload[key] is not None:
            parts.append(f"{key}={payload[key]}")
        if len(parts) >= 4:
            break
    if not parts and isinstance(payload.get("notes"), list):
        parts.append("notes=" + "; ".join(str(note) for note in payload["notes"][:2]))
    return ", ".join(parts) if parts else "report available"


def _report_status_class(status: str) -> str:
    normalized = status.upper()
    if normalized in {"REJECT", "NO_GO", "BLOCKED", "FAILED", "REVIEW_REQUIRED", "INVALID", "WEAK"}:
        return "danger"
    if normalized in {"NOT_ENOUGH_DATA", "NEEDS_FILTER", "NO_DATA", "EMPTY", "MISSING", "NO_TRADES", "NEEDS_MORE_TRADES", "MIXED"}:
        return "warn"
    return "ok"


def _plain_status_class(status: str) -> str:
    normalized = status.lower()
    if normalized in {"stop", "belum siap", "stop / cek dulu"}:
        return "danger"
    if normalized in {"perlu data", "pantau", "belum ada", "menunggu", "demo aman"}:
        return "warn"
    return "ok"


def _csv_row_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with path.open("r", newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _level_class(level: str) -> str:
    normalized = level.upper()
    if normalized in {"ERROR", "CRITICAL"}:
        return "danger"
    if normalized == "WARNING":
        return "warn"
    return "ok"


def _context_summary(context: dict) -> str:
    parts = []
    for key in ("symbol", "timeframe", "reason"):
        value = context.get(key)
        if value:
            parts.append(f"{key}={value}")
    return " | " + escape(", ".join(parts)) if parts else ""


def _help_text_for(label: str) -> str:
    normalized = label.strip().lower()
    direct = {
        entry.term.lower(): f"{entry.plain_meaning} {entry.watch_for}"
        for entry in load_glossary_entries()
    }
    aliases = {
        "p/l demo": direct["p/l"],
        "paper net p/l": direct["p/l"],
        "net p/l paper": direct["p/l"],
        "realized p/l demo": direct["p/l"],
        "evidence": direct["evidence"],
        "avg evidence score": direct["evidence score"],
        "status dashboard": "Ringkasan apakah dashboard belajar sudah punya data yang bisa dibaca.",
        "learning dashboard": "Ringkasan pola, volume, outcome paper, dan evidence score.",
        "human feedback": "Ringkasan label manual dari review chart/trade untuk lesson bot.",
        "validasi config": "Cek mode bot, live lock, dan simbol tanpa melakukan order.",
        "import db": "Masukkan data CSV/JSON lokal ke SQLite agar bisa dipelajari.",
        "learning db": "Buat snapshot pola dari database lokal.",
        "jalankan siklus": "Ambil candle terbaru, proses analisa paper, update laporan, lalu refresh P/L demo. Tetap tidak membuat order live.",
        "live evidence": direct["evidence"],
        "paper campaign": direct["paper/demo"],
        "kill switch": direct["kill switch"],
    }
    if normalized in direct:
        return direct[normalized]
    return aliases.get(normalized, "")


def _action_label(action: str) -> str:
    labels = {
        "validate_config": "Validasi Config",
        "seed_demo_data": "Demo Data",
        "local_demo": "Local Demo",
        "vps_demo": "VPS Demo",
        "import_runtime_db": "Import DB",
        "db_learning_report": "Learning DB",
        "skill_loop": "Skill Loop",
        "pattern_memory": "Pattern Memory",
        "learning_dashboard": "Learning Dashboard",
        "human_feedback": "Human Feedback",
        "build_dashboard": "Buat Dashboard",
        "security_qa": "Security QA",
        "production_smoke": "Production Smoke",
        "incident_drill": "Incident Drill",
        "live_go_no_go": "Live Go/No-Go",
        "live_evidence": "Live Evidence",
        "evidence_campaign": "Evidence Campaign",
        "testnet_demo": "Testnet Demo",
        "paper_campaign": "Paper Campaign",
        "run_cycle": "Jalankan Siklus",
        "sync_btc_15m": "Sinkron BTC 15m",
        "sync_eth_15m": "Sinkron ETH 15m",
    }
    return labels.get(action, action.replace("_", " ").title())


def _json_reports(root: Path) -> list[dict]:
    if not root.exists():
        return []
    reports: list[dict] = []
    for path in root.rglob("*.json"):
        payload = _read_json(path)
        if payload is not None:
            reports.append(payload)
    return reports


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


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


def _read_candle_rows(root: Path, symbol: str, timeframe: str) -> list[dict[str, str]]:
    path = root / symbol.replace("/", "_") / f"{timeframe}.csv"
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: int(row.get("open_time_ms", 0) or 0))
    return rows


def _safe_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def _load_paper_trade_rows(root: Path) -> list[PnlTradeRow]:
    rows: list[PnlTradeRow] = []
    if not root.exists():
        return rows
    for path in root.rglob("trades.csv"):
        if not path.exists() or path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    rows.append(
                        PnlTradeRow(
                            symbol=str(row.get("symbol", "")),
                            timeframe=str(row.get("timeframe", "")),
                            exit_time=_format_ms(row.get("exit_time_ms", "")),
                            entry_price=float(row.get("entry_price", 0) or 0),
                            exit_price=float(row.get("exit_price", 0) or 0),
                            net_pnl=float(row.get("net_pnl", 0) or 0),
                            exit_reason=str(row.get("exit_reason", "")),
                        )
                    )
                except ValueError:
                    continue
    return sorted(rows, key=lambda trade: trade.exit_time)


def _aggregate_daily_pnl_rows(trades: list[PnlTradeRow]) -> list[DailyPnlRow]:
    buckets: dict[str, list[PnlTradeRow]] = {}
    for trade in trades:
        date = trade.exit_time.split("T", 1)[0] if trade.exit_time else "-"
        buckets.setdefault(date, []).append(trade)
    rows: list[DailyPnlRow] = []
    for date, day_trades in sorted(buckets.items(), reverse=True):
        net_pnl = sum(trade.net_pnl for trade in day_trades)
        result = "Profit" if net_pnl > 0 else "Loss" if net_pnl < 0 else "Flat"
        rows.append(
            DailyPnlRow(
                date=date,
                trade_count=len(day_trades),
                net_pnl=net_pnl,
                best_trade_pnl=max(trade.net_pnl for trade in day_trades),
                worst_trade_pnl=min(trade.net_pnl for trade in day_trades),
                result=result,
            )
        )
    return rows


def _load_paper_order_rows(root: Path) -> list[PaperExecutionRow]:
    rows: list[PaperExecutionRow] = []
    if not root.exists():
        return rows
    for path in root.rglob("orders.csv"):
        if not path.exists() or path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    rows.append(
                        PaperExecutionRow(
                            time_utc=_format_ms(row.get("open_time_ms", "")),
                            symbol=str(row.get("symbol", "")),
                            timeframe=str(row.get("timeframe", "")),
                            action=str(row.get("action", "")),
                            side=str(row.get("side", "")),
                            status=str(row.get("status", "")),
                            price=float(row.get("price", 0) or 0),
                            quantity=float(row.get("quantity", 0) or 0),
                            notional=float(row.get("notional", 0) or 0),
                            fee=float(row.get("fee", 0) or 0),
                            reason=str(row.get("reason", "")),
                        )
                    )
                except ValueError:
                    continue
    return sorted(rows, key=lambda order: order.time_utc)


def _load_latest_position_snapshot(root: Path) -> PaperPositionSnapshot | None:
    snapshots: list[tuple[int, PaperPositionSnapshot]] = []
    if not root.exists():
        return None
    for path in root.rglob("account.csv"):
        if not path.exists() or path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    open_time_ms = int(row.get("open_time_ms", 0) or 0)
                    snapshots.append(
                        (
                            open_time_ms,
                            PaperPositionSnapshot(
                                time_utc=_format_ms(open_time_ms),
                                equity=float(row.get("equity", 0) or 0),
                                day_start_equity=float(row.get("day_start_equity", 0) or 0),
                                open_positions=int(row.get("open_positions", 0) or 0),
                                trading_status=str(row.get("trading_status", "") or "UNKNOWN"),
                                status_reason=str(row.get("status_reason", "") or ""),
                            ),
                        )
                    )
                except ValueError:
                    continue
    if not snapshots:
        return None
    return sorted(snapshots, key=lambda item: item[0])[-1][1]


def _load_equity_series(root: Path) -> list[list[float]]:
    series: list[list[float]] = []
    if not root.exists():
        return series
    for path in root.rglob("account.csv"):
        if not path.exists() or path.stat().st_size == 0:
            continue
        points: list[tuple[int, float]] = []
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    points.append((int(row.get("open_time_ms", 0) or 0), float(row.get("equity", 0) or 0)))
                except ValueError:
                    continue
        if points:
            series.append([equity for _, equity in sorted(points)])
    return series


def _aggregate_equity_points(series: list[list[float]], limit: int) -> list[float]:
    if not series:
        return []
    points: list[float] = []
    for index in range(limit):
        total = 0.0
        for row in series:
            source_index = round(index * (len(row) - 1) / max(limit - 1, 1))
            total += row[source_index]
        points.append(total)
    return points


def _format_ms(value: object) -> str:
    try:
        timestamp = int(str(value)) / 1000
    except ValueError:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="minutes")


def _sum_csv_float(root: Path, filename: str, field: str) -> float:
    if not root.exists():
        return 0.0
    total = 0.0
    for path in root.rglob(filename):
        if path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    total += float(row.get(field, 0) or 0)
                except ValueError:
                    continue
    return total
