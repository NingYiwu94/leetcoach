from app.dashboard import (
    PLAN_PATH,
    RECORDS_PATH,
    get_dashboard_data,
    load_json
)
from core.learning_analyzer import analyze_learning_patterns


def analyze_learning_state():
    dashboard_data = get_dashboard_data()
    plan = load_json(PLAN_PATH, {})
    records = load_json(RECORDS_PATH, [])

    if not isinstance(plan, dict):
        plan = {}
    if not isinstance(records, list):
        records = []

    week = plan.get("week", "")
    title = plan.get("title", "暂无计划")
    plan_phase = dashboard_data.get("plan_phase", {})
    phase_label = plan_phase.get("label", "")
    current_stage = f"Week {week} {title}" if week != "" else title
    if phase_label:
        current_stage = f"{current_stage}（{phase_label}）"

    completed_count = dashboard_data.get("completed_count", 0)
    total_count = dashboard_data.get("total_count", 0)
    completion_rate = completed_count / total_count if total_count else 0
    pending_review_count = dashboard_data.get("pending_review_count", 0)
    review_pressure = dashboard_data.get("review_pressure", {})
    phase_status = plan_phase.get("status", "unknown")
    pending_plan_count = max(total_count - completed_count, 0)

    if phase_status == "upcoming":
        progress_status = "等待计划开始"
        recommended_action = (
            "新计划尚未开始，建议先处理到期复习并整理上一阶段薄弱点。"
        )
    elif phase_status == "ended" and pending_plan_count > 0:
        progress_status = "计划已结束但有遗留"
        recommended_action = (
            f"当前计划仍有 {pending_plan_count} 项任务未完成，"
            "建议纳入下一阶段计划。"
        )
    elif phase_status == "ended":
        progress_status = "当前计划已完成"
        recommended_action = "建议查看并确认下一阶段计划。"
    elif phase_status == "unknown":
        progress_status = "计划日期待检查"
        recommended_action = "建议检查当前计划的 start_date 配置。"
    elif completion_rate < 0.5:
        progress_status = "进度偏慢"
        recommended_action = "建议优先补齐本阶段任务，不要急着增加新题。"
    elif completion_rate >= 0.8 and pending_review_count < 3:
        progress_status = "进度良好"
        recommended_action = "可以进入下一周计划，并适当增加新题。"
    else:
        progress_status = "进度正常"
        recommended_action = "建议继续完成本周计划，保持当前学习节奏。"

    if review_pressure.get("level") == "较大":
        review_status = "复习压力较大"
        recommended_action += "建议今天优先处理到期复习。"
    elif pending_review_count:
        review_status = "复习压力正常"
    else:
        review_status = "复习压力较小"

    learning_analysis = analyze_learning_patterns(records=records)
    main_problem = learning_analysis.get(
        "main_weakness",
        "暂无明确问题"
    )
    if main_problem == "暂无明确分类":
        main_problem = "暂无明确问题"

    main_topic = learning_analysis.get("main_topic", "")
    if main_topic:
        recommended_action += (
            f"做题时重点关注“{main_topic}”相关问题。"
        )

    return {
        "current_stage": current_stage,
        "progress_status": progress_status,
        "review_status": review_status,
        "main_problem": main_problem,
        "learning_analysis": learning_analysis,
        "recommended_action": recommended_action
    }


def format_agent_state(data):
    return "\n".join([
        "===== LeetCoach Agent 状态判断 =====",
        "",
        f"当前阶段：{data.get('current_stage', '暂无计划')}",
        f"进度状态：{data.get('progress_status', '未知')}",
        f"复习状态：{data.get('review_status', '未知')}",
        f"主要问题：{data.get('main_problem', '暂无明确问题')}",
        f"推荐行动：{data.get('recommended_action', '建议继续保持学习记录。')}"
    ])
