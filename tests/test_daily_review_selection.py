import unittest

from core.review_scheduler import select_daily_reviews


class DailyReviewSelectionTests(unittest.TestCase):
    def setUp(self):
        self.reviews = [
            {"problem_id": "977", "priority_score": 10},
            {"problem_id": "704", "priority_score": 8},
            {"problem_id": "59", "priority_score": 5},
            {"problem_id": "24", "priority_score": 3}
        ]

    def test_plan_day_limits_reviews_and_avoids_duplicate_problem(self):
        result = select_daily_reviews(
            self.reviews,
            today_problem_ids=["24"],
            task_type="new"
        )

        self.assertEqual(
            ["977", "704"],
            [item["problem_id"] for item in result["selected"]]
        )
        self.assertEqual(4, result["due_count"])
        self.assertEqual(2, len(result["deferred"]))
        reasons = {
            item["problem_id"]: item["deferred_reason"]
            for item in result["deferred"]
        }
        self.assertEqual("已由今日计划覆盖", reasons["24"])
        self.assertEqual("超过今日复习容量", reasons["59"])

    def test_day_without_new_problem_can_show_three_reviews(self):
        result = select_daily_reviews(
            self.reviews,
            today_problem_ids=[],
            task_type=""
        )
        self.assertEqual(3, len(result["selected"]))
        self.assertEqual(1, len(result["deferred"]))

    def test_review_and_summary_days_keep_focus_on_stage_task(self):
        for task_type in ("review_day", "summary"):
            with self.subTest(task_type=task_type):
                result = select_daily_reviews(
                    self.reviews,
                    task_type=task_type
                )
                self.assertEqual([], result["selected"])
                self.assertEqual(4, len(result["deferred"]))


if __name__ == "__main__":
    unittest.main()
