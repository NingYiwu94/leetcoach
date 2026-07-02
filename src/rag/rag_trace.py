import json
import re
from datetime import datetime
from pathlib import Path

from rag.rag_engine import (
    canonical_doc_type,
    evidence_group,
    is_background_doc,
    is_personalized_doc,
)

from app_paths import BASE_DIR
RAG_TRACE_LOG_PATH = BASE_DIR / "data" / "rag_trace_logs.json"

SOURCE_FILE_MAP = {
    "records": "records.json",
    "reviews": "reviews.json",
    "problem_notes": "problem_notes.json",
    "ai_solution_notes": "ai_solution_notes.json",
    "problem_bank": "problem_bank.json",
    "personalized_memory": "rag_personalized_memory_enhanced.json",
}

DOC_TYPE_MAP = {
    "records": "record",
    "reviews": "review",
    "problem_notes": "problem_note",
    "ai_solution_notes": "ai_solution_note",
    "problem_bank": "problem_bank",
    "stage_summary": "stage_summary",
    "agent_memory": "agent_memory",
    "silent_agent_memory": "silent_agent_memory",
    "personalized_memory": "personalized_memory",
}

HISTORY_MARKERS = [
    "历史",
    "之前",
    "曾经",
    "过去",
    "相似问题",
    "复盘",
    "错因",
    "薄弱",
]


def _short_text(text, limit=300):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _as_list(value):
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    if value not in (None, ""):
        return [value]
    return []


def _normalize_text(text):
    return str(text or "").lower()


def _extract_keywords(text):
    text = str(text or "")
    keywords = set()
    for token in re.findall(r"[a-zA-Z0-9_+-]{2,}", text):
        keywords.add(token.lower())
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        if len(chunk) <= 8:
            keywords.add(chunk)
        for size in (2, 3, 4):
            for index in range(0, max(0, len(chunk) - size + 1)):
                keywords.add(chunk[index:index + size])
    return {
        item for item in keywords
        if len(item) >= 2 and item not in {"问题", "记录", "计划", "学习", "题目"}
    }


def _flatten_plan_fields(plan):
    fields = {}
    if not isinstance(plan, dict):
        return fields

    for key in ("title", "reason"):
        value = plan.get(key)
        if value:
            fields[key] = str(value)

    focus = plan.get("recommended_focus", [])
    if isinstance(focus, list) and focus:
        fields["recommended_focus"] = " ".join(str(item) for item in focus)

    days = plan.get("days", {})
    if isinstance(days, dict):
        iterable = days.items()
    elif isinstance(days, list):
        iterable = enumerate(days, start=1)
    else:
        iterable = []

    for day_key, day in iterable:
        if not isinstance(day, dict):
            continue
        for field in ("goal", "reason", "date_note"):
            value = day.get(field)
            if value:
                fields[f"days.{day_key}.{field}"] = str(value)
        problems = day.get("problems", [])
        if isinstance(problems, list):
            fields[f"days.{day_key}.problems"] = " ".join(
                str(item) for item in problems
            )
    return fields


def extract_plan_text(plan):
    return "\n".join(_flatten_plan_fields(plan).values())


def _doc_terms(doc):
    terms = set()
    problem_id = str(doc.get("problem_id", "") or "").strip()
    title = str(doc.get("title", "") or "").strip()
    content = str(doc.get("content", "") or "")
    metadata = doc.get("metadata", {})
    if problem_id:
        terms.add(problem_id)
    if title:
        terms.add(title)
        terms.update(_extract_keywords(title))
    if isinstance(metadata, dict):
        for key in ("topic", "topics", "pattern", "patterns", "mistake_type", "difficulty", "status"):
            for item in _as_list(metadata.get(key)):
                terms.add(str(item))
                terms.update(_extract_keywords(str(item)))
    terms.update(list(_extract_keywords(content))[:20])
    return {str(item).strip() for item in terms if str(item).strip()}


