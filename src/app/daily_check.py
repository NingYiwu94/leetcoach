from app.dashboard import get_dashboard_data


def get_daily_check_data():
    dashboard_data = get_dashboard_data()
    today_problems = dashboard_data.get("today_problems", [])

    today_new_problem_count = len(today_problems)
    today_completed_problem_count = sum(
        1 for problem in today_problems if problem.get("completed")
    )
    today_pending_problem_count = (
        today_new_problem_count - today_completed_problem_count
    )
    today_review_count = len(dashboard_data.get("today_reviews", []))
    due_review_count = dashboard_data.get(
        "due_review_count",
        today_review_count
    )
    deferred_review_count = dashboard_data.get(
        "deferred_review_count",
        0
    )
    pending_review_count = dashboard_data.get("pending_review_count", 0)
    review_pressure = dashboard_data.get("review_pressure", {})
    plan_phase = dashboard_data.get("plan_phase", {})
    phase_status = plan_phase.get("status", "unknown")

    if phase_status == "upcoming" and today_review_count > 0:
        suggestion = (
            f"新计划还有 {plan_phase.get('days_until_start', 0)} 天开始，"
            "建议今天优先处理到期复习。"
        )
    elif phase_status == "upcoming":
        suggestion = (
            f"新计划还有 {plan_phase.get('days_until_start', 0)} 天开始，"
            "今天可以整理错题和薄弱点。"
        )
    elif phase_status == "ended" and today_review_count > 0:
        suggestion = "当前计划已结束，建议先完成到期复习，再确认下一阶段计划。"
    elif phase_status == "ended":
        suggestion = "当前计划已结束，建议查看并确认下一阶段计划。"
    elif today_pending_problem_count > 0 and today_review_count > 0:
        suggestion = "今天还有新题和复习任务，建议先完成复习，再做新题。"
    elif today_pending_problem_count > 0:
        suggestion = "今天还有新题未完成，建议优先完成今日计划。"
    elif today_review_count > 0:
        suggestion = "今天没有新题压力，建议完成到期复习。"
    else:
        suggestion = "今天任务已清空，可以做总结或自由练习。"

    return {
        "today_new_problem_count": today_new_problem_count,
        "today_completed_problem_count": today_completed_problem_count,
        "today_pending_problem_count": today_pending_problem_count,
        "today_review_count": today_review_count,
        "due_review_count": due_review_count,
        "deferred_review_count": deferred_review_count,
        "pending_review_count": pending_review_count,
        "review_pressure": review_pressure.get("level", "较小"),
        "plan_phase": plan_phase,
        "suggestion": suggestion
    }


def format_daily_check(data):
    return "\n".join([
        "===== 今日状态检查 =====",
        "",
        f"今日新题：{data.get('today_new_problem_count', 0)} 题",
        f"今日已完成：{data.get('today_completed_problem_count', 0)} 题",
        f"今日待完成：{data.get('today_pending_problem_count', 0)} 题",
        f"今日到期复习：{data.get('today_review_count', 0)} 题",
        (
            f"复习队列暂缓：{data.get('deferred_review_count', 0)} 题"
        ),
        f"总待复习：{data.get('pending_review_count', 0)} 题",
        f"复习压力：{data.get('review_pressure', '较小')}",
        "",
        "状态判断：",
        data.get("suggestion", "今天任务已清空，可以做总结或自由练习。")
    ])
