# QA10 Production Smoke & Rollback

Production smoke verifies that the VPS phase can be checked and rolled back
without enabling live trading.

## Command

```bash
python -m trading_bot.cli production-smoke-report --config config/bot.sample.toml
```

The report is saved at:

```text
work/market_data/qa/production_smoke/report.json
```

## Required Checks

- config remains non-live;
- smoke script validates config, runs cycle, and builds dashboard;
- rollback disables timer and stops service;
- rollback preserves logs and restores config/data from backups;
- security QA, risk guard, VPS readiness, incident drill, and live go/no-go
  reports are readable.

## Rollback

The rollback procedure lives in `docs/vps-deployment.md`. The first action is
always to disable the timer before touching config or data:

```bash
sudo systemctl disable --now trading-bot-cycle.timer
sudo systemctl stop trading-bot-cycle.service
```

Production smoke must be `PASSED` before enabling the timer again.
