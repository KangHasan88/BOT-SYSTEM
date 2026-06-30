# Live Readiness Gate

Live readiness gate adalah pengaman sebelum bot boleh masuk fase live kecil.
Gate ini tidak menyalakan live trading. Gate hanya membuat laporan apakah evidence
sudah cukup untuk review manual.

## Required Evidence

- Config masih konservatif dan `live_enabled=false`.
- Security guard lulus: withdrawal disabled, no live env, no secret leak.
- Backtest metrics berstatus `PAPER_CANDIDATE`.
- Walk-forward validation berstatus `PAPER_CANDIDATE`.
- Paper trading punya sample trade yang cukup.
- Kill switch drill sudah dicatat.
- Owner approval dicatat manual.

## Command

```bash
python -m trading_bot.cli live-readiness-report --config config/bot.sample.toml --env-file .env.example --scan-root .
python -m trading_bot.cli live-go-no-go-report --config config/bot.sample.toml
```

Expected status selama fase research/paper adalah `BLOCKED`.
Status `READY_FOR_MANUAL_REVIEW` hanya berarti evidence otomatis sudah lengkap,
bukan izin live otomatis.

Final QA9 go/no-go checklist didokumentasikan di `docs/live-go-no-go.md`.
