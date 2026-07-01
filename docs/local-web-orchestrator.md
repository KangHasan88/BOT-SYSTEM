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
- Demo Data lokal tanpa exchange/live;
- Local Demo readiness untuk cek jalur demo end-to-end;
- VPS Demo readiness untuk cek jalur private VPS paper mode;
- Import DB SQLite lokal;
- Learning DB dari SQLite lokal;
- Skill Loop untuk review pembelajaran dan kandidat eksperimen;
- Buat Dashboard statis;
- Security QA;
- Production Smoke;
- Live Go/No-Go report;
- Live Evidence gate;
- Evidence Campaign untuk refresh seluruh bukti readiness lokal;
- Paper Campaign untuk monitor evidence paper 2-4 minggu;
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

## Control Room Awam

Panel `Control Room Awam` adalah tampilan pertama untuk user non-teknis. Panel
ini menampilkan ringkasan kondisi bot, mode akun, P/L demo, evidence live, dan
7 step bernomor:

- Cek Keamanan;
- Cek Data Market;
- Cek Sinyal;
- Cek Risiko;
- Demo Trade;
- Pantau P/L;
- Review Go Live.

Setiap step punya hover message agar user paham arti status tanpa membuka file
teknis. Panel ini tetap read-only dan tidak menyediakan tombol real live order.

## Demo Walkthrough

Panel `Demo Walkthrough` adalah jalur demo lokal 1-6:

- buka web lokal;
- cek config;
- isi data demo;
- jalankan evidence campaign;
- pantau P/L;
- review go-live blocker.

Setiap kartu punya nomor urut, status, aksi yang perlu diklik, dan hover message
bahasa awam. Jalur ini membantu user menjalankan demo lokal tanpa membuka file
teknis satu per satu. Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/walkthrough
```

## Local Demo Readiness

Panel `Local Demo Readiness` membaca report end-to-end demo lokal dari:

```text
work/market_data/demo/local_demo.json
```

Klik tombol `Local Demo` untuk membuat report ini. Jika data demo belum ada,
aksi ini boleh mengisi data demo terlebih dahulu, lalu memeriksa:

- web lokal;
- config safe dan live lock;
- candle demo;
- paper trades;
- report JSON;
- P/L Visual Monitor.

Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/local-demo
```

## Private VPS Demo

Panel `Private VPS Demo` membaca:

```text
work/market_data/demo/vps_demo.json
```

Klik tombol `VPS Demo` untuk memeriksa kesiapan demo VPS private. Panel ini
mengecek config VPS paper-only, service web yang bind ke localhost, script SSH
tunnel, runbook private access, evidence local demo, paper campaign, dan live
lock.

Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/vps-demo
```

## P/L Visual Monitor

Panel `P/L Visual Monitor` membaca hasil paper/demo dari file `account.csv` dan
`trades.csv`. Panel ini menampilkan:

- realized P/L demo;
- win rate;
- jumlah trade;
- equity terakhir;
- perubahan equity;
- best/worst trade;
- mini equity curve;
- trade terakhir.

Semua angka di panel ini berasal dari simulasi paper/demo, bukan real-money
live account. Data yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/pnl
```

## Paper Campaign

Panel `Paper Campaign` membaca:

```text
work/market_data/qa/paper_campaign/report.json
```

Klik tombol `Paper Campaign` untuk refresh tracker paper 2-4 minggu. Panel ini
menampilkan completion percent, jumlah pair stabil, total paper trade, net P/L
paper, blocker aktif, dan detail per symbol/timeframe.

Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/paper-campaign
```

## Skill Loop

Panel `Skill Loop` membaca:

```text
work/market_data/reports/learning/skill_loop.json
```

Klik tombol `Skill Loop` untuk membuat ringkasan loop belajar: capture data,
baca pola, review trade, paper campaign, evidence gate, dan kandidat eksperimen
berikutnya. Output ini hanya research/readiness, bukan sinyal live order.

Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/skill-loop
```

## Pattern Memory

Panel `Pattern Memory` membaca:

```text
work/market_data/reports/learning/pattern_memory.json
```

Klik tombol `Pattern Memory` setelah `Import DB` dan `Learning DB`. Panel ini
menampilkan observation, grade outcome, jumlah paper trade, win rate, P/L,
label manual, dan aksi review berikutnya. Tujuannya agar pola yang terlihat
bagus tetap diuji dulu, bukan langsung masuk live.

Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/pattern-memory
```

## Setup Cepat

Halaman utama punya checklist first-run untuk:

- validitas config;
- live guard nonaktif;
- ketersediaan root data market;
- sample candle demo;
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

Tombol `Learning DB` membuat snapshot pembelajaran dari candle yang sudah masuk
SQLite. Output-nya muncul di Browser Laporan sebagai kategori `Learning`.

Untuk demo akun pertama, gunakan `Demo Data` dan paper/sandbox dulu. Ini membuat
bot bisa dipakai end-to-end tanpa real-money live key.

## Demo/Testnet Monitoring

Panel `Demo/Testnet Monitoring` menampilkan report terakhir dari tombol
`Testnet Demo`: status demo, environment, live guard, dan daftar order demo.
Panel ini read-only dan tidak punya tombol real live order.

Ringkasan yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/testnet-demo
```

## Live Evidence Gate

Panel `Live Evidence Gate` membaca report dari tombol `Live Evidence`.
Isinya status kesiapan live, persentase completion, blocker aktif, dan detail
evidence seperti QA security, data quality, backtest, walk-forward, paper
stability, incident drill, testnet demo, learning snapshot, readiness, dan
owner Go/No-Go.

Report ini sengaja boleh `INCOMPLETE`. Itu artinya bot belum boleh real live
karena masih ada bukti yang kurang, misalnya jumlah trade paper belum cukup
atau readiness masih `BLOCKED`.

Ringkasan yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/live-evidence
```

Tombol `Evidence Campaign` menjalankan rangkaian aman untuk demo/paper:
data quality gate, backtest report, walk-forward report, paper stability,
live readiness, Go/No-Go, lalu Live Evidence. Jika data lokal belum cukup,
aksi ini mengisi demo data lokal terlebih dahulu. Hasil ringkas disimpan ke:

```text
work/market_data/readiness/evidence_campaign.json
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
