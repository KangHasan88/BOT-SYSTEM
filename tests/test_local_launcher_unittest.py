from __future__ import annotations

import unittest
from pathlib import Path


class LocalLauncherTest(unittest.TestCase):
    def test_launcher_files_exist(self) -> None:
        self.assertTrue(Path("start-bot-web.cmd").exists())
        self.assertTrue(Path("scripts/start-local-orchestrator.ps1").exists())
        self.assertTrue(Path("scripts/stop-local-orchestrator.ps1").exists())

    def test_cmd_launcher_points_to_powershell_script(self) -> None:
        text = Path("start-bot-web.cmd").read_text(encoding="utf-8")

        self.assertIn("scripts\\start-local-orchestrator.ps1", text)
        self.assertIn("ExecutionPolicy Bypass", text)

    def test_powershell_launcher_tracks_pid_and_health_check(self) -> None:
        text = Path("scripts/start-local-orchestrator.ps1").read_text(encoding="utf-8")

        self.assertIn("serve-orchestrator", text)
        self.assertIn("/api/setup", text)
        self.assertIn("local-web.pid", text)
        self.assertIn("local-web.out.log", text)
        self.assertIn("local-web.err.log", text)

    def test_launcher_does_not_expose_live_trading_commands(self) -> None:
        combined = "\n".join(
            [
                Path("start-bot-web.cmd").read_text(encoding="utf-8"),
                Path("scripts/start-local-orchestrator.ps1").read_text(encoding="utf-8"),
                Path("scripts/stop-local-orchestrator.ps1").read_text(encoding="utf-8"),
            ]
        ).lower()

        self.assertNotIn("buy", combined)
        self.assertNotIn("sell", combined)
        self.assertNotIn("place_live_order", combined)
        self.assertNotIn("approved_live = true", combined)


if __name__ == "__main__":
    unittest.main()
