import json
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
DATA_DIR = BASE_DIR / "data"
PENDING_ACTIONS_PATH = DATA_DIR / "agent_pending_actions.json"
TOOL_CALL_LOG_PATH = DATA_DIR / "agent_tool_call_logs.json"
DECISION_LOG_PATH = DATA_DIR / "agent_decision_logs.json"
USER_LEARNING_PROFILE_PATH = DATA_DIR / "user_learning_profile.json"

FEEDBACK_STATUSES = {"confirmed", "rejected", "snoozed", "executed", "failed"}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _backup_broken_file(path):
    if not path.exists():
        return
    backup = path.with_name(
        f"{path.stem}.broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    )
    try:
        path.replace(backup)
    except OSError:
        pass


def load_json(path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return data


def _load_profile_json(path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _backup_broken_file(path)
        return default
    except OSError:
        return default
    return data


def load_user_learning_profile():
    profile = _load_profile_json(USER_LEARNING_PROFILE_PATH, {})
    return profile if isinstance(profile, dict) else {}


def _get_response_type(action):
    response = action.get("user_response")
    if isinstance(response, dict):
        response_type = str(response.get("type", "")).strip()
        if response_type:
            return response_type
    status = str(action.get("status", "")).strip()
    if status == "executed":
        return "confirmed"
    if status in {"confirmed", "rejected", "snoozed"}:
        return status
    if status == "failed" and isinstance(response, dict):
        return str(response.get("type", "")).strip() or "confirmed"
    return ""


def _is_feedback_action(action):
    if not isinstance(action, dict):
        return False
    if isinstance(action.get("user_response"), dict):
        return True
    return str(action.get("status", "")).strip() in FEEDBACK_STATUSES


def _preference_from_counts(stats):
    total = stats.get("confirmed", 0) + stats.get("rejected", 0) + stats.get("snoozed", 0)
    if total < 2:
        return "insufficient_data"
    ranked = sorted(
        [
            ("often_confirmed", stats.get("confirmed", 0)),
            ("often_rejected", stats.get("rejected", 0)),
            ("often_snoozed", stats.get("snoozed", 0)),
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    if ranked[0][1] == 0:
        return "insufficient_data"
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "mixed"
    return ranked[0][0]


def _format_rate(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def analyze_user_feedback(limit=100):
    pending_actions = load_json(PENDING_ACTIONS_PATH, [])
    tool_logs = load_json(TOOL_CALL_LOG_PATH, [])
    decision_logs = load_json(DECISION_LOG_PATH, [])
    if not isinstance(pending_actions, list):
        pending_actions = []
    if not isinstance(tool_logs, list):
        tool_logs = []
    if not isinstance(decision_logs, list):
        decision_logs = []

    feedback_actions = [
        action for action in pending_actions
        if _is_feedback_action(action)
    ][-max(1, int(limit or 100)):]

    confirmed_count = 0
    rejected_count = 0
    snoozed_count = 0
    executed_count = 0
    failed_count = 0
    action_preferences = {}

    for action in feedback_actions:
        response_type = _get_response_type(action)
        status = str(action.get("status", "")).strip()
        action_type = str(action.get("action_type") or action.get("tool_name") or "unknown")
        stats = action_preferences.setdefault(
            action_type,
            {
                "confirmed": 0,
                "rejected": 0,
                "snoozed": 0,
                "executed": 0,
                "failed": 0,
                "preference": "insufficient_data",
            },
        )

        if response_type == "confirmed":
            confirmed_count += 1
            stats["confirmed"] += 1
        elif response_type == "rejected":
            rejected_count += 1
            stats["rejected"] += 1
        elif response_type == "snoozed":
            snoozed_count += 1
            stats["snoozed"] += 1

        if status == "executed":
            executed_count += 1
            stats["executed"] += 1
        elif status == "failed":
            failed_count += 1
            stats["failed"] += 1

    for stats in action_preferences.values():
        stats["preference"] = _preference_from_counts(stats)

    total_feedback_count = confirmed_count + rejected_count + snoozed_count
    if total_feedback_count:
        confirmation_rate = confirmed_count / total_feedback_count
        rejection_rate = rejected_count / total_feedback_count
        snooze_rate = snoozed_count / total_feedback_count
    else:
        confirmation_rate = 0.0
        rejection_rate = 0.0
        snooze_rate = 0.0

    guidelines = []
    style = "neutral"
    reason = "用户反馈分布较均衡，暂时保持当前 Agent 节奏。"
    confidence = 0.45

    if total_feedback_count < 3:
        style = "insufficient_data"
        reason = "反馈数据较少，暂不形成强偏好。"
        confidence = 0.2
        guidelines.append("反馈数据较少，Agent 应保持克制，不要过度推断用户偏好。")
    else:
        if confirmation_rate >= 0.7:
            style = "trusting_agent"
            reason = "用户较常确认 Agent 建议，可以继续在关键节点主动生成计划草案。"
            confidence = min(0.9, 0.55 + confirmation_rate * 0.35)
            guidelines.append("用户较常确认 Agent 建议，可以继续在关键节点主动生成计划草案。")
        if snooze_rate >= 0.4:
            style = "conservative"
            reason = "用户经常暂缓 Agent 建议，计划切换应更克制。"
            confidence = min(0.85, 0.55 + snooze_rate * 0.35)
            guidelines.append("用户经常暂缓 Agent 建议，计划切换应更克制。")
        if rejection_rate >= 0.3:
            style = "very_conservative"
            reason = "用户较常拒绝 Agent 建议，后续应降低自动建议频率，并提供更明确理由。"
            confidence = min(0.9, 0.6 + rejection_rate * 0.35)
            guidelines.append("用户较常拒绝 Agent 建议，后续应降低自动建议频率，并提供更明确理由。")

    apply_plan_stats = action_preferences.get("apply_plan_draft", {})
    if apply_plan_stats.get("preference") == "often_snoozed":
        guidelines.append("应用计划草案前，应在 UI 中更清楚说明切换原因。")
    if apply_plan_stats.get("preference") == "often_rejected":
        guidelines.append("不要主动推进计划应用，除非用户明确要求。")

    generate_plan_stats = action_preferences.get("generate_plan_draft", {})
    create_plan_stats = action_preferences.get("create_week_plan_next", {})
    if (
        generate_plan_stats.get("preference") == "often_confirmed"
        or create_plan_stats.get("preference") == "often_confirmed"
    ):
        guidelines.append("用户接受 AI 计划草案生成，可继续保留该主动建议。")

    # Keep order stable while avoiding duplicate guidance.
    seen = set()
    unique_guidelines = []
    for item in guidelines:
        if item in seen:
            continue
        seen.add(item)
        unique_guidelines.append(item)

    return {
        "updated_at": _now(),
        "source": {
            "pending_actions_count": len(pending_actions),
            "tool_call_log_count": len(tool_logs),
            "decision_log_count": len(decision_logs),
            "feedback_window": len(feedback_actions),
        },
        "feedback_summary": {
            "total_feedback_count": total_feedback_count,
            "confirmed_count": confirmed_count,
            "rejected_count": rejected_count,
            "snoozed_count": snoozed_count,
            "executed_count": executed_count,
            "failed_count": failed_count,
            "confirmation_rate": round(confirmation_rate, 4),
            "rejection_rate": round(rejection_rate, 4),
            "snooze_rate": round(snooze_rate, 4),
        },
        "plan_preference": {
            "style": style,
            "reason": reason,
            "confidence": round(confidence, 2),
        },
        "action_preferences": action_preferences,
        "agent_guidelines": unique_guidelines,
    }


def save_user_learning_profile(profile):
    safe_profile = profile if isinstance(profile, dict) else {}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if USER_LEARNING_PROFILE_PATH.exists():
        try:
            json.loads(USER_LEARNING_PROFILE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _backup_broken_file(USER_LEARNING_PROFILE_PATH)
        except OSError:
            pass
    USER_LEARNING_PROFILE_PATH.write_text(
        json.dumps(safe_profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return safe_profile


def format_user_feedback_report(profile):
    if not isinstance(profile, dict) or not profile:
        return "===== 用户反馈记忆 =====\n\n暂无用户反馈记忆。"

    summary = profile.get("feedback_summary", {}) if isinstance(profile.get("feedback_summary"), dict) else {}
    preference = profile.get("plan_preference", {}) if isinstance(profile.get("plan_preference"), dict) else {}
    action_preferences = profile.get("action_preferences", {})
    if not isinstance(action_preferences, dict):
        action_preferences = {}
    guidelines = profile.get("agent_guidelines", [])
    if not isinstance(guidelines, list):
        guidelines = []

    lines = [
        "===== 用户反馈记忆 =====",
        "",
        f"更新时间：{profile.get('updated_at', '')}",
        "",
        "反馈概况：",
        f"- 总反馈数：{summary.get('total_feedback_count', 0)}",
        f"- 确认：{summary.get('confirmed_count', 0)}（{_format_rate(summary.get('confirmation_rate', 0))}）",
        f"- 拒绝：{summary.get('rejected_count', 0)}（{_format_rate(summary.get('rejection_rate', 0))}）",
        f"- 暂缓：{summary.get('snoozed_count', 0)}（{_format_rate(summary.get('snooze_rate', 0))}）",
        "",
        "计划偏好：",
        f"- 风格：{preference.get('style', 'unknown')}",
        f"- 置信度：{preference.get('confidence', 0)}",
        f"- 原因：{preference.get('reason', '')}",
        "",
        "动作偏好：",
    ]
    if action_preferences:
        for action_type, stats in sorted(action_preferences.items()):
            if not isinstance(stats, dict):
                continue
            lines.append(
                "- {action_type}：确认 {confirmed}，拒绝 {rejected}，暂缓 {snoozed}，偏好 {preference}".format(
                    action_type=action_type,
                    confirmed=stats.get("confirmed", 0),
                    rejected=stats.get("rejected", 0),
                    snoozed=stats.get("snoozed", 0),
                    preference=stats.get("preference", "unknown"),
                )
            )
    else:
        lines.append("- 暂无")

    lines.extend(["", "Agent 后续准则："])
    if guidelines:
        lines.extend(f"- {item}" for item in guidelines)
    else:
        lines.append("- 暂无明确准则。")

    return "\n".join(lines)


def format_user_learning_profile_for_prompt(profile):
    if not isinstance(profile, dict) or not profile:
        return "暂无用户反馈偏好。"
    preference = profile.get("plan_preference", {}) if isinstance(profile.get("plan_preference"), dict) else {}
    summary = profile.get("feedback_summary", {}) if isinstance(profile.get("feedback_summary"), dict) else {}
    guidelines = profile.get("agent_guidelines", [])
    if not isinstance(guidelines, list):
        guidelines = []

    lines = [
        f"偏好风格：{preference.get('style', 'unknown')}",
        f"偏好原因：{preference.get('reason', '')}",
        f"确认率：{_format_rate(summary.get('confirmation_rate', 0))}",
        f"拒绝率：{_format_rate(summary.get('rejection_rate', 0))}",
        f"暂缓率：{_format_rate(summary.get('snooze_rate', 0))}",
    ]
    if guidelines:
        lines.append("生成计划时请参考：")
        lines.extend(f"- {item}" for item in guidelines[:5])
    else:
        lines.append("暂无明确长期准则。")
    return "\n".join(lines)


if __name__ == "__main__":
    current_profile = analyze_user_feedback()
    save_user_learning_profile(current_profile)
    print(format_user_feedback_report(current_profile))
