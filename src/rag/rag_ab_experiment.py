import json
from datetime import datetime
from pathlib import Path

from ai.ai_plan_generator import generate_ai_week_plan_next
from rag.rag_engine import load_last_rag_debug


from app_paths import BASE_DIR
AB_RESULTS_PATH = BASE_DIR / "data" / "rag_ab_experiment_results.json"
AB_CANDIDATES_PATH = BASE_DIR / "data" / "rag_ab_candidates.json"


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


def _plan_text(plan):
    if not isinstance(plan, dict):
        return ""
    parts = [
        str(plan.get("title", "")),
        str(plan.get("reason", "")),
        " ".join(str(item) for item in plan.get("recommended_focus", []) or []),
    ]
    days = plan.get("days", {})
    if isinstance(days, dict):
        for day in days.values():
            if not isinstance(day, dict):
                continue
            parts.append(str(day.get("goal", "")))
            parts.append(str(day.get("reason", "")))
            parts.extend(str(item) for item in day.get("problems", []) or [])
    return "\n".join(parts)


def _rag_terms(rag_context):
    terms = set()
    if not isinstance(rag_context, dict):
        return terms
    for document in rag_context.get("documents", []) or []:
        if not isinstance(document, dict):
            continue
        for key in ("problem_id", "title", "source"):
            value = str(document.get(key, "") or "").strip()
            if value:
                terms.add(value)
        metadata = document.get("metadata", {})
        if isinstance(metadata, dict):
            for key in ("mistake_type", "topics", "difficulty"):
                value = metadata.get(key)
                if isinstance(value, list):
                    terms.update(str(item) for item in value if item)
                elif value:
                    terms.add(str(value))
    return {item for item in terms if item}


def plan_uses_historical_context(plan, rag_context):
    text = _plan_text(plan)
    if not text.strip():
        return False
    for term in _rag_terms(rag_context):
        if term and term in text:
            return True
    markers = ["历史", "之前", "曾经", "过去", "相似问题", "复盘", "错因"]
    return any(marker in text for marker in markers)


def _summarize_plan(plan, rag_context=None):
    plan = plan if isinstance(plan, dict) else {}
    eval_result = plan.get("llm_eval_result", {})
    if not isinstance(eval_result, dict):
        eval_result = {}
    retrieved_count = int(plan.get("rag_retrieved_count", 0) or 0)
    used_count = int(plan.get("rag_used_count", 0) or 0)
    usage_rate = round(used_count / retrieved_count, 4) if retrieved_count else 0
    personalized_retrieved_count = int(
        plan.get("rag_personalized_retrieved_count", 0) or 0
    )
    personalized_used_count = int(
        plan.get("rag_personalized_used_count", 0) or 0
    )
    background_retrieved_count = int(
        plan.get("rag_background_retrieved_count", 0) or 0
    )
    background_used_count = int(
        plan.get("rag_background_used_count", 0) or 0
    )
    personalized_usage_rate = (
        round(personalized_used_count / personalized_retrieved_count, 4)
        if personalized_retrieved_count else 0
    )
    background_usage_rate = (
        round(background_used_count / background_retrieved_count, 4)
        if background_retrieved_count else 0
    )
    personalized_evidence_share = (
        round(personalized_retrieved_count / retrieved_count, 4)
        if retrieved_count else 0
    )
    return {
        "score": plan.get("llm_final_score", eval_result.get("score", 0)),
        "fallback_used": bool(plan.get("llm_fallback_used")),
        "uses_historical_context": plan_uses_historical_context(
            plan,
            rag_context or plan.get("rag_context", {}),
        ),
        "rag_retrieved_count": retrieved_count,
        "rag_used_count": used_count,
        "rag_usage_rate": usage_rate,
        "rag_personalized_retrieved_count": personalized_retrieved_count,
        "rag_personalized_used_count": personalized_used_count,
        "rag_personalized_usage_rate": personalized_usage_rate,
        "rag_background_retrieved_count": background_retrieved_count,
        "rag_background_used_count": background_used_count,
        "rag_background_usage_rate": background_usage_rate,
        "rag_personalized_evidence_share": personalized_evidence_share,
        "used_doc_ids": plan.get("rag_used_doc_ids", []) or [],
        "rag_trace_summary": plan.get("rag_trace_summary", ""),
        "errors": eval_result.get("errors", []) or [],
        "warnings": eval_result.get("warnings", []) or [],
        "infos": eval_result.get("infos", []) or [],
        "plan_title": (
            f"Week {plan.get('week', '')} - {plan.get('title', '')}"
        ).strip(" -"),
    }


