# Orchestrator Web Lokal

Orchestrator web lokal adalah UI browser pertama untuk mengendalikan bot dari
laptop. UI ini jalan di localhost dan hanya membuka aksi aman untuk mode
paper/research.

Layout, spacing, card, table, font, dan pola interaksinya mengikuti
`docs/ui-design-reference.md`, dengan Kanban sebagai referensi visual. Default
bahasa UI adalah Bahasa Indonesia, sementara istilah teknis seperti Kill Switch,
Security QA, Go/No-Go, dan paper/research tetap dipakai agar konsisten dengan
backlog dan laporan.

## Mulai

Buka PowerShell dari root project:

```powershell
cd C:\Users\IT-MGR\Documents\Codex\2026-06-28\bro-2
& 'C:\Users\IT-MGR\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m trading_bot.cli serve-orchestrator --config config/bot.sample.toml --host 127.0.0.1 --port 8000
```

Lalu buka:

```text
http://127.0.0.1:8000
```

Cara paling gampang, double-click:

```text
start-bot-web.cmd
```

Atau jalankan:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local-orchestrator.ps1
```

Launcher akan menjalankan orchestrator di background, menyimpan process id ke
`work/orchestrator/local-web.pid`, menunggu `/api/setup`, lalu membuka browser
ketika sudah siap.

Untuk stop:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-local-orchestrator.ps1
```

## Aksi Aman

- Validasi Config;
- Import DB SQLite lokal;
- Buat Dashboard statis;
- Security QA;
- Production Smoke;
- Live Go/No-Go report;
- Jalankan Siklus offline-safe;
- Sinkron data terbaru BTC/USDT 15m;
- Sinkron data terbaru ETH/USDT 15m.

Input limit candle dibatasi 1-1000. Saat command sedang berjalan, orchestrator
menulis file `action.lock` agar klik browser lain tidak memulai command yang
bentrok.

Tidak ada tombol live buy/sell/order di UI ini.

## Status Bot

Halaman utama merangkum:

- status data quality gate;
- jumlah trade paper dan net PnL;
- status live go/no-go dan readiness;
- kill switch, live flag, dan status security.

Status bahaya seperti `BLOCKED` dan `NO_GO` ditampilkan sebagai badge yang jelas.

## Setup Cepat

Halaman utama punya checklist first-run untuk:

- validitas config;
- live guard nonaktif;
- ketersediaan root data market;
- report Security QA;
- dashboard yang sudah dibuat;
- database SQLite lokal;
- aksi UI pertama yang tercatat.

Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/setup
```

## Browser Laporan

Halaman ini punya browser laporan read-only untuk:

- metrik backtest;
- validasi walk-forward;
- order, trade, dan snapshot akun paper;
- jurnal market harian.

Ringkasan yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/reports
```

## Database Lokal

Panel `Database Lokal` menampilkan path SQLite, ukuran file, waktu update,
total row, dan jumlah row per tabel utama. Jalankan `Import DB` setelah sync
atau paper cycle agar data harian masuk ke arsip lokal.

Ringkasan yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/database
```

## Kill Switch Dan Incident Panel

Halaman utama punya panel safety untuk:

- status dan alasan kill switch saat ini;
- aktivasi manual kill switch dengan alasan wajib;
- clear kill switch setelah review operator;
- status incident drill terbaru dan ringkasan skenario.

Incident drill bisa dijalankan dari bagian Aksi Aman. Status panel tersedia
sebagai JSON di:

```text
http://127.0.0.1:8000/api/incident
```

## Aktivitas

Setiap aksi UI menulis catatan aktivitas ke:

```text
work/market_data/orchestrator/activity.jsonl
```

Output aktivitas terbaru ditampilkan di halaman.

## Audit Timeline

Halaman ini juga membaca:

```text
work/market_data/logs/audit.jsonl
```

Event audit bisa difilter berdasarkan level, simbol, dan timeframe. Timeline
menandai `ERROR` dan `CRITICAL` dengan jelas dan refresh berkala tanpa restart
bot.
