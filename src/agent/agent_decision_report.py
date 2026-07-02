import json
from collections import Counter
from pathlib import Path

from agent.agent_decision_log import AGENT_DECISION_LOG_PATH


def load_agent_decision_logs():
    if not AGENT_DECISION_LOG_PATH.exists():
        return []
    try:
        data = json.loads(AGENT_DECISION_LOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summarize_agent_decisions(limit=50):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 50
    logs = [
        item for item in load_agent_decision_logs()[-limit:]
        if isinstance(item, dict)
    ]
    action_counts = Counter()
    state_counts = Counter()
    decision_counts = Counter()
    confidences = []

    for item in logs:
        action_counts[str(item.get("action", "") or "unknown")] += 1
        state_counts[str(item.get("state", "") or "unknown")] += 1
        decision_counts[str(item.get("decision", "") or "unknown")] += 1
        confidences.append(_as_float(item.get("confidence"), 0.0))

    avg_confidence = (
        round(sum(confidences) / len(confidences), 3)
        if confidences else 0.0
    )
    recent = []
    for item in reversed(logs[-5:]):
        recent.append({
            "timestamp": item.get("timestamp", ""),
            "state": item.get("state", ""),
            "decision": item.get("decision", ""),
            "action": item.get("action", ""),
            "reason": item.get("reason", ""),
            "confidence": item.get("confidence", 0),
            "result": item.get("result", {}),
        })

    return {
        "total": len(logs),
        "action_counts": dict(action_counts),
        "state_counts": dict(state_counts),
        "decision_counts": dict(decision_counts),
        "avg_confidence": avg_confidence,
        "most_common_states": state_counts.most_common(5),
        "recent_decisions": recent,
    }


def _count(mapping, key):
    return int((mapping or {}).get(key, 0) or 0)


def format_agent_decision_summary(summary):
    if not isinstance(summary, dict):
        return "暂无 Agent 决策统计。"
    actions = summary.get("action_counts", {}) or {}
    decisions = summary.get("decision_counts", {}) or {}
    states = summary.get("state_counts", {}) or {}
    lines = [
        "===== Agent 决策统计报告 =====",
        "",
        f"最近决策：{summary.get('total', 0)} 条",
        "",
        "总体：",
        f"- no_action：{_count(actions, 'no_action')} 次",
        f"- generate_next_plan_draft：{_count(decisions, 'generate_next_plan_draft')} 次",
        f"- create_week_plan_next：{_count(actions, 'create_week_plan_next')} 次",
        f"- surface_review_tasks：{_count(actions, 'surface_review_tasks')} 次",
        f"- recommend_review_first：{_count(actions, 'recommend_review_first')} 次",
        f"- do_not_generate_new_plan：{_count(actions, 'do_not_generate_new_plan')} 次",
        f"- waiting_for_user_confirmation：{_count(states, 'waiting_for_user_confirmation')} 次",
        f"- 平均置信度：{summary.get('avg_confidence', 0)}",
        "",
        "最常见状态：",
    ]
    states = summary.get("most_common_states", []) or []
    if states:
        for state, count in states:
            lines.append(f"- {state}：{count} 次")
    else:
        lines.append("- 暂无")

    lines.extend(["", "最近 5 条："])
    recent = summary.get("recent_decisions", []) or []
    if recent:
        for index, item in enumerate(recent, start=1):
            lines.extend([
                f"{index}. {item.get('timestamp', '')}",
                f"   状态：{item.get('state', '')}",
                f"   决策：{item.get('decision', '')}",
                f"   行动：{item.get('action', '')}",
                f"   原因：{item.get('reason', '')}",
            ])
    else:
        lines.append("- 暂无")
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    print(format_agent_decision_summary(summarize_agent_decisions(limit=50)))
