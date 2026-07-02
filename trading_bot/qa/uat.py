from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig


@dataclass(frozen=True)
class UatCheck:
    name: str
    status: str
    reason: str
    next_action: str


@dataclass(frozen=True)
class UatReport:
    status: str
    generated_at_utc: str
    completion_pct: float
    bug_count: int
    summary: str
    guardrail: str
    checks: list[UatCheck] = field(default_factory=list)
    bugs: list[str] = field(default_factory=list)


def build_uat_report(config: BotConfig, bug_path: str | Path | None = None) -> UatReport:
    root = Path(config.data_root)
    bugs = _load_bugs(root, bug_path)
    checks = [
        _check("local_web", Path("scripts/start-local-orchestrator.ps1").exists(), "start script tersedia", "Jalankan start-bot-web.cmd"),
        _check("watchdog", Path("scripts/watch-local-orchestrator.ps1").exists(), "watchdog tersedia", "Jalankan start-bot-watchdog.cmd jika web mati"),
        _check("demo_data", (root / "demo" / "local_demo.json").exists(), "local demo report tersedia", "Klik Local Demo"),
        _check("pnl_monitor", _count_csv_rows(root / "paper", "trades.csv") > 0, "paper trade tersedia untuk P/L", "Klik Demo Data atau Run Cycle paper"),
        _check("fundamental_lane", (root / "reports" / "fundamental" / "report.json").exists(), "fundamental lane report tersedia", "Klik Fundamental"),
        _check("experiment_scoreboard", (root / "reports" / "learning" / "experiment_scoreboard.json").exists(), "scoreboard report tersedia", "Klik Experiment Scoreboard"),
        _check("live_locked", not config.live_enabled and not config.approved_live, "real live terkunci", "Jangan aktifkan live sampai evidence lengkap"),
    ]
    passed = sum(1 for check in checks if check.status == "PASS")
    completion = round(passed / len(checks) * 100, 2) if checks else 0.0
    status = "UAT_READY_FOR_DEMO" if completion >= 85 and not bugs else "UAT_HAS_BUGS" if bugs else "UAT_INCOMPLETE"
    return UatReport(
        status=status,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        completion_pct=completion,
        bug_count=len(bugs),
        summary=f"{passed}/{len(checks)} UAT check(s) passed, open bugs={len(bugs)}",
        guardrail="UAT ready means demo/paper ready only. Real live remains gated by evidence and owner approval.",
        checks=checks,
        bugs=bugs,
    )


def save_uat_report(report: UatReport, root: str | Path) -> Path:
    path = Path(root) / "qa" / "uat" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _check(name: str, passed: bool, reason: str, next_action: str) -> UatCheck:
    return UatCheck(name=name, status="PASS" if passed else "TODO", reason=reason, next_action="" if passed else next_action)


def _load_bugs(root: Path, bug_path: str | Path | None) -> list[str]:
    path = Path(bug_path) if bug_path else root / "qa" / "uat" / "bugs.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["bugs.json invalid"]
    bugs = payload.get("bugs", []) if isinstance(payload, dict) else []
    return [str(item) for item in bugs if str(item).strip()]


def _count_csv_rows(root: Path, filename: str) -> int:
    count = 0
    for path in root.glob(f"**/{filename}"):
        try:
            rows = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        count += max(len(rows) - 1, 0)
    return count
