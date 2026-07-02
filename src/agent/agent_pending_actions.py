import json
import re
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
PENDING_ACTIONS_PATH = BASE_DIR / "data" / "agent_pending_actions.json"
ACTIVE_STATUSES = {"pending", "snoozed"}
VALID_STATUSES = {
    "pending",
    "confirmed",
    "rejected",
    "snoozed",
    "executed",
    "failed",
    "expired",
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_id_part(value):
    text = str(value or "action").strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    return text.strip("_") or "action"


def _backup_broken_file(path):
    backup = path.with_name(
        f"{path.stem}.broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    )
    try:
        path.replace(backup)
    except OSError:
        pass


def load_pending_actions():
    if not PENDING_ACTIONS_PATH.exists():
        return []
    try:
        data = json.loads(PENDING_ACTIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _backup_broken_file(PENDING_ACTIONS_PATH)
        return []
    except OSError:
        return []
    return data if isinstance(data, list) else []


def save_pending_actions(actions):
    safe_actions = actions if isinstance(actions, list) else []
    PENDING_ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_ACTIONS_PATH.write_text(
        json.dumps(safe_actions[-500:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return safe_actions[-500:]


def find_existing_pending_action(tool_name, action_type):
    tool_name = str(tool_name or "")
    action_type = str(action_type or tool_name)
    for action in reversed(load_pending_actions()):
        if not isinstance(action, dict):
            continue
        if action.get("status") not in ACTIVE_STATUSES:
            continue
        if (
            str(action.get("tool_name", "")) == tool_name
            and str(action.get("action_type", "")) == action_type
        ):
            return action
    return None


def create_pending_action(
    tool_name,
    action_type=None,
    title=None,
    description=None,
    reason=None,
    risk_level="low",
    requires_confirmation=True,
    tool_input=None,
    source_decision_id=None,
    agent_name="silent_agent",
):
    action_type = action_type or tool_name
    existing = find_existing_pending_action(tool_name, action_type)
    if existing:
        return existing

    created_at = _now()
    action_id = (
        f"pending_{_safe_id_part(action_type)}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    )
    action = {
        "action_id": action_id,
        "created_at": created_at,
        "updated_at": created_at,
        "agent_name": agent_name,
        "tool_name": tool_name,
        "action_type": action_type,
        "title": title or f"待确认动作：{action_type}",
        "description": description or "",
        "reason": reason or "",
        "risk_level": risk_level,
        "requires_confirmation": bool(requires_confirmation),
        "status": "pending",
        "tool_input": tool_input if isinstance(tool_input, dict) else {},
        "source_decision_id": source_decision_id or "",
        "user_response": None,
        "result": None,
    }
    actions = load_pending_actions()
    actions.append(action)
    save_pending_actions(actions)
    return action


def get_active_pending_actions():
    return [
        action for action in load_pending_actions()
        if isinstance(action, dict) and action.get("status") in ACTIVE_STATUSES
    ]


def get_pending_action(action_id):
    for action in load_pending_actions():
        if isinstance(action, dict) and action.get("action_id") == action_id:
            return action
    return None


def update_pending_action_status(
    action_id,
    status,
    user_response=None,
    result=None,
):
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid pending action status: {status}")

    actions = load_pending_actions()
    updated = None
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action_id") != action_id:
            continue
        action["status"] = status
        action["updated_at"] = _now()
        if user_response is not None:
            action["user_response"] = user_response
        if result is not None:
            action["result"] = result
        updated = action
        break
    if updated is None:
        return None
    save_pending_actions(actions)
    return updated


def format_active_pending_actions(actions=None):
    actions = actions if isinstance(actions, list) else get_active_pending_actions()
    lines = ["===== Agent 待确认动作 =====", ""]
    if not actions:
        lines.append("当前没有待确认动作。")
        return "\n".join(lines)

    for index, action in enumerate(actions, start=1):
        lines.extend([
            f"{index}. {action.get('title', '')}",
            f"   action_id：{action.get('action_id', '')}",
            f"   工具：{action.get('tool_name', '')}",
            f"   风险等级：{action.get('risk_level', '')}",
            f"   状态：{action.get('status', '')}",
            f"   原因：{action.get('reason', '')}",
            "",
        ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    print(format_active_pending_actions())
