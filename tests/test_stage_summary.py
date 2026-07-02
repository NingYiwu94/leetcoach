import tempfile
import unittest
from pathlib import Path

import planning.plan_task_state as plan_task_state
from ai.ai_plan_generator import get_recent_stage_summaries
from planning.plan_task_state import (
    complete_milestone_task,
    get_stage_summaries
)
from core.stage_summary import format_stage_summary, generate_stage_summary


PLAN = {
    "week": 1,
    "title": "数组基础周",
    "weekly_theme": "数组与指针",
    "start_date": "2026-06-15",
    "days": {
        "1": {"problems": ["704"]},
        "2": {"problems": ["27"]},
        "6": {
            "problems": [],
            "task_type": "review_day",
            "review_problems": ["704", "27"]
        },
        "7": {
            "problems": [],
            "task_type": "summary",
            "topic": "周总结"
        }
    }
}

PROBLEM_BANK = {
    "704": {"title": "二分查找"},
    "27": {"title": "移除元素"}
}


class StageSummaryTests(unittest.TestCase):
    def test_summary_uses_completion_and_latest_mastery(self):
        records = [
            {
                "problem_id": "704",
                "date": "2026-06-15",
                "status": "AC",
                "plan_week": 1,
                "plan_start_date": "2026-06-15"
            },
            {
                "problem_id": "27",
                "date": "2026-06-15",
                "status": "AC",
                "plan_week": 1,
                "plan_start_date": "2026-06-15"
            }
        ]
        reviews = [
            {
                "problem_id": "704",
                "done": True,
                "mastery_result": "independent",
                "mastery_label": "独立写出",
                "completed_at": "2026-06-15 10:00:00"
            },
            {
                "problem_id": "27",
                "done": True,
                "mastery_result": "assisted",
                "mastery_label": "看提示写出",
                "completed_at": "2026-06-15 10:01:00"
            }
        ]

        summary = generate_stage_summary(
            PLAN,
            records,
            reviews,
            PROBLEM_BANK
        )

        self.assertEqual(2, summary["completed_count"])
        self.assertEqual(["704"], summary["mastery"]["independent"])
        self.assertEqual(["27"], summary["mastery"]["assisted"])
        self.assertEqual(["27"], summary["needs_review"])
        self.assertIn("稳定性", summary["conclusion"])
        text = format_stage_summary(summary, PROBLEM_BANK)
        self.assertIn("704 二分查找", text)
        self.assertIn("27 移除元素", text)

    def test_summary_is_saved_with_milestone(self):
        summary = {
            "generated_at": "2026-06-15 11:00:00",
            "week": 1,
            "conclusion": "本阶段已完成"
        }
        task = {
            "task_id": "summary-task",
            "kind": "milestone",
            "day_index": 7,
            "task_type": "summary",
            "title": "周总结",
            "stage_summary": summary
        }

        with tempfile.TemporaryDirectory() as folder:
            original_path = plan_task_state.PLAN_TASK_STATE_PATH
            plan_task_state.PLAN_TASK_STATE_PATH = (
                Path(folder) / "plan_task_state.json"
            )
            try:
                self.assertTrue(complete_milestone_task(task, PLAN))
                self.assertEqual([summary], get_stage_summaries())
            finally:
                plan_task_state.PLAN_TASK_STATE_PATH = original_path

    def test_unfinished_plan_is_not_called_basically_complete(self):
        summary = generate_stage_summary(
            PLAN,
            [{
                "problem_id": "704",
                "date": "2026-06-15",
                "status": "AC",
                "plan_week": 1,
                "plan_start_date": "2026-06-15"
            }],
            [],
            PROBLEM_BANK
        )
        self.assertIn("尚未完成", summary["conclusion"])
        self.assertEqual(["27"], summary["needs_review"])

    def test_recent_summaries_are_sorted_and_limited(self):
        state = [
            {"stage_summary": {"generated_at": "2026-06-10", "week": 1}},
            {"stage_summary": {"generated_at": "2026-06-12", "week": 3}},
            {"stage_summary": {"generated_at": "2026-06-11", "week": 2}},
            {"completed": True}
        ]
        summaries = get_recent_stage_summaries(state, limit=2)
        self.assertEqual([2, 3], [item["week"] for item in summaries])


if __name__ == "__main__":
    unittest.main()
