# AI/ML Research Assistant Guardrails

AI boleh membantu membaca daily report, dataset pola, backtest, walk-forward, dan
post-trade analysis. AI tidak boleh menjadi execution engine.

## Allowed

- Membuat research note.
- Mengusulkan eksperimen parameter.
- Mengusulkan filter entry/exit untuk diuji.
- Merangkum pola menang/kalah dari data.

## Blocked

- Menempatkan order live.
- Mengubah live config.
- Mematikan stop loss, daily stop, profit lock, atau risk manager.
- Mempromosikan strategi tanpa backtest dan paper validation.
- Memakai rekomendasi sebagai sinyal order langsung.

Semua rekomendasi AI harus masuk backlog eksperimen, lalu diuji melalui backtest,
walk-forward, dan paper trading sebelum dipakai.
