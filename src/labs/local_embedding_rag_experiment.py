import json
import time
from datetime import datetime
from pathlib import Path

from llm.embedding_client import get_embeddings_batch
from labs.local_model_client import get_local_embedding
from rag.rag_engine import (
    build_rag_documents,
    clean_problem_id,
    cosine_similarity,
    embedding_text,
    score_document,
    tokenize,
)


from app_paths import BASE_DIR
RESULTS_PATH = BASE_DIR / "data" / "local_embedding_rag_experiment_results.json"

DEFAULT_QUERY = "双指针什么时候移动左指针"
DEFAULT_TOP_K = 5
DEFAULT_CANDIDATE_LIMIT = 12


def _load_json_list(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        backup = path.with_suffix(path.suffix + ".bak")
        try:
            path.replace(backup)
        except OSError:
            pass
        return []
    return data if isinstance(data, list) else []


def save_local_embedding_rag_result(result):
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results = _load_json_list(RESULTS_PATH)
    results.append(result)
    RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_local_embedding_rag_results():
    return _load_json_list(RESULTS_PATH)


def _select_candidate_documents(query, limit=DEFAULT_CANDIDATE_LIMIT):
    documents = build_rag_documents(use_enhanced_memory=True)
    query_tokens = tokenize(query)
    scored = []
    for document in documents:
        score = score_document(document, query_tokens, problem_id="")
        if score > 0:
            scored.append((score, document))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        scored = [(0, document) for document in documents[:limit]]
    return [document for _, document in scored[:limit]]


def _make_result_item(document, similarity):
    return {
        "doc_id": document.get("id", ""),
        "source": document.get("source", ""),
        "doc_type": document.get("doc_type", ""),
        "problem_id": clean_problem_id(document.get("problem_id", "")),
        "title": document.get("title", ""),
        "similarity": round(float(similarity), 4),
        "content_preview": str(document.get("content", ""))[:160],
    }


def _rank_with_vectors(query_vector, documents, doc_vectors, top_k):
    ranked = []
    for document, vector in zip(documents, doc_vectors):
        similarity = cosine_similarity(query_vector, vector)
        ranked.append(_make_result_item(document, similarity))
    ranked.sort(key=lambda item: item.get("similarity", 0), reverse=True)
    return ranked[:top_k]


def _cloud_embedding_search(query, documents, top_k):
    started = time.time()
    embedding_latency = 0.0
    try:
        texts = [query] + [embedding_text(document) for document in documents]
        batch_result = get_embeddings_batch(texts, batch_size=10, timeout=20)
        embedding_latency = batch_result.get("latency_seconds", 0.0)
        if not batch_result.get("success"):
            raise RuntimeError(batch_result.get("error_message") or "Cloud embedding failed.")
        vectors = batch_result.get("embeddings", [])
        if len(vectors) != len(texts):
            raise RuntimeError("Cloud embedding count does not match query and candidate count.")
        top_results = _rank_with_vectors(vectors[0], documents, vectors[1:], top_k)
        return {
            "success": True,
            "embedding_model": batch_result.get("model", ""),
            "provider": "cloud",
            "latency_seconds": round(time.time() - started, 3),
            "embedding_latency_seconds": embedding_latency,
            "retrieval_latency_seconds": round(time.time() - started - embedding_latency, 3),
            "top_results": top_results,
            "avg_similarity": _average_similarity(top_results),
            "error_message": "",
        }
    except Exception as exc:
        return {
            "success": False,
            "embedding_model": "",
            "provider": "cloud",
            "latency_seconds": round(time.time() - started, 3),
            "embedding_latency_seconds": embedding_latency,
            "retrieval_latency_seconds": 0.0,
            "top_results": [],
            "avg_similarity": 0.0,
            "error_message": str(exc),
        }


def _local_embedding_search(query, documents, top_k):
    started = time.time()
    embedding_started = time.time()
    try:
        query_result = get_local_embedding(query)
        if not query_result.get("success"):
            raise RuntimeError(query_result.get("error_message") or "本地查询向量生成失败。")
        doc_vectors = []
        model = query_result.get("model", "")
        provider = query_result.get("provider", "local")
        for document in documents:
            result = get_local_embedding(embedding_text(document))
            if not result.get("success"):
                raise RuntimeError(result.get("error_message") or "本地文档向量生成失败。")
            doc_vectors.append(result.get("embedding", []))
            model = result.get("model", model)
            provider = result.get("provider", provider)
        embedding_latency = round(time.time() - embedding_started, 3)
        top_results = _rank_with_vectors(
            query_result.get("embedding", []),
            documents,
            doc_vectors,
            top_k,
        )
        return {
            "success": True,
            "embedding_model": model,
            "provider": provider,
            "latency_seconds": round(time.time() - started, 3),
            "embedding_latency_seconds": embedding_latency,
            "retrieval_latency_seconds": round(time.time() - started - embedding_latency, 3),
            "top_results": top_results,
            "avg_similarity": _average_similarity(top_results),
            "error_message": "",
        }
    except Exception as exc:
        return {
            "success": False,
            "embedding_model": "",
            "provider": "local",
            "latency_seconds": round(time.time() - started, 3),
            "embedding_latency_seconds": round(time.time() - embedding_started, 3),
            "retrieval_latency_seconds": 0.0,
            "top_results": [],
            "avg_similarity": 0.0,
            "error_message": str(exc),
        }


def _average_similarity(top_results):
    values = [
        float(item.get("similarity", 0) or 0)
        for item in top_results or []
    ]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _doc_ids(result, limit):
    return [
        str(item.get("doc_id", ""))
        for item in (result.get("top_results") or [])[:limit]
        if item.get("doc_id")
    ]


def _overlap(left, right, limit):
    left_ids = set(_doc_ids(left, limit))
    right_ids = set(_doc_ids(right, limit))
    if not left_ids or not right_ids:
        return 0.0
    return round(len(left_ids & right_ids) / min(len(left_ids), len(right_ids)), 4)


def _compare_results(cloud, local):
    cloud_top1 = _doc_ids(cloud, 1)
    local_top1 = _doc_ids(local, 1)
    top1_same = bool(cloud_top1 and local_top1 and cloud_top1[0] == local_top1[0])
    top3_overlap = _overlap(cloud, local, 3)
    top5_overlap = _overlap(cloud, local, 5)
    if not cloud.get("success") or not local.get("success"):
        similarity = "unavailable"
    elif top1_same and top3_overlap >= 0.67:
        similarity = "good"
    elif top3_overlap >= 0.34 or top5_overlap >= 0.4:
        similarity = "partial"
    else:
        similarity = "weak"
    return {
        "top1_same": top1_same,
        "top3_overlap": top3_overlap,
        "top5_overlap": top5_overlap,
        "ranking_similarity": similarity,
    }


def run_local_embedding_rag_experiment(
    query=DEFAULT_QUERY,
    top_k=DEFAULT_TOP_K,
    candidate_limit=DEFAULT_CANDIDATE_LIMIT,
):
    documents = _select_candidate_documents(query, limit=candidate_limit)
    cloud = _cloud_embedding_search(query, documents, top_k=top_k)
    local = _local_embedding_search(query, documents, top_k=top_k)
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": query,
        "candidate_count": len(documents),
        "top_k": top_k,
        "cloud": cloud,
        "local": local,
        "comparison": _compare_results(cloud, local),
    }
    save_local_embedding_rag_result(result)
    return result


