import json
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
AGENT_TOOL_CALL_LOG_PATH = BASE_DIR / "data" / "agent_tool_call_logs.json"


def _load_json_list(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_name(
            f"{path.stem}.broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        )
        try:
            path.replace(backup)
        except OSError:
            pass
        return []
    except OSError:
        return []
    return data if isinstance(data, list) else []


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _redact_sensitive(value):
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if "key" in lowered or "token" in lowered or "secret" in lowered:
                clean[key] = "[REDACTED]"
            else:
                clean[key] = _redact_sensitive(item)
        return clean
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def log_agent_tool_call(record):
    if not isinstance(record, dict):
        record = {}
    safe_record = _redact_sensitive(dict(record))
    safe_record.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    safe_record.setdefault("agent_name", "silent_agent")

    logs = _load_json_list(AGENT_TOOL_CALL_LOG_PATH)
    logs.append(safe_record)
    _save_json(AGENT_TOOL_CALL_LOG_PATH, logs[-500:])
    return safe_record