def detect_context_usage(doc, plan_text, plan=None):
    plan_text = str(plan_text or "")
    plan_text_norm = _normalize_text(plan_text)
    fields = _flatten_plan_fields(plan) if isinstance(plan, dict) else {"plan": plan_text}
    matched_fields = []
    reasons = []

    problem_id = str(doc.get("problem_id", "") or "").strip()
    if problem_id and problem_id in plan_text:
        reasons.append(f"计划中出现题号 {problem_id}")

    title = str(doc.get("title", "") or "").strip()
    if title and title in plan_text:
        reasons.append(f"计划中出现标题 {title}")

    metadata = doc.get("metadata", {})
    metadata_terms = []
    if isinstance(metadata, dict):
        for key in ("topic", "topics", "pattern", "patterns", "mistake_type"):
            metadata_terms.extend(str(item) for item in _as_list(metadata.get(key)))
    for term in metadata_terms:
        if term and term in plan_text:
            reasons.append(f"计划中出现相关标签 {term}")
            break

    doc_keywords = _doc_terms(doc)
    matched_keywords = []
    for keyword in sorted(doc_keywords, key=len, reverse=True):
        if len(keyword) < 2:
            continue
        if _normalize_text(keyword) in plan_text_norm:
            matched_keywords.append(keyword)
        if len(matched_keywords) >= 3:
            break
    if matched_keywords:
        reasons.append("计划中出现证据关键词：" + "、".join(matched_keywords))

    has_history_marker = any(marker in plan_text for marker in HISTORY_MARKERS)
    if has_history_marker and (problem_id and problem_id in plan_text or matched_keywords):
        reasons.append("计划使用了历史/复盘表达，并靠近相关题号或题型")

    terms = set()
    if problem_id:
        terms.add(problem_id)
    if title:
        terms.add(title)
    terms.update(metadata_terms)
    terms.update(matched_keywords)
    for path, value in fields.items():
        value_norm = _normalize_text(value)
        if any(str(term) and _normalize_text(term) in value_norm for term in terms):
            matched_fields.append(path)

    used = bool(reasons)
    return {
        "used": used,
        "matched_fields": matched_fields[:8],
        "match_reason": "；".join(reasons[:4]) if reasons else "未发现明确引用",
    }


def _normalize_documents(retrieved_context):
    if isinstance(retrieved_context, dict):
        documents = retrieved_context.get("documents", [])
    else:
        documents = retrieved_context
    return documents if isinstance(documents, list) else []


def _evidence_item(doc, usage):
    source = str(doc.get("source", "") or "")
    doc_type = canonical_doc_type(DOC_TYPE_MAP.get(source, doc.get("doc_type", source)))
    group = evidence_group({"doc_type": doc_type, "source": source})
    return {
        "doc_id": doc.get("id", ""),
        "doc_type": doc_type,
        "evidence_group": group,
        "source_file": SOURCE_FILE_MAP.get(source, source),
        "problem_id": doc.get("problem_id", ""),
        "title": doc.get("title", ""),
        "text_preview": _short_text(doc.get("content", ""), 300),
        "used_in_plan": bool(usage.get("used")),
        "matched_fields": usage.get("matched_fields", []),
        "match_reason": usage.get("match_reason", ""),
    }


