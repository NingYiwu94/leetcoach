import json
from datetime import date, datetime
from pathlib import Path


from app_paths import BASE_DIR
AGENT_MEMORY_PATH = BASE_DIR / "data" / "agent_memory.json"


def load_agent_memory():
    if not AGENT_MEMORY_PATH.exists():
        return []

    try:
        with open(AGENT_MEMORY_PATH, "r", encoding="utf-8") as f:
            memory = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    return memory if isinstance(memory, list) else []


def _save_agent_memory(memory):
    AGENT_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = AGENT_MEMORY_PATH.with_suffix(".json.tmp")
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)
    temporary_path.replace(AGENT_MEMORY_PATH)


def normalize_agent_memory(memory):
    if not isinstance(memory, list):
        return []

    daily_snapshots = {}
    undated_items = []
    for item in memory:
        if not isinstance(item, dict):
            continue

        memory_date = str(item.get("date", "")).strip()
        if not memory_date:
            undated_items.append(dict(item))
            continue

        snapshot = dict(item)
        try:
            run_count = max(1, int(snapshot.get("run_count", 1)))
        except (TypeError, ValueError):
            run_count = 1

        existing = daily_snapshots.get(memory_date)
        if existing is not None:
            try:
                existing_count = max(
                    1, int(existing.get("run_count", 1))
                )
            except (TypeError, ValueError):
                existing_count = 1
            run_count += existing_count
            snapshot.setdefault(
                "first_seen_at",
                existing.get("first_seen_at")
                or f"{memory_date} 00:00:00"
            )

        snapshot["run_count"] = run_count
        snapshot.setdefault(
            "first_seen_at",
            f"{memory_date} 00:00:00"
        )
        snapshot.setdefault(
            "updated_at",
            snapshot.get("first_seen_at")
        )
        daily_snapshots[memory_date] = snapshot

    normalized = [
        daily_snapshots[memory_date]
        for memory_date in sorted(daily_snapshots)
    ]
    normalized.extend(undated_items)
    return normalized


def reconcile_agent_memory():
    memory = load_agent_memory()
    normalized = normalize_agent_memory(memory)
    if normalized == memory:
        return False
    _save_agent_memory(normalized)
    return True


def save_agent_memory(stage, progress_status, main_problem, action_plan):
    memory = normalize_agent_memory(load_agent_memory())
    today = str(date.today())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = next(
        (
            item for item in memory
            if isinstance(item, dict) and item.get("date") == today
        ),
        None
    )
    try:
        run_count = int(existing.get("run_count", 0)) + 1
    except (AttributeError, TypeError, ValueError):
        run_count = 1

    snapshot = {
        "date": today,
        "stage": stage,
        "progress_status": progress_status,
        "main_problem": main_problem,
        "action_plan": list(action_plan) if isinstance(action_plan, list) else [],
        "first_seen_at": (
            existing.get("first_seen_at", now)
            if isinstance(existing, dict)
            else now
        ),
        "updated_at": now,
        "run_count": run_count
    }
    if existing is None:
        memory.append(snapshot)
    else:
        existing.clear()
        existing.update(snapshot)

    memory = normalize_agent_memory(memory)
    _save_agent_memory(memory)
    return snapshot


def analyze_trend():
    recent_memory = [
        item
        for item in normalize_agent_memory(load_agent_memory())
        if isinstance(item, dict) and str(item.get("date", "")).strip()
    ][-7:]

    if not recent_memory:
        return "目前还没有 Agent 运行记录。"

    progress_stats = {}
    problem_stats = {}

    for item in recent_memory:
        progress_status = item.get("progress_status", "未知")
        progress_stats[progress_status] = progress_stats.get(progress_status, 0) + 1

        main_problem = item.get("main_problem", "暂无明确问题")
        problem_stats[main_problem] = problem_stats.get(main_problem, 0) + 1

    sorted_progress = sorted(
        progress_stats.items(),
        key=lambda item: item[1],
        reverse=True
    )
    sorted_problems = sorted(
        problem_stats.items(),
        key=lambda item: item[1],
        reverse=True
    )

    lines = [
        "===== Agent 趋势分析 =====",
        "",
        f"最近 {len(recent_memory)} 个有记录的日期：",
        ""
    ]

    for status, count in sorted_progress:
        lines.append(f"{status}：{count} 天")

    lines.extend(["", "主要问题：", ""])

    for problem, count in sorted_problems:
        lines.append(f"{problem}：{count} 天")

    return "\n".join(lines)
