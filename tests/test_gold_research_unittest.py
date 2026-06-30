import unittest

from trading_bot.markets import build_gold_research_plan, is_gold_live_allowed


class GoldResearchTest(unittest.TestCase):
    def test_gold_is_research_only(self) -> None:
        plan = build_gold_research_plan()

        self.assertEqual(plan.status, "RESEARCH_ONLY")
        self.assertEqual(plan.instrument, "XAUUSD")
        self.assertEqual(plan.allowed_mode, "research")
        self.assertFalse(is_gold_live_allowed())

    def test_gold_requires_separate_evidence(self) -> None:
        plan = build_gold_research_plan()

        self.assertTrue(any("spread" in item for item in plan.required_evidence))
        self.assertTrue(any("not part of v1 live universe" in item for item in plan.blockers))


if __name__ == "__main__":
    unittest.main()
