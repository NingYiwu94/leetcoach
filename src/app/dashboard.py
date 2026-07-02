import json
from datetime import date, datetime
from pathlib import Path

from core.learning_analyzer import analyze_learning_patterns
from planning.plan_progress import (
    get_completed_problem_ids,
    get_planned_problem_ids
)
from planning.plan_phase import get_self_paced_plan_phase
from planning.plan_task_state import (
    get_completed_milestone_ids,
    get_plan_milestones
)
from core.review_scheduler import (
    build_review_queue,
    get_review_pressure,
    select_daily_reviews
)


from app_paths import BASE_DIR
PLAN_PATH = BASE_DIR / "config" / "week_plan.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"


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


def short_plan_title(plan):
    if not isinstance(plan, dict):
        return "暂无计划"
    theme = str(plan.get("weekly_theme", "")).strip()
    if theme:
        return theme
    title = str(plan.get("title", "暂无计划")).strip() or "暂无计划"
    for separator in ("：", ":", "-", "—"):
        if separator in title:
            title = title.split(separator, 1)[0].strip()
            break
    for noisy_word in ("核心题巩固与验收周", "巩固与验收周", "学习周"):
        title = title.replace(noisy_word, "").strip()
    return title or "暂无计划"


def get_dashboard_data():
    plan = load_json(PLAN_PATH, {})
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    records = load_json(RECORDS_PATH, [])
    reviews = load_json(REVIEWS_PATH, [])

    if not isinstance(plan, dict):
        plan = {}
    if not isinstance(problem_bank, dict):
        problem_bank = {}
    if not isinstance(records, list):
        records = []
    if not isinstance(reviews, list):
        reviews = []

    week = plan.get("week", "")
    title = short_plan_title(plan)
    plan_title = f"Week {week} - {title}" if week != "" else title

    days = plan.get("days", {})
    if not isinstance(days, dict):
        days = {}

    planned_problem_ids = set(get_planned_problem_ids(plan))
    completed_problem_ids = get_completed_problem_ids(plan, records)
    completed_milestone_ids = get_completed_milestone_ids(plan)
    milestones = get_plan_milestones(plan)
    plan_phase = get_self_paced_plan_phase(
        plan,
        completed_problem_ids,
        completed_milestone_ids
    )
    day_index = plan_phase["day_index"]

    today_plan = days.get(str(day_index), {})
    if not isinstance(today_plan, dict):
        today_plan = {}

    today_goal = today_plan.get("goal", "暂无今日目标")
    today_problem_ids = today_plan.get("problems", [])
    if not isinstance(today_problem_ids, list):
        today_problem_ids = []

    today_problems = []
    for problem_id in today_problem_ids:
        problem_id = clean_problem_id(problem_id)
        problem = problem_bank.get(problem_id, {})
        if not isinstance(problem, dict):
            problem = {}

        today_problems.append({
            "problem_id": problem_id,
            "title": problem.get("title", "未知题目"),
            "difficulty": problem.get("difficulty", "未知难度")
        })

    today_reviews = []
    pending_review_queue = build_review_queue(
        reviews,
        records,
        due_only=False
    )
    due_review_queue = build_review_queue(
        reviews,
        records,
        due_only=True
    )
    daily_review_selection = select_daily_reviews(
        due_review_queue,
        today_problem_ids=today_problem_ids,
        task_type=today_plan.get("task_type", "")
    )
    selected_review_queue = daily_review_selection["selected"]
    pending_review_count = len(pending_review_queue)
    review_pressure = get_review_pressure(pending_review_queue)

    for review in selected_review_queue:
        problem_id = review["problem_id"]
        problem = problem_bank.get(problem_id, {})
        if not isinstance(problem, dict):
            problem = {}

        today_reviews.append({
            "problem_id": problem_id,
            "title": problem.get("title", "未知题目"),
            "priority_level": review.get("priority_level", "低"),
            "priority_score": review.get("priority_score", 0),
            "failure_count": review.get("failure_count", 0),
            "assisted_count": review.get("assisted_count", 0),
            "overdue_days": review.get("overdue_days", 0),
            "review_round": review.get("review_round", 1),
            "previous_mastery_label": review.get(
                "previous_mastery_label",
                ""
            ),
            "reason": review.get("reason", "")
        })

    for problem in today_problems:
        problem["completed"] = problem["problem_id"] in completed_problem_ids

    learning_analysis = analyze_learning_patterns(
        records=records,
        problem_bank=problem_bank
    )
    weakest_mistake_type = learning_analysis.get(
        "main_weakness",
        "暂无明确分类"
    )

    pending_today_problems = [
        problem for problem in today_problems if not problem.get("completed")
    ]
    has_today_problems = bool(pending_today_problems)
    has_today_reviews = bool(today_reviews)

    if plan_phase["status"] == "upcoming" and has_today_reviews:
        suggestion = (
            f"新计划将在 {plan_phase['days_until_start']} 天后开始，"
            "今天优先完成到期复习，为新阶段腾出精力。"
        )
    elif plan_phase["status"] == "upcoming":
        suggestion = (
            f"新计划将在 {plan_phase['days_until_start']} 天后开始，"
            "今天可以整理旧题和薄弱点，不必提前赶进度。"
        )
    elif plan_phase["status"] == "ended" and has_today_reviews:
        suggestion = (
            "当前计划周期已结束，今天先完成到期复习，再确认下一阶段计划。"
        )
    elif plan_phase["status"] == "ended":
        suggestion = "当前计划周期已结束，建议查看并确认下一阶段计划。"
    elif has_today_reviews and has_today_problems:
        top_review = today_reviews[0]
        suggestion = (
            f"建议先复习 {top_review['problem_id']}，"
            "再开始今日新题。"
        )
    elif has_today_reviews:
        top_review = today_reviews[0]
        suggestion = (
            f"今天重点复习 {top_review['problem_id']}，"
            "优先处理高风险遗忘点。"
        )
    elif has_today_problems:
        suggestion = "今天按计划完成新题，并记录主要卡点。"
    else:
        suggestion = "今天可以进行周总结或自由复盘。"

    if weakest_mistake_type != "暂无明确分类":
        suggestion += (
            f"近期主要薄弱点是“{weakest_mistake_type}”，"
            "做题时请重点关注。"
        )

    return {
        "plan_title": plan_title,
        "day_index": day_index,
        "plan_phase": plan_phase,
        "today_goal": today_goal,
        "today_problems": today_problems,
        "today_reviews": today_reviews,
        "completed_count": (
            len(completed_problem_ids) + len(completed_milestone_ids)
        ),
        "total_count": len(planned_problem_ids) + len(milestones),
        "pending_review_count": pending_review_count,
        "due_review_count": daily_review_selection["due_count"],
        "deferred_review_count": len(
            daily_review_selection["deferred"]
        ),
        "daily_review_limit": daily_review_selection["limit"],
        "review_pressure": review_pressure,
        "learning_analysis": learning_analysis,
        "weakest_mistake_type": weakest_mistake_type,
        "suggestion": suggestion
    }


