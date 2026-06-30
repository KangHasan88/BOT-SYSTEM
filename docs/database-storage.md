# Database Storage Lokal

Bot saat ini tetap menulis file runtime utama sebagai CSV/JSON di
`work/market_data/`, lalu bisa mengarsipkannya ke SQLite lokal. SQLite dipakai
sebagai tahap aman sebelum PostgreSQL karena tidak butuh server database dan
cocok untuk laptop/VPS demo.

## Command

Inisialisasi database:

```powershell
& 'C:\Users\IT-MGR\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m trading_bot.cli init-db --config config/bot.sample.toml
```

Import data runtime:

```powershell
& 'C:\Users\IT-MGR\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m trading_bot.cli import-runtime-db --config config/bot.sample.toml
```

Cek ringkasan database:

```powershell
& 'C:\Users\IT-MGR\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m trading_bot.cli db-status --config config/bot.sample.toml
```

Default file database:

```text
work/market_data/bot.sqlite3
```

## Data Yang Diarsipkan

- candle market dari CSV OHLCV;
- order, trade, dan account snapshot paper;
- audit event dari `logs/audit.jsonl`;
- aktivitas orchestrator dari `orchestrator/activity.jsonl`.

Import bersifat idempotent. Jika command dijalankan berkali-kali, row yang sama
tidak akan dobel.

Ringkasan SQLite juga muncul di web orchestrator sebagai panel `Database Lokal`
dan tersedia via JSON di:

```text
http://127.0.0.1:8000/api/database
```

## Batasan V1

SQLite ini belum menggantikan semua CSV/JSON sebagai source of truth runtime.
Untuk fase berikutnya, bot bisa membaca agregasi dari SQLite untuk dashboard,
daily learning, dan pattern study. PostgreSQL baru masuk akal saat bot sudah
stabil di VPS dan volume data makin besar.
