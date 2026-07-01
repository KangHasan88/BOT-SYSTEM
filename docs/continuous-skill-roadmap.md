# Continuous Skill Improvement Roadmap

Tujuan project ini adalah membuat bot yang terus meningkat kemampuan analisanya
tanpa pernah mengorbankan risk guard. Bot boleh makin pintar dari data harian,
paper trade, backtest, human feedback, dan review risiko, tetapi tidak boleh
auto-promote strategi ke live.

## Prinsip Utama

- Skill naik dari evidence, bukan feeling.
- Loss limit lebih penting daripada target profit.
- AI dan learning module hanya boleh mengusulkan eksperimen.
- Strategi baru harus lewat backtest, walk-forward, paper campaign, dan review
  owner sebelum dipakai di live.
- Real live tetap locked sampai live evidence lengkap dan owner approval ada.

## Learning Loop

Loop peningkatan skill harus berulang dalam urutan ini:

1. Capture data: candle, spread, liquidity metadata, paper trade, account
   snapshot, audit log, dan daily journal.
2. Baca pola: regime market, trend/sideways, volume spike, wick, liquidity
   sweep, false signal, dan news-risk note.
3. Review hasil: trade menang/kalah, alasan entry, alasan exit, stop loss,
   profit lock, skip/reject, dan mistake tag.
4. Buat eksperimen: kandidat filter, parameter, session rule, atau risk rule
   baru dengan hypothesis tertulis.
5. Backtest dan walk-forward: cek no-lookahead, fee, spread, slippage,
   drawdown, profit factor, expectancy, dan stability.
6. Paper campaign: jalankan 2-4 minggu atau sampai sample trade cukup.
7. Evidence gate: hanya kandidat yang lolos boleh masuk owner review.
8. Scale decision: keep, improve, pause, rollback, atau archive.

## Skill Metrics

Metrik minimal yang harus dibaca sebelum menyebut bot "lebih pintar":

- data quality status;
- jumlah candle valid per symbol/timeframe;
- sample trade count;
- win rate;
- expectancy;
- profit factor;
- max drawdown;
- average R;
- risk/reward realized;
- consecutive loss;
- paper stability day count;
- mistake tag frequency;
- manual feedback count;
- evidence completion percent.

Win rate tinggi tidak cukup. Strategi dengan win rate tinggi tetap ditolak jika
expectancy buruk, drawdown terlalu besar, data quality gagal, atau paper evidence
belum cukup.

## Phase Roadmap

### Phase 1: Local Demo

Goal: user bisa melihat bot berjalan di laptop dengan data demo/paper.

Required evidence:

- local web orchestrator bisa dibuka;
- Demo Walkthrough selesai;
- P/L Visual Monitor menampilkan paper/demo result;
- SQLite learning snapshot tersedia;
- real live disabled.

### Phase 2: Paper Campaign

Goal: bot mulai mengumpulkan bukti stabil dari paper trading.

Required evidence:

- data quality gate tidak BLOCKED;
- minimal 14 hari paper evidence;
- minimal 20 completed paper trades;
- paper stability report tidak menemukan critical error;
- post-trade review dan daily journal tersedia.

### Phase 3: Testnet/Sandbox

Goal: flow order diuji di adapter sandbox/testnet tanpa uang asli.

Required evidence:

- testnet demo report PASSED;
- order placement/cancel flow tercatat;
- live guard tetap PASS;
- no withdrawal permission;
- incident drill dan kill switch sudah diuji.

### Phase 4: Tiny Live Locked

Goal: hanya menyiapkan live kecil, bukan auto-enable.

Required evidence:

- live evidence READY_FOR_MANUAL_REVIEW;
- live go/no-go GO_FOR_OWNER_REVIEW;
- owner approval tersimpan;
- modal, max loss, risk cap, dan jadwal trading diset manual;
- rollback plan siap;
- live config masih disabled sampai owner enable secara sadar.

## Mandatory Card Checklist

Setiap card `LEARN`, `UX`, `PAPER`, `TESTNET`, dan `LIVE` harus menjawab:

- Data apa yang dicapture?
- Evidence apa yang membuktikan fitur ini bekerja?
- Risiko apa yang bisa membuat user salah paham?
- Apakah fitur ini bisa memicu live order? Jika ya, card harus ditolak untuk v1.
- Apakah ada fallback atau kill-switch behavior?
- Apakah output-nya bisa dibaca user awam?
- Apakah hasilnya tersimpan sebagai report, CSV, SQLite, atau audit log?
- Test apa yang membuktikan guardrail tetap aman?
- Kanban comment apa yang harus ditulis saat progress/testing/done?

## Promotion Rules

Strategi atau filter baru hanya boleh naik level dengan aturan:

- `research -> backtest`: data quality PASS dan hypothesis tertulis.
- `backtest -> paper`: no-lookahead PASS, fee/spread/slippage dihitung, drawdown
  masih di bawah batas.
- `paper -> owner review`: sample trade cukup, paper stability PASS, risk guard
  dan incident drill PASS.
- `owner review -> tiny live plan`: live evidence lengkap, owner approval ada,
  dan live phase plan masih read-only.

Tidak ada jalur `AI recommendation -> live order`.

## Stop Conditions

Learning loop harus berhenti atau masuk review jika:

- data quality BLOCKED;
- daily max loss tersentuh;
- monthly drawdown tersentuh;
- two consecutive losses in one day;
- kill switch active;
- exchange API bermasalah;
- strategy version menghasilkan outlier loss;
- manual reviewer memberi tag `unsafe`, `news risk`, atau `false signal` berulang.

## Human Feedback Labels

Label sederhana untuk review manual:

- `setup bagus`;
- `entry telat`;
- `exit cepat`;
- `market sideways`;
- `news risk`;
- `false signal`;
- `risk terlalu besar`;
- `profit lock bagus`;
- `skip benar`;
- `perlu eksperimen`.

Label ini menjadi bahan riset, bukan perintah live.

## Weekly Review Output

Setiap minggu, bot harus bisa menghasilkan ringkasan:

- apa yang dipelajari;
- pola yang sering menang;
- pola yang sering kalah;
- mistake tag terbanyak;
- kandidat eksperimen baru;
- strategi yang harus dipause;
- evidence yang masih kurang sebelum live review.

Command:

```bash
python -m trading_bot.cli skill-loop-report --config config/bot.sample.toml
```

Report:

```text
work/market_data/reports/learning/skill_loop.json
```

## Guardrail Summary

Bot boleh belajar terus, tetapi live execution adalah privilege yang dibuka
manual. Sampai semua evidence lengkap, status real live harus tetap locked.
