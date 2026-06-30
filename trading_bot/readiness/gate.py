from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from trading_bot.config import BotConfig
from trading_bot.security import load_env_file, scan_for_secrets, validate_env_security


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: str
    reason: str


@dataclass(frozen=True)
class ReadinessReport:
    status: str
    checks: list[ReadinessCheck]
    summary: str


def evaluate_live_readiness(
    config: BotConfig,
    env_file: str | Path = ".env.example",
    scan_root: str | Path = ".",
    min_paper_trades: int = 20,
) -> ReadinessReport:
    checks = [
        _config_check(config),
        _security_check(env_file, scan_root),
        _backtest_check(config.data_root),
        _walk_forward_check(config.data_root),
        _paper_trading_check(config.data_root, min_paper_trades),
        _kill_switch_check(),
        _manual_approval_check(config),
    ]
    failed = [check for check in checks if check.status != "PASS"]
    if failed:
        return ReadinessReport(
            status="BLOCKED",
            checks=checks,
            summary=f"{len(failed)} live readiness checks still blocked",
        )
    return ReadinessReport(
        status="READY_FOR_MANUAL_REVIEW",
        checks=checks,
        summary="all automated checks passed; manual owner approval is still required before live",
    )


def save_live_readiness_report(report: ReadinessReport, root: str | Path) -> Path:
    path = Path(root) / "readiness" / "live_readiness.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path


def _config_check(config: BotConfig) -> ReadinessCheck:
    if config.live_enabled:
        return ReadinessCheck("config_live_disabled", "FAIL", "live_enabled must stay false during readiness review")
    if config.market_type != "crypto_spot":
        return ReadinessCheck("config_live_disabled", "FAIL", "only crypto_spot is allowed in v1")
    if config.max_open_positions > 1:
        return ReadinessCheck("config_live_disabled", "FAIL", "max_open_positions must be <= 1")
    return ReadinessCheck("config_live_disabled", "PASS", "live disabled and conservative market config active")


def _security_check(env_file: str | Path, scan_root: str | Path) -> ReadinessCheck:
    try:
        env = load_env_file(env_file)
    except FileNotFoundError as exc:
        return ReadinessCheck("security_env_and_secret_scan", "FAIL", str(exc))
    report = validate_env_security(env)
    findings = scan_for_secrets(scan_root)
    if not report.ok:
        return ReadinessCheck("security_env_and_secret_scan", "FAIL", "; ".join(report.errors))
    if findings:
        first = findings[0]
        return ReadinessCheck(
            "security_env_and_secret_scan",
            "FAIL",
            f"secret-like value found at {first.path}:{first.line_number}",
        )
    return ReadinessCheck("security_env_and_secret_scan", "PASS", "env guard and secret scan passed")


def _backtest_check(root: str | Path) -> ReadinessCheck:
    reports = _json_files(Path(root) / "backtests")
    if not reports:
        return ReadinessCheck("backtest_gate", "FAIL", "no backtest metrics reports found")
    bad = [report for report in reports if report.get("recommendation") != "PAPER_CANDIDATE"]
    if bad:
        return ReadinessCheck("backtest_gate", "FAIL", "one or more backtest reports are not PAPER_CANDIDATE")
    return ReadinessCheck("backtest_gate", "PASS", f"{len(reports)} backtest report(s) passed")


def _walk_forward_check(root: str | Path) -> ReadinessCheck:
    reports = _json_files(Path(root) / "validation" / "walk_forward")
    if not reports:
        return ReadinessCheck("walk_forward_gate", "FAIL", "no walk-forward validation reports found")
    bad = [report for report in reports if report.get("recommendation") != "PAPER_CANDIDATE"]
    if bad:
        return ReadinessCheck("walk_forward_gate", "FAIL", "one or more walk-forward reports are not PAPER_CANDIDATE")
    return ReadinessCheck("walk_forward_gate", "PASS", f"{len(reports)} walk-forward report(s) passed")


def _paper_trading_check(root: str | Path, min_paper_trades: int) -> ReadinessCheck:
    trade_count = 0
    for path in (Path(root) / "paper").rglob("trades.csv"):
        if path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            trade_count += sum(1 for _ in csv.DictReader(handle))
    if trade_count < min_paper_trades:
        return ReadinessCheck(
            "paper_trading_evidence",
            "FAIL",
            f"paper trades {trade_count} below minimum {min_paper_trades}",
        )
    return ReadinessCheck("paper_trading_evidence", "PASS", f"paper trades={trade_count}")


def _kill_switch_check() -> ReadinessCheck:
    return ReadinessCheck(
        "kill_switch_drill",
        "FAIL",
        "manual kill switch drill evidence is not recorded yet",
    )


def _manual_approval_check(config: BotConfig) -> ReadinessCheck:
    if config.approved_live:
        return ReadinessCheck("manual_owner_approval", "PASS", "manual approval flag is true")
    return ReadinessCheck("manual_owner_approval", "FAIL", "manual owner approval is not recorded")


def _json_files(root: Path) -> list[dict]:
    if not root.exists():
        return []
    reports: list[dict] = []
    for path in root.rglob("*.json"):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return reports
