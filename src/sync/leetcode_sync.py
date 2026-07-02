import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib import error, request

from core.review_scheduler import reconcile_review_tasks, upsert_review_task
from core.learning_analyzer import refresh_learning_analysis
from sync.browser_sync import diagnose_browser_sync


from app_paths import BASE_DIR
CONFIG_PATH = BASE_DIR / "config" / "leetcode_config.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
DEBUG_PATH = BASE_DIR / "data" / "leetcode_sync_debug.json"
SYNC_STATE_PATH = BASE_DIR / "data" / "leetcode_sync_state.json"

DEFAULT_CONFIG = {
    "leetcode_username": "",
    "site": "leetcode.cn",
    "auto_sync_on_start": True,
    "sync_limit": 20
}

SITE_ENDPOINTS = {
    "leetcode.cn": "https://leetcode.cn/graphql/noj-go/",
    "leetcode.com": "https://leetcode.com/graphql/"
}


def _load_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_leetcode_config():
    if not CONFIG_PATH.exists():
        _save_json(CONFIG_PATH, DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    config = _load_json(CONFIG_PATH, {})
    if not isinstance(config, dict):
        return DEFAULT_CONFIG.copy()

    normalized = DEFAULT_CONFIG.copy()
    normalized.update({
        key: config[key]
        for key in DEFAULT_CONFIG
        if key in config
    })

    if normalized["site"] not in {"leetcode.cn", "leetcode.com"}:
        normalized["site"] = DEFAULT_CONFIG["site"]

    try:
        normalized["sync_limit"] = max(1, int(normalized["sync_limit"]))
    except (TypeError, ValueError):
        normalized["sync_limit"] = DEFAULT_CONFIG["sync_limit"]

    normalized["leetcode_username"] = str(
        normalized["leetcode_username"] or ""
    ).strip()
    normalized["auto_sync_on_start"] = bool(
        normalized["auto_sync_on_start"]
    )
    return normalized


def _graphql_queries(site):
    username_query = """
    query recentSubmissionList($username: String!, $limit: Int!) {
      recentSubmissionList(username: $username, limit: $limit) {
        title
        titleSlug
        timestamp
        statusDisplay
        lang
      }
    }
    """

    if site == "leetcode.com":
        return [(username_query, "username", "recentSubmissionList")]

    user_slug_query = """
    query recentSubmissionList($userSlug: String!, $limit: Int!) {
      recentSubmissionList(userSlug: $userSlug, limit: $limit) {
        title
        titleSlug
        timestamp
        statusDisplay
        lang
      }
    }
    """
    recent_ac_query = """
    query recentAcSubmissions($userSlug: String!) {
      recentACSubmissions(userSlug: $userSlug) {
        submitTime
        question {
          title
          translatedTitle
          titleSlug
        }
      }
    }
    """
    return [
        (recent_ac_query, "userSlug", "recentACSubmissions"),
        (username_query, "username", "recentSubmissionList"),
        (user_slug_query, "userSlug", "recentSubmissionList")
    ]


def _format_timestamp(value):
    if value in (None, ""):
        return "", None

    try:
        timestamp = int(float(value))
        if timestamp > 10_000_000_000:
            timestamp //= 1000
        submitted_at = datetime.fromtimestamp(timestamp)
        return submitted_at.strftime("%Y-%m-%d %H:%M:%S"), timestamp
    except (TypeError, ValueError, OSError, OverflowError):
        return str(value), None


def _normalize_api_item(item, accepted_only=False):
    if not isinstance(item, dict):
        return None

    question = item.get("question")
    if not isinstance(question, dict):
        question = {}

    title = (
        item.get("title")
        or question.get("translatedTitle")
        or question.get("title")
        or ""
    )
    title_slug = item.get("titleSlug") or question.get("titleSlug") or ""
    raw_timestamp = item.get("timestamp", item.get("submitTime"))
    submit_time, timestamp = _format_timestamp(raw_timestamp)
    status = (
        item.get("statusDisplay")
        or item.get("status")
        or ("Accepted" if accepted_only else "")
    )
    language = item.get("lang") or item.get("language") or ""

    if not title and not title_slug:
        return None

    return {
        "title": str(title),
        "title_slug": str(title_slug),
        "status": str(status or "Accepted"),
        "language": str(language),
        "submit_time": submit_time,
        "timestamp": timestamp
    }


def _fetch_recent_submissions_with_browser(
    username,
    limit,
    allow_browser_open=True
):
    try:
        from sync.browser_sync import fetch_recent_submissions_with_browser

        result = fetch_recent_submissions_with_browser(
            username,
            limit,
            allow_browser_open=allow_browser_open
        )
    except Exception as exc:
        result = {
            "success": False,
            "submissions": [],
            "error_type": "BrowserSessionError",
            "error_message": str(exc),
            "request_url": "https://leetcode.cn/graphql/noj-go/",
            "raw_response_preview": ""
        }

    normalized = []
    for item in result.get("submissions", []):
        if not isinstance(item, dict):
            continue
        submit_time, timestamp = _format_timestamp(
            item.get("timestamp", item.get("submit_time"))
        )
        normalized.append({
            "title": str(item.get("title", "")),
            "title_slug": str(item.get("title_slug", "")),
            "status": str(item.get("status", "Accepted")),
            "language": str(item.get("language", "")),
            "submit_time": submit_time,
            "timestamp": timestamp
        })

    result["submissions"] = normalized
    browser_attempts = result.pop("browser_attempts", [])
    if browser_attempts:
        result["request_attempts"] = [
            {
                "attempt": index,
                "query_name": item.get("name", ""),
                "transport": "chrome_devtools",
                "request_url": item.get("url", ""),
                "http_status": item.get("status"),
                "success": item.get("status") == 200,
                "error_type": "",
                "error_message": item.get("parse_error", ""),
                "raw_response_preview": item.get("text", "")[:500]
            }
            for index, item in enumerate(browser_attempts, start=1)
            if isinstance(item, dict)
        ]
    else:
        result["request_attempts"] = [{
            "attempt": 1,
            "query_name": "browser_session",
            "transport": "chrome_devtools",
            "http_status": 200 if result.get("success") else None,
            "success": bool(result.get("success")),
            "error_type": result.get("error_type", ""),
            "error_message": result.get("error_message", ""),
            "raw_response_preview": result.get(
                "raw_response_preview", ""
            )[:500]
        }]
    return result


def _is_cloudflare_challenge(response_preview):
    preview = str(response_preview or "").lower()
    markers = (
        "just a moment",
        "challenges.cloudflare.com",
        "cf-chl-",
        "cloudflare"
    )
    return any(marker in preview for marker in markers)


def _load_local_submission_cache(_limit):
    # Deprecated: local records must not be treated as a successful sync source.
    # Keeping this shim avoids breaking older tests or external imports.
    return []


def fetch_recent_submissions(
    username,
    site,
    limit,
    interactive=False,
    allow_local_cache=False
):
    username = str(username or "").strip()
    if not username:
        return {
            "success": False,
            "submissions": [],
            "error_type": "MissingUsername",
            "error_message": "未提供力扣用户名。",
            "raw_response_preview": "",
            "request_url": "",
            "request_attempts": []
        }

    if site not in {"leetcode.cn", "leetcode.com"}:
        return {
            "success": False,
            "submissions": [],
            "error_type": "InvalidSite",
            "error_message": f"不支持的站点：{site}",
            "raw_response_preview": "",
            "request_url": "",
            "request_attempts": []
        }

    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        return {
            "success": False,
            "submissions": [],
            "error_type": "InvalidLimit",
            "error_message": f"无效的同步数量：{limit}",
            "raw_response_preview": "",
            "request_url": "",
            "request_attempts": []
        }

    if site == "leetcode.cn":
        sync_state = _load_json(SYNC_STATE_PATH, {})
        existing_records = _load_json(RECORDS_PATH, [])
        has_synced_records = (
            isinstance(existing_records, list)
            and any(
                isinstance(record, dict)
                and record.get("source") == "leetcode_auto_sync"
                for record in existing_records
            )
        )
        previously_succeeded = (
            (
                isinstance(sync_state, dict)
                and sync_state.get("success") is True
                and sync_state.get("username") == username
                and sync_state.get("site") == site
            )
            or has_synced_records
        )
        browser_result = _fetch_recent_submissions_with_browser(
            username,
            limit,
            allow_browser_open=(interactive or not previously_succeeded)
        )
        if browser_result.get("success"):
            browser_result["sync_source"] = (
                "browser_cache"
                if browser_result.get("from_cache")
                else "browser_fresh"
            )
            return browser_result

        return browser_result

    endpoint = SITE_ENDPOINTS[site]
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "LeetCoach/1.5 (public submissions sync)",
        "Origin": f"https://{site}",
        "Referer": f"https://{site}/"
    }
    diagnostics = []
    request_attempts = []
    last_preview = ""

    for attempt_index, (
        query,
        username_key,
        result_key
    ) in enumerate(_graphql_queries(site), start=1):
        last_preview = ""
        variables = {username_key: username}
        if "$limit" in query:
            variables["limit"] = limit
        attempt = {
            "attempt": attempt_index,
            "query_name": result_key,
            "username_parameter": username_key,
            "variables": variables.copy(),
            "http_status": None,
            "success": False,
            "error_type": "",
            "error_message": "",
            "raw_response_preview": ""
        }

        payload = json.dumps({
            "query": query,
            "variables": variables
        }).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=payload,
            headers=headers,
            method="POST"
        )

        try:
            with request.urlopen(http_request, timeout=8) as response:
                attempt["http_status"] = getattr(response, "status", 200)
                raw_response = response.read().decode("utf-8")
                last_preview = raw_response[:500]
                attempt["raw_response_preview"] = last_preview
        except error.HTTPError as exc:
            preview = ""
            try:
                preview = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            last_preview = preview
            if exc.code == 403 and _is_cloudflare_challenge(preview):
                error_type = "CloudflareChallenge"
                message = (
                    f"{result_key}: CloudflareChallenge "
                    "公开接口要求浏览器验证，匿名标准库请求被拦截"
                )
            else:
                error_type = "HTTPError"
                message = f"{result_key}: HTTPError {exc.code} {exc.reason}"
            diagnostics.append(message)
            attempt.update({
                "http_status": exc.code,
                "error_type": error_type,
                "error_message": message,
                "raw_response_preview": preview
            })
            request_attempts.append(attempt)
            if error_type == "CloudflareChallenge":
                break
            continue
        except error.URLError as exc:
            message = f"{result_key}: URLError {exc.reason}"
            diagnostics.append(message)
            attempt.update({
                "error_type": "URLError",
                "error_message": message
            })
            request_attempts.append(attempt)
            continue
        except TimeoutError as exc:
            message = f"{result_key}: TimeoutError {exc}"
            diagnostics.append(message)
            attempt.update({
                "error_type": "TimeoutError",
                "error_message": message
            })
            request_attempts.append(attempt)
            continue
        except OSError as exc:
            message = f"{result_key}: OSError {exc}"
            diagnostics.append(message)
            attempt.update({
                "error_type": type(exc).__name__,
                "error_message": message
            })
            request_attempts.append(attempt)
            continue

        try:
            response_data = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            message = f"{result_key}: JSONDecodeError {exc.msg}"
            diagnostics.append(message)
            attempt.update({
                "error_type": "JSONDecodeError",
                "error_message": message
            })
            request_attempts.append(attempt)
            continue

        graphql_errors = response_data.get("errors")
        if graphql_errors:
            message = (
                f"{result_key}: GraphQLError "
                f"{json.dumps(graphql_errors, ensure_ascii=False)[:300]}"
            )
            diagnostics.append(message)
            attempt.update({
                "error_type": "GraphQLError",
                "error_message": message
            })

        data = response_data.get("data")
        if not isinstance(data, dict):
            message = (
                f"{result_key}: ResponseStructureError 缺少 data object"
            )
            diagnostics.append(message)
            if not attempt["error_type"]:
                attempt.update({
                    "error_type": "ResponseStructureError",
                    "error_message": message
                })
            request_attempts.append(attempt)
            continue

        items = data.get(result_key)
        if not isinstance(items, list):
            message = (
                f"{result_key}: ResponseStructureError "
                f"{result_key} 不是 list"
            )
            diagnostics.append(message)
            if not attempt["error_type"]:
                attempt.update({
                    "error_type": "ResponseStructureError",
                    "error_message": message
                })
            request_attempts.append(attempt)
            continue

        normalized = []
        for item in items[:limit]:
            submission = _normalize_api_item(
                item,
                accepted_only=result_key == "recentACSubmissions"
            )
            if submission:
                normalized.append(submission)

        if normalized:
            attempt["success"] = True
            request_attempts.append(attempt)
            return {
                "success": True,
                "submissions": normalized,
                "error_type": "",
                "error_message": "",
                "raw_response_preview": last_preview,
                "request_url": endpoint,
                "request_attempts": request_attempts
            }

        message = (
            f"{result_key}: EmptySubmissions 接口返回列表但没有可用记录"
        )
        diagnostics.append(message)
        attempt.update({
            "error_type": "EmptySubmissions",
            "error_message": message
        })
        request_attempts.append(attempt)

    error_message = "；".join(diagnostics) or "未获得可用的提交记录。"
    error_type = "FetchFailed"
    if any("CloudflareChallenge" in item for item in diagnostics):
        error_type = "CloudflareChallenge"
    elif diagnostics and all("EmptySubmissions" in item for item in diagnostics):
        error_type = "EmptySubmissions"
    elif any("GraphQLError" in item for item in diagnostics):
        error_type = "GraphQLError"
    elif any("ResponseStructureError" in item for item in diagnostics):
        error_type = "ResponseStructureError"
    elif any("HTTPError" in item for item in diagnostics):
        error_type = "HTTPError"
    elif any("URLError" in item for item in diagnostics):
        error_type = "URLError"

    return {
        "success": False,
        "submissions": [],
        "error_type": error_type,
        "error_message": error_message,
        "raw_response_preview": last_preview,
        "request_url": endpoint,
        "request_attempts": request_attempts
    }


