from collections import Counter

from agent.agent_pending_actions import load_pending_actions


def summarize_pending_actions(limit=50):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 50

    actions = [
        action for action in load_pending_actions()[-limit:]
        if isinstance(action, dict)
    ]
    status_counts = Counter(str(action.get("status", "unknown")) for action in actions)
    active = [
        action for action in actions
        if action.get("status") in {"pending", "snoozed"}
    ]
    recent = list(reversed(actions[-5:]))
    return {
        "total": len(actions),
        "active_count": len(active),
        "active_actions": active,
        "status_counts": dict(status_counts),
        "recent_actions": recent,
    }


def _count(mapping, key):
    return int((mapping or {}).get(key, 0) or 0)


def format_pending_actions_report(summary):
    if not isinstance(summary, dict):
        return "暂无 Agent 待确认动作报告。"
    statuses = summary.get("status_counts", {}) or {}
    lines = [
        "===== Agent 待确认动作报告 =====",
        "",
        f"当前待确认：{summary.get('active_count', 0)} 条",
        "",
    ]

    active = summary.get("active_actions", []) or []
    if active:
        for index, action in enumerate(active, start=1):
            lines.extend([
                f"{index}. {action.get('title', '')}",
                f"   action_id：{action.get('action_id', '')}",
                f"   工具：{action.get('tool_name', '')}",
                f"   风险等级：{action.get('risk_level', '')}",
                f"   原因：{action.get('reason', '')}",
                f"   状态：{action.get('status', '')}",
                "",
            ])
    else:
        lines.extend(["当前没有待确认动作。", ""])

    lines.extend([
        "历史统计：",
        f"- pending：{_count(statuses, 'pending')}",
        f"- confirmed：{_count(statuses, 'confirmed')}",
        f"- rejected：{_count(statuses, 'rejected')}",
        f"- snoozed：{_count(statuses, 'snoozed')}",
        f"- executed：{_count(statuses, 'executed')}",
        f"- failed：{_count(statuses, 'failed')}",
        "",
        "最近 5 条：",
    ])
    recent = summary.get("recent_actions", []) or []
    if not recent:
        lines.append("- 暂无")
    else:
        for index, action in enumerate(recent, start=1):
            lines.extend([
                f"{index}. {action.get('created_at', '')}",
                f"   标题：{action.get('title', '')}",
                f"   工具：{action.get('tool_name', '')}",
                f"   状态：{action.get('status', '')}",
            ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    print(format_pending_actions_report(summarize_pending_actions(limit=50)))
