from pathlib import Path
import unittest


class UxArchitectureDecisionTest(unittest.TestCase):
    def test_decision_record_documents_local_web_first(self) -> None:
        doc = Path("docs/ux-architecture-decision.md").read_text(encoding="utf-8")

        self.assertIn("local web", doc.lower())
        self.assertIn("localhost", doc)
        self.assertIn("Engine mode", doc)
        self.assertIn("Desktop app is explicitly postponed", doc)
        self.assertIn("Public internet exposure is explicitly rejected", doc)
        self.assertIn("cached status", doc)
        self.assertIn("Live action remains unavailable", doc)


if __name__ == "__main__":
    unittest.main()
