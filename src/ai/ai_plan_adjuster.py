import json
from pathlib import Path

from core.next_plan import generate_next_week_plan_draft


from app_paths import BASE_DIR
PLAN_PATH = BASE_DIR / "config" / "week_plan.json"
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
AGENT_MEMORY_PATH = BASE_DIR / "data" / "agent_memory.json"
AI_NEXT_PLAN_PATH = BASE_DIR / "data" / "ai_next_plan_draft.json"


def load_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def clean_problem_id(problem_id):
    problem_id = str(problem_id)
    problem_id = problem_id.replace("题号：", "")
    problem_id = problem_id.replace("题号:", "")
    problem_id = problem_id.replace("题号", "")
    return problem_id.strip()


def _default_days():
    return {
        "1": {"goal": "复习本周未完成题", "tasks": [], "task_type": "review"},
        "2": {"goal": "复习需要提示的题", "tasks": [], "task_type": "review"},
        "3": {"goal": "巩固主要薄弱题型", "tasks": [], "task_type": "redo"},
        "4": {"goal": "适量新题练习", "tasks": [], "task_type": "new"},
        "5": {"goal": "适量新题练习", "tasks": [], "task_type": "new"},
        "6": {"goal": "复习错题", "tasks": [], "task_type": "review"},
        "7": {"goal": "周总结", "tasks": [], "task_type": "summary"}
    }


def parse_ai_next_week_plan(raw_text, next_week):
    try:
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("AI response is not an object")
    except (json.JSONDecodeError, TypeError, ValueError):
        data = {
            "plan_title": f"Week {next_week} 学习巩固周",
            "strategy": "AI 返回格式异常，建议以规则版计划为基础进行温和调整。",
            "days": _default_days(),
            "reason": str(raw_text).strip() or "当前数据不足，建议保持复习和记录。"
        }

    plan_title = data.get("plan_title") or f"Week {next_week} 学习巩固周"
    strategy = data.get("strategy") or "优先复习未完成题，再安排适量新题。"
    reason = data.get("reason") or "根据本周记录与复习压力进行调整。"

    days = data.get("days", {})
    if not isinstance(days, dict):
        days = {}

    defaults = _default_days()
    normalized_days = {}
    for day_index in range(1, 8):
        day_key = str(day_index)
        day_data = days.get(day_key, {})
        if not isinstance(day_data, dict):
            day_data = {}

        default = defaults[day_key]
        tasks = day_data.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = [str(tasks)] if tasks not in (None, "") else []

        normalized_days[day_key] = {
            "goal": day_data.get("goal", default["goal"]),
            "tasks": [str(task) for task in tasks],
            "task_type": day_data.get("task_type", default["task_type"])
        }

    return {
        "plan_title": plan_title,
        "strategy": strategy,
        "days": normalized_days,
        "reason": reason
    }


def save_ai_next_plan_draft(plan_dict):
    AI_NEXT_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AI_NEXT_PLAN_PATH, "w", encoding="utf-8") as f:
        json.dump(plan_dict, f, ensure_ascii=False, indent=2)


