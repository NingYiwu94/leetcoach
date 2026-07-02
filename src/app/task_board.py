import json
from pathlib import Path

from app.dashboard import get_dashboard_data
from planning.plan_progress import get_completed_problem_ids
from planning.plan_task_state import (
    complete_milestone_task,
    get_completed_milestone_ids,
    get_plan_milestones
)
from core.recorder import add_record
from core.reviewer import mark_review_done, record_stage_review_results
from core.stage_summary import generate_stage_summary


from app_paths import BASE_DIR
PLAN_PATH = BASE_DIR / "config" / "week_plan.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
RECORDS_PATH = BASE_DIR / "data" / "records.json"
SYNC_STATE_PATH = BASE_DIR / "data" / "leetcode_sync_state.json"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _clean_problem_id(problem_id):
    return str(problem_id or "").strip()


def _short_text(value, fallback="", limit=68):
    text = str(value or "").strip()
    if not text:
        return fallback
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _load_sync_status():
    state = load_json(SYNC_STATE_PATH, {})
    if not isinstance(state, dict) or not state.get("success"):
        return {
            "text": "最近同步：暂时没有成功记录",
            "detail": "同步失败时仍会继续使用本地记录。"
        }

    last_success_at = str(state.get("last_success_at", "")).strip() or "未知"
    imported = state.get("imported", 0)
    fetched = state.get("fetched", 0)
    return {
        "text": f"最近同步：{last_success_at}",
        "detail": f"上次读取 {fetched} 条提交，新增 {imported} 条。"
    }


def _build_plan_task_reason(today_plan, problem_id):
    if not isinstance(today_plan, dict):
        return "按今天的学习节奏推进。"

    reason = _short_text(today_plan.get("reason", ""))
    if reason:
        return reason

    previous = _short_text(today_plan.get("relation_previous", ""))
    next_step = _short_text(today_plan.get("relation_next", ""))
    if previous and next_step:
        return f"{previous} {next_step}"
    if previous:
        return previous
    if next_step:
        return next_step

    return f"今天需要推进 {problem_id} 这道计划题。"


def _build_review_task_reason(review):
    if not isinstance(review, dict):
        return "今天安排一次复习巩固。"

    reason = _short_text(review.get("reason", ""))
    if reason:
        return reason

    priority = str(review.get("priority_level", "中")).strip()
    overdue_days = int(review.get("overdue_days", 0) or 0)
    failure_count = int(review.get("failure_count", 0) or 0)
    assisted_count = int(review.get("assisted_count", 0) or 0)

    if overdue_days > 0:
        return f"这道题已逾期 {overdue_days} 天，今天优先补上。"
    if failure_count > 0:
        return f"之前出现过 {failure_count} 次未通过，今天需要回炉。"
    if assisted_count > 0:
        return f"之前有 {assisted_count} 次看提示后 AC，今天检查是否能独立写出。"
    return f"这是今天的{priority}优先级复习任务。"


def _build_learning_snapshot(data, today_tasks, week_tasks, completed_ids):
    plan_phase = data.get("plan_phase", {})
    stage = data.get("today_topic") or plan_phase.get("label", "暂无阶段")
    progress_text = f"{data.get('week_completed', 0)} / {len(week_tasks)}"

    plan = data.get("plan", {})
    required_ids = []
    for field in ("must_master", "guided_mastery"):
        values = plan.get(field, [])
        if isinstance(values, list):
            required_ids.extend(
                _clean_problem_id(problem_id)
                for problem_id in values
                if _clean_problem_id(problem_id)
            )

    pending_required = [
        problem_id
        for problem_id in required_ids
        if problem_id not in completed_ids
    ]
    deferred_count = data.get("deferred_review_count", 0)
    if pending_required:
        current_risk = (
            "当前风险："
            + "、".join(pending_required[:3])
            + " 尚未完成验收"
        )
    elif deferred_count:
        current_risk = f"当前风险：还有 {deferred_count} 道到期复习在后台队列中"
    else:
        current_risk = "当前风险：暂无明显阻塞"

    next_task = next(
        (task for task in today_tasks if not task.get("completed")),
        None
    )
    if next_task:
        next_step = (
            f"下一步：先完成 {next_task.get('problem_id', '')} "
            f"{next_task.get('title', '当前任务')}".strip()
        )
    elif plan_phase.get("all_tasks_completed"):
        next_step = "下一步：本阶段已完成，查看阶段总结或确认下一阶段计划"
    else:
        next_step = _short_text(
            data.get("suggestion", ""),
            fallback="下一步：按今天的节奏继续推进。"
        )

    return {
        "stage": f"当前阶段：{stage}",
        "progress": f"本周进度：{progress_text}",
        "risk": current_risk,
        "next_step": next_step
    }


