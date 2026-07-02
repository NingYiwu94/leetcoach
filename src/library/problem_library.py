import json
from pathlib import Path


from app_paths import BASE_DIR
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
RECORDS_PATH = BASE_DIR / "data" / "records.json"
AI_SOLUTION_NOTES_PATH = BASE_DIR / "data" / "ai_solution_notes.json"
WEEK_PLAN_PATH = BASE_DIR / "config" / "week_plan.json"
TOPIC_CATALOG_PATH = BASE_DIR / "config" / "topic_catalog.json"

COMPLETED_STATUSES = {"AC", "看提示后AC"}
DIFFICULTY_ORDER = ["Easy", "Medium", "Hard", "Unknown"]


def load_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def clean_problem_id(problem_id):
    value = str(problem_id or "")
    for prefix in ("题号：", "题号:", "题号"):
        value = value.replace(prefix, "")
    return value.strip()


def normalize_status(status):
    return str(status or "").replace(" ", "").strip()


def normalize_difficulty(difficulty):
    value = str(difficulty or "").strip()
    if value in {"Easy", "简单"}:
        return "Easy"
    if value in {"Medium", "中等"}:
        return "Medium"
    if value in {"Hard", "困难"}:
        return "Hard"
    return "Unknown"


def normalize_source(source):
    value = str(source or "").strip()
    if value == "leetcode_auto_sync":
        return "leetcode_auto_sync"
    if value in {"leetcode_import", "import"}:
        return "import"
    if value:
        return value
    return "manual"


def normalize_topic_catalog(topic_catalog=None):
    catalog = (
        topic_catalog
        if isinstance(topic_catalog, dict)
        else load_json(TOPIC_CATALOG_PATH, {})
    )
    if not isinstance(catalog, dict):
        catalog = {}

    normalized = {}
    for topic, config in catalog.items():
        topic_name = str(topic or "").strip()
        if not topic_name:
            continue

        if not isinstance(config, dict):
            config = {"total": config}

        try:
            total = int(config.get("total", 0) or 0)
        except (TypeError, ValueError):
            total = 0

        try:
            order = int(config.get("order", 9999) or 9999)
        except (TypeError, ValueError):
            order = 9999

        difficulty_total = {}
        raw_difficulty_total = config.get("difficulty_total", {})
        if isinstance(raw_difficulty_total, dict):
            for difficulty, count in raw_difficulty_total.items():
                normalized_difficulty = normalize_difficulty(difficulty)
                try:
                    difficulty_total[normalized_difficulty] = int(count)
                except (TypeError, ValueError):
                    pass

        normalized[topic_name] = {
            "topic": topic_name,
            "total": total,
            "order": order,
            "description": str(config.get("description", "")).strip(),
            "difficulty_total": difficulty_total
        }

    return normalized


def get_completed_records(records):
    completed_by_problem = {}
    if not isinstance(records, list):
        return completed_by_problem

    for record in records:
        if not isinstance(record, dict):
            continue
        problem_id = clean_problem_id(record.get("problem_id"))
        if not problem_id:
            continue
        if normalize_status(record.get("status")) not in COMPLETED_STATUSES:
            continue

        timestamp = str(
            record.get("submit_time")
            or " ".join(
                part for part in [
                    str(record.get("date", "")).strip(),
                    str(record.get("time", "")).strip()
                ] if part
            )
        ).strip()
        existing = completed_by_problem.get(problem_id)
        if existing is None or timestamp >= str(existing.get("completed_at", "")):
            completed_by_problem[problem_id] = {
                "problem_id": problem_id,
                "completed_at": timestamp or str(record.get("date", "")),
                "source": normalize_source(record.get("source")),
                "raw_record": record
            }

    return completed_by_problem


def get_ai_solution_problem_ids():
    notes = load_json(AI_SOLUTION_NOTES_PATH, [])
    if not isinstance(notes, list):
        return set()
    return {
        clean_problem_id(item.get("problem_id"))
        for item in notes
        if isinstance(item, dict) and clean_problem_id(item.get("problem_id"))
    }


def _empty_difficulty_stats():
    return {
        difficulty: {"completed": 0, "local_total": 0, "catalog_total": None}
        for difficulty in DIFFICULTY_ORDER
    }


def _new_topic_data(topic_name, catalog_item=None):
    catalog_item = catalog_item if isinstance(catalog_item, dict) else {}
    difficulty_stats = _empty_difficulty_stats()
    for difficulty, count in catalog_item.get("difficulty_total", {}).items():
        if difficulty in difficulty_stats:
            difficulty_stats[difficulty]["catalog_total"] = count

    return {
        "topic": topic_name,
        "completed": 0,
        "total": int(catalog_item.get("total", 0) or 0),
        "order": int(catalog_item.get("order", 9999) or 9999),
        "description": catalog_item.get("description", ""),
        "difficulty_stats": difficulty_stats,
        "problems": [],
        "completed_problems": [],
        "unfinished_plan_problems": [],
        "source_counts": {}
    }


def _as_list(value):
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def get_problem_topics(problem, catalog):
    if not isinstance(problem, dict):
        return ["未分类"]

    catalog_topics = set(catalog.keys())
    topics = []

    primary_topic = str(problem.get("topic", "")).strip()
    if primary_topic:
        topics.append(primary_topic)

    pattern = str(problem.get("pattern", "")).strip()
    if pattern:
        topics.append(pattern)

    for field in ("tags", "topics"):
        for item in _as_list(problem.get(field)):
            topic = str(item or "").strip()
            if topic and topic in catalog_topics:
                topics.append(topic)

    unique_topics = []
    for topic in topics:
        if topic and topic not in unique_topics:
            unique_topics.append(topic)

    return unique_topics or ["未分类"]


