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


ACTIONS: dict[str, tuple[str, ...]] = {
    "validate_config": ("validate-config", "--config", "{config}"),
    "import_runtime_db": ("import-runtime-db", "--config", "{config}"),
    "build_dashboard": ("build-dashboard", "--config", "{config}"),
    "security_qa": ("security-qa-report", "--config", "{config}", "--env-file", ".env.example", "--scan-root", "."),
    "production_smoke": ("production-smoke-report", "--config", "{config}"),
    "incident_drill": ("incident-drill-report", "--config", "{config}"),
    "live_go_no_go": ("live-go-no-go-report", "--config", "{config}"),
    "run_cycle": ("run-cycle", "--config", "{config}", "--limit", "{limit}"),
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
                "Klik Jalankan Siklus atau Sinkron untuk membuat data",
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
    incident: IncidentPanel | None = None,
) -> str:
    activities = activities or []
    audit_events = audit_events or []
    health = health or HealthSummary("MISSING", "", "MISSING", "", "MISSING", "", "MISSING", "")
    setup_checks = setup_checks or []
    reports = reports or []
    incident = incident or IncidentPanel(False, "", "", "MISSING", "", 0, "belum ada laporan incident drill")
    action_buttons = "".join(_action_button(action, status.action_running) for action in ACTIONS)
    activity_html = _activity_html(activities)
    audit_html = _audit_html(audit_events)
    health_html = _health_html(health)
    setup_html = _setup_html(setup_checks)
    reports_html = _reports_html(reports)
    incident_html = _incident_html(incident)
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
    .metric {{ min-height: 86px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; font-weight: 600; margin-bottom: 8px; }}
    .metric strong {{ display: block; font-size: 18px; font-weight: 800; overflow-wrap: anywhere; }}
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
      <p class="small">Urutan awal yang disarankan: Validasi Config, Security QA, Buat Dashboard, lalu Jalankan Siklus.</p>
    </section>
    <section class="panel">
      <h2>Browser Laporan</h2>
      <div>{reports_html}</div>
      <p class="small">Laporan ini read-only dari file lokal paper/research.</p>
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
                if parsed.path == "/api/incident":
                    self._json_response(asdict(load_incident_panel(config_path)))
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
                incident = load_incident_panel(config_path)
                self._html_response(build_orchestrator_page(status, activities, audit_events, health, setup, reports, incident))
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
    return (
        f'<button type="button" class="btn" data-action="{escape(action)}" {"disabled" if disabled else ""} '
        f'title="{escape(_action_label(action))}">{icon}{escape(_action_label(action))}</button>'
    )


def _action_icon(action: str) -> str:
    if "sync" in action:
        return _svg_icon("refresh")
    if "security" in action or "go_no_go" in action or "incident" in action:
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


def _metric(label: str, value: object) -> str:
    return (
        '<div class="panel metric">'
        f"<span>{escape(str(label))}</span>"
        f"<strong>{value if str(value).startswith('<') else escape(str(value))}</strong>"
        "</div>"
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
    if normalized in {"REJECT", "NO_GO", "BLOCKED", "FAILED", "REVIEW_REQUIRED", "INVALID"}:
        return "danger"
    if normalized in {"NOT_ENOUGH_DATA", "NEEDS_FILTER", "NO_DATA", "EMPTY", "MISSING"}:
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


def _action_label(action: str) -> str:
    labels = {
        "validate_config": "Validasi Config",
        "import_runtime_db": "Import DB",
        "build_dashboard": "Buat Dashboard",
        "security_qa": "Security QA",
        "production_smoke": "Production Smoke",
        "incident_drill": "Incident Drill",
        "live_go_no_go": "Live Go/No-Go",
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
