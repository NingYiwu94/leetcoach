import json
from collections import Counter, defaultdict

from rag.rag_trace import RAG_TRACE_LOG_PATH


PERSONALIZED_TYPES = {
    "record",
    "review",
    "mistake",
    "problem_note",
    "ai_solution_note",
    "ai_solution",
    "ai_note",
    "stage_summary",
    "agent_memory",
    "silent_agent_memory",
    "personalized_memory",
}

BACKGROUND_TYPES = {
    "problem_bank",
    "topic_catalog",
    "curriculum",
}


def load_rag_trace_logs():
    if not RAG_TRACE_LOG_PATH.exists():
        return []
    try:
        data = json.loads(RAG_TRACE_LOG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rate(used, retrieved):
    if not retrieved:
        return 0.0
    return round(used / retrieved, 4)


def _format_rate(value):
    return f"{_as_float(value) * 100:.1f}%"


def _format_number(value):
    value = _as_float(value)
    return f"{value:.1f}"


def _evidence_items(record):
    if not isinstance(record, dict):
        return []
    trace = record.get("trace", {})
    if not isinstance(trace, dict):
        trace = record
    items = trace.get("evidence_items", [])
    return items if isinstance(items, list) else []


def _trace_dict(record):
    trace = record.get("trace", {}) if isinstance(record, dict) else {}
    return trace if isinstance(trace, dict) else {}


def _record_metric(record, key):
    if not isinstance(record, dict):
        return 0
    if key in record:
        return int(_as_float(record.get(key)))
    trace = _trace_dict(record)
    return int(_as_float(trace.get(key, 0)))


def _item_group(item):
    group = str(item.get("evidence_group", "") or "").strip()
    if group:
        return group
    doc_type = str(item.get("doc_type", "") or "").strip()
    if doc_type in PERSONALIZED_TYPES:
        return "personalized"
    if doc_type in BACKGROUND_TYPES:
        return "background"
    return "unknown"


def _title_for_problem(problem_titles, problem_id):
    titles = problem_titles.get(problem_id, Counter())
    if not titles:
        return ""
    return titles.most_common(1)[0][0]


def _build_diagnosis(summary, doc_type_stats, used_total):
    diagnosis = []
    avg_usage_rate = summary.get("avg_usage_rate", 0)
    personalized_share = summary.get("personalized_evidence_share", 0)
    personalized_usage = summary.get("avg_personalized_usage_rate", 0)
    background_usage = summary.get("avg_background_usage_rate", 0)

    if avg_usage_rate >= 0.5:
        diagnosis.append(
            f"RAG 平均使用率为 {_format_rate(avg_usage_rate)}，说明模型确实在使用检索到的上下文。"
        )
    elif avg_usage_rate >= 0.2:
        diagnosis.append(
            f"RAG 平均使用率为 {_format_rate(avg_usage_rate)}，有一定作用，但使用率仍需提升。"
        )
    else:
        diagnosis.append(
            f"RAG 平均使用率为 {_format_rate(avg_usage_rate)}，模型较少使用检索结果，建议优化 Prompt 或文档构建。"
        )

    if personalized_share >= 0.55 and personalized_usage >= 0.45:
        diagnosis.append(
            "个性化证据占比和使用率较好，RAG 正在更多利用用户真实学习历史。"
        )
    elif personalized_share < 0.45:
        diagnosis.append(
            "个性化证据占比偏低，当前 RAG 可能仍较多依赖题库背景；后续应提升 records、reviews、problem_notes、stage_summary 等文档的召回。"
        )
    elif personalized_usage < 0.35:
        diagnosis.append(
            "个性化证据已被检索到，但使用率偏低；建议继续强化 Prompt 中“优先使用个人历史”的要求。"
        )

    problem_bank_used = doc_type_stats.get("problem_bank", {}).get("used", 0)
    if used_total and problem_bank_used / used_total >= 0.45:
        diagnosis.append(
            "problem_bank 使用占比较高。它提供的是题库背景，不完全等同于个性化学习记忆；应重点观察 record、review、problem_note、ai_solution_note 等个人历史文档的使用率。"
        )

    if background_usage > personalized_usage and summary.get("avg_background_retrieved_count", 0):
        diagnosis.append(
            "背景证据使用率高于个性化证据，说明检索排序或文档内容仍可能偏向通用题库信息。"
        )

    if doc_type_stats:
        best = sorted(
            doc_type_stats.items(),
            key=lambda item: (item[1].get("usage_rate", 0), item[1].get("used", 0)),
            reverse=True,
        )[0]
        diagnosis.append(
            f"{best[0]} 类型文档当前使用率最高，可作为后续 RAG 文档构建的观察对象。"
        )

    return diagnosis


def summarize_rag_traces(limit=20):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 20

    records = [
        item for item in load_rag_trace_logs()[-limit:]
        if isinstance(item, dict)
    ]
    total_traces = len(records)
    if not total_traces:
        return {
            "total_traces": 0,
            "avg_retrieved_count": 0.0,
            "avg_used_count": 0.0,
            "avg_usage_rate": 0.0,
            "avg_personalized_retrieved_count": 0.0,
            "avg_personalized_used_count": 0.0,
            "avg_personalized_usage_rate": 0.0,
            "avg_background_retrieved_count": 0.0,
            "avg_background_used_count": 0.0,
            "avg_background_usage_rate": 0.0,
            "personalized_evidence_share": 0.0,
            "doc_type_stats": {},
            "top_used_problems": [],
            "frequently_unused_docs": [],
            "diagnosis": ["暂无 RAG 证据链记录，请先运行 RAG A/B 实验。"],
        }

    retrieved_total = 0
    used_total = 0
    personalized_retrieved_total = 0
    personalized_used_total = 0
    background_retrieved_total = 0
    background_used_total = 0
    doc_type_working = defaultdict(lambda: {"retrieved": 0, "used": 0})
    problem_used = Counter()
    problem_titles = defaultdict(Counter)
    doc_working = {}

    for record in records:
        evidence_items = _evidence_items(record)
        retrieved_total += _record_metric(record, "retrieved_count") or len(evidence_items)
        used_total += _record_metric(record, "used_count") or len(
            [item for item in evidence_items if item.get("used_in_plan")]
        )

        p_retrieved = _record_metric(record, "personalized_retrieved_count")
        p_used = _record_metric(record, "personalized_used_count")
        b_retrieved = _record_metric(record, "background_retrieved_count")
        b_used = _record_metric(record, "background_used_count")

        if not (p_retrieved or p_used or b_retrieved or b_used):
            for item in evidence_items:
                group = _item_group(item)
                used = bool(item.get("used_in_plan"))
                if group == "personalized":
                    p_retrieved += 1
                    if used:
                        p_used += 1
                elif group == "background":
                    b_retrieved += 1
                    if used:
                        b_used += 1

        personalized_retrieved_total += p_retrieved
        personalized_used_total += p_used
        background_retrieved_total += b_retrieved
        background_used_total += b_used

        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            doc_type = str(item.get("doc_type", "") or "unknown")
            group = _item_group(item)
            if group == "personalized" and doc_type == "ai_solution":
                doc_type = "ai_solution_note"
            problem_id = str(item.get("problem_id", "") or "").strip()
            title = str(item.get("title", "") or "").strip()
            doc_id = str(item.get("doc_id", "") or "").strip()
            used = bool(item.get("used_in_plan"))

            doc_type_working[doc_type]["retrieved"] += 1
            if used:
                doc_type_working[doc_type]["used"] += 1
                if problem_id:
                    problem_used[problem_id] += 1
                    if title:
                        problem_titles[problem_id][title] += 1

            key = doc_id or f"{problem_id}:{title}"
            if key not in doc_working:
                doc_working[key] = {
                    "doc_id": doc_id,
                    "problem_id": problem_id,
                    "title": title,
                    "doc_type": doc_type,
                    "evidence_group": group,
                    "retrieved_count": 0,
                    "used_count": 0,
                }
            doc_working[key]["retrieved_count"] += 1
            if used:
                doc_working[key]["used_count"] += 1

    doc_type_stats = {}
    for doc_type, stats in sorted(doc_type_working.items()):
        retrieved = stats["retrieved"]
        used = stats["used"]
        doc_type_stats[doc_type] = {
            "retrieved": retrieved,
            "used": used,
            "usage_rate": _rate(used, retrieved),
        }

    top_used_problems = [
        {
            "problem_id": problem_id,
            "title": _title_for_problem(problem_titles, problem_id),
            "used_count": count,
        }
        for problem_id, count in problem_used.most_common(10)
    ]

    frequently_unused_docs = sorted(
        [
            item for item in doc_working.values()
            if item.get("retrieved_count", 0) >= 2
            and item.get("used_count", 0) == 0
        ],
        key=lambda item: item.get("retrieved_count", 0),
        reverse=True,
    )[:10]

    avg_retrieved_count = round(retrieved_total / total_traces, 2)
    avg_used_count = round(used_total / total_traces, 2)
    avg_personalized_retrieved_count = round(personalized_retrieved_total / total_traces, 2)
    avg_personalized_used_count = round(personalized_used_total / total_traces, 2)
    avg_background_retrieved_count = round(background_retrieved_total / total_traces, 2)
    avg_background_used_count = round(background_used_total / total_traces, 2)

    summary = {
        "total_traces": total_traces,
        "limit": limit,
        "avg_retrieved_count": avg_retrieved_count,
        "avg_used_count": avg_used_count,
        "avg_usage_rate": _rate(avg_used_count, avg_retrieved_count),
        "avg_personalized_retrieved_count": avg_personalized_retrieved_count,
        "avg_personalized_used_count": avg_personalized_used_count,
        "avg_personalized_usage_rate": _rate(
            avg_personalized_used_count,
            avg_personalized_retrieved_count,
        ),
        "avg_background_retrieved_count": avg_background_retrieved_count,
        "avg_background_used_count": avg_background_used_count,
        "avg_background_usage_rate": _rate(
            avg_background_used_count,
            avg_background_retrieved_count,
        ),
        "personalized_evidence_share": _rate(
            personalized_retrieved_total,
            retrieved_total,
        ),
        "personalized_used_share": _rate(
            personalized_used_total,
            used_total,
        ),
        "doc_type_stats": doc_type_stats,
        "top_used_problems": top_used_problems,
        "frequently_unused_docs": frequently_unused_docs,
    }
    summary["diagnosis"] = _build_diagnosis(summary, doc_type_stats, used_total)
    return summary


def format_rag_trace_summary(summary):
    if not isinstance(summary, dict) or not summary.get("total_traces"):
        diagnosis = []
        if isinstance(summary, dict):
            diagnosis = summary.get("diagnosis", [])
        return "\n".join(diagnosis) if diagnosis else "暂无 RAG 证据链统计记录。"

    lines = [
        "===== RAG 证据链统计报告 =====",
        "",
        f"统计范围：最近 {summary.get('total_traces', 0)} 次 RAG 计划生成",
        "",
        "总体情况：",
        f"- 平均检索记忆数：{_format_number(summary.get('avg_retrieved_count'))}",
        f"- 平均被引用记忆数：{_format_number(summary.get('avg_used_count'))}",
        f"- 平均使用率：{_format_rate(summary.get('avg_usage_rate'))}",
        "",
        "个性化证据：",
        f"- 平均检索数：{_format_number(summary.get('avg_personalized_retrieved_count'))}",
        f"- 平均使用数：{_format_number(summary.get('avg_personalized_used_count'))}",
        f"- 使用率：{_format_rate(summary.get('avg_personalized_usage_rate'))}",
        f"- 检索占比：{_format_rate(summary.get('personalized_evidence_share'))}",
        f"- 使用占比：{_format_rate(summary.get('personalized_used_share'))}",
        "",
        "题库背景：",
        f"- 平均检索数：{_format_number(summary.get('avg_background_retrieved_count'))}",
        f"- 平均使用数：{_format_number(summary.get('avg_background_used_count'))}",
        f"- 使用率：{_format_rate(summary.get('avg_background_usage_rate'))}",
        "",
        "按文档类型：",
    ]

    doc_type_stats = summary.get("doc_type_stats", {})
    if isinstance(doc_type_stats, dict) and doc_type_stats:
        for doc_type, stats in sorted(
            doc_type_stats.items(),
            key=lambda item: item[1].get("used", 0),
            reverse=True,
        ):
            lines.append(
                f"- {doc_type}：检索 {stats.get('retrieved', 0)} 次，"
                f"使用 {stats.get('used', 0)} 次，"
                f"使用率 {_format_rate(stats.get('usage_rate'))}"
            )
    else:
        lines.append("- 暂无")

    lines.extend(["", "最常被引用的题目："])
    top_used = summary.get("top_used_problems", [])
    if isinstance(top_used, list) and top_used:
        for index, item in enumerate(top_used[:8], start=1):
            label = " ".join(
                part for part in [item.get("problem_id", ""), item.get("title", "")]
                if part
            )
            lines.append(f"{index}. {label or '未知题目'}：{item.get('used_count', 0)} 次")
    else:
        lines.append("- 暂无")

    lines.extend(["", "经常被检索但未使用的文档："])
    unused = summary.get("frequently_unused_docs", [])
    if isinstance(unused, list) and unused:
        for index, item in enumerate(unused[:8], start=1):
            label = " ".join(
                part for part in [item.get("problem_id", ""), item.get("title", "")]
                if part
            )
            lines.append(
                f"{index}. {item.get('doc_id') or '未知文档'}，"
                f"{label or '无题目信息'}，"
                f"类型 {item.get('doc_type', 'unknown')}，"
                f"检索 {item.get('retrieved_count', 0)} 次，"
                f"使用 {item.get('used_count', 0)} 次"
            )
    else:
        lines.append("- 暂无")

    lines.extend(["", "诊断："])
    for item in summary.get("diagnosis", []) or []:
        lines.append(f"- {item}")

    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    report = summarize_rag_traces(limit=20)
    print(format_rag_trace_summary(report))
