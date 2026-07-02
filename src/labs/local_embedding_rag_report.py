import json
from pathlib import Path


from app_paths import BASE_DIR
RESULTS_PATH = BASE_DIR / "data" / "local_embedding_rag_experiment_results.json"


def load_local_embedding_rag_results():
    if not RESULTS_PATH.exists():
        return []
    try:
        data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _average(values):
    values = [value for value in values if value is not None]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _rate(count, total):
    if not total:
        return 0.0
    return round(count / total, 4)


def _percent(value):
    return f"{_safe_float(value) * 100:.1f}%"


def _successful_pair_count(results):
    count = 0
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("local", {}).get("success") and item.get("cloud", {}).get("success"):
            count += 1
    return count


def summarize_local_embedding_rag_experiments(limit=20):
    results = load_local_embedding_rag_results()
    recent = results[-limit:] if limit else results
    total_runs = len(results)
    total = len(recent)
    all_local_success = 0
    all_cloud_success = 0
    local_success = 0
    cloud_success = 0
    top1_same_count = 0
    local_latencies = []
    cloud_latencies = []
    top3_overlaps = []
    top5_overlaps = []
    ranking_similarity_counts = {}

    for item in results:
        local = item.get("local", {}) if isinstance(item, dict) else {}
        cloud = item.get("cloud", {}) if isinstance(item, dict) else {}
        if local.get("success"):
            all_local_success += 1
        if cloud.get("success"):
            all_cloud_success += 1

    for item in recent:
        local = item.get("local", {}) if isinstance(item, dict) else {}
        cloud = item.get("cloud", {}) if isinstance(item, dict) else {}
        comparison = item.get("comparison", {}) if isinstance(item, dict) else {}
        if local.get("success"):
            local_success += 1
            local_latencies.append(_safe_float(local.get("latency_seconds")))
        if cloud.get("success"):
            cloud_success += 1
            cloud_latencies.append(_safe_float(cloud.get("latency_seconds")))

        # Ranking overlap is only meaningful when both sides succeeded.
        if local.get("success") and cloud.get("success"):
            if comparison.get("top1_same"):
                top1_same_count += 1
            top3_overlaps.append(_safe_float(comparison.get("top3_overlap")))
            top5_overlaps.append(_safe_float(comparison.get("top5_overlap")))

        label = comparison.get("ranking_similarity", "unknown")
        ranking_similarity_counts[label] = ranking_similarity_counts.get(label, 0) + 1

    pair_count = _successful_pair_count(recent)
    summary = {
        "total_runs": total_runs,
        "recent_runs": total,
        "valid_pair_count": pair_count,
        "overall_local_success_rate": _rate(all_local_success, total_runs),
        "overall_cloud_success_rate": _rate(all_cloud_success, total_runs),
        "recent_local_success_rate": _rate(local_success, total),
        "recent_cloud_success_rate": _rate(cloud_success, total),
        "total_experiments": total,
        "valid_pair_experiments": pair_count,
        "local": {
            "success_count": local_success,
            "success_rate": _rate(local_success, total),
            "avg_latency_seconds": _average(local_latencies),
        },
        "cloud": {
            "success_count": cloud_success,
            "success_rate": _rate(cloud_success, total),
            "avg_latency_seconds": _average(cloud_latencies),
        },
        "comparison": {
            "top1_same_rate": _rate(top1_same_count, pair_count),
            "avg_top3_overlap": _average(top3_overlaps),
            "avg_top5_overlap": _average(top5_overlaps),
            "ranking_similarity_counts": ranking_similarity_counts,
        },
    }
    recommendation = recommend_local_embedding_strategy(summary)
    summary.update(recommendation)
    # Backward compatibility for older GUI/report callers.
    summary["recommended_mode"] = recommendation.get("recommended_strategy")
    return summary


