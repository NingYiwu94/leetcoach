import json
from datetime import datetime
from pathlib import Path

from agent.agent_decision_log import log_agent_decision
from agent.agent_observer import collect_learning_observation
from agent.agent_pending_actions import create_pending_action
from agent.agent_policy import ACTION_TOOL_MAP, decide_next_agent_action, map_action_to_tool
from agent.agent_tool_executor import execute_agent_tool
from agent.agent_tool_log import log_agent_tool_call
from agent.agent_tools import get_tool_definition


from app_paths import BASE_DIR
SILENT_AGENT_MEMORY_PATH = BASE_DIR / "data" / "silent_agent_memory.json"


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    return data if isinstance(data, type(default)) else default


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".json.tmp")
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temporary_path.replace(path)


def _save_silent_memory(record):
    memory = _load_json(SILENT_AGENT_MEMORY_PATH, [])
    if not isinstance(memory, list):
        memory = []

    now = record.get("timestamp", "")
    last = memory[-1] if memory and isinstance(memory[-1], dict) else None
    if (
        last
        and last.get("date") == record.get("date")
        and last.get("trigger") == record.get("trigger")
        and last.get("status") == record.get("status")
        and last.get("action") == record.get("action")
        and last.get("fingerprint") == record.get("fingerprint")
        and not record.get("generated")
    ):
        last["last_seen_at"] = now
        last["run_count"] = int(last.get("run_count", 1)) + 1
    else:
        record["run_count"] = 1
        record["last_seen_at"] = now
        memory.append(record)

    _save_json(SILENT_AGENT_MEMORY_PATH, memory[-120:])


def evaluate_silent_agent(trigger="startup"):
    observation = collect_learning_observation()
    decision = decide_next_agent_action(observation)
    action = decision.get("action", "no_action")
    tool_name = map_action_to_tool(action)
    return {
        "status": decision.get("state", "unknown"),
        "trigger": trigger,
        "action": action,
        "tool_name": tool_name,
        "decision": decision.get("decision", ""),
        "reason": decision.get("reason", ""),
        "confidence": decision.get("confidence", 0),
        "generated": False,
        "needs_user_confirmation": bool(decision.get("requires_user_confirmation")),
        "message": "",
        "fingerprint": "",
        "observation": observation,
        "policy": decision,
    }


def _build_tool_input(result, trigger):
    observation = result.get("observation", {})
    if not isinstance(observation, dict):
        observation = {}
    return {
        "trigger": trigger,
        "reason": result.get("reason", ""),
        "decision": result.get("decision", ""),
        "state": (result.get("policy", {}) or {}).get(
            "state",
            result.get("status", ""),
        ),
        "observation": observation,
        "overdue_review_count": observation.get("overdue_review_count"),
    }


def _pending_title(tool_name):
    if tool_name == "apply_plan_draft":
        return "应用下一阶段计划草案"
    return f"确认执行 Agent 工具：{tool_name}"


def _pending_description(tool_name):
    if tool_name == "apply_plan_draft":
        return "Agent 建议应用当前待确认的下一阶段计划草案。该动作会修改正式计划，但会保留原有备份机制。"
    return "Agent 判断该工具需要用户确认后才能执行。"


def _execute_mapped_tool(result, trigger, decision_id):
    action = result.get("action", "no_action")
    tool_name = map_action_to_tool(action)
    if action not in ACTION_TOOL_MAP:
        tool_name = "no_action"
        result["reason"] = f"未知 action：{action}，Agent 已安全映射为 no_action。"

    definition = get_tool_definition(tool_name) or get_tool_definition("no_action") or {}
    tool_input = _build_tool_input(result, trigger)

    if definition.get("requires_confirmation"):
        pending_action = create_pending_action(
            tool_name=tool_name,
            action_type=tool_name,
            title=_pending_title(tool_name),
            description=_pending_description(tool_name),
            reason=result.get("reason", ""),
            risk_level=definition.get("risk_level", "unknown"),
            requires_confirmation=True,
            tool_input=tool_input,
            source_decision_id=decision_id,
            agent_name="silent_agent",
        )
        tool_result = {
            "tool_name": tool_name,
            "success": True,
            "status": "pending_confirmation",
            "message": "该工具需要用户确认，已创建待确认动作。",
            "requires_confirmation": True,
            "pending_action_id": pending_action.get("action_id"),
            "error_type": "",
            "error_message": "",
        }
    else:
        tool_result = execute_agent_tool(tool_name, tool_input=tool_input)

    return tool_name, definition, tool_input, tool_result


