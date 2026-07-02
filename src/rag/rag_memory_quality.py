import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from rag.rag_engine import (
    PROBLEM_BANK_PATH,
    build_rag_documents,
    clean_problem_id,
    document_doc_type,
    is_personalized_doc,
    load_json,
    short_text,
)


from app_paths import BASE_DIR
DATA_DIR = BASE_DIR / "data"
QUALITY_REPORT_PATH = DATA_DIR / "rag_memory_quality_report.json"
ENHANCED_MEMORY_PATH = DATA_DIR / "rag_personalized_memory_enhanced.json"

PERSONALIZED_TYPES = {
    "record",
    "review",
    "mistake",
    "problem_note",
    "ai_solution_note",
    "stage_summary",
    "agent_memory",
    "silent_agent_memory",
}

STAGE_TYPES = {"stage_summary", "agent_memory", "silent_agent_memory"}
CODE_PATTERNS = [
    r"```",
    r"\bclass\s+Solution\b",
    r"\bdef\s+\w+\s*\(",
    r"\bpublic\s*:",
    r"#include\s*<",
    r"\bvector\s*<",
    r"\bListNode\b",
    r"\bTreeNode\b",
]
BEHAVIOR_MARKERS = [
    "AC",
    "Accepted",
    "未通过",
    "Wrong Answer",
    "看提示",
    "复习",
    "掌握",
    "mastery",
    "status",
    "done",
    "next_review",
]
PERSONAL_MARKERS = [
    "mistake",
    "错因",
    "卡点",
    "note",
    "笔记",
    "掌握",
    "reason",
    "review",
    "复习",
    "main_problem",
    "主要问题",
]


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save_json_with_backup(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = path.with_name(
                f"{path.stem}.broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            )
            try:
                path.replace(backup)
            except OSError:
                pass
        except OSError:
            pass
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_rag_documents():
    try:
        documents = build_rag_documents()
    except Exception:
        documents = []
    return documents if isinstance(documents, list) else []


def _doc_text(doc):
    if not isinstance(doc, dict):
        return ""
    return str(doc.get("content") or doc.get("text") or "").strip()


def _metadata(doc):
    metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
    return metadata if isinstance(metadata, dict) else {}


def _has_code(text):
    return any(re.search(pattern, text or "", re.IGNORECASE) for pattern in CODE_PATTERNS)


def _has_any(text, markers):
    text = str(text or "")
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def _has_topic_or_tags(doc):
    metadata = _metadata(doc)
    for key in ("topic", "topics", "pattern", "patterns", "tags", "difficulty", "mastery"):
        value = metadata.get(key)
        if isinstance(value, list) and any(str(item).strip() for item in value):
            return True
        if isinstance(value, str) and value.strip():
            return True
    problem_id = clean_problem_id(doc.get("problem_id", ""))
    if _topics_text(_problem_info(problem_id)):
        return True
    text = _doc_text(doc)
    return _has_any(text, ["专题", "topic", "pattern", "双指针", "链表", "哈希", "数组"])


def _has_behavior(doc):
    metadata = _metadata(doc)
    if any(metadata.get(key) not in (None, "") for key in ("status", "done", "mastery", "next_review_date")):
        return True
    return _has_any(_doc_text(doc), BEHAVIOR_MARKERS)


def _has_personal_problem(doc):
    metadata = _metadata(doc)
    if any(metadata.get(key) not in (None, "") for key in ("mistake_type", "mistake_note", "mastery")):
        return True
    return _has_any(_doc_text(doc), PERSONAL_MARKERS)


def _quality_level(score):
    if score >= 85:
        return "good"
    if score >= 70:
        return "warning"
    return "poor"


def evaluate_personalized_doc_quality(doc):
    if not isinstance(doc, dict) or not is_personalized_doc(doc):
        return None

    doc_type = document_doc_type(doc)
    if doc_type not in PERSONALIZED_TYPES:
        return None

    score = 100
    issues = []
    suggestions = []
    text = _doc_text(doc)
    title = str(doc.get("title", "") or "").strip()
    problem_id = clean_problem_id(doc.get("problem_id", ""))
    stage_like = doc_type in STAGE_TYPES

    if not text:
        score -= 50
        issues.append("文本为空")
        suggestions.append("补充可被计划生成引用的学习事实。")
    elif len(text) < 30:
        score -= 20
        issues.append("文本过短")
        suggestions.append("补充状态、卡点、复习原因或掌握程度。")

    if not problem_id and not stage_like:
        score -= 10
        issues.append("缺少题号")
        suggestions.append("补充 problem_id，方便计划定位具体题目。")

    if not title and not stage_like:
        score -= 10
        issues.append("缺少标题")
        suggestions.append("补充题目标题。")

    if not _has_topic_or_tags(doc):
        score -= 10
        issues.append("缺少专题或模式标签")
        suggestions.append("补充 topic/pattern/tags，帮助计划控制专题路径。")

    if not _has_behavior(doc):
        score -= 15
        issues.append("缺少用户行为状态")
        suggestions.append("补充 AC、未通过、复习、掌握程度等信息。")

    if not _has_personal_problem(doc):
        score -= 15
        issues.append("缺少个性化问题")
        suggestions.append("补充 mistake_type、mistake_note、复习结果或掌握程度。")

    if _has_code(text):
        score -= 20
        issues.append("包含疑似完整代码")
        suggestions.append("计划 RAG 中只保留思路、易错点和复杂度。")

    if len(text) > 1000:
        score -= 10
        issues.append("文本过长")
        suggestions.append("压缩为 80-250 字的计划证据摘要。")

    if doc_type in {"problem_note", "ai_solution_note"} and not _has_behavior(doc):
        score -= 20
        issues.append("更像题目介绍，缺少用户历史信息")
        suggestions.append("补充用户理解状态或复习价值。")

    score = max(0, min(100, score))
    return {
        "doc_id": doc.get("id", ""),
        "doc_type": doc_type,
        "problem_id": problem_id,
        "title": title,
        "score": score,
        "quality_level": _quality_level(score),
        "issues": issues,
        "suggestions": suggestions,
    }


def _problem_info(problem_id):
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    if not isinstance(problem_bank, dict):
        return {}
    problem = problem_bank.get(clean_problem_id(problem_id), {})
    return problem if isinstance(problem, dict) else {}


def _topics_text(problem):
    topics = problem.get("topics", []) if isinstance(problem, dict) else []
    if isinstance(topics, list):
        return "、".join(str(item) for item in topics if item)
    return str(topics or "")


def _sanitize_memory_text(text):
    text = re.sub(r"```[\s\S]*?```", " ", str(text or ""))
    text = re.sub(r"\bclass\s+Solution[\s\S]*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return short_text(text, 250)


def _bounded_memory_text(text):
    text = _sanitize_memory_text(text)
    if len(text) <= 250:
        return text
    return text[:250].rstrip() + "..."


def rewrite_personalized_memory_doc(doc):
    if not isinstance(doc, dict):
        return {"doc_id": "", "rewritten_text": "", "rewrite_reason": "文档无效"}

    doc_type = document_doc_type(doc)
    problem_id = clean_problem_id(doc.get("problem_id", ""))
    problem = _problem_info(problem_id)
    title = str(doc.get("title") or problem.get("title") or "").strip()
    topics = _topics_text(problem)
    metadata = _metadata(doc)
    text = _sanitize_memory_text(_doc_text(doc))

    status = metadata.get("status", "")
    mastery = metadata.get("mastery", "")
    done = metadata.get("done", "")
    next_review = metadata.get("next_review_date", "")

    if doc_type == "record":
        rewritten = (
            f"用户在 {problem_id} {title} 的最近记录状态为 {status or '未知'}。"
            f"该题属于 {topics or '未标注专题'}。"
            f"历史记录摘要：{text}。后续计划可据此安排复习、重做或同专题巩固。"
        )
        reason = "补充题号、标题、状态、专题和用户历史记录摘要。"
    elif doc_type == "review":
        rewritten = (
            f"用户需要复习 {problem_id} {title}。"
            f"下次复习日期为 {next_review or '未设置'}，当前完成状态为 {done}。"
            f"复习原因摘要：{text}。该题可作为后续计划中的复习任务。"
        )
        reason = "补充复习状态、复习日期和计划用途。"
    elif doc_type == "problem_note":
        rewritten = (
            f"用户对 {problem_id} {title} 的个人笔记显示：{text}。"
            f"掌握程度为 {mastery or '未知'}，专题为 {topics or '未标注'}。"
            "这可反映其理解状态和后续复习价值。"
        )
        reason = "将个人笔记压缩为可用于计划生成的掌握度证据。"
    elif doc_type == "ai_solution_note":
        rewritten = (
            f"AI 题解笔记显示 {problem_id} {title} 的关键复习材料为：{text}。"
            "该内容只保留思路、易错点和复杂度，可作为复习参考，不包含完整代码。"
        )
        reason = "移除代码风险，只保留思路、易错点和复杂度摘要。"
    elif doc_type in STAGE_TYPES:
        rewritten = (
            f"阶段或 Agent 记忆显示：{text}。"
            "后续计划应优先关注其中提到的主要问题、进度状态和推荐行动。"
        )
        reason = "提取阶段状态、主要问题和后续行动方向。"
    else:
        rewritten = (
            f"个性化学习记忆显示：{text}。"
            "后续计划可将其作为用户真实学习历史证据。"
        )
        reason = "将原始记忆压缩为计划可引用摘要。"

    return {
        "doc_id": doc.get("id", ""),
        "rewritten_text": _bounded_memory_text(rewritten),
        "rewrite_reason": reason,
    }


def _enhanced_doc_id(doc, rewritten_text):
    raw = "|".join([
        str(doc.get("id", "")),
        str(doc.get("problem_id", "")),
        rewritten_text,
    ])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    doc_type = document_doc_type(doc)
    problem_id = clean_problem_id(doc.get("problem_id", "")) or "global"
    return f"enhanced_{doc_type}_{problem_id}_{digest}"


def build_enhanced_personalized_memory_docs(audit_items=None):
    documents = load_rag_documents()
    quality_by_id = {}
    if isinstance(audit_items, list):
        for item in audit_items:
            if isinstance(item, dict):
                quality_by_id[item.get("doc_id", "")] = item

    enhanced = []
    for doc in documents:
        if not isinstance(doc, dict) or not is_personalized_doc(doc):
            continue
        quality = quality_by_id.get(doc.get("id", ""))
        if not quality:
            quality = evaluate_personalized_doc_quality(doc)
        if not quality or quality.get("quality_level") == "good":
            continue
        rewrite = rewrite_personalized_memory_doc(doc)
        rewritten_text = rewrite.get("rewritten_text", "")
        if not rewritten_text:
            continue
        enhanced.append({
            "doc_id": _enhanced_doc_id(doc, rewritten_text),
            "source_doc_id": doc.get("id", ""),
            "doc_type": "personalized_memory",
            "problem_id": clean_problem_id(doc.get("problem_id", "")),
            "title": doc.get("title", ""),
            "text": rewritten_text,
            "metadata": {
                "source_doc_type": document_doc_type(doc),
                "quality_score": quality.get("score", 0),
                "quality_level": quality.get("quality_level", ""),
                "generated_by": "rule_based_memory_rewrite",
                "rewrite_reason": rewrite.get("rewrite_reason", ""),
            },
        })

    _save_json_with_backup(ENHANCED_MEMORY_PATH, enhanced)
    return enhanced


def run_rag_memory_quality_audit():
    documents = [
        doc for doc in load_rag_documents()
        if isinstance(doc, dict) and is_personalized_doc(doc)
    ]
    evaluations = []
    low_quality_docs = []
    type_scores = defaultdict(list)

    for doc in documents:
        result = evaluate_personalized_doc_quality(doc)
        if not result:
            continue
        evaluations.append(result)
        type_scores[result["doc_type"]].append(result["score"])
        if result["quality_level"] in {"warning", "poor"}:
            rewrite = rewrite_personalized_memory_doc(doc)
            low_quality_docs.append({
                **result,
                "rewritten_text": rewrite.get("rewritten_text", ""),
                "rewrite_reason": rewrite.get("rewrite_reason", ""),
            })

    scores = [item["score"] for item in evaluations]
    doc_type_summary = {}
    for doc_type, values in sorted(type_scores.items()):
        doc_type_summary[doc_type] = {
            "count": len(values),
            "avg_score": round(sum(values) / len(values), 2) if values else 0,
        }

    enhanced_docs = build_enhanced_personalized_memory_docs(evaluations)
    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_personalized_docs": len(evaluations),
        "good_count": len([item for item in evaluations if item["quality_level"] == "good"]),
        "warning_count": len([item for item in evaluations if item["quality_level"] == "warning"]),
        "poor_count": len([item for item in evaluations if item["quality_level"] == "poor"]),
        "avg_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "doc_type_summary": doc_type_summary,
        "low_quality_docs": low_quality_docs,
        "enhanced_docs_count": len(enhanced_docs),
        "enhanced_docs_path": str(ENHANCED_MEMORY_PATH.relative_to(BASE_DIR)),
    }
    report["diagnosis"] = _build_report_diagnosis(report)
    _save_json_with_backup(QUALITY_REPORT_PATH, report)
    return report


def _build_report_diagnosis(report):
    diagnosis = []
    total = int(report.get("total_personalized_docs", 0) or 0)
    if not total:
        return ["暂无个性化 RAG 文档，建议先积累刷题记录、复习记录和题目笔记。"]

    avg_score = float(report.get("avg_score", 0) or 0)
    if avg_score >= 85:
        diagnosis.append("个性化 RAG 文档整体质量较好，可以继续观察它们在计划生成中的引用情况。")
    elif avg_score >= 70:
        diagnosis.append("个性化 RAG 文档整体可用，但仍有部分文档缺少卡点、专题或复习状态。")
    else:
        diagnosis.append("个性化 RAG 文档整体质量偏低，建议优先使用增强摘要进行下一轮 RAG 实验。")

    summary = report.get("doc_type_summary", {})
    if isinstance(summary, dict):
        weak_types = [
            doc_type for doc_type, item in summary.items()
            if isinstance(item, dict) and item.get("avg_score", 100) < 70
        ]
        if weak_types:
            diagnosis.append(
                "低分文档类型：" + "、".join(weak_types) + "，建议补充用户状态、错因和复习价值。"
            )

    if report.get("enhanced_docs_count", 0):
        diagnosis.append(
            f"已生成 {report.get('enhanced_docs_count')} 条规则增强记忆，可用于后续 RAG 实验。"
        )
    return diagnosis


def format_rag_memory_quality_report(report):
    if not isinstance(report, dict):
        return "暂无 RAG 个性化记忆质量报告。"

    lines = [
        "===== RAG 个性化记忆质量报告 =====",
        "",
        f"生成时间：{report.get('timestamp', '')}",
        f"个性化文档总数：{report.get('total_personalized_docs', 0)}",
        f"平均质量评分：{report.get('avg_score', 0)}",
        f"good：{report.get('good_count', 0)}",
        f"warning：{report.get('warning_count', 0)}",
        f"poor：{report.get('poor_count', 0)}",
        "",
        "按类型：",
    ]
    summary = report.get("doc_type_summary", {})
    if isinstance(summary, dict) and summary:
        for doc_type, item in sorted(summary.items()):
            lines.append(
                f"- {doc_type}：{item.get('count', 0)} 条，平均 {item.get('avg_score', 0)}"
            )
    else:
        lines.append("- 暂无")

    lines.extend(["", "低质量文档示例："])
    low_quality = report.get("low_quality_docs", [])
    if isinstance(low_quality, list) and low_quality:
        for index, item in enumerate(low_quality[:8], start=1):
            lines.extend([
                f"{index}. {item.get('doc_id', '') or '未知文档'}",
                f"   类型：{item.get('doc_type', '')}",
                f"   题号：{item.get('problem_id', '') or '无'}",
                f"   评分：{item.get('score', 0)}",
                f"   问题：{'；'.join(item.get('issues', []) or []) or '无'}",
                "   建议重写：",
                f"   {item.get('rewritten_text', '')}",
                "",
            ])
    else:
        lines.append("- 暂无")

    lines.extend([
        f"增强记忆文件：{report.get('enhanced_docs_path', 'data/rag_personalized_memory_enhanced.json')}",
        f"增强记忆数量：{report.get('enhanced_docs_count', 0)}",
        "",
        "诊断：",
    ])
    for item in report.get("diagnosis", []) or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    audit_report = run_rag_memory_quality_audit()
    print(format_rag_memory_quality_report(audit_report))
