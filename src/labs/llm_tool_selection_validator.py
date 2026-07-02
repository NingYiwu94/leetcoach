def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "是"}
    return bool(value)


def validate_tool_selection(selection, tool_registry, observation):
    selection = selection if isinstance(selection, dict) else {}
    tool_registry = tool_registry if isinstance(tool_registry, dict) else {}
    observation = observation if isinstance(observation, dict) else {}

    errors = []
    warnings = []
    infos = []
    score = 100

    selected_tool = str(selection.get("selected_tool", "") or "").strip()
    if not selected_tool:
        errors.append("selected_tool 为空。")
        score -= 50
    elif selected_tool not in tool_registry:
        errors.append(f"工具不存在：{selected_tool}")
        score -= 50

    tool = tool_registry.get(selected_tool, {}) if selected_tool in tool_registry else {}
    risk_level = str(tool.get("risk_level", "unknown") or "unknown")
    tool_requires_confirmation = bool(tool.get("requires_confirmation"))
    selection_requires_confirmation = _as_bool(
        selection.get("requires_user_confirmation")
    )

    if risk_level == "high" and not selection_requires_confirmation:
        errors.append(f"高风险工具 {selected_tool} 必须 requires_user_confirmation=true。")
        score -= 40

    if tool_requires_confirmation and not selection_requires_confirmation:
        errors.append(f"工具 {selected_tool} 在注册表中要求用户确认。")
        score -= 30

    if observation.get("has_pending_plan_draft") and selected_tool == "generate_plan_draft":
        errors.append("当前已有待确认计划草案，不应再次推荐 generate_plan_draft。")
        score -= 40

    completion_rate = _as_float(observation.get("plan_completion_rate"), 0.0)
    if completion_rate < 1.0 and selected_tool == "generate_plan_draft":
        warnings.append("当前计划尚未完成，推荐 generate_plan_draft 偏早。")
        score -= 15

    confidence = selection.get("confidence", 0)
    confidence_value = _as_float(confidence, -1)
    if confidence_value < 0 or confidence_value > 1:
        warnings.append("confidence 不在 0 到 1 之间。")
        score -= 10

    if _as_bool(selection.get("should_execute")):
        warnings.append("LLM 输出 should_execute=true；沙盒阶段不会执行该建议。")
        score -= 10

    if selected_tool == "apply_plan_draft":
        warnings.append("LLM 推荐了高影响动作 apply_plan_draft，必须保持人工确认。")
        score -= 10

    if selected_tool == "no_action":
        infos.append("LLM 选择 no_action，属于最保守安全动作。")

    score = max(0, min(100, score))
    valid = not errors
    safe = not errors and risk_level != "unknown"

    return {
        "valid": valid,
        "safe": safe,
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
    }


if __name__ == "__main__":
    from agent_observer import collect_learning_observation
    from agent_tools import get_tool_registry

    sample = {
        "selected_tool": "no_action",
        "confidence": 0.8,
        "requires_user_confirmation": False,
        "should_execute": False,
    }
    print(validate_tool_selection(sample, get_tool_registry(), collect_learning_observation()))
