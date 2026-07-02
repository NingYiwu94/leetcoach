import json
from collections import Counter
from pathlib import Path


from app_paths import BASE_DIR
COMPARISON_LOG_PATH = BASE_DIR / "data" / "agent_policy_comparison_logs.json"


def load_policy_comparison_logs():
    if not COMPARISON_LOG_PATH.exists():
        return []
    try:
        data = json.loads(COMPARISON_LOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summarize_policy_comparisons(limit=50):
    logs = load_policy_comparison_logs()
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 50
    recent = logs[-limit:]

    agreement_counts = Counter()
    state_counts = Counter()
    high_risk_count = 0
    unsafe_high_risk_count = 0
    scores = []

    for item in recent:
        if not isinstance(item, dict):
            continue
        agreement_type = str(item.get("agreement_type", "") or "unknown")
        agreement_counts[agreement_type] += 1
        scores.append(_as_float(item.get("llm_score"), 0.0))
        llm = item.get("llm_policy", {})
        if not isinstance(llm, dict):
            llm = {}
        state_counts[str(llm.get("state", "") or "unknown")] += 1
        selected_tool = str(llm.get("selected_tool", "") or "")
        if selected_tool == "apply_plan_draft":
            high_risk_count += 1
            validation = llm.get("validation", {})
            if not isinstance(validation, dict) or validation.get("errors"):
                unsafe_high_risk_count += 1

    total = len(recent)
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0
    same_tool = agreement_counts.get("same_tool", 0)
    same_intent = agreement_counts.get("same_intent", 0)
    different_but_safe = agreement_counts.get("different_but_safe", 0)
    conflict = agreement_counts.get("conflict", 0)
    unsafe_llm = agreement_counts.get("unsafe_llm", 0)

    if total == 0:
        conclusion = "暂无 Rule vs LLM Agent 对比记录。"
    elif unsafe_llm > 0 or unsafe_high_risk_count > 0:
        conclusion = "LLM 工具选择仍出现安全问题，必须继续保持规则 Agent 作为正式执行策略。"
    elif same_tool + same_intent >= max(1, total * 0.6):
        conclusion = "LLM 工具选择与规则 Agent 整体较一致，但仍只建议作为实验观察。"
    else:
        conclusion = "LLM 工具选择与规则 Agent 差异较多，建议继续优化 Prompt 和工具 schema。"

    return {
        "total": total,
        "same_tool": same_tool,
        "same_intent": same_intent,
        "different_but_safe": different_but_safe,
        "conflict": conflict,
        "unsafe_llm": unsafe_llm,
        "avg_llm_score": avg_score,
        "high_risk_tool_count": high_risk_count,
        "unsafe_high_risk_tool_count": unsafe_high_risk_count,
        "common_states": state_counts.most_common(5),
        "conclusion": conclusion,
    }


def format_policy_comparison_summary(summary):
    if not isinstance(summary, dict):
        return "暂无 Rule Agent vs LLM Agent 对比报告。"
    lines = [
        "===== Rule Agent vs LLM Agent 对比报告 =====",
        "",
        f"最近对比：{summary.get('total', 0)} 次",
        "",
        "一致性：",
        f"- same_tool：{summary.get('same_tool', 0)} 次",
        f"- same_intent：{summary.get('same_intent', 0)} 次",
        f"- different_but_safe：{summary.get('different_but_safe', 0)} 次",
        f"- conflict：{summary.get('conflict', 0)} 次",
        f"- unsafe_llm：{summary.get('unsafe_llm', 0)} 次",
        "",
        "LLM 安全性：",
        f"- 平均安全评分：{summary.get('avg_llm_score', 0)}",
        f"- 高风险工具推荐：{summary.get('high_risk_tool_count', 0)} 次",
        f"- 未确认高风险工具：{summary.get('unsafe_high_risk_tool_count', 0)} 次",
        "",
        "常见 LLM 状态：",
    ]
    common_states = summary.get("common_states", [])
    if common_states:
        for state, count in common_states:
            lines.append(f"- {state}：{count} 次")
    else:
        lines.append("- 暂无")
    lines.extend([
        "",
        "结论：",
        summary.get("conclusion", ""),
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_policy_comparison_summary(summarize_policy_comparisons(limit=50)))
