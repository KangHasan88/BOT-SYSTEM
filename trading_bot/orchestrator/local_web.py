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
from trading_bot.safety import read_kill_switch


ACTIONS: dict[str, tuple[str, ...]] = {
    "validate_config": ("validate-config", "--config", "{config}"),
    "build_dashboard": ("build-dashboard", "--config", "{config}"),
    "security_qa": ("security-qa-report", "--config", "{config}", "--env-file", ".env.example", "--scan-root", "."),
    "production_smoke": ("production-smoke-report", "--config", "{config}"),
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
        checks.append(SetupCheck("Config", "PASS", "config file is valid", ""))
        checks.append(
            SetupCheck(
                "Live Guard",
                "PASS" if not config.live_enabled else "FAIL",
                "live is disabled" if not config.live_enabled else "live must be disabled",
                "Keep BOT_LIVE_ENABLED=false",
            )
        )
        checks.append(
            SetupCheck(
                "Data Root",
                "PASS" if root.exists() else "TODO",
                str(root),
                "Click Run Cycle or Sync to create data files",
            )
        )
        checks.append(
            SetupCheck(
                "Security QA",
                "PASS" if _json_value(root / "qa" / "security" / "report.json", "status", "") == "PASSED" else "TODO",
                _json_value(root / "qa" / "security" / "report.json", "status", "missing"),
                "Click Security QA",
            )
        )
        checks.append(
            SetupCheck(
                "Dashboard",
                "PASS" if (root / "dashboard" / "index.html").exists() else "TODO",
                str(root / "dashboard" / "index.html"),
                "Click Build Dashboard",
            )
        )
        checks.append(
            SetupCheck(
                "First Run",
                "PASS" if recent_activities(root, limit=1) else "TODO",
                "orchestrator activity exists" if recent_activities(root, limit=1) else "no UI action yet",
                "Click Validate Config, then Run Cycle",
            )
        )
    except (ConfigError, ValueError) as exc:
        checks.append(SetupCheck("Config", "FAIL", str(exc), "Fix config file"))
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
) -> str:
    activities = activities or []
    audit_events = audit_events or []
    health = health or HealthSummary("MISSING", "", "MISSING", "", "MISSING", "", "MISSING", "")
    setup_checks = setup_checks or []
    reports = reports or []
    action_buttons = "".join(
        f'<button type="button" data-action="{escape(action)}" {"disabled" if status.action_running else ""}>{escape(_action_label(action))}</button>'
        for action in ACTIONS
    )
    activity_html = _activity_html(activities)
    audit_html = _audit_html(audit_events)
    health_html = _health_html(health)
    setup_html = _setup_html(setup_checks)
    reports_html = _reports_html(reports)
    safety_class = "danger" if status.live_enabled or status.kill_switch_active else "ok"
    live_text = "LIVE ENABLED" if status.live_enabled else "Live Disabled"
    kill_text = "ACTIVE" if status.kill_switch_active else "Clear"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Bot Orchestrator</title>
  <style>
    :root {{
      --page: #f5f7fb;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #64748b;
      --line: #d9e2ec;
      --good: #0f766e;
      --bad: #b91c1c;
      --warn: #b45309;
      --focus: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; background: var(--page); color: var(--ink); }}
    header {{ background: var(--panel); border-bottom: 1px solid var(--line); padding: 18px 22px; }}
    h1 {{ margin: 0; font-size: 22px; letter-spacing: 0; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .panel h2 {{ margin: 0 0 10px; font-size: 15px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 8px; }}
    .metric strong {{ display: block; font-size: 18px; overflow-wrap: anywhere; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .ok {{ background: #e6f4f1; color: var(--good); }}
    .danger {{ background: #fde8e8; color: var(--bad); }}
    .warn {{ background: #fff4e5; color: var(--warn); }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    button {{ border: 1px solid #b9c6d3; border-radius: 6px; background: #ffffff; padding: 9px 11px; cursor: pointer; font-weight: 700; }}
    button:hover {{ border-color: var(--focus); color: var(--focus); }}
    pre {{ margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; line-height: 1.45; }}
    .activity {{ border-top: 1px solid var(--line); padding-top: 10px; margin-top: 10px; }}
    .activity:first-child {{ border-top: 0; margin-top: 0; padding-top: 0; }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }}
    select, input {{ border: 1px solid var(--line); border-radius: 6px; padding: 8px; background: #fff; }}
    .small {{ color: var(--muted); font-size: 12px; }}
  </style>
</head>
<body>
  <header><h1>Trading Bot Orchestrator</h1></header>
  <main>
    <section class="grid">
      {_metric("Mode", status.mode)}
      {_metric("Safety", f'<span class="badge {safety_class}">{escape(live_text)}</span>')}
      {_metric("Kill Switch", f'<span class="badge {"danger" if status.kill_switch_active else "ok"}">{escape(kill_text)}</span>')}
      {_metric("Go/No-Go", status.go_no_go_decision)}
      {_metric("Security QA", status.security_status)}
      {_metric("Production Smoke", status.production_smoke_status)}
      {_metric("Action Lock", status.running_action if status.action_running else "Idle")}
    </section>
    <section class="panel">
      <h2>Bot Health</h2>
      <div class="grid">{health_html}</div>
    </section>
    <section class="panel">
      <h2>Quick Setup</h2>
      <div>{setup_html}</div>
      <p class="small">Recommended first run: Validate Config, Security QA, Build Dashboard, then Run Cycle.</p>
    </section>
    <section class="panel">
      <h2>Report Browser</h2>
      <div>{reports_html}</div>
      <p class="small">Reports are read-only summaries from local paper/research files.</p>
    </section>
    <section class="panel">
      <h2>Safe Actions</h2>
      <label class="small" for="limit">Candle limit</label>
      <input id="limit" type="number" min="1" max="1000" value="10" style="width:100px; padding:8px; margin:0 0 10px 8px; border:1px solid var(--line); border-radius:6px;">
      <div class="actions">{action_buttons}</div>
      <p class="small">All actions run CLI commands in paper/research mode. No live order action is exposed here.</p>
    </section>
    <section class="panel">
      <h2>Paths</h2>
      <p>Data root: <strong>{escape(status.data_root)}</strong></p>
      <p>Static dashboard: <strong>{escape(status.dashboard_path)}</strong></p>
    </section>
    <section class="panel">
      <h2>Activity</h2>
      <div id="activity">{activity_html}</div>
    </section>
    <section class="panel">
      <h2>Audit Timeline</h2>
      <div class="filters">
        <select id="audit-level">
          <option value="">All Levels</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>
        <input id="audit-symbol" placeholder="Symbol">
        <input id="audit-timeframe" placeholder="Timeframe">
        <button type="button" id="audit-refresh">Refresh</button>
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
        button.textContent = 'Running...';
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
                self._html_response(build_orchestrator_page(status, activities, audit_events, health, setup, reports))
            except (ConfigError, ValueError, OSError) as exc:
                self._json_response({"error": str(exc)}, status=500)

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            try:
                parsed = urlparse(self.path)
                if parsed.path != "/api/actions":
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


def _metric(label: str, value: object) -> str:
    return (
        '<div class="panel metric">'
        f"<span>{escape(str(label))}</span>"
        f"<strong>{value if str(value).startswith('<') else escape(str(value))}</strong>"
        "</div>"
    )


def _activity_html(activities: list[OrchestratorActivity]) -> str:
    if not activities:
        return '<p class="small">No orchestrator activity yet.</p>'
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
        return '<p class="small">No audit events yet.</p>'
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
            _health_card("Readiness", health.readiness_status, health.readiness_reason),
            _health_card("Safety", health.safety_status, health.safety_reason),
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
        return '<p class="small">Setup checks are not available.</p>'
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
        "<table style=\"width:100%;border-collapse:collapse;\">"
        "<thead><tr><th>Check</th><th>Status</th><th>Reason</th><th>Next</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _reports_html(reports: list[ReportItem]) -> str:
    if not reports:
        return '<p class="small">No reports found yet. Run Backtest, Walk-Forward, Paper, or Daily Journal actions first.</p>'
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
        "<table style=\"width:100%;border-collapse:collapse;\">"
        "<thead><tr><th>Type</th><th>Name</th><th>Status</th><th>Summary</th><th>Path</th><th>Updated</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
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
    return action.replace("_", " ").title()


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
