# Trading Research Bot

Bot ini dibangun sebagai research system terlebih dahulu, bukan live trading bot.
Fokus awalnya adalah BTC/USDT dan ETH/USDT spot, dengan data capture, backtest,
paper trading, risk manager, dan review harian sebelum live kecil dipertimbangkan.

## Demo Ready Quick Start

Status saat ini: ready to use untuk demo/paper account. Real live money tetap
terkunci sampai evidence paper cukup dan owner approval dilakukan manual.

Cara paling gampang di laptop:

1. Double-click `start-bot-web.cmd`.
2. Buka `http://127.0.0.1:8000/`.
3. Ikuti panel `Demo Walkthrough`.
4. Pantau naik-turun profit/loss di panel `P/L Visual Monitor`.
5. Jika halaman mati atau `refused to connect`, double-click `start-bot-watchdog.cmd`.

Panel penting untuk user awam:

- `Control Room Awam`: ringkasan status aman/tidak aman.
- `P/L Visual Monitor`: equity curve, win rate, trade count, dan net P/L demo.
- `Fundamental/Event Lane`: warna risiko news/macro/exchange.
- `Experiment Scoreboard`: daftar eksperimen strategi yang boleh lanjut paper review.
- `Human Feedback`: label manual dari review chart/trade untuk melatih lesson bot.
- `Live Evidence Gate`: bukti sebelum live; status live real tetap no-go sampai lengkap.

Release check terakhir:

- UAT: `UAT_READY_FOR_DEMO`, completion `100%`, bugs `0`.
- Local demo: `READY_FOR_LOCAL_DEMO`.
- Test suite: `244 unittest OK`.
- Safety: `live_enabled=false`, `approved_live=false`.

## Operating Principle

- Default mode: `research`.
- Live trading: disabled by default.
- Instrument v1: BTC/USDT and ETH/USDT spot only.
- No leverage, no futures, no margin, no altcoin kecil.
- Learning engine may recommend experiments, but must not change live strategy.

## Project Layout

- `docs/`: risk policy, market decision, runbook notes.
- `config/`: sample config and operating profile.
- `trading_bot/`: Python package skeleton.
- `tests/`: basic safety tests.

## First Milestone

1. Lock risk policy and no-live guard.
2. Lock BTC/ETH spot as initial research market.
3. Build data collector and feature engine.
4. Backtest conservative strategies.
5. Run paper trading before any live path.

## Useful Commands

```bash
python -m trading_bot.cli validate-config --config config/bot.sample.toml
python -m trading_bot.cli sync-ohlcv --symbol BTC/USDT --timeframe 15m --limit 500
python -m trading_bot.cli data-quality-gate --symbol BTC/USDT --timeframe 15m
python -m trading_bot.cli run-backtest --symbol BTC/USDT --timeframe 15m --initial-equity 1000
python -m trading_bot.cli backtest-report --symbol BTC/USDT --timeframe 15m --initial-equity 1000
python -m trading_bot.cli run-paper --symbol BTC/USDT --timeframe 15m --initial-equity 1000
python -m trading_bot.cli daily-journal --symbol BTC/USDT --timeframe 15m --initial-equity 1000
python -m trading_bot.cli build-dashboard
python -m trading_bot.cli serve-orchestrator --config config/bot.sample.toml --host 127.0.0.1 --port 8000
python -m trading_bot.cli init-db --config config/bot.sample.toml
python -m trading_bot.cli import-runtime-db --config config/bot.sample.toml
python -m trading_bot.cli alert-daily-report --symbol BTC/USDT --timeframe 15m
python -m trading_bot.cli alert-stop --symbol BTC/USDT --reason "daily target reached" --equity 1010
python -m trading_bot.cli sandbox-order --environment sandbox --symbol BTC/USDT --side buy --order-type market --quantity 0.001
python -m trading_bot.cli run-cycle --config config/bot.sample.toml --limit 10
python -m trading_bot.cli evaluate-session --open-time-ms 1782700200000
python -m trading_bot.cli validate-security --env-file .env.example --scan-root .
python -m trading_bot.cli security-qa-report --config config/bot.sample.toml --env-file .env.example --scan-root .
python -m trading_bot.cli vps-readiness-report --config config/bot.vps.sample.toml
python -m trading_bot.cli production-smoke-report --config config/bot.sample.toml
python -m trading_bot.cli audit-summary --config config/bot.sample.toml --limit 10
python -m trading_bot.cli build-research-dataset --symbol BTC/USDT --timeframe 15m --horizon-candles 12
python -m trading_bot.cli walk-forward-report --symbol BTC/USDT --timeframe 15m
python -m trading_bot.cli paper-stability-report --symbol BTC/USDT --timeframe 15m --min-days 14 --min-trades 20
python -m trading_bot.cli risk-guard-drill --config config/bot.sample.toml --symbol BTC/USDT
python -m trading_bot.cli incident-drill-report --config config/bot.sample.toml --symbol BTC/USDT
python -m trading_bot.cli live-readiness-report --config config/bot.sample.toml --env-file .env.example --scan-root .
python -m trading_bot.cli live-phase-one-plan --config config/bot.sample.toml --capital-idr 1000000
python -m trading_bot.cli live-go-no-go-report --config config/bot.sample.toml
python -m trading_bot.cli post-trade-report --symbol BTC/USDT --timeframe 15m
python -m trading_bot.cli gold-research-plan
python -m trading_bot.cli evaluate-ai-recommendation --action experiment_proposal --title "Tighten RSI filter" --rationale "Losses cluster when RSI is weak" --proposed-change "Test min RSI 50"
python -m trading_bot.cli kill-switch --action status
```

