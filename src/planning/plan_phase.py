from datetime import date, datetime

from planning.plan_task_state import get_milestone_task_id


def _parse_start_date(plan):
    if not isinstance(plan, dict):
        return None
    try:
        return datetime.strptime(
            str(plan.get("start_date", "")),
            "%Y-%m-%d"
        ).date()
    except (TypeError, ValueError):
        return None


def get_plan_phase(plan, today=None):
    today = today or date.today()
    start_date = _parse_start_date(plan)

    if start_date is None:
        return {
            "status": "unknown",
            "day_index": 0,
            "start_date": "",
            "days_until_start": 0,
            "days_after_end": 0,
            "label": "计划日期未知"
        }

    day_index = (today - start_date).days + 1
    if day_index < 1:
        days_until_start = (start_date - today).days
        return {
            "status": "upcoming",
            "day_index": day_index,
            "start_date": str(start_date),
            "days_until_start": days_until_start,
            "days_after_end": 0,
            "label": f"计划将在 {days_until_start} 天后开始"
        }

    if day_index <= 7:
        return {
            "status": "active",
            "day_index": day_index,
            "start_date": str(start_date),
            "days_until_start": 0,
            "days_after_end": 0,
            "label": f"Day {day_index}"
        }

    days_after_end = day_index - 7
    return {
        "status": "ended",
        "day_index": day_index,
        "start_date": str(start_date),
        "days_until_start": 0,
        "days_after_end": days_after_end,
        "label": f"计划已结束 {days_after_end} 天"
    }


def get_self_paced_plan_phase(
    plan,
    completed_problem_ids=None,
    completed_milestone_ids=None,
    today=None
):
    phase = get_plan_phase(plan, today=today)
    if not isinstance(plan, dict):
        return phase

    completed = {
        str(problem_id or "").strip()
        for problem_id in (completed_problem_ids or [])
        if str(problem_id or "").strip()
    }
    completed_milestones = {
        str(task_id or "").strip()
        for task_id in (completed_milestone_ids or [])
        if str(task_id or "").strip()
    }
    days = plan.get("days", {})
    if not isinstance(days, dict):
        return phase

    planned_problem_ids = []
    planned_milestone_ids = []
    first_unfinished_day = None
    for day_index in range(1, 8):
        day = days.get(str(day_index), {})
        if not isinstance(day, dict):
            continue
        problems = day.get("problems", [])
        if not isinstance(problems, list):
            continue
        day_problem_ids = [
            str(problem_id or "").strip()
            for problem_id in problems
            if str(problem_id or "").strip()
        ]
        planned_problem_ids.extend(
            problem_id
            for problem_id in day_problem_ids
            if problem_id not in planned_problem_ids
        )
        has_unfinished_problem = any(
            problem_id not in completed
            for problem_id in day_problem_ids
        )
        task_type = str(day.get("task_type", "")).strip()
        milestone_id = ""
        if task_type in {"review_day", "summary"}:
            milestone_id = get_milestone_task_id(plan, day_index, day)
            planned_milestone_ids.append(milestone_id)
        has_unfinished_milestone = (
            bool(milestone_id)
            and milestone_id not in completed_milestones
        )
        if (
            first_unfinished_day is None
            and (has_unfinished_problem or has_unfinished_milestone)
        ):
            first_unfinished_day = day_index

    result = dict(phase)
    result["calendar_day_index"] = phase.get("day_index", 0)
    result["self_paced"] = True

    if first_unfinished_day is not None:
        result.update({
            "status": "active",
            "day_index": first_unfinished_day,
            "label": f"Day {first_unfinished_day}",
            "all_tasks_completed": False
        })
        return result

    all_task_ids = planned_problem_ids + planned_milestone_ids
    all_tasks_completed = bool(all_task_ids)
    result.update({
        "status": "completed" if all_tasks_completed else phase["status"],
        "day_index": 7 if all_tasks_completed else phase.get("day_index", 0),
        "label": "本阶段已完成" if all_tasks_completed else phase["label"],
        "all_tasks_completed": all_tasks_completed
    })
    return result


def format_plan_phase(phase):
    if not isinstance(phase, dict):
        return "计划日期未知"
    return phase.get("label", "计划日期未知")
