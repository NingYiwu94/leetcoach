from agent.agent_memory import save_agent_memory
from agent.agent_state import analyze_learning_state
from app.daily_check import get_daily_check_data
from app.dashboard import get_dashboard_data


def run_agent():
    dashboard_data = get_dashboard_data()
    daily_check_data = get_daily_check_data()
    state_data = analyze_learning_state()

    day_index = dashboard_data.get("day_index", 0)
    plan_title = dashboard_data.get("plan_title", "暂无计划")
    week_name = plan_title.split(" - ", 1)[0].replace(" ", "")
    plan_phase = dashboard_data.get("plan_phase", {})
    phase_status = plan_phase.get("status", "unknown")
    if phase_status == "active":
        stage = f"{week_name} Day{day_index}"
    elif phase_status == "upcoming":
        stage = (
            f"{week_name} 未开始"
            f"（{plan_phase.get('days_until_start', 0)} 天后）"
        )
    elif phase_status == "ended":
        stage = f"{week_name} 已结束"
    else:
        stage = f"{week_name} 日期未知"

    priorities = []
    estimated_minutes = 0

    today_reviews = dashboard_data.get("today_reviews", [])
    for review in today_reviews:
        problem_id = review.get("problem_id", "")
        title = review.get("title", "未知题目")
        priorities.append(f"复习 {problem_id} {title}".strip())
        estimated_minutes += 15

    today_problems = dashboard_data.get("today_problems", [])
    for problem in today_problems:
        if problem.get("completed"):
            continue

        problem_id = problem.get("problem_id", "")
        title = problem.get("title", "未知题目")
        priorities.append(f"完成 {problem_id} {title}".strip())
        estimated_minutes += 25

    if priorities:
        priorities.append("记录今日卡点和错因")
        estimated_minutes += 5
    elif phase_status == "upcoming":
        priorities.append("整理上一阶段错题和薄弱点")
        estimated_minutes = 15
    elif phase_status == "ended":
        priorities.append("查看并确认下一阶段计划")
        estimated_minutes = 10
    else:
        priorities.append("完成今日总结或自由复盘")
        estimated_minutes = 15

    if len(priorities) > 3:
        priorities = priorities[:3]

    learning_status = state_data.get("progress_status", "未知")
    main_problem = state_data.get("main_problem", "暂无明确问题")

    if daily_check_data.get("today_review_count", 0) > 0:
        current_priority = "优先处理到期复习"
    elif daily_check_data.get("today_pending_problem_count", 0) > 0:
        current_priority = "优先完成今日计划题"
    elif phase_status == "upcoming":
        current_priority = "等待新计划开始，整理旧题和薄弱点"
    elif phase_status == "ended":
        current_priority = "确认下一阶段学习计划"
    else:
        current_priority = "今日任务已清空，进行总结或自由复盘"

    data = {
        "stage": stage,
        "learning_status": learning_status,
        "main_problem": main_problem,
        "current_priority": current_priority,
        "action_plan": priorities,
        "estimated_minutes": estimated_minutes
    }

    try:
        save_agent_memory(
            stage=stage,
            progress_status=learning_status,
            main_problem=main_problem,
            action_plan=priorities
        )
    except Exception:
        print("Agent 记忆保存失败，但今日行动方案已生成。")

    return data


def format_agent_report(data):
    lines = [
        "===== LeetCoach Agent =====",
        "",
        "当前阶段：",
        data.get("stage", "暂无计划"),
        "",
        "学习状态：",
        data.get("learning_status", "未知"),
        "",
        "当前主要问题：",
        data.get("main_problem", "暂无明确问题"),
        "",
        "当前优先任务：",
        data.get("current_priority", "暂无"),
        "",
        "今日优先级：",
        ""
    ]

    action_plan = data.get("action_plan", [])
    for index, action in enumerate(action_plan, start=1):
        lines.extend([f"P{index}:", action, ""])

    lines.extend([
        "预计耗时：",
        f"{data.get('estimated_minutes', 0)} 分钟"
    ])

    return "\n".join(lines)
