from pathlib import Path
import tempfile
import unittest

from trading_bot.security import load_env_file, scan_for_secrets, validate_env_security


class SecurityTest(unittest.TestCase):
    def test_env_example_is_safe(self) -> None:
        env = load_env_file(Path(".env.example"))
        report = validate_env_security(env)

        self.assertTrue(report.ok)
        self.assertEqual(report.errors, [])

    def test_withdrawal_permission_is_rejected(self) -> None:
        report = validate_env_security(
            {
                "BOT_MODE": "paper",
                "BOT_LIVE_ENABLED": "false",
                "BOT_APPROVED_LIVE": "false",
                "API_WITHDRAWAL_PERMISSION": "true",
            }
        )

        self.assertFalse(report.ok)
        self.assertIn("API_WITHDRAWAL_PERMISSION must be false", report.errors)

    def test_live_mode_is_rejected(self) -> None:
        report = validate_env_security(
            {
                "BOT_MODE": "live",
                "BOT_LIVE_ENABLED": "true",
                "BOT_APPROVED_LIVE": "true",
                "API_WITHDRAWAL_PERMISSION": "false",
            }
        )

        self.assertFalse(report.ok)
        self.assertTrue(any("live" in error for error in report.errors))

    def test_secret_scanner_finds_plain_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "bad.env").write_text(
                "EXCHANGE_API_SECRET=abcdefghijklmnopqrstuvwxyz123456\n",
                encoding="utf-8",
            )
            findings = scan_for_secrets(root, excludes=set())

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line_number, 1)

    def test_secret_scanner_ignores_blank_examples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "example.env").write_text("EXCHANGE_API_SECRET=\n", encoding="utf-8")
            findings = scan_for_secrets(root, excludes=set())

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