Paper mode writes virtual orders, trades, and account snapshots under
`work/market_data/paper`. It is intentionally disconnected from exchange order APIs.
Daily journal writes market research summaries under `work/market_data/reports/daily`.
The dashboard MVP writes a local HTML review page under `work/market_data/dashboard`.
The local web orchestrator runs at `http://127.0.0.1:8000` when started.
SQLite archive storage writes to `work/market_data/bot.sqlite3` for local
research history.
Alerting writes local JSON messages under `work/market_data/alerts/outbox` until
Telegram/email credentials are configured in a later secure adapter.
Execution v1 only exposes sandbox/testnet adapters; live order routing is not enabled.
VPS deployment assets live under `deploy/`, with the runbook in `docs/vps-deployment.md`.
Session rules use Asia/Jakarta entry windows from config; data collection can still run 24/7.
Security policy lives in `docs/security-policy.md`; live credentials remain blocked in v1.
Structured audit logs are written to `work/market_data/logs/audit.jsonl`.
Research pattern outcome datasets are written to `work/market_data/research/pattern_outcomes`.
Walk-forward validation reports are written to `work/market_data/validation/walk_forward`.
Paper stability QA reports are written to `work/market_data/qa/paper_stability`; `BLOCKED` is expected until 2-4 week demo evidence exists.
Risk guard drill reports are written to `work/market_data/qa/risk_guard_drill`.
Incident drill reports are written to `work/market_data/qa/incident_drill`.
Data quality gate reports are written to `work/market_data/qa/data_quality_gate`.
Security QA reports are written to `work/market_data/qa/security`.
VPS readiness reports are written to `work/market_data/qa/vps_readiness`.
Production smoke reports are written to `work/market_data/qa/production_smoke`.
Live readiness reports are written to `work/market_data/readiness`; `BLOCKED` is expected until evidence is complete.
Live phase one planning is guard-only in v1; it calculates limits and stays blocked until readiness passes.
Live go/no-go reports are written to `work/market_data/qa/live_go_no_go`.
Post-trade reports are written to `work/market_data/post_trade`.
Gold/XAUUSD is research-only and blocked from v1 live readiness.
AI/ML guardrails are documented in `docs/ai-ml-guardrails.md`; AI outputs remain research-only.
Disaster recovery and kill switch steps are documented in `docs/disaster-recovery.md`.
QA test matrix is documented in `docs/test-matrix.md`.
Backtest QA policy is documented in `docs/backtest-qa.md`.
Paper trading QA policy is documented in `docs/paper-trading-qa.md`.
Risk guard QA policy is documented in `docs/risk-guard-qa.md`.
Incident drill QA policy is documented in `docs/incident-drill-qa.md`.
Data quality QA policy is documented in `docs/data-quality-qa.md`.
Security QA policy is documented in `docs/security-qa.md`.
VPS readiness QA policy is documented in `docs/vps-readiness-qa.md`.
Production smoke and rollback policy is documented in `docs/production-smoke-rollback.md`.
Live go/no-go policy is documented in `docs/live-go-no-go.md`.
UX architecture decision is documented in `docs/ux-architecture-decision.md`.
Local web orchestrator usage is documented in `docs/local-web-orchestrator.md`.
SQLite archive storage is documented in `docs/database-storage.md`.
