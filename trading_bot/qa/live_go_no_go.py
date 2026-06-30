from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig


@dataclass(frozen=True)
class GoNoGoItem:
    name: str
    status: str
    reason: str


@dataclass(frozen=True)
class LiveGoNoGoReport:
    decision: str
    items: list[GoNoGoItem]
    generated_at_utc: str
    summary: str


def evaluate_live_go_no_go(config: BotConfig, owner_approved: bool = False) -> LiveGoNoGoReport:
    root = Path(config.data_root)
    items = [
        _config_item(config),
        _report_item(root, "qa/security/report.json", {"PASSED"}, "security_qa"),
        _report_item(root, "qa/risk_guard_drill/report.json", {"PASSED"}, "risk_guard_drill"),
        _report_item(root, "qa/vps_readiness/report.json", {"PASSED"}, "vps_readiness"),
        _report_item(root, "qa/incident_drill/report.json", {"PASSED"}, "incident_drill"),
        _paper_stability_item(root),
        _data_quality_item(root),
        _readiness_item(root),
        GoNoGoItem(
            "owner_approval",
            "PASS" if owner_approved else "FAIL",
            "owner approval recorded" if owner_approved else "owner approval is not recorded",
        ),
    ]
    failed = [item for item in items if item.status != "PASS"]
    decision = "GO_FOR_OWNER_REVIEW" if not failed else "NO_GO"
    return LiveGoNoGoReport(
        decision=decision,
        items=items,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        summary="all checklist items passed" if not failed else f"{len(failed)} checklist item(s) blocked",
    )


def save_live_go_no_go_report(report: LiveGoNoGoReport, root: str | Path) -> Path:
    path = Path(root) / "qa" / "live_go_no_go" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config_item(config: BotConfig) -> GoNoGoItem:
    if config.live_enabled:
        return GoNoGoItem("config_live_disabled", "FAIL", "live_enabled must remain false")
    if config.market_type != "crypto_spot":
        return GoNoGoItem("config_live_disabled", "FAIL", "v1 only allows crypto_spot")
    if config.max_open_positions > 1:
        return GoNoGoItem("config_live_disabled", "FAIL", "max_open_positions must be <= 1")
    return GoNoGoItem("config_live_disabled", "PASS", "config is conservative and live is disabled")


def _report_item(root: Path, relative_path: str, pass_values: set[str], name: str) -> GoNoGoItem:
    payload = _read_json(root / relative_path)
    if payload is None:
        return GoNoGoItem(name, "FAIL", f"missing report: {relative_path}")
    status = str(payload.get("status", ""))
    if status in pass_values:
        return GoNoGoItem(name, "PASS", f"report status={status}")
    return GoNoGoItem(name, "FAIL", f"report status={status or 'unknown'}")


def _paper_stability_item(root: Path) -> GoNoGoItem:
    reports = list((root / "qa" / "paper_stability").rglob("report.json"))
    if not reports:
        return GoNoGoItem("paper_stability", "FAIL", "missing paper stability report")
    passed = []
    blocked = []
    for path in reports:
        payload = _read_json(path) or {}
        if payload.get("status") == "PAPER_STABLE":
            passed.append(path)
        else:
            blocked.append(path)
    if passed and not blocked:
        return GoNoGoItem("paper_stability", "PASS", f"{len(passed)} paper stability report(s) passed")
    return GoNoGoItem("paper_stability", "FAIL", f"{len(blocked) or len(reports)} paper stability report(s) blocked")


def _data_quality_item(root: Path) -> GoNoGoItem:
    reports = list((root / "qa" / "data_quality_gate").rglob("report.json"))
    if not reports:
        return GoNoGoItem("data_quality_gate", "FAIL", "missing data quality gate report")
    blocked = []
    for path in reports:
        payload = _read_json(path) or {}
        if payload.get("status") == "BLOCKED":
            blocked.append(path)
    if blocked:
        return GoNoGoItem("data_quality_gate", "FAIL", f"{len(blocked)} data quality report(s) blocked")
    return GoNoGoItem("data_quality_gate", "PASS", f"{len(reports)} data quality report(s) passed or warned")


def _readiness_item(root: Path) -> GoNoGoItem:
    payload = _read_json(root / "readiness" / "live_readiness.json")
    if payload is None:
        return GoNoGoItem("live_readiness", "FAIL", "missing live readiness report")
    status = str(payload.get("status", ""))
    if status == "READY_FOR_MANUAL_REVIEW":
        return GoNoGoItem("live_readiness", "PASS", "live readiness is ready for manual review")
    return GoNoGoItem("live_readiness", "FAIL", f"live readiness status={status or 'unknown'}")


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