def _choose_winner(without_rag, with_rag):
    without_score = int(without_rag.get("score") or 0)
    with_score = int(with_rag.get("score") or 0)
    retrieved_count = int(with_rag.get("rag_retrieved_count", 0) or 0)
    used_count = int(with_rag.get("rag_used_count", 0) or 0)
    usage_text = ""
    if retrieved_count:
        usage_text = (
            f"；同时检索到的 {retrieved_count} 条历史记忆中有 "
            f"{used_count} 条被计划明确引用"
        )
    if with_rag.get("fallback_used") and not without_rag.get("fallback_used"):
        return (
            "without_rag",
            "使用 RAG 的实验触发了兜底，而无 RAG 版本没有触发兜底。",
        )
    if without_rag.get("fallback_used") and not with_rag.get("fallback_used"):
        return (
            "with_rag",
            "使用 RAG 后未触发兜底，而无 RAG 版本触发了兜底" + usage_text + "。",
        )
    if with_score > without_score:
        return (
            "with_rag",
            "使用 RAG 后计划评分更高" + usage_text + "。",
        )
    if with_score < without_score:
        return (
            "without_rag",
            "无 RAG 版本计划评分更高，建议检查 RAG 是否引入了噪声。",
        )
    if with_rag.get("uses_historical_context") and not without_rag.get(
        "uses_historical_context"
    ):
        return (
            "with_rag",
            "两者评分相同，但使用 RAG 的计划更明显引用了历史学习上下文" + usage_text + "。",
        )
    return (
        "tie",
        "两者评分接近，暂时无法证明 RAG 对本次计划生成有明显提升。",
    )


def run_rag_plan_ab_experiment():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query = "用户最近薄弱点和下一阶段计划"

    without_plan = generate_ai_week_plan_next(
        trigger="rag_ab_without_rag",
        context_fingerprint=f"rag_ab_{timestamp}_without",
        prompt_version="v1",
        save_draft=False,
        with_rag=False,
    )
    with_plan = generate_ai_week_plan_next(
        trigger="rag_ab_with_rag",
        context_fingerprint=f"rag_ab_{timestamp}_with",
        prompt_version="v1",
        save_draft=False,
        with_rag=True,
    )
    rag_context = load_last_rag_debug()

    without_summary = _summarize_plan(without_plan, {})
    with_summary = _summarize_plan(with_plan, rag_context)
    winner, winner_reason = _choose_winner(without_summary, with_summary)
    result = {
        "timestamp": timestamp,
        "task": "rag_plan_ab_experiment",
        "query": query,
        "results": {
            "without_rag": without_summary,
            "with_rag": with_summary,
        },
        "winner": winner,
        "winner_reason": winner_reason,
    }
    _append_json_list(AB_RESULTS_PATH, result)
    _append_json_list(
        AB_CANDIDATES_PATH,
        {
            "timestamp": timestamp,
            "without_rag": without_plan,
            "with_rag": with_plan,
        },
        limit=30,
    )
    return result


def _format_bool(value):
    return "是" if value else "否"


def format_rag_ab_experiment_result(result):
    if not isinstance(result, dict):
        return "暂无 RAG 有无对比实验结果。"
    lines = [
        "===== RAG 有无对比实验 =====",
        "",
        f"查询：{result.get('query', '')}",
        "",
    ]
    labels = {
        "without_rag": "无 RAG",
        "with_rag": "有 RAG",
    }
    results = result.get("results", {})
    if not isinstance(results, dict):
        results = {}
    for key in ("without_rag", "with_rag"):
        item = results.get(key, {})
        if not isinstance(item, dict):
            item = {}
        lines.extend([
            f"{labels[key]}：",
            f"- 计划标题：{item.get('plan_title', '')}",
            f"- 评分：{item.get('score', 0)}",
            f"- fallback：{_format_bool(item.get('fallback_used'))}",
            f"- 引用历史上下文：{_format_bool(item.get('uses_historical_context'))}",
            f"- RAG 检索记忆数：{item.get('rag_retrieved_count', 0)}",
            f"- RAG 引用记忆数：{item.get('rag_used_count', 0)}",
            f"- RAG 使用率：{round(float(item.get('rag_usage_rate', 0) or 0) * 100, 1)}%",
            f"- 严重问题：{len(item.get('errors', []) or [])}",
            f"- 质量提醒：{len(item.get('warnings', []) or [])}",
            "",
        ])
    lines.extend([
        f"推荐结论：{result.get('winner', '')}",
        f"原因：{result.get('winner_reason', '')}",
        "",
        "说明：本实验只用于分析，不会应用任何计划。",
    ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    experiment = run_rag_plan_ab_experiment()
    print(format_rag_ab_experiment_result(experiment))
