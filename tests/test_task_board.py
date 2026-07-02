import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sync.browser_sync as browser_sync
import app.task_board as task_board
import sync.leetcode_sync as leetcode_sync
class TaskBoardTests(unittest.TestCase):
    def test_today_tasks_include_plan_and_review_reasons(self):
        dashboard_data = {
            "day_index": 1,
            "today_problems": [
                {
                    "problem_id": "206",
                    "title": "反转链表",
                    "difficulty": "Easy",
                    "completed": False
                }
            ],
            "today_reviews": [
                {
                    "problem_id": "24",
                    "title": "两两交换链表中的节点",
                    "priority_level": "高",
                    "review_round": 2,
                    "reason": "上次看提示后 AC，今天确认是否能独立写出。"
                }
            ]
        }
        plan = {
            "days": {
                "1": {
                    "problems": ["206"],
                    "reason": "先掌握链表指针反转，为后面节点重连打基础。"
                }
            }
        }

        tasks = task_board.get_today_tasks(dashboard_data=dashboard_data, plan=plan)

        self.assertEqual(2, len(tasks))
        self.assertEqual(
            "先掌握链表指针反转，为后面节点重连打基础。",
            tasks[0]["reason"]
        )
        self.assertIn("今天确认是否能独立写出", tasks[1]["reason"])

    def test_task_board_data_exposes_sync_status_and_learning_snapshot(self):
        plan = {
            "week": 4,
            "title": "链表专题",
            "start_date": "2026-06-12",
            "must_master": ["160"],
            "days": {
                "1": {
                    "problems": ["206"],
                    "goal": "反转链表",
                    "topic": "链表三指针反转",
                    "task_type": "review"
                }
            }
        }
        sync_state = {
            "success": True,
            "last_success_at": "2026-06-16 09:30:00",
            "fetched": 8,
            "imported": 1
        }
        dashboard_data = {
            "plan_title": "Week 4 - 链表专题",
            "day_index": 1,
            "plan_phase": {
                "label": "Day 1",
                "day_index": 1,
                "all_tasks_completed": False
            },
            "today_goal": "反转链表",
            "today_problems": [
                {
                    "problem_id": "206",
                    "title": "反转链表",
                    "difficulty": "Easy",
                    "completed": False
                }
            ],
            "today_reviews": [],
            "due_review_count": 0,
            "deferred_review_count": 1,
            "suggestion": "先完成 206，再看后台复习。",
        }

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan_path = root / "week_plan.json"
            problem_bank_path = root / "problem_bank.json"
            records_path = root / "records.json"
            sync_path = root / "leetcode_sync_state.json"

            plan_path.write_text(
                json.dumps(plan, ensure_ascii=False),
                encoding="utf-8"
            )
            problem_bank_path.write_text(
                json.dumps({"206": {"title": "反转链表", "difficulty": "Easy"}}, ensure_ascii=False),
                encoding="utf-8"
            )
            records_path.write_text("[]", encoding="utf-8")
            sync_path.write_text(
                json.dumps(sync_state, ensure_ascii=False),
                encoding="utf-8"
            )

            with (
                patch.object(task_board, "PLAN_PATH", plan_path),
                patch.object(task_board, "PROBLEM_BANK_PATH", problem_bank_path),
                patch.object(task_board, "RECORDS_PATH", records_path),
                patch.object(task_board, "SYNC_STATE_PATH", sync_path),
                patch.object(task_board, "get_dashboard_data", return_value=dashboard_data)
            ):
                data = task_board.get_task_board_data()

        self.assertIn("2026-06-16 09:30:00", data["sync_status"]["text"])
        self.assertIn("读取 8 条提交", data["sync_status"]["detail"])
        self.assertIn("160", data["learning_snapshot"]["risk"])
        self.assertIn("206", data["learning_snapshot"]["next_step"])


