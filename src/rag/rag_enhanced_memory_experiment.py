import json
from datetime import datetime
from pathlib import Path

from ai.ai_plan_generator import generate_ai_week_plan_next


from app_paths import BASE_DIR
DATA_DIR = BASE_DIR / "data"
ENHANCED_MEMORY_PATH = DATA_DIR / "rag_personalized_memory_enhanced.json"
RESULTS_PATH = DATA_DIR / "rag_enhanced_memory_experiment_results.json"
CANDIDATES_PATH = DATA_DIR / "rag_enhanced_memory_candidates.json"


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_json_list(path, item, limit=100):
    data = _load_json(path, [])
    if not isinstance(data, list):
        data = []
    data.append(item)
    _save_json(path, data[-limit:])


def _as_list(value):
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


def _score(plan):
    if not isinstance(plan, dict):
        return 0
    value = plan.get("llm_final_score")
    if value is None:
        value = (plan.get("llm_eval_result") or {}).get("score", 0)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def _evidence_items(plan):
    trace = plan.get("rag_trace", {}) if isinstance(plan, dict) else {}
    if not isinstance(trace, dict):
        return []
    items = trace.get("evidence_items", [])
    return items if isinstance(items, list) else []


def _used_items(plan):
    return [
        item for item in _evidence_items(plan)
        if isinstance(item, dict) and item.get("used_in_plan")
    ]


def _problem_bank_used_share(plan):
    used_items = _used_items(plan)
    if not used_items:
        return 0
    problem_bank_used = [
        item for item in used_items
        if item.get("doc_type") == "problem_bank"
    ]
    return round(len(problem_bank_used) / len(used_items), 4)


def _summarize_plan(plan):
    plan = plan if isinstance(plan, dict) else {}
    eval_result = plan.get("llm_eval_result", {})
    if not isinstance(eval_result, dict):
        eval_result = {}
    retrieved_count = int(plan.get("rag_retrieved_count", 0) or 0)
    used_count = int(plan.get("rag_used_count", 0) or 0)
    personalized_retrieved = int(plan.get("rag_personalized_retrieved_count", 0) or 0)
    personalized_used = int(plan.get("rag_personalized_used_count", 0) or 0)
    background_retrieved = int(plan.get("rag_background_retrieved_count", 0) or 0)
    background_used = int(plan.get("rag_background_used_count", 0) or 0)
    enhanced_retrieved = int(plan.get("enhanced_memory_retrieved_count", 0) or 0)
    enhanced_used = int(plan.get("enhanced_memory_used_count", 0) or 0)
    return {
        "score": _score(plan),
        "fallback_used": bool(plan.get("llm_fallback_used")),
        "rag_retrieved_count": retrieved_count,
        "rag_used_count": used_count,
        "rag_usage_rate": round(used_count / retrieved_count, 4) if retrieved_count else 0,
        "personalized_retrieved_count": personalized_retrieved,
        "personalized_used_count": personalized_used,
        "personalized_usage_rate": (
            round(personalized_used / personalized_retrieved, 4)
            if personalized_retrieved else 0
        ),
        "background_retrieved_count": background_retrieved,
        "background_used_count": background_used,
        "background_usage_rate": (
            round(background_used / background_retrieved, 4)
            if background_retrieved else 0
        ),
        "enhanced_memory_available": bool(plan.get("enhanced_memory_available")),
        "enhanced_memory_retrieved_count": enhanced_retrieved,
        "enhanced_memory_used_count": enhanced_used,
        "enhanced_memory_usage_rate": (
            round(enhanced_used / enhanced_retrieved, 4)
            if enhanced_retrieved else 0
        ),
        "problem_bank_used_share": _problem_bank_used_share(plan),
        "used_doc_ids": plan.get("rag_used_doc_ids", []) or [],
        "used_enhanced_doc_ids": plan.get("used_enhanced_doc_ids", []) or [],
        "errors": eval_result.get("errors", []) or [],
        "warnings": eval_result.get("warnings", []) or [],
        "infos": eval_result.get("infos", []) or [],
        "plan_title": (
            f"Week {plan.get('week', '')} - {plan.get('title', '')}"
        ).strip(" -"),
    }


def _winner_tuple(item, prefer_enhanced=False):
    fallback_penalty = -1 if item.get("fallback_used") else 0
    score = float(item.get("score") or 0)
    personalized_usage = float(item.get("personalized_usage_rate") or 0)
    enhanced_used = float(item.get("enhanced_memory_used_count") or 0)
    problem_bank_share = float(item.get("problem_bank_used_share") or 0)
    warning_count = len(_as_list(item.get("warnings", [])))
    prefer = 0.1 if prefer_enhanced else 0
    return (
        fallback_penalty,
        score,
        personalized_usage,
        enhanced_used,
        -problem_bank_share,
        -warning_count,
        prefer,
    )


