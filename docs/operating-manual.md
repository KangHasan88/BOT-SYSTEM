# Trading Bot Operating Manual

Bot ini masih safety-first research system. Live trading tidak aktif.

## Quick Status

```bash
python -m trading_bot.cli validate-config --config config/bot.sample.toml
python -m trading_bot.cli validate-security --env-file .env.example --scan-root .
python -m trading_bot.cli security-qa-report --config config/bot.sample.toml --env-file .env.example --scan-root .
python -m trading_bot.cli audit-summary --config config/bot.sample.toml --limit 10
python -m trading_bot.cli kill-switch --action status
python -m trading_bot.cli risk-guard-drill --config config/bot.sample.toml --symbol BTC/USDT
```

## Local Dashboard

UX direction: `docs/ux-architecture-decision.md`
Local web orchestrator: `docs/local-web-orchestrator.md`
Database storage lokal: `docs/database-storage.md`
Gated live demo pack: `docs/live-demo-gated-pack.md`

Start local web orchestrator:

```powershell
cd C:\Users\IT-MGR\Documents\Codex\2026-06-28\bro-2
& 'C:\Users\IT-MGR\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m trading_bot.cli serve-orchestrator --config config/bot.sample.toml --host 127.0.0.1 --port 8000
```

Cara paling gampang:

```powershell
.\start-bot-web.cmd
```

Jika browser `127.0.0.1:8000` refused, jalankan watchdog:

```powershell
.\start-bot-watchdog.cmd
```

Watchdog hanya menjaga web demo/paper tetap hidup. Tidak ada order live dari
helper ini.

Dashboard lokal:

`work/market_data/dashboard/index.html`

Build ulang dashboard:

```bash
python -m trading_bot.cli build-dashboard
```

Init/import database lokal:

```bash
python -m trading_bot.cli seed-demo-data --config config/bot.sample.toml
python -m trading_bot.cli local-demo-report --config config/bot.sample.toml --seed-demo-if-needed
python -m trading_bot.cli vps-demo-report --config config/bot.sample.toml
python -m trading_bot.cli init-db --config config/bot.sample.toml
python -m trading_bot.cli import-runtime-db --config config/bot.sample.toml
python -m trading_bot.cli db-status --config config/bot.sample.toml
python -m trading_bot.cli db-learning-report --config config/bot.sample.toml
python -m trading_bot.cli skill-loop-report --config config/bot.sample.toml
python -m trading_bot.cli pattern-memory-report --config config/bot.sample.toml
python -m trading_bot.cli learning-dashboard-report --config config/bot.sample.toml
python -m trading_bot.cli add-feedback-label --config config/bot.sample.toml --symbol BTC/USDT --timeframe 15m --label entry_telat --note "entry terlalu jauh dari trigger"
python -m trading_bot.cli human-feedback-report --config config/bot.sample.toml
python -m trading_bot.cli add-fundamental-event --config config/bot.sample.toml --symbol BTC/USDT --category macro --risk HIGH --title "US CPI release window" --note "pause entry baru dekat event"
python -m trading_bot.cli fundamental-report --config config/bot.sample.toml
python -m trading_bot.cli add-strategy-experiment --config config/bot.sample.toml --strategy-id volume_spike_retest --version v1 --hypothesis "volume spike after sweep improves entry timing" --status PAPER --backtest-score 30 --paper-score 25 --evidence-score 20 --risk-score 5
python -m trading_bot.cli experiment-scoreboard --config config/bot.sample.toml
python -m trading_bot.cli uat-report --config config/bot.sample.toml
```

## Data Collection

Sync latest public candles:

```bash
python -m trading_bot.cli sync-ohlcv --symbol BTC/USDT --timeframe 15m --limit 500
python -m trading_bot.cli sync-ohlcv --symbol ETH/USDT --timeframe 15m --limit 500
```

Audit data:

```bash
python -m trading_bot.cli quality-report --symbol BTC/USDT --timeframe 15m
python -m trading_bot.cli data-quality-gate --symbol BTC/USDT --timeframe 15m
```

Data quality gate blocks research use when candles have gaps, duplicates, stale
feed, malformed OHLC, or bad prices.

## Research Cycle

Run full offline-safe cycle:

```bash
python -m trading_bot.cli run-cycle --config config/bot.sample.toml --limit 10
```

Run with latest market sync:

```bash
python -m trading_bot.cli run-cycle --config config/bot.sample.toml --sync-latest --limit 500
```

Cycle writes:

