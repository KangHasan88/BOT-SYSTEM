from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.qa import PaperCampaignConfig, evaluate_paper_campaign, save_paper_campaign_report


class PaperCampaignTest(unittest.TestCase):
    def test_campaign_blocks_until_minimum_evidence_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            report = evaluate_paper_campaign(config, PaperCampaignConfig(min_days=14, preferred_days=28, min_trades=20))

        self.assertEqual("PAPER_CAMPAIGN_COLLECTING", report.status)
        self.assertEqual(1, report.pairs_checked)
        self.assertEqual(0, report.stable_pair_count)
        self.assertGreater(len(report.blockers), 0)
        self.assertLess(report.completion_pct, 100.0)

    def test_campaign_accepts_stable_paper_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_paper_fixture(data_root, trade_count=20, day_count=14)
            config = load_config(config_path)

            report = evaluate_paper_campaign(config, PaperCampaignConfig(min_days=14, preferred_days=28, min_trades=20))
            path = save_paper_campaign_report(report, config.data_root)
            path_exists = path.exists()

        self.assertTrue(path_exists)
        self.assertEqual("PAPER_CAMPAIGN_READY", report.status)
        self.assertEqual(1, report.stable_pair_count)
        self.assertEqual(20, report.total_trade_count)
        self.assertEqual(100.0, report.completion_pct)
        self.assertEqual([], report.blockers)


def _write_config(path: Path, data_root: Path) -> None:
    path.write_text(
        '[bot]\nmode = "research"\nlive_enabled = false\napproved_live = false\ntimezone = "Asia/Jakarta"\n'
        '[market]\ntype = "crypto_spot"\nsymbols = ["BTC/USDT"]\ntimeframes = ["15m"]\n'
        '[data]\nroot = "'
        + str(data_root).replace("\\", "\\\\")
        + '"\nprovider = "binance_public"\n'
        '[risk]\nmax_open_positions = 1\n'
        '[sessions]\nentry_windows_wib = ["08:00-11:00"]\nalways_collect_data = true\n',
        encoding="utf-8",
    )


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
        orders.append(
            {
                "symbol": "BTC/USDT",
                "timeframe": "15m",
                "open_time_ms": _ms(entry),
                "side": "buy",
                "action": "OPEN",
                "price": 100.0,
                "quantity": 0.1,
                "notional": 10.0,
                "fee": 0.01,
                "status": "FILLED",
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
