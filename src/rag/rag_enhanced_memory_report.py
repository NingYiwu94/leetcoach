import json
from pathlib import Path


from app_paths import BASE_DIR
RESULTS_PATH = BASE_DIR / "data" / "rag_enhanced_memory_experiment_results.json"


def load_enhanced_memory_experiment_results():
    if not RESULTS_PATH.exists():
        return []
    try:
        data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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
        return 0.0
    return round(sum(values) / len(values), 4)


def _rate(count, total):
    if not total:
        return 0.0
    return round(count / total, 4)


def _empty_stats():
    return {
        "runs": 0,
        "scores": [],
        "fallback_count": 0,
        "personalized_usage_rates": [],
        "background_usage_rates": [],
        "problem_bank_shares": [],
        "enhanced_memory_used_counts": [],
        "warning_counts": [],
        "win_count": 0,
    }


def _append_metric(stats, key, value):
    value = _as_float(value)
    if value is not None:
        stats[key].append(value)


def _finalize_stats(stats):
    runs = stats["runs"]
    return {
        "runs": runs,
        "avg_score": round(_avg(stats["scores"]), 2),
        "fallback_count": stats["fallback_count"],
        "fallback_rate": _rate(stats["fallback_count"], runs),
        "avg_personalized_usage_rate": _avg(stats["personalized_usage_rates"]),
        "avg_background_usage_rate": _avg(stats["background_usage_rates"]),
        "avg_problem_bank_used_share": _avg(stats["problem_bank_shares"]),
        "avg_enhanced_memory_used_count": round(_avg(stats["enhanced_memory_used_counts"]), 2),
        "avg_warnings": round(_avg(stats["warning_counts"]), 2),
        "win_count": stats["win_count"],
    }


def _collect_stats(experiments):
    working = {
        "normal_rag": _empty_stats(),
        "enhanced_memory_rag": _empty_stats(),
    }
    for experiment in experiments:
        if not isinstance(experiment, dict):
            continue
        winner = str(experiment.get("winner", "") or "")
        results = experiment.get("results", {})
        if not isinstance(results, dict):
            continue
        for key in ("normal_rag", "enhanced_memory_rag"):
            item = results.get(key, {})
            if not isinstance(item, dict):
                continue
            stats = working[key]
            stats["runs"] += 1
            _append_metric(stats, "scores", item.get("score"))
            if item.get("fallback_used"):
                stats["fallback_count"] += 1
            _append_metric(stats, "personalized_usage_rates", item.get("personalized_usage_rate"))
            _append_metric(stats, "background_usage_rates", item.get("background_usage_rate"))
            _append_metric(stats, "problem_bank_shares", item.get("problem_bank_used_share"))
            _append_metric(stats, "enhanced_memory_used_counts", item.get("enhanced_memory_used_count"))
            stats["warning_counts"].append(len(_as_list(item.get("warnings", []))))
            if winner == key:
                stats["win_count"] += 1
    return {
        "normal_rag": _finalize_stats(working["normal_rag"]),
        "enhanced_memory_rag": _finalize_stats(working["enhanced_memory_rag"]),
    }


def recommend_enhanced_memory_mode(summary):
    total = int(summary.get("total_experiments", 0) or 0)
    normal = summary.get("normal_rag", {}) or {}
    enhanced = summary.get("enhanced_memory_rag", {}) or {}
    if total < 3:
        return {
            "recommended_mode": "insufficient_data",
            "recommendation_reason": "实验次数较少，建议继续观察。",
        }

    better = []
    if enhanced.get("avg_score", 0) >= normal.get("avg_score", 0):
        better.append("平均评分不低于普通 RAG")
    if enhanced.get("fallback_rate", 1) <= normal.get("fallback_rate", 1):
        better.append("fallback 率不高于普通 RAG")
    if enhanced.get("avg_personalized_usage_rate", 0) > normal.get("avg_personalized_usage_rate", 0):
        better.append("个性化证据使用率更高")
    if enhanced.get("avg_problem_bank_used_share", 1) < normal.get("avg_problem_bank_used_share", 1):
        better.append("problem_bank 使用占比更低")
    if enhanced.get("win_count", 0) > normal.get("win_count", 0):
        better.append("胜出次数更多")
    if enhanced.get("avg_enhanced_memory_used_count", 0) > 0:
        better.append("增强记忆确实被计划引用")

    if len(better) >= 4:
        return {
            "recommended_mode": "enhanced_memory_rag_candidate",
            "recommendation_reason": (
                "增强记忆 RAG 表现明显更好：" + "、".join(better)
                + "。后续可以继续扩大样本，再考虑是否加入默认 RAG。"
            ),
        }
    if len(better) >= 2:
        return {
            "recommended_mode": "continue_experiment",
            "recommendation_reason": (
                "增强记忆 RAG 有一定积极信号：" + "、".join(better)
                + "。建议继续实验，不要急着设为默认。"
            ),
        }
    return {
        "recommended_mode": "normal_rag",
        "recommendation_reason": (
            "当前增强记忆 RAG 尚未稳定优于普通 RAG，建议继续优化增强记忆内容或检索排序。"
        ),
    }


def summarize_enhanced_memory_experiments(limit=20):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 20
    experiments = [
        item for item in load_enhanced_memory_experiment_results()[-limit:]
        if isinstance(item, dict)
    ]
    stats = _collect_stats(experiments)
    summary = {
        "total_experiments": len(experiments),
        "limit": limit,
        **stats,
    }
    summary.update(recommend_enhanced_memory_mode(summary))
    return summary


def _format_rate(value):
    try:
        return f"{float(value or 0) * 100:.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _mode_block(title, stats):
    stats = stats if isinstance(stats, dict) else {}
    lines = [
        f"{title}：",
        f"- 运行次数：{stats.get('runs', 0)}",
        f"- 平均评分：{stats.get('avg_score', 0)}",
        f"- fallback 率：{_format_rate(stats.get('fallback_rate'))}",
        f"- 个性化证据使用率：{_format_rate(stats.get('avg_personalized_usage_rate'))}",
        f"- 背景证据使用率：{_format_rate(stats.get('avg_background_usage_rate'))}",
        f"- problem_bank 使用占比：{_format_rate(stats.get('avg_problem_bank_used_share'))}",
        f"- 平均 enhanced memory 使用数：{stats.get('avg_enhanced_memory_used_count', 0)}",
        f"- 平均质量提醒数：{stats.get('avg_warnings', 0)}",
        f"- 胜出次数：{stats.get('win_count', 0)}",
    ]
    return lines


def format_enhanced_memory_summary(summary):
    if not isinstance(summary, dict):
        return "暂无增强记忆 RAG 统计报告。"
    lines = [
        "===== 增强个性化记忆 RAG 统计报告 =====",
        "",
        f"统计范围：最近 {summary.get('total_experiments', 0)} 次实验",
        "",
    ]
    lines.extend(_mode_block("普通 RAG", summary.get("normal_rag", {})))
    lines.append("")
    lines.extend(_mode_block("增强记忆 RAG", summary.get("enhanced_memory_rag", {})))
    lines.extend([
        "",
        f"推荐模式：{summary.get('recommended_mode', '')}",
        "",
        "推荐原因：",
        summary.get("recommendation_reason", ""),
        "",
        "说明：本报告只给出实验建议，不会自动修改默认 RAG 策略。",
    ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    report = summarize_enhanced_memory_experiments(limit=20)
    print(format_enhanced_memory_summary(report))
