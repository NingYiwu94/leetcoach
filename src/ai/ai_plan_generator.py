import json
import os
import shutil
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from agent.agent_feedback_memory import (
    format_user_learning_profile_for_prompt,
    load_user_learning_profile,
)
from ai.ai_plan_evaluator import evaluate_ai_plan
from llm.llm_logger import log_llm_call
from llm.llm_output_validator import validate_week_plan_output
from core.next_plan import generate_next_week_plan_draft
from core.learning_analyzer import (
    analyze_learning_patterns,
    summarize_review_mastery
)
from core.learning_curriculum import (
    build_plan_scaffold,
    canonical_problem_id,
    summarize_problem_history
)
from planning.plan_progress import get_completed_problem_ids, get_plan_records
from planning.plan_review import clear_plan_review_state
from llm.prompt_loader import load_prompt_template, render_prompt
from rag.rag_engine import (
    format_plan_rag_context,
    retrieve_embedding_rag_context,
    retrieve_rag_context,
    short_text,
)
from rag.rag_trace import build_rag_trace, save_rag_trace_log


from app_paths import BASE_DIR, SCHEMAS_DIR
CURRENT_PLAN_PATH = BASE_DIR / "config" / "week_plan.json"
NEXT_PLAN_PATH = BASE_DIR / "config" / "week_plan_next.json"
PLAN_ARCHIVE_DIR = BASE_DIR / "config" / "plan_archive"
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
RECORDS_PATH = BASE_DIR / "data" / "records.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews.json"
AGENT_MEMORY_PATH = BASE_DIR / "data" / "agent_memory.json"
PLAN_TASK_STATE_PATH = BASE_DIR / "data" / "plan_task_state.json"
HINT_LOG_PATH = BASE_DIR / "data" / "hint_logs.json"
WEEK_PLAN_SCHEMA_PATH = SCHEMAS_DIR / "week_plan_schema.json"
PLAN_PROMPT_VERSION = "ai_plan_generator_v1"
PLAN_PROMPT_NAME = "ai_plan_generator"
PLAN_PROMPT_SEMVER = "v1"


def _normalize_prompt_version(prompt_version):
    value = str(prompt_version or "v1").strip().lower()
    if value.startswith("ai_plan_generator_"):
        value = value.replace("ai_plan_generator_", "", 1)
    if value not in {"v1", "v2"}:
        value = "v1"
    return value


def _prompt_template_name(prompt_version):
    version = _normalize_prompt_version(prompt_version)
    return f"ai_plan_generator_{version}"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default

def _json_text(data, max_chars=6000):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]"
    return text


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _summarize_records(records, problem_bank):
    if not isinstance(records, list):
        return "无有效刷题记录。"
    recent = records[-20:]
    status_counts = {}
    problem_ids = []
    for record in records:
        if not isinstance(record, dict):
            continue
        status = str(record.get("status", "未知")).replace(" ", "")
        status_counts[status] = status_counts.get(status, 0) + 1
        problem_id = clean_problem_id(record.get("problem_id"))
        if problem_id and problem_id not in problem_ids:
            problem_ids.append(problem_id)
    lines = [
        f"总记录数：{len(records)}",
        "状态分布：" + _json_text(status_counts, max_chars=1000),
        "最近记录："
    ]
    for record in recent[-8:]:
        if not isinstance(record, dict):
            continue
        problem_id = clean_problem_id(record.get("problem_id"))
        problem = problem_bank.get(problem_id, {})
        title = problem.get("title", record.get("title", "")) if isinstance(problem, dict) else ""
        lines.append(
            f"- {record.get('date', '')} {problem_id} {title} "
            f"{record.get('status', '')}"
        )
    return "\n".join(lines)


def _summarize_reviews(reviews):
    if not isinstance(reviews, list):
        return "无有效复习记录。"
    pending = [
        review for review in reviews
        if isinstance(review, dict) and not review.get("done")
    ]
    lines = [
        f"复习任务总数：{len(reviews)}",
        f"待完成复习：{len(pending)}"
    ]
    for review in pending[:10]:
        lines.append(
            f"- {clean_problem_id(review.get('problem_id'))} "
            f"next={review.get('next_review_date', '')} "
            f"priority={review.get('priority_level', '')} "
            f"reason={review.get('reason', '')}"
        )
    return "\n".join(lines)


def _summarize_problem_bank(problem_bank, plan_scaffold, records=None):
    if not isinstance(problem_bank, dict):
        problem_bank = {}
    records = records if isinstance(records, list) else []
    history = summarize_problem_history(records, problem_bank)
    completed_ids = [
        problem_id
        for problem_id, item in history.items()
        if item.get("ac_count", 0) or item.get("assisted_count", 0)
    ]
    scaffold_ids = []
    days = plan_scaffold.get("days", {}) if isinstance(plan_scaffold, dict) else {}
    for day in days.values():
        if not isinstance(day, dict):
            continue
        for problem_id in day.get("problems", []):
            problem_id = clean_problem_id(problem_id)
            if problem_id and problem_id not in scaffold_ids:
                scaffold_ids.append(problem_id)
    lines = [
        f"题库题目数：{len(problem_bank)}",
        f"本地题库已完成题数：{len(completed_ids)}",
        f"本地题库已完成题号：{', '.join(completed_ids[:60]) or '无'}",
        f"课程骨架主题：{plan_scaffold.get('weekly_theme', '')}",
        f"课程骨架已完成题：{', '.join(plan_scaffold.get('completed_in_topic', [])) or '无'}",
        f"课程骨架剩余题：{', '.join(plan_scaffold.get('remaining_in_topic', [])) or '无'}",
        f"课程骨架题目：{', '.join(scaffold_ids) or '无'}"
    ]
    for problem_id in scaffold_ids:
        problem = problem_bank.get(problem_id, {})
        if isinstance(problem, dict):
            lines.append(
                f"- {problem_id} {problem.get('title', '')} "
                f"{problem.get('difficulty', '')} "
                f"topics={problem.get('topics', [])}"
            )
    return "\n".join(lines)


def _summarize_agent_memory(agent_memory, hint_logs, coaching_brief):
    lines = [
        "教练摘要：",
        _json_text(coaching_brief, max_chars=3000),
        "",
        f"最近 Agent 记忆数：{len(agent_memory) if isinstance(agent_memory, list) else 0}",
        f"最近提示记录数：{len(hint_logs) if isinstance(hint_logs, list) else 0}"
    ]
    return "\n".join(lines)


def _build_plan_rag_query(
    current_plan,
    plan_scaffold,
    learning_analysis,
    learner_profile,
    review_context,
    records
):
    scaffold_days = plan_scaffold.get("days", {}) if isinstance(plan_scaffold, dict) else {}
    scaffold_problem_ids = []
    for day in scaffold_days.values():
        if not isinstance(day, dict):
            continue
        for problem_id in day.get("problems", []):
            problem_id = clean_problem_id(problem_id)
            if problem_id and problem_id not in scaffold_problem_ids:
                scaffold_problem_ids.append(problem_id)

    pending_review_ids = []
    for review in review_context:
        if not isinstance(review, dict):
            continue
        problem_id = clean_problem_id(review.get("problem_id"))
        if problem_id and problem_id not in pending_review_ids:
            pending_review_ids.append(problem_id)

    recent_problem_ids = []
    for record in records[-30:]:
        if not isinstance(record, dict):
            continue
        problem_id = clean_problem_id(record.get("problem_id"))
        if problem_id and problem_id not in recent_problem_ids:
            recent_problem_ids.append(problem_id)

    query_parts = [
        "LeetCoach AI plan generation",
        f"current week: {current_plan.get('week', '') if isinstance(current_plan, dict) else ''}",
        f"current title: {current_plan.get('title', '') if isinstance(current_plan, dict) else ''}",
        f"learner level: {learner_profile.get('level', '') if isinstance(learner_profile, dict) else ''}",
        f"weekly theme: {plan_scaffold.get('weekly_theme', '') if isinstance(plan_scaffold, dict) else ''}",
        f"weekly goal: {plan_scaffold.get('weekly_goal', '') if isinstance(plan_scaffold, dict) else ''}",
        f"remaining in topic: {' '.join(plan_scaffold.get('remaining_in_topic', [])) if isinstance(plan_scaffold, dict) else ''}",
        f"completed in topic: {' '.join(plan_scaffold.get('completed_in_topic', [])) if isinstance(plan_scaffold, dict) else ''}",
        f"scaffold problems: {' '.join(scaffold_problem_ids)}",
        f"pending reviews: {' '.join(pending_review_ids)}",
        f"recent records: {' '.join(recent_problem_ids)}",
        f"main weakness: {learning_analysis.get('main_weakness', '') if isinstance(learning_analysis, dict) else ''}",
        f"risk problems: {' '.join(str(item) for item in learning_analysis.get('risky_problems', [])[:8]) if isinstance(learning_analysis, dict) else ''}",
        "Need evidence for choosing next 7-day algorithm learning plan, review tasks, unfinished problems, assisted AC, failed attempts, mastery notes.",
    ]
    return "\n".join(query_parts)


