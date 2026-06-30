# Security Policy

Bot v1 tidak boleh memakai live trading key.

## API Key Rules

- Public market data tidak membutuhkan private key.
- Testnet key harus dipisah dari live key.
- Live key belum boleh dipakai sampai go/no-go production checklist lulus.
- Withdrawal permission wajib disabled.
- Jika exchange mendukung IP whitelist, wajib aktif sebelum live kecil.
- Secret tidak boleh ditulis ke repo, config TOML, README, atau Kanban.

## Local Checks

```bash
python -m trading_bot.cli validate-security --env-file .env.example --scan-root .
python -m trading_bot.cli security-qa-report --config config/bot.sample.toml --env-file .env.example --scan-root .
```

Security validator mengecek:

- `BOT_LIVE_ENABLED=false`
- `BOT_APPROVED_LIVE=false`
- `API_WITHDRAWAL_PERMISSION=false`
- API key dan secret tidak timpang
- repo tidak punya assignment secret mentah yang terlihat seperti credential asli

Security QA report disimpan ke `work/market_data/qa/security/report.json` dan
didokumentasikan di `docs/security-qa.md`.
