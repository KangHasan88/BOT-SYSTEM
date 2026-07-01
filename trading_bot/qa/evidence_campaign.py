from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.backtest import BacktestConfig, calculate_backtest_metrics, run_event_backtest
from trading_bot.config import BotConfig
from trading_bot.data_collector import CandleCsvStore, timeframe_to_ms
from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.demo import seed_demo_data_pack
from trading_bot.qa.data_quality import DataQualityGateConfig, evaluate_data_quality_gate, save_data_quality_gate_report
from trading_bot.qa.live_go_no_go import evaluate_live_go_no_go, save_live_go_no_go_report
from trading_bot.qa.paper_stability import PaperStabilityConfig, evaluate_paper_stability, save_paper_stability_report
from trading_bot.readiness import evaluate_live_evidence, evaluate_live_readiness, save_live_evidence_report, save_live_readiness_report
from trading_bot.reports.backtest import save_backtest_metrics_report
from trading_bot.reports.walk_forward import save_walk_forward_report
from trading_bot.validation import WalkForwardConfig, run_walk_forward_validation


@dataclass(frozen=True)
class EvidenceCampaignStep:
    name: str
    symbol: str
    timeframe: str
    status: str
    reason: str
    path: str = ""


@dataclass(frozen=True)
class EvidenceCampaignReport:
    status: str
    generated_at_utc: str
    seeded_demo_data: bool
    pairs_checked: int
    pass_count: int
    blocked_count: int
    summary: str
    readiness_status: str
    go_no_go_decision: str
    live_evidence_status: str
    live_evidence_completion_pct: float
    steps: list[EvidenceCampaignStep] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceCampaignConfig:
    seed_demo_if_needed: bool = False
    candles_per_pair: int = 500
    min_candles: int = 360
    initial_equity: float = 1_000.0
    min_notional: float = 1.0
    min_paper_trades: int = 20
    paper_min_days: int = 14
    paper_min_trades: int = 20
    walk_forward_train_candles: int = 240
    walk_forward_test_candles: int = 120
    walk_forward_step_candles: int = 120
    walk_forward_min_test_trades: int = 5


def run_evidence_campaign(config: BotConfig, campaign: EvidenceCampaignConfig | None = None) -> EvidenceCampaignReport:
    campaign_config = campaign or EvidenceCampaignConfig()
    store = CandleCsvStore(config.data_root)
    seeded = False
    if campaign_config.seed_demo_if_needed and _needs_demo_seed(config, store, campaign_config.min_candles):
        seed_demo_data_pack(
            config,
            candles_per_pair=max(campaign_config.candles_per_pair, campaign_config.min_candles),
            initial_equity=campaign_config.initial_equity,
        )
        seeded = True

    steps: list[EvidenceCampaignStep] = []
    for symbol in config.symbols:
        for timeframe in config.timeframes:
            candles = store.load(symbol, timeframe)
            metadata = _metadata(symbol, campaign_config.min_notional)
            steps.append(_run_data_quality(config, symbol, timeframe, candles))
            steps.append(_run_backtest(config, symbol, timeframe, candles, metadata, campaign_config))
            steps.append(_run_walk_forward(config, symbol, timeframe, candles, metadata, campaign_config))
            steps.append(_run_paper_stability(config, symbol, timeframe, campaign_config))

    readiness = evaluate_live_readiness(config, min_paper_trades=campaign_config.min_paper_trades)
    readiness_path = save_live_readiness_report(readiness, config.data_root)
    steps.append(EvidenceCampaignStep("live_readiness", "", "", readiness.status, readiness.summary, str(readiness_path)))

    go_no_go = evaluate_live_go_no_go(config, owner_approved=False)
    go_no_go_path = save_live_go_no_go_report(go_no_go, config.data_root)
    steps.append(EvidenceCampaignStep("live_go_no_go", "", "", go_no_go.decision, go_no_go.summary, str(go_no_go_path)))

    live_evidence = evaluate_live_evidence(config, min_paper_trades=campaign_config.min_paper_trades)
    live_evidence_path = save_live_evidence_report(live_evidence, config.data_root)
    steps.append(
        EvidenceCampaignStep(
            "live_evidence",
            "",
            "",
            live_evidence.status,
            live_evidence.summary,
            str(live_evidence_path),
        )
    )

    blocked = [step for step in steps if _is_blocked(step)]
    return EvidenceCampaignReport(
        status="EVIDENCE_READY" if not blocked else "EVIDENCE_INCOMPLETE",
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        seeded_demo_data=seeded,
        pairs_checked=len(config.symbols) * len(config.timeframes),
        pass_count=len(steps) - len(blocked),
        blocked_count=len(blocked),
        summary="all evidence steps passed" if not blocked else f"{len(blocked)} evidence step(s) still blocked",
        readiness_status=readiness.status,
        go_no_go_decision=go_no_go.decision,
        live_evidence_status=live_evidence.status,
        live_evidence_completion_pct=live_evidence.completion_pct,
        steps=steps,
    )