def _choose_winner(normal, enhanced):
    normal_rank = _winner_tuple(normal)
    enhanced_rank = _winner_tuple(enhanced, prefer_enhanced=True)
    if enhanced_rank > normal_rank:
        reasons = []
        if enhanced.get("fallback_used") != normal.get("fallback_used"):
            reasons.append("增强记忆 RAG 未触发兜底，而普通 RAG 触发了兜底")
        if enhanced.get("score", 0) > normal.get("score", 0):
            reasons.append("增强记忆 RAG 评分更高")
        if enhanced.get("personalized_usage_rate", 0) > normal.get("personalized_usage_rate", 0):
            reasons.append("个性化证据使用率更高")
        if enhanced.get("enhanced_memory_used_count", 0):
            reasons.append(
                f"有 {enhanced.get('enhanced_memory_used_count')} 条增强记忆被计划引用"
            )
        if enhanced.get("problem_bank_used_share", 0) < normal.get("problem_bank_used_share", 0):
            reasons.append("problem_bank 使用占比下降")
        return (
            "enhanced_memory_rag",
            "；".join(reasons) or "增强记忆 RAG 在综合排序中表现更好。",
        )
    if normal_rank > enhanced_rank:
        reasons = []
        if normal.get("fallback_used") != enhanced.get("fallback_used"):
            reasons.append("普通 RAG 未触发兜底，而增强记忆 RAG 触发了兜底")
        if normal.get("score", 0) > enhanced.get("score", 0):
            reasons.append("普通 RAG 评分更高")
        if normal.get("personalized_usage_rate", 0) >= enhanced.get("personalized_usage_rate", 0):
            reasons.append("增强记忆没有提升个性化证据使用率")
        return (
            "normal_rag",
            "；".join(reasons) or "普通 RAG 在综合排序中表现更稳。",
        )
    return (
        "tie",
        "两种模式结果接近，当前样本无法证明增强记忆带来稳定提升。",
    )


def run_enhanced_memory_ab_experiment():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    enhanced_memory_available = (
        ENHANCED_MEMORY_PATH.exists()
        and bool(_load_json(ENHANCED_MEMORY_PATH, []))
    )

    normal_plan = generate_ai_week_plan_next(
        trigger="enhanced_memory_ab_normal",
        context_fingerprint=f"enhanced_memory_ab_{timestamp}_normal",
        prompt_version="v1",
        save_draft=False,
        with_rag=True,
        use_enhanced_memory=False,
    )
    enhanced_plan = generate_ai_week_plan_next(
        trigger="enhanced_memory_ab_enhanced",
        context_fingerprint=f"enhanced_memory_ab_{timestamp}_enhanced",
        prompt_version="v1",
        save_draft=False,
        with_rag=True,
        use_enhanced_memory=True,
    )

    normal_summary = _summarize_plan(normal_plan)
    enhanced_summary = _summarize_plan(enhanced_plan)
    enhanced_summary["enhanced_memory_available"] = bool(enhanced_memory_available)
    winner, winner_reason = _choose_winner(normal_summary, enhanced_summary)

    result = {
        "timestamp": timestamp,
        "task": "rag_enhanced_memory_ab_experiment",
        "enhanced_memory_available": bool(enhanced_memory_available),
        "results": {
            "normal_rag": normal_summary,
            "enhanced_memory_rag": enhanced_summary,
        },
        "winner": winner,
        "winner_reason": winner_reason,
    }
    _append_json_list(RESULTS_PATH, result)
    _append_json_list(
        CANDIDATES_PATH,
        {
            "timestamp": timestamp,
            "normal_rag": normal_plan,
            "enhanced_memory_rag": enhanced_plan,
        },
        limit=30,
    )
    return result


def _format_bool(value):
    return "是" if value else "否"


def _format_rate(value):
    try:
        return f"{float(value or 0) * 100:.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _format_mode_block(title, item):
    item = item if isinstance(item, dict) else {}
    lines = [
        f"{title}：",
        f"- 计划标题：{item.get('plan_title', '')}",
        f"- 评分：{item.get('score', 0)}",
        f"- fallback：{_format_bool(item.get('fallback_used'))}",
        f"- RAG 使用率：{_format_rate(item.get('rag_usage_rate'))}",
        f"- 个性化证据使用数：{item.get('personalized_used_count', 0)}",
        f"- 个性化证据使用率：{_format_rate(item.get('personalized_usage_rate'))}",
        f"- 背景证据使用数：{item.get('background_used_count', 0)}",
        f"- 背景证据使用率：{_format_rate(item.get('background_usage_rate'))}",
        f"- problem_bank 使用占比：{_format_rate(item.get('problem_bank_used_share'))}",
        f"- 严重问题：{len(_as_list(item.get('errors', [])))}",
        f"- 质量提醒：{len(_as_list(item.get('warnings', [])))}",
    ]
    if "enhanced_memory_used_count" in item:
        lines.extend([
            f"- enhanced memory 检索数：{item.get('enhanced_memory_retrieved_count', 0)}",
            f"- enhanced memory 使用数：{item.get('enhanced_memory_used_count', 0)}",
            f"- enhanced memory 使用率：{_format_rate(item.get('enhanced_memory_usage_rate'))}",
        ])
    return lines


def format_enhanced_memory_ab_result(result):
    if not isinstance(result, dict):
        return "暂无增强个性化记忆 RAG A/B 实验结果。"
    results = result.get("results", {})
    if not isinstance(results, dict):
        results = {}
    lines = [
        "===== 增强个性化记忆 RAG A/B 实验 =====",
        "",
        f"实验时间：{result.get('timestamp', '')}",
        f"增强记忆可用：{_format_bool(result.get('enhanced_memory_available'))}",
        "",
    ]
    lines.extend(_format_mode_block("普通 RAG", results.get("normal_rag", {})))
    lines.append("")
    lines.extend(_format_mode_block("增强记忆 RAG", results.get("enhanced_memory_rag", {})))
    lines.extend([
        "",
        f"推荐模式：{result.get('winner', '')}",
        "",
        "推荐原因：",
        result.get("winner_reason", ""),
        "",
        "说明：本实验只用于分析，不会应用任何计划，也不会改变默认 RAG 策略。",
    ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    experiment = run_enhanced_memory_ab_experiment()
    print(format_enhanced_memory_ab_result(experiment))
