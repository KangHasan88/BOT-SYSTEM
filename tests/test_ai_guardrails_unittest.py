import unittest

from trading_bot.ai_guardrails import AiRecommendation, evaluate_ai_recommendation


class AiGuardrailsTest(unittest.TestCase):
    def test_research_experiment_is_accepted(self) -> None:
        decision = evaluate_ai_recommendation(
            AiRecommendation(
                action="experiment_proposal",
                title="Tighten RSI filter",
                rationale="Post-trade losses cluster when RSI is weak.",
                proposed_change="Test min RSI 50 instead of 45.",
            )
        )

        self.assertEqual(decision.status, "ACCEPTED_FOR_RESEARCH")

    def test_live_order_is_blocked(self) -> None:
        decision = evaluate_ai_recommendation(
            AiRecommendation(
                action="experiment_proposal",
                title="Place live order",
                rationale="Looks strong.",
                proposed_change="place_order BTC/USDT now",
            )
        )

        self.assertEqual(decision.status, "BLOCKED")
        self.assertIn("bypass", decision.reason)

    def test_must_require_backtest_and_paper(self) -> None:
        decision = evaluate_ai_recommendation(
            AiRecommendation(
                action="parameter_hypothesis",
                title="Skip validation",
                rationale="Fast idea.",
                proposed_change="Use new EMA periods",
                requires_backtest=False,
            )
        )

        self.assertEqual(decision.status, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
