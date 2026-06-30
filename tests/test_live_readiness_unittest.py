from pathlib import Path
import json
import tempfile
import unittest

from trading_bot.config import BotConfig
from trading_bot.readiness import evaluate_live_readiness, save_live_readiness_report


def config(root: str, approved_live: bool = False) -> BotConfig:
    return BotConfig(
        mode="paper",
        live_enabled=False,
        approved_live=approved_live,
        symbols=("BTC/USDT",),
        market_type="crypto_spot",
        timeframes=("15m",),
        data_root=root,
        data_provider="binance_public",
        max_open_positions=1,
        daily_max_loss_pct=1.0,
        monthly_max_drawdown_pct=5.0,
        entry_windows_wib=("08:00-11:00",),
        always_collect_data=True,
    )


class LiveReadinessTest(unittest.TestCase):
    def test_default_gate_is_blocked_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "BOT_MODE=paper\nBOT_LIVE_ENABLED=false\nBOT_APPROVED_LIVE=false\nAPI_WITHDRAWAL_PERMISSION=false\n",
                encoding="utf-8",
            )
            report = evaluate_live_readiness(config(temp_dir), env_file=env_path, scan_root=temp_dir)

        self.assertEqual(report.status, "BLOCKED")
        self.assertTrue(any(check.name == "backtest_gate" and check.status == "FAIL" for check in report.checks))

    def test_security_failure_blocks_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "BOT_MODE=paper\nBOT_LIVE_ENABLED=false\nBOT_APPROVED_LIVE=false\nAPI_WITHDRAWAL_PERMISSION=true\n",
                encoding="utf-8",
            )
            report = evaluate_live_readiness(config(temp_dir), env_file=env_path, scan_root=temp_dir)

        security = next(check for check in report.checks if check.name == "security_env_and_secret_scan")
        self.assertEqual(security.status, "FAIL")
        self.assertIn("API_WITHDRAWAL_PERMISSION", security.reason)

    def test_save_live_readiness_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "BOT_MODE=paper\nBOT_LIVE_ENABLED=false\nBOT_APPROVED_LIVE=false\nAPI_WITHDRAWAL_PERMISSION=false\n",
                encoding="utf-8",
            )
            report = evaluate_live_readiness(config(temp_dir), env_file=env_path, scan_root=temp_dir)
            path = save_live_readiness_report(report, temp_dir)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "BLOCKED")
        self.assertIn("checks", payload)


if __name__ == "__main__":
    unittest.main()
