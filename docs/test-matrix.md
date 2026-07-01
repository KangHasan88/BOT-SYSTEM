# QA1 Test Matrix

This matrix defines the minimum automated and manual QA coverage before the bot
can move from research into sustained paper trading or any future live review.

## Standard Commands

```bash
python -m unittest discover tests "*_unittest.py"
python -m trading_bot.cli validate-config --config config/bot.sample.toml
python -m trading_bot.cli validate-security --env-file .env.example --scan-root .
python -m trading_bot.cli security-qa-report --config config/bot.sample.toml --env-file .env.example --scan-root .
python -m trading_bot.cli run-cycle --config config/bot.sample.toml --limit 10
python -m trading_bot.cli data-quality-gate --config config/bot.sample.toml --symbol BTC/USDT --timeframe 15m
python -m trading_bot.cli paper-stability-report --config config/bot.sample.toml --symbol BTC/USDT --timeframe 15m --min-days 14 --min-trades 20
python -m trading_bot.cli risk-guard-drill --config config/bot.sample.toml --symbol BTC/USDT
python -m trading_bot.cli incident-drill-report --config config/bot.sample.toml --symbol BTC/USDT
python -m trading_bot.cli vps-readiness-report --config config/bot.vps.sample.toml
python -m trading_bot.cli production-smoke-report --config config/bot.sample.toml
python -m trading_bot.cli live-readiness-report --config config/bot.sample.toml --env-file .env.example --scan-root .
python -m trading_bot.cli live-go-no-go-report --config config/bot.sample.toml
```

`paper-stability-report` and `live-readiness-report` are expected to stay
`BLOCKED` until enough paper evidence is complete.

## Release Threshold

- Full unit/regression suite must pass.
- Config guard must pass.
- Security guard must pass with zero secret findings.
- Offline-safe cycle must complete without crashing.
- Live readiness must not accidentally become ready without manual evidence.
- Kill switch status must be known before running any scheduled cycle.

## Module Matrix

