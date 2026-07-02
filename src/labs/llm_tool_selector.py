import json
import time
from datetime import datetime

from agent.agent_feedback_memory import (
    format_user_learning_profile_for_prompt,
    load_user_learning_profile,
)
from agent.agent_observer import collect_learning_observation
from agent.agent_tools import get_tool_registry
from llm.llm_logger import log_llm_call
from labs.llm_tool_selection_validator import validate_tool_selection
from llm.prompt_loader import load_prompt_template, render_prompt


PROMPT_VERSION = "llm_tool_selector_v1"


def _json_text(data, max_chars=5000):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]"
    return text


def _fallback_selection(reason, error_type="", error_message=""):
    return {
        "state": "fallback",
        "selected_tool": "no_action",
        "tool_input": {"reason": reason},
        "reason": reason,
        "confidence": 0.0,
        "requires_user_confirmation": False,
        "risk_assessment": "low",
        "should_execute": False,
        "fallback_used": True,
        "error_type": error_type,
        "error_message": error_message,
    }


def _parse_json_response(raw_text):
    if not isinstance(raw_text, str):
        return None
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _tool_registry_for_prompt(tool_registry):
    items = []
    for name, tool in sorted(tool_registry.items()):
        if not isinstance(tool, dict):
            continue
        items.append({
            "name": name,
            "description": tool.get("description", ""),
            "risk_level": tool.get("risk_level", "unknown"),
            "requires_confirmation": bool(tool.get("requires_confirmation")),
            "input_schema": tool.get("input_schema", {}),
        })
    return items


def _normalize_selection(selection):
    selection = selection if isinstance(selection, dict) else {}
    return {
        "state": str(selection.get("state", "") or "unknown"),
        "selected_tool": str(selection.get("selected_tool", "") or "no_action"),
        "tool_input": selection.get("tool_input") if isinstance(selection.get("tool_input"), dict) else {},
        "reason": str(selection.get("reason", "") or ""),
        "confidence": selection.get("confidence", 0),
        "requires_user_confirmation": bool(selection.get("requires_user_confirmation", False)),
        "risk_assessment": str(selection.get("risk_assessment", "") or ""),
        "should_execute": bool(selection.get("should_execute", False)),
        "fallback_used": bool(selection.get("fallback_used", False)),
        "error_type": str(selection.get("error_type", "") or ""),
        "error_message": str(selection.get("error_message", "") or ""),
    }