def build_plan_rag_context(
    current_plan,
    plan_scaffold,
    learning_analysis,
    learner_profile,
    review_context,
    records,
    use_enhanced_memory=False,
):
    query = _build_plan_rag_query(
        current_plan,
        plan_scaffold,
        learning_analysis,
        learner_profile,
        review_context,
        records
    )
    try:
        rag_mode = os.getenv("LEETCOACH_PLAN_RAG_MODE", "keyword").strip().lower()
        if rag_mode == "embedding":
            rag_context = retrieve_embedding_rag_context(
                query,
                problem_id="",
                top_k=10,
                max_chars=4200,
                selection_strategy="plan",
                use_enhanced_memory=use_enhanced_memory,
            )
        else:
            rag_context = retrieve_rag_context(
                query,
                problem_id="",
                top_k=10,
                max_chars=2800,
                selection_strategy="plan",
                use_enhanced_memory=use_enhanced_memory,
            )
    except Exception as error:
        rag_context = {
            "documents": [],
            "context_text": f"RAG 检索失败：{error}",
            "matched_count": 0,
            "total_candidate_count": 0,
            "mode": "error",
            "embedding_error": str(error)
        }

    rag_context["query"] = query
    rag_context["use_enhanced_memory"] = bool(use_enhanced_memory)
    documents = rag_context.get("documents", [])
    evidence = []
    if isinstance(documents, list):
        for document in documents[:12]:
            if not isinstance(document, dict):
                continue
            evidence.append({
                "source": document.get("source", ""),
                "problem_id": document.get("problem_id", ""),
                "title": document.get("title", ""),
                "score": document.get("score", 0),
                "similarity": document.get("similarity", ""),
                "summary": short_text(document.get("content", ""), 180)
            })

    rag_context["evidence"] = evidence
    priority_text = _format_plan_priority_evidence(
        plan_scaffold,
        review_context,
        records
    )
    base_context_text = rag_context.get("context_text", "")
    rag_context["context_text"] = "\n\n".join(
        item for item in [
            "【计划优先证据】\n" + priority_text if priority_text else "",
            "【Embedding RAG 召回证据】\n" + base_context_text if base_context_text else ""
        ] if item
    )
    base_context_text = format_plan_rag_context(documents)
    plan_rag_instruction = "\n".join([
        "【RAG 使用要求】",
        "- 优先使用【用户个性化学习记忆】中的刷题记录、复习记录、笔记、阶段总结和 Agent 记忆。",
        "- 【题库背景信息】只用于确认专题、难度和题目属性，不要把它当作用户已经掌握或没掌握的证据。",
        "- 如果个性化记忆和题库背景冲突，以个性化记忆为准。",
    ])
    rag_context["context_text"] = "\n\n".join(
        item for item in [
            "【计划优先证据】\n" + priority_text if priority_text else "",
            plan_rag_instruction + "\n\n" + base_context_text if base_context_text else ""
        ] if item
    )
    return rag_context


def _format_plan_priority_evidence(plan_scaffold, review_context, records):
    scaffold_days = plan_scaffold.get("days", {}) if isinstance(plan_scaffold, dict) else {}
    scaffold_problem_ids = []
    for day in scaffold_days.values():
        if not isinstance(day, dict):
            continue
        for problem_id in day.get("problems", []):
            problem_id = clean_problem_id(problem_id)
            if problem_id and problem_id not in scaffold_problem_ids:
                scaffold_problem_ids.append(problem_id)

    pending_review_ids = []
    for review in review_context:
        if not isinstance(review, dict):
            continue
        problem_id = clean_problem_id(review.get("problem_id"))
        if problem_id and problem_id not in pending_review_ids:
            pending_review_ids.append(problem_id)

    target_ids = []
    for problem_id in scaffold_problem_ids + pending_review_ids:
        if problem_id and problem_id not in target_ids:
            target_ids.append(problem_id)

    lines = []
    if scaffold_problem_ids:
        lines.append("课程骨架题号：" + "、".join(scaffold_problem_ids))
    if pending_review_ids:
        lines.append("待复习题号：" + "、".join(pending_review_ids[:12]))

    for problem_id in target_ids[:18]:
        matched_records = [
            record for record in records
            if (
                isinstance(record, dict)
                and clean_problem_id(record.get("problem_id")) == problem_id
            )
        ]
        matched_records = matched_records[-3:]
        matched_reviews = [
            review for review in review_context
            if (
                isinstance(review, dict)
                and clean_problem_id(review.get("problem_id")) == problem_id
            )
        ]
        fragments = []
        if matched_records:
            latest = matched_records[-1]
            fragments.append(
                "最近记录="
                + str(latest.get("status", "未知"))
                + " "
                + str(latest.get("date", ""))
            )
            mistake_type = str(latest.get("mistake_type", "") or "").strip()
            if mistake_type:
                fragments.append("错因=" + mistake_type)
        if matched_reviews:
            pending = [item for item in matched_reviews if not item.get("done")]
            if pending:
                next_dates = [
                    str(item.get("next_review_date", ""))
                    for item in pending
                    if str(item.get("next_review_date", "")).strip()
                ]
                fragments.append(
                    "待复习="
                    + str(len(pending))
                    + (" next=" + min(next_dates) if next_dates else "")
                )
        if fragments:
            lines.append(f"- {problem_id}: " + "；".join(fragments))

    return "\n".join(lines)


def _build_eval_context(
    context,
    current_plan,
    records,
    reviews,
    problem_bank,
    learning_analysis,
    learner_profile
):
    planned_ids = _planned_problem_ids(current_plan)
    completed_ids = get_completed_problem_ids(current_plan, records)
    failed_ids = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if str(record.get("status", "")).replace(" ", "") == "未通过":
            problem_id = clean_problem_id(record.get("problem_id"))
            if problem_id and problem_id not in failed_ids:
                failed_ids.append(problem_id)
    return {
        **context,
        "problem_bank": problem_bank,
        "expected_week": _next_week_number(current_plan),
        "completed_problem_ids": sorted(_all_completed_problem_ids(records)),
        "unfinished_problem_ids": [
            problem_id for problem_id in planned_ids
            if problem_id not in completed_ids
        ],
        "failed_problem_ids": failed_ids,
        "main_weakness": learning_analysis.get("main_weakness", ""),
        "learner_profile": learner_profile,
        "pending_reviews": [
            review for review in reviews
            if isinstance(review, dict) and not review.get("done")
        ]
    }

def get_recent_stage_summaries(plan_task_state, limit=3):
    if not isinstance(plan_task_state, list):
        return []
    summaries = [
        item.get("stage_summary")
        for item in plan_task_state
        if (
            isinstance(item, dict)
            and isinstance(item.get("stage_summary"), dict)
        )
    ]
    summaries.sort(key=lambda item: str(item.get("generated_at", "")))
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 3
    return summaries[-limit:]


def build_coaching_brief(
    learner_profile,
    learning_analysis,
    reviews,
    hint_logs
):
    risky_problems = learning_analysis.get("risky_problems", [])
    if not isinstance(risky_problems, list):
        risky_problems = []
    pending_reviews = [
        item for item in reviews
        if isinstance(item, dict) and not item.get("done")
    ]
    recent_hints = [
        item for item in hint_logs[-20:]
        if isinstance(item, dict)
    ]
    hint_problem_counts = {}
    for item in recent_hints:
        problem_id = clean_problem_id(item.get("problem_id"))
        if problem_id:
            hint_problem_counts[problem_id] = (
                hint_problem_counts.get(problem_id, 0) + 1
            )
    repeated_hint_problems = [
        problem_id
        for problem_id, count in sorted(
            hint_problem_counts.items(),
            key=lambda item: (-item[1], item[0])
        )
        if count >= 2
    ]

    constraints = []
    if learner_profile.get("level") == "beginner":
        constraints.append("保持低题量，每天最多一道核心题，不安排 Hard。")
    if learning_analysis.get("review_not_mastered_count", 0):
        constraints.append("存在复习仍未掌握的题，必须先重做再进入新专题。")
    if learning_analysis.get("assisted_count", 0):
        constraints.append("看提示后 AC 较多，计划中必须安排关掉提示后的独立重写。")
    if repeated_hint_problems:
        constraints.append(
            "这些题多次请求提示，需要降低新题比例并安排复盘："
            + "、".join(repeated_hint_problems[:3])
            + "。"
        )
    if not constraints:
        constraints.append("保持当前节奏，用验收结果决定是否进入下一阶段。")

    return {
        "learner_level": learner_profile.get("label", "未判断"),
        "learning_status": learning_analysis.get("learning_status", ""),
        "main_weakness": learning_analysis.get("main_weakness", ""),
        "top_risky_problems": [
            {
                "problem_id": item.get("problem_id", ""),
                "title": item.get("title", ""),
                "risk_score": item.get("risk_score", 0),
                "patterns": item.get("patterns", [])
            }
            for item in risky_problems[:3]
            if isinstance(item, dict)
        ],
        "pending_review_count": len(pending_reviews),
        "repeated_hint_problems": repeated_hint_problems[:5],
        "planning_constraints": constraints
    }


