import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path


from app_paths import BASE_DIR
PLAN_REVIEW_PATH = BASE_DIR / "config" / "plan_review_state.json"


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


def get_draft_identity(draft):
    if not isinstance(draft, dict):
        return ""
    identity_data = {
        "week": draft.get("week"),
        "generated_at": draft.get("generated_at"),
        "context_fingerprint": draft.get("context_fingerprint"),
        "start_date": draft.get("start_date"),
        "title": draft.get("title")
    }
    serialized = json.dumps(
        identity_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_plan_review_state():
    state = load_json(PLAN_REVIEW_PATH, {})
    return state if isinstance(state, dict) else {}


def get_draft_review_status(draft, today=None):
    today = today or date.today()
    identity = get_draft_identity(draft)
    state = load_plan_review_state()

    if not identity or state.get("draft_identity") != identity:
        return {
            "status": "pending",
            "snoozed": False,
            "snoozed_until": "",
            "draft_identity": identity
        }

    snoozed_until = str(state.get("snoozed_until", "")).strip()
    try:
        snooze_date = datetime.strptime(
            snoozed_until, "%Y-%m-%d"
        ).date()
    except ValueError:
        snooze_date = None

    snoozed = snooze_date is not None and today < snooze_date
    return {
        "status": "snoozed" if snoozed else "pending",
        "snoozed": snoozed,
        "snoozed_until": snoozed_until,
        "draft_identity": identity
    }


def snooze_plan_draft(draft, days=1):
    identity = get_draft_identity(draft)
    if not identity:
        return {
            "success": False,
            "message": "计划草案不存在，无法暂缓提醒。"
        }

    try:
        days = max(1, int(days))
    except (TypeError, ValueError):
        days = 1

    snoozed_until = date.today() + timedelta(days=days)
    state = {
        "draft_identity": identity,
        "draft_week": draft.get("week", ""),
        "snoozed_until": str(snoozed_until),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_json(PLAN_REVIEW_PATH, state)
    return {
        "success": True,
        "message": f"已暂缓提醒，将在 {snoozed_until} 再次提醒。",
        **state
    }


def clear_plan_review_state():
    try:
        PLAN_REVIEW_PATH.unlink(missing_ok=True)
        return True
    except OSError:
        return False
