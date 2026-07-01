from pathlib import Path
import unittest


class ContinuousSkillRoadmapTest(unittest.TestCase):
    def test_roadmap_defines_learning_loop_and_guardrails(self) -> None:
        roadmap = Path("docs/continuous-skill-roadmap.md").read_text(encoding="utf-8")

        self.assertIn("Learning Loop", roadmap)
        self.assertIn("Capture data", roadmap)
        self.assertIn("Backtest dan walk-forward", roadmap)
        self.assertIn("Paper campaign", roadmap)
        self.assertIn("Evidence gate", roadmap)
        self.assertIn("Tidak ada jalur `AI recommendation -> live order`", roadmap)
        self.assertIn("Real live tetap locked", roadmap)

    def test_roadmap_has_metrics_and_card_checklist(self) -> None:
        roadmap = Path("docs/continuous-skill-roadmap.md").read_text(encoding="utf-8")

        for phrase in [
            "expectancy",
            "profit factor",
            "max drawdown",
            "mistake tag",
            "Mandatory Card Checklist",
            "Data apa yang dicapture?",
            "Test apa yang membuktikan guardrail tetap aman?",
        ]:
            self.assertIn(phrase, roadmap)

    def test_operating_manual_links_to_roadmap(self) -> None:
        manual = Path("docs/operating-manual.md").read_text(encoding="utf-8")

        self.assertIn("continuous-skill-roadmap", manual)


if __name__ == "__main__":
    unittest.main()
