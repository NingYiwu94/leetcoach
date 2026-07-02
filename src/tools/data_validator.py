import json
from pathlib import Path


from app_paths import BASE_DIR
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"

RECORDS_PATH = DATA_DIR / "records.json"
REVIEWS_PATH = DATA_DIR / "reviews.json"
HINT_LOGS_PATH = DATA_DIR / "hint_logs.json"
AI_SOLUTION_NOTES_PATH = DATA_DIR / "ai_solution_notes.json"
AGENT_MEMORY_PATH = DATA_DIR / "agent_memory.json"
AI_WEEKLY_REVIEWS_PATH = DATA_DIR / "ai_weekly_reviews.json"
AI_NEXT_PLAN_PATH = DATA_DIR / "ai_next_plan_draft.json"
LEETCODE_CONFIG_PATH = CONFIG_DIR / "leetcode_config.json"
WEEK_PLAN_NEXT_PATH = CONFIG_DIR / "week_plan_next.json"
PLAN_ARCHIVE_DIR = CONFIG_DIR / "plan_archive"
PLAN_REVIEW_PATH = CONFIG_DIR / "plan_review_state.json"
LEARNING_ANALYSIS_PATH = DATA_DIR / "learning_analysis.json"
LEETCODE_SYNC_STATE_PATH = DATA_DIR / "leetcode_sync_state.json"
PLAN_TASK_STATE_PATH = DATA_DIR / "plan_task_state.json"
LLM_CALL_LOGS_PATH = DATA_DIR / "llm_call_logs.json"
LLM_EVAL_RESULTS_PATH = DATA_DIR / "llm_eval_results.json"

VALID_STATUSES = {"AC", "看提示后AC", "未通过"}
VALID_REVIEW_MASTERY = {
    "independent",
    "assisted",
    "not_mastered"
}


def _validate_file(path, required_fields, compatible_fields=None):
    compatible_fields = compatible_fields or {}
    result = {
        "file_name": path.name,
        "count": 0,
        "errors": [],
        "warnings": []
    }

    if not path.exists():
        result["errors"].append(f"{path.name} 文件不存在")
        return result

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        result["errors"].append(f"{path.name} JSON 格式损坏")
        return result
    except OSError as error:
        result["errors"].append(f"{path.name} 无法读取：{error}")
        return result

    if not isinstance(data, list):
        result["errors"].append(f"{path.name} 顶层结构应为 list")
        return result

    result["count"] = len(data)

    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            result["errors"].append(f"{path.name} 第 {index} 条不是对象")
            continue

        for field in required_fields:
            if field not in item:
                result["warnings"].append(
                    f"{path.name} 第 {index} 条缺少核心字段 {field}"
                )

        for field, fallback in compatible_fields.items():
            if field not in item:
                result["warnings"].append(
                    f"{path.name} 第 {index} 条缺少 {field}，"
                    f"已兼容为“{fallback}”"
                )

    return result


def validate_records():
    result = _validate_file(
        RECORDS_PATH,
        required_fields={"date", "problem_id", "status"},
        compatible_fields={
            "difficulty_feeling": "未知",
            "mistake_type": "未分类",
            "mistake_note": "空内容"
        }
    )

    if result["errors"]:
        return result

    try:
        with open(RECORDS_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
    except (OSError, json.JSONDecodeError):
        return result

    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict) or "status" not in record:
            continue

        status = str(record["status"]).replace(" ", "")
        if status not in VALID_STATUSES:
            result["warnings"].append(
                f"records.json 第 {index} 条 status 为“{record['status']}”，"
                "不在合法值 AC、看提示后AC、未通过 中"
            )

    return result


def validate_reviews():
    result = _validate_file(
        REVIEWS_PATH,
        required_fields={"problem_id", "next_review_date", "reason", "done"}
    )
    if not REVIEWS_PATH.exists():
        return result

    try:
        with open(REVIEWS_PATH, "r", encoding="utf-8") as f:
            reviews = json.load(f)
    except (OSError, json.JSONDecodeError):
        return result
    if not isinstance(reviews, list):
        return result

    active_problem_ids = set()
    for index, review in enumerate(reviews, start=1):
        if not isinstance(review, dict):
            continue
        review_round = review.get("review_round")
        if review_round is not None:
            try:
                if int(review_round) < 1:
                    raise ValueError
            except (TypeError, ValueError):
                result["warnings"].append(
                    f"reviews.json 第 {index} 条 review_round 应为正整数"
                )

        for field in ("mastery_result", "previous_mastery_result"):
            value = review.get(field)
            if value and value not in VALID_REVIEW_MASTERY:
                result["warnings"].append(
                    f"reviews.json 第 {index} 条 {field} 为“{value}”，"
                    "应为 independent、assisted 或 not_mastered"
                )

        if review.get("done"):
            continue
        problem_id = str(review.get("problem_id", "")).strip()
        if problem_id in active_problem_ids:
            result["warnings"].append(
                f"reviews.json 题号 {problem_id} 存在多个待完成复习任务"
            )
        active_problem_ids.add(problem_id)
    return result


