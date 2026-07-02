import json
from datetime import date, datetime
from pathlib import Path

from planning.plan_progress import (
    get_completed_problem_ids,
    get_planned_problem_ids
)
from planning.plan_phase import get_self_paced_plan_phase
from planning.plan_task_state import (
    get_completed_milestone_ids,
    get_plan_milestones
)
from planning.plan_review import get_draft_review_status

from app_paths import BASE_DIR
CONFIG_DIR = BASE_DIR / "config"
CURRENT_PLAN_PATH = CONFIG_DIR / "week_plan.json"
NEXT_PLAN_PATH = CONFIG_DIR / "week_plan_next.json"
PLAN_ARCHIVE_DIR = CONFIG_DIR / "plan_archive"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
RECORDS_PATH = BASE_DIR / "data" / "records.json"


def load_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def clean_problem_id(problem_id):
    value = str(problem_id or "")
    for prefix in ("题号：", "题号:", "题号"):
        value = value.replace(prefix, "")
    return value.strip()


def _get_planned_problem_ids(plan):
    problem_ids = []
    days = plan.get("days", {})
    if not isinstance(days, dict):
        return problem_ids

    for day_index in range(1, 8):
        day = days.get(str(day_index), {})
        if not isinstance(day, dict):
            continue
        problems = day.get("problems", [])
        if not isinstance(problems, list):
            continue
        for problem_id in problems:
            problem_id = clean_problem_id(problem_id)
            if problem_id and problem_id not in problem_ids:
                problem_ids.append(problem_id)
    return problem_ids


def _get_completed_problem_ids(records):
    completed = set()
    if not isinstance(records, list):
        return completed

    for record in records:
        if not isinstance(record, dict):
            continue
        status = str(record.get("status", "")).replace(" ", "")
        if status in {"AC", "看提示后AC"}:
            completed.add(clean_problem_id(record.get("problem_id")))
    return completed


