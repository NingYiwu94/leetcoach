import json
from collections import Counter, defaultdict

from agent.agent_tool_log import AGENT_TOOL_CALL_LOG_PATH
from agent.agent_tools import get_tool_definition


def load_agent_tool_logs():
    if not AGENT_TOOL_CALL_LOG_PATH.exists():
        return []
    try:
        data = json.loads(AGENT_TOOL_CALL_LOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def summarize_agent_tool_calls(limit=50):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 50

    logs = [
        item for item in load_agent_tool_logs()[-limit:]
        if isinstance(item, dict)
    ]
    tool_counts = Counter()
    status_counts = Counter()
    failed_tool_counts = Counter()
    high_risk_auto_executed = []
    recent = []

    for item in logs:
        tool_name = str(item.get("tool_name", "") or "unknown")
        status = str(
            (item.get("tool_result") or {}).get("status")
            or item.get("status")
            or "unknown"
        )
        tool_counts[tool_name] += 1
        status_counts[status] += 1
        if status == "failed":
            failed_tool_counts[tool_name] += 1
        if (
            item.get("risk_level") == "high"
            and item.get("executed")
            and status == "executed"
        ):
            high_risk_auto_executed.append(item)

    for item in reversed(logs[-5:]):
        result = item.get("tool_result") if isinstance(item.get("tool_result"), dict) else {}
        recent.append({
            "timestamp": item.get("timestamp", ""),
            "tool_name": item.get("tool_name", ""),
            "status": result.get("status") or item.get("status", ""),
            "message": result.get("message", ""),
            "risk_level": item.get("risk_level", ""),
            "requires_confirmation": item.get("requires_confirmation", False),
        })

    return {
        "total": len(logs),
        "tool_counts": dict(tool_counts),
        "status_counts": dict(status_counts),
        "failed_tool_counts": dict(failed_tool_counts),
        "most_failed_tool": failed_tool_counts.most_common(1)[0] if failed_tool_counts else None,
        "high_risk_auto_executed_count": len(high_risk_auto_executed),
        "recent_tool_calls": recent,
    }


def _count(mapping, key):
    return int((mapping or {}).get(key, 0) or 0)


def format_agent_tool_summary(summary):
    if not isinstance(summary, dict):
        return "暂无 Agent 工具调用统计。"
    tools = summary.get("tool_counts", {}) or {}
    statuses = summary.get("status_counts", {}) or {}
    lines = [
        "===== Agent 工具调用统计 =====",
        "",
        f"最近工具调用：{summary.get('total', 0)} 次",
        "",
        "按工具：",
    ]

    for tool_name in [
        "no_action",
        "generate_plan_draft",
        "surface_review_tasks",
        "recommend_review_first",
        "do_not_generate_new_plan",
        "sync_leetcode_records",
        "apply_plan_draft",
    ]:
        lines.append(f"- {tool_name}：{_count(tools, tool_name)} 次")

    lines.extend([
        "",
        "状态：",
        f"- executed：{_count(statuses, 'executed')} 次",
        f"- skipped：{_count(statuses, 'skipped')} 次",
        f"- failed：{_count(statuses, 'failed')} 次",
        f"- pending_confirmation：{_count(statuses, 'pending_confirmation')} 次",
        "",
        "安全检查：",
    ])
    if summary.get("high_risk_auto_executed_count"):
        lines.append(
            f"- 警告：发现 {summary.get('high_risk_auto_executed_count')} 次高风险工具自动执行。"
        )
    else:
        lines.append("- 高风险工具未被自动执行，符合预期。")

    most_failed = summary.get("most_failed_tool")
    if most_failed:
        lines.append(f"- 失败最多的工具：{most_failed[0]}（{most_failed[1]} 次）")
    else:
        lines.append("- 暂无工具失败记录。")

    lines.extend(["", "最近 5 次："])
    recent = summary.get("recent_tool_calls", []) or []
    if not recent:
        lines.append("- 暂无")
    else:
        for index, item in enumerate(recent, start=1):
            lines.extend([
                f"{index}. {item.get('timestamp', '')}",
                f"   工具：{item.get('tool_name', '')}",
                f"   状态：{item.get('status', '')}",
                f"   风险：{item.get('risk_level', '')}",
                f"   说明：{item.get('message', '')}",
            ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    print(format_agent_tool_summary(summarize_agent_tool_calls(limit=50)))