def validate_hint_logs():
    return _validate_file(
        HINT_LOGS_PATH,
        required_fields={
            "date",
            "problem_id",
            "user_question",
            "hint_level",
            "hint_title",
            "hint_content",
            "next_question",
            "do_not_show_code"
        }
    )


def validate_ai_solution_notes():
    if not AI_SOLUTION_NOTES_PATH.exists():
        return {
            "file_name": AI_SOLUTION_NOTES_PATH.name,
            "count": 0,
            "errors": [],
            "warnings": ["ai_solution_notes.json 文件不存在，生成题解后会自动创建"]
        }

    return _validate_file(
        AI_SOLUTION_NOTES_PATH,
        required_fields={
            "problem_id",
            "idea",
            "language",
            "code",
            "common_mistakes",
            "time_complexity",
            "generated_at",
            "source"
        },
        compatible_fields={
            "problem_title": "空标题"
        }
    )


def validate_agent_memory():
    result = _validate_file(
        AGENT_MEMORY_PATH,
        required_fields={
            "date",
            "stage",
            "progress_status",
            "main_problem",
            "action_plan"
        }
    )
    if not AGENT_MEMORY_PATH.exists():
        return result

    try:
        with open(AGENT_MEMORY_PATH, "r", encoding="utf-8") as f:
            memory = json.load(f)
    except (OSError, json.JSONDecodeError):
        return result

    if not isinstance(memory, list):
        return result

    seen_dates = set()
    for index, item in enumerate(memory, start=1):
        if not isinstance(item, dict):
            continue
        memory_date = str(item.get("date", "")).strip()
        if memory_date and memory_date in seen_dates:
            result["warnings"].append(
                f"agent_memory.json 第 {index} 条日期 {memory_date} "
                "重复，建议运行记忆整理"
            )
        seen_dates.add(memory_date)

        if "run_count" not in item:
            result["warnings"].append(
                f"agent_memory.json 第 {index} 条缺少 run_count，"
                "旧数据会自动兼容"
            )
    return result