def get_week_tasks(plan=None, problem_bank=None, records=None):
    plan = plan if isinstance(plan, dict) else load_json(PLAN_PATH, {})
    problem_bank = (
        problem_bank
        if isinstance(problem_bank, dict)
        else load_json(PROBLEM_BANK_PATH, {})
    )
    records = records if isinstance(records, list) else load_json(
        RECORDS_PATH, []
    )

    completed_ids = get_completed_problem_ids(plan, records)
    completed_milestone_ids = get_completed_milestone_ids(plan)
    tasks_by_problem = {}
    days = plan.get("days", {}) if isinstance(plan, dict) else {}
    if not isinstance(days, dict):
        days = {}

    for day_index in range(1, 8):
        day = days.get(str(day_index), {})
        if not isinstance(day, dict):
            continue
        problems = day.get("problems", [])
        if not isinstance(problems, list):
            continue

        for raw_problem_id in problems:
            problem_id = _clean_problem_id(raw_problem_id)
            if not problem_id:
                continue
            task = tasks_by_problem.setdefault(problem_id, {
                "task_id": f"plan:{problem_id}",
                "kind": "plan",
                "problem_id": problem_id,
                "title": "未知题目",
                "difficulty": "未知",
                "scheduled_days": [],
                "completed": problem_id in completed_ids
            })
            task["scheduled_days"].append(day_index)
            problem = problem_bank.get(problem_id, {})
            if isinstance(problem, dict):
                task["title"] = problem.get("title", "未知题目")
                task["difficulty"] = problem.get("difficulty", "未知")

    tasks = list(tasks_by_problem.values())
    for milestone in get_plan_milestones(plan):
        milestone["scheduled_days"] = [milestone["day_index"]]
        milestone["difficulty"] = milestone["label"]
        milestone["completed"] = (
            milestone["task_id"] in completed_milestone_ids
        )
        tasks.append(milestone)
    return tasks


def get_today_tasks(dashboard_data=None, plan=None):
    data = (
        dashboard_data
        if isinstance(dashboard_data, dict)
        else get_dashboard_data()
    )
    tasks = []
    plan = plan if isinstance(plan, dict) else load_json(PLAN_PATH, {})
    days = plan.get("days", {}) if isinstance(plan, dict) else {}
    if not isinstance(days, dict):
        days = {}
    day_index = data.get("day_index", 0)
    today_plan = days.get(str(day_index), {})
    if not isinstance(today_plan, dict):
        today_plan = {}

    for problem in data.get("today_problems", []):
        if not isinstance(problem, dict):
            continue
        problem_id = _clean_problem_id(problem.get("problem_id"))
        tasks.append({
            "task_id": f"plan:{problem_id}",
            "kind": "plan",
            "problem_id": problem_id,
            "title": problem.get("title", "未知题目"),
            "difficulty": problem.get("difficulty", "未知"),
            "label": "今日计划",
            "completed": bool(problem.get("completed")),
            "reason": _build_plan_task_reason(today_plan, problem_id)
        })

    for review in data.get("today_reviews", []):
        if not isinstance(review, dict):
            continue
        problem_id = _clean_problem_id(review.get("problem_id"))
        review_label = (
            f"第 {review.get('review_round', 1)} 轮复习"
            f" · {review.get('priority_level', '低')}优先级"
        )
        if review.get("previous_mastery_label"):
            review_label += (
                f" · 上次{review['previous_mastery_label']}"
            )
        tasks.append({
            "task_id": f"review:{problem_id}",
            "kind": "review",
            "problem_id": problem_id,
            "title": review.get("title", "未知题目"),
            "label": review_label,
            "completed": False,
            "reason": _build_review_task_reason(review)
        })

    completed_milestones = get_completed_milestone_ids(plan)
    for milestone in get_plan_milestones(plan):
        if milestone.get("day_index") != day_index:
            continue
        milestone["completed"] = (
            milestone["task_id"] in completed_milestones
        )
        milestone["reason"] = _short_text(
            milestone.get("goal", ""),
            fallback="今天的阶段任务，用来确认这一周是否真的掌握。"
        )
        tasks.insert(0, milestone)

    return tasks


