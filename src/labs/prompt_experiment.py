import json
from datetime import datetime
from pathlib import Path

from ai.ai_plan_generator import (
    CURRENT_PLAN_PATH,
    PROBLEM_BANK_PATH,
    RECORDS_PATH,
    REVIEWS_PATH,
    generate_ai_week_plan_next,
    load_json,
)


from app_paths import BASE_DIR
EXPERIMENT_RESULTS_PATH = BASE_DIR / "data" / "prompt_experiment_results.json"
EXPERIMENT_CANDIDATES_PATH = (
    BASE_DIR / "data" / "prompt_experiment_candidates.json"
)
UNKNOWN_FALLBACK_REASON = (
    "未知原因：生成流程标记了 fallback，但未返回具体原因，请检查 ai_plan_generator.py"
)


def _save_json_list(path, item, limit=100):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = []
    if not isinstance(data, list):
        data = []
    data.append(item)
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 100
    path.write_text(
        json.dumps(data[-limit:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _context_summary():
    current_plan = load_json(CURRENT_PLAN_PATH, {})
    records = load_json(RECORDS_PATH, [])
    reviews = load_json(REVIEWS_PATH, [])
    problem_bank = load_json(PROBLEM_BANK_PATH, {})

    if not isinstance(current_plan, dict):
        current_plan = {}
    if not isinstance(records, list):
        records = []
    if not isinstance(reviews, list):
        reviews = []
    if not isinstance(problem_bank, dict):
        problem_bank = {}

    return {
        "current_week": current_plan.get("week", ""),
        "records_count": len(records),
        "reviews_count": len(reviews),
        "problem_bank_count": len(problem_bank),
        "current_topic": (
            current_plan.get("title")
            or current_plan.get("weekly_theme")
            or ""
        ),
    }


def _as_list(value):
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def _as_score(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _score_label(value):
    if value is None or value == "":
        return "无"
    return str(value)


def _bool_label(value, true_text="成功", false_text="失败", unknown_text="未记录"):
    if value is True:
        return true_text
    if value is False:
        return false_text
    return unknown_text


def _fallback_reason(plan, fallback_used):
    if not fallback_used or not isinstance(plan, dict):
        return ""
    reason = (
        plan.get("llm_fallback_reason")
        or plan.get("ai_generation_error")
        or ""
    )
    return str(reason).strip() or UNKNOWN_FALLBACK_REASON


def _result_from_plan(prompt_version, plan=None, error=None):
    if error is not None:
        error_message = str(error)
        return {
            "prompt_version": prompt_version,
            "raw_success": False,
            "parsed_success": False,
            "schema_valid": False,
            "raw_score": None,
            "final_score": 0,
            "score": 0,
            "quality_level": "failed",
            "fallback_used": True,
            "fallback_reason": "API 调用失败：" + error_message,
            "errors": [error_message],
            "warnings": [],
            "infos": [],
            "issues": [error_message],
            "plan_title": "",
            "error_message": error_message,
        }

    if not isinstance(plan, dict):
        return _result_from_plan(
            prompt_version,
            error=ValueError("计划生成结果为空或不是 JSON object"),
        )

    eval_result = plan.get("llm_eval_result", {})
    if not isinstance(eval_result, dict):
        eval_result = {}
    schema_check = plan.get("llm_schema_check", {})
    if not isinstance(schema_check, dict):
        schema_check = {}

    fallback_used = bool(plan.get("llm_fallback_used"))
    final_score = (
        plan.get("llm_final_score")
        if plan.get("llm_final_score") not in (None, "")
        else eval_result.get("score", plan.get("score", 0))
    )
    final_score = _as_score(final_score)
    raw_score = plan.get("llm_raw_score")
    if raw_score not in (None, ""):
        raw_score = _as_score(raw_score, default=None)

    errors = _as_list(eval_result.get("errors", []))
    warnings = _as_list(eval_result.get("warnings", []))
    infos = _as_list(eval_result.get("infos", []))
    legacy_issues = _as_list(eval_result.get("issues", []))
    issues = errors + warnings
    if not issues and legacy_issues:
        issues = legacy_issues

    return {
        "prompt_version": prompt_version,
        "raw_success": plan.get("llm_raw_success"),
        "parsed_success": plan.get("llm_parsed_success"),
        "schema_valid": plan.get(
            "llm_schema_valid",
            schema_check.get("valid"),
        ),
        "raw_score": raw_score,
        "final_score": final_score,
        "score": final_score,
        "quality_level": eval_result.get("quality_level", "unknown"),
        "fallback_used": fallback_used,
        "fallback_reason": _fallback_reason(plan, fallback_used),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "issues": issues,
        "plan_title": (
            f"Week {plan.get('week', '')} - {plan.get('title', '')}"
        ).strip(" -"),
    }


def _problem_count(item, key):
    return len(_as_list(item.get(key, [])))


def _version_or_unknown(item):
    return str(item.get("prompt_version") or "未知")


def _choose_by_score_then_issues(items):
    return sorted(
        items,
        key=lambda item: (
            _as_score(item.get("final_score", item.get("score", 0))),
            -_problem_count(item, "errors"),
            -_problem_count(item, "warnings"),
            1 if item.get("prompt_version") == "v1" else 0,
        ),
        reverse=True,
    )[0]


def _reason_for_non_fallback_winner(winner, loser):
    winner_version = _version_or_unknown(winner)
    loser_version = _version_or_unknown(loser)
    winner_score = _as_score(winner.get("final_score", winner.get("score", 0)))
    loser_score = _as_score(loser.get("final_score", loser.get("score", 0)))
    winner_errors = _problem_count(winner, "errors")
    loser_errors = _problem_count(loser, "errors")
    winner_warnings = _problem_count(winner, "warnings")
    loser_warnings = _problem_count(loser, "warnings")

    if winner_score > loser_score:
        return f"{winner_version} 评分更高，且未触发兜底。"
    if winner_score < loser_score:
        return (
            f"{loser_version} 评分更高，但触发了规则兜底；"
            f"优先选择原始输出可用的 {winner_version}。"
        )
    if winner_errors < loser_errors:
        return f"两者评分相同，但 {winner_version} 的严重问题更少。"
    if winner_warnings < loser_warnings:
        return f"两者评分相同，但 {winner_version} 的质量提醒更少。"
    if winner_version == "v1":
        return "两者评分和问题数量相同，按规则选择默认稳定版本 v1。"
    return (
        f"两者评分和问题数量相同，但 {loser_version} 触发了规则兜底，"
        f"而 {winner_version} 未触发兜底。"
    )


def _choose_winner(results):
    results = [item for item in results if isinstance(item, dict)]
    if not results:
        return "v1", "没有可用实验结果，默认保留稳定版本 v1。"

    non_fallback = [item for item in results if not item.get("fallback_used")]
    fallback = [item for item in results if item.get("fallback_used")]

    if len(non_fallback) == 1 and len(results) == 2:
        winner = non_fallback[0]
        loser = fallback[0]
        return (
            _version_or_unknown(winner),
            (
                f"{_version_or_unknown(loser)} 触发了规则兜底，"
                f"而 {_version_or_unknown(winner)} 未触发兜底；"
                "在当前实验中，优先选择原始输出可用的 Prompt。"
            ),
        )

    if non_fallback:
        winner = _choose_by_score_then_issues(non_fallback)
        others = [
            item for item in results
            if item.get("prompt_version") != winner.get("prompt_version")
        ]
        loser = _choose_by_score_then_issues(others) if others else {}
        return _version_or_unknown(winner), _reason_for_non_fallback_winner(
            winner,
            loser,
        )

    winner = _choose_by_score_then_issues(results)
    winner_version = _version_or_unknown(winner)
    return (
        winner_version,
        (
            f"两个版本都触发了兜底，当前推荐 {winner_version} 的兜底结果；"
            "建议检查原始输出失败原因。"
        ),
    )


def run_plan_prompt_comparison():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    context_summary = _context_summary()
    results = []
    candidates = {
        "timestamp": timestamp,
        "task": "ai_plan_prompt_comparison",
        "plans": {},
    }

    for version in ("v1", "v2"):
        try:
            plan = generate_ai_week_plan_next(
                trigger="prompt_experiment",
                context_fingerprint=f"prompt_experiment_{timestamp}_{version}",
                prompt_version=version,
                save_draft=False,
            )
            results.append(_result_from_plan(version, plan=plan))
            candidates["plans"][version] = plan
        except Exception as error:
            results.append(_result_from_plan(version, error=error))
            candidates["plans"][version] = {
                "error_message": str(error),
            }

    winner, winner_reason = _choose_winner(results)
    experiment = {
        "timestamp": timestamp,
        "task": "ai_plan_prompt_comparison",
        "context_summary": context_summary,
        "results": results,
        "winner": winner,
        "winner_reason": winner_reason,
    }
    _save_json_list(EXPERIMENT_RESULTS_PATH, experiment)
    _save_json_list(EXPERIMENT_CANDIDATES_PATH, candidates, limit=30)
    return experiment


def _format_list(items):
    items = _as_list(items)
    if not items:
        return "- 无"
    return "\n".join(f"- {item}" for item in items[:8])


def format_prompt_comparison_result(result):
    if not isinstance(result, dict):
        return "Prompt 版本对比实验暂时不可用。"

    context = result.get("context_summary", {})
    if not isinstance(context, dict):
        context = {}
    lines = [
        "===== Prompt 版本对比实验 =====",
        "",
        "任务：AI 下一阶段计划生成",
        (
            "上下文："
            f"Week {context.get('current_week', '')}，"
            f"当前专题：{context.get('current_topic', '') or '未知'}"
        ),
        "",
    ]

    for item in result.get("results", []):
        if not isinstance(item, dict):
            continue
        version = item.get("prompt_version", "未知")
        raw_score = item.get("raw_score")
        final_score = item.get(
            "final_score",
            item.get("score", "未评估"),
        )
        fallback_used = bool(item.get("fallback_used"))
        fallback_reason = item.get("fallback_reason") or "无"

        lines.extend([
            f"Prompt {version}:",
            f"- 计划标题：{item.get('plan_title', '') or '生成失败'}",
            "- 原始输出状态："
            + _bool_label(item.get("raw_success"), "成功", "失败"),
            "- JSON 解析："
            + _bool_label(item.get("parsed_success"), "成功", "失败"),
            "- Schema 校验："
            + _bool_label(item.get("schema_valid"), "通过", "未通过"),
            f"- 原始评分：{_score_label(raw_score)}",
            f"- 最终评分：{final_score}",
            f"- 状态：{item.get('quality_level', 'unknown')}",
            f"- fallback：{'是' if fallback_used else '否'}",
            f"- fallback 原因：{fallback_reason if fallback_used else '无'}",
            "- 严重问题：",
            _format_list(item.get("errors", [])),
            "- 质量提醒：",
            _format_list(item.get("warnings", [])),
            "- 说明：",
            _format_list(item.get("infos", [])),
            "",
        ])

    lines.extend([
        f"推荐版本：{result.get('winner', 'v1')}",
        f"原因：{result.get('winner_reason', '')}",
    ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    comparison = run_plan_prompt_comparison()
    print(format_prompt_comparison_result(comparison))
