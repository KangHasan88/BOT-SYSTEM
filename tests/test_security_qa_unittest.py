from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_bot.qa import generate_security_qa_report, save_security_qa_report


class SecurityQaTest(unittest.TestCase):
    def test_security_qa_passes_safe_env_and_clean_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_file = _write_env(root, "BOT_MODE=research\nBOT_LIVE_ENABLED=false\nAPI_WITHDRAWAL_PERMISSION=false\n")

            report = generate_security_qa_report(env_file, root)

        self.assertEqual("PASSED", report.status)
        self.assertTrue(all(check.status == "PASSED" for check in report.checks))
        self.assertEqual([], report.secret_findings)

    def test_security_qa_blocks_withdrawal_and_live_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_file = _write_env(
                root,
                "BOT_MODE=live\nBOT_LIVE_ENABLED=true\nBOT_APPROVED_LIVE=true\nAPI_WITHDRAWAL_PERMISSION=true\n",
            )

            report = generate_security_qa_report(env_file, root)

        self.assertEqual("BLOCKED", report.status)
        failed = {check.name for check in report.checks if check.status == "FAILED"}
        self.assertIn("env_security", failed)
        self.assertIn("withdrawal_disabled", failed)
        self.assertIn("live_blocked", failed)

    def test_security_qa_blocks_secret_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_file = _write_env(root, "BOT_MODE=research\nAPI_WITHDRAWAL_PERMISSION=false\n")
            (root / "leaked.txt").write_text(
                "EXCHANGE_API_SECRET=abcdefghijklmnopqrstuvwxyz123456\n",
                encoding="utf-8",
            )

            report = generate_security_qa_report(env_file, root)

        self.assertEqual("BLOCKED", report.status)
        self.assertEqual(1, len(report.secret_findings))
        self.assertIn("secret_scan", {check.name for check in report.checks if check.status == "FAILED"})

    def test_saves_security_qa_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_file = _write_env(root, "BOT_MODE=research\nAPI_WITHDRAWAL_PERMISSION=false\n")
            report = generate_security_qa_report(env_file, root)
            path = save_security_qa_report(report, root)

            self.assertTrue(path.exists())
            self.assertIn('"status": "PASSED"', path.read_text(encoding="utf-8"))


def _write_env(root: Path, content: str) -> Path:
    path = root / ".env"
    path.write_text(content, encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
