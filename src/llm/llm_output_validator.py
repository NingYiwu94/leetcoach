SOLUTION_CONTENT_FIELDS = {
    "code",
    "solution",
    "answer",
    "full_code",
    "complete_code",
    "source_code",
}
SOLUTION_TEXT_MARKERS = {
    "```python",
    "```cpp",
    "class Solution",
    "#include",
    "完整代码如下",
    "代码如下",
    "具体实现如下",
}


def _contains_solution_field(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SOLUTION_CONTENT_FIELDS:
                return True
            if _contains_solution_field(item):
                return True
    elif isinstance(value, list):
        return any(_contains_solution_field(item) for item in value)
    elif isinstance(value, str):
        return any(marker in value for marker in SOLUTION_TEXT_MARKERS)
    return False


def validate_week_plan_output(plan):
    issues = []

    if not isinstance(plan, dict):
        return {
            "valid": False,
            "score": 0,
            "issues": ["输出不是 JSON object"]
        }

    for field in {
        "week",
        "title",
        "start_date",
        "days",
        "generated_by",
        "reason",
        "recommended_focus"
    }:
        if field not in plan:
            issues.append(f"缺少字段 {field}")

    days = plan.get("days")
    if not isinstance(days, dict):
        issues.append("days 不是 object")
        days = {}

    for day_index in range(1, 8):
        key = str(day_index)
        day = days.get(key)
        if not isinstance(day, dict):
            issues.append(f"Day {day_index} 缺失或不是 object")
            continue

        for field in {"date_note", "problems", "goal", "reason"}:
            if field not in day:
                issues.append(f"Day {day_index} 缺少 {field}")

        problems = day.get("problems", [])
        if not isinstance(problems, list):
            issues.append(f"Day {day_index} problems 不是 list")
        elif len(problems) > 2:
            issues.append(f"Day {day_index} problems 超过 2 道")

    if _contains_solution_field(plan):
        issues.append("计划中出现题解或代码字段")

    recommended_focus = plan.get("recommended_focus", [])
    if "recommended_focus" in plan and not isinstance(recommended_focus, list):
        issues.append("recommended_focus 不是 list")

    score = max(0, 100 - len(issues) * 10)
    return {
        "valid": not issues,
        "score": score,
        "issues": issues
    }
