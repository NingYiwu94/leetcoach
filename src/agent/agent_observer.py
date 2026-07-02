import json
from datetime import date, datetime
from pathlib import Path

from core.learning_analyzer import analyze_learning_patterns
from app.task_board import get_task_board_data


from app_paths import BASE_DIR
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
SYNC_STATE_PATH = BASE_DIR / "data" / "leetcode_sync_state.json"
NEXT_PLAN_PATH = BASE_DIR / "config" / "week_plan_next.json"


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    if default is None:
        return data
    return data if isinstance(data, type(default)) else default


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_failed(record):
    status = str(record.get("status", "") if isinstance(record, dict) else "")
    raw_status = str(record.get("raw_status", "") if isinstance(record, dict) else "")
    return "未通过" in status or "Wrong Answer" in raw_status or status.lower() in {"failed", "fail"}


def _is_hint_ac(record):
    status = str(record.get("status", "") if isinstance(record, dict) else "")
    return "看提示后AC" in status or "提示" in status


def _overdue_reviews(reviews):
    today = date.today()
    count = 0
    for review in reviews:
        if not isinstance(review, dict) or review.get("done"):
            continue
        value = str(review.get("next_review_date", "")).strip()
        try:
            review_date = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            continue
        if review_date < today:
            count += 1
    return count


def collect_learning_observation():
    records = _load_json(RECORDS_PATH, [])
    reviews = _load_json(REVIEWS_PATH, [])
    problem_bank = _load_json(PROBLEM_BANK_PATH, {})
    sync_state = _load_json(SYNC_STATE_PATH, {})
    draft = _load_json(NEXT_PLAN_PATH, None)

    if not isinstance(records, list):
        records = []
    if not isinstance(reviews, list):
        reviews = []
    if not isinstance(problem_bank, dict):
        problem_bank = {}
    if not isinstance(sync_state, dict):
        sync_state = {}

    try:
        board = get_task_board_data()
    except Exception:
        board = {}

    plan = board.get("plan", {}) if isinstance(board, dict) else {}
    phase = board.get("plan_phase", {}) if isinstance(board, dict) else {}
    week_tasks = board.get("week_tasks", []) if isinstance(board, dict) else []
    if not isinstance(week_tasks, list):
        week_tasks = []

    total_task_count = len(week_tasks)
    completed_task_count = sum(1 for task in week_tasks if isinstance(task, dict) and task.get("completed"))
    completion_rate = round(completed_task_count / total_task_count, 4) if total_task_count else 0.0

    unfinished_problem_count = sum(
        1 for task in week_tasks
        if isinstance(task, dict)
        and task.get("kind") == "plan"
        and not task.get("completed")
    )
    pending_review_count = sum(
        1 for review in reviews
        if isinstance(review, dict) and not review.get("done")
    )
    recent_records = records[-20:]
    analysis = {}
    try:
        analysis = analyze_learning_patterns(records, problem_bank, reviews)
    except Exception:
        analysis = {}
    if not isinstance(analysis, dict):
        analysis = {}

    return {
        "current_week": _as_int(plan.get("week") if isinstance(plan, dict) else 0),
        "current_day": _as_int(phase.get("day_index") if isinstance(phase, dict) else 0),
        "current_topic": (
            board.get("today_topic")
            or (plan.get("title") if isinstance(plan, dict) else "")
            or (plan.get("weekly_theme") if isinstance(plan, dict) else "")
        ),
        "plan_completion_rate": completion_rate,
        "completed_task_count": completed_task_count,
        "total_task_count": total_task_count,
        "pending_review_count": pending_review_count,
        "overdue_review_count": _overdue_reviews(reviews),
        "unfinished_problem_count": unfinished_problem_count,
        "recent_failed_count": sum(1 for item in recent_records if _is_failed(item)),
        "recent_hint_ac_count": sum(1 for item in recent_records if _is_hint_ac(item)),
        "has_pending_plan_draft": isinstance(draft, dict) and bool(draft),
        "last_sync_status": (
            "success" if sync_state.get("success") else "failed" if sync_state else None
        ),
        "last_sync_time": sync_state.get("last_success_at") or sync_state.get("last_attempt_at"),
        "main_weakness": analysis.get("main_weakness") or "暂无明确分类",
        "current_plan_phase": phase.get("label") if isinstance(phase, dict) else None,
    }


def format_learning_observation(observation):
    if not isinstance(observation, dict):
        return "暂无 Agent 观察。"
    lines = [
        "===== Agent 当前观察 =====",
        "",
        f"当前 Week：{observation.get('current_week')}",
        f"当前 Day：{observation.get('current_day')}",
        f"当前专题：{observation.get('current_topic') or '暂无'}",
        f"计划完成率：{observation.get('plan_completion_rate', 0) * 100:.1f}%",
        f"已完成任务：{observation.get('completed_task_count', 0)} / {observation.get('total_task_count', 0)}",
        f"待复习总数：{observation.get('pending_review_count', 0)}",
        f"到期未复习：{observation.get('overdue_review_count', 0)}",
        f"未完成计划题：{observation.get('unfinished_problem_count', 0)}",
        f"最近未通过：{observation.get('recent_failed_count', 0)}",
        f"最近看提示后 AC：{observation.get('recent_hint_ac_count', 0)}",
        f"是否有待确认草案：{'是' if observation.get('has_pending_plan_draft') else '否'}",
        f"最近同步状态：{observation.get('last_sync_status') or '暂无'}",
        f"最近同步时间：{observation.get('last_sync_time') or '暂无'}",
        f"主要薄弱点：{observation.get('main_weakness') or '暂无明确分类'}",
        f"当前阶段：{observation.get('current_plan_phase') or '暂无'}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_learning_observation(collect_learning_observation()))
