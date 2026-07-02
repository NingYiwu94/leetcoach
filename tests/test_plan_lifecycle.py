import json
import tempfile
import unittest
from pathlib import Path

import planning.plan_task_state as plan_task_state
from planning.plan_phase import get_self_paced_plan_phase
from planning.plan_task_state import (
    complete_milestone_task,
    get_completed_milestone_ids,
    get_plan_milestones
)


def build_plan(week=1, activated_at="2026-06-15 09:00:00"):
    days = {}
    for day_index, problem_id in enumerate(
        ["704", "27", "977", "209", "59"],
        start=1
    ):
        days[str(day_index)] = {
            "problems": [problem_id],
            "goal": f"完成 {problem_id}",
            "topic": f"题目 {problem_id}",
            "task_type": "new"
        }
    days["6"] = {
        "problems": [],
        "goal": "重做核心题",
        "topic": "阶段复习",
        "task_type": "review_day"
    }
    days["7"] = {
        "problems": [],
        "goal": "整理模板与错因",
        "topic": "阶段总结",
        "task_type": "summary"
    }
    return {
        "week": week,
        "start_date": "2026-06-15",
        "activated_at": activated_at,
        "days": days
    }


class PlanLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_state_path = plan_task_state.PLAN_TASK_STATE_PATH
        plan_task_state.PLAN_TASK_STATE_PATH = (
            Path(self.temp_dir.name) / "plan_task_state.json"
        )

    def tearDown(self):
        plan_task_state.PLAN_TASK_STATE_PATH = self.original_state_path
        self.temp_dir.cleanup()

    def test_five_problems_do_not_skip_review_and_summary(self):
        plan = build_plan()
        completed_problems = {"704", "27", "977", "209", "59"}

        phase = get_self_paced_plan_phase(
            plan,
            completed_problems,
            set()
        )
        self.assertEqual("active", phase["status"])
        self.assertEqual(6, phase["day_index"])

        milestones = get_plan_milestones(plan)
        phase = get_self_paced_plan_phase(
            plan,
            completed_problems,
            {milestones[0]["task_id"]}
        )
        self.assertEqual("active", phase["status"])
        self.assertEqual(7, phase["day_index"])

        phase = get_self_paced_plan_phase(
            plan,
            completed_problems,
            {item["task_id"] for item in milestones}
        )
        self.assertEqual("completed", phase["status"])
        self.assertTrue(phase["all_tasks_completed"])

    def test_milestone_completion_is_persisted_and_plan_scoped(self):
        plan = build_plan()
        review_task = get_plan_milestones(plan)[0]

        self.assertTrue(complete_milestone_task(review_task, plan))
        self.assertIn(
            review_task["task_id"],
            get_completed_milestone_ids(plan)
        )

        next_plan = build_plan(
            week=2,
            activated_at="2026-06-15 10:00:00"
        )
        self.assertEqual(set(), get_completed_milestone_ids(next_plan))

        saved = json.loads(
            plan_task_state.PLAN_TASK_STATE_PATH.read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(1, len(saved))
        self.assertTrue(saved[0]["completed"])

    def test_obsolete_state_does_not_inflate_current_progress(self):
        plan = build_plan()
        state = [{
            "plan_key": plan_task_state.get_plan_key(plan),
            "task_id": "obsolete-task",
            "completed": True
        }]
        self.assertEqual(
            set(),
            get_completed_milestone_ids(plan, state=state)
        )


if __name__ == "__main__":
    unittest.main()