def run_silent_agent(trigger="startup"):
    now = datetime.now()
    decision_id = f"silent_agent_{now.strftime('%Y%m%d_%H%M%S_%f')}"
    result = evaluate_silent_agent(trigger)
    tool_name = result.get("tool_name", "no_action")
    tool_definition = get_tool_definition(tool_name) or {}
    tool_input = {}
    tool_result = {}

    try:
        tool_name, tool_definition, tool_input, tool_result = _execute_mapped_tool(
            result,
            trigger,
            decision_id,
        )
        result["tool_name"] = tool_name
        result["tool_result"] = tool_result
        result["message"] = tool_result.get("message") or result.get("reason", "")
        result["needs_user_confirmation"] = bool(
            tool_result.get("requires_confirmation")
            or result.get("needs_user_confirmation")
        )
        result["generated"] = bool(tool_result.get("generated"))
        result["draft_week"] = tool_result.get("draft_week")
        result["generated_by"] = tool_result.get("generated_by")
        result["generated_at"] = tool_result.get("generated_at")
        result["fingerprint"] = tool_result.get(
            "fingerprint",
            result.get("fingerprint", ""),
        )
        if tool_result.get("error_message"):
            result["error_message"] = tool_result.get("error_message")
    except Exception as error:
        tool_result = {
            "tool_name": tool_name,
            "success": False,
            "status": "failed",
            "message": "Agent 工具编排失败，已安全停止。",
            "requires_confirmation": False,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        result.update(
            {
                "status": "error",
                "action": "no_action",
                "tool_name": tool_name,
                "tool_result": tool_result,
                "generated": False,
                "needs_user_confirmation": False,
                "message": tool_result["message"],
                "error_message": str(error),
            }
        )

    memory_record = {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "trigger": trigger,
        "status": result.get("status", ""),
        "action": result.get("action", "none"),
        "tool_name": result.get("tool_name", ""),
        "tool_status": (result.get("tool_result", {}) or {}).get("status", ""),
        "decision": result.get("decision", ""),
        "reason": result.get("reason", ""),
        "confidence": result.get("confidence", 0),
        "generated": bool(result.get("generated")),
        "draft_week": result.get("draft_week"),
        "message": result.get("message", ""),
        "fingerprint": result.get("fingerprint", ""),
        "error_message": result.get("error_message", ""),
    }
    try:
        _save_silent_memory(memory_record)
    except Exception:
        pass

    try:
        log_agent_tool_call({
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "agent_name": "silent_agent",
            "decision_id": decision_id,
            "tool_name": result.get("tool_name", tool_name),
            "tool_input": tool_input,
            "tool_result": result.get("tool_result", tool_result),
            "risk_level": tool_definition.get("risk_level", "unknown"),
            "requires_confirmation": bool(tool_definition.get("requires_confirmation")),
            "executed": (
                (result.get("tool_result", {}) or {}).get("status") == "executed"
            ),
        })
    except Exception:
        pass

    try:
        log_agent_decision({
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "agent_name": "silent_agent",
            "decision_id": decision_id,
            "trigger": trigger,
            "observation": result.get("observation", {}),
            "state": (result.get("policy", {}) or {}).get(
                "state",
                result.get("status", ""),
            ),
            "decision": result.get("decision", ""),
            "action": result.get("action", ""),
            "tool_name": result.get("tool_name", ""),
            "reason": result.get("reason", ""),
            "confidence": result.get("confidence", 0),
            "requires_user_confirmation": bool(result.get("needs_user_confirmation")),
            "result": {
                "success": not bool(result.get("error_message")),
                "generated": bool(result.get("generated")),
                "message": result.get("message", ""),
                "draft_week": result.get("draft_week"),
                "tool_result": result.get("tool_result", {}),
                "error_message": result.get("error_message", ""),
            },
        })
    except Exception:
        pass

    return result
