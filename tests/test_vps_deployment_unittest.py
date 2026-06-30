from pathlib import Path
import unittest

from trading_bot.config import load_config


ROOT = Path(__file__).resolve().parents[1]


class VpsDeploymentTest(unittest.TestCase):
    def test_vps_config_is_paper_only(self) -> None:
        config = load_config(ROOT / "config" / "bot.vps.sample.toml")

        self.assertEqual(config.mode, "paper")
        self.assertFalse(config.live_enabled)
        self.assertFalse(config.approved_live)
        self.assertEqual(config.data_root, "/var/lib/trading-bot/data")

    def test_systemd_service_uses_tradingbot_user_and_no_live_command(self) -> None:
        service = (ROOT / "deploy" / "systemd" / "trading-bot-cycle.service").read_text(encoding="utf-8")

        self.assertIn("User=tradingbot", service)
        self.assertIn("run-cycle", service)
        self.assertIn("--sync-latest", service)
        self.assertNotIn("live", service.lower())

    def test_timer_runs_every_15_minutes(self) -> None:
        timer = (ROOT / "deploy" / "systemd" / "trading-bot-cycle.timer").read_text(encoding="utf-8")

        self.assertIn("OnUnitActiveSec=15min", timer)
        self.assertIn("Persistent=true", timer)

    def test_smoke_script_validates_config_and_cycle(self) -> None:
        smoke = (ROOT / "deploy" / "smoke-vps.sh").read_text(encoding="utf-8")

        self.assertIn("validate-config", smoke)
        self.assertIn("run-cycle", smoke)
        self.assertIn("build-dashboard", smoke)


if __name__ == "__main__":
    unittest.main()