def get_task_board_data():
    plan = load_json(PLAN_PATH, {})
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    records = load_json(RECORDS_PATH, [])
    dashboard_data = get_dashboard_data()
    plan_phase = dashboard_data.get("plan_phase", {})
    day_index = plan_phase.get("day_index", 0)
    days = plan.get("days", {}) if isinstance(plan, dict) else {}
    if not isinstance(days, dict):
        days = {}
    today_plan = days.get(str(day_index), {})
    if not isinstance(today_plan, dict):
        today_plan = {}
    week_tasks = get_week_tasks(plan, problem_bank, records)
    today_tasks = get_today_tasks(dashboard_data, plan)
    completed_problem_ids = set(get_completed_problem_ids(plan, records))
    learning_snapshot = _build_learning_snapshot({
        "plan": plan,
        "plan_phase": plan_phase,
        "today_topic": today_plan.get("topic", ""),
        "suggestion": dashboard_data.get("suggestion", ""),
        "deferred_review_count": dashboard_data.get(
            "deferred_review_count",
            0
        ),
        "week_completed": sum(
            1 for task in week_tasks if task.get("completed")
        )
    }, today_tasks, week_tasks, completed_problem_ids)

    return {
        "plan": plan,
        "plan_title": dashboard_data.get("plan_title", "暂无计划"),
        "plan_phase": plan_phase,
        "today_goal": dashboard_data.get("today_goal", "暂无今日目标"),
        "today_topic": today_plan.get("topic", ""),
        "today_mastery_requirement": today_plan.get(
            "mastery_requirement",
            ""
        ),
        "today_execution_steps": today_plan.get(
            "execution_steps",
            []
        ),
        "today_summary_focus": today_plan.get("summary_focus", ""),
        "weekly_theme": plan.get("weekly_theme", plan.get("title", "")),
        "weekly_goal": plan.get("weekly_goal", ""),
        "minimum_acceptance": plan.get("minimum_acceptance", ""),
        "today_tasks": today_tasks,
        "week_tasks": week_tasks,
        "due_review_count": dashboard_data.get("due_review_count", 0),
        "deferred_review_count": dashboard_data.get(
            "deferred_review_count",
            0
        ),
        "today_completed": sum(
            1 for task in today_tasks if task.get("completed")
        ),
        "week_completed": sum(
            1 for task in week_tasks if task.get("completed")
        ),
        "suggestion": dashboard_data.get("suggestion", ""),
        "sync_status": _load_sync_status(),
        "learning_snapshot": learning_snapshot
    }


def complete_task(task, plan=None):
    if not isinstance(task, dict):
        return {"success": False, "message": "任务格式无效。"}
    if task.get("completed"):
        return {"success": True, "already_completed": True}

    plan = plan if isinstance(plan, dict) else load_json(PLAN_PATH, {})
    if task.get("kind") == "milestone":
        if task.get("task_type") == "review_day":
            review_problems = task.get("review_problems", [])
            review_results = task.get("review_results", {})
            if review_problems and not all(
                problem_id in review_results
                for problem_id in review_problems
            ):
                return {
                    "success": False,
                    "message": "请先填写所有核心题的复习结果。"
                }
            ordered_results = {
                problem_id: review_results[problem_id]
                for problem_id in review_problems
            }
            if not record_stage_review_results(
                ordered_results,
                assessment_id=task.get("task_id", "")
            ):
                return {
                    "success": False,
                    "message": "核心题复习结果保存失败。"
                }
        if (
            task.get("task_type") == "summary"
            and not isinstance(task.get("stage_summary"), dict)
        ):
            task = dict(task)
            task["stage_summary"] = generate_stage_summary(plan)
        success = complete_milestone_task(task, plan)
        return {
            "success": success,
            "message": (
                f"{task.get('title', '阶段任务')}已完成。"
                if success
                else "阶段任务保存失败。"
            )
        }

    problem_id = _clean_problem_id(task.get("problem_id"))
    if not problem_id:
        return {"success": False, "message": "任务缺少题号。"}

    if task.get("kind") == "review":
        mastery_result = task.get("review_mastery", "independent")
        success = mark_review_done(problem_id, mastery_result)
        mastery_labels = {
            "independent": "独立写出",
            "assisted": "看提示写出",
            "not_mastered": "仍未掌握"
        }
        mastery_label = mastery_labels.get(
            mastery_result,
            "独立写出"
        )
        return {
            "success": success,
            "message": (
                f"已记录“{mastery_label}”，后续复习已自动安排。"
                if success
                else "没有找到该题的待完成复习任务。"
            )
        }

    add_record(
        problem_id=problem_id,
        status="AC",
        difficulty_feeling="未知",
        mistake_type="未分类",
        mistake_note="任务清单点击完成",
        source="task_board",
        plan_week=plan.get("week"),
        plan_start_date=plan.get("start_date")
    )
    return {
        "success": True,
        "message": f"{problem_id} 已完成。"
    }
