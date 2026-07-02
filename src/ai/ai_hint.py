import json
import time
from datetime import datetime
from pathlib import Path

from llm.llm_logger import log_llm_call
from llm.prompt_loader import load_prompt_template, render_prompt


from app_paths import BASE_DIR, SCHEMAS_DIR
HINT_LOG_PATH = BASE_DIR / "data" / "hint_logs.json"
HINT_SCHEMA_PATH = SCHEMAS_DIR / "hint_schema.json"
PROMPT_VERSION = "ai_hint_v1"
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"


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

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_hint_log(problem_id, user_question, hint_level, hint_dict):
    hint_logs = load_json(HINT_LOG_PATH, [])
    if not isinstance(hint_logs, list):
        hint_logs = []

    hint_log = {
        "date": str(datetime.now().date()),
        "problem_id": problem_id,
        "user_question": user_question,
        "hint_level": hint_level,
        "hint_title": hint_dict.get("hint_title", ""),
        "hint_content": hint_dict.get("hint_content", ""),
        "next_question": hint_dict.get("next_question", ""),
        "do_not_show_code": hint_dict.get("do_not_show_code", True)
    }

    hint_logs.append(hint_log)
    save_json(HINT_LOG_PATH, hint_logs)


def parse_hint_response(raw_text):
    try:
        hint_dict = json.loads(raw_text)
        if isinstance(hint_dict, dict):
            hint_dict["do_not_show_code"] = True
            return hint_dict
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "problem_id": "",
        "hint_level": "",
        "hint_title": "AI 提示",
        "hint_content": raw_text,
        "do_not_show_code": True,
        "next_question": "你可以尝试根据这个提示继续思考。"
    }


def format_hint(hint_dict):
    depth_labels = {
        "1": "方向提示",
        "2": "关键观察",
        "3": "结构化思路"
    }
    hint_level = str(hint_dict.get("hint_level", ""))
    return "\n".join([
        "===== AI 智能提示 =====",
        "",
        f"题号：{hint_dict.get('problem_id', '')}",
        f"提示方式：{depth_labels.get(hint_level, '自动判断')}",
        f"标题：{hint_dict.get('hint_title', 'AI 提示')}",
        "",
        "提示：",
        str(hint_dict.get("hint_content", "")),
        "",
        "继续思考：",
        str(hint_dict.get(
            "next_question",
            "你可以尝试根据这个提示继续思考。"
        ))
    ])


def _clean_problem_id(problem_id):
    value = str(problem_id or "")
    for prefix in ("题号：", "题号:", "题号"):
        value = value.replace(prefix, "")
    return value.strip()


def _problem_context(problem_id):
    problem_id = _clean_problem_id(problem_id)
    records = load_json(RECORDS_PATH, [])
    reviews = load_json(REVIEWS_PATH, [])
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    if not isinstance(records, list):
        records = []
    if not isinstance(reviews, list):
        reviews = []
    if not isinstance(problem_bank, dict):
        problem_bank = {}

    related_records = [
        record for record in records
        if (
            isinstance(record, dict)
            and _clean_problem_id(record.get("problem_id")) == problem_id
        )
    ]
    related_reviews = [
        review for review in reviews
        if (
            isinstance(review, dict)
            and _clean_problem_id(review.get("problem_id")) == problem_id
        )
    ]
    problem = problem_bank.get(problem_id, {})
    if not isinstance(problem, dict):
        problem = {}

    statuses = [str(item.get("status", "")) for item in related_records]
    notes = [
        str(item.get("mistake_note", "")).strip()
        for item in related_records
        if str(item.get("mistake_note", "")).strip()
        and str(item.get("mistake_note", "")).strip() not in {
            "力扣自动同步",
            "GUI快捷标记完成"
        }
    ]
    latest_review = related_reviews[-1] if related_reviews else {}
    return {
        "problem": {
            "problem_id": problem_id,
            "title": problem.get("title", ""),
            "difficulty": problem.get("difficulty", ""),
            "topics": problem.get("topics", []),
            "key_points": problem.get("key_points", [])
        },
        "attempt_count": len(related_records),
        "status_history": statuses[-5:],
        "failed_count": sum(1 for status in statuses if status == "未通过"),
        "assisted_count": sum(
            1 for status in statuses if status.replace(" ", "") == "看提示后AC"
        ),
        "recent_notes": notes[-3:],
        "latest_review_mastery": latest_review.get("mastery_label", ""),
        "latest_review_result": latest_review.get("mastery_result", "")
    }