def save_sync_debug(username, site, fetch_result):
    debug_data = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username": username,
        "site": site,
        "request_url": fetch_result.get("request_url", ""),
        "success": False,
        "error_type": fetch_result.get("error_type", "UnknownError"),
        "error_message": fetch_result.get(
            "error_message",
            "未获得详细错误信息。"
        ),
        "raw_response_preview": fetch_result.get(
            "raw_response_preview",
            ""
        )[:500],
        "request_attempts": fetch_result.get("request_attempts", [])
    }
    _save_json(DEBUG_PATH, debug_data)


def _sync_failure_report(
    username,
    site,
    error_type,
    error_message,
    request_url="",
    raw_response_preview="",
    request_attempts=None,
    fetched=0,
    skipped=0
):
    failure_details = {
        "request_url": request_url,
        "error_type": error_type,
        "error_message": error_message,
        "raw_response_preview": raw_response_preview,
        "request_attempts": request_attempts or []
    }

    try:
        save_sync_debug(username, site, failure_details)
    except OSError:
        pass

    state = _load_json(SYNC_STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}
    try:
        consecutive_failures = int(state.get("consecutive_failures", 0)) + 1
    except (TypeError, ValueError):
        consecutive_failures = 1
    state.update({
        "success": False,
        "username": username,
        "site": site,
        "last_attempt_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_failure_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "consecutive_failures": consecutive_failures,
        "last_error_type": error_type,
        "last_error_message": error_message,
        "fetched": fetched,
        "imported": 0
    })
    try:
        _save_json(SYNC_STATE_PATH, state)
    except OSError:
        pass

    return {
        "enabled": True,
        "success": False,
        "username": username,
        "site": site,
        "fetched": fetched,
        "imported": 0,
        "skipped": skipped,
        "message": "同步失败，已继续使用本地数据。",
        "error_type": error_type,
        "error_message": error_message,
        "consecutive_failures": consecutive_failures,
        "debug_file": "data/leetcode_sync_debug.json"
    }


