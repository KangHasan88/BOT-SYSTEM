from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig


@dataclass(frozen=True)
class LearningDashboardTrend:
    symbol: str
    timeframe: str
    observation: str
    outcome_grade: str
    trade_count: int
    win_rate_pct: float
    total_net_pnl: float
    pattern_count: int
    volume_spike: bool
    evidence_score: float
    status: str
    next_action: str


@dataclass(frozen=True)
class LearningDashboardReport:
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
    trends: list[LearningDashboardTrend] = field(default_factory=list)


def build_learning_dashboard_report(config: BotConfig) -> LearningDashboardReport:
    root = Path(config.data_root)
    learning = _read_json(root / "reports" / "learning" / "database_snapshot.json") or {}
    memory = _read_json(root / "reports" / "learning" / "pattern_memory.json") or {}
    evidence = _read_json(root / "readiness" / "live_evidence.json") or {}
    campaign = _read_json(root / "qa" / "paper_campaign" / "report.json") or {}

    learning_rows = _rows_by_pair(learning.get("rows", []))
    memory_rows = memory.get("rows", []) if isinstance(memory.get("rows", []), list) else []
    trends = [
        _trend_row(
            row,
            learning_rows.get((str(row.get("symbol", "")), str(row.get("timeframe", ""))), {}),
            float(evidence.get("completion_pct", 0) or 0),
            float(campaign.get("completion_pct", 0) or 0),
        )
        for row in memory_rows
        if isinstance(row, dict)
    ]

    if not trends:
        trends = [
            _empty_trend(row, float(evidence.get("completion_pct", 0) or 0), float(campaign.get("completion_pct", 0) or 0))
            for row in learning_rows.values()
        ]

    average_score = sum(row.evidence_score for row in trends) / len(trends) if trends else 0.0
    promising_count = sum(1 for row in trends if row.outcome_grade == "PROMISING")
    weak_count = sum(1 for row in trends if row.outcome_grade in {"WEAK", "MIXED"})
    volume_spike_count = sum(1 for row in trends if row.volume_spike)
    status = "LEARNING_DASHBOARD_ACTIVE" if trends else "LEARNING_DASHBOARD_NEEDS_DATA"
    return LearningDashboardReport(
        status=status,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        trend_count=len(trends),
        promising_count=promising_count,
        weak_count=weak_count,
        volume_spike_count=volume_spike_count,
        average_evidence_score=average_score,
        live_evidence_completion_pct=float(evidence.get("completion_pct", 0) or 0),
        paper_campaign_completion_pct=float(campaign.get("completion_pct", 0) or 0),
        summary=_summary(status, len(trends), promising_count, weak_count),
        guardrail="Learning dashboard is read-only research and must never trigger live execution.",
        trends=trends,
    )


def save_learning_dashboard_report(report: LearningDashboardReport, root: str | Path) -> Path:
    path = Path(root) / "reports" / "learning" / "learning_dashboard.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _trend_row(
    memory: dict,
    learning: dict,
    live_completion_pct: float,
    paper_completion_pct: float,
) -> LearningDashboardTrend:
    pattern_count = _pattern_total(learning.get("pattern_counts", {}))
    latest_volume_ratio = learning.get("latest_volume_ratio")
    volume_spike = bool(latest_volume_ratio is not None and float(latest_volume_ratio) >= 1.8)
    trade_count = int(memory.get("trade_count", 0) or 0)
    outcome_grade = str(memory.get("outcome_grade", "NO_TRADES"))
    score = _evidence_score(trade_count, outcome_grade, live_completion_pct, paper_completion_pct)
    return LearningDashboardTrend(
        symbol=str(memory.get("symbol", "")),
        timeframe=str(memory.get("timeframe", "")),
        observation=str(memory.get("observation", learning.get("observation", "NO_DATA"))),
        outcome_grade=outcome_grade,
        trade_count=trade_count,
        win_rate_pct=float(memory.get("win_rate_pct", 0) or 0),
        total_net_pnl=float(memory.get("total_net_pnl", 0) or 0),
        pattern_count=pattern_count,
        volume_spike=volume_spike,
        evidence_score=score,
        status=_trend_status(outcome_grade, trade_count, score),
        next_action=str(memory.get("next_action", "Lanjutkan paper review")),
    )


def _empty_trend(learning: dict, live_completion_pct: float, paper_completion_pct: float) -> LearningDashboardTrend:
    pattern_count = _pattern_total(learning.get("pattern_counts", {}))
    latest_volume_ratio = learning.get("latest_volume_ratio")
    volume_spike = bool(latest_volume_ratio is not None and float(latest_volume_ratio) >= 1.8)
    score = _evidence_score(0, "NO_TRADES", live_completion_pct, paper_completion_pct)
    return LearningDashboardTrend(
        symbol=str(learning.get("symbol", "")),
        timeframe=str(learning.get("timeframe", "")),
        observation=str(learning.get("observation", "NO_DATA")),
        outcome_grade="NO_TRADES",
        trade_count=0,
        win_rate_pct=0.0,
        total_net_pnl=0.0,
        pattern_count=pattern_count,
        volume_spike=volume_spike,
        evidence_score=score,
        status="BUTUH PAPER",
        next_action="Jalankan paper campaign dan tambah label review",
    )


def _evidence_score(trade_count: int, grade: str, live_completion_pct: float, paper_completion_pct: float) -> float:
    trade_score = min(trade_count / 20, 1.0) * 40
    grade_score = {"PROMISING": 30, "MIXED": 15, "NEEDS_MORE_TRADES": 10, "WEAK": 0, "NO_TRADES": 0}.get(grade, 0)
    campaign_score = min(paper_completion_pct, 100) * 0.2
    live_score = min(live_completion_pct, 100) * 0.1
    return round(trade_score + grade_score + campaign_score + live_score, 2)


def _trend_status(grade: str, trade_count: int, score: float) -> str:
    if grade == "PROMISING" and score >= 70:
        return "REVIEW CANDIDATE"
    if grade in {"WEAK", "MIXED"}:
        return "REVIEW FILTER"
    if trade_count < 20:
        return "BUTUH PAPER"
    return "PANTAU"


def _rows_by_pair(rows: object) -> dict[tuple[str, str], dict]:
    result: dict[tuple[str, str], dict] = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            result[(str(row.get("symbol", "")), str(row.get("timeframe", "")))] = row
    return result


def _pattern_total(pattern_counts: object) -> int:
    if not isinstance(pattern_counts, dict):
        return 0
    return sum(int(value or 0) for value in pattern_counts.values())


def _summary(status: str, trend_count: int, promising_count: int, weak_count: int) -> str:
    if status != "LEARNING_DASHBOARD_ACTIVE":
        return "learning dashboard butuh Learning DB atau Pattern Memory"
    return f"{trend_count} trend terbaca, {promising_count} promising, {weak_count} perlu review filter"


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