| Module | Test File | Test Type | Critical Guard |
| --- | --- | --- | --- |
| Config safety | `tests/test_config_guard_unittest.py` | unit | Reject unsafe live mode, unknown symbols, invalid market config |
| Data collector | `tests/test_data_collector_unittest.py` | unit | Dedup candles and preserve ordered storage |
| Market context | `tests/test_market_context_unittest.py` | unit | Validate symbol metadata, spread, order book context |
| Data quality | `tests/test_quality_report_unittest.py` | unit | Detect gaps, duplicates, bad/zero data |
| Data quality gate | `tests/test_data_quality_gate_unittest.py` | integration | Block gap, duplicate, stale feed, bad price, malformed candle |
| Feature engine | `tests/test_feature_engine_unittest.py` | unit | Build indicators without malformed rows |
| Pattern analyzer | `tests/test_pattern_analyzer_unittest.py` | unit | Detect sweeps/false breakouts deterministically |
| Regime classifier | `tests/test_regime_classifier_unittest.py` | unit | Classify market regime from features |
| Signal engine | `tests/test_signal_engine_unittest.py` | unit | Produce BUY/EXIT/SKIP with reasons |
| Risk manager | `tests/test_risk_manager_unittest.py` | unit | Reject invalid size, tight/wide stops, daily/monthly limit |
| Profit lock | `tests/test_profit_lock_unittest.py` | unit | Stop after daily target/floor and lock position profit |
| Risk guard drill | `tests/test_risk_guard_drill_unittest.py` | integration | Verify daily stop, monthly DD, profit lock, position lock, kill switch |
| Backtest engine | `tests/test_backtest_engine_unittest.py` | integration | Include fee/slippage and close positions safely |
| Backtest metrics | `tests/test_backtest_metrics_unittest.py` | unit | Reject weak metrics and small sample |
| Paper simulator | `tests/test_paper_simulator_unittest.py` | integration | Paper-only orders, risk rejects, journal export |
| Paper stability QA | `tests/test_paper_stability_unittest.py` | integration | Block live review until 2-4 week paper evidence is stable |
| Paper campaign | `tests/test_paper_campaign_unittest.py` | integration | Aggregate 2-4 week paper evidence before live review |
| Daily journal | `tests/test_daily_journal_unittest.py` | integration | Summarize regime, pattern, paper result, review status |
| Dashboard | `tests/test_dashboard_unittest.py` | unit | Render dashboard safely and escape report text |
| Local orchestrator | `tests/test_orchestrator_unittest.py` | unit | Render safe local web UI and block live order actions |
| Alerting | `tests/test_alerts_unittest.py` | unit | Build stop/error/daily report alert outbox |
| Execution sandbox | `tests/test_execution_sandbox_unittest.py` | unit | Sandbox/testnet only, reject live environment |
| VPS deployment | `tests/test_vps_deployment_unittest.py` | static QA | Service uses non-root user and live remains disabled |
| VPS readiness | `tests/test_vps_readiness_unittest.py` | static QA | Gate service hardening, timer behavior, smoke script, monitoring |
| Private VPS demo access | `tests/test_private_vps_access_unittest.py` | static QA | Web orchestrator binds to localhost and uses SSH tunnel only |
| Private VPS demo readiness | `tests/test_vps_demo_unittest.py` | unit | Gate VPS paper demo evidence, private access, and live lock |
| Production smoke | `tests/test_production_smoke_unittest.py` | static QA | Gate smoke script, rollback plan, QA evidence reports |
| Scheduler | `tests/test_scheduler_unittest.py` | unit | Enforce WIB entry windows |
| Security | `tests/test_security_unittest.py` | unit | Reject withdrawal permission, live mode, leaked secret |
| Security QA | `tests/test_security_qa_unittest.py` | integration | Report env guard, secret scan, live block, withdrawal disabled |
| Observability | `tests/test_observability_unittest.py` | integration | Write/read audit events and cycle activity |
| Research dataset | `tests/test_research_dataset_unittest.py` | unit | Label pattern outcome and export dataset |
| Walk-forward | `tests/test_walk_forward_unittest.py` | integration | Split train/test and gate out-of-sample results |
| Live readiness | `tests/test_live_readiness_unittest.py` | unit | Block live when evidence is missing |
| Live go/no-go | `tests/test_live_go_no_go_unittest.py` | integration | Aggregate QA evidence and owner approval before live review |
| Live phase one | `tests/test_live_phase_one_unittest.py` | unit | Plan small capital only, reject aggressive risk |
| Gold research | `tests/test_gold_research_unittest.py` | unit | Keep XAUUSD research-only |
| AI guardrails | `tests/test_ai_guardrails_unittest.py` | unit | Block direct order/risk bypass recommendations |
| Continuous skill roadmap | `tests/test_continuous_skill_roadmap_unittest.py` | static QA | Require learning loop, promotion rules, and no auto-live guardrail |
| Kill switch | `tests/test_kill_switch_unittest.py` | integration | Block cycle while kill switch is active |
| Incident drill | `tests/test_incident_drill_unittest.py` | integration | Verify exchange API down, network down, bot crash safe response |
| Post-trade analysis | `tests/test_post_trade_unittest.py` | unit | Summarize PnL, exit reason, best/worst hour |
| Operating manual | `tests/test_operating_manual_unittest.py` | static QA | Manual contains critical operations |

## Manual QA Checklist

- Verify dashboard opens from `work/market_data/dashboard/index.html`.
- Verify local web orchestrator opens at `http://127.0.0.1:8000`.
- Verify kill switch drill: activate, run cycle, confirm zero pairs processed, clear.
- Verify data quality gate passes or intentionally blocks before reading signals.
- Verify readiness remains `BLOCKED` without paper/backtest evidence.
- Verify paper stability remains `BLOCKED` until 14+ days and 20+ paper trades exist.
- Verify risk guard drill returns `PASSED` before any production scheduler review.
- Verify incident drill returns `PASSED` before production smoke testing.
- Verify no live exchange key is required for public data collection.
- Verify security QA report is `PASSED` before VPS production readiness.
- Verify VPS readiness report is `PASSED` before enabling timer on server.
- Verify live go/no-go remains `NO_GO` until owner approval and evidence are complete.
- Verify production smoke report is `PASSED` before enabling or re-enabling VPS timer.
- Verify all generated reports can be found from the operating manual.

## Future QA Expansion

- Add deeper no-lookahead audit for feature and signal generation internals.
- Add stale-data guard tests.
- Add VPS service smoke test after actual deployment.
- Add local web orchestrator UI tests after UX work starts.
