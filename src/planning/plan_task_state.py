import json
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
PLAN_TASK_STATE_PATH = BASE_DIR / "data" / "plan_task_state.json"
MILESTONE_TASK_TYPES = {"review_day", "summary"}


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".json.tmp")
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temporary_path.replace(path)


def get_plan_key(plan):
    if not isinstance(plan, dict):
        return ""
    week = str(plan.get("week", "")).strip()
    start_date = str(plan.get("start_date", "")).strip()
    activated_at = str(plan.get("activated_at", "")).strip()
    return f"week:{week}|start:{start_date}|activated:{activated_at}"


def get_milestone_task_id(plan, day_index, day=None):
    day = day if isinstance(day, dict) else {}
    task_type = str(day.get("task_type", "milestone")).strip()
    return f"{get_plan_key(plan)}|day:{day_index}|type:{task_type}"


def get_plan_milestones(plan):
    if not isinstance(plan, dict):
        return []

    days = plan.get("days", {})
    if not isinstance(days, dict):
        return []

    milestones = []
    for day_index in range(1, 8):
        day = days.get(str(day_index), {})
        if not isinstance(day, dict):
            continue
        task_type = str(day.get("task_type", "")).strip()
        if task_type not in MILESTONE_TASK_TYPES:
            continue
        milestones.append({
            "task_id": get_milestone_task_id(plan, day_index, day),
            "kind": "milestone",
            "day_index": day_index,
            "task_type": task_type,
            "title": day.get(
                "topic",
                "复习验收" if task_type == "review_day" else "周总结"
            ),
            "goal": day.get("goal", ""),
            "review_problems": [
                str(problem_id or "").strip()
                for problem_id in day.get("review_problems", [])
                if str(problem_id or "").strip()
            ],
            "label": "阶段复习" if task_type == "review_day" else "阶段总结"
        })
    return milestones


def load_plan_task_state():
    state = load_json(PLAN_TASK_STATE_PATH, [])
    return state if isinstance(state, list) else []


def get_stage_summaries(state=None):
    state = state if isinstance(state, list) else load_plan_task_state()
    summaries = []
    for item in state:
        if not isinstance(item, dict):
            continue
        summary = item.get("stage_summary")
        if item.get("completed") and isinstance(summary, dict):
            summaries.append(summary)
    summaries.sort(key=lambda item: str(item.get("generated_at", "")))
    return summaries


def get_completed_milestone_ids(plan, state=None):
    plan_key = get_plan_key(plan)
    state = state if isinstance(state, list) else load_plan_task_state()
    valid_task_ids = {
        item["task_id"]
        for item in get_plan_milestones(plan)
    }
    return {
        str(item.get("task_id", "")).strip()
        for item in state
        if (
            isinstance(item, dict)
            and item.get("completed")
            and item.get("plan_key") == plan_key
            and str(item.get("task_id", "")).strip()
            in valid_task_ids
        )
    }


def complete_milestone_task(task, plan):
    if not isinstance(task, dict) or not isinstance(plan, dict):
        return False

    task_id = str(task.get("task_id", "")).strip()
    if not task_id:
        return False

    state = load_plan_task_state()
    for item in state:
        if not isinstance(item, dict) or item.get("task_id") != task_id:
            continue
        item["completed"] = True
        item["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(task.get("stage_summary"), dict):
            item["stage_summary"] = task["stage_summary"]
        save_json(PLAN_TASK_STATE_PATH, state)
        return True

    state.append({
        "plan_key": get_plan_key(plan),
        "plan_week": plan.get("week"),
        "plan_start_date": plan.get("start_date"),
        "task_id": task_id,
        "day_index": task.get("day_index"),
        "task_type": task.get("task_type"),
        "title": task.get("title", ""),
        "completed": True,
        "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    if isinstance(task.get("stage_summary"), dict):
        state[-1]["stage_summary"] = task["stage_summary"]
    save_json(PLAN_TASK_STATE_PATH, state)
    return True
