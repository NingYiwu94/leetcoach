import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import ai.ai_plan_generator as ai_plan_generator
class PlanActivationTests(unittest.TestCase):
    def test_confirmed_plan_starts_immediately(self):
        current_plan = {
            "week": 1,
            "title": "当前计划",
            "start_date": "2026-06-01",
            "days": {}
        }
        draft = {
            "week": 2,
            "title": "下一阶段",
            "start_date": "2099-01-01",
            "days": {
                "1": {
                    "problems": ["704"],
                    "goal": "练习二分查找",
                    "task_type": "new"
                }
            }
        }

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            current_path = root / "week_plan.json"
            next_path = root / "week_plan_next.json"
            archive_dir = root / "plan_archive"
            current_path.write_text(
                json.dumps(current_plan, ensure_ascii=False),
                encoding="utf-8"
            )
            next_path.write_text(
                json.dumps(draft, ensure_ascii=False),
                encoding="utf-8"
            )

            with (
                patch.object(
                    ai_plan_generator,
                    "CURRENT_PLAN_PATH",
                    current_path
                ),
                patch.object(
                    ai_plan_generator,
                    "NEXT_PLAN_PATH",
                    next_path
                ),
                patch.object(
                    ai_plan_generator,
                    "PLAN_ARCHIVE_DIR",
                    archive_dir
                ),
                patch.object(
                    ai_plan_generator,
                    "BASE_DIR",
                    root
                ),
                patch.object(
                    ai_plan_generator,
                    "clear_plan_review_state",
                    return_value=True
                )
            ):
                result = ai_plan_generator.apply_week_plan_next()

            self.assertTrue(result["success"])
            applied = json.loads(
                current_path.read_text(encoding="utf-8")
            )
            self.assertEqual(str(date.today()), applied["start_date"])
            self.assertEqual(
                "2099-01-01",
                applied["planned_start_date"]
            )
            self.assertEqual(
                "immediate_on_confirmation",
                applied["activation_mode"]
            )
            self.assertFalse(next_path.exists())
            self.assertEqual(1, len(list(archive_dir.glob("*.json"))))
            self.assertEqual(
                1,
                len(list(root.glob("week_plan_backup_*.json")))
            )


if __name__ == "__main__":
    unittest.main()
