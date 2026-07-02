import json
import time
from datetime import date
from pathlib import Path

from llm.llm_logger import log_llm_call
from llm.prompt_loader import load_prompt_template, render_prompt
from core.recorder import generate_week_summary


from app_paths import BASE_DIR, SCHEMAS_DIR
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
AGENT_MEMORY_PATH = BASE_DIR / "data" / "agent_memory.json"
PLAN_PATH = BASE_DIR / "config" / "week_plan.json"
AI_WEEKLY_REVIEWS_PATH = BASE_DIR / "data" / "ai_weekly_reviews.json"
WEEKLY_REVIEW_SCHEMA_PATH = SCHEMAS_DIR / "weekly_review_schema.json"
PROMPT_VERSION = "ai_weekly_review_v1"


def load_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def clean_problem_id(problem_id):
    problem_id = str(problem_id)
    problem_id = problem_id.replace("题号：", "")
    problem_id = problem_id.replace("题号:", "")
    problem_id = problem_id.replace("题号", "")
    return problem_id.strip()


def save_ai_weekly_review(review_dict):
    reviews = load_json(AI_WEEKLY_REVIEWS_PATH, [])
    if not isinstance(reviews, list):
        reviews = []

    reviews.append({
        "date": str(date.today()),
        "week": review_dict.get("week", ""),
        "summary_title": review_dict.get("summary_title", ""),
        "overall_progress": review_dict.get("overall_progress", ""),
        "main_weaknesses": review_dict.get("main_weaknesses", []),
        "representative_problems": review_dict.get(
            "representative_problems",
            []
        ),
        "learning_feedback": review_dict.get("learning_feedback", ""),
        "next_week_focus": review_dict.get("next_week_focus", []),
        "recommended_actions": review_dict.get("recommended_actions", [])
    })

    AI_WEEKLY_REVIEWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AI_WEEKLY_REVIEWS_PATH, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)


def parse_ai_weekly_review(raw_text, week):
    try:
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("AI response is not an object")
    except (json.JSONDecodeError, TypeError, ValueError):
        data = {
            "week": week,
            "summary_title": f"Week {week} 学习总结",
            "overall_progress": "当前数据有限，建议结合规则版总结查看本周进度。",
            "main_weaknesses": [],
            "representative_problems": [],
            "learning_feedback": str(raw_text).strip() or "暂未获得有效 AI 总结。",
            "next_week_focus": ["继续完成计划题", "保持错因记录"],
            "recommended_actions": [
                "查看规则版本周总结",
                "优先补齐未完成题",
                "继续记录主要卡点"
            ]
        }

    list_fields = {
        "main_weaknesses",
        "representative_problems",
        "next_week_focus",
        "recommended_actions"
    }
    defaults = {
        "week": week,
        "summary_title": f"Week {week} 学习总结",
        "overall_progress": "当前数据有限，建议继续保持学习记录。",
        "learning_feedback": "建议结合规则版总结继续复盘。"
    }

    normalized = {}
    for field, default in defaults.items():
        value = data.get(field, default)
        normalized[field] = default if value in (None, "") else value

    for field in list_fields:
        value = data.get(field, [])
        if not isinstance(value, list):
            value = [str(value)] if value not in (None, "") else []
        normalized[field] = [str(item) for item in value]

    return normalized