def infer_hint_level(problem_id, user_question):
    context = _problem_context(problem_id)
    question = str(user_question or "")
    strong_signals = (
        "完全不会",
        "没思路",
        "不知道",
        "写不出",
        "卡住",
        "报错",
        "bug"
    )
    if (
        context["failed_count"] >= 2
        or context["latest_review_result"] == "not_mastered"
        or any(signal in question for signal in strong_signals)
    ):
        return "3"
    if (
        context["assisted_count"] > 0
        or context["attempt_count"] > 0
        or "为什么" in question
        or "怎么" in question
    ):
        return "2"
    return "1"


def generate_hint(problem_id, user_question, hint_level=None):
    from llm_client import LLMClient

    if hint_level in (None, "", "auto", "自动"):
        hint_level = infer_hint_level(problem_id, user_question)
    hint_level = str(hint_level)
    learning_context = _problem_context(problem_id)

    level_instructions = {
        "1": "只给思路方向，不要给关键步骤。",
        "2": "给出关键观察和状态转移思路，但不要给完整代码。",
        "3": "给出伪代码级提示，但不要给完整可提交代码。"
    }
    level_instruction = level_instructions.get(
        str(hint_level),
        level_instructions["1"]
    )

    prompt_template = load_prompt_template(PROMPT_VERSION)
    user_prompt = render_prompt(
        prompt_template,
        {
            "problem_id": problem_id,
            "user_question": user_question,
            "hint_level": hint_level,
            "level_instruction": level_instruction,
            "learning_context": json.dumps(
                learning_context,
                ensure_ascii=False,
                indent=2
            ),
            "output_schema": json.dumps(
                load_json(HINT_SCHEMA_PATH, {}),
                ensure_ascii=False,
                indent=2
            )
        }
    )
    system_prompt = "你是 LeetCoach 的分层提示模块，只输出严格 JSON。"

    start_time = time.time()
    raw_text = ""
    model_name = ""
    client = LLMClient()
    model_name = client.model
    try:
        raw_text = client.chat(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.5
        )
    except Exception as error:
        try:
            log_llm_call({
                "task": "ai_hint",
                "prompt_version": PROMPT_VERSION,
                "model": model_name,
                "input_summary": {
                    "problem_id": problem_id,
                    "hint_level": hint_level
                },
                "raw_output": raw_text,
                "parsed_success": False,
                "schema_valid": False,
                "fallback_used": True,
                "error_message": str(error),
                "latency_seconds": round(time.time() - start_time, 3)
            })
        except Exception:
            pass
        raise
    hint_dict = parse_hint_response(raw_text)
    try:
        log_llm_call({
            "task": "ai_hint",
            "prompt_version": PROMPT_VERSION,
            "model": model_name,
            "input_summary": {
                "problem_id": problem_id,
                "hint_level": hint_level
            },
            "raw_output": raw_text,
            "parsed_success": not hint_dict.get("parse_fallback", False),
            "schema_valid": bool(hint_dict.get("do_not_show_code", True)),
            "fallback_used": bool(hint_dict.get("parse_fallback", False)),
            "error_message": "",
            "latency_seconds": round(time.time() - start_time, 3)
        })
    except Exception:
        pass

    try:
        save_hint_log(problem_id, user_question, hint_level, hint_dict)
    except Exception:
        print("提示记录保存失败，但 AI 提示已生成。")

    return hint_dict
