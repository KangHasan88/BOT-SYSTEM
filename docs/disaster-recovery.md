# Disaster Recovery, Kill Switch & Safe Shutdown

Kill switch v1 memakai file lokal di data root:

`work/market_data/safety/kill_switch.json`

Jika file aktif, `run-cycle` berhenti sebelum memproses market pair.

## Commands

```bash
python -m trading_bot.cli kill-switch --action status
python -m trading_bot.cli kill-switch --action activate --reason "manual drill"
python -m trading_bot.cli kill-switch --action clear
python -m trading_bot.cli incident-drill-report --config config/bot.sample.toml --symbol BTC/USDT
```

## Safe Shutdown Rules

- Bot tidak boleh membuka entry baru saat kill switch aktif.
- Cycle tetap boleh membuat dashboard agar status bisa dilihat.
- Audit log harus mencatat `cycle_blocked`.
- Clearing kill switch hanya boleh dilakukan setelah penyebab insiden dicatat.
- Incident drill harus `PASSED` sebelum production smoke test.

QA8 incident drill detail: `docs/incident-drill-qa.md`.
