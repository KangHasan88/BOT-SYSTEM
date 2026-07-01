from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig


@dataclass(frozen=True)
class EvidenceItem:
    name: str
    status: str
    reason: str
    next_action: str


@dataclass(frozen=True)
class LiveEvidenceReport:
    status: str
    completion_pct: float
    generated_at_utc: str
    items: list[EvidenceItem]
    blockers: list[str]
    summary: str


def evaluate_live_evidence(config: BotConfig, min_paper_trades: int = 20) -> LiveEvidenceReport:
    root = Path(config.data_root)
    items = [
        _config_item(config),
        _security_item(root),
        _data_quality_item(root),
        _backtest_item(root),
        _walk_forward_item(root),
        _paper_trade_item(root, min_paper_trades),
        _paper_stability_item(root),
        _risk_guard_item(root),
        _incident_item(root),
        _testnet_demo_item(root),
        _learning_item(root),
        _live_readiness_item(root),
        _live_go_no_go_item(root),
    ]
    passed = [item for item in items if item.status == "PASS"]
    blockers = [f"{item.name}: {item.reason}" for item in items if item.status == "FAIL"]
    completion_pct = round((len(passed) / len(items)) * 100, 2) if items else 0.0
    status = "COMPLETE_FOR_OWNER_REVIEW" if not blockers else "INCOMPLETE"
    summary = (
        "all evidence complete for owner review; real live still requires manual approval"
        if not blockers
        else f"{len(blockers)} evidence item(s) incomplete"
    )
    return LiveEvidenceReport(
        status=status,
        completion_pct=completion_pct,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        items=items,
        blockers=blockers,
        summary=summary,
    )


def save_live_evidence_report(report: LiveEvidenceReport, root: str | Path) -> Path:
    path = Path(root) / "readiness" / "live_evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path


def _config_item(config: BotConfig) -> EvidenceItem:
    if config.live_enabled:
        return EvidenceItem("config_live_disabled", "FAIL", "live_enabled is true", "Set live_enabled=false")
    if config.max_open_positions > 1:
        return EvidenceItem("config_conservative", "FAIL", "max_open_positions > 1", "Keep max_open_positions <= 1")
    return EvidenceItem("config_conservative", "PASS", "live disabled and conservative config active", "")


def _security_item(root: Path) -> EvidenceItem:
    payload = _read_json(root / "qa" / "security" / "report.json")
    return _report_item("security_qa", payload, {"PASSED"}, "Klik Security QA")


def _data_quality_item(root: Path) -> EvidenceItem:
    reports = _json_reports(root / "qa" / "data_quality_gate")
    if not reports:
        return EvidenceItem("data_quality_gate", "FAIL", "missing data quality reports", "Jalankan Demo Data atau Jalankan Siklus")
    blocked = [report for report in reports if report.get("status") == "BLOCKED"]
    if blocked:
        return EvidenceItem("data_quality_gate", "FAIL", f"{len(blocked)} blocked report(s)", "Perbaiki/backfill data candle")
    return EvidenceItem("data_quality_gate", "PASS", f"{len(reports)} data quality report(s) available", "")


def _backtest_item(root: Path) -> EvidenceItem:
    reports = _json_reports(root / "backtests")
    if not reports:
        return EvidenceItem("backtest", "FAIL", "missing backtest reports", "Jalankan Backtest/Run Cycle")
    passed = [report for report in reports if report.get("recommendation") in {"PAPER_CANDIDATE", "PASS"}]
    status = "PASS" if passed else "FAIL"
    return EvidenceItem("backtest", status, f"{len(passed)}/{len(reports)} candidate report(s)", "" if passed else "Review strategy/filter")


def _walk_forward_item(root: Path) -> EvidenceItem:
    reports = _json_reports(root / "validation" / "walk_forward")
    if not reports:
        return EvidenceItem("walk_forward", "FAIL", "missing walk-forward reports", "Jalankan Walk-Forward/Run Cycle")
    passed = [report for report in reports if report.get("recommendation") in {"PAPER_CANDIDATE", "PASS"}]
    status = "PASS" if passed else "FAIL"
    return EvidenceItem("walk_forward", status, f"{len(passed)}/{len(reports)} candidate report(s)", "" if passed else "Review out-of-sample result")


