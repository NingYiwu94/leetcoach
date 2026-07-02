from datetime import datetime

from agent.agent_pending_actions import (
    get_pending_action,
    get_active_pending_actions,
    update_pending_action_status,
)
from agent.agent_tool_executor import execute_agent_tool
from agent.agent_tool_log import log_agent_tool_call
from agent.agent_tools import get_tool_definition


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log_tool(action, result, executed):
    definition = get_tool_definition(action.get("tool_name")) or {}
    log_agent_tool_call({
        "timestamp": _now(),
        "agent_name": action.get("agent_name", "silent_agent"),
        "decision_id": action.get("source_decision_id", ""),
        "tool_name": action.get("tool_name", ""),
        "tool_input": action.get("tool_input", {}),
        "tool_result": result,
        "risk_level": action.get("risk_level") or definition.get("risk_level", "unknown"),
        "requires_confirmation": bool(
            action.get("requires_confirmation")
            or definition.get("requires_confirmation")
        ),
        "executed": bool(executed),
    })


def confirm_pending_action(action_id):
    action = get_pending_action(action_id)
    if not action:
        return {
            "success": False,
            "status": "failed",
            "message": "没有找到该待确认动作。",
        }
    if action.get("status") not in {"pending", "snoozed"}:
        return {
            "success": False,
            "status": "failed",
            "message": f"该动作当前状态为 {action.get('status')}，不能确认执行。",
        }

    user_response = {
        "type": "confirmed",
        "responded_at": _now(),
        "reason": "用户确认执行该 Agent 建议动作。",
    }
    tool_result = execute_agent_tool(
        action.get("tool_name"),
        tool_input=action.get("tool_input", {}),
        confirmed_by_user=True,
    )
    next_status = "executed" if tool_result.get("success") else "failed"
    updated = update_pending_action_status(
        action_id,
        next_status,
        user_response=user_response,
        result=tool_result,
    )
    _log_tool(action, tool_result, executed=(next_status == "executed"))
    return {
        "success": bool(tool_result.get("success")),
        "status": next_status,
        "message": tool_result.get("message", ""),
        "action": updated,
        "tool_result": tool_result,
    }


def reject_pending_action(action_id, reason=None):
    action = get_pending_action(action_id)
    if not action:
        return {
            "success": False,
            "status": "failed",
            "message": "没有找到该待确认动作。",
        }
    user_response = {
        "type": "rejected",
        "responded_at": _now(),
        "reason": reason or "用户拒绝该 Agent 建议。",
    }
    updated = update_pending_action_status(
        action_id,
        "rejected",
        user_response=user_response,
    )
    return {
        "success": True,
        "status": "rejected",
        "message": "已拒绝该待确认动作。",
        "action": updated,
    }


def snooze_pending_action(action_id, reason=None):
    action = get_pending_action(action_id)
    if not action:
        return {
            "success": False,
            "status": "failed",
            "message": "没有找到该待确认动作。",
        }
    user_response = {
        "type": "snoozed",
        "responded_at": _now(),
        "reason": reason or "用户选择稍后处理。",
    }
    updated = update_pending_action_status(
        action_id,
        "snoozed",
        user_response=user_response,
    )
    return {
        "success": True,
        "status": "snoozed",
        "message": "已暂缓该待确认动作。",
        "action": updated,
    }


def get_first_active_pending_action():
    actions = get_active_pending_actions()
    return actions[0] if actions else None


if __name__ == "__main__":
    action = get_first_active_pending_action()
    if not action:
        print("当前没有待确认动作。")
    else:
        print(f"第一条待确认动作：{action.get('action_id')} - {action.get('title')}")