def _format_top_results(results):
    if not results:
        return "- 暂无结果"
    lines = []
    for index, item in enumerate(results, start=1):
        problem = f"{item.get('problem_id', '')} {item.get('title', '')}".strip()
        if not problem:
            problem = item.get("doc_id", "")
        lines.append(
            f"{index}. {problem} | {item.get('source', '')} | 相似度 {item.get('similarity', 0)}"
        )
    return "\n".join(lines)


def format_local_embedding_rag_experiment(result):
    cloud = result.get("cloud", {})
    local = result.get("local", {})
    comparison = result.get("comparison", {})
    lines = [
        "===== 本地 Embedding RAG 对比实验 =====",
        "",
        f"查询：{result.get('query', '')}",
        f"候选文档：{result.get('candidate_count', 0)} 条",
        f"Top-K：{result.get('top_k', 0)}",
        "",
        "云端 Embedding：",
        f"- 状态：{'成功' if cloud.get('success') else '失败'}",
        f"- 模型：{cloud.get('embedding_model', '') or '无'}",
        f"- 总耗时：{cloud.get('latency_seconds', 0)} 秒",
        f"- 平均相似度：{cloud.get('avg_similarity', 0)}",
    ]
    if cloud.get("success"):
        lines.extend(["", _format_top_results(cloud.get("top_results", []))])
    else:
        lines.append(f"- 错误：{cloud.get('error_message', '')}")

    lines.extend([
        "",
        "本地 Embedding：",
        f"- 状态：{'成功' if local.get('success') else '失败'}",
        f"- 模型：{local.get('embedding_model', '') or '无'}",
        f"- 总耗时：{local.get('latency_seconds', 0)} 秒",
        f"- 平均相似度：{local.get('avg_similarity', 0)}",
    ])
    if local.get("success"):
        lines.extend(["", _format_top_results(local.get("top_results", []))])
    else:
        lines.append(f"- 错误：{local.get('error_message', '')}")

    lines.extend([
        "",
        "对比：",
        f"- Top1 一致：{'是' if comparison.get('top1_same') else '否'}",
        f"- Top3 overlap：{comparison.get('top3_overlap', 0)}",
        f"- Top5 overlap：{comparison.get('top5_overlap', 0)}",
        f"- 排序相似度：{comparison.get('ranking_similarity', '')}",
        "",
        "说明：本实验只比较检索效果，不会修改正式 Embedding 策略。",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_local_embedding_rag_experiment(run_local_embedding_rag_experiment()))
