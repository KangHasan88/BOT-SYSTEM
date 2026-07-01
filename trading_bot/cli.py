from __future__ import annotations

import argparse
from pathlib import Path

from trading_bot.alerts import AlertOutbox, build_daily_report_alert, build_error_alert, build_stop_alert
from trading_bot.ai_guardrails import AiRecommendation, evaluate_ai_recommendation
from trading_bot.backtest import BacktestCsvStore, calculate_backtest_metrics, run_event_backtest
from trading_bot.config import ConfigError, load_config
from trading_bot.dashboard import save_review_dashboard
from trading_bot.data_collector.binance_public import BinancePublicKlineClient
from trading_bot.data_collector.context_store import MarketContextCsvStore
from trading_bot.data_collector.csv_store import CandleCsvStore
from trading_bot.data_collector.service import MarketDataCollector
from trading_bot.demo import seed_demo_data_pack
from trading_bot.execution import ExchangeOrderRequest, SandboxExchangeAdapter
from trading_bot.feature_engine import FeatureCsvStore, RegimeCsvStore, build_features, classify_regimes
from trading_bot.live import LivePhaseOneConfig, build_live_phase_one_plan
from trading_bot.markets import build_gold_research_plan
from trading_bot.ops import run_research_cycle
from trading_bot.orchestrator import serve_orchestrator
from trading_bot.observability import read_audit_events
from trading_bot.paper import PaperConfig, PaperCsvStore, run_paper_session
from trading_bot.pattern_analyzer import PatternCsvStore, detect_price_action_patterns
from trading_bot.post_trade import generate_post_trade_report, load_paper_trades, save_post_trade_report
from trading_bot.qa import (
    DataQualityGateConfig,
    PaperStabilityConfig,
    evaluate_data_quality_gate,
    evaluate_live_go_no_go,
    evaluate_paper_stability,
    evaluate_production_smoke,
    evaluate_vps_readiness,
    generate_security_qa_report,
    run_incident_drill,
    run_risk_guard_drill,
    save_data_quality_gate_report,
    save_incident_drill_report,
    save_live_go_no_go_report,
    save_paper_stability_report,
    save_production_smoke_report,
    save_risk_guard_drill_report,
    save_security_qa_report,
    save_vps_readiness_report,
)
from trading_bot.reports.backtest import save_backtest_metrics_report
from trading_bot.reports.daily_journal import generate_daily_market_journal, save_daily_market_journal
from trading_bot.reports.quality import save_quality_report
from trading_bot.reports.walk_forward import save_walk_forward_report
from trading_bot.research import (
    ResearchDatasetCsvStore,
    build_pattern_outcome_dataset,
    generate_database_learning_snapshot,
    save_database_learning_snapshot,
)
from trading_bot.readiness import evaluate_live_readiness, save_live_readiness_report
from trading_bot.scheduler import is_entry_allowed_at_ms
from trading_bot.security import load_env_file, scan_for_secrets, validate_env_security
from trading_bot.safety import activate_kill_switch, clear_kill_switch, read_kill_switch
from trading_bot.storage import default_database_path, import_runtime_data, init_database, load_database_status
from trading_bot.risk_manager import (
    AccountState,
    TradeCandidate,
    evaluate_daily_profit_lock,
    evaluate_position_lock,
    evaluate_trade_risk,
)
from trading_bot.strategy import SignalCsvStore, generate_conservative_signals
from trading_bot.validation import WalkForwardConfig, run_walk_forward_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trading-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config")
    validate.add_argument(
        "--config",
        default="config/bot.sample.toml",
        help="Path to the bot config file.",
    )

    init_db = subparsers.add_parser("init-db")
    init_db.add_argument("--config", default="config/bot.sample.toml")
    init_db.add_argument("--db-path")
    init_db.add_argument("--schema", default="database/schema.sql")

    import_db = subparsers.add_parser("import-runtime-db")
    import_db.add_argument("--config", default="config/bot.sample.toml")
    import_db.add_argument("--db-path")
    import_db.add_argument("--schema", default="database/schema.sql")

    db_status = subparsers.add_parser("db-status")
    db_status.add_argument("--config", default="config/bot.sample.toml")
    db_status.add_argument("--db-path")

    db_learning = subparsers.add_parser("db-learning-report")
    db_learning.add_argument("--config", default="config/bot.sample.toml")
    db_learning.add_argument("--db-path")
    db_learning.add_argument("--limit", type=int, default=500)

    demo_data = subparsers.add_parser("seed-demo-data")
    demo_data.add_argument("--config", default="config/bot.sample.toml")
    demo_data.add_argument("--candles-per-pair", type=int, default=180)
    demo_data.add_argument("--initial-equity", type=float, default=1_000.0)

    sync = subparsers.add_parser("sync-ohlcv")
    sync.add_argument("--config", default="config/bot.sample.toml")
    sync.add_argument("--symbol", required=True)
    sync.add_argument("--timeframe", required=True)
    sync.add_argument("--limit", type=int, default=500)

    backfill = subparsers.add_parser("backfill-ohlcv")
    backfill.add_argument("--config", default="config/bot.sample.toml")
    backfill.add_argument("--symbol", required=True)
    backfill.add_argument("--timeframe", required=True)
    backfill.add_argument("--start-time-ms", type=int, required=True)
    backfill.add_argument("--batches", type=int, default=1)
    backfill.add_argument("--limit", type=int, default=1000)

    audit = subparsers.add_parser("audit-ohlcv")
    audit.add_argument("--config", default="config/bot.sample.toml")
    audit.add_argument("--symbol", required=True)
    audit.add_argument("--timeframe", required=True)

    quality = subparsers.add_parser("quality-report")
    quality.add_argument("--config", default="config/bot.sample.toml")
    quality.add_argument("--symbol", required=True)
    quality.add_argument("--timeframe", required=True)

    data_quality_gate = subparsers.add_parser("data-quality-gate")
    data_quality_gate.add_argument("--config", default="config/bot.sample.toml")
    data_quality_gate.add_argument("--symbol", required=True)
    data_quality_gate.add_argument("--timeframe", required=True)
    data_quality_gate.add_argument("--now-ms", type=int)
    data_quality_gate.add_argument("--max-stale-candles", type=int, default=3)

    features = subparsers.add_parser("build-features")
    features.add_argument("--config", default="config/bot.sample.toml")
    features.add_argument("--symbol", required=True)
    features.add_argument("--timeframe", required=True)

    patterns = subparsers.add_parser("analyze-patterns")
    patterns.add_argument("--config", default="config/bot.sample.toml")
    patterns.add_argument("--symbol", required=True)
    patterns.add_argument("--timeframe", required=True)
    patterns.add_argument("--lookback", type=int, default=20)

    research_dataset = subparsers.add_parser("build-research-dataset")
    research_dataset.add_argument("--config", default="config/bot.sample.toml")
    research_dataset.add_argument("--symbol", required=True)
    research_dataset.add_argument("--timeframe", required=True)
    research_dataset.add_argument("--lookback", type=int, default=20)
    research_dataset.add_argument("--horizon-candles", type=int, default=12)

    regimes = subparsers.add_parser("classify-regimes")
    regimes.add_argument("--config", default="config/bot.sample.toml")
    regimes.add_argument("--symbol", required=True)
    regimes.add_argument("--timeframe", required=True)

    signals = subparsers.add_parser("generate-signals")
    signals.add_argument("--config", default="config/bot.sample.toml")
    signals.add_argument("--symbol", required=True)
    signals.add_argument("--timeframe", required=True)

    risk = subparsers.add_parser("evaluate-risk")
    risk.add_argument("--symbol", required=True)
    risk.add_argument("--side", default="buy")
    risk.add_argument("--entry-price", type=float, required=True)
    risk.add_argument("--stop-price", type=float, required=True)
    risk.add_argument("--equity", type=float, required=True)
    risk.add_argument("--day-start-equity", type=float, required=True)
    risk.add_argument("--month-start-equity", type=float, required=True)
    risk.add_argument("--open-positions", type=int, default=0)
    risk.add_argument("--min-notional", type=float, default=5.0)

    daily_lock = subparsers.add_parser("evaluate-profit-lock")
    daily_lock.add_argument("--day-start-equity", type=float, required=True)
    daily_lock.add_argument("--current-equity", type=float, required=True)
    daily_lock.add_argument("--previous-high-watermark-equity", type=float)

    position_lock = subparsers.add_parser("evaluate-position-lock")
    position_lock.add_argument("--side", default="buy")
    position_lock.add_argument("--entry-price", type=float, required=True)
    position_lock.add_argument("--stop-price", type=float, required=True)
    position_lock.add_argument("--current-price", type=float, required=True)

    backtest = subparsers.add_parser("run-backtest")
    backtest.add_argument("--config", default="config/bot.sample.toml")
    backtest.add_argument("--symbol", required=True)
    backtest.add_argument("--timeframe", required=True)
    backtest.add_argument("--initial-equity", type=float, default=1_000.0)
    backtest.add_argument("--min-notional", type=float, default=1.0)

    backtest_report = subparsers.add_parser("backtest-report")
    backtest_report.add_argument("--config", default="config/bot.sample.toml")
    backtest_report.add_argument("--symbol", required=True)
    backtest_report.add_argument("--timeframe", required=True)
    backtest_report.add_argument("--initial-equity", type=float, default=1_000.0)
    backtest_report.add_argument("--min-notional", type=float, default=1.0)

    walk_forward = subparsers.add_parser("walk-forward-report")
    walk_forward.add_argument("--config", default="config/bot.sample.toml")
    walk_forward.add_argument("--symbol", required=True)
    walk_forward.add_argument("--timeframe", required=True)
    walk_forward.add_argument("--initial-equity", type=float, default=1_000.0)
    walk_forward.add_argument("--min-notional", type=float, default=1.0)
    walk_forward.add_argument("--train-candles", type=int, default=240)
    walk_forward.add_argument("--test-candles", type=int, default=120)
    walk_forward.add_argument("--step-candles", type=int, default=120)
    walk_forward.add_argument("--min-test-trades", type=int, default=5)

    paper = subparsers.add_parser("run-paper")
    paper.add_argument("--config", default="config/bot.sample.toml")
    paper.add_argument("--symbol", required=True)
    paper.add_argument("--timeframe", required=True)
    paper.add_argument("--initial-equity", type=float, default=1_000.0)
    paper.add_argument("--min-notional", type=float, default=1.0)

    daily_journal = subparsers.add_parser("daily-journal")
    daily_journal.add_argument("--config", default="config/bot.sample.toml")
    daily_journal.add_argument("--symbol", required=True)
    daily_journal.add_argument("--timeframe", required=True)
    daily_journal.add_argument("--initial-equity", type=float, default=1_000.0)
    daily_journal.add_argument("--min-notional", type=float, default=1.0)

    dashboard = subparsers.add_parser("build-dashboard")
    dashboard.add_argument("--config", default="config/bot.sample.toml")

    orchestrator = subparsers.add_parser("serve-orchestrator")
    orchestrator.add_argument("--config", default="config/bot.sample.toml")
    orchestrator.add_argument("--host", default="127.0.0.1")
    orchestrator.add_argument("--port", type=int, default=8000)

    alert_daily = subparsers.add_parser("alert-daily-report")
    alert_daily.add_argument("--config", default="config/bot.sample.toml")
    alert_daily.add_argument("--symbol", required=True)
    alert_daily.add_argument("--timeframe", required=True)

    alert_stop = subparsers.add_parser("alert-stop")
    alert_stop.add_argument("--config", default="config/bot.sample.toml")
    alert_stop.add_argument("--symbol", required=True)
    alert_stop.add_argument("--reason", required=True)
    alert_stop.add_argument("--equity", type=float)

    alert_error = subparsers.add_parser("alert-error")
    alert_error.add_argument("--config", default="config/bot.sample.toml")
    alert_error.add_argument("--component", required=True)
    alert_error.add_argument("--error", required=True)

    sandbox_order = subparsers.add_parser("sandbox-order")
    sandbox_order.add_argument("--environment", choices=["sandbox", "testnet"], default="sandbox")
    sandbox_order.add_argument("--symbol", required=True)
    sandbox_order.add_argument("--side", choices=["buy", "sell"], required=True)
    sandbox_order.add_argument("--order-type", choices=["market", "limit"], default="market")
    sandbox_order.add_argument("--quantity", type=float, required=True)
    sandbox_order.add_argument("--price", type=float)

    cycle = subparsers.add_parser("run-cycle")
    cycle.add_argument("--config", default="config/bot.sample.toml")
    cycle.add_argument("--sync-latest", action="store_true")
    cycle.add_argument("--limit", type=int, default=500)
    cycle.add_argument("--initial-equity", type=float, default=1_000.0)
    cycle.add_argument("--min-notional", type=float, default=1.0)

    session = subparsers.add_parser("evaluate-session")
    session.add_argument("--config", default="config/bot.sample.toml")
    session.add_argument("--open-time-ms", type=int, required=True)

    security = subparsers.add_parser("validate-security")
    security.add_argument("--env-file", default=".env.example")
    security.add_argument("--scan-root", default=".")

    security_qa = subparsers.add_parser("security-qa-report")
    security_qa.add_argument("--config", default="config/bot.sample.toml")
    security_qa.add_argument("--env-file", default=".env.example")
    security_qa.add_argument("--scan-root", default=".")

    audit_summary = subparsers.add_parser("audit-summary")
    audit_summary.add_argument("--config", default="config/bot.sample.toml")
    audit_summary.add_argument("--limit", type=int, default=10)

    readiness = subparsers.add_parser("live-readiness-report")
    readiness.add_argument("--config", default="config/bot.sample.toml")
    readiness.add_argument("--env-file", default=".env.example")
    readiness.add_argument("--scan-root", default=".")
    readiness.add_argument("--min-paper-trades", type=int, default=20)

    live_plan = subparsers.add_parser("live-phase-one-plan")
    live_plan.add_argument("--config", default="config/bot.sample.toml")
    live_plan.add_argument("--env-file", default=".env.example")
    live_plan.add_argument("--scan-root", default=".")
    live_plan.add_argument("--min-paper-trades", type=int, default=20)
    live_plan.add_argument("--capital-idr", type=float, default=1_000_000.0)

    go_no_go = subparsers.add_parser("live-go-no-go-report")
    go_no_go.add_argument("--config", default="config/bot.sample.toml")
    go_no_go.add_argument("--owner-approved", action="store_true")

    vps_readiness = subparsers.add_parser("vps-readiness-report")
    vps_readiness.add_argument("--config", default="config/bot.vps.sample.toml")
    vps_readiness.add_argument("--service", default="deploy/systemd/trading-bot-cycle.service")
    vps_readiness.add_argument("--timer", default="deploy/systemd/trading-bot-cycle.timer")
    vps_readiness.add_argument("--smoke", default="deploy/smoke-vps.sh")
    vps_readiness.add_argument("--output-config", default="config/bot.sample.toml")

    production_smoke = subparsers.add_parser("production-smoke-report")
    production_smoke.add_argument("--config", default="config/bot.sample.toml")
    production_smoke.add_argument("--smoke", default="deploy/smoke-vps.sh")
    production_smoke.add_argument("--runbook", default="docs/vps-deployment.md")

    post_trade = subparsers.add_parser("post-trade-report")
    post_trade.add_argument("--config", default="config/bot.sample.toml")
    post_trade.add_argument("--symbol", required=True)
    post_trade.add_argument("--timeframe", required=True)

    paper_stability = subparsers.add_parser("paper-stability-report")
    paper_stability.add_argument("--config", default="config/bot.sample.toml")
    paper_stability.add_argument("--symbol", required=True)
    paper_stability.add_argument("--timeframe", required=True)
    paper_stability.add_argument("--min-days", type=int, default=14)
    paper_stability.add_argument("--min-trades", type=int, default=20)

    risk_drill = subparsers.add_parser("risk-guard-drill")
    risk_drill.add_argument("--config", default="config/bot.sample.toml")
    risk_drill.add_argument("--symbol", default="BTC/USDT")

    incident_drill = subparsers.add_parser("incident-drill-report")
    incident_drill.add_argument("--config", default="config/bot.sample.toml")
    incident_drill.add_argument("--symbol", default="BTC/USDT")

    gold_plan = subparsers.add_parser("gold-research-plan")

    ai_guard = subparsers.add_parser("evaluate-ai-recommendation")
    ai_guard.add_argument("--action", required=True)
    ai_guard.add_argument("--title", required=True)
    ai_guard.add_argument("--rationale", required=True)
    ai_guard.add_argument("--proposed-change", required=True)

    kill_switch = subparsers.add_parser("kill-switch")
    kill_switch.add_argument("--config", default="config/bot.sample.toml")
    kill_switch.add_argument("--action", choices=["status", "activate", "clear"], required=True)
    kill_switch.add_argument("--reason", default="")

    context = subparsers.add_parser("capture-market-context")
    context.add_argument("--config", default="config/bot.sample.toml")
    context.add_argument("--symbol", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-config":
        try:
            config = load_config(Path(args.config))
        except ConfigError as exc:
            print(f"config invalid: {exc}")
            return 2

        print(
            "config ok: "
            f"mode={config.mode}, live_enabled={str(config.live_enabled).lower()}, "
            f"symbols={','.join(config.symbols)}"
        )
        return 0

    if args.command == "init-db":
        try:
            config = load_config(Path(args.config))
            db_path = Path(args.db_path) if args.db_path else default_database_path(config.data_root)
            path = init_database(db_path, args.schema)
        except (ConfigError, OSError) as exc:
            print(f"init db failed: {exc}")
            return 2

        print(f"init db ok: path={path}")
        return 0

    if args.command == "import-runtime-db":
        try:
            config = load_config(Path(args.config))
            db_path = Path(args.db_path) if args.db_path else default_database_path(config.data_root)
            summary = import_runtime_data(config.data_root, db_path, args.schema)
        except (ConfigError, OSError, ValueError) as exc:
            print(f"import runtime db failed: {exc}")
            return 2

        print(
            "import runtime db ok: "
            f"path={summary.db_path}, total={summary.total_rows}, candles={summary.candles}, "
            f"paper_orders={summary.paper_orders}, paper_trades={summary.paper_trades}, "
            f"paper_account={summary.paper_account_snapshots}, audit={summary.audit_events}, "
            f"orchestrator={summary.orchestrator_activities}"
        )
        return 0

    if args.command == "db-status":
        try:
            config = load_config(Path(args.config))
            db_path = Path(args.db_path) if args.db_path else default_database_path(config.data_root)
            status = load_database_status(config.data_root, db_path)
        except (ConfigError, OSError, ValueError) as exc:
            print(f"db status failed: {exc}")
            return 2

        print(
            "db status: "
            f"path={status.db_path}, exists={str(status.exists).lower()}, "
            f"size_bytes={status.size_bytes}, total_rows={status.total_rows}, "
            f"updated_at_utc={status.updated_at_utc or '-'}"
        )
        for table in status.tables:
            print(f"table: {table.table} rows={table.rows}")
        return 0 if status.exists else 2

    if args.command == "db-learning-report":
        try:
            config = load_config(Path(args.config))
            db_path = Path(args.db_path) if args.db_path else default_database_path(config.data_root)
            snapshot = generate_database_learning_snapshot(
                db_path,
                symbols=list(config.symbols),
                timeframes=list(config.timeframes),
                limit=args.limit,
            )
            path = save_database_learning_snapshot(snapshot, config.data_root)
        except (ConfigError, OSError, ValueError) as exc:
            print(f"db learning report failed: {exc}")
            return 2

        print(
            "db learning report ok: "
            f"path={path}, rows={len(snapshot.rows)}, notes={len(snapshot.notes)}, db={snapshot.db_path}"
        )
        for note in snapshot.notes:
            print(f"note: {note}")
        return 0

    if args.command == "seed-demo-data":
        try:
            config = load_config(Path(args.config))
            result = seed_demo_data_pack(
                config,
                candles_per_pair=args.candles_per_pair,
                initial_equity=args.initial_equity,
            )
        except (ConfigError, OSError, ValueError) as exc:
            print(f"seed demo data failed: {exc}")
            return 2

        print(
            "seed demo data ok: "
            f"candles={result.candle_rows}, cycle_candles={result.cycle_candles_seen}, "
            f"paper_trades={result.paper_trades}, db_rows={result.database_rows}, "
            f"learning={result.learning_report_path}, dashboard={result.dashboard_path}"
        )
        return 0

    if args.command == "sync-ohlcv":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            collector = MarketDataCollector(
                store=CandleCsvStore(config.data_root),
                client=BinancePublicKlineClient(),
            )
            result = collector.sync_latest(args.symbol, args.timeframe, limit=args.limit)
        except (ConfigError, ValueError) as exc:
            print(f"sync failed: {exc}")
            return 2

        print(
            "sync ok: "
            f"symbol={result.symbol}, timeframe={result.timeframe}, "
            f"fetched={result.fetched}, inserted={result.inserted_or_updated}, "
            f"total={result.total_after_sync}"
        )
        return 0

    if args.command == "backfill-ohlcv":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            collector = MarketDataCollector(
                store=CandleCsvStore(config.data_root),
                client=BinancePublicKlineClient(),
            )
            result = collector.backfill(
                args.symbol,
                args.timeframe,
                start_time_ms=args.start_time_ms,
                batches=args.batches,
                limit=args.limit,
            )
        except (ConfigError, ValueError) as exc:
            print(f"backfill failed: {exc}")
            return 2

        print(
            "backfill ok: "
            f"symbol={result.symbol}, timeframe={result.timeframe}, "
            f"fetched={result.fetched}, inserted={result.inserted_or_updated}, "
            f"total={result.total_after_sync}"
        )
        return 0

    if args.command == "audit-ohlcv":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            collector = MarketDataCollector(
                store=CandleCsvStore(config.data_root),
                client=BinancePublicKlineClient(),
            )
            report = collector.quality_report(args.symbol, args.timeframe)
        except (ConfigError, ValueError) as exc:
            print(f"audit failed: {exc}")
            return 2

        print(
            "audit ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, "
            f"candles={report.candle_count}, gaps={report.gap_count}, "
            f"duplicates={report.duplicate_count}, zero_volume={report.zero_volume_count}, "
            f"dataset_id={report.dataset_id}"
        )
        return 0

    if args.command == "quality-report":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            collector = MarketDataCollector(
                store=CandleCsvStore(config.data_root),
                client=BinancePublicKlineClient(),
            )
            report = collector.quality_report(args.symbol, args.timeframe)
            path = save_quality_report(report, config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"quality report failed: {exc}")
            return 2

        print(
            "quality report ok: "
            f"path={path}, candles={report.candle_count}, gaps={report.gap_count}, "
            f"dataset_id={report.dataset_id}"
        )
        return 0

    if args.command == "data-quality-gate":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            report = evaluate_data_quality_gate(
                candles,
                args.symbol,
                args.timeframe,
                now_ms=args.now_ms,
                config=DataQualityGateConfig(max_stale_candles=args.max_stale_candles),
            )
            path = save_data_quality_gate_report(report, config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"data quality gate failed: {exc}")
            return 2

        print(
            "data quality gate: "
            f"status={report.status}, candles={report.candle_count}, gaps={report.gap_count}, "
            f"duplicates={report.duplicate_count}, stale_candles={report.stale_candles}, "
            f"bad_prices={report.non_positive_price_count}, high_low_violations={report.high_low_violation_count}, "
            f"path={path}"
        )
        for blocker in report.blockers:
            print(f"blocker: {blocker}")
        for warning in report.warnings:
            print(f"warning: {warning}")
        return 0 if report.status in {"PASSED", "WARN"} else 2

    if args.command == "build-features":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candle_store = CandleCsvStore(config.data_root)
            candles = candle_store.load(args.symbol, args.timeframe)
            rows = build_features(candles)
            path = FeatureCsvStore(config.data_root).write(rows)
        except (ConfigError, ValueError) as exc:
            print(f"build features failed: {exc}")
            return 2

        print(
            "build features ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, rows={len(rows)}, "
            f"path={path or ''}"
        )
        return 0

    if args.command == "analyze-patterns":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            signals = detect_price_action_patterns(candles, lookback=args.lookback)
            path = PatternCsvStore(config.data_root).write(signals, args.symbol, args.timeframe)
        except (ConfigError, ValueError) as exc:
            print(f"analyze patterns failed: {exc}")
            return 2

        print(
            "analyze patterns ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, signals={len(signals)}, path={path}"
        )
        return 0

    if args.command == "build-research-dataset":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            patterns = detect_price_action_patterns(candles, lookback=args.lookback)
            rows = build_pattern_outcome_dataset(candles, patterns, horizon_candles=args.horizon_candles)
            path = ResearchDatasetCsvStore(config.data_root).write(rows, args.symbol, args.timeframe)
        except (ConfigError, ValueError) as exc:
            print(f"build research dataset failed: {exc}")
            return 2

        print(
            "build research dataset ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, rows={len(rows)}, path={path}"
        )
        return 0

    if args.command == "classify-regimes":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            feature_rows = build_features(candles)
            regime_rows = classify_regimes(feature_rows)
            path = RegimeCsvStore(config.data_root).write(
                regime_rows,
                args.symbol,
                args.timeframe,
            )
        except (ConfigError, ValueError) as exc:
            print(f"classify regimes failed: {exc}")
            return 2

        print(
            "classify regimes ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, rows={len(regime_rows)}, path={path}"
        )
        return 0

    if args.command == "generate-signals":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            feature_rows = build_features(candles)
            regime_rows = classify_regimes(feature_rows)
            signal_rows = generate_conservative_signals(feature_rows, regime_rows)
            path = SignalCsvStore(config.data_root).write(
                signal_rows,
                args.symbol,
                args.timeframe,
            )
        except (ConfigError, ValueError) as exc:
            print(f"generate signals failed: {exc}")
            return 2

        buy_count = sum(1 for signal in signal_rows if signal.action == "BUY_CANDIDATE")
        exit_count = sum(1 for signal in signal_rows if signal.action == "EXIT_CANDIDATE")
        skip_count = sum(1 for signal in signal_rows if signal.action == "SKIP")
        print(
            "generate signals ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, rows={len(signal_rows)}, "
            f"buy={buy_count}, exit={exit_count}, skip={skip_count}, path={path}"
        )
        return 0

    if args.command == "evaluate-risk":
        from trading_bot.data_collector.market_context import SymbolMetadata

        decision = evaluate_trade_risk(
            account=AccountState(
                equity=args.equity,
                day_start_equity=args.day_start_equity,
                month_start_equity=args.month_start_equity,
                open_positions=args.open_positions,
            ),
            candidate=TradeCandidate(
                symbol=args.symbol,
                side=args.side,
                entry_price=args.entry_price,
                stop_price=args.stop_price,
                confidence=0.5,
            ),
            metadata=SymbolMetadata(
                symbol=args.symbol,
                base_asset=args.symbol.split("/")[0] if "/" in args.symbol else "",
                quote_asset=args.symbol.split("/")[1] if "/" in args.symbol else "",
                min_notional=args.min_notional,
                price_precision=8,
                quantity_precision=8,
                taker_fee_pct=0.10,
                maker_fee_pct=0.10,
                source="cli",
            ),
        )
        print(
            "risk decision: "
            f"status={decision.status}, quantity={decision.quantity:.8f}, "
            f"notional={decision.notional:.8f}, risk={decision.risk_amount:.8f}, "
            f"stop_distance_pct={decision.stop_distance_pct:.4f}, reason={decision.reason}"
        )
        return 0 if decision.status == "APPROVED" else 2

    if args.command == "evaluate-profit-lock":
        state = evaluate_daily_profit_lock(
            day_start_equity=args.day_start_equity,
            current_equity=args.current_equity,
            previous_high_watermark_equity=args.previous_high_watermark_equity,
        )
        print(
            "profit lock: "
            f"status={state.status}, active={str(state.lock_active).lower()}, "
            f"high_watermark={state.high_watermark_equity:.8f}, "
            f"floor={state.floor_equity or 0:.8f}, reason={state.reason}"
        )
        return 0 if state.status != "STOP_TRADING" else 2

    if args.command == "evaluate-position-lock":
        decision = evaluate_position_lock(
            side=args.side,
            entry_price=args.entry_price,
            stop_price=args.stop_price,
            current_price=args.current_price,
        )
        print(
            "position lock: "
            f"update={str(decision.should_update_stop).lower()}, "
            f"new_stop={decision.new_stop_price:.8f}, reason={decision.reason}"
        )
        return 0

    if args.command == "run-backtest":
        from trading_bot.backtest import BacktestConfig
        from trading_bot.data_collector.market_context import SymbolMetadata

        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            result = run_event_backtest(
                candles,
                metadata=SymbolMetadata(
                    symbol=args.symbol,
                    base_asset=args.symbol.split("/")[0],
                    quote_asset=args.symbol.split("/")[1],
                    min_notional=args.min_notional,
                    price_precision=8,
                    quantity_precision=8,
                    taker_fee_pct=0.10,
                    maker_fee_pct=0.10,
                    source="cli",
                ),
                config=BacktestConfig(initial_equity=args.initial_equity),
            )
            trades_path, equity_path = BacktestCsvStore(config.data_root).write(result)
        except (ConfigError, ValueError) as exc:
            print(f"backtest failed: {exc}")
            return 2

        print(
            "backtest ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, trades={len(result.trades)}, "
            f"initial={result.initial_equity:.8f}, final={result.final_equity:.8f}, "
            f"trades_path={trades_path}, equity_path={equity_path}"
        )
        return 0

    if args.command == "backtest-report":
        from trading_bot.backtest import BacktestConfig
        from trading_bot.data_collector.market_context import SymbolMetadata

        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            result = run_event_backtest(
                candles,
                metadata=SymbolMetadata(
                    symbol=args.symbol,
                    base_asset=args.symbol.split("/")[0],
                    quote_asset=args.symbol.split("/")[1],
                    min_notional=args.min_notional,
                    price_precision=8,
                    quantity_precision=8,
                    taker_fee_pct=0.10,
                    maker_fee_pct=0.10,
                    source="cli",
                ),
                config=BacktestConfig(initial_equity=args.initial_equity),
            )
            metrics = calculate_backtest_metrics(result)
            path = save_backtest_metrics_report(metrics, config.data_root, args.symbol, args.timeframe)
        except (ConfigError, ValueError) as exc:
            print(f"backtest report failed: {exc}")
            return 2

        print(
            "backtest report ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, trades={metrics.trade_count}, "
            f"return_pct={metrics.total_return_pct:.4f}, max_dd_pct={metrics.max_drawdown_pct:.4f}, "
            f"profit_factor={metrics.profit_factor}, recommendation={metrics.recommendation}, path={path}"
        )
        return 0

    if args.command == "walk-forward-report":
        from trading_bot.data_collector.market_context import SymbolMetadata

        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            report = run_walk_forward_validation(
                candles,
                metadata=SymbolMetadata(
                    symbol=args.symbol,
                    base_asset=args.symbol.split("/")[0],
                    quote_asset=args.symbol.split("/")[1],
                    min_notional=args.min_notional,
                    price_precision=8,
                    quantity_precision=8,
                    taker_fee_pct=0.10,
                    maker_fee_pct=0.10,
                    source="cli",
                ),
                config=WalkForwardConfig(
                    train_candles=args.train_candles,
                    test_candles=args.test_candles,
                    step_candles=args.step_candles,
                    min_test_trades=args.min_test_trades,
                    initial_equity=args.initial_equity,
                ),
            )
            path = save_walk_forward_report(report, config.data_root, args.symbol, args.timeframe)
        except (ConfigError, ValueError) as exc:
            print(f"walk-forward report failed: {exc}")
            return 2

        print(
            "walk-forward report ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, folds={report.fold_count}, "
            f"test_trades={report.total_test_trades}, recommendation={report.recommendation}, path={path}"
        )
        return 0 if report.recommendation != "REJECT" else 2

    if args.command == "run-paper":
        from trading_bot.data_collector.market_context import SymbolMetadata

        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            result = run_paper_session(
                candles,
                metadata=SymbolMetadata(
                    symbol=args.symbol,
                    base_asset=args.symbol.split("/")[0],
                    quote_asset=args.symbol.split("/")[1],
                    min_notional=args.min_notional,
                    price_precision=8,
                    quantity_precision=8,
                    taker_fee_pct=0.10,
                    maker_fee_pct=0.10,
                    source="cli",
                ),
                config=PaperConfig(initial_equity=args.initial_equity),
            )
            orders_path, trades_path, account_path = PaperCsvStore(config.data_root).write(result)
        except (ConfigError, ValueError) as exc:
            print(f"paper session failed: {exc}")
            return 2

        rejected_count = sum(1 for order in result.orders if order.status == "REJECTED")
        print(
            "paper session ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, orders={len(result.orders)}, "
            f"rejected={rejected_count}, trades={len(result.trades)}, "
            f"initial={result.initial_equity:.8f}, final={result.final_equity:.8f}, "
            f"orders_path={orders_path}, trades_path={trades_path}, account_path={account_path}"
        )
        return 0

    if args.command == "daily-journal":
        from trading_bot.backtest import BacktestConfig
        from trading_bot.data_collector.market_context import SymbolMetadata

        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            metadata = SymbolMetadata(
                symbol=args.symbol,
                base_asset=args.symbol.split("/")[0],
                quote_asset=args.symbol.split("/")[1],
                min_notional=args.min_notional,
                price_precision=8,
                quantity_precision=8,
                taker_fee_pct=0.10,
                maker_fee_pct=0.10,
                source="cli",
            )
            paper_result = run_paper_session(
                candles,
                metadata=metadata,
                config=PaperConfig(initial_equity=args.initial_equity),
            )
            backtest_result = run_event_backtest(
                candles,
                metadata=metadata,
                config=BacktestConfig(initial_equity=args.initial_equity),
            )
            journal = generate_daily_market_journal(candles, paper_result, backtest_result)
            path = save_daily_market_journal(journal, config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"daily journal failed: {exc}")
            return 2

        print(
            "daily journal ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, date={journal.report_date_utc}, "
            f"candles={journal.candle_count}, regime={journal.dominant_regime}, "
            f"review_status={journal.review_status}, path={path}"
        )
        return 0

    if args.command == "build-dashboard":
        try:
            config = load_config(Path(args.config))
            path = save_review_dashboard(config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"build dashboard failed: {exc}")
            return 2

        print(f"build dashboard ok: path={path}")
        return 0

    if args.command == "serve-orchestrator":
        try:
            load_config(Path(args.config))
            serve_orchestrator(args.host, args.port, args.config)
        except (ConfigError, ValueError, OSError) as exc:
            print(f"serve orchestrator failed: {exc}")
            return 2
        return 0

    if args.command == "alert-daily-report":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            candles = CandleCsvStore(config.data_root).load(args.symbol, args.timeframe)
            journal = generate_daily_market_journal(candles)
            message = build_daily_report_alert(journal)
            path = AlertOutbox(config.data_root).write(message)
        except (ConfigError, ValueError) as exc:
            print(f"alert daily report failed: {exc}")
            return 2

        print(f"alert daily report ok: severity={message.severity}, path={path}")
        return 0

    if args.command == "alert-stop":
        try:
            config = load_config(Path(args.config))
            message = build_stop_alert(args.symbol, args.reason, args.equity)
            path = AlertOutbox(config.data_root).write(message)
        except (ConfigError, ValueError) as exc:
            print(f"alert stop failed: {exc}")
            return 2

        print(f"alert stop ok: severity={message.severity}, path={path}")
        return 0

    if args.command == "alert-error":
        try:
            config = load_config(Path(args.config))
            message = build_error_alert(args.component, args.error)
            path = AlertOutbox(config.data_root).write(message)
        except (ConfigError, ValueError) as exc:
            print(f"alert error failed: {exc}")
            return 2

        print(f"alert error ok: severity={message.severity}, path={path}")
        return 0

    if args.command == "sandbox-order":
        try:
            adapter = SandboxExchangeAdapter(args.environment)
            order = adapter.place_order(
                ExchangeOrderRequest(
                    symbol=args.symbol,
                    side=args.side,
                    order_type=args.order_type,
                    quantity=args.quantity,
                    price=args.price,
                )
            )
        except ValueError as exc:
            print(f"sandbox order failed: {exc}")
            return 2

        print(
            "sandbox order ok: "
            f"environment={args.environment}, order_id={order.order_id}, "
            f"status={order.status}, symbol={order.symbol}, side={order.side}, quantity={order.quantity}"
        )
        return 0

    if args.command == "run-cycle":
        try:
            config = load_config(Path(args.config))
            result = run_research_cycle(
                config,
                sync_latest=args.sync_latest,
                limit=args.limit,
                initial_equity=args.initial_equity,
                min_notional=args.min_notional,
            )
        except (ConfigError, ValueError) as exc:
            print(f"cycle failed: {exc}")
            return 2

        print(
            "cycle ok: "
            f"symbols={result.symbols_processed}, pairs={result.timeframes_processed}, "
            f"candles={result.candles_seen}, paper_trades={result.paper_trades}, "
            f"alerts={result.alerts_written}, dashboard_path={result.dashboard_path}"
        )
        return 0

    if args.command == "evaluate-session":
        try:
            config = load_config(Path(args.config))
            decision = is_entry_allowed_at_ms(args.open_time_ms, config.entry_windows_wib)
        except (ConfigError, ValueError) as exc:
            print(f"evaluate session failed: {exc}")
            return 2

        print(
            "session decision: "
            f"allowed={str(decision.allowed).lower()}, local_time={decision.local_time}, "
            f"reason={decision.reason}"
        )
        return 0 if decision.allowed else 2

    if args.command == "validate-security":
        try:
            env = load_env_file(args.env_file)
            report = validate_env_security(env)
            findings = scan_for_secrets(args.scan_root)
        except (FileNotFoundError, ValueError) as exc:
            print(f"security validation failed: {exc}")
            return 2

        print(
            "security validation: "
            f"env_ok={str(report.ok).lower()}, errors={len(report.errors)}, "
            f"warnings={len(report.warnings)}, secret_findings={len(findings)}"
        )
        for error in report.errors:
            print(f"error: {error}")
        for warning in report.warnings:
            print(f"warning: {warning}")
        for finding in findings[:20]:
            print(f"finding: {finding.path}:{finding.line_number}")
        return 0 if report.ok and not findings else 2

    if args.command == "security-qa-report":
        try:
            config = load_config(Path(args.config))
            report = generate_security_qa_report(args.env_file, args.scan_root)
            path = save_security_qa_report(report, config.data_root)
        except (ConfigError, FileNotFoundError, ValueError) as exc:
            print(f"security qa failed: {exc}")
            return 2

        print(
            "security qa: "
            f"status={report.status}, checks={len(report.checks)}, "
            f"secret_findings={len(report.secret_findings)}, warnings={len(report.warnings)}, path={path}"
        )
        for check in report.checks:
            print(f"{check.status} {check.name}: {check.reason}")
        for warning in report.warnings:
            print(f"warning: {warning}")
        for finding in report.secret_findings[:20]:
            print(f"finding: {finding.path}:{finding.line_number}")
        return 0 if report.status == "PASSED" else 2

    if args.command == "audit-summary":
        try:
            config = load_config(Path(args.config))
            events = read_audit_events(config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"audit summary failed: {exc}")
            return 2

        print(f"audit summary: events={len(events)}")
        for event in events[-args.limit :]:
            print(
                f"{event.created_at_utc} {event.level} {event.event}: "
                f"{event.message} {event.context}"
            )
        return 0

    if args.command == "live-readiness-report":
        try:
            config = load_config(Path(args.config))
            report = evaluate_live_readiness(
                config,
                env_file=args.env_file,
                scan_root=args.scan_root,
                min_paper_trades=args.min_paper_trades,
            )
            path = save_live_readiness_report(report, config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"live readiness failed: {exc}")
            return 2

        print(
            "live readiness: "
            f"status={report.status}, checks={len(report.checks)}, path={path}, summary={report.summary}"
        )
        for check in report.checks:
            print(f"{check.status} {check.name}: {check.reason}")
        return 0 if report.status == "READY_FOR_MANUAL_REVIEW" else 2

    if args.command == "live-phase-one-plan":
        try:
            config = load_config(Path(args.config))
            readiness_report = evaluate_live_readiness(
                config,
                env_file=args.env_file,
                scan_root=args.scan_root,
                min_paper_trades=args.min_paper_trades,
            )
            plan = build_live_phase_one_plan(
                readiness_report,
                LivePhaseOneConfig(capital_idr=args.capital_idr),
            )
        except (ConfigError, ValueError) as exc:
            print(f"live phase one plan failed: {exc}")
            return 2

        print(
            "live phase one plan: "
            f"status={plan.status}, capital_idr={plan.capital_idr:.2f}, "
            f"max_risk_per_trade_idr={plan.max_risk_per_trade_idr:.2f}, "
            f"daily_max_loss_idr={plan.daily_max_loss_idr:.2f}, "
            f"monthly_max_drawdown_idr={plan.monthly_max_drawdown_idr:.2f}, "
            f"max_open_positions={plan.max_open_positions}, reason={plan.reason}"
        )
        return 0 if plan.status == "READY_FOR_OWNER_APPROVAL" else 2

    if args.command == "live-go-no-go-report":
        try:
            config = load_config(Path(args.config))
            report = evaluate_live_go_no_go(config, owner_approved=args.owner_approved)
            path = save_live_go_no_go_report(report, config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"live go/no-go failed: {exc}")
            return 2

        print(
            "live go/no-go: "
            f"decision={report.decision}, items={len(report.items)}, path={path}, summary={report.summary}"
        )
        for item in report.items:
            print(f"{item.status} {item.name}: {item.reason}")
        return 0 if report.decision == "GO_FOR_OWNER_REVIEW" else 2

    if args.command == "vps-readiness-report":
        try:
            output_config = load_config(Path(args.output_config))
            report = evaluate_vps_readiness(args.config, args.service, args.timer, args.smoke)
            path = save_vps_readiness_report(report, output_config.data_root)
        except (ConfigError, FileNotFoundError, ValueError) as exc:
            print(f"vps readiness failed: {exc}")
            return 2

        print(
            "vps readiness: "
            f"status={report.status}, checks={len(report.checks)}, path={path}"
        )
        for check in report.checks:
            print(f"{check.status} {check.name}: {check.reason}")
        return 0 if report.status == "PASSED" else 2

    if args.command == "production-smoke-report":
        try:
            config = load_config(Path(args.config))
            report = evaluate_production_smoke(args.config, args.smoke, args.runbook)
            path = save_production_smoke_report(report, config.data_root)
        except (ConfigError, FileNotFoundError, ValueError) as exc:
            print(f"production smoke failed: {exc}")
            return 2

        print(
            "production smoke: "
            f"status={report.status}, checks={len(report.checks)}, path={path}"
        )
        for check in report.checks:
            print(f"{check.status} {check.name}: {check.reason}")
        return 0 if report.status == "PASSED" else 2

    if args.command == "post-trade-report":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            trades = load_paper_trades(config.data_root, args.symbol, args.timeframe)
            report = generate_post_trade_report(trades, args.symbol, args.timeframe)
            path = save_post_trade_report(report, config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"post-trade report failed: {exc}")
            return 2

        print(
            "post-trade report ok: "
            f"symbol={args.symbol}, timeframe={args.timeframe}, trades={report.summary.trade_count}, "
            f"win_rate_pct={report.summary.win_rate_pct:.2f}, "
            f"total_net_pnl={report.summary.total_net_pnl:.8f}, path={path}"
        )
        return 0

    if args.command == "paper-stability-report":
        try:
            config = load_config(Path(args.config))
            _ensure_requested_market(config, args.symbol, args.timeframe)
            report = evaluate_paper_stability(
                config.data_root,
                args.symbol,
                args.timeframe,
                PaperStabilityConfig(min_days=args.min_days, min_trades=args.min_trades),
            )
            path = save_paper_stability_report(report, config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"paper stability failed: {exc}")
            return 2

        print(
            "paper stability: "
            f"status={report.status}, observed_days={report.observed_days}, "
            f"trades={report.trade_count}, rejected_orders={report.rejected_order_count}, "
            f"stop_losses={report.stop_loss_count}, critical_errors={report.critical_error_count}, "
            f"path={path}"
        )
        for blocker in report.blockers:
            print(f"blocker: {blocker}")
        for warning in report.warnings:
            print(f"warning: {warning}")
        return 0 if report.status == "PAPER_STABLE" else 2

    if args.command == "risk-guard-drill":
        try:
            config = load_config(Path(args.config))
            if args.symbol not in config.symbols:
                raise ConfigError(f"symbol is not configured: {args.symbol}")
            report = run_risk_guard_drill(config.data_root, args.symbol)
            path = save_risk_guard_drill_report(report, config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"risk guard drill failed: {exc}")
            return 2

        print(
            "risk guard drill: "
            f"status={report.status}, checks={len(report.checks)}, path={path}"
        )
        for check in report.checks:
            print(f"{check.status} {check.name}: expected={check.expected}, actual={check.actual}")
        return 0 if report.status == "PASSED" else 2

    if args.command == "incident-drill-report":
        try:
            config = load_config(Path(args.config))
            if args.symbol not in config.symbols:
                raise ConfigError(f"symbol is not configured: {args.symbol}")
            report = run_incident_drill(config.data_root, args.symbol)
            path = save_incident_drill_report(report, config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"incident drill failed: {exc}")
            return 2

        print(
            "incident drill: "
            f"status={report.status}, scenarios={len(report.scenarios)}, path={path}"
        )
        for scenario in report.scenarios:
            print(
                f"{scenario.status} {scenario.name}: "
                f"audit={scenario.audit_event}, alert={scenario.alert_kind}, response={scenario.safe_response}"
            )
        return 0 if report.status == "PASSED" else 2

    if args.command == "gold-research-plan":
        plan = build_gold_research_plan()
        print(
            "gold research plan: "
            f"status={plan.status}, instrument={plan.instrument}, allowed_mode={plan.allowed_mode}"
        )
        for blocker in plan.blockers:
            print(f"blocker: {blocker}")
        for evidence in plan.required_evidence:
            print(f"required: {evidence}")
        return 0

    if args.command == "evaluate-ai-recommendation":
        decision = evaluate_ai_recommendation(
            AiRecommendation(
                action=args.action,
                title=args.title,
                rationale=args.rationale,
                proposed_change=args.proposed_change,
            )
        )
        print(f"ai guardrail: status={decision.status}, reason={decision.reason}")
        return 0 if decision.status == "ACCEPTED_FOR_RESEARCH" else 2

    if args.command == "kill-switch":
        try:
            config = load_config(Path(args.config))
            if args.action == "activate":
                path = activate_kill_switch(config.data_root, args.reason)
                print(f"kill switch activated: path={path}, reason={args.reason}")
                return 0
            if args.action == "clear":
                clear_kill_switch(config.data_root)
                print("kill switch cleared")
                return 0
            state = read_kill_switch(config.data_root)
        except (ConfigError, ValueError) as exc:
            print(f"kill switch failed: {exc}")
            return 2

        print(
            "kill switch status: "
            f"active={str(state.active).lower()}, reason={state.reason}, "
            f"created_at_utc={state.created_at_utc or ''}"
        )
        return 2 if state.active else 0

    if args.command == "capture-market-context":
        try:
            config = load_config(Path(args.config))
            if args.symbol not in config.symbols:
                raise ConfigError(f"symbol is not configured: {args.symbol}")
            collector = MarketDataCollector(
                store=CandleCsvStore(config.data_root),
                client=BinancePublicKlineClient(),
                context_store=MarketContextCsvStore(config.data_root),
            )
            metadata, ticker, order_book = collector.capture_market_context(args.symbol)
        except (ConfigError, ValueError) as exc:
            print(f"market context failed: {exc}")
            return 2

        print(
            "market context ok: "
            f"symbol={metadata.symbol}, min_notional={metadata.min_notional}, "
            f"spread_pct={ticker.spread_pct:.6f}, "
            f"imbalance={order_book.imbalance_ratio:.6f}"
        )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _ensure_requested_market(config, symbol: str, timeframe: str) -> None:
    if symbol not in config.symbols:
        raise ConfigError(f"symbol is not configured: {symbol}")
    if timeframe not in config.timeframes:
        raise ConfigError(f"timeframe is not configured: {timeframe}")


if __name__ == "__main__":
    raise SystemExit(main())