- quality reports;
- features, regimes, patterns, signals;
- paper trading output;
- post-trade report;
- daily journal;
- walk-forward report;
- dashboard;
- alert outbox;
- audit log.

## Backtest And Validation

```bash
python -m trading_bot.cli run-backtest --symbol BTC/USDT --timeframe 15m --initial-equity 1000
python -m trading_bot.cli backtest-report --symbol BTC/USDT --timeframe 15m --initial-equity 1000
python -m trading_bot.cli walk-forward-report --symbol BTC/USDT --timeframe 15m
```

## Paper Trading Review

```bash
python -m trading_bot.cli run-paper --symbol BTC/USDT --timeframe 15m --initial-equity 1000
python -m trading_bot.cli post-trade-report --symbol BTC/USDT --timeframe 15m
python -m trading_bot.cli paper-campaign-report --config config/bot.sample.toml --min-days 14 --preferred-days 28 --min-trades 20
python -m trading_bot.cli paper-stability-report --symbol BTC/USDT --timeframe 15m --min-days 14 --min-trades 20
python -m trading_bot.cli daily-journal --symbol BTC/USDT --timeframe 15m --initial-equity 1000
```

Paper stability should stay `BLOCKED` until 14-28 days of demo evidence and at
least 20 completed paper trades are available.

## Readiness And Live Guard

Live readiness should stay `BLOCKED` until evidence is complete.

```bash
python -m trading_bot.cli live-readiness-report --config config/bot.sample.toml --env-file .env.example --scan-root .
python -m trading_bot.cli live-evidence-report --config config/bot.sample.toml --min-paper-trades 20
python -m trading_bot.cli evidence-campaign-report --config config/bot.sample.toml --seed-demo-if-needed
python -m trading_bot.cli live-phase-one-plan --config config/bot.sample.toml --capital-idr 1000000
python -m trading_bot.cli live-go-no-go-report --config config/bot.sample.toml
```

Live phase one is only a plan in v1. It does not route live orders.
`live-evidence-report` is expected to stay `INCOMPLETE` until paper evidence and
owner-review evidence are complete.
`evidence-campaign-report` refreshes local demo/paper evidence without opening
real live execution.

Demo account / testnet flow:

```bash
python -m trading_bot.cli testnet-demo-report --config config/bot.sample.toml --environment testnet
python -m trading_bot.cli sandbox-order --environment sandbox --symbol BTC/USDT --side buy --order-type market --quantity 0.001
```

## Kill Switch

```bash
python -m trading_bot.cli kill-switch --action status
python -m trading_bot.cli kill-switch --action activate --reason "manual safe shutdown"
python -m trading_bot.cli kill-switch --action clear
python -m trading_bot.cli incident-drill-report --config config/bot.sample.toml --symbol BTC/USDT
```

When active, `run-cycle` stops before processing market pairs and logs
`cycle_blocked`.

Risk guard drill verifies daily stop, monthly drawdown, profit lock, position
lock, and kill switch behavior without touching the real kill switch state.

## VPS

Read: `docs/vps-deployment.md`
Private VPS demo access: `docs/private-vps-demo-access.md`

Smoke:

```bash
APP_DIR=/opt/trading-bot CONFIG_PATH=/etc/trading-bot/bot.toml bash deploy/smoke-vps.sh
python -m trading_bot.cli vps-readiness-report --config config/bot.vps.sample.toml
python -m trading_bot.cli production-smoke-report --config config/bot.sample.toml
```

Systemd:

```bash
systemctl status trading-bot-cycle.timer
journalctl -u trading-bot-cycle.service -n 80 --no-pager
```

Private web tunnel from laptop:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-vps-demo-tunnel.ps1 -SshUser tradingbot -SshHost 31.97.106.123 -LocalPort 18000 -RemotePort 8000
```

## Security

Read: `docs/security-policy.md`

Rules:

- no withdrawal permission;
- no live key in repo;
- public data works without private key;
- live config blocked until readiness passes and owner manually approves.

## Research Extensions

- Continuous skill roadmap: `docs/continuous-skill-roadmap.md`
- Gold/XAUUSD: `python -m trading_bot.cli gold-research-plan`
- AI/ML guardrails: `docs/ai-ml-guardrails.md`
- Pattern dataset: `python -m trading_bot.cli build-research-dataset --symbol BTC/USDT --timeframe 15m`

## Test Suite

```bash
python -m unittest discover tests "*_unittest.py"
```

Test matrix: `docs/test-matrix.md`