def generate_ai_weekly_review():
    records = load_json(RECORDS_PATH, [])
    reviews = load_json(REVIEWS_PATH, [])
    agent_memory = load_json(AGENT_MEMORY_PATH, [])
    plan = load_json(PLAN_PATH, {})
    week = plan.get("week", "") if isinstance(plan, dict) else ""
    rule_summary = generate_week_summary()

    context = {
        "week_plan": plan,
        "records": records,
        "reviews": reviews,
        "agent_memory": agent_memory[-7:] if isinstance(agent_memory, list) else [],
        "rule_week_summary": rule_summary
    }

    prompt_template = load_prompt_template(PROMPT_VERSION)
    user_prompt = render_prompt(
        prompt_template,
        {
            "weekly_context": json.dumps(context, ensure_ascii=False),
            "output_schema": json.dumps(
                load_json(WEEKLY_REVIEW_SCHEMA_PATH, {}),
                ensure_ascii=False,
                indent=2
            )
        }
    )
    system_prompt = "你是 LeetCoach 的学习反思模块，只输出严格 JSON。"

    raw_text = ""
    start_time = time.time()
    model_name = ""
    try:
        from llm_client import LLMClient

        client = LLMClient()
        model_name = client.model
        raw_text = client.chat(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.4
        )
    except Exception as error:
        try:
            log_llm_call({
                "task": "ai_weekly_review",
                "prompt_version": PROMPT_VERSION,
                "model": model_name,
                "input_summary": {"week": week, "records_count": len(records)},
                "raw_output": raw_text,
                "parsed_success": False,
                "schema_valid": False,
                "fallback_used": True,
                "error_message": str(error),
                "latency_seconds": round(time.time() - start_time, 3)
            })
        except Exception:
            pass
        return {
            "fallback": True,
            "message": "AI 周总结生成失败，建议使用规则版本周总结。",
            "rule_result": rule_summary
        }

    review_dict = parse_ai_weekly_review(raw_text, week)
    try:
        log_llm_call({
            "task": "ai_weekly_review",
            "prompt_version": PROMPT_VERSION,
            "model": model_name,
            "input_summary": {"week": week, "records_count": len(records)},
            "raw_output": raw_text,
            "parsed_success": not review_dict.get("parse_fallback", False),
            "schema_valid": True,
            "fallback_used": False,
            "error_message": "",
            "latency_seconds": round(time.time() - start_time, 3)
        })
    except Exception:
        pass

    known_problem_ids = set()
    if isinstance(plan, dict):
        for day_data in plan.get("days", {}).values():
            if isinstance(day_data, dict):
                for problem_id in day_data.get("problems", []):
                    known_problem_ids.add(clean_problem_id(problem_id))

    if isinstance(records, list):
        for record in records:
            if isinstance(record, dict):
                known_problem_ids.add(
                    clean_problem_id(record.get("problem_id", ""))
                )

    review_dict["representative_problems"] = [
        clean_problem_id(problem_id)
        for problem_id in review_dict["representative_problems"]
        if clean_problem_id(problem_id) in known_problem_ids
    ]

    try:
        save_ai_weekly_review(review_dict)
    except Exception:
        print("AI 周总结保存失败，但总结已生成。")

    return review_dict


def format_ai_weekly_review(review_dict):
    if review_dict.get("fallback"):
        return "\n".join([
            review_dict.get(
                "message",
                "AI 周总结生成失败，建议使用规则版本周总结。"
            ),
            "",
            review_dict.get("rule_result", generate_week_summary())
        ])

    lines = [
        "===== AI 周总结 =====",
        "",
        f"周次：Week {review_dict.get('week', '')}",
        f"标题：{review_dict.get('summary_title', '')}",
        "",
        "整体进度：",
        str(review_dict.get("overall_progress", "")),
        "",
        "主要薄弱点："
    ]

    weaknesses = review_dict.get("main_weaknesses", [])
    lines.extend(f"- {item}" for item in weaknesses)
    if not weaknesses:
        lines.append("- 暂无明确薄弱点")

    lines.extend(["", "代表题目："])
    problems = review_dict.get("representative_problems", [])
    lines.extend(f"- {item}" for item in problems)
    if not problems:
        lines.append("- 暂无")

    lines.extend([
        "",
        "学习反馈：",
        str(review_dict.get("learning_feedback", "")),
        "",
        "下周重点："
    ])
    focus = review_dict.get("next_week_focus", [])
    lines.extend(f"- {item}" for item in focus)
    if not focus:
        lines.append("- 继续完成计划并保持记录")

    lines.extend(["", "推荐行动："])
    actions = review_dict.get("recommended_actions", [])
    lines.extend(f"- {item}" for item in actions)
    if not actions:
        lines.append("- 查看规则版总结并完成未完成题")

    return "\n".join(lines)
