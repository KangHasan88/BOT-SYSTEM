from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldResearchPlan:
    status: str
    instrument: str
    allowed_mode: str
    blockers: list[str]
    required_evidence: list[str]


def build_gold_research_plan() -> GoldResearchPlan:
    return GoldResearchPlan(
        status="RESEARCH_ONLY",
        instrument="XAUUSD",
        allowed_mode="research",
        blockers=[
            "gold is not part of v1 live universe",
            "broker/CFD/futures rules differ from crypto spot",
            "spread, session, swap, and margin rules must be modeled separately",
            "leverage exposure is not allowed for small-capital phase",
        ],
        required_evidence=[
            "trusted XAUUSD OHLCV data source selected",
            "trading session calendar defined",
            "spread and fee/slippage model documented",
            "separate backtest and walk-forward validation completed",
            "paper trading track completed without live credentials",
        ],
    )


def is_gold_live_allowed() -> bool:
    return False
