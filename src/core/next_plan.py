from app.dashboard import (
    PLAN_PATH,
    PROBLEM_BANK_PATH,
    RECORDS_PATH,
    clean_problem_id,
    load_json
)
from core.learning_analyzer import analyze_learning_patterns
from planning.plan_progress import (
    get_completed_problem_ids,
    get_plan_records,
    get_planned_problem_ids
)


def generate_next_week_plan_draft():
    plan = load_json(PLAN_PATH, {})
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    records = load_json(RECORDS_PATH, [])

    if not isinstance(plan, dict):
        plan = {}
    if not isinstance(problem_bank, dict):
        problem_bank = {}
    if not isinstance(records, list):
        records = []

    planned_problem_ids = get_planned_problem_ids(plan)
    completed_ids = get_completed_problem_ids(plan, records)
    plan_records = get_plan_records(plan, records)
    failed_ids = set()
    hinted_ids = set()
    mistake_stats = {}

    for record in plan_records:
        if not isinstance(record, dict):
            continue

        problem_id = clean_problem_id(record.get("problem_id", ""))
        status = str(record.get("status", "未知")).replace(" ", "")

        if status == "未通过":
            failed_ids.add(problem_id)
        if status == "看提示后AC":
            hinted_ids.add(problem_id)

        mistake_type = record.get("mistake_type", "未分类") or "未分类"
        if mistake_type != "未分类":
            mistake_stats[mistake_type] = mistake_stats.get(mistake_type, 0) + 1

    completed_planned_ids = [
        problem_id
        for problem_id in planned_problem_ids
        if problem_id in completed_ids
    ]
    unfinished_ids = [
        problem_id
        for problem_id in planned_problem_ids
        if problem_id not in completed_ids
    ]
    review_ids = [
        problem_id
        for problem_id in planned_problem_ids
        if problem_id in hinted_ids or problem_id in failed_ids
    ]

    learning_analysis = analyze_learning_patterns(
        records=records,
        problem_bank=problem_bank
    )
    main_mistake_type = learning_analysis.get("main_weakness", "")
    if main_mistake_type == "暂无明确分类":
        main_mistake_type = ""

    day_3 = "Day 3：巩固当前薄弱题型"
    if main_mistake_type:
        day_3 = f"Day 3：针对主要薄弱点“{main_mistake_type}”安排专项练习"

    lines = [
        "===== 下一周计划雏形 =====",
        "",
        "本周完成情况：",
        f"- 计划题目：{len(planned_problem_ids)} 题",
        f"- 已完成：{len(completed_planned_ids)} 题",
        f"- 未完成：{len(unfinished_ids)} 题",
        "",
        "建议下周安排：",
        "Day 1：复习本周未完成题",
        "Day 2：复习看提示后 AC 的题",
        day_3,
        "Day 4：新题练习",
        "Day 5：新题练习",
        "Day 6：复习错题",
        "Day 7：总结与自由练习",
        "",
        "遗留题目："
    ]

    if unfinished_ids:
        for problem_id in unfinished_ids:
            title = problem_bank.get(problem_id, {}).get("title", "未知题目")
            lines.append(f"- {problem_id} {title}")
    else:
        lines.append("- 暂无")

    lines.extend(["", "重点复习题："])
    if review_ids:
        for problem_id in review_ids:
            title = problem_bank.get(problem_id, {}).get("title", "未知题目")
            lines.append(f"- {problem_id} {title}")
    else:
        lines.append("- 暂无")

    if len(records) < 3:
        lines.extend([
            "",
            "当前记录较少，建议下周继续完成数组基础题，并保持记录。"
        ])

    return "\n".join(lines)
