import json
from pathlib import Path


from app_paths import BASE_DIR
EXPERIMENT_RESULTS_PATH = BASE_DIR / "data" / "prompt_experiment_results.json"


def load_prompt_experiment_results():
    if not EXPERIMENT_RESULTS_PATH.exists():
        return []
    try:
        data = json.loads(EXPERIMENT_RESULTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("Prompt 实验记录 JSON 损坏，暂时无法生成统计报告。")
        return []
    except OSError as error:
        print(f"读取 Prompt 实验记录失败：{error}")
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


def _bool_or_none(value):
    if value is True or value is False:
        return value
    return None


def _empty_version_stats():
    return {
        "runs": 0,
        "final_scores": [],
        "raw_scores": [],
        "fallback_count": 0,
        "parsed_success_count": 0,
        "parsed_known_count": 0,
        "schema_valid_count": 0,
        "schema_known_count": 0,
        "error_counts": [],
        "warning_counts": [],
        "win_count": 0,
    }


def _avg(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _rate(count, total):
    if not total:
        return None
    return round(count / total, 4)


def _finalize_version_stats(stats):
    runs = stats["runs"]
    fallback_count = stats["fallback_count"]
    return {
        "runs": runs,
        "avg_final_score": _avg(stats["final_scores"]),
        "avg_raw_score": _avg(stats["raw_scores"]),
        "fallback_count": fallback_count,
        "fallback_rate": _rate(fallback_count, runs),
        "parsed_success_rate": _rate(
            stats["parsed_success_count"],
            stats["parsed_known_count"],
        ),
        "schema_valid_rate": _rate(
            stats["schema_valid_count"],
            stats["schema_known_count"],
        ),
        "avg_errors": _avg(stats["error_counts"]) or 0.0,
        "avg_warnings": _avg(stats["warning_counts"]) or 0.0,
        "win_count": stats["win_count"],
    }


def _result_score(item, key, fallback_key=None):
    value = _as_float(item.get(key))
    if value is None and fallback_key:
        value = _as_float(item.get(fallback_key))
    return value


def summarize_prompt_experiments(limit=20):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 20

    experiments = load_prompt_experiment_results()[-limit:]
    working = {}

    for experiment in experiments:
        if not isinstance(experiment, dict):
            continue
        winner = str(experiment.get("winner", "") or "").strip()
        results = experiment.get("results", [])
        if not isinstance(results, list):
            continue

        for item in results:
            if not isinstance(item, dict):
                continue
            version = str(item.get("prompt_version", "") or "").strip()
            if not version:
                continue
            stats = working.setdefault(version, _empty_version_stats())
            stats["runs"] += 1

            final_score = _result_score(item, "final_score", "score")
            if final_score is not None:
                stats["final_scores"].append(final_score)

            raw_score = _result_score(item, "raw_score")
            if raw_score is not None:
                stats["raw_scores"].append(raw_score)

            if item.get("fallback_used"):
                stats["fallback_count"] += 1

            parsed_success = _bool_or_none(item.get("parsed_success"))
            if parsed_success is not None:
                stats["parsed_known_count"] += 1
                if parsed_success:
                    stats["parsed_success_count"] += 1

            schema_valid = _bool_or_none(item.get("schema_valid"))
            if schema_valid is not None:
                stats["schema_known_count"] += 1
                if schema_valid:
                    stats["schema_valid_count"] += 1

            errors = _as_list(item.get("errors", []))
            warnings = _as_list(item.get("warnings", []))
            if not errors and not warnings and item.get("issues"):
                warnings = _as_list(item.get("issues", []))
            stats["error_counts"].append(len(errors))
            stats["warning_counts"].append(len(warnings))

            if version == winner:
                stats["win_count"] += 1

    versions = {
        version: _finalize_version_stats(stats)
        for version, stats in sorted(working.items())
    }
    summary = {
        "total_experiments": len([
            item for item in experiments if isinstance(item, dict)
        ]),
        "limit": limit,
        "versions": versions,
        "recommended_default": "v1",
        "recommendation_reason": "",
    }
    recommendation = recommend_default_prompt(summary)
    summary.update(recommendation)
    return summary


def _metric(summary, version, key, default=0):
    value = summary.get("versions", {}).get(version, {}).get(key)
    if value is None:
        return default
    return value


def recommend_default_prompt(summary):
    versions = summary.get("versions", {}) if isinstance(summary, dict) else {}
    v1 = versions.get("v1", {})
    v2 = versions.get("v2", {})

    if not versions:
        return {
            "recommended_default": "v1",
            "recommendation_reason": (
                "暂无 Prompt 实验记录，请先运行 Prompt 版本对比实验。"
            ),
        }

    if v1.get("runs", 0) < 3 or v2.get("runs", 0) < 3:
        return {
            "recommended_default": "v1",
            "recommendation_reason": (
                "实验次数不足，建议继续观察；当前不建议切换默认 Prompt。"
            ),
        }

    matched = []
    if _metric(summary, "v2", "avg_final_score") >= (
        _metric(summary, "v1", "avg_final_score") + 3
    ):
        matched.append("平均最终评分更高")
    if _metric(summary, "v2", "fallback_rate", 1) < _metric(
        summary,
        "v1",
        "fallback_rate",
        1,
    ):
        matched.append("fallback 率更低")
    if _metric(summary, "v2", "win_count") > _metric(summary, "v1", "win_count"):
        matched.append("胜出次数更多")
    if _metric(summary, "v2", "schema_valid_rate", 0) >= _metric(
        summary,
        "v1",
        "schema_valid_rate",
        0,
    ):
        matched.append("Schema 通过率不低于 v1")
    if _metric(summary, "v2", "avg_warnings", 999) < _metric(
        summary,
        "v1",
        "avg_warnings",
        999,
    ):
        matched.append("平均质量提醒更少")

    if len(matched) >= 3:
        return {
            "recommended_default": "v2",
            "recommendation_reason": (
                "v2 在最近多次实验中满足："
                + "、".join(matched)
                + "。建议后续手动评估是否将默认 Prompt 切换为 v2。"
            ),
        }

    return {
        "recommended_default": "v1",
        "recommendation_reason": (
            "v2 尚未在足够多的关键指标上稳定优于 v1，建议继续保留默认稳定版本 v1。"
        ),
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
    return f"{value * 100:.1f}%"


def format_prompt_experiment_summary(summary):
    if not isinstance(summary, dict) or not summary.get("versions"):
        return "暂无 Prompt 实验记录，请先运行 Prompt 版本对比实验。"

    total = summary.get("total_experiments", 0)
    lines = [
        "===== Prompt 实验统计报告 =====",
        "",
        f"统计范围：最近 {total} 次实验",
        "",
    ]

    for version, stats in summary.get("versions", {}).items():
        lines.extend([
            f"Prompt {version}:",
            f"- 运行次数：{stats.get('runs', 0)}",
            f"- 平均最终评分：{_format_number(stats.get('avg_final_score'))}",
            f"- 平均原始评分：{_format_number(stats.get('avg_raw_score'))}",
            f"- fallback 次数：{stats.get('fallback_count', 0)}",
            f"- fallback 率：{_format_rate(stats.get('fallback_rate'))}",
            f"- JSON 解析成功率：{_format_rate(stats.get('parsed_success_rate'))}",
            f"- Schema 通过率：{_format_rate(stats.get('schema_valid_rate'))}",
            f"- 平均严重问题数：{_format_number(stats.get('avg_errors'))}",
            f"- 平均质量提醒数：{_format_number(stats.get('avg_warnings'))}",
            f"- 胜出次数：{stats.get('win_count', 0)}",
            "",
        ])

    if total < 3:
        lines.extend([
            "提示：",
            "当前实验次数较少，暂不建议切换默认 Prompt。",
            "",
        ])

    lines.extend([
        f"推荐默认版本：{summary.get('recommended_default', 'v1')}",
        "",
        "推荐原因：",
        summary.get("recommendation_reason", ""),
    ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    report = summarize_prompt_experiments(limit=20)
    print(format_prompt_experiment_summary(report))