def recommend_local_embedding_strategy(summary):
    total = summary.get("total_experiments", 0)
    pair_count = summary.get("valid_pair_experiments", 0)
    local = summary.get("local", {})
    cloud = summary.get("cloud", {})
    comparison = summary.get("comparison", {})

    local_success = _safe_float(local.get("success_rate"))
    cloud_success = _safe_float(cloud.get("success_rate"))
    local_latency = _safe_float(local.get("avg_latency_seconds"))
    cloud_latency = _safe_float(cloud.get("avg_latency_seconds"))
    top3_overlap = _safe_float(comparison.get("avg_top3_overlap"))
    top5_overlap = _safe_float(comparison.get("avg_top5_overlap"))

    if total < 5:
        return {
            "recommended_strategy": "insufficient_data",
            "recommendation_reason": "实验次数较少，建议继续采样。",
            "confidence": 0.25,
            "action_suggestions": [
                "继续运行 local_embedding_rag_experiment.py，至少累计 5 次实验。",
                "保留云端 Embedding 为默认策略。",
                "先观察本地 Embedding 在不同查询下的成功率和排序稳定性。",
            ],
        }

    if local_success < 0.7:
        return {
            "recommended_strategy": "keep_cloud_default",
            "recommendation_reason": "本地 Embedding 成功率不足，暂不建议默认启用。",
            "confidence": 0.75,
            "action_suggestions": [
                "继续保留云端 Embedding 为默认。",
                "检查 Ollama 服务、模型加载和 timeout 配置。",
                "待本地成功率稳定后再重新评估。",
            ],
        }

    if cloud_success < 0.4 and local_success >= 0.8:
        return {
            "recommended_strategy": "use_local_fallback",
            "recommendation_reason": "云端 Embedding 连接不稳定，本地 Embedding 可作为可靠 fallback。",
            "confidence": 0.72,
            "action_suggestions": [
                "继续保留云端 Embedding 为默认。",
                "在云端失败时使用本地 Embedding fallback。",
                "继续采集云端恢复后的排序重叠率样本。",
            ],
        }

    if (
        local_success >= 0.9
        and top5_overlap >= 0.7
        and local_latency > 0
        and cloud_latency > 0
        and local_latency < cloud_latency
    ):
        return {
            "recommended_strategy": "use_local_default",
            "recommendation_reason": "本地 Embedding 成功率高，检索结果与云端较接近，且延迟更低。",
            "confidence": 0.88,
            "action_suggestions": [
                "可以考虑把本地 Embedding 作为候选默认策略。",
                "切换前建议再测试更多专题查询。",
                "保留云端 Embedding fallback，避免本地服务关闭时影响 RAG。",
            ],
        }

    if (
        local_success >= 0.8
        and top5_overlap >= 0.6
        and (pair_count == 0 or top3_overlap < 0.67)
    ):
        return {
            "recommended_strategy": "use_local_fallback",
            "recommendation_reason": "本地 Embedding 基本可用，但检索排序与云端仍有差异，建议先作为备用方案。",
            "confidence": 0.68,
            "action_suggestions": [
                "继续保留云端 Embedding 为默认。",
                "在云端失败时使用本地 Embedding fallback。",
                "继续采集更多 RAG 对比实验结果。",
                "后续可以测试 bge-m3 等其他本地 embedding 模型。",
            ],
        }

    if local_latency > 0 and cloud_latency > 0 and local_latency > cloud_latency * 1.5 and top5_overlap < 0.6:
        return {
            "recommended_strategy": "keep_cloud_default",
            "recommendation_reason": "本地 Embedding 延迟明显高于云端，且检索重叠率不高。",
            "confidence": 0.7,
            "action_suggestions": [
                "保持云端 Embedding 为默认。",
                "优化本地模型加载或尝试更合适的 embedding 模型。",
                "继续用实验报告观察本地模型表现。",
            ],
        }

    return {
        "recommended_strategy": "continue_observing",
        "recommendation_reason": "本地 Embedding 已有一定可用性，但当前样本还不足以稳定判断默认策略。",
        "confidence": 0.55,
        "action_suggestions": [
            "继续采集更多 RAG 对比实验结果。",
            "观察云端恢复后与本地排序的 Top-K overlap。",
            "暂时不要自动切换默认 Embedding。",
        ],
    }


