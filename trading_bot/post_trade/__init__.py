"""Post-trade analysis package."""

from trading_bot.post_trade.analysis import (
    PostTradeReport,
    TradeSummary,
    generate_post_trade_report,
    save_post_trade_report,
)
from trading_bot.post_trade.csv_loader import load_paper_trades

__all__ = [
    "PostTradeReport",
    "TradeSummary",
    "generate_post_trade_report",
    "load_paper_trades",
    "save_post_trade_report",
]
