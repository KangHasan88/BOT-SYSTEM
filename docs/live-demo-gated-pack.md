# Gated Live Demo Pack

Dokumen ini menutup backlog LIVE1-LIVE5 sebagai jalur gated. Ini bukan izin
menyalakan real live. Selama paper evidence belum cukup dan owner belum approve,
hasil live pack tetap `NO_GO`.

## LIVE1 Tiny Live Phase Setup

- Modal fase kecil default: Rp1.000.000.
- Max risk per trade: 0.25% atau Rp2.500.
- Daily stop: 1% atau Rp10.000.
- Monthly drawdown stop: 5% atau Rp50.000.
- Max open position: 1.
- Syarat: `live-readiness-report` harus `READY_FOR_MANUAL_REVIEW`.
- Syarat: `live-go-no-go-report --owner-approved` harus `GO_FOR_OWNER_REVIEW`.
- Real API key tetap belum dipasang di repo.

## LIVE2 Live User Demo Read-Only First

- Mode pertama setelah approval adalah read-only monitoring.
- Dashboard hanya boleh menampilkan balance, status koneksi, P/L, audit, dan
  kill switch.
- Tidak ada tombol market order di UI.
- Exchange key harus withdrawal disabled dan permission minimal.

## LIVE3 Tiny Live Smoke

- Sesi smoke boleh berakhir `NO_TRADE`; itu valid jika kondisi risiko tidak
  memenuhi rule.
- Jika ada trade, nominal harus mengikuti risk cap LIVE1.
- Review wajib mencatat entry reason, exit reason, P/L, slippage, spread, dan
  apakah profit lock bekerja.
- Setelah sesi pertama, bot harus pause untuk owner review.

## LIVE4 Incident & Rollback

- Kill switch harus bisa aktif sebelum sesi.
- Jika network/API down, bot harus stop membuka posisi baru.
- Jika web/orchestrator crash, watchdog boleh restart dashboard, tetapi tidak
  boleh membuat order baru.
- Rollback default: clear live key dari environment, kembali ke paper mode,
  jalankan incident drill, lalu tulis post-incident note.

## LIVE5 Post-Live Review

Keputusan setelah sesi:

- `SCALE`: hanya jika evidence live kecil positif, risk guard bekerja, dan tidak
  ada incident.
- `PAUSE`: jika P/L negatif kecil, sinyal tidak jelas, atau butuh review.
- `STOP`: jika loss limit, incident, slippage buruk, atau user tidak nyaman.

## Current Project Status

Untuk kondisi saat ini, keputusan live adalah `NO_GO_FOR_REAL_LIVE` dan
`READY_TO_USE_FOR_DEMO_PAPER` jika UAT report lulus.
