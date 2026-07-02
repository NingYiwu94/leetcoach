import unittest

from ai.ai_plan_generator import (
    analyze_user_level,
    validate_ai_week_plan
)
from core.learning_analyzer import analyze_learning_patterns
from core.learning_curriculum import build_plan_scaffold, select_current_topic


PROBLEM_BANK = {
    "704": {"title": "二分查找", "difficulty": "Easy"},
    "27": {"title": "移除元素", "difficulty": "Easy"},
    "977": {"title": "有序数组的平方", "difficulty": "Easy"},
    "209": {"title": "长度最小的子数组", "difficulty": "Medium"},
    "59": {"title": "螺旋矩阵 II", "difficulty": "Medium"},
    "203": {"title": "移除链表元素", "difficulty": "Easy"}
}


def completed_array_records():
    return [
        {
            "problem_id": problem_id,
            "date": "2026-06-15",
            "status": "AC"
        }
        for problem_id in ["704", "27", "977", "209", "59"]
    ]


def mastery_review(problem_id, result, completed_at):
    labels = {
        "independent": "独立写出",
        "assisted": "看提示写出",
        "not_mastered": "仍未掌握"
    }
    return {
        "problem_id": problem_id,
        "done": True,
        "mastery_result": result,
        "mastery_label": labels[result],
        "completed_at": completed_at
    }


class AdaptivePlanningTests(unittest.TestCase):
    def test_not_mastered_blocks_topic_advance(self):
        records = completed_array_records()
        reviews = [
            mastery_review(
                "704",
                "not_mastered",
                "2026-06-15 10:00:00"
            )
        ]
        analysis = analyze_learning_patterns(
            records,
            PROBLEM_BANK,
            reviews
        )
        topic = select_current_topic(
            records,
            PROBLEM_BANK,
            analysis["review_mastery"]
        )

        self.assertEqual("array", topic["id"])
        self.assertEqual(1, analysis["review_not_mastered_count"])

    def test_assisted_keeps_topic_for_independent_rewrite(self):
        records = completed_array_records()
        reviews = [
            mastery_review(
                "977",
                "assisted",
                "2026-06-15 10:00:00"
            )
        ]
        profile = analyze_user_level(records, PROBLEM_BANK, reviews)
        scaffold = build_plan_scaffold(
            records,
            PROBLEM_BANK,
            profile,
            reviews
        )

        self.assertEqual("array", scaffold["curriculum_topic_id"])
        self.assertEqual(["977"], scaffold["mastery_review_ids"])
        self.assertEqual("977", scaffold["days"]["1"]["problems"][0])
        self.assertEqual("review", scaffold["days"]["1"]["task_type"])
        self.assertLessEqual(profile["weekly_problem_target"], 5)

    def test_latest_independent_result_clears_old_block(self):
        records = completed_array_records()
        reviews = [
            mastery_review(
                "704",
                "not_mastered",
                "2026-06-14 10:00:00"
            ),
            mastery_review(
                "704",
                "independent",
                "2026-06-15 10:00:00"
            )
        ]
        analysis = analyze_learning_patterns(
            records,
            PROBLEM_BANK,
            reviews
        )
        topic = select_current_topic(
            records,
            PROBLEM_BANK,
            analysis["review_mastery"]
        )
        profile = analyze_user_level(records, PROBLEM_BANK, reviews)

        self.assertEqual("linked_list", topic["id"])
        self.assertEqual(0, analysis["review_not_mastered_count"])
        self.assertEqual(1, profile["review_mastery_counts"]["independent"])
        self.assertEqual(0, profile["review_mastery_counts"]["not_mastered"])

    def test_adaptive_fields_survive_plan_validation(self):
        plan = validate_ai_week_plan({
            "week": 2,
            "title": "数组巩固周",
            "start_date": "2026-06-16",
            "days": {},
            "mastery_review_ids": ["704"],
            "priority_review_ids": ["704", "977"],
            "adaptive_reason": "最近复习仍未掌握，减少新题。"
        })
        self.assertEqual(["704"], plan["mastery_review_ids"])
        self.assertEqual(
            ["704", "977"],
            plan["priority_review_ids"]
        )
        self.assertIn("减少新题", plan["adaptive_reason"])


if __name__ == "__main__":
    unittest.main()
