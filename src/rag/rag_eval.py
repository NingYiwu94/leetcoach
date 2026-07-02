import json
import os
from datetime import datetime
from pathlib import Path

from rag.rag_engine import (
    RAG_DEBUG_PATH,
    retrieve_embedding_rag_context,
    retrieve_rag_context,
    short_text,
)


from app_paths import BASE_DIR
RAG_EVAL_RESULTS_PATH = BASE_DIR / "data" / "rag_eval_results.json"

ALGORITHM_TERMS = {
    "双指针",
    "滑动窗口",
    "哈希表",
    "链表",
    "二分",
    "栈",
    "队列",
    "递归",
    "边界",
    "指针",
    "窗口",
    "复杂度",
    "数组",
    "树",
    "动态规划",
}


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


def _append_json_list(path, item, limit=200):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = []
    except json.JSONDecodeError:
        backup = path.with_name(
            path.name + f".broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        )
        try:
            path.replace(backup)
        except OSError:
            pass
        data = []
    except OSError:
        data = []
    if not isinstance(data, list):
        data = []
    data.append(item)
    _save_json(path, data[-limit:])


def load_rag_debug():
    data = _load_json(RAG_DEBUG_PATH, {})
    return data if isinstance(data, dict) else {}


def _query_terms(query):
    text = str(query or "").lower()
    terms = set()
    for term in ALGORITHM_TERMS:
        if term.lower() in text:
            terms.add(term.lower())
    for chunk in text.replace("，", " ").replace("？", " ").split():
        if len(chunk.strip()) >= 2:
            terms.add(chunk.strip())
    return terms


def simple_relevance_check(query, text, problem_id="", title=""):
    combined = " ".join([
        str(text or ""),
        str(problem_id or ""),
        str(title or ""),
    ]).lower()
    if not combined.strip():
        return False
    for term in _query_terms(query):
        if term and term in combined:
            return True
    query_text = str(query or "").lower()
    if problem_id and str(problem_id).lower() in query_text:
        return True
    if title and str(title).lower() in query_text:
        return True
    return False


def _doc_type(document):
    return str(document.get("doc_type") or document.get("source") or "unknown")


def _doc_text(document):
    return " ".join([
        str(document.get("title", "")),
        str(document.get("content", "")),
        str(document.get("text", "")),
    ])


def _summarize_result(document, rank):
    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "rank": rank,
        "doc_id": document.get("id") or document.get("doc_id") or "",
        "doc_type": _doc_type(document),
        "problem_id": document.get("problem_id", ""),
        "title": document.get("title", ""),
        "score": document.get("score", document.get("similarity", "")),
        "text_preview": short_text(_doc_text(document), 180),
        "metadata": metadata,
    }


def evaluate_rag_retrieval(query, results):
    results = results if isinstance(results, list) else []
    top_k = len(results)
    issues = []
    score = 100
    checks = {
        "has_results": bool(results),
        "top1_relevant": False,
        "has_problem_context": False,
        "has_mistake_context": False,
        "has_ai_note_context": False,
        "duplicate_results_low": True,
    }

    if not results:
        score -= 50
        issues.append("没有检索到结果。")
    else:
        top1 = results[0]
        checks["top1_relevant"] = simple_relevance_check(
            query,
            _doc_text(top1),
            top1.get("problem_id", ""),
            top1.get("title", ""),
        )
        if not checks["top1_relevant"]:
            score -= 20
            issues.append("Top1 结果与查询关键词不够相关。")

        problem_ids = [
            str(item.get("problem_id", "")).strip()
            for item in results
            if str(item.get("problem_id", "")).strip()
        ]
        if problem_ids and len(set(problem_ids)) <= 1 and len(problem_ids) >= 3:
            score -= 10
            checks["duplicate_results_low"] = False
            issues.append("检索结果集中在同一道题，可能存在重复上下文。")

        low_text_count = 0
        low_similarity_count = 0
        for item in results:
            source = _doc_type(item)
            text = _doc_text(item)
            if source in {"problem_bank", "problem"}:
                checks["has_problem_context"] = True
            if source in {"records", "mistake", "reviews"}:
                checks["has_mistake_context"] = True
            if source == "ai_solution_notes":
                checks["has_ai_note_context"] = True
            if len(text.strip()) < 20:
                low_text_count += 1
            try:
                result_score = float(item.get("similarity", item.get("score", 0)))
                if result_score < 0.05:
                    low_similarity_count += 1
            except (TypeError, ValueError):
                pass

        if not checks["has_mistake_context"]:
            score -= 10
            issues.append("未检索到历史错因或复习记录类文档。")
        if not checks["has_problem_context"]:
            score -= 10
            issues.append("未检索到题目上下文类文档。")
        if not checks["has_ai_note_context"]:
            issues.append("未检索到 AI 题解笔记类文档。")
        if low_text_count:
            score -= 10
            issues.append("部分检索结果内容为空或过短。")
        if results and low_similarity_count >= max(2, len(results) // 2):
            score -= 10
            issues.append("Top-K 中存在较多低相似度结果。")

    score = max(0, min(100, score))
    if score >= 85:
        quality_level = "good"
    elif score >= 70:
        quality_level = "warning"
    else:
        quality_level = "poor"

    return {
        "query": str(query or ""),
        "top_k": top_k,
        "score": score,
        "quality_level": quality_level,
        "checks": checks,
        "issues": issues,
        "results_summary": [
            _summarize_result(item, index)
            for index, item in enumerate(results[:5], start=1)
        ],
    }


def save_rag_eval_result(evaluation, context=None):
    context = context if isinstance(context, dict) else {}
    documents = context.get("documents", [])
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": evaluation.get("query", ""),
        "score": evaluation.get("score", 0),
        "quality_level": evaluation.get("quality_level", ""),
        "top_k": evaluation.get("top_k", 0),
        "issues": evaluation.get("issues", []),
        "top_doc_ids": [
            item.get("id", "")
            for item in documents[:5]
            if isinstance(item, dict)
        ],
        "used_embedding": context.get("mode") == "embedding",
        "used_keyword_fallback": context.get("mode") == "keyword_fallback",
    }
    _append_json_list(RAG_EVAL_RESULTS_PATH, record)
    return record