def _collect_week_plan_problem_ids(plan):
    problem_ids = []
    if not isinstance(plan, dict):
        return problem_ids
    days = plan.get("days", {})
    if not isinstance(days, dict):
        return problem_ids

    for day in days.values():
        if not isinstance(day, dict):
            continue
        for problem_id in _as_list(day.get("problems")):
            clean_id = clean_problem_id(problem_id)
            if clean_id and clean_id not in problem_ids:
                problem_ids.append(clean_id)
    return problem_ids


def get_problem_library_data(
    problem_bank=None,
    records=None,
    topic_catalog=None,
    week_plan=None
):
    problem_bank = (
        problem_bank
        if isinstance(problem_bank, dict)
        else load_json(PROBLEM_BANK_PATH, {})
    )
    records = records if isinstance(records, list) else load_json(
        RECORDS_PATH,
        []
    )
    week_plan = (
        week_plan
        if isinstance(week_plan, dict)
        else load_json(WEEK_PLAN_PATH, {})
    )

    if not isinstance(problem_bank, dict):
        problem_bank = {}

    catalog = normalize_topic_catalog(topic_catalog)
    topics = {
        topic_name: _new_topic_data(topic_name, item)
        for topic_name, item in catalog.items()
    }

    completed_records = get_completed_records(records)
    ai_solution_ids = get_ai_solution_problem_ids()
    planned_problem_ids = _collect_week_plan_problem_ids(week_plan)
    completed_known_ids = set()

    for problem_id, problem in problem_bank.items():
        problem_id = clean_problem_id(problem_id)
        if not problem_id or not isinstance(problem, dict):
            continue

        completed_record = completed_records.get(problem_id)
        is_completed = completed_record is not None
        if is_completed:
            completed_known_ids.add(problem_id)

        difficulty = normalize_difficulty(problem.get("difficulty"))
        problem_topics = get_problem_topics(problem, catalog)

        problem_item = {
            "problem_id": problem_id,
            "title": problem.get("title", "未知题目"),
            "difficulty": difficulty,
            "topics": problem_topics,
            "completed": is_completed,
            "skill": problem.get("skill", ""),
            "template": problem.get("template", ""),
            "completed_at": (
                completed_record.get("completed_at", "")
                if completed_record
                else ""
            ),
            "source": (
                completed_record.get("source", "")
                if completed_record
                else ""
            ),
            "has_ai_solution": problem_id in ai_solution_ids
        }

        for topic_name in problem_topics:
            topic_data = topics.setdefault(
                topic_name,
                _new_topic_data(topic_name)
            )
            topic_data["difficulty_stats"][difficulty]["local_total"] += 1
            topic_data["problems"].append(problem_item)
            if is_completed:
                topic_data["completed"] += 1
                topic_data["difficulty_stats"][difficulty]["completed"] += 1
                topic_data["completed_problems"].append(problem_item)
                source = problem_item["source"] or "manual"
                topic_data["source_counts"][source] = (
                    topic_data["source_counts"].get(source, 0) + 1
                )

            if problem_id in planned_problem_ids and not is_completed:
                topic_data["unfinished_plan_problems"].append(problem_item)

    unknown_completed_count = 0
    for problem_id, completed_record in completed_records.items():
        if problem_id in completed_known_ids:
            continue
        unknown_completed_count += 1
        raw_record = completed_record.get("raw_record", {})
        topic_data = topics.setdefault("未分类", _new_topic_data("未分类"))
        problem_item = {
            "problem_id": problem_id,
            "title": raw_record.get("title", "未知题目"),
            "difficulty": "Unknown",
            "topics": ["未分类"],
            "completed": True,
            "skill": "",
            "template": "",
            "completed_at": completed_record.get("completed_at", ""),
            "source": completed_record.get("source", ""),
            "has_ai_solution": problem_id in ai_solution_ids
        }
        topic_data["completed"] += 1
        topic_data["difficulty_stats"]["Unknown"]["completed"] += 1
        topic_data["completed_problems"].append(problem_item)
        topic_data["problems"].append(problem_item)
        source = problem_item["source"] or "manual"
        topic_data["source_counts"][source] = (
            topic_data["source_counts"].get(source, 0) + 1
        )

    catalog_total_sum = sum(item["total"] for item in catalog.values())
    topic_list = sorted(
        topics.values(),
        key=lambda item: (
            item["topic"] == "未分类",
            item["order"],
            item["topic"]
        )
    )

    return {
        "topic_total_sum": catalog_total_sum,
        "total_problem_count": catalog_total_sum,
        "completed_problem_count": len(completed_records),
        "known_completed_problem_count": len(completed_known_ids),
        "unknown_completed_problem_count": unknown_completed_count,
        "topic_count": len(catalog),
        "topics": topic_list,
        "catalog_source": str(TOPIC_CATALOG_PATH)
    }


def get_topic_detail(topic_name, library_data=None):
    data = (
        library_data
        if isinstance(library_data, dict)
        else get_problem_library_data()
    )
    for topic in data.get("topics", []):
        if topic.get("topic") == topic_name:
            return topic
    topics = data.get("topics", [])
    return topics[0] if topics else None
