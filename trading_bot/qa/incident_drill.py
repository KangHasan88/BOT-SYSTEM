from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.alerts import AlertOutbox, build_error_alert, build_stop_alert
from trading_bot.observability import JsonlAuditLogger, read_audit_events


@dataclass(frozen=True)
class IncidentScenarioResult:
    name: str
    status: str
    audit_event: str
    alert_kind: str
    safe_response: str
    reason: str


@dataclass(frozen=True)
class IncidentDrillReport:
    status: str
    scenarios: list[IncidentScenarioResult]
    generated_at_utc: str


def run_incident_drill(root: str | Path, symbol: str = "BTC/USDT") -> IncidentDrillReport:
    root_path = Path(root)
    logger = JsonlAuditLogger(root_path)
    outbox = AlertOutbox(root_path)
    scenarios = [
        _exchange_api_down(root_path, logger, outbox),
        _network_down(root_path, logger, outbox),
        _bot_crash(root_path, logger, outbox, symbol),
    ]
    return IncidentDrillReport(
        status="PASSED" if all(scenario.status == "PASSED" for scenario in scenarios) else "FAILED",
        scenarios=scenarios,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def save_incident_drill_report(report: IncidentDrillReport, root: str | Path) -> Path:
    path = Path(root) / "qa" / "incident_drill" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _exchange_api_down(root: Path, logger: JsonlAuditLogger, outbox: AlertOutbox) -> IncidentScenarioResult:
    event = logger.write(
        "incident_exchange_api_down",
        "exchange API unavailable during drill",
        level="ERROR",
        safe_response="skip sync and block new entries",
    )
    alert = build_error_alert("exchange_api", "exchange API unavailable during drill")
    outbox.write(alert)
    return _result(
        root,
        "exchange_api_down",
        event.event,
        alert.kind,
        "skip sync and block new entries",
    )


def _network_down(root: Path, logger: JsonlAuditLogger, outbox: AlertOutbox) -> IncidentScenarioResult:
    event = logger.write(
        "incident_network_down",
        "network unavailable during drill",
        level="ERROR",
        safe_response="do not trade on stale data",
    )
    alert = build_error_alert("network", "network unavailable during drill")
    outbox.write(alert)
    return _result(root, "network_down", event.event, alert.kind, "do not trade on stale data")


def _bot_crash(
    root: Path,
    logger: JsonlAuditLogger,
    outbox: AlertOutbox,
    symbol: str,
) -> IncidentScenarioResult:
    event = logger.write(
        "incident_bot_crash",
        "bot crash simulated during drill",
        level="CRITICAL",
        safe_response="require operator review before restart",
    )
    alert = build_stop_alert(symbol, "bot crash simulated during drill")
    outbox.write(alert)
    return _result(
        root,
        "bot_crash",
        event.event,
        alert.kind,
        "require operator review before restart",
    )


def _result(
    root: Path,
    name: str,
    expected_event: str,
    expected_alert_kind: str,
    safe_response: str,
) -> IncidentScenarioResult:
    events = read_audit_events(root)
    alert_files = list((root / "alerts" / "outbox").glob(f"*-{expected_alert_kind}.json"))
    passed = any(event.event == expected_event for event in events) and bool(alert_files)
    return IncidentScenarioResult(
        name=name,
        status="PASSED" if passed else "FAILED",
        audit_event=expected_event,
        alert_kind=expected_alert_kind,
        safe_response=safe_response,
        reason="audit and alert written" if passed else "missing audit event or alert",
    )
