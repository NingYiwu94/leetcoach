import json
import math
import time
from datetime import datetime
from pathlib import Path

from llm.embedding_client import get_embeddings_batch
from labs.local_model_client import (
    check_local_service,
    format_local_service_status,
    get_local_embedding,
    load_local_model_config,
    warmup_local_embedding,
)


from app_paths import BASE_DIR
LOG_PATH = BASE_DIR / "data" / "local_model_test_logs.json"

TEST_TEXT = "双指针题目中，我经常搞不清什么时候移动左指针。"
COMPARE_QUERY = "双指针什么时候移动左指针"
COMPARE_DOCS = [
    {
        "doc_id": "candidate_1",
        "text": "用户在 977 有序数组的平方中卡在左右平方相等时不知道移动哪个指针。",
    },
    {
        "doc_id": "candidate_2",
        "text": "用户在 242 有效的字母异位词中练习了哈希表计数。",
    },
    {
        "doc_id": "candidate_3",
        "text": "用户在 19 删除链表倒数第 N 个节点中不熟悉快慢指针间隔。",
    },
]


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


def log_local_model_test(record):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logs = _load_json_list(LOG_PATH)
    safe_record = {
        "timestamp": record.get("timestamp")
        or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_type": record.get("test_type", ""),
        "provider": record.get("provider", ""),
        "model": record.get("model", ""),
        "success": bool(record.get("success")),
        "latency_seconds": record.get("latency_seconds", 0),
        "embedding_dim": record.get("embedding_dim"),
        "error_message": record.get("error_message", ""),
    }
    logs.append(safe_record)
    LOG_PATH.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")


def test_local_service():
    result = check_local_service()
    log_local_model_test({
        "test_type": "local_service_check",
        "provider": result.get("provider", ""),
        "model": "",
        "success": result.get("success", False),
        "latency_seconds": result.get("latency_seconds", 0),
        "error_message": result.get("error_message", ""),
    })
    return result


def test_local_embedding():
    result = get_local_embedding(TEST_TEXT)
    result["test_text"] = TEST_TEXT
    result["embedding_dim"] = len(result.get("embedding", []))
    log_local_model_test({
        "test_type": "local_embedding_test",
        "provider": result.get("provider", ""),
        "model": result.get("model", ""),
        "success": result.get("success", False),
        "latency_seconds": result.get("latency_seconds", 0),
        "embedding_dim": result.get("embedding_dim"),
        "error_message": result.get("error_message", ""),
    })
    return result


def test_local_embedding_warmup():
    result = warmup_local_embedding()
    log_local_model_test({
        "test_type": "local_embedding_warmup",
        "provider": result.get("provider", ""),
        "model": result.get("model", ""),
        "success": result.get("success", False),
        "latency_seconds": result.get("latency_seconds", 0),
        "embedding_dim": result.get("embedding_dim"),
        "error_message": result.get("error_message", ""),
    })
    return result


def cosine_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _rank_documents(query_vector, doc_vectors):
    ranked = []
    for doc, vector in zip(COMPARE_DOCS, doc_vectors):
        ranked.append({
            "doc_id": doc["doc_id"],
            "text": doc["text"],
            "score": round(cosine_similarity(query_vector, vector), 4),
        })
    return sorted(ranked, key=lambda item: item.get("score", 0), reverse=True)


def _cloud_embedding_rankings():
    started = time.time()
    try:
        batch_result = get_embeddings_batch(
            [COMPARE_QUERY] + [doc["text"] for doc in COMPARE_DOCS],
            batch_size=10,
            timeout=15,
        )
        if not batch_result.get("success"):
            raise RuntimeError(batch_result.get("error_message") or "Cloud embedding failed.")
        vectors = batch_result.get("embeddings", [])
        return {
            "success": True,
            "model": batch_result.get("model", ""),
            "provider": "cloud",
            "latency_seconds": round(time.time() - started, 3),
            "rankings": _rank_documents(vectors[0], vectors[1:]),
            "error_message": "",
        }
    except Exception as exc:
        return {
            "success": False,
            "model": "",
            "provider": "cloud",
            "latency_seconds": round(time.time() - started, 3),
            "rankings": [],
            "error_message": str(exc),
        }


def _local_embedding_rankings():
    started = time.time()
    try:
        query_result = get_local_embedding(COMPARE_QUERY)
        if not query_result.get("success"):
            raise RuntimeError(query_result.get("error_message") or "本地查询向量生成失败。")
        doc_vectors = []
        for doc in COMPARE_DOCS:
            doc_result = get_local_embedding(doc["text"])
            if not doc_result.get("success"):
                raise RuntimeError(doc_result.get("error_message") or "本文档地向量生成失败。")
            doc_vectors.append(doc_result.get("embedding", []))
        return {
            "success": True,
            "model": query_result.get("model", ""),
            "provider": query_result.get("provider", "local"),
            "latency_seconds": round(time.time() - started, 3),
            "rankings": _rank_documents(query_result.get("embedding", []), doc_vectors),
            "error_message": "",
        }
    except Exception as exc:
        return {
            "success": False,
            "model": "",
            "provider": "local",
            "latency_seconds": round(time.time() - started, 3),
            "rankings": [],
            "error_message": str(exc),
        }


