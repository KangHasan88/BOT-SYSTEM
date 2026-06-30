from __future__ import annotations

from dataclasses import dataclass


ALLOWED_ACTIONS = {"research_note", "experiment_proposal", "parameter_hypothesis"}
BLOCKED_KEYWORDS = {
    "place_order",
    "live_order",
    "disable_stop",
    "disable_risk",
    "bypass_risk",
    "set_live_enabled_true",
    "withdrawal",
}


@dataclass(frozen=True)
class AiRecommendation:
    action: str
    title: str
    rationale: str
    proposed_change: str
    requires_backtest: bool = True
    requires_paper: bool = True


@dataclass(frozen=True)
class GuardrailDecision:
    status: str
    reason: str


def evaluate_ai_recommendation(recommendation: AiRecommendation) -> GuardrailDecision:
    text = " ".join(
        [
            recommendation.action,
            recommendation.title,
            recommendation.rationale,
            recommendation.proposed_change,
        ]
    ).lower()

    if recommendation.action not in ALLOWED_ACTIONS:
        return GuardrailDecision("BLOCKED", "AI action is outside research-only allowlist")
    if any(keyword in text for keyword in BLOCKED_KEYWORDS):
        return GuardrailDecision("BLOCKED", "AI recommendation attempts to bypass live/risk guard")
    if not recommendation.requires_backtest or not recommendation.requires_paper:
        return GuardrailDecision("BLOCKED", "AI experiment must require backtest and paper validation")
    return GuardrailDecision("ACCEPTED_FOR_RESEARCH", "recommendation may enter experiment backlog")
