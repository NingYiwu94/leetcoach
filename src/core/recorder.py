import json
from pathlib import Path
from datetime import datetime, timedelta

from core.review_scheduler import upsert_review_task
from core.learning_analyzer import (
    analyze_learning_patterns,
    refresh_learning_analysis
)


from app_paths import BASE_DIR
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"


def load_json(path, default):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_problem_id(problem_id):
    problem_id = str(problem_id)
    problem_id = problem_id.replace("题号：", "")
    problem_id = problem_id.replace("题号:", "")
    problem_id = problem_id.replace("题号", "")
    return problem_id.strip()


def calculate_next_review(status, difficulty_feeling):
    """
    简单复习规则：
    - easy: 7天后
    - normal: 3天后
    - hard: 1天后
    - failed: 明天
    """
    today = datetime.now().date()

    if status == "未通过":
        delta = 1
    elif difficulty_feeling == "困难":
        delta = 1
    elif difficulty_feeling == "一般":
        delta = 3
    else:
        delta = 7

    return str(today + timedelta(days=delta))


def add_record(
    problem_id,
    status,
    difficulty_feeling,
    mistake_type,
    mistake_note,
    source="",
    plan_week=None,
    plan_start_date=""
):
    problem_id = clean_problem_id(problem_id)

    records = load_json(RECORDS_PATH, [])
    reviews = load_json(REVIEWS_PATH, [])

    now = datetime.now()

    record = {
        "date": str(now.date()),
        "time": now.strftime("%H:%M:%S"),
        "problem_id": problem_id,
        "status": status,
        "difficulty_feeling": difficulty_feeling,
        "mistake_type": mistake_type,
        "mistake_note": mistake_note
    }
    if source:
        record["source"] = source
    if plan_week not in (None, ""):
        record["plan_week"] = plan_week
    if plan_start_date:
        record["plan_start_date"] = str(plan_start_date)

    next_review_date = calculate_next_review(status, difficulty_feeling)

    records.append(record)
    review = upsert_review_task(
        reviews=reviews,
        record=record,
        records=records,
        reason=f"错因分类：{mistake_type}；问题：{mistake_note}"
    )

    save_json(RECORDS_PATH, records)
    save_json(REVIEWS_PATH, reviews)
    try:
        refresh_learning_analysis()
    except Exception:
        pass

    return record, review


def get_all_records():
    records = load_json(RECORDS_PATH, [])
    return records


def format_records(records):
    if not records:
        return "目前还没有刷题记录。"

    lines = []

    for i, record in enumerate(records, start=1):
        lines.append(f"{i}. 题号：{record.get('problem_id', '未知')}")
        lines.append(f"   日期：{record.get('date', '未知')}")
        lines.append(f"   状态：{record.get('status', '未知')}")
        lines.append(f"   难度感受：{record.get('difficulty_feeling', '未知')}")
        lines.append(f"   错因分类：{record.get('mistake_type', '未分类')}")
        lines.append(f"   问题/收获：{record.get('mistake_note', '无')}")
        lines.append("")

    return "\n".join(lines)


def get_mistake_stats():
    records = load_json(RECORDS_PATH, [])
    stats = {}

    for record in records:
        mistake_type = record.get("mistake_type", "未分类")
        stats[mistake_type] = stats.get(mistake_type, 0) + 1

    return stats


def format_mistake_stats(stats):
    if not stats:
        return "目前还没有错因统计。"

    lines = ["错因统计："]
    sorted_stats = sorted(
        (
            item for item in stats.items()
            if item[0] != "未分类"
        ),
        key=lambda item: item[1],
        reverse=True
    )

    for i, (mistake_type, count) in enumerate(sorted_stats, start=1):
        lines.append(f"{i}. {mistake_type}：{count} 次")

    unclassified_count = stats.get("未分类", 0)
    if unclassified_count:
        lines.extend([
            "",
            f"未分类记录：{unclassified_count} 次",
            "说明：自动同步产生的未分类记录不作为薄弱点判断依据。"
        ])

    return "\n".join(lines)


def generate_week_summary():
    records = load_json(RECORDS_PATH, [])
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    week_records = []

    for record in records:
        try:
            record_date = datetime.strptime(record.get("date", ""), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue

        if week_start <= record_date <= week_end:
            week_records.append(record)

    if not week_records:
        return "本周还没有刷题记录，暂时无法生成总结。"

    status_stats = {
        "AC": 0,
        "看提示后 AC": 0,
        "未通过": 0,
        "未知": 0
    }
    mistake_stats = {}
    difficulty_stats = {}

    for record in week_records:
        status = record.get("status", "未知")

        if status == "AC":
            status_stats["AC"] += 1
        elif status.replace(" ", "") == "看提示后AC":
            status_stats["看提示后 AC"] += 1
        elif status == "未通过":
            status_stats["未通过"] += 1
        else:
            status_stats["未知"] += 1

        mistake_type = record.get("mistake_type", "未分类") or "未分类"
        if mistake_type != "未分类":
            mistake_stats[mistake_type] = (
                mistake_stats.get(mistake_type, 0) + 1
            )

        difficulty = record.get("difficulty_feeling", "未知") or "未知"
        difficulty_stats[difficulty] = difficulty_stats.get(difficulty, 0) + 1

    sorted_mistakes = sorted(
        mistake_stats.items(),
        key=lambda item: item[1],
        reverse=True
    )
    sorted_difficulties = sorted(
        difficulty_stats.items(),
        key=lambda item: item[1],
        reverse=True
    )
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    learning_analysis = analyze_learning_patterns(
        records=week_records,
        problem_bank=problem_bank
    )

    recent_notes = []
    for record in reversed(week_records):
        note = record.get("mistake_note", "").strip()
        if note and note not in {
            "力扣自动同步",
            "GUI快捷标记完成"
        }:
            recent_notes.append(note)
        if len(recent_notes) == 3:
            break

    lines = [
        "===== 本周刷题总结 =====",
        "",
        f"本周总刷题次数：{len(week_records)}",
        f"AC：{status_stats['AC']} 次",
        f"看提示后 AC：{status_stats['看提示后 AC']} 次",
        f"未通过：{status_stats['未通过']} 次"
    ]

    if status_stats["未知"]:
        lines.append(f"未知：{status_stats['未知']} 次")

    lines.extend(["", "主要错因："])
    if sorted_mistakes:
        for i, (mistake_type, count) in enumerate(sorted_mistakes, start=1):
            lines.append(f"{i}. {mistake_type}：{count} 次")
    else:
        inferred_weakness = learning_analysis.get(
            "main_weakness",
            "暂无明确分类"
        )
        lines.append(f"1. 自动推断：{inferred_weakness}")

    lines.extend(["", "难度感受："])
    for i, (difficulty, count) in enumerate(sorted_difficulties, start=1):
        lines.append(f"{i}. {difficulty}：{count} 次")

    lines.extend(["", "典型问题/收获："])
    if recent_notes:
        for note in recent_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- 暂无记录")

    lines.extend(["", "本周建议："])
    main_mistake_type = learning_analysis.get(
        "main_weakness",
        "暂无明确分类"
    )
    if main_mistake_type != "暂无明确分类":
        lines.append(
            f"本周主要问题集中在“{main_mistake_type}”，"
            "建议针对该类问题复习对应题型模板。"
        )
    else:
        lines.append("建议继续保持记录，积累更多刷题数据。")

    return "\n".join(lines)
