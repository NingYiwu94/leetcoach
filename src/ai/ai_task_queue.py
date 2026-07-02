import json
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
AI_TASK_LOG_PATH = BASE_DIR / "data" / "ai_task_logs.json"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".json.tmp")
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temporary_path.replace(path)


def log_ai_task(task_type, problem_id="", language="", status="running", message=""):
    logs = load_json(AI_TASK_LOG_PATH, [])
    if not isinstance(logs, list):
        logs = []

    record = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_type": str(task_type or "ai_task"),
        "problem_id": str(problem_id or ""),
        "language": str(language or ""),
        "status": str(status or "running"),
        "message": str(message or ""),
    }
    logs.append(record)
    save_json(AI_TASK_LOG_PATH, logs[-100:])
    return record


def get_recent_ai_tasks(limit=5):
    logs = load_json(AI_TASK_LOG_PATH, [])
    if not isinstance(logs, list):
        return []
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 5
    return list(reversed(logs[-limit:]))