def run_rag_retrieval_quality_test(query=None, top_k=5):
    query = query or "双指针什么时候移动左指针"
    mode = os.getenv("LEETCOACH_RAG_MODE", "keyword").strip().lower()
    if mode == "embedding":
        context = retrieve_embedding_rag_context(query, top_k=top_k, max_chars=1800)
    else:
        context = retrieve_rag_context(query, top_k=top_k, max_chars=1800)
    evaluation = evaluate_rag_retrieval(query, context.get("documents", []))
    save_rag_eval_result(evaluation, context)
    evaluation["retrieval_mode"] = context.get("mode", "")
    evaluation["total_candidate_count"] = context.get("total_candidate_count", 0)
    return evaluation


def _yes_no(value):
    return "是" if value else "否"


def format_rag_eval_report(evaluation):
    if not isinstance(evaluation, dict):
        return "暂无 RAG 检索质量评估结果。"
    checks = evaluation.get("checks", {})
    if not isinstance(checks, dict):
        checks = {}
    lines = [
        "===== RAG 检索质量测试 =====",
        "",
        "查询：",
        str(evaluation.get("query", "")),
        "",
        f"检索评分：{evaluation.get('score', 0)}",
        f"质量等级：{evaluation.get('quality_level', 'unknown')}",
        f"检索模式：{evaluation.get('retrieval_mode', 'unknown')}",
        "",
        "检查项：",
        f"- 有检索结果：{_yes_no(checks.get('has_results'))}",
        f"- Top1 相关：{_yes_no(checks.get('top1_relevant'))}",
        f"- 包含题目上下文：{_yes_no(checks.get('has_problem_context'))}",
        f"- 包含历史错因/复习记录：{_yes_no(checks.get('has_mistake_context'))}",
        f"- 包含 AI 题解笔记：{_yes_no(checks.get('has_ai_note_context'))}",
        f"- 重复结果较低：{_yes_no(checks.get('duplicate_results_low'))}",
        "",
        "主要问题：",
    ]
    issues = evaluation.get("issues", [])
    if issues:
        lines.extend(f"- {issue}" for issue in issues[:8])
    else:
        lines.append("- 无")
    lines.extend(["", "Top 5 结果："])
    results = evaluation.get("results_summary", [])
    if not results:
        lines.append("- 无")
    for item in results:
        lines.extend([
            f"{item.get('rank')}. {item.get('problem_id', '')} {item.get('title', '')}".strip(),
            f"   类型：{item.get('doc_type', '')}",
            f"   相似度/分数：{item.get('score', '')}",
            f"   内容：{item.get('text_preview', '')}",
            "",
        ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    report = run_rag_retrieval_quality_test()
    print(format_rag_eval_report(report))
