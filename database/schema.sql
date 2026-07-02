-- Trading bot database blueprint.
-- The current app stores runtime data as CSV/JSON under work/market_data/.
-- This schema mirrors that structure for a future SQLite/PostgreSQL backend.

CREATE TABLE IF NOT EXISTS market_candles (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time_ms INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    close_time_ms INTEGER,
    quote_asset_volume REAL,
    trades INTEGER,
    taker_buy_base_volume REAL,
    taker_buy_quote_volume REAL,
    source TEXT NOT NULL DEFAULT 'binance_public',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (symbol, timeframe, open_time_ms)
);

CREATE TABLE IF NOT EXISTS market_context_snapshots (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,
    captured_at_ms INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strategy_signals (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time_ms INTEGER NOT NULL,
    signal TEXT NOT NULL,
    confidence REAL NOT NULL,
    reason TEXT NOT NULL,
    close REAL NOT NULL,
    atr REAL,
    rsi REAL,
    ema_fast REAL,
    ema_slow REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (symbol, timeframe, open_time_ms)
);

CREATE TABLE IF NOT EXISTS detected_patterns (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time_ms INTEGER NOT NULL,
    pattern TEXT NOT NULL,
    direction TEXT NOT NULL,
    strength REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_regimes (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time_ms INTEGER NOT NULL,
    regime TEXT NOT NULL,
    volatility_state TEXT NOT NULL,
    trend_state TEXT NOT NULL,
    score REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (symbol, timeframe, open_time_ms)
);

CREATE TABLE IF NOT EXISTS paper_orders (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time_ms INTEGER NOT NULL,
    side TEXT NOT NULL,
    action TEXT NOT NULL,
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    notional REAL NOT NULL,
    fee REAL NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    entry_time_ms INTEGER NOT NULL,
    exit_time_ms INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    quantity REAL NOT NULL,
    gross_pnl REAL NOT NULL,
    fees REAL NOT NULL,
    net_pnl REAL NOT NULL,
    exit_reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_account_snapshots (
    id INTEGER PRIMARY KEY,
    open_time_ms INTEGER NOT NULL,
    equity REAL NOT NULL,
    day_start_equity REAL NOT NULL,
    month_start_equity REAL NOT NULL,
    open_positions INTEGER NOT NULL,
    consecutive_losses_today INTEGER NOT NULL,
    trading_status TEXT NOT NULL,
    status_reason TEXT NOT NULL,
    unrealized_pnl REAL NOT NULL DEFAULT 0,
    marked_equity REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    entry_time_ms INTEGER NOT NULL,
    exit_time_ms INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    quantity REAL NOT NULL,
    gross_pnl REAL NOT NULL,
    fees REAL NOT NULL,
    net_pnl REAL NOT NULL,
    exit_reason TEXT NOT NULL,
    entry_signal_time_ms INTEGER,
    exit_signal_time_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backtest_equity_points (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time_ms INTEGER NOT NULL,
    equity REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS qa_reports (
    id INTEGER PRIMARY KEY,
    report_type TEXT NOT NULL,
    symbol TEXT,
    timeframe TEXT,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS readiness_reports (
    id INTEGER PRIMARY KEY,
    status TEXT NOT NULL,
    live_enabled INTEGER NOT NULL DEFAULT 0,
    approved_live INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    event TEXT NOT NULL,
    message TEXT NOT NULL,
    context_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orchestrator_activity (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    return_code INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    output_tail TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_market_candles_symbol_tf_time
    ON market_candles (symbol, timeframe, open_time_ms);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf_time
    ON strategy_signals (symbol, timeframe, open_time_ms);

CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol_tf_exit
    ON paper_trades (symbol, timeframe, exit_time_ms);

CREATE INDEX IF NOT EXISTS idx_audit_events_level_ts
    ON audit_events (level, ts);

CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_orders_unique_import
    ON paper_orders (symbol, timeframe, open_time_ms, side, action, status, reason);

CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_trades_unique_import
    ON paper_trades (symbol, timeframe, entry_time_ms, exit_time_ms, exit_reason);

CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_account_unique_import
    ON paper_account_snapshots (open_time_ms);

CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_events_unique_import
    ON audit_events (ts, level, event, message);

CREATE UNIQUE INDEX IF NOT EXISTS idx_orchestrator_activity_unique_import
    ON orchestrator_activity (ts, action, status, return_code);
