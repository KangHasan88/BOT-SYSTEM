# VPS Deployment Runbook

Target awal VPS adalah menjalankan data collector dan paper bot otomatis.
Live trading tetap disabled.

## Paths

- App: `/opt/trading-bot`
- Config: `/etc/trading-bot/bot.toml`
- Env: `/etc/trading-bot/trading-bot.env`
- Data: `/var/lib/trading-bot/data`
- Logs: journalctl unit `trading-bot-cycle.service`
- Private web: `trading-bot-orchestrator.service` bound to `127.0.0.1:8000`

## Install Outline

```bash
sudo useradd --system --create-home --home-dir /var/lib/trading-bot tradingbot
sudo mkdir -p /opt/trading-bot /etc/trading-bot /var/lib/trading-bot/data /var/log/trading-bot
sudo chown -R tradingbot:tradingbot /opt/trading-bot /var/lib/trading-bot /var/log/trading-bot
sudo cp config/bot.vps.sample.toml /etc/trading-bot/bot.toml
sudo cp deploy/trading-bot.env.example /etc/trading-bot/trading-bot.env
sudo cp deploy/systemd/trading-bot-cycle.* /etc/systemd/system/
sudo cp deploy/systemd/trading-bot-orchestrator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot-cycle.timer
```

## Smoke Check

```bash
APP_DIR=/opt/trading-bot CONFIG_PATH=/etc/trading-bot/bot.toml bash deploy/smoke-vps.sh
python -m trading_bot.cli vps-readiness-report --config config/bot.vps.sample.toml
systemctl status trading-bot-cycle.timer
journalctl -u trading-bot-cycle.service -n 80 --no-pager
```

## Private Web Demo

Read: `docs/private-vps-demo-access.md`

The VPS web orchestrator must bind to `127.0.0.1:8000` and be accessed from the
laptop via SSH tunnel or VPN. Do not expose this dashboard as a public website.

## Safety Gates

- `live_enabled` must stay `false`.
- API key is not required for v1 public data capture.
- Withdrawal permission must stay disabled for any future key.
- First VPS phase only runs research, paper trading, reports, dashboard, and alert outbox.

QA7 readiness details live in `docs/vps-readiness-qa.md`.

## Rollback Plan

If production smoke fails or the timer behaves unexpectedly:

```bash
sudo systemctl disable --now trading-bot-cycle.timer
sudo systemctl stop trading-bot-cycle.service
sudo journalctl -u trading-bot-cycle.service -n 120 --no-pager
sudo cp /etc/trading-bot/bot.toml.bak /etc/trading-bot/bot.toml
sudo rsync -a /var/lib/trading-bot/data.bak/ /var/lib/trading-bot/data/
sudo systemctl daemon-reload
```

Rollback rules:

- disable timer before changing config or data;
- preserve journal logs before cleanup;
- restore config before restarting service;
- restore data only from a known backup path;
- rerun `vps-readiness-report` and `production-smoke-report` before enabling timer again.
