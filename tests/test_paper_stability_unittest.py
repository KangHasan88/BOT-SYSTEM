from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_bot.observability import JsonlAuditLogger
from trading_bot.qa import PaperStabilityConfig, evaluate_paper_stability, save_paper_stability_report


class PaperStabilityTest(unittest.TestCase):
    def test_blocks_when_paper_evidence_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = evaluate_paper_stability(
                tmpdir,
                "BTC/USDT",
                "15m",
                PaperStabilityConfig(min_days=14, min_trades=20),
            )

        self.assertEqual("BLOCKED", report.status)
        self.assertIn("observed_days 0 < required 14", report.blockers)
        self.assertIn("trade_count 0 < required 20", report.blockers)

    def test_accepts_stable_paper_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_paper_fixture(root, trade_count=20, day_count=14)

            report = evaluate_paper_stability(
                root,
                "BTC/USDT",
                "15m",
                PaperStabilityConfig(min_days=14, min_trades=20),
            )

        self.assertEqual("PAPER_STABLE", report.status)
        self.assertEqual(14, report.observed_days)
        self.assertEqual(20, report.trade_count)
        self.assertAlmostEqual(20.0, report.rejected_order_pct)
        self.assertEqual([], report.blockers)

    def test_blocks_on_critical_audit_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_paper_fixture(root, trade_count=20, day_count=14)
            JsonlAuditLogger(root).write(
                "cycle_failed",
                "paper run crashed",
                level="ERROR",
                symbol="BTC/USDT",
            )

            report = evaluate_paper_stability(root, "BTC/USDT", "15m")

        self.assertEqual("BLOCKED", report.status)
        self.assertEqual(1, report.critical_error_count)
        self.assertIn("critical_error_count 1 > allowed 0", report.blockers)

    def test_saves_report_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_paper_fixture(root, trade_count=20, day_count=14)
            report = evaluate_paper_stability(root, "BTC/USDT", "15m")
            path = save_paper_stability_report(report, root)

            self.assertTrue(path.exists())
            self.assertIn('"status": "PAPER_STABLE"', path.read_text(encoding="utf-8"))


def _write_paper_fixture(root: Path, trade_count: int, day_count: int) -> None:
    base = root / "paper" / "BTC_USDT" / "15m"
    base.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    account_rows = []
    for day in range(day_count):
        account_rows.append(
            {
                "open_time_ms": _ms(start + timedelta(days=day)),
                "equity": 1000 + day,
                "day_start_equity": 1000 + day,
                "month_start_equity": 1000,
                "open_positions": 0,
                "consecutive_losses_today": 0,
                "trading_status": "ACTIVE",
                "status_reason": "",
            }
        )
    _write_csv(base / "account.csv", account_rows)

    orders = []
    trades = []
    for index in range(trade_count):
        entry = start + timedelta(days=index % day_count, minutes=index)
        exit_at = entry + timedelta(minutes=15)
        status = "REJECTED" if index % 5 == 0 else "FILLED"
        orders.append(
            {
                "symbol": "BTC/USDT",
                "timeframe": "15m",
                "open_time_ms": _ms(entry),
                "side": "buy",
                "action": "BUY",
                "price": 100.0,
                "quantity": 0.1,
                "notional": 10.0,
                "fee": 0.01,
                "status": status,
                "reason": "fixture",
            }
        )
        trades.append(
            {
                "symbol": "BTC/USDT",
                "timeframe": "15m",
                "entry_time_ms": _ms(entry),
                "exit_time_ms": _ms(exit_at),
                "entry_price": 100.0,
                "exit_price": 101.0,
                "quantity": 0.1,
                "gross_pnl": 0.1,
                "fees": 0.02,
                "net_pnl": 0.08,
                "exit_reason": "take_profit",
            }
        )
    _write_csv(base / "orders.csv", orders)
    _write_csv(base / "trades.csv", trades)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


if __name__ == "__main__":
    unittest.main()