def clean_problem_id(problem_id):
    value = str(problem_id or "")
    for prefix in ("题号：", "题号:", "题号"):
        value = value.replace(prefix, "")
    return value.strip()


def analyze_user_level(records, problem_bank, reviews=None):
    if not isinstance(records, list):
        records = []
    if not isinstance(problem_bank, dict):
        problem_bank = {}

    synced_records = [
        record
        for record in records
        if (
            isinstance(record, dict)
            and record.get("source") == "leetcode_auto_sync"
        )
    ]
    evidence_records = synced_records or [
        record for record in records if isinstance(record, dict)
    ]
    unique_problem_ids = {
        canonical_problem_id(record, problem_bank)
        for record in evidence_records
        if canonical_problem_id(record, problem_bank)
    }
    accepted_ids = {
        canonical_problem_id(record, problem_bank)
        for record in evidence_records
        if (
            canonical_problem_id(record, problem_bank)
            and str(record.get("status", "")).replace(" ", "")
            in {"AC", "看提示后AC"}
        )
    }
    failed_count = sum(
        1
        for record in evidence_records
        if str(record.get("status", "")).replace(" ", "") == "未通过"
    )
    difficulty_counts = {"Easy": 0, "Medium": 0, "Hard": 0, "Unknown": 0}
    for problem_id in unique_problem_ids:
        problem = problem_bank.get(problem_id, {})
        difficulty = (
            str(problem.get("difficulty", "Unknown")).strip().title()
            if isinstance(problem, dict)
            else "Unknown"
        )
        if difficulty not in difficulty_counts:
            difficulty = "Unknown"
        difficulty_counts[difficulty] += 1

    unique_count = len(unique_problem_ids)
    submission_count = len(evidence_records)
    if unique_count < 10 or submission_count < 15:
        level = "beginner"
        label = "新手"
        max_daily_problems = 1
        allowed_difficulties = ["Easy", "Medium"]
        weekly_problem_target = 5
        guidance = (
            "以 Easy 模板题为基础，可以加入经典 Medium，"
            "但 Medium 只要求看提示写出或第一遍理解；"
            "每天最多 1 道题，至少安排 1 天复习和 1 天总结，不安排 Hard。"
        )
    elif unique_count < 40 or submission_count < 80:
        level = "developing"
        label = "基础进阶"
        max_daily_problems = 2
        allowed_difficulties = ["Easy", "Medium"]
        weekly_problem_target = 8
        guidance = (
            "Easy 与 Medium 搭配，每天最多 2 道题，"
            "优先巩固失败题和薄弱题型，不安排 Hard。"
        )
    else:
        level = "experienced"
        label = "熟练"
        max_daily_problems = 2
        allowed_difficulties = ["Easy", "Medium", "Hard"]
        weekly_problem_target = 10
        guidance = (
            "根据历史薄弱点安排 Medium 为主的训练，"
            "仅在记录显示基础稳定时少量加入 Hard。"
        )

    mastery_counts = {
        "independent": 0,
        "assisted": 0,
        "not_mastered": 0
    }
    for item in summarize_review_mastery(reviews).values():
        result = item.get("latest_result")
        if result in mastery_counts:
            mastery_counts[result] += 1
    if mastery_counts["not_mastered"]:
        weekly_problem_target = min(weekly_problem_target, 4)
        guidance += (
            " 最近复习中存在“仍未掌握”，下一阶段应减少新题，"
            "优先保留同专题重做。"
        )
    elif mastery_counts["assisted"] > mastery_counts["independent"]:
        weekly_problem_target = min(weekly_problem_target, 5)
        guidance += (
            " 最近复习较依赖提示，应优先练习独立重写。"
        )

    return {
        "level": level,
        "label": label,
        "submission_count": submission_count,
        "synced_submission_count": len(synced_records),
        "unique_problem_count": unique_count,
        "accepted_problem_count": len(accepted_ids),
        "failed_submission_count": failed_count,
        "difficulty_counts": difficulty_counts,
        "max_daily_problems": max_daily_problems,
        "allowed_difficulties": allowed_difficulties,
        "weekly_problem_target": weekly_problem_target,
        "review_mastery_counts": mastery_counts,
        "guidance": guidance
    }


def parse_ai_plan_response(raw_text):
    if not isinstance(raw_text, str):
        return None

    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        plan = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

    return plan if isinstance(plan, dict) else None


def _next_week_number(current_plan):
    try:
        return int(current_plan.get("week", 0)) + 1
    except (TypeError, ValueError):
        return 1


def _short_topic_title(value):
    text = str(value or "").strip()
    topic_keywords = [
        "数组",
        "链表",
        "哈希表",
        "字符串",
        "栈",
        "队列",
        "二叉树",
        "回溯",
        "动态规划",
        "贪心",
        "图论",
    ]
    for keyword in topic_keywords:
        if keyword in text:
            return keyword
    for separator in ("：", ":", "-", "—", "与", "和", "基础", "入门", "巩固"):
        if separator in text:
            text = text.split(separator)[0].strip()
    return text or "学习计划"


def _all_completed_problem_ids(records):
    completed = set()
    if not isinstance(records, list):
        return completed
    for record in records:
        if not isinstance(record, dict):
            continue
        problem_id = clean_problem_id(record.get("problem_id"))
        status = str(record.get("status", "")).replace(" ", "").strip()
        if problem_id and status in {"AC", "看提示后AC"}:
            completed.add(problem_id)
    return completed


def _enforce_plan_hard_rules(plan, current_plan=None, records=None):
    plan = validate_ai_week_plan(plan)
    current_plan = (
        current_plan
        if isinstance(current_plan, dict)
        else load_json(CURRENT_PLAN_PATH, {})
    )
    records = records if isinstance(records, list) else load_json(RECORDS_PATH, [])

    if isinstance(current_plan, dict):
        plan["week"] = _next_week_number(current_plan)

    theme = plan.get("weekly_theme") or plan.get("title")
    plan["title"] = _short_topic_title(theme)

    completed_ids = _all_completed_problem_ids(records)
    excluded_as_new = []
    days = plan.get("days", {})
    if not isinstance(days, dict):
        days = {}
    for day in days.values():
        if not isinstance(day, dict):
            continue
        task_type = str(day.get("task_type") or "new").strip() or "new"
        problems = day.get("problems", [])
        if not isinstance(problems, list):
            problems = [problems] if problems not in (None, "") else []
        cleaned = []
        completed_in_day = []
        for problem_id in problems:
            problem_id = clean_problem_id(problem_id)
            if not problem_id or problem_id in cleaned:
                continue
            cleaned.append(problem_id)
            if problem_id in completed_ids:
                completed_in_day.append(problem_id)

        if task_type == "new" and completed_in_day:
            day["task_type"] = "review"
            day["goal"] = "复习已完成题，确认是否能独立重写"
            day["reason"] = "这道题已有完成记录，因此不会作为新题重复安排。"
            review_problems = day.get("review_problems", [])
            if not isinstance(review_problems, list):
                review_problems = []
            for problem_id in completed_in_day:
                if problem_id not in review_problems:
                    review_problems.append(problem_id)
                if problem_id not in excluded_as_new:
                    excluded_as_new.append(problem_id)
            day["review_problems"] = review_problems[:3]
        day["problems"] = cleaned[:2]

    quality = plan.get("quality_check", {})
    if not isinstance(quality, dict):
        quality = {}
    quality["excluded_completed_as_new"] = excluded_as_new
    plan["quality_check"] = quality
    return plan


def _next_start_date(current_plan):
    start_date = current_plan.get("start_date")
    try:
        current_start = datetime.strptime(
            str(start_date), "%Y-%m-%d"
        ).date()
        candidate = current_start + timedelta(days=7)
    except (TypeError, ValueError):
        candidate = date.today() + timedelta(days=1)

    if candidate <= date.today():
        candidate = date.today() + timedelta(days=1)
    return str(candidate)


