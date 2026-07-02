from datetime import datetime


COMPLETED_STATUSES = {"AC", "看提示后AC"}


def clean_problem_id(problem_id):
    value = str(problem_id or "")
    for prefix in ("题号：", "题号:", "题号"):
        value = value.replace(prefix, "")
    return value.strip()


def get_planned_problem_ids(plan):
    problem_ids = []
    if not isinstance(plan, dict):
        return problem_ids

    days = plan.get("days", {})
    if not isinstance(days, dict):
        return problem_ids

    for day in days.values():
        if not isinstance(day, dict):
            continue
        problems = day.get("problems", [])
        if not isinstance(problems, list):
            continue
        for problem_id in problems:
            problem_id = clean_problem_id(problem_id)
            if problem_id and problem_id not in problem_ids:
                problem_ids.append(problem_id)
    return problem_ids


def _parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def get_record_date(record):
    if not isinstance(record, dict):
        return None
    return _parse_date(record.get("submit_time") or record.get("date"))


def get_record_datetime(record):
    if not isinstance(record, dict):
        return None

    submit_time = str(record.get("submit_time", "")).strip()
    if submit_time:
        try:
            return datetime.strptime(
                submit_time[:19],
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            pass

    date_value = str(record.get("date", "")).strip()
    time_value = str(record.get("time", "")).strip() or "23:59:59"
    try:
        return datetime.strptime(
            f"{date_value[:10]} {time_value[:8]}",
            "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        return None


def get_plan_activation_datetime(plan):
    if not isinstance(plan, dict):
        return None

    activated_at = str(plan.get("activated_at", "")).strip()
    if activated_at:
        try:
            return datetime.strptime(
                activated_at[:19],
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            pass

    start_date = get_plan_start_date(plan)
    if start_date is None:
        return None
    return datetime.combine(start_date, datetime.min.time())


def get_plan_start_date(plan):
    if not isinstance(plan, dict):
        return None
    return _parse_date(plan.get("start_date"))


def get_plan_records(plan, records):
    if not isinstance(records, list):
        return []

    activation_datetime = get_plan_activation_datetime(plan)
    if activation_datetime is None:
        return [record for record in records if isinstance(record, dict)]

    scoped_records = []
    for record in records:
        same_plan = (
            str(record.get("plan_week", "")) == str(plan.get("week", ""))
            and str(record.get("plan_start_date", ""))
            == str(plan.get("start_date", ""))
        )
        record_datetime = get_record_datetime(record)
        if same_plan or (
            record_datetime is not None
            and record_datetime >= activation_datetime
        ):
            scoped_records.append(record)
    return scoped_records


def get_completed_problem_ids(plan, records):
    planned_ids = set(get_planned_problem_ids(plan))
    completed_ids = set()

    for record in get_plan_records(plan, records):
        problem_id = clean_problem_id(record.get("problem_id"))
        status = str(record.get("status", "")).replace(" ", "")
        if problem_id in planned_ids and status in COMPLETED_STATUSES:
            completed_ids.add(problem_id)

    return completed_ids
