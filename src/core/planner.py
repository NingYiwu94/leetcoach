import json
from pathlib import Path
from datetime import date, datetime


from app_paths import BASE_DIR
PLAN_PATH = BASE_DIR / "config" / "week_plan.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_current_day_index():
    plan = load_json(PLAN_PATH)

    start_date = datetime.strptime(plan["start_date"], "%Y-%m-%d").date()
    today = date.today()

    return (today - start_date).days + 1


def show_today_tasks():
    plan = load_json(PLAN_PATH)
    problem_bank = load_json(PROBLEM_BANK_PATH)

    day_index = get_current_day_index()
    day_key = str(day_index)

    print("\n====== 今日任务 ======")
    print(f"计划：Week {plan['week']} - {plan['title']}")

    if day_index < 1:
        print("计划还没有开始。")
        return

    if day_key not in plan["days"]:
        print("本周计划已经结束。")
        return

    today_plan = plan["days"][day_key]

    print(f"今天是：{today_plan['date_note']}")
    print(f"今日目标：{today_plan['goal']}")

    problem_ids = today_plan["problems"]

    if not problem_ids:
        print("今日没有新题。")
        return

    print("\n今日题目：")

    for problem_id in problem_ids:
        problem = problem_bank.get(problem_id, {})

        title = problem.get("title", "未知题目")
        difficulty = problem.get("difficulty", "未知难度")
        tags = problem.get("tags", [])

        print(f"- {problem_id} {title} [{difficulty}]")
        print(f"  标签：{', '.join(tags)}")