def save_evidence_campaign_report(report: EvidenceCampaignReport, root: str | Path) -> Path:
    path = Path(root) / "readiness" / "evidence_campaign.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _run_data_quality(config: BotConfig, symbol: str, timeframe: str, candles: list) -> EvidenceCampaignStep:
    now_ms = _offline_now_ms(candles, timeframe)
    report = evaluate_data_quality_gate(
        candles,
        symbol,
        timeframe,
        now_ms=now_ms,
        config=DataQualityGateConfig(max_stale_candles=3),
    )
    path = save_data_quality_gate_report(report, config.data_root)
    return EvidenceCampaignStep("data_quality_gate", symbol, timeframe, report.status, "; ".join(report.blockers), str(path))


def _run_backtest(
    config: BotConfig,
    symbol: str,
    timeframe: str,
    candles: list,
    metadata: SymbolMetadata,
    campaign: EvidenceCampaignConfig,
) -> EvidenceCampaignStep:
    result = run_event_backtest(candles, metadata, BacktestConfig(initial_equity=campaign.initial_equity))
    metrics = calculate_backtest_metrics(result)
    path = save_backtest_metrics_report(metrics, config.data_root, symbol, timeframe)
    return EvidenceCampaignStep("backtest", symbol, timeframe, metrics.recommendation, metrics.reason, str(path))


def _run_walk_forward(
    config: BotConfig,
    symbol: str,
    timeframe: str,
    candles: list,
    metadata: SymbolMetadata,
    campaign: EvidenceCampaignConfig,
) -> EvidenceCampaignStep:
    report = run_walk_forward_validation(
        candles,
        metadata,
        WalkForwardConfig(
            train_candles=campaign.walk_forward_train_candles,
            test_candles=campaign.walk_forward_test_candles,
            step_candles=campaign.walk_forward_step_candles,
            min_test_trades=campaign.walk_forward_min_test_trades,
            initial_equity=campaign.initial_equity,
        ),
    )
    path = save_walk_forward_report(report, config.data_root, symbol, timeframe)
    return EvidenceCampaignStep("walk_forward", symbol, timeframe, report.recommendation, report.reason, str(path))


def _run_paper_stability(
    config: BotConfig,
    symbol: str,
    timeframe: str,
    campaign: EvidenceCampaignConfig,
) -> EvidenceCampaignStep:
    report = evaluate_paper_stability(
        config.data_root,
        symbol,
        timeframe,
        PaperStabilityConfig(min_days=campaign.paper_min_days, min_trades=campaign.paper_min_trades),
    )
    path = save_paper_stability_report(report, config.data_root)
    return EvidenceCampaignStep("paper_stability", symbol, timeframe, report.status, "; ".join(report.blockers), str(path))


def _needs_demo_seed(config: BotConfig, store: CandleCsvStore, min_candles: int) -> bool:
    for symbol in config.symbols:
        for timeframe in config.timeframes:
            if len(store.load(symbol, timeframe)) < min_candles:
                return True
    return False


def _offline_now_ms(candles: list, timeframe: str) -> int | None:
    if not candles:
        return None
    return max(candle.open_time_ms for candle in candles) + timeframe_to_ms(timeframe)


def _metadata(symbol: str, min_notional: float) -> SymbolMetadata:
    base, quote = symbol.split("/")
    return SymbolMetadata(
        symbol=symbol,
        base_asset=base,
        quote_asset=quote,
        min_notional=min_notional,
        price_precision=8,
        quantity_precision=8,
        taker_fee_pct=0.10,
        maker_fee_pct=0.10,
        source="evidence_campaign",
    )


def _is_blocked(step: EvidenceCampaignStep) -> bool:
    return step.status not in {
        "PASSED",
        "PASS",
        "PAPER_CANDIDATE",
        "PAPER_STABLE",
        "READY_FOR_MANUAL_REVIEW",
        "GO_FOR_OWNER_REVIEW",
        "COMPLETE_FOR_OWNER_REVIEW",
    }
