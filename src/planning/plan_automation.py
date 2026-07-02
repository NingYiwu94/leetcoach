import hashlib
import json
from datetime import datetime
from pathlib import Path

from ai.ai_plan_generator import generate_ai_week_plan_next
from core.learning_analyzer import analyze_learning_patterns
from planning.plan_manager import get_plan_management_data


from app_paths import BASE_DIR
PLAN_PATH = BASE_DIR / "config" / "week_plan.json"
DRAFT_PATH = BASE_DIR / "config" / "week_plan_next.json"
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
PLAN_TASK_STATE_PATH = BASE_DIR / "data" / "plan_task_state.json"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def build_plan_context_fingerprint():
    plan = load_json(PLAN_PATH, {})
    records = load_json(RECORDS_PATH, [])
    reviews = load_json(REVIEWS_PATH, [])
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    plan_task_state = load_json(PLAN_TASK_STATE_PATH, [])

    if not isinstance(records, list):
        records = []
    if not isinstance(reviews, list):
        reviews = []

    analysis = analyze_learning_patterns(
        records=records,
        problem_bank=problem_bank if isinstance(problem_bank, dict) else {},
        reviews=reviews
    )
    context = {
        "plan": plan,
        "record_keys": [
            {
                "problem_id": item.get("problem_id"),
                "status": item.get("status"),
                "submit_time": item.get("submit_time"),
                "date": item.get("date")
            }
            for item in records
            if isinstance(item, dict)
        ],
        "pending_reviews": [
            {
                "problem_id": item.get("problem_id"),
                "next_review_date": item.get("next_review_date"),
                "priority_level": item.get("priority_level"),
                "previous_mastery_result": item.get(
                    "previous_mastery_result"
                )
            }
            for item in reviews
            if isinstance(item, dict) and not item.get("done")
        ],
        "learning_analysis": {
            "main_weakness": analysis.get("main_weakness"),
            "failure_count": analysis.get("failure_count"),
            "assisted_count": analysis.get("assisted_count"),
            "unresolved_count": analysis.get("unresolved_count"),
            "review_not_mastered_count": analysis.get(
                "review_not_mastered_count"
            ),
            "review_assisted_count": analysis.get(
                "review_assisted_count"
            ),
            "risky_problem_ids": [
                item.get("problem_id")
                for item in analysis.get("risky_problems", [])
            ],
            "review_mastery": {
                problem_id: {
                    "latest_result": item.get("latest_result"),
                    "latest_completed_at": item.get(
                        "latest_completed_at"
                    )
                }
                for problem_id, item in analysis.get(
                    "review_mastery",
                    {}
                ).items()
            }
        },
        "plan_task_state": plan_task_state
    }
    serialized = json.dumps(
        context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def evaluate_auto_plan_generation():
    management = get_plan_management_data()
    plan = management.get("plan", {})
    draft = management.get("draft")
    current_week = plan.get("week", 0) if isinstance(plan, dict) else 0
    try:
        current_week = int(current_week)
    except (TypeError, ValueError):
        current_week = 0

    expected_week = current_week + 1
    fingerprint = build_plan_context_fingerprint()

    if not isinstance(plan, dict) or not plan:
        return {
            "should_generate": True,
            "status": "initial_setup",
            "message": "尚无正式计划，将根据同步记录生成第一周计划草案。",
            "fingerprint": fingerprint
        }

    if not management.get("should_generate_next"):
        return {
            "should_generate": False,
            "status": "not_ready",
            "message": management.get("plan_advice", ""),
            "fingerprint": fingerprint
        }

    if isinstance(draft, dict):
        try:
            draft_week = int(draft.get("week", 0))
        except (TypeError, ValueError):
            draft_week = 0

        if draft_week == expected_week:
            if draft.get("context_fingerprint") == fingerprint:
                status = "draft_current"
                message = "下一阶段计划草案已是最新版本，等待用户确认。"
            else:
                status = "draft_needs_refresh"
                message = (
                    "学习状态已变化，但现有计划草案已保留。"
                    "请查看后决定是否手动重新生成。"
                )
            return {
                "should_generate": False,
                "status": status,
                "message": message,
                "fingerprint": fingerprint
            }

    return {
        "should_generate": True,
        "status": "ready",
        "message": "当前计划已进入切换阶段，将生成下一阶段计划草案。",
        "fingerprint": fingerprint
    }


def auto_generate_next_plan_if_needed(trigger="sync"):
    evaluation = evaluate_auto_plan_generation()
    if not evaluation.get("should_generate"):
        return {
            "generated": False,
            **evaluation
        }

    generation_trigger = trigger
    if evaluation.get("status") == "initial_setup":
        generation_trigger = "initial_setup"
    else:
        management = get_plan_management_data()
        if (
            management.get("total_count", 0) > 0
            and management.get("completed_count", 0)
            == management.get("total_count", 0)
        ):
            generation_trigger = "week_completed"

    plan = generate_ai_week_plan_next(
        trigger=generation_trigger,
        context_fingerprint=evaluation["fingerprint"]
    )
    return {
        "generated": True,
        "status": "generated",
        "message": "已自动生成下一阶段计划草案，等待用户确认。",
        "draft_week": plan.get("week"),
        "generated_by": plan.get("generated_by"),
        "generated_at": plan.get("generated_at"),
        "fingerprint": evaluation["fingerprint"]
    }


def format_auto_plan_status(result):
    if not isinstance(result, dict):
        return "计划自动评估暂时不可用。"

    lines = [
        "===== 计划自动评估 =====",
        "",
        result.get("message", "暂无计划状态。")
    ]
    if result.get("generated"):
        lines.extend([
            f"目标周次：Week {result.get('draft_week', '')}",
            f"生成方式：{result.get('generated_by', '')}",
            f"生成时间：{result.get('generated_at', '')}",
            "",
            "计划不会自动应用，请在今日面板或“计划管理”中查看并确认。"
        ])
    return "\n".join(lines)
