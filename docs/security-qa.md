# QA6 Security QA Report

Security QA verifies that the bot remains research/paper-first and that no live
credential risk is present before production readiness work continues.

## Command

```bash
python -m trading_bot.cli security-qa-report --config config/bot.sample.toml --env-file .env.example --scan-root .
```

The report is saved at:

```text
work/market_data/qa/security/report.json
```

## Required Checks

- `env_security`: validates the full environment guard.
- `withdrawal_disabled`: requires `API_WITHDRAWAL_PERMISSION=false`.
- `live_blocked`: requires live execution to remain disabled.
- `credential_pairing`: rejects API key without secret or secret without key.
- `secret_scan`: rejects leaked-looking raw exchange secrets in source files.

## Pass Rule

The report must be `PASSED` before VPS production readiness or live review work.
Any failed check blocks deployment.

Warnings can still appear when private credentials are present. In v1, real live
credentials should not be used; if testnet keys are introduced later, they must
be trading-only and IP-whitelisted where the exchange supports it.