def get_plan_management_data():
    plan = load_json(CURRENT_PLAN_PATH, {})
    draft = load_json(NEXT_PLAN_PATH, None)
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    records = load_json(RECORDS_PATH, [])

    if not isinstance(plan, dict):
        plan = {}
    if not isinstance(draft, dict):
        draft = None
    if not isinstance(problem_bank, dict):
        problem_bank = {}

    planned_ids = get_planned_problem_ids(plan)
    completed_ids = get_completed_problem_ids(plan, records)
    milestones = get_plan_milestones(plan)
    completed_milestone_ids = get_completed_milestone_ids(plan)
    completed_planned_ids = [
        problem_id
        for problem_id in planned_ids
        if problem_id in completed_ids
    ]

    plan_phase = get_self_paced_plan_phase(
        plan,
        completed_ids,
        completed_milestone_ids
    )
    day_index = plan_phase["day_index"]

    total_count = len(planned_ids) + len(milestones)
    completed_count = (
        len(completed_planned_ids) + len(completed_milestone_ids)
    )
    completion_rate = (
        completed_count / total_count
        if total_count
        else 0
    )

    readiness_reasons = []
    if total_count and completed_count == total_count:
        readiness_reasons.append("当前计划的题目、复习和总结已经全部完成")

    should_generate_next = bool(
        total_count and completed_count == total_count
    )
    draft_status = "missing"
    if isinstance(draft, dict):
        try:
            draft_week = int(draft.get("week", 0))
        except (TypeError, ValueError):
            draft_week = 0
        try:
            current_week = int(plan.get("week", 0))
        except (TypeError, ValueError):
            current_week = 0

        if draft_week == current_week + 1:
            draft_status = "available"
        elif draft_week <= current_week:
            draft_status = "old_or_applied"
        else:
            draft_status = "future"

    if draft_status == "available":
        draft_review = get_draft_review_status(draft)
        if draft_review.get("snoozed"):
            plan_advice = (
                "下一阶段计划草案已暂缓提醒，将在 "
                f"{draft_review.get('snoozed_until')} 再次提醒。"
            )
        else:
            plan_advice = (
                "下一阶段计划草案已生成，请查看后决定是否应用。"
            )
    elif should_generate_next:
        draft_review = {
            "status": "none",
            "snoozed": False,
            "snoozed_until": ""
        }
        plan_advice = (
            "建议生成下一阶段计划草案，查看后再决定是否应用。"
        )
    else:
        draft_review = {
            "status": "none",
            "snoozed": False,
            "snoozed_until": ""
        }
        plan_advice = "当前计划仍在进行中，建议先完成现有任务。"

    backups = []
    for path in sorted(
        CONFIG_DIR.glob("week_plan_backup_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True
    ):
        backups.append({
            "file_name": path.name,
            "modified_time": datetime.fromtimestamp(
                path.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M:%S")
        })

    archives = []
    if PLAN_ARCHIVE_DIR.exists():
        for path in sorted(
            PLAN_ARCHIVE_DIR.glob("week_plan_week_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True
        ):
            archived_plan = load_json(path, {})
            if not isinstance(archived_plan, dict):
                archived_plan = {}
            archives.append({
                "file_name": path.name,
                "week": archived_plan.get("week", ""),
                "title": archived_plan.get("title", "暂无标题"),
                "activated_at": archived_plan.get(
                    "activated_at", "未知"
                )
            })

    return {
        "plan": plan,
        "draft": draft,
        "draft_status": draft_status,
        "draft_review": draft_review,
        "problem_bank": problem_bank,
        "day_index": day_index,
        "plan_phase": plan_phase,
        "planned_problem_ids": planned_ids,
        "completed_problem_ids": completed_planned_ids,
        "completed_milestone_ids": list(completed_milestone_ids),
        "milestones": milestones,
        "completed_count": completed_count,
        "total_count": total_count,
        "completion_rate": completion_rate,
        "should_generate_next": should_generate_next,
        "readiness_reasons": readiness_reasons,
        "plan_advice": plan_advice,
        "backups": backups,
        "archives": archives
    }


def format_current_plan(data):
    plan = data.get("plan", {})
    problem_bank = data.get("problem_bank", {})
    if not isinstance(plan, dict) or not plan:
        return "目前没有可用的当前计划。"

    lines = [
        "===== 当前学习计划 =====",
        "",
        f"计划：Week {plan.get('week', '')} - {plan.get('title', '暂无标题')}",
        f"开始日期：{plan.get('start_date', '未知')}",
        f"当前进度：{data.get('completed_count', 0)} / "
        f"{data.get('total_count', 0)} 项",
        "",
        "每日安排："
    ]

    days = plan.get("days", {})
    if not isinstance(days, dict):
        days = {}

    completed = set(data.get("completed_problem_ids", []))
    for day_index in range(1, 8):
        day = days.get(str(day_index), {})
        if not isinstance(day, dict):
            day = {}
        lines.append(
            f"Day {day_index}：{day.get('goal', '暂无目标')}"
        )
        problems = day.get("problems", [])
        if not isinstance(problems, list) or not problems:
            lines.append("  - 无新题")
            continue
        for problem_id in problems:
            problem_id = clean_problem_id(problem_id)
            problem = problem_bank.get(problem_id, {})
            title = (
                problem.get("title", "题库中暂无详细信息")
                if isinstance(problem, dict)
                else "题库中暂无详细信息"
            )
            status = "已完成" if problem_id in completed else "待完成"
            lines.append(f"  - {problem_id} {title} [{status}]")

    lines.extend(["", "计划判断："])
    reasons = data.get("readiness_reasons", [])
    if reasons:
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("- 当前计划尚未进入切换阶段")
    lines.extend(["", data.get("plan_advice", "")])
    if data.get("draft_status") == "available":
        draft = data.get("draft", {})
        draft_review = data.get("draft_review", {})
        lines.extend([
            "",
            (
                "草案状态：已暂缓至 "
                f"{draft_review.get('snoozed_until', '')}"
                if draft_review.get("snoozed")
                else "草案状态：等待确认"
            ),
            f"草案目标：Week {draft.get('week', '')} - "
            f"{draft.get('title', '暂无标题')}",
            f"生成时间：{draft.get('generated_at', '未知')}"
        ])
    return "\n".join(lines)


def format_plan_backups(backups):
    lines = ["===== 计划备份 =====", ""]
    if not backups:
        lines.append("目前还没有计划备份。")
        return "\n".join(lines)

    for index, backup in enumerate(backups, start=1):
        lines.append(
            f"{index}. {backup.get('file_name', '')}"
            f"（{backup.get('modified_time', '')}）"
        )
    return "\n".join(lines)


def format_plan_archives(archives):
    lines = ["===== 已应用计划归档 =====", ""]
    if not archives:
        lines.append("目前还没有已应用的计划归档。")
        return "\n".join(lines)

    for index, archive in enumerate(archives, start=1):
        lines.extend([
            (
                f"{index}. Week {archive.get('week', '')} - "
                f"{archive.get('title', '暂无标题')}"
            ),
            f"   应用时间：{archive.get('activated_at', '未知')}",
            f"   文件：config/plan_archive/{archive.get('file_name', '')}"
        ])
    return "\n".join(lines)