class SyncOverviewTests(unittest.TestCase):
    def test_format_sync_overview_shows_mapping_and_failure_hint(self):
        overview = {
            "sync_state": {
                "last_success_at": "2026-06-16 10:00:00",
                "fetched": 5,
                "imported": 2
            },
            "recent_records": [
                {
                    "problem_id": "206",
                    "title": "反转链表",
                    "submit_time": "2026-06-16 09:58:00"
                },
                {
                    "problem_id": "swap-nodes",
                    "title": "Swap Nodes",
                    "title_slug": "swap-nodes"
                }
            ],
            "mapped_records": [
                {
                    "problem_id": "206",
                    "title": "反转链表",
                    "submit_time": "2026-06-16 09:58:00"
                }
            ],
            "unmapped_records": [
                {
                    "problem_id": "swap-nodes",
                    "title": "Swap Nodes",
                    "title_slug": "swap-nodes"
                }
            ],
            "debug_data": {
                "error_type": "BrowserExtensionUnavailable",
                "error_message": "未收到扩展响应。"
            }
        }

        text = leetcode_sync.format_sync_overview(overview)

        self.assertIn("最近同步时间：2026-06-16 10:00:00", text)
        self.assertIn("成功映射题号：1 条", text)
        self.assertIn("未映射到题号：1 条", text)
        self.assertIn("swap-nodes", text)
        self.assertIn("确认 Chrome 扩展已加载", text)

    def test_interactive_fetch_does_not_silently_fallback_to_local_cache(self):
        browser_failure = {
            "success": False,
            "submissions": [],
            "error_type": "SilentBrowserSessionUnavailable",
            "error_message": "未检测到可响应标签页。",
            "request_url": "http://127.0.0.1:18777",
            "request_attempts": []
        }

        with (
            patch.object(
                leetcode_sync,
                "_fetch_recent_submissions_with_browser",
                return_value=browser_failure
            ),
            patch.object(
                leetcode_sync,
                "_load_local_submission_cache",
                return_value=[{"title": "旧缓存"}]
            ),
            patch.object(
                leetcode_sync,
                "_load_json",
                side_effect=[{}, []]
            )
        ):
            result = leetcode_sync.fetch_recent_submissions(
                "example-user",
                "leetcode.cn",
                20,
                interactive=True
            )

        self.assertFalse(result["success"])
        self.assertEqual(
            "SilentBrowserSessionUnavailable",
            result["error_type"]
        )

    def test_auto_fetch_does_not_use_local_records_as_successful_sync(self):
        browser_failure = {
            "success": False,
            "submissions": [],
            "error_type": "SilentBrowserSessionUnavailable",
            "error_message": "未检测到可响应标签页。",
            "request_url": "http://127.0.0.1:18777",
            "request_attempts": []
        }

        with (
            patch.object(
                leetcode_sync,
                "_fetch_recent_submissions_with_browser",
                return_value=browser_failure
            ),
            patch.object(
                leetcode_sync,
                "_load_local_submission_cache",
                return_value=[{"title": "旧缓存"}]
            ),
            patch.object(
                leetcode_sync,
                "_load_json",
                side_effect=[{}, []]
            )
        ):
            result = leetcode_sync.fetch_recent_submissions(
                "example-user",
                "leetcode.cn",
                20,
                interactive=False
            )

        self.assertFalse(result["success"])
        self.assertEqual(
            "SilentBrowserSessionUnavailable",
            result["error_type"]
        )

    def test_format_sync_diagnostics_highlights_tab_cache_and_next_step(self):
        result = {
            "success": True,
            "extension_version": "1.1.0",
            "total_tabs_seen": 6,
            "extension_online": True,
            "leetcode_tabs_found": 1,
            "detected_tab_urls": ["https://leetcode.cn/u/example-user/"],
            "cache_available": True,
            "cache_is_today": False,
            "cache_time": "2026-06-12T12:14:58.000Z",
            "cache_submission_count": 8,
            "fresh_fetch_success": False,
            "fresh_error_type": "BrowserExtensionError",
            "fresh_error_message": "浏览器页面未能读取提交记录。"
        }

        text = leetcode_sync.format_sync_diagnostics(result)

        self.assertIn("扩展版本：1.1.0", text)
        self.assertIn("检测到力扣标签页：1 个", text)
        self.assertIn("缓存是否为今天：否", text)
        self.assertIn("本次直接抓取：失败", text)
        self.assertIn("当前缓存不是今天的", text)

    def test_format_sync_diagnostics_handles_successful_fetch(self):
        result = {
            "success": True,
            "extension_version": "1.1.2",
            "total_tabs_seen": 4,
            "extension_online": True,
            "leetcode_tabs_found": 1,
            "detected_tab_urls": ["https://leetcode.cn/u/example-user/"],
            "cache_available": True,
            "cache_is_today": True,
            "cache_time": "2026-06-16T10:15:00.000Z",
            "cache_submission_count": 10,
            "fresh_fetch_success": True,
            "fresh_result_count": 3
        }

        text = leetcode_sync.format_sync_diagnostics(result)

        self.assertIn("扩展版本：1.1.2", text)
        self.assertIn("本次直接抓取：成功", text)
        self.assertIn("本次抓取到：3 条提交", text)

    def test_legacy_extension_diagnosis_has_explicit_reload_message(self):
        text = leetcode_sync.format_sync_diagnostics({
            "success": False,
            "error_type": "LegacyExtensionVersion",
            "error_message": "当前 Chrome 中运行的仍是旧版 LeetCoach 扩展。"
        })

        self.assertIn("LegacyExtensionVersion", text)
        self.assertIn("chrome://extensions", text)
        self.assertIn("点击一次“刷新”", text)

    def test_browser_sync_detects_legacy_extension_response(self):
        class FakeBridge:
            def start(self):
                return None

            def wait(self, timeout=8):
                return {"success": True, "submissions": []}

            def close(self):
                return None

        with patch.object(browser_sync, "SyncBridge", return_value=FakeBridge()):
            result = browser_sync.diagnose_browser_sync("example-user", limit=20)

        self.assertFalse(result["success"])
        self.assertEqual("LegacyExtensionVersion", result["error_type"])


if __name__ == "__main__":
    unittest.main()
