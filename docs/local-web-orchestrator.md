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

## Mulai di Sini

Panel `Mulai di Sini` adalah menu instalasi dan langkah awal di web. Panel ini
muncul di bagian atas dashboard agar user tidak perlu membuka file satu per
satu.

Urutannya:

1. Buka folder project:

```text
C:\Users\IT-MGR\Documents\Codex\2026-06-28\bro-2
```

2. Double-click launcher:

```text
start-bot-web.cmd
```

3. Buka web lokal:

```text
http://127.0.0.1:8000/
```

4. Ikuti `Demo Walkthrough`.
5. Pantau naik-turun profit/loss di `P/L Visual Monitor`.
6. Jika browser refused, double-click:

```text
start-bot-watchdog.cmd
```

Menu ini tetap demo/paper only. Real live tetap dikunci sampai evidence dan
owner approval lengkap.

Jika halaman `127.0.0.1:8000` mati atau muncul `refused to connect`, jalankan
watchdog lokal:

```text
start-bot-watchdog.cmd
```

Watchdog mengecek `http://127.0.0.1:8000/api/status` berkala. Jika tidak sehat,
helper akan memanggil `scripts/start-local-orchestrator.ps1` tanpa membuka
browser baru. Log watchdog tersimpan di:

```text
work/orchestrator/watchdog.log
```

Untuk repair sekali jalan:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\watch-local-orchestrator.ps1 -MaxChecks 1
```

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

## Kamus Awam

Panel `Kamus Awam` menjelaskan istilah yang sering muncul di control room:

- `Paper/Demo`;
- `P/L`;
- `Evidence`;
- `Evidence Score`;
- `BUTUH PAPER`;
- `Pattern Memory`;
- `Skill Loop`;
- `Kill Switch`;
- `Go/No-Go`;
- `Volume Spike`.

Istilah yang sama dipakai sebagai hover message di tombol dan metric utama.
Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/glossary
```

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

Untuk user awam, panel juga menampilkan `Kesimpulan Awam`:

- `Profit Demo`: saldo simulasi naik dan realized P/L positif.
- `Loss Demo`: saldo simulasi turun dan realized P/L negatif.
- `Campuran / Perlu Review`: salah satu angka bagus tetapi angka lain belum
  aman, misalnya realized P/L positif tetapi equity terakhir masih turun dari
  saldo awal.

Cara baca cepat:

- `Equity Terakhir` adalah saldo simulasi terakhir.
- `Equity Change` adalah naik/turun saldo dari awal. Minus berarti saldo demo
  sedang turun.
- `Realized P/L Demo` adalah total profit/rugi dari trade yang sudah selesai.
- `Win Rate` hanya persentase trade menang; tidak otomatis berarti strategi
  aman.

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

## Learning Dashboard

Panel `Learning Dashboard` membaca:

```text
work/market_data/reports/learning/learning_dashboard.json
```

Klik tombol `Learning Dashboard` setelah `Skill Loop` dan `Pattern Memory`.
Panel ini menampilkan evidence score, status awam seperti `BUTUH PAPER`,
volume spike, jumlah trade, win rate, P/L, dan aksi berikutnya. Score ini untuk
prioritas review, bukan izin live.

Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/learning-dashboard
```

## Human Feedback

Panel `Human Feedback` membaca:

```text
work/market_data/reports/learning/human_feedback.json
```

Label manual ditulis ke:

```text
work/market_data/reports/learning/manual_labels.json
```

Gunakan command `add-feedback-label` untuk memberi label seperti
`entry_telat`, `false_signal`, `profit_lock_bagus`, atau `skip_benar`, lalu
klik tombol `Human Feedback` untuk refresh lesson di web. Feedback ini hanya
bahan review dan eksperimen, bukan perintah live.

Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/human-feedback
```

## Fundamental/Event Lane

Panel `Fundamental/Event Lane` membaca:

```text
work/market_data/reports/fundamental/report.json
```

Event manual disimpan di:

```text
work/market_data/reports/fundamental/events.json
```

Risk color:

- `LOW / green`: lanjut review teknikal.
- `MEDIUM / yellow`: hati-hati, cek volatilitas dan spread.
- `HIGH / orange`: pause entry baru sampai event lewat atau direview.
- `BLOCK / red`: jangan percaya sinyal baru sebelum owner review.

Command:

```bash
python -m trading_bot.cli add-fundamental-event --config config/bot.sample.toml --symbol BTC/USDT --category macro --risk HIGH --title "US CPI release window" --note "pause entry baru dekat event"
python -m trading_bot.cli fundamental-report --config config/bot.sample.toml
```

Status yang sama tersedia sebagai JSON di:

```text
http://127.0.0.1:8000/api/fundamental
```

## Experiment Scoreboard

Panel `Experiment Scoreboard` membaca:

```text
work/market_data/reports/learning/experiment_scoreboard.json
```

Registry eksperimen strategi tersimpan di:

```text
work/market_data/reports/learning/strategy_experiments.json
```

Gunakan command:

```bash
python -m trading_bot.cli add-strategy-experiment --config config/bot.sample.toml --strategy-id volume_spike_retest --version v1 --hypothesis "volume spike after sweep improves entry timing" --status PAPER --backtest-score 30 --paper-score 25 --evidence-score 20 --risk-score 5
python -m trading_bot.cli experiment-scoreboard --config config/bot.sample.toml
```

Score tinggi hanya boleh mendorong eksperimen ke backtest/paper review. Tidak
ada promosi langsung ke live.

Endpoint:

```text
http://127.0.0.1:8000/api/experiment-scoreboard
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