def get_auto_sync_decision(cooldown_minutes=10):
    state = load_sync_state()
    last_attempt_at = str(state.get("last_attempt_at", "")).strip()
    if not last_attempt_at:
        return {"should_sync": True, "reason": "尚无同步尝试记录"}
    try:
        last_attempt = datetime.strptime(
            last_attempt_at,
            "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        return {"should_sync": True, "reason": "同步时间记录无效"}

    elapsed_seconds = (datetime.now() - last_attempt).total_seconds()
    if elapsed_seconds < max(1, int(cooldown_minutes)) * 60:
        remaining = max(
            1,
            int((cooldown_minutes * 60 - elapsed_seconds + 59) // 60)
        )
        return {
            "should_sync": False,
            "reason": f"距离上次同步较近，约 {remaining} 分钟后再自动尝试"
        }
    return {"should_sync": True, "reason": "已超过自动同步冷却时间"}


def map_submission_to_problem_id(submission):
    if not isinstance(submission, dict):
        return ""

    problem_bank = _load_json(PROBLEM_BANK_PATH, {})
    if not isinstance(problem_bank, dict):
        problem_bank = {}

    title_slug = str(submission.get("title_slug", "")).strip().lower()
    title = str(submission.get("title", "")).strip().lower()

    for problem_id, problem in problem_bank.items():
        if not isinstance(problem, dict):
            continue

        slug = str(
            problem.get("title_slug") or problem.get("slug") or ""
        ).strip().lower()
        if title_slug and slug == title_slug:
            return str(problem_id)

    for problem_id, problem in problem_bank.items():
        if not isinstance(problem, dict):
            continue

        known_titles = {
            str(problem.get("title", "")).strip().lower(),
            str(problem.get("english_title", "")).strip().lower()
        }
        if title and title in known_titles:
            return str(problem_id)

    return title_slug or str(submission.get("title", "")).strip()


def normalize_synced_submission(submission):
    if not isinstance(submission, dict):
        return None

    problem_id = map_submission_to_problem_id(submission)
    if not problem_id:
        return None

    raw_status = str(submission.get("status", "")).strip() or "Unknown"
    status = "AC" if raw_status.lower() == "accepted" else "未通过"
    normalized_status = raw_status.lower().replace(" ", "")
    accepted_values = {"accepted", "ac", "通过", "已通过"}
    status = "AC" if normalized_status in accepted_values else "未通过"
    submit_time = str(submission.get("submit_time", "")).strip()

    try:
        submit_date = str(
            datetime.strptime(submit_time, "%Y-%m-%d %H:%M:%S").date()
        )
    except ValueError:
        submit_date = str(date.today())
        if not submit_time:
            submit_time = f"{submit_date} 00:00:00"

    return {
        "date": submit_date,
        "problem_id": problem_id,
        "status": status,
        "difficulty_feeling": "未知",
        "mistake_type": "未分类",
        "mistake_note": "力扣自动同步",
        "source": "leetcode_auto_sync",
        "raw_status": raw_status,
        "language": str(submission.get("language", "")).strip(),
        "submit_time": submit_time,
        "title": str(submission.get("title", "")).strip(),
        "title_slug": str(submission.get("title_slug", "")).strip()
    }


def get_recent_synced_records(limit=10):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 10

    records = _load_json(RECORDS_PATH, [])
    if not isinstance(records, list):
        return []

    synced_records = [
        record
        for record in records
        if (
            isinstance(record, dict)
            and record.get("source") == "leetcode_auto_sync"
        )
    ]
    synced_records.sort(
        key=lambda record: (
            str(record.get("submit_time", "")),
            str(record.get("date", ""))
        ),
        reverse=True
    )
    return synced_records[:limit]


def format_recent_synced_records(records):
    if not records:
        return "\n".join([
            "===== 最近同步记录 =====",
            "",
            "目前还没有力扣自动同步记录。"
        ])

    lines = ["===== 最近同步记录 =====", ""]

    for index, record in enumerate(records, start=1):
        problem_id = str(record.get("problem_id", "")).strip() or "未知"
        title = str(record.get("title", "")).strip() or "未知题目"
        status = str(record.get("status", "")).strip() or "未知"
        submit_time = (
            str(record.get("submit_time", "")).strip()
            or str(record.get("date", "")).strip()
            or "未知"
        )

        lines.extend([
            f"{index}. {problem_id} {title}",
            f"   状态：{status}",
            f"   时间：{submit_time}",
            ""
        ])

    return "\n".join(lines).rstrip()


def load_sync_state():
    state = _load_json(SYNC_STATE_PATH, {})
    return state if isinstance(state, dict) else {}


def load_sync_debug():
    debug_data = _load_json(DEBUG_PATH, {})
    return debug_data if isinstance(debug_data, dict) else {}


def get_sync_overview(limit=8):
    records = get_recent_synced_records(limit=limit)
    sync_state = load_sync_state()
    debug_data = load_sync_debug()

    mapped_records = []
    unmapped_records = []
    for record in records:
        if not isinstance(record, dict):
            continue
        problem_id = str(record.get("problem_id", "")).strip()
        if problem_id.isdigit():
            mapped_records.append(record)
        else:
            unmapped_records.append(record)

    return {
        "sync_state": sync_state,
        "debug_data": debug_data,
        "recent_records": records,
        "mapped_records": mapped_records,
        "unmapped_records": unmapped_records
    }


def format_sync_overview(overview):
    if not isinstance(overview, dict):
        return "暂时无法读取同步状态。"

    sync_state = overview.get("sync_state", {})
    debug_data = overview.get("debug_data", {})
    records = overview.get("recent_records", [])
    mapped_records = overview.get("mapped_records", [])
    unmapped_records = overview.get("unmapped_records", [])

    last_success_at = str(sync_state.get("last_success_at", "")).strip()
    last_attempt_at = str(sync_state.get("last_attempt_at", "")).strip()
    fetched = sync_state.get("fetched", 0)
    imported = sync_state.get("imported", 0)
    from_cache = bool(sync_state.get("from_cache"))
    cache_time = str(sync_state.get("cache_time", "")).strip()
    sync_source = str(sync_state.get("sync_source", "")).strip()
    consecutive_failures = int(
        sync_state.get("consecutive_failures", 0) or 0
    )
    recent_imported = sync_state.get("recent_imported", [])
    if not isinstance(recent_imported, list):
        recent_imported = []

    lines = [
        "最近尝试时间："
        + (last_attempt_at if last_attempt_at else "暂无"),
        "最近同步时间："
        + (last_success_at if last_success_at else "暂无成功记录"),
        "最近数据来源："
        + (
            "Chrome 扩展缓存"
            if from_cache or sync_source == "browser_cache"
            else "Chrome 实时抓取"
            if sync_source == "browser_fresh"
            else "暂无"
        ),
        f"最近一次读取：{fetched} 条提交",
        f"最近一次新增：{imported} 条记录",
        f"连续失败：{consecutive_failures} 次",
        "",
        f"成功映射题号：{len(mapped_records)} 条",
        f"未映射到题号：{len(unmapped_records)} 条"
    ]

    if from_cache:
        lines.extend([
            "",
            "说明：最近一次使用的是 Chrome 扩展缓存。",
            "如果你今天刚提交过题，请保持力扣页面打开后点击“同步力扣记录”。"
        ])
        if cache_time:
            lines.append(f"缓存时间：{cache_time}")

    if recent_imported:
        lines.extend(["", "最近新增到 LeetCoach："])
        for record in recent_imported[:5]:
            lines.append(
                f"- {record.get('problem_id', '')} "
                f"{record.get('title', '未知题目')} · "
                f"{record.get('status', '未知')} · "
                f"{record.get('submit_time', '未知时间')}"
            )

    if mapped_records:
        lines.extend(["", "最近映射成功的提交："])
        for record in mapped_records[:5]:
            lines.append(
                f"- {record.get('problem_id', '')} "
                f"{record.get('title', '未知题目')} · "
                f"{record.get('submit_time', record.get('date', '未知时间'))}"
            )

    if unmapped_records:
        lines.extend(["", "最近未映射的提交："])
        for record in unmapped_records[:5]:
            lines.append(
                f"- {record.get('problem_id', '') or record.get('title_slug', '')} "
                f"{record.get('title', '未知题目')}"
            )
        lines.append("处理方式：检查 problem_bank.json 是否缺少对应 slug。")

    if not records:
        lines.extend(["", "最近还没有自动同步记录。"])

    if debug_data.get("error_type"):
        lines.extend([
            "",
            "最近一次失败：",
            f"错误类型：{debug_data.get('error_type', 'UnknownError')}",
            f"错误信息：{debug_data.get('error_message', '未获得详细错误信息。')}"
        ])
        error_type = str(debug_data.get("error_type", "")).strip()
        if error_type in {
            "BrowserLoginRequired",
            "BrowserSessionError",
            "BrowserStartError",
            "BrowserBridgeError",
            "BrowserExtensionUnavailable",
            "BrowserExtensionError",
            "ExtensionRuntimeError",
            "SilentBrowserSessionUnavailable"
        }:
            lines.extend([
                "建议：确认 Chrome 扩展已加载，并在正常 Chrome 中打开并登录力扣。"
            ])
        elif error_type == "CloudflareChallenge":
            lines.extend([
                "建议：保持正常 Chrome 中的力扣页面可访问，再重新点击同步。"
            ])
        else:
            lines.extend([
                "建议：先检查用户名、站点配置和最近提交是否能在浏览器里正常看到。"
            ])

    return "\n".join(lines)


def format_sync_brief(overview):
    if not isinstance(overview, dict):
        return "暂时无法读取同步状态。"

    sync_state = overview.get("sync_state", {})
    debug_data = overview.get("debug_data", {})
    records = overview.get("recent_records", [])
    mapped_records = overview.get("mapped_records", [])
    unmapped_records = overview.get("unmapped_records", [])

    last_success_at = str(sync_state.get("last_success_at", "")).strip()
    last_attempt_at = str(sync_state.get("last_attempt_at", "")).strip()
    fetched = sync_state.get("fetched", 0)
    imported = sync_state.get("imported", 0)
    success = bool(sync_state.get("success"))

    lines = ["===== 同步记录 =====", ""]
    if success:
        lines.append(f"最近同步：{last_success_at or '暂无时间'}")
        lines.append(f"读取提交：{fetched} 条")
        lines.append(f"新增记录：{imported} 条")
    else:
        lines.append("最近同步：需要处理")
        if last_attempt_at:
            lines.append(f"最近尝试：{last_attempt_at}")
        error_type = (
            str(sync_state.get("last_error_type", "")).strip()
            or str(debug_data.get("error_type", "")).strip()
        )
        error_message = (
            str(sync_state.get("last_error_message", "")).strip()
            or str(debug_data.get("error_message", "")).strip()
        )
        if error_type:
            lines.append(f"失败类型：{error_type}")
        if error_message:
            lines.append(f"失败原因：{error_message[:120]}")

    if unmapped_records:
        lines.append(f"未映射题目：{len(unmapped_records)} 条")
        lines.append("处理方式：补充 problem_bank.json 中对应题目的 slug。")
    else:
        lines.append(f"已映射题目：{len(mapped_records)} 条")

    if records:
        lines.extend(["", "最近记录："])
        for record in records[:5]:
            problem_id = str(record.get("problem_id", "")).strip() or "未知"
            title = str(record.get("title", "")).strip() or "未知题目"
            status = str(record.get("status", "")).strip() or "未知"
            submit_time = (
                str(record.get("submit_time", "")).strip()
                or str(record.get("date", "")).strip()
                or "未知时间"
            )
            lines.append(f"- {problem_id} {title} · {status} · {submit_time}")
    else:
        lines.extend(["", "最近还没有同步记录。"])

    return "\n".join(lines)


def get_sync_diagnostics(limit=20):
    config = load_leetcode_config()
    username = config.get("leetcode_username", "")
    if not username:
        return {
            "success": False,
            "error_type": "MissingUsername",
            "error_message": "未配置力扣用户名。"
        }
    return diagnose_browser_sync(username, limit=limit)


def format_sync_diagnostics(data):
    if not isinstance(data, dict):
        return "暂时无法读取同步自检结果。"

    if not data.get("success"):
        error_type = data.get("error_type", "UnknownError")
        error_message = data.get("error_message", "未获得详细错误信息。")
        lines = [
            "===== 同步自检 =====",
            "",
            "状态：失败",
            f"错误类型：{error_type}",
            f"错误信息：{error_message}",
            "",
            "建议："
        ]
        if error_type == "LegacyExtensionVersion":
            lines.extend([
                "1. 打开 chrome://extensions",
                "2. 找到 LeetCoach Sync Bridge",
                "3. 点击一次“刷新”",
                "4. 回到 LeetCoach 再次点击“同步自检”"
            ])
            return "\n".join(lines)
        return "\n".join([
            *lines,
            "1. 确认 Chrome 扩展已加载并启用",
            "2. 确认使用的是安装了扩展的那个 Chrome 配置",
            "3. 在正常 Chrome 中打开任意一个 leetcode.cn 页面"
        ])

    tabs_found = int(data.get("leetcode_tabs_found", 0) or 0)
    cache_available = bool(data.get("cache_available"))
    cache_is_today = bool(data.get("cache_is_today"))
    fresh_fetch_success = bool(data.get("fresh_fetch_success"))
    fresh_error_type = (
        data.get("fresh_error_type", "UnknownError")
        or "UnknownError"
    )
    fresh_error_message = (
        data.get("fresh_error_message", "未获得详细错误信息。")
        or "未获得详细错误信息。"
    )

    lines = [
        "===== 同步自检 =====",
        "",
        f"扩展在线：是",
        f"扩展版本：{data.get('extension_version', '未知')}",
        f"扩展看到的总标签页：{data.get('total_tabs_seen', '未知')}",
        f"检测到力扣标签页：{tabs_found} 个",
        f"缓存可用：{'是' if cache_available else '否'}",
        (
            "缓存是否为今天："
            + ("是" if cache_is_today else "否")
            if cache_available
            else "缓存是否为今天：暂无缓存"
        ),
        f"缓存时间：{data.get('cache_time', '') or '未知'}",
        f"缓存提交数：{data.get('cache_submission_count', 0)} 条",
        f"本次直接抓取：{'成功' if fresh_fetch_success else '失败'}"
    ]

    tab_urls = data.get("detected_tab_urls", [])
    if isinstance(tab_urls, list) and tab_urls:
        lines.extend(["", "检测到的力扣页面："])
        for url in tab_urls:
            lines.append(f"- {url}")

    if fresh_fetch_success:
        lines.append(
            f"本次抓取到：{data.get('fresh_result_count', 0)} 条提交"
        )
    else:
        lines.extend([
            "",
            "本次抓取失败：",
            f"错误类型：{fresh_error_type}",
            f"错误信息：{fresh_error_message}"
        ])

    lines.extend(["", "建议："])
    if fresh_error_type == "NoLeetCodeTabOpen" or tabs_found == 0:
        lines.append("1. 先在正常 Chrome 中打开一个 leetcode.cn 页面。")
    else:
        lines.append("1. 保持当前 leetcode.cn 标签页打开，再点击“立即同步”。")

    if not cache_available:
        lines.append("2. 当前还没有缓存，打开力扣页面停留几秒，让扩展先缓存一次。")
    elif not cache_is_today:
        lines.append("2. 当前缓存不是今天的，说明扩展最近没有拿到新提交。")
    else:
        lines.append("2. 当前已有今天的缓存，若仍没同步上，继续检查题号映射。")

    if not fresh_fetch_success:
        lines.append("3. 若页面已打开但抓取仍失败，先在 chrome://extensions 中点击扩展的“刷新”，再检查该 Chrome 是否就是安装扩展并已登录的那个配置。")
    else:
        lines.append("3. 若抓取成功但 LeetCoach 没更新，下一步重点检查 records.json 去重和题号映射。")

    return "\n".join(lines)


def _record_key(record):
    canonical_id = str(record.get("problem_id", "")).strip()
    if record.get("source") == "leetcode_auto_sync":
        mapped_id = map_submission_to_problem_id({
            "problem_id": canonical_id,
            "title": record.get("title", ""),
            "title_slug": record.get("title_slug", "")
        })
        if mapped_id:
            canonical_id = mapped_id
    return (
        canonical_id,
        str(record.get("submit_time", "")).strip(),
        str(record.get("raw_status", "")).strip(),
        str(record.get("source", "")).strip()
    )


def repair_synced_identity_data(records, reviews):
    if not isinstance(records, list) or not isinstance(reviews, list):
        return records, reviews, False

    changed = False
    repaired_records = []
    seen_keys = set()
    for record in records:
        if not isinstance(record, dict):
            repaired_records.append(record)
            continue
        item = dict(record)
        if item.get("source") == "leetcode_auto_sync":
            mapped_id = map_submission_to_problem_id({
                "title": item.get("title", ""),
                "title_slug": item.get("title_slug", "")
            })
            if mapped_id and item.get("problem_id") != mapped_id:
                item["problem_id"] = mapped_id
                changed = True
        key = _record_key(item)
        if (
            item.get("source") == "leetcode_auto_sync"
            and key in seen_keys
        ):
            changed = True
            continue
        seen_keys.add(key)
        repaired_records.append(item)

    problem_bank = _load_json(PROBLEM_BANK_PATH, {})
    slug_to_id = {}
    if isinstance(problem_bank, dict):
        for problem_id, problem in problem_bank.items():
            if not isinstance(problem, dict):
                continue
            slug = str(
                problem.get("slug")
                or problem.get("title_slug")
                or ""
            ).strip()
            if slug:
                slug_to_id[slug] = str(problem_id)

    repaired_reviews = []
    seen_review_keys = set()
    for review in reviews:
        if not isinstance(review, dict):
            repaired_reviews.append(review)
            continue
        item = dict(review)
        problem_id = str(item.get("problem_id", "")).strip()
        mapped_id = slug_to_id.get(problem_id)
        if mapped_id:
            item["problem_id"] = mapped_id
            changed = True
        review_key = (
            str(item.get("problem_id", "")).strip(),
            str(item.get("next_review_date", "")).strip(),
            bool(item.get("done")),
            str(item.get("source", "")).strip(),
            str(item.get("reason", "")).strip()
        )
        if review_key in seen_review_keys:
            changed = True
            continue
        seen_review_keys.add(review_key)
        repaired_reviews.append(item)

    return repaired_records, repaired_reviews, changed


def _sync_review(reviews, record, records):
    reason = f"力扣自动同步：{record['raw_status']}"
    upsert_review_task(
        reviews=reviews,
        record=record,
        records=records,
        reason=reason,
        source="leetcode_auto_sync"
    )


def sync_leetcode_submissions(interactive=False):
    config = load_leetcode_config()
    username = config.get("leetcode_username", "")
    site = config.get("site", "leetcode.cn")
    limit = config.get("sync_limit", 20)

    if not username:
        return {
            "enabled": False,
            "success": False,
            "username": "",
            "site": site,
            "fetched": 0,
            "imported": 0,
            "skipped": 0,
            "message": "未配置力扣用户名，跳过自动同步。"
        }

    fetch_result = fetch_recent_submissions(
        username,
        site,
        limit,
        interactive=interactive,
        allow_local_cache=True
    )
    if not fetch_result.get("success"):
        return _sync_failure_report(
            username=username,
            site=site,
            error_type=fetch_result.get("error_type", "UnknownError"),
            error_message=fetch_result.get(
                "error_message",
                "未获得详细错误信息。"
            ),
            request_url=fetch_result.get("request_url", ""),
            raw_response_preview=fetch_result.get(
                "raw_response_preview",
                ""
            ),
            request_attempts=fetch_result.get("request_attempts", [])
        )

    submissions = fetch_result.get("submissions", [])
    submissions = sorted(
        submissions,
        key=lambda item: str(item.get("submit_time", ""))
        if isinstance(item, dict)
        else ""
    )
    records = _load_json(RECORDS_PATH, [])
    reviews = _load_json(REVIEWS_PATH, [])
    if not isinstance(records, list) or not isinstance(reviews, list):
        return _sync_failure_report(
            username=username,
            site=site,
            error_type="LocalDataError",
            error_message=(
                "data/records.json 或 data/reviews.json 的顶层结构不是列表。"
            ),
            request_url=fetch_result.get("request_url", ""),
            raw_response_preview=fetch_result.get(
                "raw_response_preview",
                ""
            ),
            request_attempts=fetch_result.get("request_attempts", []),
            fetched=len(submissions),
            skipped=len(submissions)
        )

    records, reviews, identity_repaired = repair_synced_identity_data(
        records,
        reviews
    )
    existing_keys = {
        _record_key(record)
        for record in records
        if isinstance(record, dict)
    }
    imported = 0
    skipped = 0
    imported_records = []

    for submission in submissions:
        record = normalize_synced_submission(submission)
        if record is None:
            skipped += 1
            continue

        key = _record_key(record)
        if key in existing_keys:
            skipped += 1
            continue

        records.append(record)
        existing_keys.add(key)
        _sync_review(reviews, record, records)
        imported += 1
        imported_records.append(record)

    reviews_changed = reconcile_review_tasks(reviews, records)
    try:
        if imported or identity_repaired:
            _save_json(RECORDS_PATH, records)
        if imported or reviews_changed or identity_repaired:
            _save_json(REVIEWS_PATH, reviews)
    except OSError as exc:
        return _sync_failure_report(
            username=username,
            site=site,
            error_type="LocalWriteError",
            error_message=f"写入本地 JSON 文件失败：{exc}",
            request_url=fetch_result.get("request_url", ""),
            raw_response_preview=fetch_result.get(
                "raw_response_preview",
                ""
            ),
            request_attempts=fetch_result.get("request_attempts", []),
            fetched=len(submissions),
            skipped=len(submissions)
        )

    try:
        refresh_learning_analysis()
    except Exception:
        pass

    from_cache = bool(fetch_result.get("from_cache"))
    cache_time = str(fetch_result.get("cache_time", ""))
    cache_source = str(fetch_result.get("cache_source", "browser"))

    if not from_cache:
        try:
            _save_json(SYNC_STATE_PATH, {
                "success": True,
                "username": username,
                "site": site,
                "last_attempt_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "last_success_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "fetched": len(submissions),
                "imported": imported,
                "skipped": skipped,
                "from_cache": False,
                "sync_source": fetch_result.get(
                    "sync_source",
                    "browser_fresh"
                ),
                "consecutive_failures": 0,
                "last_error_type": "",
                "last_error_message": "",
                "recent_imported": [
                    {
                        "problem_id": item.get("problem_id", ""),
                        "title": item.get("title", ""),
                        "status": item.get("status", ""),
                        "submit_time": item.get("submit_time", "")
                    }
                    for item in imported_records[-10:]
                ]
            })
        except OSError:
            pass
    else:
        state = _load_json(SYNC_STATE_PATH, {})
        if not isinstance(state, dict):
            state = {}
        state.update({
            "success": True,
            "username": username,
            "site": site,
            "last_attempt_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "last_cache_read_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "fetched": len(submissions),
            "imported": imported,
            "skipped": skipped,
            "from_cache": True,
            "sync_source": fetch_result.get("sync_source", "browser_cache"),
            "cache_source": cache_source,
            "cache_time": cache_time,
            "last_error_type": "",
            "last_error_message": ""
        })
        try:
            _save_json(SYNC_STATE_PATH, state)
        except OSError:
            pass

    return {
        "enabled": True,
        "success": True,
        "username": username,
        "site": site,
        "fetched": len(submissions),
        "imported": imported,
        "skipped": skipped,
        "recent_imported": imported_records[-10:],
        "from_cache": from_cache,
        "sync_source": fetch_result.get(
            "sync_source",
            "browser_cache" if from_cache else "browser_fresh"
        ),
        "cache_source": cache_source,
        "cache_time": cache_time,
        "message": (
            "已读取最近同步缓存。"
            if from_cache
            else "同步完成。"
        )
    }


def format_sync_report(report):
    if not report.get("enabled"):
        return "\n".join([
            "===== 力扣自动同步 =====",
            "",
            "未配置力扣用户名。",
            "请打开 config/leetcode_config.json 填写 leetcode_username。"
        ])

    if report.get("success") and report.get("from_cache"):
        status = "已读取最近同步缓存"
    elif report.get("success"):
        status = "同步完成"
    else:
        status = "同步失败，已继续使用本地数据。"
    lines = [
        "===== 力扣自动同步 =====",
        "",
        f"用户：{report.get('username', '')}",
        f"站点：{report.get('site', '')}",
        f"状态：{status}"
    ]

    if report.get("success"):
        lines.extend([
            "",
            f"读取记录：{report.get('fetched', 0)} 条",
            f"新增记录：{report.get('imported', 0)} 条",
            f"跳过重复：{report.get('skipped', 0)} 条"
        ])
        if report.get("from_cache"):
            cache_time = report.get("cache_time") or "未知"
            cache_source = (
                "浏览器扩展缓存"
                if report.get("cache_source") == "browser"
                else "本地最近同步记录"
            )
            lines.extend([
                f"缓存来源：{cache_source}",
                f"最近实时同步：{cache_time}",
                "",
                "说明：当前没有可响应的力扣页面，未发现新的提交记录。"
            ])
    else:
        lines.extend([
            "",
            f"错误类型：{report.get('error_type', 'UnknownError')}",
            f"错误信息：{report.get('error_message', '未获得详细错误信息。')}",
            (
                f"调试文件："
                f"{report.get('debug_file', 'data/leetcode_sync_debug.json')}"
            ),
            "请求尝试明细：已写入调试文件的 request_attempts 字段",
        ])

        if report.get("error_type") in {
            "BrowserLoginRequired",
            "BrowserSessionError",
            "BrowserStartError",
            "BrowserBridgeError",
            "BrowserExtensionUnavailable",
            "BrowserExtensionError",
            "ExtensionRuntimeError"
        }:
            lines.extend([
                "",
                "原因：",
                "Chrome 同步组件尚未连接，或正常 Chrome 中尚未登录力扣。",
                "",
                "处理方式：",
                "1. 在“数据同步”页面点击“安装 Chrome 同步组件”。",
                "2. 在 chrome://extensions 中加载 extensions/chrome 目录。",
                "3. 在正常 Chrome 中登录力扣后再次同步。",
                "LeetCoach 不读取或记录 Cookie。"
            ])
        elif report.get("error_type") == "CloudflareChallenge":
            lines.extend([
                "",
                "原因：",
                "力扣公开接口要求浏览器验证。",
                "请更新到浏览器会话同步版本后重试。"
            ])
        else:
            lines.extend([
                "",
                "提示：",
                "请确认：",
                "1. leetcode_username 是否为主页 URL 中 /u/ 后面的用户名",
                "2. site 是否为 leetcode.cn",
                "3. 最近提交记录是否公开",
                "4. GraphQL 接口是否发生变化"
            ])

    return "\n".join(lines)


if __name__ == "__main__":
    report = sync_leetcode_submissions()
    print(format_sync_report(report))