def generate_ai_next_week_plan():
    plan = load_json(PLAN_PATH, {})
    records = load_json(RECORDS_PATH, [])
    reviews = load_json(REVIEWS_PATH, [])
    agent_memory = load_json(AGENT_MEMORY_PATH, [])
    rule_plan = generate_next_week_plan_draft()

    current_week = plan.get("week", 0) if isinstance(plan, dict) else 0
    try:
        next_week = int(current_week) + 1
    except (TypeError, ValueError):
        next_week = 1

    context = {
        "current_week_plan": plan,
        "records": records,
        "reviews": reviews,
        "agent_memory": agent_memory[-7:] if isinstance(agent_memory, list) else [],
        "rule_next_week_plan": rule_plan
    }

    system_prompt = (
        "你是 LeetCoach 的学习计划调整模块。"
        "请根据真实数据生成保守、可执行的下一周学习计划建议。"
        "不要盲目增加题量，不要虚构具体题号。"
        "必须只返回严格 JSON，不要使用 Markdown 代码块或额外解释。"
    )
    user_prompt = f"""
请根据以下数据生成下一周计划建议：
{json.dumps(context, ensure_ascii=False)}

严格返回以下 JSON 结构：
{{
  "plan_title": "Week {next_week} 计划标题",
  "strategy": "下周整体策略",
  "days": {{
    "1": {{"goal": "目标", "tasks": ["已有题号"], "task_type": "review"}},
    "2": {{"goal": "目标", "tasks": [], "task_type": "review"}},
    "3": {{"goal": "目标", "tasks": [], "task_type": "redo"}},
    "4": {{"goal": "目标", "tasks": [], "task_type": "new"}},
    "5": {{"goal": "目标", "tasks": [], "task_type": "new"}},
    "6": {{"goal": "目标", "tasks": [], "task_type": "review"}},
    "7": {{"goal": "目标", "tasks": [], "task_type": "summary"}}
  }},
  "reason": "调整原因"
}}

要求：
- 只输出合法 JSON。
- 不要使用 Markdown 代码块。
- 复习和重做任务只能引用输入数据中已有的题号。
- 新题尚未确定时 tasks 保持空列表，不要虚构题号。
- 数据不足时减少新题量并给出温和建议。
""".strip()

    try:
        from llm_client import LLMClient

        client = LLMClient()
        raw_text = client.chat(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.4
        )
    except Exception:
        return {
            "fallback": True,
            "message": "AI 下周计划生成失败，建议使用规则版下一周计划雏形。",
            "rule_result": rule_plan
        }

    plan_dict = parse_ai_next_week_plan(raw_text, next_week)

    known_problem_ids = set()
    if isinstance(plan, dict):
        for day_data in plan.get("days", {}).values():
            if isinstance(day_data, dict):
                for problem_id in day_data.get("problems", []):
                    known_problem_ids.add(clean_problem_id(problem_id))

    for data_list in (records, reviews):
        if not isinstance(data_list, list):
            continue
        for item in data_list:
            if isinstance(item, dict):
                known_problem_ids.add(
                    clean_problem_id(item.get("problem_id", ""))
                )

    for day_data in plan_dict["days"].values():
        if day_data["task_type"] == "new":
            day_data["tasks"] = []
        else:
            day_data["tasks"] = [
                clean_problem_id(problem_id)
                for problem_id in day_data["tasks"]
                if clean_problem_id(problem_id) in known_problem_ids
            ]

    try:
        save_ai_next_plan_draft(plan_dict)
    except Exception:
        print("AI 下周计划草案保存失败，但计划建议已生成。")

    return plan_dict


def format_ai_next_week_plan(plan_dict):
    if plan_dict.get("fallback"):
        return "\n".join([
            plan_dict.get(
                "message",
                "AI 下周计划生成失败，建议使用规则版下一周计划雏形。"
            ),
            "",
            plan_dict.get("rule_result", generate_next_week_plan_draft())
        ])

    lines = [
        "===== AI 下周计划建议 =====",
        "",
        f"计划：{plan_dict.get('plan_title', '')}",
        "",
        "整体策略：",
        str(plan_dict.get("strategy", "")),
        "",
        "每日安排："
    ]

    days = plan_dict.get("days", {})
    for day_index in range(1, 8):
        day = days.get(str(day_index), {})
        task_type = day.get("task_type", "")
        lines.append(
            f"Day {day_index}：{day.get('goal', '')}"
            f" [{task_type}]"
        )

        tasks = day.get("tasks", [])
        if tasks:
            lines.append(f"  任务：{', '.join(str(task) for task in tasks)}")
        else:
            lines.append("  任务：待确定")

    lines.extend([
        "",
        "调整原因：",
        str(plan_dict.get("reason", ""))
    ])

    return "\n".join(lines)
