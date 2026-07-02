from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig


ALLOWED_EXPERIMENT_STATUS = ["IDEA", "BACKTEST", "PAPER", "REJECTED", "PAUSED"]


@dataclass(frozen=True)
class StrategyExperiment:
    strategy_id: str
    version: str
    hypothesis: str
    source: str
    status: str
    backtest_score: float
    paper_score: float
    risk_score: float
    evidence_score: float
    created_at_utc: str


@dataclass(frozen=True)
class ExperimentScoreRow:
    strategy_id: str
    version: str
    status: str
    total_score: float
    recommendation: str
    hypothesis: str
    source: str


@dataclass(frozen=True)
class ExperimentScoreboardReport:
    status: str
    generated_at_utc: str
    registry_path: str
    experiment_count: int
    top_strategy: str
    summary: str
    guardrail: str
    rows: list[ExperimentScoreRow] = field(default_factory=list)


def add_strategy_experiment(
    config: BotConfig,
    strategy_id: str,
    version: str,
    hypothesis: str,
    source: str = "manual",
    status: str = "IDEA",
    backtest_score: float = 0.0,
    paper_score: float = 0.0,
    risk_score: float = 0.0,
    evidence_score: float = 0.0,
    registry_path: str | Path | None = None,
) -> StrategyExperiment:
    normalized_status = status.strip().upper()
    if normalized_status not in ALLOWED_EXPERIMENT_STATUS:
        raise ValueError(f"status must be one of: {', '.join(ALLOWED_EXPERIMENT_STATUS)}")
    experiment = StrategyExperiment(
        strategy_id=_normalize_id(strategy_id),
        version=version.strip() or "v0",
        hypothesis=hypothesis.strip(),
        source=source.strip() or "manual",
        status=normalized_status,
        backtest_score=float(backtest_score),
        paper_score=float(paper_score),
        risk_score=float(risk_score),
        evidence_score=float(evidence_score),
        created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    if not experiment.strategy_id:
        raise ValueError("strategy_id is required")
    if not experiment.hypothesis:
        raise ValueError("hypothesis is required")
    path = _registry_path(config, registry_path)
    payload = _read_registry(path)
    payload["experiments"].append(asdict(experiment))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return experiment


def build_experiment_scoreboard(
    config: BotConfig,
    registry_path: str | Path | None = None,
    limit: int = 12,
) -> ExperimentScoreboardReport:
    path = _registry_path(config, registry_path)
    experiments = _load_experiments(path)
    rows = sorted((_score_row(item) for item in experiments), key=lambda row: row.total_score, reverse=True)
    top_strategy = f"{rows[0].strategy_id} {rows[0].version}" if rows else "-"
    return ExperimentScoreboardReport(
        status="EXPERIMENT_SCOREBOARD_ACTIVE" if rows else "EXPERIMENT_SCOREBOARD_EMPTY",
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        registry_path=str(path),
        experiment_count=len(rows),
        top_strategy=top_strategy,
        summary=_summary(len(rows), top_strategy),
        guardrail="Experiment registry is review-only. A high score can promote to paper review, never directly to live.",
        rows=rows[:limit],
    )


def save_experiment_scoreboard(report: ExperimentScoreboardReport, root: str | Path) -> Path:
    path = Path(root) / "reports" / "learning" / "experiment_scoreboard.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _registry_path(config: BotConfig, registry_path: str | Path | None) -> Path:
    if registry_path is not None:
        return Path(registry_path)
    return Path(config.data_root) / "reports" / "learning" / "strategy_experiments.json"


def _read_registry(path: Path) -> dict:
    if not path.exists():
        return {"experiments": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"experiments": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("experiments", []), list):
        return {"experiments": []}
    return {"experiments": payload.get("experiments", [])}


def _load_experiments(path: Path) -> list[StrategyExperiment]:
    rows: list[StrategyExperiment] = []
    for row in _read_registry(path)["experiments"]:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "IDEA")).strip().upper()
        if status not in ALLOWED_EXPERIMENT_STATUS:
            continue
        rows.append(
            StrategyExperiment(
                strategy_id=str(row.get("strategy_id", "")),
                version=str(row.get("version", "v0")),
                hypothesis=str(row.get("hypothesis", "")),
                source=str(row.get("source", "manual")),
                status=status,
                backtest_score=float(row.get("backtest_score", 0) or 0),
                paper_score=float(row.get("paper_score", 0) or 0),
                risk_score=float(row.get("risk_score", 0) or 0),
                evidence_score=float(row.get("evidence_score", 0) or 0),
                created_at_utc=str(row.get("created_at_utc", "")),
            )
        )
    return [row for row in rows if row.strategy_id and row.hypothesis]


def _score_row(experiment: StrategyExperiment) -> ExperimentScoreRow:
    total = experiment.backtest_score + experiment.paper_score + experiment.evidence_score - experiment.risk_score
    recommendation = "NEEDS_EVIDENCE"
    if experiment.status == "REJECTED" or total < 0:
        recommendation = "REJECTED"
    elif experiment.status == "PAPER" and total >= 60:
        recommendation = "PAPER_CANDIDATE"
    elif total >= 30:
        recommendation = "WATCHLIST"
    return ExperimentScoreRow(
        strategy_id=experiment.strategy_id,
        version=experiment.version,
        status=experiment.status,
        total_score=round(total, 2),
        recommendation=recommendation,
        hypothesis=experiment.hypothesis,
        source=experiment.source,
    )


def _summary(count: int, top_strategy: str) -> str:
    if count == 0:
        return "belum ada eksperimen strategi; tambah ide dari review pattern/human feedback"
    return f"{count} eksperimen tercatat, top strategy={top_strategy}"


def _normalize_id(strategy_id: str) -> str:
    return strategy_id.strip().lower().replace(" ", "_").replace("-", "_")
