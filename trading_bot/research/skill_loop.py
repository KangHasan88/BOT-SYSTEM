from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig
from trading_bot.data_collector import CandleCsvStore


@dataclass(frozen=True)
class SkillLoopStep:
    name: str
    status: str
    metric: str
    finding: str
    next_action: str


@dataclass(frozen=True)
class SkillLoopReport:
    status: str
    generated_at_utc: str
    candle_rows: int
    paper_trades: int
    paper_net_pnl: float
    learning_rows: int
    evidence_completion_pct: float
    paper_campaign_status: str
    experiment_candidates: list[str]
    summary: str
    guardrail: str
    steps: list[SkillLoopStep] = field(default_factory=list)


def build_skill_loop_report(config: BotConfig) -> SkillLoopReport:
    root = Path(config.data_root)
    candle_rows = _count_candle_rows(config)
    paper_trades, paper_net_pnl = _paper_trade_metrics(root)
    learning = _read_json(root / "reports" / "learning" / "database_snapshot.json") or {}
    learning_rows = len(learning.get("rows", [])) if isinstance(learning.get("rows", []), list) else 0
    learning_notes = learning.get("notes", []) if isinstance(learning.get("notes", []), list) else []
    evidence = _read_json(root / "readiness" / "live_evidence.json") or {}
    paper_campaign = _read_json(root / "qa" / "paper_campaign" / "report.json") or {}
    evidence_completion = float(evidence.get("completion_pct", 0) or 0)
    paper_campaign_status = str(paper_campaign.get("status", "MISSING"))

    steps = [
        SkillLoopStep(
            "capture_data",
            "PASS" if candle_rows > 0 else "TODO",
            f"candles={candle_rows}",
            "market data tersedia" if candle_rows > 0 else "belum ada candle yang bisa dipelajari",
            "Klik Demo Data atau Sinkron data market",
        ),
        SkillLoopStep(
            "read_patterns",
            "PASS" if learning_rows > 0 else "TODO",
            f"learning_rows={learning_rows}",
            "; ".join(str(note) for note in learning_notes[:2]) if learning_notes else "learning snapshot belum tersedia",
            "Klik Import DB lalu Learning DB",
        ),
        SkillLoopStep(
            "review_trades",
            "PASS" if paper_trades > 0 else "TODO",
            f"paper_trades={paper_trades}, net_pnl={paper_net_pnl:.8f}",
            "paper trade sudah bisa direview" if paper_trades > 0 else "belum ada paper trade untuk review",
            "Klik Jalankan Siklus atau Evidence Campaign",
        ),
        SkillLoopStep(
            "paper_campaign",
            "PASS" if paper_campaign_status in {"PAPER_CAMPAIGN_READY", "PAPER_CAMPAIGN_COLLECTING"} else "TODO",
            paper_campaign_status,
            str(paper_campaign.get("summary", "paper campaign belum tersedia")),
            "Klik Paper Campaign",
        ),
        SkillLoopStep(
            "evidence_gate",
            "PASS" if evidence_completion > 0 else "TODO",
            f"completion={evidence_completion:.2f}%",
            str(evidence.get("summary", "live evidence belum tersedia")),
            "Klik Live Evidence",
        ),
    ]
    blockers = [step for step in steps if step.status != "PASS"]
    candidates = _experiment_candidates(learning_notes, paper_campaign, paper_net_pnl)
    status = "SKILL_LOOP_ACTIVE" if not blockers else "SKILL_LOOP_NEEDS_DATA"
    return SkillLoopReport(
        status=status,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        candle_rows=candle_rows,
        paper_trades=paper_trades,
        paper_net_pnl=paper_net_pnl,
        learning_rows=learning_rows,
        evidence_completion_pct=evidence_completion,
        paper_campaign_status=paper_campaign_status,
        experiment_candidates=candidates,
        summary="skill loop has enough evidence to keep improving" if status == "SKILL_LOOP_ACTIVE" else f"{len(blockers)} learning step(s) need more data",
        guardrail="Research only. No AI recommendation or learning output may place live orders.",
        steps=steps,
    )


def save_skill_loop_report(report: SkillLoopReport, root: str | Path) -> Path:
    path = Path(root) / "reports" / "learning" / "skill_loop.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _paper_trade_metrics(root: Path) -> tuple[int, float]:
    count = 0
    net_pnl = 0.0
    for path in (root / "paper").rglob("trades.csv") if (root / "paper").exists() else []:
        if path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                count += 1
                try:
                    net_pnl += float(row.get("net_pnl", 0) or 0)
                except ValueError:
                    continue
    return count, net_pnl


def _count_candle_rows(config: BotConfig) -> int:
    store = CandleCsvStore(config.data_root)
    total = 0
    for symbol in config.symbols:
        for timeframe in config.timeframes:
            total += len(store.load(symbol, timeframe))
    return total


def _experiment_candidates(learning_notes: list, paper_campaign: dict, paper_net_pnl: float) -> list[str]:
    candidates: list[str] = []
    for note in learning_notes[:3]:
        candidates.append(f"Review pattern note: {note}")
    blockers = paper_campaign.get("blockers", [])
    if isinstance(blockers, list):
        for blocker in blockers[:3]:
            candidates.append(f"Collect more paper evidence: {blocker}")
    if paper_net_pnl < 0:
        candidates.append("Review losing exits before adding new entries")
    if not candidates:
        candidates.append("Continue collecting data and compare pattern outcomes weekly")
    return candidates


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
