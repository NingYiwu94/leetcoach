import json
from datetime import datetime
from pathlib import Path

from core.learning_analyzer import summarize_review_mastery
from planning.plan_progress import (
    get_completed_problem_ids,
    get_plan_records,
    get_planned_problem_ids
)


from app_paths import BASE_DIR
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def generate_stage_summary(
    plan,
    records=None,
    reviews=None,
    problem_bank=None
):
    plan = plan if isinstance(plan, dict) else {}
    records = (
        records
        if isinstance(records, list)
        else load_json(RECORDS_PATH, [])
    )
    reviews = (
        reviews
        if isinstance(reviews, list)
        else load_json(REVIEWS_PATH, [])
    )
    problem_bank = (
        problem_bank
        if isinstance(problem_bank, dict)
        else load_json(PROBLEM_BANK_PATH, {})
    )

    planned_ids = get_planned_problem_ids(plan)
    completed_ids = get_completed_problem_ids(plan, records)
    plan_records = get_plan_records(plan, records)
    mastery = summarize_review_mastery(reviews)

    statuses = {"AC": 0, "看提示后AC": 0, "未通过": 0}
    for record in plan_records:
        status = str(record.get("status", "")).replace(" ", "")
        if status in statuses:
            statuses[status] += 1

    mastery_groups = {
        "independent": [],
        "assisted": [],
        "not_mastered": [],
        "not_assessed": []
    }
    for problem_id in planned_ids:
        result = mastery.get(problem_id, {}).get("latest_result")
        if result not in mastery_groups:
            result = "not_assessed"
        mastery_groups[result].append(problem_id)

    unfinished_ids = [
        problem_id
        for problem_id in planned_ids
        if problem_id not in completed_ids
    ]
    needs_review = []
    for problem_id in (
        mastery_groups["not_mastered"]
        + mastery_groups["assisted"]
        + unfinished_ids
    ):
        if problem_id not in needs_review:
            needs_review.append(problem_id)

    if mastery_groups["not_mastered"]:
        conclusion = "本阶段尚未达标，下一阶段应继续当前专题并减少新题。"
        recommendation = (
            "优先重做“仍未掌握”的题，达到不看完整题解写出后再进入新专题。"
        )
    elif unfinished_ids:
        conclusion = "本阶段尚未完成，仍有计划题需要补齐。"
        recommendation = "先完成本阶段遗留题，再进行核心题复习和阶段验收。"
    elif mastery_groups["assisted"]:
        conclusion = "本阶段基本完成，但独立解题稳定性仍需巩固。"
        recommendation = (
            "下一阶段前两天优先重做需要提示或未完成的题，再少量加入新题。"
        )
    else:
        conclusion = "本阶段已完成，可以进入下一专题。"
        recommendation = "保持复习节奏，并按课程路线进入下一专题。"

    def describe(problem_id):
        problem = problem_bank.get(problem_id, {})
        title = (
            problem.get("title", "")
            if isinstance(problem, dict)
            else ""
        )
        return f"{problem_id} {title}".strip()

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "week": plan.get("week"),
        "plan_title": plan.get("title", "当前阶段"),
        "weekly_theme": plan.get(
            "weekly_theme",
            plan.get("title", "当前专题")
        ),
        "planned_count": len(planned_ids),
        "completed_count": len(completed_ids),
        "completed_problems": [
            describe(problem_id)
            for problem_id in planned_ids
            if problem_id in completed_ids
        ],
        "status_counts": statuses,
        "mastery": mastery_groups,
        "needs_review": needs_review,
        "conclusion": conclusion,
        "recommendation": recommendation
    }


def format_stage_summary(summary, problem_bank=None):
    if not isinstance(summary, dict):
        return "阶段总结暂时不可用。"
    problem_bank = (
        problem_bank
        if isinstance(problem_bank, dict)
        else load_json(PROBLEM_BANK_PATH, {})
    )

    def names(problem_ids):
        values = []
        for problem_id in problem_ids:
            problem = problem_bank.get(problem_id, {})
            title = (
                problem.get("title", "")
                if isinstance(problem, dict)
                else ""
            )
            values.append(f"{problem_id} {title}".strip())
        return "、".join(values) or "暂无"

    mastery = summary.get("mastery", {})
    status_counts = summary.get("status_counts", {})
    return "\n".join([
        "===== 本阶段学习总结 =====",
        "",
        (
            f"阶段：Week {summary.get('week', '')} - "
            f"{summary.get('plan_title', '当前阶段')}"
        ),
        f"专题：{summary.get('weekly_theme', '当前专题')}",
        (
            f"计划完成：{summary.get('completed_count', 0)} / "
            f"{summary.get('planned_count', 0)} 题"
        ),
        (
            "本阶段提交："
            f"AC {status_counts.get('AC', 0)} 次，"
            f"看提示后 AC {status_counts.get('看提示后AC', 0)} 次，"
            f"未通过 {status_counts.get('未通过', 0)} 次"
        ),
        "",
        "掌握度验收：",
        f"- 独立写出：{names(mastery.get('independent', []))}",
        f"- 看提示写出：{names(mastery.get('assisted', []))}",
        f"- 仍未掌握：{names(mastery.get('not_mastered', []))}",
        f"- 尚未验收：{names(mastery.get('not_assessed', []))}",
        "",
        f"阶段判断：{summary.get('conclusion', '')}",
        f"下一步建议：{summary.get('recommendation', '')}"
    ])