def validate_plan_task_state():
    if not PLAN_TASK_STATE_PATH.exists():
        return {
            "file_name": PLAN_TASK_STATE_PATH.name,
            "count": 0,
            "errors": [],
            "warnings": [
                "plan_task_state.json 文件不存在，完成复习日或总结日后会自动创建"
            ]
        }
    result = _validate_file(
        PLAN_TASK_STATE_PATH,
        required_fields={
            "plan_key",
            "task_id",
            "day_index",
            "task_type",
            "completed",
            "completed_at"
        }
    )
    if result["errors"]:
        return result
    try:
        with open(PLAN_TASK_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return result

    for index, item in enumerate(state, start=1):
        if not isinstance(item, dict):
            continue
        summary = item.get("stage_summary")
        if summary is None:
            continue
        if not isinstance(summary, dict):
            result["warnings"].append(
                f"plan_task_state.json 第 {index} 条 stage_summary 应为 object"
            )
            continue
        for field in {
            "generated_at",
            "week",
            "planned_count",
            "completed_count",
            "mastery",
            "conclusion",
            "recommendation"
        }:
            if field not in summary:
                result["warnings"].append(
                    f"plan_task_state.json 第 {index} 条 stage_summary "
                    f"缺少字段 {field}"
                )
    return result


def validate_ai_weekly_reviews():
    if not AI_WEEKLY_REVIEWS_PATH.exists():
        return {
            "file_name": AI_WEEKLY_REVIEWS_PATH.name,
            "count": 0,
            "errors": [],
            "warnings": ["ai_weekly_reviews.json 文件不存在，生成后会自动创建"]
        }

    return _validate_file(
        AI_WEEKLY_REVIEWS_PATH,
        required_fields={
            "date",
            "week",
            "summary_title",
            "overall_progress",
            "main_weaknesses",
            "representative_problems",
            "learning_feedback",
            "next_week_focus",
            "recommended_actions"
        }
    )


def validate_ai_next_plan_draft():
    result = {
        "file_name": AI_NEXT_PLAN_PATH.name,
        "count": 0,
        "errors": [],
        "warnings": []
    }

    if not AI_NEXT_PLAN_PATH.exists():
        result["warnings"].append(
            "ai_next_plan_draft.json 文件不存在，生成后会自动创建"
        )
        return result

    try:
        with open(AI_NEXT_PLAN_PATH, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except json.JSONDecodeError:
        result["errors"].append("ai_next_plan_draft.json JSON 格式损坏")
        return result
    except OSError as error:
        result["errors"].append(
            f"ai_next_plan_draft.json 无法读取：{error}"
        )
        return result

    if not isinstance(plan, dict):
        result["errors"].append("ai_next_plan_draft.json 顶层结构应为 object")
        return result

    result["count"] = 1
    for field in {"plan_title", "strategy", "days", "reason"}:
        if field not in plan:
            result["warnings"].append(
                f"ai_next_plan_draft.json 缺少核心字段 {field}"
            )

    days = plan.get("days")
    if "days" in plan and not isinstance(days, dict):
        result["warnings"].append(
            "ai_next_plan_draft.json 的 days 应为 object"
        )

    return result


def validate_leetcode_config():
    result = {
        "file_name": "leetcode_config.json",
        "count": 0,
        "errors": [],
        "warnings": []
    }

    if not LEETCODE_CONFIG_PATH.exists():
        result["warnings"].append(
            "config/leetcode_config.json 文件不存在，自动同步将跳过"
        )
        return result

    try:
        with open(LEETCODE_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError:
        result["warnings"].append(
            "config/leetcode_config.json JSON 格式损坏，自动同步将跳过"
        )
        return result
    except OSError as error:
        result["warnings"].append(
            f"config/leetcode_config.json 无法读取：{error}"
        )
        return result

    if not isinstance(config, dict):
        result["warnings"].append(
            "config/leetcode_config.json 顶层结构应为 object"
        )
        return result

    result["count"] = 1
    for field in {
        "leetcode_username",
        "site",
        "auto_sync_on_start",
        "sync_limit"
    }:
        if field not in config:
            result["warnings"].append(
                f"config/leetcode_config.json 缺少字段 {field}"
            )

    if config.get("site") not in {"leetcode.cn", "leetcode.com"}:
        result["warnings"].append(
            "config/leetcode_config.json 的 site 应为 "
            "leetcode.cn 或 leetcode.com"
        )

    return result


def validate_week_plan_next():
    result = {
        "file_name": WEEK_PLAN_NEXT_PATH.name,
        "count": 0,
        "errors": [],
        "warnings": []
    }

    if not WEEK_PLAN_NEXT_PATH.exists():
        result["warnings"].append(
            "config/week_plan_next.json 文件不存在，生成后会自动创建"
        )
        return result

    try:
        with open(WEEK_PLAN_NEXT_PATH, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except json.JSONDecodeError:
        result["errors"].append("week_plan_next.json JSON 格式损坏")
        return result
    except OSError as error:
        result["errors"].append(
            f"week_plan_next.json 无法读取：{error}"
        )
        return result

    if not isinstance(plan, dict):
        result["errors"].append("week_plan_next.json 顶层结构应为 object")
        return result

    result["count"] = 1
    days = plan.get("days")
    if not isinstance(days, dict):
        result["warnings"].append(
            "week_plan_next.json 的 days 应为 object"
        )
        return result

    for day_index in range(1, 8):
        day_key = str(day_index)
        day = days.get(day_key)
        if not isinstance(day, dict):
            result["warnings"].append(
                f"week_plan_next.json 缺少有效的 Day {day_index}"
            )
            continue
        if not isinstance(day.get("problems"), list):
            result["warnings"].append(
                f"week_plan_next.json Day {day_index} 的 problems 应为 list"
            )

    return result


def validate_learning_analysis():
    result = {
        "file_name": LEARNING_ANALYSIS_PATH.name,
        "count": 0,
        "errors": [],
        "warnings": []
    }
    if not LEARNING_ANALYSIS_PATH.exists():
        result["warnings"].append(
            "learning_analysis.json 文件不存在，分析后会自动创建"
        )
        return result

    try:
        with open(LEARNING_ANALYSIS_PATH, "r", encoding="utf-8") as f:
            analysis = json.load(f)
    except json.JSONDecodeError:
        result["errors"].append("learning_analysis.json JSON 格式损坏")
        return result
    except OSError as error:
        result["errors"].append(
            f"learning_analysis.json 无法读取：{error}"
        )
        return result

    if not isinstance(analysis, dict):
        result["errors"].append(
            "learning_analysis.json 顶层结构应为 object"
        )
        return result

    result["count"] = 1
    for field in {
        "generated_at",
        "main_weakness",
        "learning_status",
        "risky_problems",
        "recommended_actions"
    }:
        if field not in analysis:
            result["warnings"].append(
                f"learning_analysis.json 缺少字段 {field}"
            )
    return result


def validate_plan_archives():
    result = {
        "file_name": "config/plan_archive/",
        "count": 0,
        "errors": [],
        "warnings": []
    }
    if not PLAN_ARCHIVE_DIR.exists():
        return result

    for path in PLAN_ARCHIVE_DIR.glob("week_plan_week_*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                plan = json.load(f)
        except json.JSONDecodeError:
            result["errors"].append(f"{path.name} JSON 格式损坏")
            continue
        except OSError as error:
            result["errors"].append(f"{path.name} 无法读取：{error}")
            continue

        result["count"] += 1
        if not isinstance(plan, dict):
            result["errors"].append(f"{path.name} 顶层结构应为 object")
            continue

        for field in {
            "week",
            "title",
            "start_date",
            "days",
            "activated_at",
            "archive_status"
        }:
            if field not in plan:
                result["warnings"].append(
                    f"{path.name} 缺少字段 {field}"
                )

    return result


def validate_plan_review_state():
    result = {
        "file_name": PLAN_REVIEW_PATH.name,
        "count": 0,
        "errors": [],
        "warnings": []
    }
    if not PLAN_REVIEW_PATH.exists():
        return result

    try:
        with open(PLAN_REVIEW_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except json.JSONDecodeError:
        result["errors"].append("plan_review_state.json JSON 格式损坏")
        return result
    except OSError as error:
        result["errors"].append(
            f"plan_review_state.json 无法读取：{error}"
        )
        return result

    if not isinstance(state, dict):
        result["errors"].append(
            "plan_review_state.json 顶层结构应为 object"
        )
        return result

    result["count"] = 1
    for field in {
        "draft_identity",
        "draft_week",
        "snoozed_until",
        "updated_at"
    }:
        if field not in state:
            result["warnings"].append(
                f"plan_review_state.json 缺少字段 {field}"
            )
    return result


def validate_leetcode_sync_state():
    result = {
        "file_name": LEETCODE_SYNC_STATE_PATH.name,
        "count": 0,
        "errors": [],
        "warnings": []
    }
    if not LEETCODE_SYNC_STATE_PATH.exists():
        return result

    try:
        with open(LEETCODE_SYNC_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except json.JSONDecodeError:
        result["errors"].append("leetcode_sync_state.json JSON 格式损坏")
        return result
    except OSError as error:
        result["errors"].append(
            f"leetcode_sync_state.json 无法读取：{error}"
        )
        return result

    if not isinstance(state, dict):
        result["errors"].append(
            "leetcode_sync_state.json 顶层结构应为 object"
        )
        return result

    result["count"] = 1
    for field in {"success", "username", "site", "last_success_at"}:
        if field not in state:
            result["warnings"].append(
                f"leetcode_sync_state.json 缺少字段 {field}"
            )
    return result


def validate_llm_call_logs():
    if not LLM_CALL_LOGS_PATH.exists():
        return {
            "file_name": LLM_CALL_LOGS_PATH.name,
            "count": 0,
            "errors": [],
            "warnings": ["llm_call_logs.json 文件不存在，首次 LLM 调用后会自动创建"]
        }

    return _validate_file(
        LLM_CALL_LOGS_PATH,
        required_fields={
            "timestamp",
            "task",
            "prompt_version",
            "model",
            "parsed_success",
            "schema_valid",
            "fallback_used",
            "latency_seconds"
        },
        compatible_fields={
            "input_summary": "空摘要",
            "error_message": "空错误信息"
        }
    )


def validate_llm_eval_results():
    if not LLM_EVAL_RESULTS_PATH.exists():
        return {
            "file_name": LLM_EVAL_RESULTS_PATH.name,
            "count": 0,
            "errors": [],
            "warnings": ["llm_eval_results.json 文件不存在，首次 AI 计划评估后会自动创建"]
        }

    return _validate_file(
        LLM_EVAL_RESULTS_PATH,
        required_fields={
            "timestamp",
            "task",
            "score",
            "checks",
            "issues"
        }
    )


def run_all_validations():
    results = [
        validate_records(),
        validate_reviews(),
        validate_hint_logs(),
        validate_ai_solution_notes(),
        validate_agent_memory(),
        validate_ai_weekly_reviews(),
        validate_ai_next_plan_draft(),
        validate_leetcode_config(),
        validate_week_plan_next(),
        validate_plan_archives(),
        validate_plan_review_state(),
        validate_leetcode_sync_state(),
        validate_plan_task_state(),
        validate_learning_analysis(),
        validate_llm_call_logs(),
        validate_llm_eval_results()
    ]

    lines = ["===== 数据校验报告 =====", ""]
    issues = []

    for result in results:
        if result["errors"]:
            lines.append(f"{result['file_name']}：失败")
        elif result["warnings"]:
            lines.append(
                f"{result['file_name']}：通过，共 {result['count']} 条记录"
                "（有 warning）"
            )
        else:
            lines.append(
                f"{result['file_name']}：通过，共 {result['count']} 条记录"
            )

        issues.extend(result["errors"])
        issues.extend(result["warnings"])

    lines.extend(["", "发现问题："])
    if issues:
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- 未发现问题")

    return "\n".join(lines)


if __name__ == "__main__":
    print(run_all_validations())
