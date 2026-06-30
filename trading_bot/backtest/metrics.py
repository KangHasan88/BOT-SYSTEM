from __future__ import annotations

from dataclasses import dataclass

from trading_bot.backtest.models import BacktestResult, BacktestTrade


@dataclass(frozen=True)
class BacktestMetrics:
    total_return_pct: float
    gross_return_pct: float
    total_gross_pnl: float
    total_net_pnl: float
    total_fees: float
    fee_pct: float
    slippage_pct: float
    no_lookahead_passed: bool
    max_drawdown_pct: float
    trade_count: int
    win_rate_pct: float
    profit_factor: float
    expectancy: float
    average_r: float
    longest_losing_streak: int
    recommendation: str
    reason: str


def calculate_backtest_metrics(result: BacktestResult) -> BacktestMetrics:
    trades = result.trades
    total_gross_pnl = sum(trade.gross_pnl for trade in trades)
    total_net_pnl = sum(trade.net_pnl for trade in trades)
    total_fees = sum(trade.fees for trade in trades)
    total_return_pct = (
        ((result.final_equity - result.initial_equity) / result.initial_equity) * 100
        if result.initial_equity
        else 0.0
    )
    gross_return_pct = (total_gross_pnl / result.initial_equity * 100) if result.initial_equity else 0.0
    max_drawdown_pct = _max_drawdown(result)
    win_count = sum(1 for trade in trades if trade.net_pnl > 0)
    loss_count = sum(1 for trade in trades if trade.net_pnl < 0)
    gross_profit = sum(trade.net_pnl for trade in trades if trade.net_pnl > 0)
    gross_loss = abs(sum(trade.net_pnl for trade in trades if trade.net_pnl < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss else (float("inf") if gross_profit else 0.0)
    expectancy = (sum(trade.net_pnl for trade in trades) / len(trades)) if trades else 0.0
    average_r = _average_r(trades)
    longest_losing_streak = _longest_losing_streak(trades)
    win_rate_pct = (win_count / len(trades) * 100) if trades else 0.0
    recommendation, reason = _recommend(
        trade_count=len(trades),
        profit_factor=profit_factor,
        max_drawdown_pct=max_drawdown_pct,
        expectancy=expectancy,
        total_return_pct=total_return_pct,
        gross_return_pct=gross_return_pct,
        longest_losing_streak=longest_losing_streak,
        no_lookahead_passed=_no_lookahead_passed(result),
    )

    return BacktestMetrics(
        total_return_pct=total_return_pct,
        gross_return_pct=gross_return_pct,
        total_gross_pnl=total_gross_pnl,
        total_net_pnl=total_net_pnl,
        total_fees=total_fees,
        fee_pct=result.fee_pct,
        slippage_pct=result.slippage_pct,
        no_lookahead_passed=_no_lookahead_passed(result),
        max_drawdown_pct=max_drawdown_pct,
        trade_count=len(trades),
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        expectancy=expectancy,
        average_r=average_r,
        longest_losing_streak=longest_losing_streak,
        recommendation=recommendation,
        reason=reason,
    )


def _max_drawdown(result: BacktestResult) -> float:
    peak = result.initial_equity
    max_drawdown = 0.0
    for point in result.equity_curve:
        peak = max(peak, point.equity)
        if peak:
            drawdown = ((peak - point.equity) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown


def _average_r(trades: list[BacktestTrade]) -> float:
    if not trades:
        return 0.0
    r_values: list[float] = []
    for trade in trades:
        initial_risk = abs(trade.entry_price - trade.exit_price) * trade.quantity
        if initial_risk == 0:
            continue
        r_values.append(trade.net_pnl / initial_risk)
    return sum(r_values) / len(r_values) if r_values else 0.0


def _longest_losing_streak(trades: list[BacktestTrade]) -> int:
    longest = 0
    current = 0
    for trade in trades:
        if trade.net_pnl < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _recommend(
    trade_count: int,
    profit_factor: float,
    max_drawdown_pct: float,
    expectancy: float,
    total_return_pct: float,
    gross_return_pct: float,
    longest_losing_streak: int,
    no_lookahead_passed: bool,
) -> tuple[str, str]:
    if trade_count < 30:
        return "NOT_ENOUGH_DATA", "trade sample below 30"
    if not no_lookahead_passed:
        return "REJECT", "no-lookahead audit failed"
    if gross_return_pct > 0 and total_return_pct <= 0:
        return "REJECT", "strategy only profitable before costs"
    if expectancy <= 0 or total_return_pct <= 0:
        return "REJECT", "expectancy or total return is not positive"
    if max_drawdown_pct > 8:
        return "REJECT", "max drawdown above conservative threshold"
    if profit_factor < 1.3:
        return "NEEDS_FILTER", "profit factor below 1.3"
    if longest_losing_streak > 6:
        return "NEEDS_FILTER", "losing streak too long for conservative profile"
    return "PAPER_CANDIDATE", "metrics pass conservative paper-trading threshold"


def _no_lookahead_passed(result: BacktestResult) -> bool:
    for trade in result.trades:
        if trade.entry_signal_time_ms is not None and trade.entry_time_ms <= trade.entry_signal_time_ms:
            return False
        if trade.exit_signal_time_ms is not None and trade.exit_time_ms <= trade.exit_signal_time_ms:
            return False
    return True