def build_rag_trace(query, retrieved_context, generated_plan):
    documents = _normalize_documents(retrieved_context)
    plan_text = extract_plan_text(generated_plan)
    evidence_items = []

    for doc in documents:
        if not isinstance(doc, dict):
            continue
        usage = detect_context_usage(doc, plan_text, generated_plan)
        evidence_items.append(_evidence_item(doc, usage))

    used_items = [item for item in evidence_items if item.get("used_in_plan")]
    unused_items = [item for item in evidence_items if not item.get("used_in_plan")]
    personalized_items = [
        item for item in evidence_items
        if item.get("evidence_group") == "personalized"
        or is_personalized_doc(item)
    ]
    background_items = [
        item for item in evidence_items
        if item.get("evidence_group") == "background"
        or is_background_doc(item)
    ]
    personalized_used_items = [
        item for item in personalized_items if item.get("used_in_plan")
    ]
    background_used_items = [
        item for item in background_items if item.get("used_in_plan")
    ]
    enhanced_memory_items = [
        item for item in evidence_items
        if item.get("doc_type") == "personalized_memory"
    ]
    enhanced_memory_used_items = [
        item for item in enhanced_memory_items if item.get("used_in_plan")
    ]
    personalized_retrieved_count = len(personalized_items)
    personalized_used_count = len(personalized_used_items)
    background_retrieved_count = len(background_items)
    background_used_count = len(background_used_items)
    enhanced_memory_retrieved_count = len(enhanced_memory_items)
    enhanced_memory_used_count = len(enhanced_memory_used_items)
    personalized_usage_rate = (
        round(personalized_used_count / personalized_retrieved_count, 4)
        if personalized_retrieved_count else 0
    )
    background_usage_rate = (
        round(background_used_count / background_retrieved_count, 4)
        if background_retrieved_count else 0
    )
    enhanced_memory_usage_rate = (
        round(enhanced_memory_used_count / enhanced_memory_retrieved_count, 4)
        if enhanced_memory_retrieved_count else 0
    )
    unsupported_claims = []
    if any(marker in plan_text for marker in HISTORY_MARKERS) and not used_items:
        unsupported_claims.append(
            "计划中出现历史/复盘类表述，但没有检测到明确 RAG 证据引用。"
        )

    summary = (
        f"本次计划检索到 {len(evidence_items)} 条历史记忆，"
        f"其中 {len(used_items)} 条在计划中被明确引用。"
    )
    if unused_items:
        summary += f"另有 {len(unused_items)} 条检索结果暂未在计划中体现。"

    return {
        "query": str(query or ""),
        "retrieved_count": len(evidence_items),
        "used_count": len(used_items),
        "unused_count": len(unused_items),
        "personalized_retrieved_count": personalized_retrieved_count,
        "personalized_used_count": personalized_used_count,
        "personalized_usage_rate": personalized_usage_rate,
        "background_retrieved_count": background_retrieved_count,
        "background_used_count": background_used_count,
        "background_usage_rate": background_usage_rate,
        "enhanced_memory_retrieved_count": enhanced_memory_retrieved_count,
        "enhanced_memory_used_count": enhanced_memory_used_count,
        "enhanced_memory_usage_rate": enhanced_memory_usage_rate,
        "personalized_doc_ids": [
            item.get("doc_id", "") for item in personalized_items
            if item.get("doc_id")
        ],
        "background_doc_ids": [
            item.get("doc_id", "") for item in background_items
            if item.get("doc_id")
        ],
        "enhanced_memory_doc_ids": [
            item.get("doc_id", "") for item in enhanced_memory_items
            if item.get("doc_id")
        ],
        "used_enhanced_doc_ids": [
            item.get("doc_id", "") for item in enhanced_memory_used_items
            if item.get("doc_id")
        ],
        "evidence_items": evidence_items,
        "unsupported_claims": unsupported_claims,
        "summary": summary,
    }