def _default_day(day_index):
    defaults = {
        1: ("复习当前未完成题", "优先补齐已有学习任务。"),
        2: ("重做未通过或需要提示的题", "加强独立解题能力。"),
        3: ("巩固当前主要薄弱题型", "针对近期错因进行专项练习。"),
        4: ("适量练习同阶段新题", "在已有基础上平稳扩展。"),
        5: ("继续巩固本阶段题型", "保持适中的新题数量。"),
        6: ("复习错题和到期复习题", "避免只刷题不复盘。"),
        7: ("总结本周题型模板", "整理方法并准备下一阶段。")
    }
    goal, reason = defaults[day_index]
    return {
        "date_note": f"Day {day_index}",
        "problems": [],
        "goal": goal,
        "reason": reason
    }


def validate_ai_week_plan(plan):
    if not isinstance(plan, dict):
        plan = {}

    current_plan = load_json(CURRENT_PLAN_PATH, {})
    if not isinstance(current_plan, dict):
        current_plan = {}

    week = plan.get("week", _next_week_number(current_plan))
    try:
        week = int(week)
    except (TypeError, ValueError):
        week = _next_week_number(current_plan)

    title = str(plan.get("title", "")).strip()
    if not title:
        title = "算法基础巩固周"

    start_date = str(plan.get("start_date", "")).strip()
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        start_date = _next_start_date(current_plan)

    source_days = plan.get("days", {})
    if not isinstance(source_days, dict):
        source_days = {}

    learner_level = str(plan.get("learner_level", "")).strip()
    problem_limit = 1 if learner_level == "beginner" else 2
    days = {}
    for day_index in range(1, 8):
        day_key = str(day_index)
        default = _default_day(day_index)
        day = source_days.get(day_key, {})
        if not isinstance(day, dict):
            day = {}

        problems = day.get("problems", [])
        if not isinstance(problems, list):
            problems = [problems] if problems not in (None, "") else []

        cleaned_problems = []
        for problem_id in problems:
            problem_id = clean_problem_id(problem_id)
            if problem_id and problem_id not in cleaned_problems:
                cleaned_problems.append(problem_id)

        execution_steps = day.get("execution_steps", [])
        if not isinstance(execution_steps, list):
            execution_steps = [execution_steps]
        review_problems = day.get("review_problems", [])
        if not isinstance(review_problems, list):
            review_problems = [review_problems]

        days[day_key] = {
            "date_note": str(
                day.get("date_note") or default["date_note"]
            ),
            "problems": cleaned_problems[:problem_limit],
            "goal": str(day.get("goal") or default["goal"]),
            "reason": str(day.get("reason") or default["reason"]),
            "topic": str(day.get("topic") or ""),
            "task_type": str(day.get("task_type") or "new"),
            "mastery_requirement": str(
                day.get("mastery_requirement") or "看提示能写出"
            ),
            "execution_steps": [
                str(item).strip()
                for item in execution_steps
                if str(item).strip()
            ][:5],
            "summary_focus": str(day.get("summary_focus") or ""),
            "relation_previous": str(
                day.get("relation_previous") or ""
            ),
            "relation_next": str(day.get("relation_next") or ""),
            "review_problems": [
                clean_problem_id(item)
                for item in review_problems
                if clean_problem_id(item)
            ][:3]
        }

    focus = plan.get("recommended_focus", [])
    if not isinstance(focus, list):
        focus = [focus] if focus not in (None, "") else []

    validated = {
        "week": week,
        "title": title,
        "start_date": start_date,
        "days": days,
        "generated_by": str(
            plan.get("generated_by") or "ai_plan_generator"
        ),
        "reason": str(
            plan.get("reason")
            or "根据当前刷题记录和复习状态生成保守计划。"
        ),
        "recommended_focus": [
            str(item).strip() for item in focus if str(item).strip()
        ][:5],
        "weekly_theme": str(plan.get("weekly_theme") or title),
        "weekly_goal": str(plan.get("weekly_goal") or ""),
        "minimum_acceptance": str(
            plan.get("minimum_acceptance") or ""
        ),
        "transition_logic": str(plan.get("transition_logic") or ""),
        "must_master": [
            clean_problem_id(item)
            for item in plan.get("must_master", [])
            if clean_problem_id(item)
        ],
        "guided_mastery": [
            clean_problem_id(item)
            for item in plan.get("guided_mastery", [])
            if clean_problem_id(item)
        ],
        "understand_only": [
            clean_problem_id(item)
            for item in plan.get("understand_only", [])
            if clean_problem_id(item)
        ],
        "mastery_review_ids": [
            clean_problem_id(item)
            for item in plan.get("mastery_review_ids", [])
            if clean_problem_id(item)
        ],
        "priority_review_ids": [
            clean_problem_id(item)
            for item in plan.get("priority_review_ids", [])
            if clean_problem_id(item)
        ],
        "adaptive_reason": str(plan.get("adaptive_reason") or "")
    }
    for field in {
        "generated_at",
        "generated_for_week",
        "generation_trigger",
        "context_fingerprint",
        "learner_level",
        "learner_level_label",
        "learner_level_reason",
        "ai_generation_error",
        "curriculum_topic_id",
        "quality_check",
        "llm_schema_check",
        "llm_eval_result",
        "llm_fallback_used",
        "prompt_version",
        "rag_context"
    }:
        if field in plan:
            validated[field] = plan[field]
    return validated


def _merge_ai_plan_with_scaffold(ai_plan, scaffold):
    merged = dict(ai_plan) if isinstance(ai_plan, dict) else {}
    for field in {
        "curriculum_topic_id",
        "weekly_theme",
        "weekly_goal",
        "minimum_acceptance",
        "transition_logic",
        "must_master",
        "guided_mastery",
        "understand_only",
        "mastery_review_ids",
        "priority_review_ids",
        "adaptive_reason"
    }:
        merged[field] = scaffold[field]
    merged["reason"] = scaffold["selection_reason"]

    ai_days = merged.get("days", {})
    if not isinstance(ai_days, dict):
        ai_days = {}
    merged_days = {}
    for day_index in range(1, 8):
        key = str(day_index)
        base_day = scaffold["days"][key]
        ai_day = ai_days.get(key, {})
        if not isinstance(ai_day, dict):
            ai_day = {}
        day = dict(base_day)
        ai_steps = ai_day.get("execution_steps", [])
        if isinstance(ai_steps, list) and ai_steps:
            day["execution_steps"] = ai_steps
        day["problems"] = list(base_day.get("problems", []))
        day["review_problems"] = list(
            base_day.get("review_problems", [])
        )
        day["mastery_requirement"] = base_day.get(
            "mastery_requirement",
            "看提示能写出"
        )
        day["task_type"] = base_day.get("task_type", "new")
        day["topic"] = base_day.get("topic", "")
        merged_days[key] = day
    merged["days"] = merged_days
    return merged


def assess_plan_quality(plan, scaffold, problem_bank):
    issues = []
    if plan.get("weekly_theme") != scaffold.get("weekly_theme"):
        issues.append("本周主题与课程路线不一致")

    days = plan.get("days", {})
    for day_index in range(1, 8):
        key = str(day_index)
        day = days.get(key, {})
        expected = scaffold["days"][key]
        if day.get("problems", []) != expected.get("problems", []):
            issues.append(f"Day {day_index} 题目偏离课程骨架")
        for problem_id in day.get("problems", []):
            if problem_id not in problem_bank:
                issues.append(f"题号 {problem_id} 不在题库中")
        if not day.get("goal") or not day.get("reason"):
            issues.append(f"Day {day_index} 缺少目标或安排原因")
        if not day.get("execution_steps"):
            issues.append(f"Day {day_index} 缺少执行步骤")
        if not day.get("summary_focus"):
            issues.append(f"Day {day_index} 缺少总结重点")

    if days.get("6", {}).get("task_type") != "review_day":
        issues.append("Day 6 不是复习日")
    if days.get("7", {}).get("task_type") != "summary":
        issues.append("Day 7 不是总结日")
    if not plan.get("minimum_acceptance"):
        issues.append("缺少本周最低验收标准")
    if not plan.get("transition_logic"):
        issues.append("缺少下周过渡逻辑")

    return {
        "passed": not issues,
        "score": max(0, 100 - len(issues) * 10),
        "issues": issues
    }


def _planned_problem_ids(current_plan):
    problem_ids = []
    days = current_plan.get("days", {})
    if not isinstance(days, dict):
        return problem_ids

    for day in days.values():
        if not isinstance(day, dict):
            continue
        for problem_id in day.get("problems", []):
            problem_id = clean_problem_id(problem_id)
            if problem_id and problem_id not in problem_ids:
                problem_ids.append(problem_id)
    return problem_ids


