import unittest
from unittest.mock import patch

from app.task_board import complete_task


class StageReviewCompletionTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "week": 1,
            "start_date": "2026-06-15"
        }
        self.task = {
            "task_id": "stage-review",
            "kind": "milestone",
            "task_type": "review_day",
            "title": "本周核心题复习",
            "review_problems": ["704", "27", "977"],
            "review_results": {
                "704": "independent",
                "27": "assisted",
                "977": "not_mastered"
            }
        }

    def test_all_problem_results_are_saved_before_milestone(self):
        with (
            patch(
                "app.task_board.record_stage_review_results",
                return_value=True
            ) as save_results,
            patch(
                "app.task_board.complete_milestone_task",
                return_value=True
            ) as complete_milestone
        ):
            result = complete_task(self.task, self.plan)

        self.assertTrue(result["success"])
        save_results.assert_called_once_with(
            {
                "704": "independent",
                "27": "assisted",
                "977": "not_mastered"
            },
            assessment_id="stage-review"
        )
        complete_milestone.assert_called_once_with(self.task, self.plan)

    def test_missing_result_prevents_stage_completion(self):
        task = dict(self.task)
        task["review_results"] = {"704": "independent"}
        with patch(
            "app.task_board.complete_milestone_task"
        ) as complete_milestone:
            result = complete_task(task, self.plan)

        self.assertFalse(result["success"])
        complete_milestone.assert_not_called()

    def test_summary_is_generated_when_not_supplied(self):
        task = {
            "task_id": "summary",
            "kind": "milestone",
            "task_type": "summary",
            "title": "周总结"
        }
        generated = {"week": 1, "conclusion": "完成"}
        with (
            patch(
                "app.task_board.generate_stage_summary",
                return_value=generated
            ) as generate,
            patch(
                "app.task_board.complete_milestone_task",
                return_value=True
            ) as complete_milestone
        ):
            result = complete_task(task, self.plan)

        self.assertTrue(result["success"])
        generate.assert_called_once_with(self.plan)
        saved_task = complete_milestone.call_args.args[0]
        self.assertEqual(generated, saved_task["stage_summary"])


if __name__ == "__main__":
    unittest.main()