def format_dashboard(data):
    day_index = data.get("day_index", 0)
    phase = data.get("plan_phase", {})
    day_text = phase.get(
        "label",
        f"Day {day_index}" if 1 <= day_index <= 7 else "计划日期未知"
    )

    lines = [
        "===== LeetCoach 首页汇总 =====",
        "",
        f"计划：{data.get('plan_title', '暂无计划')}",
        f"今天：{day_text}",
        f"今日目标：{data.get('today_goal', '暂无今日目标')}",
        "",
        "今日计划："
    ]

    today_problems = data.get("today_problems", [])
    if today_problems:
        for problem in today_problems:
            status_text = "✅ 已完成" if problem.get("completed") else "⏳ 待完成"
            lines.append(
                f"- {problem.get('problem_id', '')} "
                f"{problem.get('title', '未知题目')} "
                f"[{problem.get('difficulty', '未知难度')}] "
                f"{status_text}"
            )
    else:
        lines.append("- 今日没有新题")

    lines.extend(["", "今日复习："])
    today_reviews = data.get("today_reviews", [])
    if today_reviews:
        for review in today_reviews:
            priority = review.get("priority_level", "低")
            review_round = review.get("review_round", 1)
            lines.append(
                f"- {review.get('problem_id', '')} "
                f"{review.get('title', '未知题目')} "
                f"[第 {review_round} 轮 / {priority}优先级]"
            )
    else:
        lines.append("- 今日暂无到期复习题")

    deferred_review_count = data.get("deferred_review_count", 0)
    if deferred_review_count:
        lines.append(
            f"- 另有 {deferred_review_count} 道到期复习保留在队列中，"
            "后续按优先级安排"
        )

    lines.extend([
        "",
        (
            f"本周进度：已完成 {data.get('completed_count', 0)} / "
            f"{data.get('total_count', 0)} 项"
        ),
        f"待复习总数：{data.get('pending_review_count', 0)} 题",
        (
            "复习压力："
            f"{data.get('review_pressure', {}).get('level', '较小')}"
        ),
        f"当前主要薄弱点：{data.get('weakest_mistake_type', '暂无明确分类')}",
        "",
        "今日建议：",
        data.get("suggestion", "今天可以进行周总结或自由复盘。")
    ])

    return "\n".join(lines)
