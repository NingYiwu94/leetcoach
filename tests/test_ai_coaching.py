import unittest
from unittest.mock import patch

from ai.ai_hint import infer_hint_level
from ai.ai_plan_generator import build_coaching_brief


class AiCoachingTests(unittest.TestCase):
    @patch("ai.ai_hint._problem_context")
    def test_hint_depth_becomes_deeper_after_repeated_failure(self, context):
        context.return_value = {
            "failed_count": 2,
            "assisted_count": 0,
            "attempt_count": 2,
            "latest_review_result": "",
        }

        self.assertEqual(infer_hint_level("977", "指针怎么移动"), "3")

    @patch("ai.ai_hint._problem_context")
    def test_hint_depth_starts_light_for_new_problem(self, context):
        context.return_value = {
            "failed_count": 0,
            "assisted_count": 0,
            "attempt_count": 0,
            "latest_review_result": "",
        }

        self.assertEqual(infer_hint_level("977", "我应该先观察什么"), "1")

    def test_coaching_brief_marks_repeated_hint_problem(self):
        brief = build_coaching_brief(
            learner_profile={"level": "beginner", "label": "新手"},
            learning_analysis={
                "learning_status": "独立解题稳定性需要加强",
                "main_weakness": "双指针",
                "risky_problems": [],
                "review_not_mastered_count": 0,
                "assisted_count": 1,
            },
            reviews=[],
            hint_logs=[
                {"problem_id": "977"},
                {"problem_id": "977"},
            ],
        )

        self.assertEqual(brief["repeated_hint_problems"], ["977"])
        self.assertTrue(
            any("无提示重写" in item or "独立重写" in item
                for item in brief["planning_constraints"])
        )


if __name__ == "__main__":
    unittest.main()
