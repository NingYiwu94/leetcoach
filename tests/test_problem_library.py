import unittest

from library.problem_library import get_problem_library_data, get_topic_detail


class ProblemLibraryTests(unittest.TestCase):
    def test_topic_catalog_controls_order_total_and_difficulty_denominator(self):
        topic_catalog = {
            "数组": {
                "total": 1900,
                "order": 1,
                "description": "数组基础",
                "difficulty_total": {
                    "Easy": 500,
                    "Medium": 1000,
                    "Hard": 400
                }
            },
            "链表": {
                "total": 260,
                "order": 2,
                "description": "链表基础",
                "difficulty_total": {
                    "Easy": 100,
                    "Medium": 120,
                    "Hard": 40
                }
            }
        }
        problem_bank = {
            "704": {
                "title": "二分查找",
                "difficulty": "Easy",
                "topic": "数组",
                "tags": ["二分查找"],
            },
            "977": {
                "title": "有序数组的平方",
                "difficulty": "Easy",
                "topic": "数组",
                "pattern": "双指针",
                "tags": ["数组", "双指针"],
            },
            "206": {
                "title": "反转链表",
                "difficulty": "Easy",
                "topic": "链表",
            },
        }
        records = [
            {
                "problem_id": "704",
                "status": "AC",
                "date": "2026-06-01",
                "source": "leetcode_auto_sync"
            },
            {
                "problem_id": "206",
                "status": "看提示后AC",
                "date": "2026-06-02",
                "source": "task_board"
            },
        ]

        data = get_problem_library_data(
            problem_bank=problem_bank,
            records=records,
            topic_catalog=topic_catalog
        )
        array_topic = get_topic_detail("数组", data)
        linked_topic = get_topic_detail("链表", data)

        self.assertEqual(2160, data["topic_total_sum"])
        self.assertEqual(2, data["completed_problem_count"])
        self.assertEqual(2, data["topic_count"])
        self.assertEqual("数组", data["topics"][0]["topic"])
        self.assertEqual(1900, array_topic["total"])
        self.assertEqual(1, array_topic["completed"])
        self.assertEqual(
            500,
            array_topic["difficulty_stats"]["Easy"]["catalog_total"]
        )
        self.assertEqual(1, array_topic["difficulty_stats"]["Easy"]["completed"])
        self.assertEqual(260, linked_topic["total"])
        self.assertEqual(1, linked_topic["completed"])

    def test_completed_record_not_in_problem_bank_counts_as_unclassified(self):
        topic_catalog = {
            "数组": {"total": 1900, "order": 1}
        }
        records = [
            {
                "problem_id": "9999",
                "title": "未知同步题",
                "status": "AC",
                "submit_time": "2026-06-03 10:00:00",
                "source": "leetcode_auto_sync"
            }
        ]

        data = get_problem_library_data(
            problem_bank={},
            records=records,
            topic_catalog=topic_catalog
        )
        unclassified = get_topic_detail("未分类", data)

        self.assertEqual(1, data["completed_problem_count"])
        self.assertEqual(1, data["unknown_completed_problem_count"])
        self.assertEqual(1, unclassified["completed"])
        self.assertEqual("leetcode_auto_sync", unclassified["completed_problems"][0]["source"])

    def test_unfinished_plan_problems_are_available_per_topic(self):
        topic_catalog = {
            "数组": {"total": 1900, "order": 1}
        }
        problem_bank = {
            "704": {
                "title": "二分查找",
                "difficulty": "Easy",
                "topic": "数组"
            }
        }
        week_plan = {
            "days": {
                "1": {"problems": ["704"]}
            }
        }

        data = get_problem_library_data(
            problem_bank=problem_bank,
            records=[],
            topic_catalog=topic_catalog,
            week_plan=week_plan
        )
        array_topic = get_topic_detail("数组", data)

        self.assertEqual(1, len(array_topic["unfinished_plan_problems"]))
        self.assertEqual("704", array_topic["unfinished_plan_problems"][0]["problem_id"])


if __name__ == "__main__":
    unittest.main()
