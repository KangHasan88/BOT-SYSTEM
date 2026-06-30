# Database Structure

The bot currently uses file-based storage so it can run safely in local paper
mode before a production database is introduced. Runtime records are written
under `work/market_data/` and are intentionally excluded from Git.

`schema.sql` documents the planned relational structure for the same data:

- candles and market context;
- signals, detected patterns, and market regimes;
- paper orders, paper trades, and account snapshots;
- backtest trades and equity curve;
- QA reports, readiness status, audit events, and orchestrator activity.

This structure is a blueprint for a future SQLite/PostgreSQL migration. Until
that migration is implemented, the source of truth remains CSV/JSON files
created by the Python services.