def select_tool_with_llm(observation=None, profile=None):
    observation = observation if isinstance(observation, dict) else collect_learning_observation()
    profile = profile if isinstance(profile, dict) else load_user_learning_profile()
    tool_registry = get_tool_registry()
    output_schema = {
        "state": "string",
        "selected_tool": "must be one registered tool name",
        "tool_input": "object",
        "reason": "string",
        "confidence": "number from 0 to 1",
        "requires_user_confirmation": "boolean",
        "risk_assessment": "low | medium | high",
        "should_execute": "boolean, must be false in this sandbox",
    }

    prompt_template = load_prompt_template(PROMPT_VERSION)
    user_prompt = render_prompt(
        prompt_template,
        {
            "observation": _json_text(observation, max_chars=3000),
            "tool_registry": _json_text(
                _tool_registry_for_prompt(tool_registry),
                max_chars=5000,
            ),
            "user_profile": format_user_learning_profile_for_prompt(profile),
            "output_schema": _json_text(output_schema, max_chars=2000),
        },
    )
    system_prompt = (
        "你是 LeetCoach 的 LLM Tool Selection Sandbox。"
        "你只能选择工具，不能执行工具。"
        "必须只返回 JSON。"
    )

    start = time.time()
    raw_text = ""
    parsed_success = False
    fallback_used = False
    model_name = ""
    error_type = ""
    error_message = ""

    try:
        from llm_client import LLMClient

        client = LLMClient(timeout=30, model_env_key="LLM_MODEL_FAST")
        model_name = client.model
        raw_text = client.chat(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=900,
            enable_thinking=False,
        )
        parsed = _parse_json_response(raw_text)
        if parsed is None:
            selection = _fallback_selection(
                "LLM 工具选择失败，使用 no_action 兜底",
                error_type="JSONParseError",
                error_message="模型没有返回合法 JSON。",
            )
            fallback_used = True
        else:
            parsed_success = True
            selection = _normalize_selection(parsed)
    except Exception as error:
        error_type = type(error).__name__
        error_message = str(error)
        selection = _fallback_selection(
            "LLM 工具选择失败，使用 no_action 兜底",
            error_type=error_type,
            error_message=error_message,
        )
        fallback_used = True

    validation = validate_tool_selection(selection, tool_registry, observation)
    latency = round(time.time() - start, 4)

    selection.update({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prompt_version": PROMPT_VERSION,
        "model": model_name,
        "parsed_success": parsed_success,
        "schema_valid": bool(validation.get("valid")),
        "safe": bool(validation.get("safe")),
        "score": validation.get("score", 0),
        "validation": validation,
        "fallback_used": bool(selection.get("fallback_used") or fallback_used),
        "latency_seconds": latency,
    })

    log_llm_call({
        "task": "llm_tool_selection",
        "prompt_name": "llm_tool_selector",
        "prompt_version": PROMPT_VERSION,
        "model": model_name,
        "input_summary": {
            "current_week": observation.get("current_week"),
            "current_day": observation.get("current_day"),
            "plan_completion_rate": observation.get("plan_completion_rate"),
            "has_pending_plan_draft": observation.get("has_pending_plan_draft"),
            "selected_tool": selection.get("selected_tool"),
            "safe": validation.get("safe"),
            "score": validation.get("score"),
        },
        "prompt_preview": user_prompt,
        "raw_output": raw_text,
        "parsed_success": parsed_success,
        "schema_valid": bool(validation.get("valid")),
        "eval_score": validation.get("score", 0),
        "fallback_used": bool(selection.get("fallback_used")),
        "error_type": selection.get("error_type") or error_type,
        "error_message": selection.get("error_message") or error_message,
        "latency_seconds": latency,
    })
    return selection


def format_llm_tool_selection(selection):
    if not isinstance(selection, dict):
        return "暂无 LLM 工具选择结果。"
    validation = selection.get("validation", {})
    if not isinstance(validation, dict):
        validation = {}
    lines = [
        "===== LLM 工具选择沙盒 =====",
        "",
        f"时间：{selection.get('timestamp', '')}",
        f"模型：{selection.get('model', '') or '未知'}",
        f"选择工具：{selection.get('selected_tool', '')}",
        f"状态：{selection.get('state', '')}",
        f"置信度：{selection.get('confidence', 0)}",
        f"风险判断：{selection.get('risk_assessment', '')}",
        f"需要用户确认：{'是' if selection.get('requires_user_confirmation') else '否'}",
        f"should_execute：{selection.get('should_execute', False)}（沙盒不会执行）",
        f"安全：{'是' if selection.get('safe') else '否'}",
        f"评分：{selection.get('score', 0)}",
        f"fallback：{'是' if selection.get('fallback_used') else '否'}",
        "",
        "理由：",
        selection.get("reason", "") or "无",
        "",
        "严重问题：",
    ]
    errors = validation.get("errors", []) or []
    warnings = validation.get("warnings", []) or []
    infos = validation.get("infos", []) or []
    lines.extend([f"- {item}" for item in errors] if errors else ["- 无"])
    lines.append("")
    lines.append("质量提醒：")
    lines.extend([f"- {item}" for item in warnings] if warnings else ["- 无"])
    lines.append("")
    lines.append("说明：")
    lines.extend([f"- {item}" for item in infos] if infos else ["- 无"])
    if selection.get("error_message"):
        lines.extend(["", f"错误：{selection.get('error_message')}"])
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_llm_tool_selection(select_tool_with_llm()))
