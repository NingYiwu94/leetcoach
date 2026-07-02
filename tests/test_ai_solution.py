import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ai.ai_solution import (
    format_solution,
    get_solution_note,
    has_detailed_code_comments,
    is_complete_solution,
    parse_solution_response,
    save_solution_note
)


class AiSolutionTests(unittest.TestCase):
    def setUp(self):
        self.raw_solution = """
{
  "problem_id": "704",
  "problem_title": "二分查找",
  "idea": "在有序数组中不断缩小目标可能所在的区间。",
  "language": "Python",
  "code": "class Solution:\\n    # 定义二分查找函数，返回目标下标\\n    def search(self, nums, target):\\n        # 左边界从数组第一个位置开始\\n        left = 0\\n        # 右边界指向最后一个有效位置\\n        right = len(nums) - 1\\n        # 闭区间仍有元素时继续查找\\n        while left <= right:\\n            # 取中点避免遗漏当前区间\\n            mid = (left + right) // 2\\n            # 找到目标后立即返回下标\\n            if nums[mid] == target:\\n                return mid\\n            # 中间值偏小，目标只可能在右半边\\n            if nums[mid] < target:\\n                left = mid + 1\\n            else:\\n                # 中间值偏大，目标只可能在左半边\\n                right = mid - 1\\n        # 区间为空仍未找到，返回 -1\\n        return -1",
  "common_mistakes": [
    {"point": "循环条件", "explanation": "闭区间应使用 left <= right。"},
    {"point": "边界更新", "explanation": "必须跳过已经比较过的 mid。"},
    {"point": "空数组", "explanation": "初始右边界会是 -1，循环自然不执行。"}
  ],
  "time_complexity": "O(log n)，每次比较都会把搜索区间缩小一半。"
}
""".strip()

    def test_valid_structured_solution_is_complete(self):
        solution = parse_solution_response(self.raw_solution)
        self.assertTrue(is_complete_solution(solution))
        self.assertEqual(3, len(solution["common_mistakes"]))
        self.assertIn("return -1", solution["code"])

    def test_formatter_has_exact_four_sections_in_order(self):
        text = format_solution(parse_solution_response(self.raw_solution))
        headings = [
            "一、解题思路",
            "二、完整代码（Python，含详细中文注释）",
            "三、易错点",
            "四、时间复杂度"
        ]
        positions = [text.index(heading) for heading in headings]
        self.assertEqual(sorted(positions), positions)
        self.assertNotIn("五、", text)
        self.assertNotIn("空间复杂度", text)
        self.assertIn("闭区间应使用 left <= right", text)

    def test_invalid_json_uses_readable_fallback(self):
        solution = parse_solution_response("模型返回了普通文本")
        self.assertTrue(solution["parse_fallback"])
        text = format_solution(solution)
        self.assertIn("模型返回了普通文本", text)
        self.assertIn("暂无可用代码", text)

    def test_string_mistakes_are_normalized(self):
        solution = parse_solution_response("""
        {
          "idea": "思路",
          "code": "代码",
          "common_mistakes": ["边界错误", "循环错误", "返回值错误"],
          "time_complexity": "O(n)"
        }
        """)
        self.assertEqual(
            "边界错误",
            solution["common_mistakes"][0]["point"]
        )

    def test_code_without_enough_comments_is_rejected(self):
        solution = parse_solution_response("""
        {
          "idea": "二分查找",
          "language": "Python",
          "code": "class Solution:\\n    def search(self, nums, target):\\n        left = 0\\n        right = len(nums) - 1\\n        while left <= right:\\n            mid = (left + right) // 2\\n            if nums[mid] == target:\\n                return mid\\n        return -1",
          "common_mistakes": [
            {"point": "边界", "explanation": "说明"},
            {"point": "更新", "explanation": "说明"},
            {"point": "返回", "explanation": "说明"}
          ],
          "time_complexity": "O(log n)"
        }
        """)
        self.assertFalse(is_complete_solution(solution))
        self.assertFalse(
            has_detailed_code_comments(
                solution["code"],
                solution["language"]
            )
        )

    def test_solution_note_can_be_saved_and_loaded_by_problem_id(self):
        solution = parse_solution_response(self.raw_solution)

        with TemporaryDirectory() as tmp_dir:
            notes_path = Path(tmp_dir) / "ai_solution_notes.json"
            with patch("ai.ai_solution.SOLUTION_NOTES_PATH", notes_path):
                saved = save_solution_note(solution)
                loaded = get_solution_note("题号：704")

        self.assertEqual("704", saved["problem_id"])
        self.assertIsNotNone(loaded)
        self.assertEqual("704", loaded["problem_id"])
        self.assertIn("有序数组", loaded["idea"])


if __name__ == "__main__":
    unittest.main()