def _generate_rule_fallback(
    current_plan,
    records,
    reviews,
    problem_bank=None,
    learner_profile=None
):
    planned_ids = _planned_problem_ids(current_plan)
    completed_ids = get_completed_problem_ids(current_plan, records)
    plan_records = get_plan_records(current_plan, records)
    failed_ids = []
    hinted_ids = []
    mistake_counts = {}

    if not isinstance(records, list):
        records = []
    for record in plan_records:
        if not isinstance(record, dict):
            continue
        problem_id = clean_problem_id(record.get("problem_id"))
        status = str(record.get("status", "")).replace(" ", "")
        if status == "未通过" and problem_id not in failed_ids:
            failed_ids.append(problem_id)
        if status == "看提示后AC" and problem_id not in hinted_ids:
            hinted_ids.append(problem_id)

        mistake_type = str(
            record.get("mistake_type") or "未分类"
        ).strip()
        if mistake_type != "未分类":
            mistake_counts[mistake_type] = (
                mistake_counts.get(mistake_type, 0) + 1
            )

    unfinished_ids = [
        problem_id
        for problem_id in planned_ids
        if problem_id not in completed_ids
    ]
    pending_review_ids = []
    if isinstance(reviews, list):
        for review in reviews:
            if not isinstance(review, dict) or review.get("done"):
                continue
            problem_id = clean_problem_id(review.get("problem_id"))
            if problem_id and problem_id not in pending_review_ids:
                pending_review_ids.append(problem_id)

    if problem_bank is None:
        problem_bank = load_json(PROBLEM_BANK_PATH, {})
    if not isinstance(problem_bank, dict):
        problem_bank = {}
    if learner_profile is None:
        learner_profile = analyze_user_level(records, problem_bank)
    learning_analysis = analyze_learning_patterns(
        records=records,
        problem_bank=problem_bank
    )
    main_weakness = learning_analysis.get("main_weakness", "")
    if main_weakness == "暂无明确分类" and mistake_counts:
        main_weakness = max(mistake_counts, key=mistake_counts.get)
    if main_weakness == "暂无明确分类":
        main_weakness = ""

    review_candidates = []
    for problem_id in unfinished_ids + failed_ids + hinted_ids:
        if problem_id and problem_id not in review_candidates:
            review_candidates.append(problem_id)

    new_candidates = []
    allowed_difficulties = set(
        learner_profile.get("allowed_difficulties", ["Easy"])
    )
    attempted_ids = {
        clean_problem_id(record.get("problem_id"))
        for record in records
        if isinstance(record, dict)
    }
    for problem_id, problem in problem_bank.items():
        if not isinstance(problem, dict):
            continue
        if (
            problem_id not in attempted_ids
            and problem.get("difficulty", "Unknown") in allowed_difficulties
        ):
            new_candidates.append(problem_id)

    easy_review_candidates = [
        problem_id
        for problem_id, problem in problem_bank.items()
        if (
            isinstance(problem, dict)
            and problem.get("difficulty") == "Easy"
            and problem_id in attempted_ids
        )
    ]
    practice_candidates = []
    for problem_id in (
        review_candidates
        + easy_review_candidates
        + pending_review_ids
        + new_candidates
    ):
        problem = problem_bank.get(problem_id, {})
        difficulty = (
            problem.get("difficulty", "Unknown")
            if isinstance(problem, dict)
            else "Unknown"
        )
        if (
            learner_profile.get("level") == "beginner"
            and difficulty != "Easy"
        ):
            continue
        if problem_id and problem_id not in practice_candidates:
            practice_candidates.append(problem_id)

    def candidate(index):
        return practice_candidates[index:index + 1]

    plan = {
        "week": _next_week_number(current_plan),
        "title": main_weakness or "算法基础",
        "start_date": _next_start_date(current_plan),
        "days": {
            "1": {
                "problems": candidate(0),
                "goal": "优先补齐当前计划中的未完成题",
                "reason": "未完成题应优先于新增题目。"
            },
            "2": {
                "problems": candidate(1),
                "goal": "重做未通过或需要提示的题",
                "reason": "通过重做加强独立解题能力。"
            },
            "3": {
                "problems": candidate(2),
                "goal": (
                    f"针对“{main_weakness}”进行复习"
                    if main_weakness
                    else "完成待复习题并整理卡点"
                ),
                "reason": "优先消化复习任务和近期薄弱点。"
            },
            "4": {
                "problems": candidate(3),
                "goal": "适量练习同阶段新题"
            },
            "5": {
                "problems": candidate(4),
                "goal": "继续巩固当前算法题型"
            },
            "6": {"problems": [], "goal": "复习本周错题和到期复习题"},
            "7": {"problems": [], "goal": "总结本周题型模板"}
        },
        "generated_by": "rule_fallback",
        "reason": (
            "AI 计划生成不可用，已根据未完成题、错题和复习记录"
            "生成保守计划草案。"
        ),
        "recommended_focus": (
            [main_weakness] if main_weakness else ["完成现有计划", "及时复盘"]
        ),
        "learner_level": learner_profile.get("level", "beginner"),
        "learner_level_label": learner_profile.get("label", "新手"),
        "learner_level_reason": learner_profile.get("guidance", "")
    }
    return validate_ai_week_plan(plan)


def _build_scaffold_fallback(
    current_plan,
    scaffold,
    learner_profile
):
    return validate_ai_week_plan({
        "week": _next_week_number(current_plan),
        "title": scaffold["weekly_theme"],
        "start_date": _next_start_date(current_plan),
        "days": scaffold["days"],
        "generated_by": "curriculum_fallback",
        "reason": (
            scaffold["selection_reason"]
            + "模型暂时不可用，已保留课程规则生成的可执行骨架。"
        ),
        "recommended_focus": [
            scaffold["weekly_theme"],
            scaffold["weekly_goal"]
        ],
        "learner_level": learner_profile.get("level", "beginner"),
        "learner_level_label": learner_profile.get("label", "新手"),
        "learner_level_reason": learner_profile.get("guidance", ""),
        **{
            field: scaffold[field]
            for field in {
                "curriculum_topic_id",
                "weekly_theme",
                "weekly_goal",
                "minimum_acceptance",
                "transition_logic",
                "must_master",
                "guided_mastery",
                "understand_only",
                "mastery_review_ids",
                "priority_review_ids",
                "adaptive_reason"
            }
        }
    })


def _correct_future_review_wording(plan, reviews):
    if not isinstance(plan, dict) or not isinstance(reviews, list):
        return plan

    pending_dates = {}
    for review in reviews:
        if not isinstance(review, dict) or review.get("done"):
            continue
        problem_id = clean_problem_id(review.get("problem_id"))
        review_date = str(review.get("next_review_date", "")).strip()
        try:
            parsed_date = datetime.strptime(
                review_date,
                "%Y-%m-%d"
            ).date()
        except ValueError:
            continue
        if (
            problem_id
            and (
                problem_id not in pending_dates
                or parsed_date < pending_dates[problem_id]
            )
        ):
            pending_dates[problem_id] = parsed_date

    try:
        start_date = datetime.strptime(
            str(plan.get("start_date", "")),
            "%Y-%m-%d"
        ).date()
    except ValueError:
        return plan

    days = plan.get("days", {})
    if not isinstance(days, dict):
        return plan
    for day_index in range(1, 8):
        day = days.get(str(day_index), {})
        if not isinstance(day, dict):
            continue
        scheduled_date = start_date + timedelta(days=day_index - 1)
        for problem_id in day.get("problems", []):
            review_date = pending_dates.get(clean_problem_id(problem_id))
            wording = f"{day.get('goal', '')}{day.get('reason', '')}"
            if (
                review_date
                and scheduled_date < review_date
                and "到期" in wording
            ):
                day["goal"] = f"提前巩固题目 {problem_id}"
                day["reason"] = (
                    f"该题计划复习日期为 {review_date}，"
                    "本次用于提前巩固，不视为到期复习。"
                )
    return plan


def save_week_plan_next(plan):
    current_plan = load_json(CURRENT_PLAN_PATH, {})
    records = load_json(RECORDS_PATH, [])
    validated_plan = _enforce_plan_hard_rules(plan, current_plan, records)
    NEXT_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NEXT_PLAN_PATH, "w", encoding="utf-8") as f:
        json.dump(validated_plan, f, ensure_ascii=False, indent=2)
    return validated_plan


def load_week_plan_next():
    plan = load_json(NEXT_PLAN_PATH, None)
    if not isinstance(plan, dict):
        return None
    current_plan = load_json(CURRENT_PLAN_PATH, {})
    records = load_json(RECORDS_PATH, [])
    plan = _enforce_plan_hard_rules(plan, current_plan, records)
    if isinstance(current_plan, dict):
        expected_week = _next_week_number(current_plan)
        try:
            draft_week = int(plan.get("week", 0))
        except (TypeError, ValueError):
            draft_week = 0
        if draft_week != expected_week:
            return None
    return plan


