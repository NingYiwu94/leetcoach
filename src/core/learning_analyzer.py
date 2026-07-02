import json
from datetime import datetime
from pathlib import Path

from core.learning_curriculum import canonical_problem_id


from app_paths import BASE_DIR
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
ANALYSIS_PATH = BASE_DIR / "data" / "learning_analysis.json"


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


def _record_datetime(record):
    submit_time = str(record.get("submit_time", "")).strip()
    if submit_time:
        try:
            return datetime.strptime(submit_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    date_value = str(record.get("date", "")).strip()
    time_value = str(record.get("time", "00:00:00")).strip()
    try:
        return datetime.strptime(
            f"{date_value} {time_value}",
            "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        return datetime.min


def summarize_review_mastery(reviews):
    summary = {}
    if not isinstance(reviews, list):
        return summary

    completed = [
        item
        for item in reviews
        if (
            isinstance(item, dict)
            and item.get("done")
            and item.get("mastery_result")
        )
    ]
    completed.sort(
        key=lambda item: str(item.get("completed_at", ""))
    )
    for review in completed:
        problem_id = clean_problem_id(review.get("problem_id"))
        mastery_result = str(review.get("mastery_result", "")).strip()
        if not problem_id or mastery_result not in {
            "independent",
            "assisted",
            "not_mastered"
        }:
            continue
        item = summary.setdefault(problem_id, {
            "independent_count": 0,
            "assisted_count": 0,
            "not_mastered_count": 0,
            "latest_result": "",
            "latest_label": "",
            "latest_completed_at": ""
        })
        item[f"{mastery_result}_count"] += 1
        item["latest_result"] = mastery_result
        item["latest_label"] = review.get("mastery_label", "")
        item["latest_completed_at"] = review.get("completed_at", "")
    return summary


def _problem_profile(
    problem_id,
    records,
    problem_bank,
    review_mastery=None
):
    ordered = sorted(records, key=_record_datetime)
    statuses = [
        str(record.get("status", "未知")).replace(" ", "")
        for record in ordered
    ]
    failed_count = statuses.count("未通过")
    assisted_count = statuses.count("看提示后AC")
    completed_indices = [
        index
        for index, status in enumerate(statuses)
        if status in {"AC", "看提示后AC"}
    ]
    attempts_before_first_completion = (
        completed_indices[0] + 1
        if completed_indices
        else len(statuses)
    )
    unresolved_failure = bool(statuses and statuses[-1] == "未通过")
    retry_before_completion = max(0, attempts_before_first_completion - 1)

    manual_mistakes = {}
    notes = []
    for record in ordered:
        mistake_type = str(
            record.get("mistake_type") or "未分类"
        ).strip()
        if mistake_type != "未分类":
            manual_mistakes[mistake_type] = (
                manual_mistakes.get(mistake_type, 0) + 1
            )
        note = str(record.get("mistake_note") or "").strip()
        if note and note not in {
            "力扣自动同步",
            "GUI快捷标记完成"
        }:
            notes.append(note)

    risk_score = failed_count * 5
    risk_score += assisted_count * 4
    risk_score += retry_before_completion * 2
    risk_score += 5 if unresolved_failure else 0
    risk_score += sum(manual_mistakes.values()) * 3
    review_mastery = (
        review_mastery
        if isinstance(review_mastery, dict)
        else {}
    )
    latest_mastery = review_mastery.get("latest_result", "")
    if latest_mastery == "not_mastered":
        risk_score += 10
    elif latest_mastery == "assisted":
        risk_score += 5

    problem = problem_bank.get(problem_id, {})
    if not isinstance(problem, dict):
        problem = {}
    topics = problem.get("topics", [])
    if not isinstance(topics, list):
        topics = []
    key_points = problem.get("key_points", [])
    if not isinstance(key_points, list):
        key_points = []

    patterns = []
    if unresolved_failure:
        patterns.append("最近一次仍未通过")
    if failed_count:
        patterns.append(f"累计未通过 {failed_count} 次")
    if assisted_count:
        patterns.append(f"看提示后 AC {assisted_count} 次")
    if retry_before_completion:
        patterns.append(f"首次完成前重试 {retry_before_completion} 次")
    if latest_mastery == "not_mastered":
        patterns.append("最近复习仍未掌握")
    elif latest_mastery == "assisted":
        patterns.append("最近复习需要提示")

    return {
        "problem_id": problem_id,
        "title": problem.get("title", "未知题目"),
        "topics": topics,
        "key_points": key_points,
        "record_count": len(ordered),
        "failed_count": failed_count,
        "assisted_count": assisted_count,
        "retry_before_completion": retry_before_completion,
        "unresolved_failure": unresolved_failure,
        "last_status": statuses[-1] if statuses else "未知",
        "manual_mistakes": manual_mistakes,
        "notes": notes[-3:],
        "patterns": patterns,
        "review_mastery": review_mastery,
        "latest_mastery_result": latest_mastery,
        "risk_score": risk_score
    }


def analyze_learning_patterns(
    records=None,
    problem_bank=None,
    reviews=None
):
    if records is None:
        records = load_json(RECORDS_PATH, [])
    if problem_bank is None:
        problem_bank = load_json(PROBLEM_BANK_PATH, {})
    if reviews is None:
        reviews = load_json(REVIEWS_PATH, [])
    if not isinstance(records, list):
        records = []
    if not isinstance(problem_bank, dict):
        problem_bank = {}
    if not isinstance(reviews, list):
        reviews = []

    review_mastery = summarize_review_mastery(reviews)
    grouped = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        problem_id = canonical_problem_id(record, problem_bank)
        if problem_id:
            grouped.setdefault(problem_id, []).append(record)

    profiles = [
        _problem_profile(
            problem_id,
            problem_records,
            problem_bank,
            review_mastery.get(problem_id)
        )
        for problem_id, problem_records in grouped.items()
    ]
    recorded_problem_ids = {profile["problem_id"] for profile in profiles}
    for problem_id, mastery in review_mastery.items():
        if problem_id in recorded_problem_ids:
            continue
        profiles.append(
            _problem_profile(
                problem_id,
                [],
                problem_bank,
                mastery
            )
        )
    profiles.sort(
        key=lambda item: (-item["risk_score"], item["problem_id"])
    )

    topic_scores = {}
    mistake_scores = {}
    for profile in profiles:
        risk_score = profile["risk_score"]
        if risk_score <= 0:
            continue
        for topic in profile["topics"]:
            if topic == "数组" and len(profile["topics"]) > 1:
                continue
            topic_scores[topic] = topic_scores.get(topic, 0) + risk_score
        for mistake_type, count in profile["manual_mistakes"].items():
            mistake_scores[mistake_type] = (
                mistake_scores.get(mistake_type, 0) + count * 3
            )

    sorted_topics = sorted(
        topic_scores.items(),
        key=lambda item: (-item[1], item[0])
    )
    sorted_mistakes = sorted(
        mistake_scores.items(),
        key=lambda item: (-item[1], item[0])
    )
    risky_problems = [
        profile for profile in profiles if profile["risk_score"] > 0
    ]

    main_topic = sorted_topics[0][0] if sorted_topics else ""
    main_mistake = sorted_mistakes[0][0] if sorted_mistakes else ""
    if main_topic and main_mistake:
        main_weakness = f"{main_topic}：{main_mistake}"
    elif main_topic:
        main_weakness = main_topic
    elif main_mistake:
        main_weakness = main_mistake
    else:
        main_weakness = "暂无明确分类"

    failure_count = sum(
        profile["failed_count"] for profile in profiles
    )
    assisted_count = sum(
        profile["assisted_count"] for profile in profiles
    )
    unresolved_count = sum(
        1 for profile in profiles if profile["unresolved_failure"]
    )
    review_not_mastered_count = sum(
        1
        for profile in profiles
        if profile["latest_mastery_result"] == "not_mastered"
    )
    review_assisted_count = sum(
        1
        for profile in profiles
        if profile["latest_mastery_result"] == "assisted"
    )
    review_independent_count = sum(
        1
        for profile in profiles
        if profile["latest_mastery_result"] == "independent"
    )

    if review_not_mastered_count:
        learning_status = "存在复习后仍未掌握的题目"
    elif unresolved_count:
        learning_status = "存在尚未解决的失败题"
    elif failure_count + assisted_count >= 3:
        learning_status = "独立解题稳定性需要加强"
    elif risky_problems:
        learning_status = "存在需要巩固的题型"
    else:
        learning_status = "当前记录未发现明显薄弱点"

    recommended_actions = []
    if risky_problems:
        top_problem = risky_problems[0]
        recommended_actions.append(
            f"优先复盘 {top_problem['problem_id']} "
            f"{top_problem['title']}。"
        )
        if top_problem["key_points"]:
            recommended_actions.append(
                "重点检查："
                + "、".join(top_problem["key_points"][:3])
                + "。"
            )
    if main_topic:
        recommended_actions.append(
            f"下一阶段继续安排“{main_topic}”相关练习。"
        )
    if not recommended_actions:
        recommended_actions.append(
            "继续自动同步提交记录，积累更多可分析数据。"
        )

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "main_weakness": main_weakness,
        "main_topic": main_topic,
        "main_mistake": main_mistake,
        "learning_status": learning_status,
        "failure_count": failure_count,
        "assisted_count": assisted_count,
        "unresolved_count": unresolved_count,
        "review_mastery": review_mastery,
        "review_not_mastered_count": review_not_mastered_count,
        "review_assisted_count": review_assisted_count,
        "review_independent_count": review_independent_count,
        "topic_scores": dict(sorted_topics),
        "mistake_scores": dict(sorted_mistakes),
        "risky_problems": risky_problems[:5],
        "recommended_actions": recommended_actions
    }


def save_learning_analysis(analysis):
    ANALYSIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ANALYSIS_PATH, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)


