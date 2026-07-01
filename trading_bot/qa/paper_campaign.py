from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig
from trading_bot.qa.paper_stability import PaperStabilityConfig, evaluate_paper_stability, save_paper_stability_report


@dataclass(frozen=True)
class PaperCampaignPair:
    symbol: str
    timeframe: str
    status: str
    observed_days: int
    target_days: int
    trade_count: int
    target_trades: int
    net_pnl: float
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    report_path: str = ""


@dataclass(frozen=True)
class PaperCampaignReport:
    status: str
    generated_at_utc: str
    min_days: int
    preferred_days: int
    min_trades: int
    pairs_checked: int
    stable_pair_count: int
    total_trade_count: int
    total_net_pnl: float
    completion_pct: float
    summary: str
    blockers: list[str] = field(default_factory=list)
    pairs: list[PaperCampaignPair] = field(default_factory=list)


@dataclass(frozen=True)
class PaperCampaignConfig:
    min_days: int = 14
    preferred_days: int = 28
    min_trades: int = 20


def evaluate_paper_campaign(config: BotConfig, campaign: PaperCampaignConfig | None = None) -> PaperCampaignReport:
    campaign_config = campaign or PaperCampaignConfig()
    pairs: list[PaperCampaignPair] = []
    blockers: list[str] = []
    for symbol in config.symbols:
        for timeframe in config.timeframes:
            stability = evaluate_paper_stability(
                config.data_root,
                symbol,
                timeframe,
                PaperStabilityConfig(min_days=campaign_config.min_days, min_trades=campaign_config.min_trades),
            )
            path = save_paper_stability_report(stability, config.data_root)
            pair_blockers = list(stability.blockers)
            pair = PaperCampaignPair(
                symbol=symbol,
                timeframe=timeframe,
                status=stability.status,
                observed_days=stability.observed_days,
                target_days=campaign_config.min_days,
                trade_count=stability.trade_count,
                target_trades=campaign_config.min_trades,
                net_pnl=stability.net_pnl,
                blockers=pair_blockers,
                warnings=list(stability.warnings),
                report_path=str(path),
            )
            pairs.append(pair)
            blockers.extend(f"{symbol} {timeframe}: {blocker}" for blocker in pair_blockers)

    stable = [pair for pair in pairs if pair.status == "PAPER_STABLE"]
    completion_pct = _campaign_completion(pairs)
    status = "PAPER_CAMPAIGN_READY" if pairs and len(stable) == len(pairs) else "PAPER_CAMPAIGN_COLLECTING"
    return PaperCampaignReport(
        status=status,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        min_days=campaign_config.min_days,
        preferred_days=campaign_config.preferred_days,
        min_trades=campaign_config.min_trades,
        pairs_checked=len(pairs),
        stable_pair_count=len(stable),
        total_trade_count=sum(pair.trade_count for pair in pairs),
        total_net_pnl=sum(pair.net_pnl for pair in pairs),
        completion_pct=completion_pct,
        summary="paper campaign evidence is ready for owner review" if status == "PAPER_CAMPAIGN_READY" else f"{len(blockers)} blocker(s) still collecting evidence",
        blockers=blockers,
        pairs=pairs,
    )


def save_paper_campaign_report(report: PaperCampaignReport, root: str | Path) -> Path:
    path = Path(root) / "qa" / "paper_campaign" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _campaign_completion(pairs: list[PaperCampaignPair]) -> float:
    if not pairs:
        return 0.0
    scores = []
    for pair in pairs:
        day_score = min(pair.observed_days / max(pair.target_days, 1), 1.0)
        trade_score = min(pair.trade_count / max(pair.target_trades, 1), 1.0)
        scores.append((day_score + trade_score) / 2)
    return round((sum(scores) / len(scores)) * 100, 2)
