# Demo Account Go-Live Path

Target terdekat adalah bot bisa dipakai end-to-end dengan demo account, bukan
real-money live account.

## Tahap Aman

1. Local demo data: jalankan `Demo Data` di web orchestrator.
2. Paper mode: bot membuat order/trade/account snapshot virtual.
3. SQLite archive: klik `Import DB`.
4. Learning snapshot: klik `Learning DB`.
5. Sandbox/testnet: gunakan adapter `sandbox` atau `testnet`, tanpa withdrawal.
6. Live review: hanya setelah paper evidence, security QA, readiness, dan manual
   owner approval lulus.

## Command Lokal

```bash
python -m trading_bot.cli seed-demo-data --config config/bot.sample.toml
python -m trading_bot.cli import-runtime-db --config config/bot.sample.toml
python -m trading_bot.cli db-learning-report --config config/bot.sample.toml
python -m trading_bot.cli testnet-demo-report --config config/bot.sample.toml --environment testnet
python -m trading_bot.cli sandbox-order --environment sandbox --symbol BTC/USDT --side buy --order-type market --quantity 0.001
```

`testnet-demo-report` membuat laporan di:

```text
work/market_data/execution/testnet_demo/report.json
```

Di web orchestrator, report yang sama tampil di panel `Demo/Testnet Monitoring`
dan API read-only:

```text
http://127.0.0.1:8000/api/testnet-demo
```

## Guard

- Real live key tidak dibutuhkan untuk demo account.
- `BOT_LIVE_ENABLED=false` wajib tetap aktif.
- Tidak ada tombol live buy/sell/order di UI lokal.
- Testnet/sandbox boleh untuk uji execution flow, tapi tidak menjadi izin real
  live otomatis.
