import json
from datetime import datetime
from pathlib import Path

from agent.agent_observer import collect_learning_observation
from agent.agent_policy import decide_next_agent_action, map_action_to_tool
from labs.llm_tool_selector import format_llm_tool_selection, select_tool_with_llm


from app_paths import BASE_DIR
COMPARISON_LOG_PATH = BASE_DIR / "data" / "agent_policy_comparison_logs.json"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_logs():
    if not COMPARISON_LOG_PATH.exists():
        return []
    try:
        data = json.loads(COMPARISON_LOG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = COMPARISON_LOG_PATH.with_name(
            f"{COMPARISON_LOG_PATH.stem}.broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        )
        try:
            COMPARISON_LOG_PATH.replace(backup)
        except OSError:
            pass
        return []
    except OSError:
        return []
    return data if isinstance(data, list) else []


def _save_log(record):
    COMPARISON_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logs = _load_logs()
    logs.append(record)
    COMPARISON_LOG_PATH.write_text(
        json.dumps(logs[-500:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return record


def _observation_summary(observation):
    observation = observation if isinstance(observation, dict) else {}
    return {
        "current_week": observation.get("current_week"),
        "current_day": observation.get("current_day"),
        "plan_completion_rate": observation.get("plan_completion_rate"),
        "pending_review_count": observation.get("pending_review_count"),
        "overdue_review_count": observation.get("overdue_review_count"),
        "has_pending_plan_draft": observation.get("has_pending_plan_draft"),
        "recent_failed_count": observation.get("recent_failed_count"),
    }


def _intent(tool_name):
    tool_name = str(tool_name or "")
    if tool_name in {"no_action", "do_not_generate_new_plan"}:
        return "wait"
    if tool_name in {"surface_review_tasks", "recommend_review_first"}:
        return "review_first"
    if tool_name in {"generate_plan_draft"}:
        return "generate_plan"
    if tool_name in {"apply_plan_draft"}:
        return "apply_plan"
    if tool_name in {"sync_leetcode_records"}:
        return "sync"
    return tool_name or "unknown"


def _agreement_type(rule_tool, llm_tool, llm_safe):
    if not llm_safe:
        return "unsafe_llm"
    if rule_tool == llm_tool:
        return "same_tool"
    if _intent(rule_tool) == _intent(llm_tool):
        return "same_intent"
    if llm_tool:
        return "different_but_safe"
    return "conflict"


def _analysis_text(agreement_type, rule_tool, llm_tool):
    if agreement_type == "same_tool":
        return f"LLM 与规则 Agent 均选择 {rule_tool}，当前状态判断一致。"
    if agreement_type == "same_intent":
        return f"LLM 选择 {llm_tool}，规则 Agent 选择 {rule_tool}，工具不同但意图接近。"
    if agreement_type == "different_but_safe":
        return f"LLM 选择 {llm_tool}，规则 Agent 选择 {rule_tool}。LLM 建议安全，但与规则策略不同，适合继续观察。"
    if agreement_type == "unsafe_llm":
        return "LLM 推荐结果未通过安全校验，不能执行。规则 Agent 仍应作为正式策略。"
    return "LLM 与规则 Agent 存在冲突，建议检查 observation、工具 schema 和 Prompt。"


def compare_rule_and_llm_policy():
    observation = collect_learning_observation()
    rule_decision = decide_next_agent_action(observation)
    rule_tool = map_action_to_tool(rule_decision.get("action"))
    llm_selection = select_tool_with_llm(observation=observation)
    llm_tool = str(llm_selection.get("selected_tool", "") or "")
    llm_safe = bool(llm_selection.get("safe"))
    agreement_type = _agreement_type(rule_tool, llm_tool, llm_safe)

    result = {
        "timestamp": _now(),
        "observation_summary": _observation_summary(observation),
        "rule_policy": {
            "state": rule_decision.get("state"),
            "action": rule_decision.get("action"),
            "tool": rule_tool,
            "reason": rule_decision.get("reason"),
            "confidence": rule_decision.get("confidence"),
        },
        "llm_policy": {
            "state": llm_selection.get("state"),
            "selected_tool": llm_tool,
            "tool_input": llm_selection.get("tool_input", {}),
            "reason": llm_selection.get("reason"),
            "confidence": llm_selection.get("confidence"),
            "requires_user_confirmation": llm_selection.get("requires_user_confirmation"),
            "should_execute": llm_selection.get("should_execute"),
            "fallback_used": llm_selection.get("fallback_used"),
            "validation": llm_selection.get("validation", {}),
        },
        "agreement": agreement_type in {"same_tool", "same_intent"},
        "agreement_type": agreement_type,
        "llm_valid": bool(llm_selection.get("schema_valid")),
        "llm_safe": llm_safe,
        "llm_score": llm_selection.get("score", 0),
        "analysis": _analysis_text(agreement_type, rule_tool, llm_tool),
    }
    return _save_log(result)


def format_policy_comparison(result):
    if not isinstance(result, dict):
        return "暂无 Rule vs LLM Agent 对比结果。"
    observation = result.get("observation_summary", {})
    rule = result.get("rule_policy", {})
    llm = result.get("llm_policy", {})
    validation = llm.get("validation", {}) if isinstance(llm, dict) else {}
    if not isinstance(validation, dict):
        validation = {}

    lines = [
        "===== Rule Agent vs LLM Agent 对比 =====",
        "",
        f"时间：{result.get('timestamp', '')}",
        "",
        "Observation：",
        f"- Week：{observation.get('current_week')}",
        f"- Day：{observation.get('current_day')}",
        f"- 计划完成率：{observation.get('plan_completion_rate')}",
        f"- 到期复习：{observation.get('overdue_review_count')}",
        f"- 待确认草案：{observation.get('has_pending_plan_draft')}",
        "",
        "规则 Agent：",
        f"- state：{rule.get('state')}",
        f"- action：{rule.get('action')}",
        f"- tool：{rule.get('tool')}",
        f"- reason：{rule.get('reason')}",
        "",
        "LLM Agent 沙盒：",
        f"- state：{llm.get('state')}",
        f"- selected_tool：{llm.get('selected_tool')}",
        f"- confidence：{llm.get('confidence')}",
        f"- requires_user_confirmation：{llm.get('requires_user_confirmation')}",
        f"- should_execute：{llm.get('should_execute')}（不会执行）",
        f"- reason：{llm.get('reason')}",
        "",
        "对比结果：",
        f"- agreement：{result.get('agreement')}",
        f"- agreement_type：{result.get('agreement_type')}",
        f"- llm_valid：{result.get('llm_valid')}",
        f"- llm_safe：{result.get('llm_safe')}",
        f"- llm_score：{result.get('llm_score')}",
        f"- analysis：{result.get('analysis')}",
        "",
        "LLM 校验问题：",
    ]
    errors = validation.get("errors", []) or []
    warnings = validation.get("warnings", []) or []
    if errors:
        lines.extend(f"- 严重：{item}" for item in errors)
    if warnings:
        lines.extend(f"- 提醒：{item}" for item in warnings)
    if not errors and not warnings:
        lines.append("- 无")
    lines.extend([
        "",
        "注意：LLM 工具选择只用于实验比较，不会执行任何工具。",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_policy_comparison(compare_rule_and_llm_policy()))
