import json
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
AGENT_DECISION_LOG_PATH = BASE_DIR / "data" / "agent_decision_logs.json"


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


def log_agent_decision(record):
    if not isinstance(record, dict):
        record = {}
    safe_record = dict(record)
    safe_record.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    safe_record.setdefault("agent_name", "silent_agent")
    logs = _load_json_list(AGENT_DECISION_LOG_PATH)
    logs.append(safe_record)
    _save_json(AGENT_DECISION_LOG_PATH, logs[-500:])
    return safe_record