def _paper_trade_item(root: Path, min_paper_trades: int) -> EvidenceItem:
    trade_count = _count_csv_rows(root / "paper", "trades.csv")
    if trade_count < min_paper_trades:
        return EvidenceItem(
            "paper_trade_count",
            "FAIL",
            f"paper trades {trade_count} below minimum {min_paper_trades}",
            "Lanjut paper/demo campaign",
        )
    return EvidenceItem("paper_trade_count", "PASS", f"paper trades={trade_count}", "")


def _paper_stability_item(root: Path) -> EvidenceItem:
    reports = _json_reports(root / "qa" / "paper_stability")
    if not reports:
        return EvidenceItem("paper_stability", "FAIL", "missing paper stability report", "Jalankan Paper Stability Report")
    passed = [report for report in reports if report.get("status") == "PAPER_STABLE"]
    return EvidenceItem(
        "paper_stability",
        "PASS" if passed else "FAIL",
        f"{len(passed)}/{len(reports)} stable report(s)",
        "" if passed else "Kumpulkan 14-28 hari evidence",
    )


def _risk_guard_item(root: Path) -> EvidenceItem:
    payload = _read_json(root / "qa" / "risk_guard_drill" / "report.json")
    return _report_item("risk_guard_drill", payload, {"PASSED"}, "Klik Risk Guard Drill")


def _incident_item(root: Path) -> EvidenceItem:
    payload = _read_json(root / "qa" / "incident_drill" / "report.json")
    return _report_item("incident_drill", payload, {"PASSED"}, "Klik Incident Drill")


def _testnet_demo_item(root: Path) -> EvidenceItem:
    payload = _read_json(root / "execution" / "testnet_demo" / "report.json")
    return _report_item("testnet_demo", payload, {"PASSED"}, "Klik Testnet Demo")


def _learning_item(root: Path) -> EvidenceItem:
    payload = _read_json(root / "reports" / "learning" / "database_snapshot.json")
    if payload is None:
        return EvidenceItem("learning_snapshot", "FAIL", "missing database learning snapshot", "Klik Learning DB")
    rows = payload.get("rows", [])
    if isinstance(rows, list) and rows:
        return EvidenceItem("learning_snapshot", "PASS", f"learning rows={len(rows)}", "")
    return EvidenceItem("learning_snapshot", "FAIL", "learning snapshot has no rows", "Klik Import DB lalu Learning DB")


def _live_readiness_item(root: Path) -> EvidenceItem:
    payload = _read_json(root / "readiness" / "live_readiness.json")
    if payload is None:
        return EvidenceItem("live_readiness", "FAIL", "missing live readiness report", "Jalankan Live Readiness")
    status = str(payload.get("status", ""))
    if status == "READY_FOR_MANUAL_REVIEW":
        return EvidenceItem("live_readiness", "PASS", status, "")
    return EvidenceItem("live_readiness", "FAIL", f"status={status or 'unknown'}", "Jalankan ulang setelah evidence lengkap")


def _live_go_no_go_item(root: Path) -> EvidenceItem:
    payload = _read_json(root / "qa" / "live_go_no_go" / "report.json")
    if payload is None:
        return EvidenceItem("live_go_no_go", "FAIL", "missing go/no-go report", "Klik Live Go/No-Go")
    decision = str(payload.get("decision", ""))
    if decision == "GO_FOR_OWNER_REVIEW":
        return EvidenceItem("live_go_no_go", "PASS", decision, "")
    return EvidenceItem("live_go_no_go", "FAIL", f"decision={decision or 'unknown'}", "Review blockers sebelum owner approval")


def _report_item(name: str, payload: dict | None, pass_values: set[str], next_action: str) -> EvidenceItem:
    if payload is None:
        return EvidenceItem(name, "FAIL", "missing report", next_action)
    status = str(payload.get("status", payload.get("decision", "")))
    if status in pass_values:
        return EvidenceItem(name, "PASS", f"status={status}", "")
    return EvidenceItem(name, "FAIL", f"status={status or 'unknown'}", next_action)


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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _count_csv_rows(root: Path, filename: str) -> int:
    if not root.exists():
        return 0
    count = 0
    for path in root.rglob(filename):
        if path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            count += sum(1 for _ in csv.DictReader(handle))
    return count
