import json
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
NOTES_PATH = BASE_DIR / "data" / "problem_notes.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"


MASTERY_LABELS = {
    "unknown": "未评估",
    "understood": "看懂",
    "assisted": "看提示写出",
    "independent": "独立写出",
    "not_mastered": "仍未掌握",
}


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


def clean_problem_id(problem_id):
    value = str(problem_id or "")
    for prefix in ("题号：", "题号:", "题号"):
        value = value.replace(prefix, "")
    return value.strip()


def load_problem_notes():
    notes = load_json(NOTES_PATH, {})
    return notes if isinstance(notes, dict) else {}


def get_problem_note(problem_id):
    problem_id = clean_problem_id(problem_id)
    notes = load_problem_notes()
    note = notes.get(problem_id, {})
    if not isinstance(note, dict):
        note = {}
    return {
        "problem_id": problem_id,
        "note": str(note.get("note", "")),
        "mastery": str(note.get("mastery", "unknown") or "unknown"),
        "updated_at": str(note.get("updated_at", "")),
    }


def save_problem_note(problem_id, note_text, mastery):
    problem_id = clean_problem_id(problem_id)
    if not problem_id:
        raise ValueError("缺少题号，无法保存笔记。")

    mastery = str(mastery or "unknown").strip()
    if mastery not in MASTERY_LABELS:
        mastery = "unknown"

    notes = load_problem_notes()
    notes[problem_id] = {
        "problem_id": problem_id,
        "note": str(note_text or "").strip(),
        "mastery": mastery,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(NOTES_PATH, notes)
    return notes[problem_id]


def get_problem_review_summary(problem_id):
    problem_id = clean_problem_id(problem_id)
    reviews = load_json(REVIEWS_PATH, [])
    if not isinstance(reviews, list):
        reviews = []

    matched = [
        item for item in reviews
        if (
            isinstance(item, dict)
            and clean_problem_id(item.get("problem_id")) == problem_id
        )
    ]
    if not matched:
        return {
            "total": 0,
            "pending": 0,
            "latest_text": "暂无复习记录",
        }

    pending = [item for item in matched if not item.get("done")]
    latest = sorted(
        matched,
        key=lambda item: str(
            item.get("completed_at")
            or item.get("updated_at")
            or item.get("next_review_date")
            or ""
        ),
        reverse=True,
    )[0]

    if pending:
        next_date = sorted(
            str(item.get("next_review_date", "")) for item in pending
        )[0]
        latest_text = f"待复习 {len(pending)} 次，最近安排：{next_date}"
    else:
        latest_text = (
            "已完成最近复习"
            if latest.get("done")
            else "暂无待复习"
        )

    mastery_label = latest.get("mastery_label", "")
    if mastery_label:
        latest_text += f" · 最近结果：{mastery_label}"

    return {
        "total": len(matched),
        "pending": len(pending),
        "latest_text": latest_text,
    }


def get_problem_review_summary(problem_id):
    problem_id = clean_problem_id(problem_id)
    reviews = load_json(REVIEWS_PATH, [])
    if not isinstance(reviews, list):
        reviews = []

    matched = [
        item for item in reviews
        if (
            isinstance(item, dict)
            and clean_problem_id(item.get("problem_id")) == problem_id
        )
    ]
    if not matched:
        return {
            "total": 0,
            "pending": 0,
            "latest_text": "暂无复习记录",
            "pending_reviews": [],
            "latest_reason": "",
            "latest_next_review_date": "",
        }

    pending = [item for item in matched if not item.get("done")]
    latest = sorted(
        matched,
        key=lambda item: str(
            item.get("completed_at")
            or item.get("updated_at")
            or item.get("next_review_date")
            or ""
        ),
        reverse=True,
    )[0]

    if pending:
        pending_sorted = sorted(
            pending,
            key=lambda item: str(item.get("next_review_date", "")),
        )
        next_date = str(pending_sorted[0].get("next_review_date", ""))
        latest_text = f"待复习 {len(pending)} 次，最近安排：{next_date}"
    else:
        pending_sorted = []
        latest_text = "已完成最近复习" if latest.get("done") else "暂无待复习"

    mastery_label = str(latest.get("mastery_label", "")).strip()
    if mastery_label:
        latest_text += f" · 最近结果：{mastery_label}"

    return {
        "total": len(matched),
        "pending": len(pending),
        "latest_text": latest_text,
        "pending_reviews": [
            {
                "next_review_date": str(item.get("next_review_date", "")),
                "reason": str(item.get("reason", "")),
                "review_round": item.get("review_round", 1),
                "priority_level": item.get("priority_level", ""),
                "priority_score": item.get("priority_score", 0),
                "source": str(item.get("source", "")),
            }
            for item in pending_sorted
            if isinstance(item, dict)
        ],
        "latest_reason": str(latest.get("reason", "")),
        "latest_next_review_date": str(latest.get("next_review_date", "")),
    }