def format_local_embedding_rag_summary(summary):
    pair_count = summary.get("valid_pair_count", summary.get("valid_pair_experiments", 0))
    lines = [
        "===== 本地 Embedding RAG 统计报告 =====",
        "",
        f"统计范围：最近 {summary.get('total_experiments', 0)} 次实验",
        f"有效双边对比：{summary.get('valid_pair_experiments', 0)} 次",
        "",
        "本地 Embedding：",
        f"- 成功次数：{summary.get('local', {}).get('success_count', 0)}",
        f"- 成功率：{_percent(summary.get('local', {}).get('success_rate', 0))}",
        f"- 平均耗时：{summary.get('local', {}).get('avg_latency_seconds', 0)} 秒",
        "",
        "云端 Embedding：",
        f"- 成功次数：{summary.get('cloud', {}).get('success_count', 0)}",
        f"- 成功率：{_percent(summary.get('cloud', {}).get('success_rate', 0))}",
        f"- 平均耗时：{summary.get('cloud', {}).get('avg_latency_seconds', 0)} 秒",
        "",
        "排序一致性：",
        f"- Top1 一致率：{_percent(summary.get('comparison', {}).get('top1_same_rate', 0))}",
        f"- 平均 Top3 overlap：{summary.get('comparison', {}).get('avg_top3_overlap', 0)}",
        f"- 平均 Top5 overlap：{summary.get('comparison', {}).get('avg_top5_overlap', 0)}",
        "",
        "排序相似度分布：",
    ]
    lines.extend([
        "",
        "样本说明：",
        f"- 历史总实验数：{summary.get('total_runs', summary.get('total_experiments', 0))}",
        f"- 最近统计实验数：{summary.get('recent_runs', summary.get('total_experiments', 0))}",
        f"- 最近有效双边对比数：{pair_count}",
        f"- 最近本地成功率：{_percent(summary.get('recent_local_success_rate', summary.get('local', {}).get('success_rate', 0)))}",
        f"- 最近云端成功率：{_percent(summary.get('recent_cloud_success_rate', summary.get('cloud', {}).get('success_rate', 0)))}",
        f"- 历史本地成功率：{_percent(summary.get('overall_local_success_rate', summary.get('local', {}).get('success_rate', 0)))}",
        f"- 历史云端成功率：{_percent(summary.get('overall_cloud_success_rate', summary.get('cloud', {}).get('success_rate', 0)))}",
    ])
    if not pair_count:
        lines.extend([
            "",
            "提示：当前没有有效的本地/云端双边对比样本，Top-K overlap 暂无参考意义。",
        ])

    counts = summary.get("comparison", {}).get("ranking_similarity_counts", {})
    if counts:
        for label, count in sorted(counts.items()):
            lines.append(f"- {label}：{count} 次")
    else:
        lines.append("- 暂无")

    lines.extend([
        "",
        "===== 本地 Embedding 策略建议 =====",
        "",
        f"推荐策略：{summary.get('recommended_strategy', '')}",
        f"置信度：{_safe_float(summary.get('confidence', 0)):.2f}",
        "",
        "推荐原因：",
        summary.get("recommendation_reason", ""),
        "",
        "行动建议：",
    ])
    suggestions = summary.get("action_suggestions", [])
    if suggestions:
        for index, suggestion in enumerate(suggestions, start=1):
            lines.append(f"{index}. {suggestion}")
    else:
        lines.append("1. 继续采集更多实验结果。")

    lines.extend([
        "",
        "说明：报告只给出建议，不会修改 config/local_model_config.json 或正式 RAG 策略。",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_local_embedding_rag_summary(summarize_local_embedding_rag_experiments(limit=20)))
