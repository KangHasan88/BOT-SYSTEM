# QA7 VPS Production Readiness

VPS readiness verifies that the bot can run automatically as a paper/research
service without opening live execution risk.

## Command

```bash
python -m trading_bot.cli vps-readiness-report --config config/bot.vps.sample.toml
```

The report is saved at:

```text
work/market_data/qa/vps_readiness/report.json
```

## Required Checks

- VPS config is paper-only and live disabled.
- Data root is `/var/lib/trading-bot/data`.
- systemd service runs as `tradingbot`, not root.
- systemd hardening is present:
  - `NoNewPrivileges=true`
  - `PrivateTmp=true`
  - `ProtectSystem=strict`
  - `ProtectHome=true`
  - `ReadWritePaths=/var/lib/trading-bot /var/log/trading-bot`
- service command runs `run-cycle --sync-latest` and never live execution.
- timer starts after boot, runs every 15 minutes, and is persistent.
- smoke script validates config, runs a short cycle, and builds dashboard.
- runbook includes `systemctl status` and `journalctl` monitoring commands.

## Pass Rule

The report must be `PASSED` before enabling a VPS timer in production. A failed
check blocks deployment until fixed.
