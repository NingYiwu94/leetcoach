import json
from pathlib import Path
from datetime import datetime

from core.review_scheduler import (
    build_review_queue,
    clean_problem_id,
    reconcile_review_tasks,
    schedule_follow_up_review
)


from app_paths import BASE_DIR
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
RECORDS_PATH = BASE_DIR / "data" / "records.json"


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


def get_today_reviews():
    today = str(datetime.now().date())

    reviews = load_json(REVIEWS_PATH, [])
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    records = load_json(RECORDS_PATH, [])

    today_reviews = []

    for item in build_review_queue(reviews, records, due_only=True):
        problem_id = item["problem_id"]
        info = problem_bank.get(problem_id, {})

        today_reviews.append({
            "problem_id": problem_id,
            "title": info.get("title", "未知题目"),
            "topics": info.get("topics", []),
            "reason": item.get("reason", ""),
            "priority_level": item.get("priority_level", "低"),
            "priority_score": item.get("priority_score", 0),
            "failure_count": item.get("failure_count", 0),
            "assisted_count": item.get("assisted_count", 0),
            "overdue_days": item.get("overdue_days", 0),
            "review_round": item.get("review_round", 1)
        })

    return today_reviews


def maintain_review_tasks():
    reviews = load_json(REVIEWS_PATH, [])
    records = load_json(RECORDS_PATH, [])
    if not isinstance(reviews, list):
        return False

    if not reconcile_review_tasks(reviews, records):
        return False

    with open(REVIEWS_PATH, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    return True


def format_today_reviews(reviews):
    if not reviews:
        return "今日暂无到期复习题。"

    lines = ["今日建议复习："]

    for r in reviews:
        topics = "、".join(r["topics"])
        lines.append(f"- {r['problem_id']} {r['title']}")
        lines.append(f"  复习轮次：第 {r.get('review_round', 1)} 轮")
        lines.append(f"  优先级：{r.get('priority_level', '低')}")
        lines.append(f"  题型：{topics}")
        lines.append(f"  复习原因：{r['reason']}")

    return "\n".join(lines)


MASTERY_LABELS = {
    "independent": "独立写出",
    "assisted": "看提示写出",
    "not_mastered": "仍未掌握"
}


def _apply_review_result(
    reviews,
    records,
    problem_id,
    mastery_result,
    create_if_missing,
    completion_metadata=None
):
    problem_id = clean_problem_id(problem_id)
    mastery_result = str(mastery_result or "independent").strip()
    if mastery_result not in MASTERY_LABELS:
        mastery_result = "independent"

    completed_reviews = []
    for review in reviews:
        saved_problem_id = clean_problem_id(review.get("problem_id", ""))

        if saved_problem_id == problem_id and not review.get("done"):
            review["done"] = True
            review["completed_at"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            review["mastery_result"] = mastery_result
            review["mastery_label"] = MASTERY_LABELS[mastery_result]
            if isinstance(completion_metadata, dict):
                review.update(completion_metadata)
            completed_reviews.append(review)

    if not completed_reviews and create_if_missing:
        assessment = {
            "problem_id": problem_id,
            "next_review_date": str(datetime.now().date()),
            "reason": "阶段复习验收",
            "done": True,
            "source": "stage_review",
            "review_round": 1,
            "scheduled_from": "stage_review",
            "completed_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "mastery_result": mastery_result,
            "mastery_label": MASTERY_LABELS[mastery_result]
        }
        if isinstance(completion_metadata, dict):
            assessment.update(completion_metadata)
        reviews.append(assessment)
        completed_reviews.append(assessment)

    if completed_reviews:
        def review_round(item):
            try:
                return int(item.get("review_round", 1) or 1)
            except (TypeError, ValueError):
                return 1

        primary_review = max(
            completed_reviews,
            key=review_round
        )
        schedule_follow_up_review(
            reviews=reviews,
            completed_review=primary_review,
            records=records,
            mastery_result=mastery_result
        )

    return bool(completed_reviews)


def mark_review_done(
    problem_id,
    mastery_result="independent",
    create_if_missing=False
):
    reviews = load_json(REVIEWS_PATH, [])
    records = load_json(RECORDS_PATH, [])
    if not isinstance(reviews, list):
        return False
    if not isinstance(records, list):
        records = []

    success = _apply_review_result(
        reviews,
        records,
        problem_id,
        mastery_result,
        create_if_missing
    )
    if success:
        save_json(REVIEWS_PATH, reviews)
    return success


def record_stage_review_results(review_results, assessment_id=""):
    if not isinstance(review_results, dict) or not review_results:
        return False

    reviews = load_json(REVIEWS_PATH, [])
    records = load_json(RECORDS_PATH, [])
    if not isinstance(reviews, list):
        return False
    if not isinstance(records, list):
        records = []

    assessment_id = str(assessment_id or "").strip()
    if assessment_id:
        saved_problem_ids = {
            clean_problem_id(item.get("problem_id"))
            for item in reviews
            if (
                isinstance(item, dict)
                and item.get("done")
                and item.get("stage_assessment_id") == assessment_id
            )
        }
        expected_problem_ids = {
            clean_problem_id(problem_id)
            for problem_id in review_results
        }
        if saved_problem_ids == expected_problem_ids:
            return True

    completion_metadata = (
        {"stage_assessment_id": assessment_id}
        if assessment_id
        else {}
    )
    for problem_id, mastery_result in review_results.items():
        if not _apply_review_result(
            reviews,
            records,
            problem_id,
            mastery_result,
            create_if_missing=True,
            completion_metadata=completion_metadata
        ):
            return False

    save_json(REVIEWS_PATH, reviews)
    return True


if __name__ == "__main__":
    reviews = get_today_reviews()
    print(format_today_reviews(reviews))