def compare_cloud_vs_local_embedding():
    local = _local_embedding_rankings()
    cloud = _cloud_embedding_rankings()
    log_local_model_test({
        "test_type": "cloud_vs_local_embedding_local_side",
        "provider": local.get("provider", "local"),
        "model": local.get("model", ""),
        "success": local.get("success", False),
        "latency_seconds": local.get("latency_seconds", 0),
        "embedding_dim": None,
        "error_message": local.get("error_message", ""),
    })
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": COMPARE_QUERY,
        "documents": COMPARE_DOCS,
        "local": local,
        "cloud": cloud,
        "conclusion": _build_comparison_conclusion(local, cloud),
    }
    return result


def _build_comparison_conclusion(local, cloud):
    if not local.get("success") and not cloud.get("success"):
        return "本地和云端 Embedding 都暂时不可用。请先检查本地模型服务或云端 API 配置。"
    if not local.get("success"):
        return "本地 Embedding 暂不可用，当前只能观察云端排序。可安装并启动 Ollama 后重试。"
    if not cloud.get("success"):
        return "云端 Embedding 暂不可用，当前只能观察本地排序。"
    local_top = (local.get("rankings") or [{}])[0].get("doc_id")
    cloud_top = (cloud.get("rankings") or [{}])[0].get("doc_id")
    if local_top == cloud_top:
        return "本地和云端排序的第一名一致，可以继续扩大样本观察稳定性。"
    return "本地和云端排序存在差异，建议用更多查询继续比较后再决定是否切换。"


def format_local_embedding_test(result):
    lines = [
        "===== 本地 Embedding 测试 =====",
        "",
        f"状态：{'成功' if result.get('success') else '失败'}",
        f"Provider：{result.get('provider', '')}",
        f"模型：{result.get('model', '')}",
        f"测试文本：{result.get('test_text', TEST_TEXT)}",
        f"向量维度：{result.get('embedding_dim', 0)}",
        f"耗时：{result.get('latency_seconds', 0)} 秒",
    ]
    if not result.get("success"):
        lines.extend([
            "",
            f"错误：{result.get('error_message', '')}",
            "",
            f"提示：{_local_embedding_failure_hint(result)}",
        ])
    return "\n".join(lines)


def format_local_embedding_warmup(result):
    lines = [
        "===== 本地 Embedding Warmup =====",
        "",
        f"状态：{'成功' if result.get('success') else '失败'}",
        f"Provider：{result.get('provider', '')}",
        f"模型：{result.get('model', '')}",
        f"耗时：{result.get('latency_seconds', 0)} 秒",
        f"向量维度：{result.get('embedding_dim', 0)}",
        "",
        f"说明：{result.get('message', '')}",
    ]
    if not result.get("success"):
        lines.extend([
            "",
            f"错误：{result.get('error_message', '')}",
            "",
            f"提示：{_local_embedding_failure_hint(result)}",
        ])
    return "\n".join(lines)


def _local_embedding_failure_hint(result):
    config = load_local_model_config()
    embedding_config = config.get("local_embedding", {})
    if not embedding_config.get("enabled"):
        return "本地 Embedding 未启用。请在 config/local_model_config.json 中设置 local_embedding.enabled=true。"
    error_message = str(result.get("error_message", ""))
    if "超时" in error_message or "timed out" in error_message.lower():
        return "Ollama embedding 请求超时，可能是首次模型加载较慢。请先点击 warmup，或稍后重试。"
    if "refused" in error_message.lower() or "10061" in error_message:
        return "Ollama 服务不可用。请确认 Ollama 正在运行。"
    return "请确认 Ollama 正在运行、nomic-embed-text 已安装，并且模型名称与配置一致。"


def _format_rankings(rankings):
    if not rankings:
        return "- 暂无可用排序"
    lines = []
    for index, item in enumerate(rankings, start=1):
        lines.append(f"{index}. {item.get('doc_id')}，相似度 {item.get('score')}")
        lines.append(f"   {item.get('text')}")
    return "\n".join(lines)


def format_cloud_vs_local_embedding_comparison(result):
    local = result.get("local", {})
    cloud = result.get("cloud", {})
    lines = [
        "===== 云端 vs 本地 Embedding 对比 =====",
        "",
        f"查询：{result.get('query', '')}",
        "",
        "本地 Embedding：",
        f"- 状态：{'成功' if local.get('success') else '失败'}",
        f"- 模型：{local.get('model', '') or '无'}",
        f"- 耗时：{local.get('latency_seconds', 0)} 秒",
    ]
    if local.get("success"):
        lines.extend(["", _format_rankings(local.get("rankings", []))])
    else:
        lines.append(f"- 错误：{local.get('error_message', '')}")

    lines.extend([
        "",
        "云端 Embedding：",
        f"- 状态：{'成功' if cloud.get('success') else '失败'}",
        f"- 模型：{cloud.get('model', '') or '无'}",
        f"- 耗时：{cloud.get('latency_seconds', 0)} 秒",
    ])
    if cloud.get("success"):
        lines.extend(["", _format_rankings(cloud.get("rankings", []))])
    else:
        lines.append(f"- 错误：{cloud.get('error_message', '')}")

    lines.extend(["", "结论：", result.get("conclusion", "")])
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_local_service_status(test_local_service()))
    print()
    print(format_local_embedding_warmup(test_local_embedding_warmup()))
    print()
    print(format_local_embedding_test(test_local_embedding()))
    print()
    print(format_cloud_vs_local_embedding_comparison(compare_cloud_vs_local_embedding()))
