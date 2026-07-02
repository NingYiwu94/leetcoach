from datetime import date, datetime, timedelta


COMPLETED_STATUSES = {"AC", "看提示后AC"}
DEFAULT_DAILY_REVIEW_LIMIT = 2


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

    record_date = str(record.get("date", "")).strip()
    record_time = str(record.get("time", "00:00:00")).strip()
    try:
        return datetime.strptime(
            f"{record_date} {record_time}",
            "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        return datetime.min


def get_problem_learning_stats(records):
    grouped = {}
    if not isinstance(records, list):
        return grouped

    for record in records:
        if not isinstance(record, dict):
            continue
        problem_id = clean_problem_id(record.get("problem_id"))
        if not problem_id:
            continue
        grouped.setdefault(problem_id, []).append(record)

    stats = {}
    for problem_id, problem_records in grouped.items():
        ordered = sorted(problem_records, key=_record_datetime)
        statuses = [
            str(record.get("status", "未知")).replace(" ", "")
            for record in ordered
        ]
        failure_count = statuses.count("未通过")
        assisted_count = statuses.count("看提示后AC")
        consecutive_failures = 0
        for status in reversed(statuses):
            if status != "未通过":
                break
            consecutive_failures += 1

        stats[problem_id] = {
            "submission_count": len(ordered),
            "failure_count": failure_count,
            "assisted_count": assisted_count,
            "consecutive_failures": consecutive_failures,
            "last_status": statuses[-1] if statuses else "未知",
            "last_record_date": (
                str(ordered[-1].get("date", ""))
                if ordered
                else ""
            )
        }
    return stats


def calculate_review_metadata(problem_id, records, next_review_date):
    problem_id = clean_problem_id(problem_id)
    stats = get_problem_learning_stats(records).get(problem_id, {})
    failure_count = stats.get("failure_count", 0)
    assisted_count = stats.get("assisted_count", 0)
    submission_count = stats.get("submission_count", 0)
    consecutive_failures = stats.get("consecutive_failures", 0)
    last_status = stats.get("last_status", "未知")

    try:
        due_date = datetime.strptime(
            str(next_review_date),
            "%Y-%m-%d"
        ).date()
        overdue_days = max(0, (date.today() - due_date).days)
    except ValueError:
        overdue_days = 0

    score = min(overdue_days, 7) * 2
    score += failure_count * 4
    score += assisted_count * 3
    score += max(0, submission_count - 1)
    score += consecutive_failures * 3
    if last_status == "未通过":
        score += 5
    elif last_status == "看提示后AC":
        score += 3

    if score >= 8:
        priority_level = "高"
    elif score >= 3:
        priority_level = "中"
    else:
        priority_level = "低"

    return {
        "priority_score": score,
        "priority_level": priority_level,
        "failure_count": failure_count,
        "assisted_count": assisted_count,
        "submission_count": submission_count,
        "consecutive_failures": consecutive_failures,
        "last_status": last_status,
        "overdue_days": overdue_days
    }


def calculate_next_review_date(record, records):
    problem_id = clean_problem_id(record.get("problem_id"))
    status = str(record.get("status", "")).replace(" ", "")
    stats = get_problem_learning_stats(records).get(problem_id, {})

    try:
        submit_date = datetime.strptime(
            str(record.get("date", "")),
            "%Y-%m-%d"
        ).date()
    except ValueError:
        submit_date = date.today()

    if status == "未通过":
        delay = 1
    elif status == "看提示后AC":
        delay = 2
    elif stats.get("failure_count", 0) > 0:
        delay = 2
    else:
        delay = 3
    return str(submit_date + timedelta(days=delay))


def upsert_review_task(reviews, record, records, reason, source=""):
    if not isinstance(reviews, list):
        reviews = []

    problem_id = clean_problem_id(record.get("problem_id"))
    next_review_date = calculate_next_review_date(record, records)
    active_matches = [
        review
        for review in reviews
        if (
            isinstance(review, dict)
            and not review.get("done")
            and clean_problem_id(review.get("problem_id")) == problem_id
        )
    ]

    if active_matches:
        review = active_matches[0]
        review["next_review_date"] = next_review_date
        review["reason"] = reason
        review["review_round"] = 1
        review["scheduled_from"] = "learning_record"
        if source:
            review["source"] = source

        for duplicate in active_matches[1:]:
            duplicate["done"] = True
            duplicate["merged_into"] = problem_id
    else:
        review = {
            "problem_id": problem_id,
            "next_review_date": next_review_date,
            "reason": reason,
            "done": False,
            "review_round": 1,
            "scheduled_from": "learning_record"
        }
        if source:
            review["source"] = source
        reviews.append(review)

    review.update(
        calculate_review_metadata(
            problem_id,
            records,
            review.get("next_review_date", next_review_date)
        )
    )
    review["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return review


def schedule_follow_up_review(
    reviews,
    completed_review,
    records,
    mastery_result="independent"
):
    if not isinstance(reviews, list) or not isinstance(
        completed_review, dict
    ):
        return None

    problem_id = clean_problem_id(completed_review.get("problem_id"))
    if not problem_id:
        return None

    try:
        current_round = max(
            1, int(completed_review.get("review_round", 1))
        )
    except (TypeError, ValueError):
        current_round = 1
    mastery_result = str(mastery_result or "independent").strip()
    if mastery_result not in {
        "independent",
        "assisted",
        "not_mastered"
    }:
        mastery_result = "independent"

    next_round = (
        current_round
        if mastery_result == "not_mastered"
        else current_round + 1
    )

    if mastery_result == "not_mastered":
        delay_days = 1
    elif mastery_result == "assisted":
        delay_days = 3 if current_round == 1 else 5
    elif current_round == 1:
        delay_days = 7
    elif current_round == 2:
        delay_days = 14
    else:
        delay_days = 30

    stats = get_problem_learning_stats(records).get(problem_id, {})
    last_status = stats.get("last_status", "未知")
    if mastery_result == "not_mastered":
        delay_days = 1
    elif last_status == "未通过":
        delay_days = 2
    elif last_status == "看提示后AC":
        delay_days = min(delay_days, 5)
    elif stats.get("consecutive_failures", 0) > 0:
        delay_days = min(delay_days, 2)

    next_review_date = str(date.today() + timedelta(days=delay_days))
    result_labels = {
        "independent": "独立写出",
        "assisted": "看提示写出",
        "not_mastered": "仍未掌握"
    }
    mastery_label = result_labels[mastery_result]
    if mastery_result == "not_mastered":
        reason = (
            f"复习结果：{mastery_label}，保留第 {current_round} 轮，"
            "次日再次练习"
        )
    else:
        reason = (
            f"复习结果：{mastery_label}；已完成第 {current_round} 轮，"
            f"安排第 {next_round} 轮巩固"
        )

    follow_up = {
        "problem_id": problem_id,
        "next_review_date": next_review_date,
        "reason": reason,
        "done": False,
        "source": "spaced_review",
        "review_round": next_round,
        "interval_days": delay_days,
        "previous_mastery_result": mastery_result,
        "previous_mastery_label": mastery_label,
        "scheduled_from": "review_completion",
        "previous_review_completed_at": completed_review.get(
            "completed_at", ""
        ),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    follow_up.update(
        calculate_review_metadata(
            problem_id,
            records,
            next_review_date
        )
    )
    reviews.append(follow_up)
    return follow_up


def reconcile_review_tasks(reviews, records):
    if not isinstance(reviews, list):
        return False

    changed = False
    active_by_problem = {}
    for review in reviews:
        if not isinstance(review, dict) or review.get("done"):
            continue
        problem_id = clean_problem_id(review.get("problem_id"))
        if not problem_id:
            continue
        active_by_problem.setdefault(problem_id, []).append(review)

    for problem_id, matches in active_by_problem.items():
        matches.sort(
            key=lambda item: str(item.get("next_review_date", ""))
        )
        primary = matches[0]
        if "review_round" not in primary:
            primary["review_round"] = 1
            changed = True
        if "scheduled_from" not in primary:
            primary["scheduled_from"] = "learning_record"
            changed = True
        metadata = calculate_review_metadata(
            problem_id,
            records,
            primary.get("next_review_date", "")
        )
        for key, value in metadata.items():
            if primary.get(key) != value:
                primary[key] = value
                changed = True

        for duplicate in matches[1:]:
            duplicate["done"] = True
            duplicate["merged_into"] = problem_id
            duplicate["completed_at"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            changed = True

    return changed


def build_review_queue(reviews, records, due_only=False):
    if not isinstance(reviews, list):
        return []

    today = str(date.today())
    queue_by_problem = {}
    for review in reviews:
        if not isinstance(review, dict) or review.get("done"):
            continue

        problem_id = clean_problem_id(review.get("problem_id"))
        if not problem_id:
            continue
        next_review_date = str(review.get("next_review_date", ""))
        if due_only and (not next_review_date or next_review_date > today):
            continue

        item = dict(review)
        item["problem_id"] = problem_id
        item.setdefault("review_round", 1)
        item.update(
            calculate_review_metadata(
                problem_id,
                records,
                next_review_date
            )
        )

        existing = queue_by_problem.get(problem_id)
        if existing is None:
            queue_by_problem[problem_id] = item
            continue

        if next_review_date < str(existing.get("next_review_date", "")):
            existing["next_review_date"] = next_review_date
        if item["priority_score"] > existing["priority_score"]:
            existing.update(item)

    return sorted(
        queue_by_problem.values(),
        key=lambda item: (
            -item.get("priority_score", 0),
            str(item.get("next_review_date", "")),
            item.get("problem_id", "")
        )
    )


def select_daily_reviews(
    due_reviews,
    today_problem_ids=None,
    task_type="",
    limit=None
):
    if not isinstance(due_reviews, list):
        return {
            "selected": [],
            "deferred": [],
            "due_count": 0,
            "limit": 0
        }

    today_problem_ids = {
        clean_problem_id(problem_id)
        for problem_id in (today_problem_ids or [])
        if clean_problem_id(problem_id)
    }
    task_type = str(task_type or "").strip()

    if limit is None:
        if task_type in {"review_day", "summary"}:
            limit = 0
        elif today_problem_ids:
            limit = DEFAULT_DAILY_REVIEW_LIMIT
        else:
            limit = 3
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = DEFAULT_DAILY_REVIEW_LIMIT

    eligible = []
    deferred = []
    for review in due_reviews:
        if not isinstance(review, dict):
            continue
        problem_id = clean_problem_id(review.get("problem_id"))
        if problem_id in today_problem_ids:
            deferred.append({
                **review,
                "deferred_reason": "已由今日计划覆盖"
            })
        else:
            eligible.append(review)

    selected = eligible[:limit]
    deferred.extend({
        **review,
        "deferred_reason": "超过今日复习容量"
    } for review in eligible[limit:])

    return {
        "selected": selected,
        "deferred": deferred,
        "due_count": len(due_reviews),
        "limit": limit
    }


def get_review_pressure(queue):
    high_count = sum(
        1 for item in queue if item.get("priority_level") == "高"
    )
    medium_count = sum(
        1 for item in queue if item.get("priority_level") == "中"
    )
    weighted_score = high_count * 3 + medium_count * 2 + (
        len(queue) - high_count - medium_count
    )

    if high_count >= 2 or weighted_score >= 8:
        level = "较大"
    elif queue:
        level = "正常"
    else:
        level = "较小"

    return {
        "level": level,
        "high_count": high_count,
        "medium_count": medium_count,
        "total_count": len(queue),
        "weighted_score": weighted_score
    }