def refresh_learning_analysis():
    analysis = analyze_learning_patterns()
    save_learning_analysis(analysis)
    return analysis


def format_learning_analysis(analysis):
    if not isinstance(analysis, dict):
        return "目前还没有可用的自动学习分析。"

    lines = [
        "===== 自动学习分析 =====",
        "",
        f"学习状态：{analysis.get('learning_status', '未知')}",
        f"当前主要薄弱点：{analysis.get('main_weakness', '暂无明确分类')}",
        f"累计未通过：{analysis.get('failure_count', 0)} 次",
        f"看提示后 AC：{analysis.get('assisted_count', 0)} 次",
        (
            "复习仍未掌握："
            f"{analysis.get('review_not_mastered_count', 0)} 题"
        ),
        (
            "复习需要提示："
            f"{analysis.get('review_assisted_count', 0)} 题"
        ),
        (
            "复习独立写出："
            f"{analysis.get('review_independent_count', 0)} 题"
        ),
        "",
        "高风险题目："
    ]

    risky_problems = analysis.get("risky_problems", [])
    if risky_problems:
        for profile in risky_problems:
            lines.append(
                f"- {profile.get('problem_id', '')} "
                f"{profile.get('title', '未知题目')} "
                f"（风险分 {profile.get('risk_score', 0)}）"
            )
            patterns = profile.get("patterns", [])
            if patterns:
                lines.append(f"  依据：{'；'.join(patterns)}")
    else:
        lines.append("- 暂无")

    lines.extend(["", "建议行动："])
    for action in analysis.get("recommended_actions", []):
        lines.append(f"- {action}")
    return "\n".join(lines)
