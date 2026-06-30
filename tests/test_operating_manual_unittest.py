from pathlib import Path
import unittest


class OperatingManualTest(unittest.TestCase):
    def test_manual_mentions_critical_operations(self) -> None:
        manual = Path("docs/operating-manual.md").read_text(encoding="utf-8")

        self.assertIn("run-cycle", manual)
        self.assertIn("kill-switch", manual)
        self.assertIn("live-readiness-report", manual)
        self.assertIn("vps-deployment", manual)
        self.assertIn("unittest discover", manual)


if __name__ == "__main__":
    unittest.main()
