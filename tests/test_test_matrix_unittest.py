from pathlib import Path
import unittest


class TestMatrixDocumentTest(unittest.TestCase):
    def test_matrix_mentions_critical_modules_and_commands(self) -> None:
        matrix = Path("docs/test-matrix.md").read_text(encoding="utf-8")

        required_terms = [
            "python -m unittest discover",
            "validate-security",
            "live-readiness-report",
            "Config safety",
            "Risk manager",
            "Paper simulator",
            "Execution sandbox",
            "Kill switch",
            "AI guardrails",
        ]
        for term in required_terms:
            self.assertIn(term, matrix)

    def test_operating_manual_links_test_matrix(self) -> None:
        manual = Path("docs/operating-manual.md").read_text(encoding="utf-8")

        self.assertIn("docs/test-matrix.md", manual)


if __name__ == "__main__":
    unittest.main()
