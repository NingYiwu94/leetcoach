import json
from pathlib import Path


from app_paths import BASE_DIR
RAG_AB_RESULTS_PATH = BASE_DIR / "data" / "rag_ab_experiment_results.json"


def load_rag_ab_results():
    if not RAG_AB_RESULTS_PATH.exists():
        return []
    try:
        data = json.loads(RAG_AB_RESULTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _as_list(value):
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _avg(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _rate(count, total):
    if not total:
        return None
    return round(count / total, 4)


def _score(item):
    value = _as_float(item.get("score"))
    if value is None:
        value = _as_float(item.get("final_score"))
    return value


def _empty_stats():
    return {
        "runs": 0,
        "scores": [],
        "fallback_count": 0,
        "error_counts": [],
        "warning_counts": [],
        "historical_context_count": 0,
        "rag_retrieved_counts": [],
        "rag_used_counts": [],
        "rag_usage_rates": [],
        "personalized_retrieved_counts": [],
        "personalized_used_counts": [],
        "personalized_usage_rates": [],
        "background_retrieved_counts": [],
        "background_used_counts": [],
        "background_usage_rates": [],
        "personalized_evidence_shares": [],
        "win_count": 0,
    }


def _finalize_stats(stats):
    runs = stats["runs"]
    return {
        "runs": runs,
        "avg_score": _avg(stats["scores"]),
        "fallback_count": stats["fallback_count"],
        "fallback_rate": _rate(stats["fallback_count"], runs),
        "avg_errors": _avg(stats["error_counts"]) or 0.0,
        "avg_warnings": _avg(stats["warning_counts"]) or 0.0,
        "uses_historical_context_rate": _rate(stats["historical_context_count"], runs),
        "avg_rag_retrieved_count": _avg(stats["rag_retrieved_counts"]) or 0.0,
        "avg_rag_used_count": _avg(stats["rag_used_counts"]) or 0.0,
        "avg_rag_usage_rate": _avg(stats["rag_usage_rates"]) or 0.0,
        "avg_personalized_retrieved_count": _avg(stats["personalized_retrieved_counts"]) or 0.0,
        "avg_personalized_used_count": _avg(stats["personalized_used_counts"]) or 0.0,
        "avg_personalized_usage_rate": _avg(stats["personalized_usage_rates"]) or 0.0,
        "avg_background_retrieved_count": _avg(stats["background_retrieved_counts"]) or 0.0,
        "avg_background_used_count": _avg(stats["background_used_counts"]) or 0.0,
        "avg_background_usage_rate": _avg(stats["background_usage_rates"]) or 0.0,
        "avg_personalized_evidence_share": _avg(stats["personalized_evidence_shares"]) or 0.0,
        "win_count": stats["win_count"],
    }


def _append_metric(stats, key, value):
    value = _as_float(value)
    if value is not None:
        stats[key].append(value)


def summarize_rag_ab_experiments(limit=20):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 20

    experiments = [
        item for item in load_rag_ab_results()[-limit:]
        if isinstance(item, dict)
    ]
    working = {
        "without_rag": _empty_stats(),
        "with_rag": _empty_stats(),
    }

    for experiment in experiments:
        winner = str(experiment.get("winner", "") or "")
        results = experiment.get("results", {})
        if not isinstance(results, dict):
            results = {}
        for key in ("without_rag", "with_rag"):
            item = results.get(key, {})
            if not isinstance(item, dict):
                continue
            stats = working[key]
            stats["runs"] += 1

            score = _score(item)
            if score is not None:
                stats["scores"].append(score)
            if item.get("fallback_used"):
                stats["fallback_count"] += 1
            if item.get("uses_historical_context"):
                stats["historical_context_count"] += 1

            stats["error_counts"].append(len(_as_list(item.get("errors", []))))
            stats["warning_counts"].append(len(_as_list(item.get("warnings", []))))

            _append_metric(stats, "rag_retrieved_counts", item.get("rag_retrieved_count"))
            _append_metric(stats, "rag_used_counts", item.get("rag_used_count"))
            _append_metric(stats, "rag_usage_rates", item.get("rag_usage_rate"))
            _append_metric(stats, "personalized_retrieved_counts", item.get("rag_personalized_retrieved_count"))
            _append_metric(stats, "personalized_used_counts", item.get("rag_personalized_used_count"))
            _append_metric(stats, "personalized_usage_rates", item.get("rag_personalized_usage_rate"))
            _append_metric(stats, "background_retrieved_counts", item.get("rag_background_retrieved_count"))
            _append_metric(stats, "background_used_counts", item.get("rag_background_used_count"))
            _append_metric(stats, "background_usage_rates", item.get("rag_background_usage_rate"))
            _append_metric(stats, "personalized_evidence_shares", item.get("rag_personalized_evidence_share"))

            if winner == key:
                stats["win_count"] += 1

    summary = {
        "total_experiments": len(experiments),
        "limit": limit,
        "without_rag": _finalize_stats(working["without_rag"]),
        "with_rag": _finalize_stats(working["with_rag"]),
        "recommended_mode": "insufficient_data",
        "recommendation_reason": "",
    }
    _backfill_personalized_metrics_from_trace(summary, limit)
    summary.update(recommend_rag_mode(summary))
    return summary


def _backfill_personalized_metrics_from_trace(summary, limit):
    with_rag = summary.get("with_rag", {})
    if not isinstance(with_rag, dict):
        return
    if not with_rag.get("avg_rag_retrieved_count"):
        return
    if with_rag.get("avg_personalized_retrieved_count"):
        return
    try:
        from rag_trace_report import summarize_rag_traces

        trace_summary = summarize_rag_traces(limit=limit)
    except Exception:
        return
    if not isinstance(trace_summary, dict) or not trace_summary.get("total_traces"):
        return
    with_rag["avg_personalized_retrieved_count"] = trace_summary.get(
        "avg_personalized_retrieved_count",
        0.0,
    )
    with_rag["avg_personalized_used_count"] = trace_summary.get(
        "avg_personalized_used_count",
        0.0,
    )
    with_rag["avg_personalized_usage_rate"] = trace_summary.get(
        "avg_personalized_usage_rate",
        0.0,
    )
    with_rag["avg_background_retrieved_count"] = trace_summary.get(
        "avg_background_retrieved_count",
        0.0,
    )
    with_rag["avg_background_used_count"] = trace_summary.get(
        "avg_background_used_count",
        0.0,
    )
    with_rag["avg_background_usage_rate"] = trace_summary.get(
        "avg_background_usage_rate",
        0.0,
    )
    with_rag["avg_personalized_evidence_share"] = trace_summary.get(
        "personalized_evidence_share",
        0.0,
    )
    with_rag["personalized_metrics_source"] = "rag_trace_logs"


def _metric(summary, mode, key, default=0):
    value = summary.get(mode, {}).get(key)
    if value is None:
        return default
    return value


def recommend_rag_mode(summary):
    total = int(summary.get("total_experiments", 0) or 0)
    if total < 3:
        return {
            "recommended_mode": "insufficient_data",
            "recommendation_reason": "实验次数较少，建议继续观察。",
        }

    matched = []
    if _metric(summary, "with_rag", "avg_score") >= (
        _metric(summary, "without_rag", "avg_score") + 3
    ):
        matched.append("平均评分更高")
    if _metric(summary, "with_rag", "fallback_rate", 1) <= _metric(
        summary, "without_rag", "fallback_rate", 1
    ):
        matched.append("fallback 率不高于无 RAG")
    if _metric(summary, "with_rag", "uses_historical_context_rate") > _metric(
        summary, "without_rag", "uses_historical_context_rate"
    ):
        matched.append("更常引用历史上下文")
    if _metric(summary, "with_rag", "win_count") > _metric(
        summary, "without_rag", "win_count"
    ):
        matched.append("胜出次数更多")

    with_score = _metric(summary, "with_rag", "avg_score")
    without_score = _metric(summary, "without_rag", "avg_score")
    with_fallback = _metric(summary, "with_rag", "fallback_rate", 1)
    without_fallback = _metric(summary, "without_rag", "fallback_rate", 1)
    with_warnings = _metric(summary, "with_rag", "avg_warnings", 999)
    without_warnings = _metric(summary, "without_rag", "avg_warnings", 999)

    if len(matched) >= 2:
        reason = "with_rag 在最近多次实验中表现更好：" + "、".join(matched) + "。"
        personalized_share = _metric(summary, "with_rag", "avg_personalized_evidence_share")
        personalized_usage = _metric(summary, "with_rag", "avg_personalized_usage_rate")
        if personalized_share < 0.45 or personalized_usage < 0.35:
            reason += " 但个性化证据占比或使用率仍偏低，需继续优化个人历史文档质量。"
        else:
            reason += " 建议继续在 AI 计划生成中启用 RAG。"
        return {
            "recommended_mode": "with_rag",
            "recommendation_reason": reason,
        }

    if (
        with_score < without_score
        and with_fallback > without_fallback
        and with_warnings > without_warnings
    ):
        return {
            "recommended_mode": "without_rag_or_improve_docs",
            "recommendation_reason": (
                "with_rag 当前平均评分更低、fallback 更多、质量提醒更多，"
                "建议暂时关闭 RAG 实验或继续优化 RAG 文档质量。"
            ),
        }

    return {
        "recommended_mode": "continue_observing",
        "recommendation_reason": "当前数据尚不能稳定证明 RAG 明显提升计划质量，建议继续积累实验。",
    }


def _format_number(value):
    if value is None:
        return "无数据"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def _format_rate(value):
    if value is None:
        return "无数据"
    return f"{float(value) * 100:.1f}%"


def _mode_block(label, stats):
    return [
        f"{label}：",
        f"- 运行次数：{stats.get('runs', 0)}",
        f"- 平均评分：{_format_number(stats.get('avg_score'))}",
        f"- fallback 次数：{stats.get('fallback_count', 0)}",
        f"- fallback 率：{_format_rate(stats.get('fallback_rate'))}",
        f"- 平均严重问题数：{_format_number(stats.get('avg_errors'))}",
        f"- 平均质量提醒数：{_format_number(stats.get('avg_warnings'))}",
        f"- 引用历史上下文比例：{_format_rate(stats.get('uses_historical_context_rate'))}",
        f"- 平均检索记忆数：{_format_number(stats.get('avg_rag_retrieved_count'))}",
        f"- 平均被引用记忆数：{_format_number(stats.get('avg_rag_used_count'))}",
        f"- 平均 RAG 使用率：{_format_rate(stats.get('avg_rag_usage_rate'))}",
        f"- 平均个性化证据检索数：{_format_number(stats.get('avg_personalized_retrieved_count'))}",
        f"- 平均个性化证据使用数：{_format_number(stats.get('avg_personalized_used_count'))}",
        f"- 个性化证据使用率：{_format_rate(stats.get('avg_personalized_usage_rate'))}",
        f"- 平均题库背景检索数：{_format_number(stats.get('avg_background_retrieved_count'))}",
        f"- 平均题库背景使用数：{_format_number(stats.get('avg_background_used_count'))}",
        f"- 个性化证据占比：{_format_rate(stats.get('avg_personalized_evidence_share'))}",
        f"- 胜出次数：{stats.get('win_count', 0)}",
        "",
    ]


def format_rag_ab_summary(summary):
    if not isinstance(summary, dict) or not summary.get("total_experiments"):
        return "暂无 RAG A/B 实验记录，请先运行 RAG 有无对比实验。"

    lines = [
        "===== RAG A/B 实验统计报告 =====",
        "",
        f"统计范围：最近 {summary.get('total_experiments', 0)} 次实验",
        "",
    ]
    lines.extend(_mode_block("无 RAG", summary.get("without_rag", {}) or {}))
    lines.extend(_mode_block("有 RAG", summary.get("with_rag", {}) or {}))

    with_rag_stats = summary.get("with_rag", {}) or {}
    retrieved = with_rag_stats.get("avg_rag_retrieved_count", 0) or 0
    usage_rate = with_rag_stats.get("avg_rag_usage_rate", 0) or 0
    personalized_share = with_rag_stats.get("avg_personalized_evidence_share", 0) or 0
    personalized_usage = with_rag_stats.get("avg_personalized_usage_rate", 0) or 0
    if retrieved > 0 and usage_rate < 0.2:
        lines.extend([
            "RAG 使用提醒：",
            "RAG 检索到了上下文，但模型较少在计划中使用，建议优化 Prompt 中对历史记忆的使用要求。",
            "",
        ])
    if retrieved > 0 and (personalized_share < 0.45 or personalized_usage < 0.35):
        lines.extend([
            "个性化 RAG 提醒：",
            "with_rag 当前可能仍较多依赖题库背景，而不是用户个人历史。建议继续优化 records、reviews、problem_notes、stage_summary 等文档构建。",
            "",
        ])

    if summary.get("total_experiments", 0) < 3:
        lines.extend([
            "提示：",
            "当前实验次数较少，暂不建议调整 RAG 默认策略。",
            "",
        ])

    lines.extend([
        f"推荐模式：{summary.get('recommended_mode', 'insufficient_data')}",
        "",
        "推荐原因：",
        str(summary.get("recommendation_reason", "")),
    ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    report = summarize_rag_ab_experiments(limit=20)
    print(format_rag_ab_summary(report))