def generate_ai_week_plan_next(
    trigger="manual",
    context_fingerprint="",
    prompt_version="v1",
    save_draft=True,
    with_rag=True,
    use_enhanced_memory=False,
):
    current_plan = load_json(CURRENT_PLAN_PATH, {})
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    records = load_json(RECORDS_PATH, [])
    reviews = load_json(REVIEWS_PATH, [])
    agent_memory = load_json(AGENT_MEMORY_PATH, [])
    plan_task_state = load_json(PLAN_TASK_STATE_PATH, [])
    hint_logs = load_json(HINT_LOG_PATH, [])
    user_learning_profile = load_user_learning_profile()

    if not isinstance(current_plan, dict):
        current_plan = {}
    if not isinstance(problem_bank, dict):
        problem_bank = {}
    if not isinstance(records, list):
        records = []
    if not isinstance(reviews, list):
        reviews = []
    if not isinstance(agent_memory, list):
        agent_memory = []
    if not isinstance(plan_task_state, list):
        plan_task_state = []
    if not isinstance(hint_logs, list):
        hint_logs = []
    if not isinstance(user_learning_profile, dict):
        user_learning_profile = {}

    next_week = _next_week_number(current_plan)
    next_start = _next_start_date(current_plan)
    learning_analysis = analyze_learning_patterns(
        records=records,
        problem_bank=problem_bank,
        reviews=reviews
    )
    learner_profile = analyze_user_level(
        records,
        problem_bank,
        reviews
    )
    plan_scaffold = build_plan_scaffold(
        records,
        problem_bank,
        learner_profile,
        reviews
    )
    coaching_brief = build_coaching_brief(
        learner_profile,
        learning_analysis,
        reviews,
        hint_logs
    )
    today_value = date.today()
    review_context = []
    for item in reviews:
        if not isinstance(item, dict) or item.get("done"):
            continue
        review_date = str(item.get("next_review_date", "")).strip()
        try:
            parsed_review_date = datetime.strptime(
                review_date,
                "%Y-%m-%d"
            ).date()
            due_status = (
                "overdue"
                if parsed_review_date < today_value
                else "due_today"
                if parsed_review_date == today_value
                else "scheduled_future"
            )
        except ValueError:
            due_status = "unknown"
        review_context.append({
            **item,
            "due_status": due_status
        })
    if with_rag:
        plan_rag_context = build_plan_rag_context(
            current_plan,
            plan_scaffold,
            learning_analysis,
            learner_profile,
            review_context,
            records,
            use_enhanced_memory=use_enhanced_memory,
        )
    else:
        plan_rag_context = {
            "documents": [],
            "context_text": "RAG context disabled for this experiment.",
            "matched_count": 0,
            "total_candidate_count": 0,
            "mode": "disabled",
            "embedding_model": "",
            "embedding_error": "",
            "evidence": [],
            "use_enhanced_memory": False,
            "enhanced_memory_available": False,
        }
    context = {
        "current_date": str(today_value),
        "current_week_plan": current_plan,
        "problem_bank": problem_bank,
        "recent_records": records[-50:],
        "pending_reviews": review_context,
        "recent_agent_memory": agent_memory[-7:],
        "recent_hint_logs": hint_logs[-20:],
        "recent_stage_summaries": get_recent_stage_summaries(
            plan_task_state
        ),
        "user_learning_profile": user_learning_profile,
        "automatic_learning_analysis": learning_analysis,
        "coaching_brief": coaching_brief,
        "learner_profile": learner_profile,
        "curriculum_scaffold": plan_scaffold,
        "rag_context": {
            "mode": plan_rag_context.get("mode", ""),
            "embedding_model": plan_rag_context.get("embedding_model", ""),
            "matched_count": plan_rag_context.get("matched_count", 0),
            "total_candidate_count": plan_rag_context.get(
                "total_candidate_count",
                0
            ),
            "embedding_error": plan_rag_context.get("embedding_error", ""),
            "use_enhanced_memory": bool(plan_rag_context.get("use_enhanced_memory")),
            "enhanced_memory_available": bool(plan_rag_context.get("enhanced_memory_available")),
            "evidence": plan_rag_context.get("evidence", [])
        },
        "rule_plan_reference": generate_next_week_plan_draft()
    }

    selected_prompt_version = _normalize_prompt_version(prompt_version)
    selected_prompt_template = _prompt_template_name(selected_prompt_version)
    output_schema = load_json(WEEK_PLAN_SCHEMA_PATH, {})
    prompt_template = load_prompt_template(selected_prompt_template)
    user_prompt = render_prompt(
        prompt_template,
        {
            "current_plan": _json_text(current_plan),
            "records_summary": _summarize_records(records, problem_bank),
            "reviews_summary": _summarize_reviews(review_context),
            "problem_bank_summary": _summarize_problem_bank(
                problem_bank,
                plan_scaffold,
                records
            ),
            "agent_memory_summary": _summarize_agent_memory(
                agent_memory[-7:],
                hint_logs[-20:],
                coaching_brief
            )
            + "\n\n【用户长期反馈偏好】\n"
            + format_user_learning_profile_for_prompt(user_learning_profile),
            "rag_context": plan_rag_context.get(
                "context_text",
                "暂无 RAG 检索结果。"
            ),
            "full_context": _json_text(context, max_chars=7000),
            "output_schema": _json_text(output_schema, max_chars=3000)
        }
    )
    system_prompt = (
        "你是 LeetCoach 的计划生成模块。"
        "必须严格遵守用户 prompt 中的 Schema 和约束，"
        "只输出 JSON，不输出题解、代码或 Markdown。"
    )

    raw_text = ""
    parsed_plan = None
    schema_result = {"valid": False, "score": 0, "issues": ["尚未调用模型"]}
    eval_result = {"score": 0, "issues": ["尚未评估"]}
    raw_eval_result = {}
    raw_success = False
    parsed_success = False
    schema_valid = False
    raw_score = None
    fallback_used = False
    fallback_reason = ""
    error_type = ""
    error_message = ""
    model_name = ""
    start_time = time.time()

    try:
        from llm_client import LLMClient

        client = LLMClient(
            timeout=_env_int("AI_PLAN_TIMEOUT_SECONDS", 45),
            model_env_key="LLM_MODEL_STRONG"
        )
        model_name = client.model
        last_error = None
        eval_context = _build_eval_context(
            context,
            current_plan,
            records,
            reviews,
            problem_bank,
            learning_analysis,
            learner_profile
        )
        fallback_score_threshold = _env_int("AI_PLAN_FALLBACK_SCORE", 60)
        max_attempts = max(1, _env_int("AI_PLAN_MAX_ATTEMPTS", 2))
        retry_feedback = ""
        plan = None
        for attempt in range(max_attempts):
            try:
                attempt_prompt = user_prompt
                if retry_feedback:
                    attempt_prompt += (
                        "\n\n上一次计划未通过质量检查，请修正以下问题。"
                        "不要改变课程骨架题号，不要输出解释，只返回 JSON：\n"
                        + retry_feedback
                    )
                raw_text = client.chat(
                    user_prompt=attempt_prompt,
                    system_prompt=system_prompt,
                    temperature=0.15,
                    max_tokens=_env_int("AI_PLAN_MAX_TOKENS", 3200),
                    enable_thinking=False
                )
                raw_success = bool(str(raw_text or "").strip())
                parsed_plan = parse_ai_plan_response(raw_text)
                if parsed_plan is None:
                    raise ValueError("AI 返回内容不是合法计划 JSON")
                parsed_success = True

                schema_result = validate_week_plan_output(parsed_plan)
                schema_valid = bool(schema_result.get("valid", False))
                if not schema_result["valid"]:
                    raise ValueError(
                        "AI 计划未通过 Schema 校验："
                        + "；".join(schema_result["issues"])
                    )

                parsed_plan["generated_by"] = "ai_plan_generator"
                parsed_plan["learner_level"] = learner_profile["level"]
                parsed_plan["learner_level_label"] = learner_profile["label"]
                parsed_plan["learner_level_reason"] = learner_profile["guidance"]
                parsed_plan = _merge_ai_plan_with_scaffold(
                    parsed_plan,
                    plan_scaffold
                )
                plan = validate_ai_week_plan(parsed_plan)
                plan = _enforce_plan_hard_rules(
                    plan,
                    current_plan,
                    records
                )
                eval_result = evaluate_ai_plan(
                    plan,
                    eval_context,
                    save=False
                )
                raw_eval_result = eval_result
                raw_score = eval_result.get("score")
                quality = assess_plan_quality(
                    plan,
                    plan_scaffold,
                    problem_bank
                )
                has_eval_errors = bool(eval_result.get("errors", []))
                if (
                    eval_result.get("score", 0) >= fallback_score_threshold
                    and not has_eval_errors
                    and quality.get("passed")
                ):
                    break

                issues = (
                    eval_result.get("errors", [])
                    + eval_result.get("warnings", [])
                    + eval_result.get("issues", [])
                    + quality.get("issues", [])
                )
                retry_feedback = "\n".join(
                    f"- {issue}" for issue in issues[:8]
                ) or "- 计划质量评分不足，请严格遵守硬规则。"
                last_error = ValueError(
                    f"AI 计划质量不足，第 {attempt + 1} 次："
                    + retry_feedback.replace("\n", "；")
                )
                parsed_plan = None
            except Exception as error:
                last_error = error
                parsed_plan = None
                retry_feedback = (
                    "- " + str(error)
                    + "\n- 请返回严格 JSON，并遵守 week、title、days 和题量约束。"
                )
        if parsed_plan is None or plan is None:
            raise last_error or RuntimeError("AI 计划生成失败")
    except Exception as error:
        fallback_used = True
        error_type = type(error).__name__
        error_message = str(error)
        fallback_reason = error_message
        plan = _build_scaffold_fallback(
            current_plan,
            plan_scaffold,
            learner_profile
        )
        plan["ai_generation_error"] = error_message
        eval_context = _build_eval_context(
            context,
            current_plan,
            records,
            reviews,
            problem_bank,
            learning_analysis,
            learner_profile
        )
        eval_result = evaluate_ai_plan(plan, eval_context, save=False)

    latency_seconds = round(time.time() - start_time, 3)

    plan["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plan["generated_for_week"] = current_plan.get("week", "")
    plan["generation_trigger"] = trigger
    plan["context_fingerprint"] = context_fingerprint
    if trigger in {"week_completed", "initial_setup"}:
        plan["start_date"] = str(date.today())
    plan = _correct_future_review_wording(plan, reviews)
    quality = assess_plan_quality(plan, plan_scaffold, problem_bank)
    if not quality["passed"]:
        original_error = plan.get("ai_generation_error", "")
        fallback_used = True
        error_type = error_type or "QualityCheckFailed"
        plan = _build_scaffold_fallback(
            current_plan,
            plan_scaffold,
            learner_profile
        )
        plan["ai_generation_error"] = (
            original_error
            or "AI 计划未通过质量检查："
            + "；".join(quality["issues"])
        )
        error_message = plan["ai_generation_error"]
        fallback_reason = error_message
        plan["generated_at"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        plan["generated_for_week"] = current_plan.get("week", "")
        plan["generation_trigger"] = trigger
        plan["context_fingerprint"] = context_fingerprint
        if trigger in {"week_completed", "initial_setup"}:
            plan["start_date"] = str(date.today())
        quality = assess_plan_quality(
            plan,
            plan_scaffold,
            problem_bank
        )
    if fallback_used and not fallback_reason:
        fallback_reason = (
            error_message
            or plan.get("ai_generation_error", "")
            or "未知原因：生成流程标记了 fallback，但未返回具体原因，请检查 ai_plan_generator.py"
        )
    eval_context = _build_eval_context(
        context,
        current_plan,
        records,
        reviews,
        problem_bank,
        learning_analysis,
        learner_profile
    )
    eval_result = evaluate_ai_plan(plan, eval_context, save=True)
    plan["quality_check"] = quality
    plan["llm_schema_check"] = schema_result
    plan["llm_eval_result"] = eval_result
    plan["llm_raw_eval_result"] = raw_eval_result
    plan["llm_raw_success"] = raw_success
    plan["llm_parsed_success"] = parsed_success
    plan["llm_schema_valid"] = schema_valid
    plan["llm_raw_score"] = raw_score
    plan["llm_final_score"] = eval_result.get("score")
    plan["llm_fallback_used"] = fallback_used
    plan["llm_fallback_reason"] = fallback_reason if fallback_used else ""
    plan["prompt_version"] = selected_prompt_template
    plan["prompt_semver"] = selected_prompt_version
    if fallback_used:
        plan["llm_lab_notice"] = "AI 输出未通过校验，已使用规则版保守计划草案。"
    elif eval_result.get("score", 0) < 80:
        plan["llm_lab_notice"] = "AI 计划已生成，但存在若干质量提醒。"
    else:
        plan["llm_lab_notice"] = "AI 计划已生成并通过主要质量检查。"
    plan["rag_context"] = {
        "mode": plan_rag_context.get("mode", ""),
        "embedding_model": plan_rag_context.get("embedding_model", ""),
        "matched_count": plan_rag_context.get("matched_count", 0),
        "total_candidate_count": plan_rag_context.get(
            "total_candidate_count",
            0
        ),
        "embedding_error": plan_rag_context.get("embedding_error", ""),
        "use_enhanced_memory": bool(plan_rag_context.get("use_enhanced_memory")),
        "enhanced_memory_available": bool(plan_rag_context.get("enhanced_memory_available")),
        "evidence": plan_rag_context.get("evidence", [])[:8]
    }
    plan["use_enhanced_memory"] = bool(use_enhanced_memory)
    plan["enhanced_memory_available"] = bool(plan_rag_context.get("enhanced_memory_available"))
    rag_trace = {}
    rag_retrieved_count = 0
    rag_used_count = 0
    rag_used_doc_ids = []
    if with_rag and plan_rag_context.get("documents"):
        try:
            rag_trace = build_rag_trace(
                plan_rag_context.get("query", ""),
                plan_rag_context,
                plan,
            )
            save_rag_trace_log("ai_plan_generation", rag_trace)
            rag_retrieved_count = rag_trace.get("retrieved_count", 0)
            rag_used_count = rag_trace.get("used_count", 0)
            rag_used_doc_ids = [
                item.get("doc_id", "")
                for item in rag_trace.get("evidence_items", [])
                if item.get("used_in_plan")
            ]
            plan["rag_trace"] = rag_trace
            plan["rag_trace_summary"] = rag_trace.get("summary", "")
            plan["rag_retrieved_count"] = rag_retrieved_count
            plan["rag_used_count"] = rag_used_count
            plan["rag_used_doc_ids"] = rag_used_doc_ids
            plan["rag_personalized_retrieved_count"] = rag_trace.get("personalized_retrieved_count", 0)
            plan["rag_personalized_used_count"] = rag_trace.get("personalized_used_count", 0)
            plan["rag_personalized_usage_rate"] = rag_trace.get("personalized_usage_rate", 0)
            plan["rag_background_retrieved_count"] = rag_trace.get("background_retrieved_count", 0)
            plan["rag_background_used_count"] = rag_trace.get("background_used_count", 0)
            plan["rag_background_usage_rate"] = rag_trace.get("background_usage_rate", 0)
            plan["enhanced_memory_retrieved_count"] = rag_trace.get("enhanced_memory_retrieved_count", 0)
            plan["enhanced_memory_used_count"] = rag_trace.get("enhanced_memory_used_count", 0)
            plan["enhanced_memory_usage_rate"] = rag_trace.get("enhanced_memory_usage_rate", 0)
            plan["used_enhanced_doc_ids"] = rag_trace.get("used_enhanced_doc_ids", [])
        except Exception as error:
            plan["rag_trace_summary"] = f"RAG 证据链生成失败：{error}"
            plan["rag_retrieved_count"] = plan_rag_context.get("matched_count", 0)
            plan["rag_used_count"] = 0
            plan["rag_used_doc_ids"] = []
            plan["enhanced_memory_used_count"] = 0
            plan["used_enhanced_doc_ids"] = []
    else:
        plan["rag_trace_summary"] = ""
        plan["rag_retrieved_count"] = 0
        plan["rag_used_count"] = 0
        plan["rag_used_doc_ids"] = []
        plan["enhanced_memory_used_count"] = 0
        plan["used_enhanced_doc_ids"] = []
    try:
        log_llm_call({
            "task": "ai_plan_generation",
            "prompt_name": PLAN_PROMPT_NAME,
            "prompt_version": selected_prompt_version,
            "model": model_name,
            "input_summary": {
                "current_week": current_plan.get("week", ""),
                "next_week": next_week,
                "records_count": len(records),
                "reviews_count": len(reviews),
                "learner_level": learner_profile.get("level", ""),
                "rag_mode": plan_rag_context.get("mode", ""),
                "rag_matched_count": plan_rag_context.get("matched_count", 0),
                "rag_candidate_count": plan_rag_context.get(
                    "total_candidate_count",
                    0
                ),
                "with_rag": bool(with_rag),
                "use_enhanced_memory": bool(use_enhanced_memory),
                "enhanced_memory_available": bool(plan.get("enhanced_memory_available")),
                "rag_context_count": plan_rag_context.get("matched_count", 0),
                "rag_retrieved_count": plan.get("rag_retrieved_count", 0),
                "rag_used_count": plan.get("rag_used_count", 0),
                "enhanced_memory_count": plan.get("enhanced_memory_retrieved_count", 0),
                "enhanced_memory_used_count": plan.get("enhanced_memory_used_count", 0),
                "trigger": trigger
            },
            "rag_retrieved_count": plan.get("rag_retrieved_count", 0),
            "rag_used_count": plan.get("rag_used_count", 0),
            "rag_used_doc_ids": plan.get("rag_used_doc_ids", []),
            "use_enhanced_memory": bool(use_enhanced_memory),
            "enhanced_memory_available": bool(plan.get("enhanced_memory_available")),
            "enhanced_memory_count": plan.get("enhanced_memory_retrieved_count", 0),
            "enhanced_memory_used_count": plan.get("enhanced_memory_used_count", 0),
            "used_enhanced_doc_ids": plan.get("used_enhanced_doc_ids", []),
            "prompt_preview": user_prompt,
            "raw_output": raw_text,
            "parsed_success": parsed_success,
            "schema_valid": schema_valid,
            "eval_score": eval_result.get("score", ""),
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason if fallback_used else "",
            "error_type": error_type,
            "error_message": error_message,
            "latency_seconds": latency_seconds
        })
    except Exception:
        pass
    if save_draft:
        return save_week_plan_next(plan)
    return plan


def format_ai_week_plan_next(plan):
    if not isinstance(plan, dict):
        return "目前还没有下一阶段计划草案。"

    plan = validate_ai_week_plan(plan)
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    if not isinstance(problem_bank, dict):
        problem_bank = {}

    lines = [
        "===== AI 下一阶段计划草案 =====",
        "",
        f"计划：Week {plan['week']} - {plan['title']}",
        (
            f"建议开始日期：{plan['start_date']} "
            "（确认后从确认当天立即启用）"
        ),
        (
            f"学习阶段：{plan.get('learner_level_label', '未判断')}"
            f"（{plan.get('learner_level_reason', '根据提交记录综合判断')}）"
        ),
        "",
        "生成原因：",
        plan["reason"],
        "",
        "推荐重点："
    ]
    focus = plan.get("recommended_focus", [])
    if focus:
        lines.extend(f"- {item}" for item in focus)
    else:
        lines.append("- 暂无明确重点")

    lines.extend([
        "",
        f"本周主题：{plan.get('weekly_theme', plan['title'])}",
        f"本周目标：{plan.get('weekly_goal', '暂无')}",
        (
            "自适应依据："
            f"{plan.get('adaptive_reason', '根据最近学习记录调整')}"
        ),
        (
            "计划质量检查："
            f"{plan.get('quality_check', {}).get('score', '未检查')} 分"
        ),
    ])

    quality_check = plan.get("quality_check", {})
    if isinstance(quality_check, dict):
        if plan.get("llm_lab_notice"):
            lines.append("LLM Lab： " + str(plan.get("llm_lab_notice")))
        lines.append(
            "质量状态："
            + ("通过" if quality_check.get("passed") else "需要关注")
        )
        excluded = quality_check.get("excluded_completed_as_new", [])
        if excluded:
            lines.append(
                "已完成题排除为新题："
                + "、".join(str(item) for item in excluded[:8])
            )
        issues = quality_check.get("issues", [])
        if issues:
            lines.append("质量问题：")
            lines.extend(f"- {issue}" for issue in issues[:5])

    eval_result = plan.get("llm_eval_result", {})
    if isinstance(eval_result, dict) and eval_result.get("issues"):
        lines.append("AI 评估提示：")
        lines.extend(
            f"- {issue}"
            for issue in eval_result.get("issues", [])[:5]
        )

    lines.extend([
        "生成方式："
        + (
            "规则兜底"
            if plan.get("llm_fallback_used")
            else "AI 生成并通过校验"
        ),
        "",
        "难度分层：",
        (
            "必须独立写出："
            + "、".join(plan.get("must_master", []))
            if plan.get("must_master")
            else "必须独立写出：暂无"
        ),
        (
            "看提示能写出："
            + "、".join(plan.get("guided_mastery", []))
            if plan.get("guided_mastery")
            else "看提示能写出：暂无"
        ),
        (
            "第一遍理解即可："
            + "、".join(plan.get("understand_only", []))
            if plan.get("understand_only")
            else "第一遍理解即可：暂无"
        )
    ])

    for day_index in range(1, 8):
        day = plan["days"][str(day_index)]
        lines.extend([
            "",
            (
                f"Day {day_index}：{day.get('topic', '')}"
                f" | {day['goal']}"
            ),
            f"安排原因：{day['reason']}",
            f"掌握要求：{day.get('mastery_requirement', '未指定')}",
            "题目："
        ])
        if not day["problems"]:
            lines.append("- 无新题，按目标完成复习或总结")
        else:
            for problem_id in day["problems"]:
                problem = problem_bank.get(problem_id, {})
                if isinstance(problem, dict) and problem:
                    lines.append(
                        f"- {problem_id} {problem.get('title', '未知题目')}"
                    )
                else:
                    lines.append(
                        f"- {problem_id}（题库中暂无该题详细信息）"
                    )
        review_ids = day.get("review_problems", [])
        if review_ids:
            lines.append(f"复习题：{'、'.join(review_ids)}")
        steps = day.get("execution_steps", [])
        if steps:
            lines.append("执行步骤：")
            lines.extend(
                f"  {index}. {step}"
                for index, step in enumerate(steps, start=1)
            )
        if day.get("summary_focus"):
            lines.append(f"总结重点：{day['summary_focus']}")

    lines.extend([
        "",
        "本周最低验收标准：",
        plan.get("minimum_acceptance", "暂无"),
        "",
        "下周过渡逻辑：",
        plan.get("transition_logic", "暂无")
    ])

    if plan.get("generated_by") in {
        "rule_fallback",
        "curriculum_fallback"
    }:
        lines.extend([
            "",
            "提示：AI 计划生成失败，已使用规则版保守计划草案。"
        ])

    return "\n".join(lines)


def apply_week_plan_next():
    if not NEXT_PLAN_PATH.exists():
        return {
            "success": False,
            "message": "计划草案不存在，请先生成下一阶段计划。"
        }

    plan = load_week_plan_next()
    if plan is None:
        return {
            "success": False,
            "message": "计划草案格式无效，无法应用。"
        }

    current_plan = load_json(CURRENT_PLAN_PATH, {})
    if not isinstance(current_plan, dict):
        current_plan = {}

    try:
        current_week = int(current_plan.get("week", 0))
        draft_week = int(plan.get("week", 0))
    except (TypeError, ValueError):
        return {
            "success": False,
            "message": "当前计划或计划草案的周次无效，无法应用。"
        }

    if current_week and draft_week != current_week + 1:
        return {
            "success": False,
            "message": (
                f"计划草案是 Week {draft_week}，当前计划是 Week "
                f"{current_week}，只能应用紧接当前周的计划。"
            )
        }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = (
        CURRENT_PLAN_PATH.parent
        / f"week_plan_backup_{timestamp}.json"
    )
    archive_path = (
        PLAN_ARCHIVE_DIR
        / f"week_plan_week_{draft_week}_{timestamp}.json"
    )
    temporary_path = CURRENT_PLAN_PATH.with_suffix(".json.tmp")
    applied_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    applied_plan = dict(plan)
    planned_start_date = str(plan.get("start_date", "")).strip()
    applied_plan["planned_start_date"] = planned_start_date
    applied_plan["start_date"] = str(date.today())
    applied_plan["activated_at"] = applied_at
    applied_plan["activation_mode"] = "immediate_on_confirmation"
    current_replaced = False

    try:
        CURRENT_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLAN_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        with open(temporary_path, "w", encoding="utf-8") as f:
            json.dump(applied_plan, f, ensure_ascii=False, indent=2)

        if CURRENT_PLAN_PATH.exists():
            shutil.copy2(CURRENT_PLAN_PATH, backup_path)

        archived_plan = dict(applied_plan)
        archived_plan["archive_status"] = "applied"
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(archived_plan, f, ensure_ascii=False, indent=2)

        temporary_path.replace(CURRENT_PLAN_PATH)
        current_replaced = True
    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        if not current_replaced:
            try:
                archive_path.unlink(missing_ok=True)
            except OSError:
                pass
        return {
            "success": False,
            "message": f"应用计划失败：{error}"
        }

    cleanup_warning = ""
    try:
        NEXT_PLAN_PATH.unlink()
    except OSError as error:
        cleanup_warning = (
            f"计划已应用，但待确认草案文件清理失败：{error}"
        )
    if not clear_plan_review_state():
        reminder_warning = "计划草案提醒状态清理失败。"
        cleanup_warning = (
            f"{cleanup_warning} {reminder_warning}".strip()
        )

    return {
        "success": True,
        "message": (
            f"Week {draft_week} 计划已从今天立即启用。"
            "旧计划已备份，已确认草案已归档。"
        ),
        "week": draft_week,
        "backup_path": str(backup_path.relative_to(BASE_DIR)),
        "archive_path": str(archive_path.relative_to(BASE_DIR)),
        "activated_at": applied_at,
        "warning": cleanup_warning
    }
