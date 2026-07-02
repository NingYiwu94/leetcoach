import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import core.reviewer as reviewer
from core.review_scheduler import schedule_follow_up_review


class ReviewMasteryTests(unittest.TestCase):
    def setUp(self):
        self.completed_review = {
            "problem_id": "704",
            "review_round": 1,
            "completed_at": "2026-06-15 10:00:00"
        }
        self.records = [{
            "problem_id": "704",
            "date": "2026-06-15",
            "status": "AC"
        }]

    def build_follow_up(self, mastery_result):
        reviews = []
        with patch("core.review_scheduler.date") as mocked_date:
            mocked_date.today.return_value = __import__(
                "datetime"
            ).date(2026, 6, 15)
            result = schedule_follow_up_review(
                reviews,
                self.completed_review,
                self.records,
                mastery_result=mastery_result
            )
        self.assertEqual([result], reviews)
        return result

    def test_independent_review_advances_round_with_long_interval(self):
        result = self.build_follow_up("independent")
        self.assertEqual(2, result["review_round"])
        self.assertEqual(7, result["interval_days"])
        self.assertEqual("2026-06-22", result["next_review_date"])

    def test_assisted_review_advances_with_short_interval(self):
        result = self.build_follow_up("assisted")
        self.assertEqual(2, result["review_round"])
        self.assertEqual(3, result["interval_days"])
        self.assertEqual("2026-06-18", result["next_review_date"])

    def test_not_mastered_retries_same_round_tomorrow(self):
        result = self.build_follow_up("not_mastered")
        self.assertEqual(1, result["review_round"])
        self.assertEqual(1, result["interval_days"])
        self.assertEqual("2026-06-16", result["next_review_date"])
        self.assertEqual(
            "not_mastered",
            result["previous_mastery_result"]
        )

    def test_reviewer_persists_mastery_and_follow_up(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reviews_path = root / "reviews.json"
            records_path = root / "records.json"
            reviews_path.write_text(
                json.dumps([{
                    "problem_id": "704",
                    "next_review_date": "2026-06-15",
                    "reason": "测试复习",
                    "done": False,
                    "review_round": 1
                }], ensure_ascii=False),
                encoding="utf-8"
            )
            records_path.write_text(
                json.dumps(self.records, ensure_ascii=False),
                encoding="utf-8"
            )

            with (
                patch.object(reviewer, "REVIEWS_PATH", reviews_path),
                patch.object(reviewer, "RECORDS_PATH", records_path),
                patch("core.review_scheduler.date") as mocked_date
            ):
                mocked_date.today.return_value = __import__(
                    "datetime"
                ).date(2026, 6, 15)
                success = reviewer.mark_review_done(
                    "704",
                    "not_mastered"
                )

            self.assertTrue(success)
            saved = json.loads(
                reviews_path.read_text(encoding="utf-8")
            )
            self.assertEqual(2, len(saved))
            self.assertTrue(saved[0]["done"])
            self.assertEqual(
                "not_mastered",
                saved[0]["mastery_result"]
            )
            self.assertFalse(saved[1]["done"])
            self.assertEqual(1, saved[1]["review_round"])
            self.assertEqual(1, saved[1]["interval_days"])

    def test_stage_review_creates_assessment_when_no_task_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reviews_path = root / "reviews.json"
            records_path = root / "records.json"
            reviews_path.write_text("[]", encoding="utf-8")
            records_path.write_text(
                json.dumps(self.records, ensure_ascii=False),
                encoding="utf-8"
            )

            with (
                patch.object(reviewer, "REVIEWS_PATH", reviews_path),
                patch.object(reviewer, "RECORDS_PATH", records_path)
            ):
                success = reviewer.mark_review_done(
                    "704",
                    "assisted",
                    create_if_missing=True
                )

            self.assertTrue(success)
            saved = json.loads(
                reviews_path.read_text(encoding="utf-8")
            )
            self.assertEqual(2, len(saved))
            self.assertTrue(saved[0]["done"])
            self.assertEqual("stage_review", saved[0]["source"])
            self.assertEqual("assisted", saved[0]["mastery_result"])
            self.assertFalse(saved[1]["done"])
            self.assertEqual(3, saved[1]["interval_days"])

    def test_stage_review_results_are_saved_in_one_batch(self):
        reviews = [
            {
                "problem_id": "704",
                "next_review_date": "2026-06-15",
                "reason": "复习",
                "done": False,
                "review_round": 1
            },
            {
                "problem_id": "27",
                "next_review_date": "2026-06-15",
                "reason": "复习",
                "done": False,
                "review_round": 1
            }
        ]
        records = [
            {"problem_id": "704", "date": "2026-06-15", "status": "AC"},
            {"problem_id": "27", "date": "2026-06-15", "status": "AC"}
        ]
        with (
            patch.object(
                reviewer,
                "load_json",
                side_effect=[reviews, records]
            ),
            patch.object(reviewer, "save_json") as save_json
        ):
            success = reviewer.record_stage_review_results({
                "704": "independent",
                "27": "not_mastered"
            }, assessment_id="week-1-review")

        self.assertTrue(success)
        save_json.assert_called_once()
        saved_reviews = save_json.call_args.args[1]
        completed = [
            item for item in saved_reviews if item.get("done")
        ]
        self.assertEqual(2, len(completed))
        self.assertEqual(
            {"independent", "not_mastered"},
            {item["mastery_result"] for item in completed}
        )
        self.assertEqual(
            {"week-1-review"},
            {item["stage_assessment_id"] for item in completed}
        )

    def test_repeated_stage_assessment_is_idempotent(self):
        reviews = [
            {
                "problem_id": "704",
                "done": True,
                "mastery_result": "independent",
                "stage_assessment_id": "week-1-review"
            },
            {
                "problem_id": "27",
                "done": True,
                "mastery_result": "assisted",
                "stage_assessment_id": "week-1-review"
            },
            {
                "problem_id": "704",
                "done": False,
                "review_round": 2
            },
            {
                "problem_id": "27",
                "done": False,
                "review_round": 2
            }
        ]
        with (
            patch.object(
                reviewer,
                "load_json",
                side_effect=[reviews, self.records]
            ),
            patch.object(reviewer, "save_json") as save_json
        ):
            success = reviewer.record_stage_review_results(
                {
                    "704": "independent",
                    "27": "assisted"
                },
                assessment_id="week-1-review"
            )

        self.assertTrue(success)
        save_json.assert_not_called()
        self.assertFalse(reviews[2]["done"])
        self.assertFalse(reviews[3]["done"])


if __name__ == "__main__":
    unittest.main()