def _load_json_list(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup_path = path.with_name(
            f"{path.stem}.broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        )
        try:
            path.replace(backup_path)
        except OSError:
            pass
        return []
    except OSError:
        return []
    return data if isinstance(data, list) else []


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_rag_trace_log(task, trace, limit=100):
    if not isinstance(trace, dict):
        return None
    used_doc_ids = [
        item.get("doc_id", "")
        for item in trace.get("evidence_items", [])
        if item.get("used_in_plan")
    ]
    unused_doc_ids = [
        item.get("doc_id", "")
        for item in trace.get("evidence_items", [])
        if not item.get("used_in_plan")
    ]
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task": task,
        "query": trace.get("query", ""),
        "retrieved_count": trace.get("retrieved_count", 0),
        "used_count": trace.get("used_count", 0),
        "unused_count": trace.get("unused_count", 0),
        "personalized_retrieved_count": trace.get("personalized_retrieved_count", 0),
        "personalized_used_count": trace.get("personalized_used_count", 0),
        "personalized_usage_rate": trace.get("personalized_usage_rate", 0),
        "background_retrieved_count": trace.get("background_retrieved_count", 0),
        "background_used_count": trace.get("background_used_count", 0),
        "background_usage_rate": trace.get("background_usage_rate", 0),
        "enhanced_memory_retrieved_count": trace.get("enhanced_memory_retrieved_count", 0),
        "enhanced_memory_used_count": trace.get("enhanced_memory_used_count", 0),
        "enhanced_memory_usage_rate": trace.get("enhanced_memory_usage_rate", 0),
        "personalized_doc_ids": trace.get("personalized_doc_ids", []),
        "background_doc_ids": trace.get("background_doc_ids", []),
        "enhanced_memory_doc_ids": trace.get("enhanced_memory_doc_ids", []),
        "used_enhanced_doc_ids": trace.get("used_enhanced_doc_ids", []),
        "used_doc_ids": used_doc_ids,
        "unused_doc_ids": unused_doc_ids,
        "trace": trace,
    }
    logs = _load_json_list(RAG_TRACE_LOG_PATH)
    logs.append(record)
    _save_json(RAG_TRACE_LOG_PATH, logs[-limit:])
    return record


def get_recent_rag_traces(limit=5):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 5
    return list(reversed(_load_json_list(RAG_TRACE_LOG_PATH)[-limit:]))


def _format_rate(used, retrieved):
    if not retrieved:
        return "0.0%"
    return f"{used / retrieved * 100:.1f}%"


def format_rag_trace_log(record):
    if not isinstance(record, dict):
        return "暂无 RAG 证据链记录。"
    trace = record.get("trace", {})
    if not isinstance(trace, dict):
        trace = {}
    retrieved = int(record.get("retrieved_count", trace.get("retrieved_count", 0)) or 0)
    used = int(record.get("used_count", trace.get("used_count", 0)) or 0)
    lines = [
        f"{record.get('timestamp', '未知时间')}",
        f"查询：{record.get('query', trace.get('query', ''))}",
        f"检索：{retrieved} 条",
        f"使用：{used} 条",
        f"使用率：{_format_rate(used, retrieved)}",
        "",
        "被引用记忆：",
    ]
    used_items = [
        item for item in trace.get("evidence_items", [])
        if isinstance(item, dict) and item.get("used_in_plan")
    ]
    if used_items:
        for item in used_items[:8]:
            label = " ".join(
                part for part in [str(item.get("problem_id", "")), item.get("title", "")]
                if part
            )
            lines.append(f"- {label or item.get('doc_id', '未知文档')}：{item.get('match_reason', '')}")
    else:
        lines.append("- 无")

    unsupported = trace.get("unsupported_claims", [])
    if unsupported:
        lines.extend(["", "未支持声明："])
        lines.extend(f"- {item}" for item in unsupported[:5])

    lines.extend(["", "说明：", trace.get("summary", "")])
    return "\n".join(lines).rstrip()


def format_recent_rag_traces(records):
    records = records if isinstance(records, list) else []
    if not records:
        return "暂无 RAG 证据链记录。请先运行一次 AI 计划生成或 RAG A/B 实验。"
    lines = ["===== 最近 RAG 证据链 =====", ""]
    for index, record in enumerate(records[:5], start=1):
        lines.append(f"{index}. " + format_rag_trace_log(record))
        lines.append("")
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    print(format_recent_rag_traces(get_recent_rag_traces(limit=1)))
