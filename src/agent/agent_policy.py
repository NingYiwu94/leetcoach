from agent.agent_feedback_memory import load_user_learning_profile
from agent.agent_observer import collect_learning_observation


ACTION_TOOL_MAP = {
    "no_action": "no_action",
    "create_week_plan_next": "generate_plan_draft",
    "surface_review_tasks": "surface_review_tasks",
    "recommend_review_first": "recommend_review_first",
    "do_not_generate_new_plan": "do_not_generate_new_plan",
    "apply_plan_draft": "apply_plan_draft",
    "sync_leetcode_records": "sync_leetcode_records",
}


def map_action_to_tool(action):
    return ACTION_TOOL_MAP.get(str(action or ""), "no_action")


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_plan_preference():
    profile = load_user_learning_profile()
    preference = profile.get("plan_preference", {})
    if not isinstance(preference, dict):
        preference = {}
    return {
        "style": str(preference.get("style", "") or "neutral"),
        "reason": str(preference.get("reason", "") or ""),
        "confidence": _as_float(preference.get("confidence"), 0.0),
    }


def _with_feedback_note(reason, preference):
    style = preference.get("style", "neutral")
    if style not in {"conservative", "very_conservative", "trusting_agent"}:
        return reason
    note = preference.get("reason") or "Agent 已参考用户反馈记忆。"
    return f"{reason} 用户反馈记忆：{note}"


def decide_next_agent_action(observation):
    observation = observation if isinstance(observation, dict) else {}
    completion_rate = _as_float(observation.get("plan_completion_rate"))
    current_day = _as_int(observation.get("current_day"))
    overdue_reviews = _as_int(observation.get("overdue_review_count"))
    recent_failed = _as_int(observation.get("recent_failed_count"))
    preference = _get_plan_preference()
    preference_style = preference.get("style", "neutral")

    if observation.get("has_pending_plan_draft"):
        return {
            "state": "waiting_for_user_confirmation",
            "decision": "wait",
            "action": "no_action",
            "reason": "已有待确认计划草案，等待用户确认，不重复生成。",
            "confidence": 0.95,
            "requires_user_confirmation": True,
            "feedback_preference": preference,
        }

    if completion_rate >= 1.0:
        if preference_style == "very_conservative":
            return {
                "state": "plan_completed_but_user_prefers_caution",
                "decision": "wait_for_manual_plan_review",
                "action": "do_not_generate_new_plan",
                "reason": _with_feedback_note(
                    "当前计划已完成，但用户历史上较常拒绝 Agent 建议，因此暂不主动生成新计划。",
                    preference,
                ),
                "confidence": max(0.7, preference.get("confidence", 0.0)),
                "requires_user_confirmation": False,
                "feedback_preference": preference,
            }
        confidence = 0.9
        if preference_style == "conservative":
            confidence = 0.78
        elif preference_style == "trusting_agent":
            confidence = 0.93
        return {
            "state": "plan_completed",
            "decision": "generate_next_plan_draft",
            "action": "create_week_plan_next",
            "reason": _with_feedback_note(
                "当前计划已完成，且没有待确认草案，因此生成下一阶段计划草案。",
                preference,
            ),
            "confidence": confidence,
            "requires_user_confirmation": True,
            "feedback_preference": preference,
        }

    if overdue_reviews > 0:
        return {
            "state": "review_due",
            "decision": "prioritize_review",
            "action": "surface_review_tasks",
            "reason": "存在到期复习任务，应优先出现在今日任务中。",
            "confidence": 0.85,
            "requires_user_confirmation": False,
            "feedback_preference": preference,
        }

    if recent_failed >= 2:
        return {
            "state": "struggling",
            "decision": "reduce_new_tasks",
            "action": "recommend_review_first",
            "reason": "最近未通过次数较多，建议减少新题，优先复盘。",
            "confidence": 0.8,
            "requires_user_confirmation": False,
            "feedback_preference": preference,
        }

    if completion_rate < 0.5 and current_day >= 5:
        return {
            "state": "behind_schedule",
            "decision": "keep_current_plan",
            "action": "do_not_generate_new_plan",
            "reason": "当前计划进度偏慢，不应提前生成下一阶段计划。",
            "confidence": 0.8,
            "requires_user_confirmation": False,
            "feedback_preference": preference,
        }

    return {
        "state": "normal",
        "decision": "continue_current_plan",
        "action": "no_action",
        "reason": "当前学习状态正常，继续执行今日任务。",
        "confidence": 0.7,
        "requires_user_confirmation": False,
        "feedback_preference": preference,
    }


def format_agent_decision(decision):
    if not isinstance(decision, dict):
        return "暂无 Agent 决策。"
    preference = decision.get("feedback_preference", {})
    if not isinstance(preference, dict):
        preference = {}
    lines = [
        "===== Agent 当前决策 =====",
        "",
        f"状态：{decision.get('state', '')}",
        f"决策：{decision.get('decision', '')}",
        f"行动：{decision.get('action', '')}",
        f"原因：{decision.get('reason', '')}",
        f"置信度：{decision.get('confidence', 0)}",
        f"需要用户确认：{'是' if decision.get('requires_user_confirmation') else '否'}",
        "",
        "用户反馈偏好：",
        f"- 风格：{preference.get('style', 'neutral')}",
        f"- 原因：{preference.get('reason', '暂无')}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    current_observation = collect_learning_observation()
    print(format_agent_decision(decide_next_agent_action(current_observation)))
