import json
import time
from datetime import datetime
from pathlib import Path
from urllib import error, request


from app_paths import BASE_DIR
CONFIG_PATH = BASE_DIR / "config" / "local_model_config.json"

DEFAULT_CONFIG = {
    "local_embedding": {
        "enabled": False,
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model": "nomic-embed-text",
        "api_type": "ollama",
        "timeout_seconds": 120,
    },
    "local_llm": {
        "enabled": False,
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model": "qwen2.5:7b",
        "api_type": "ollama",
    },
    "fallback": {
        "embedding_fallback_to_cloud": True,
        "llm_fallback_to_cloud": True,
    },
}


def _deep_merge(default, data):
    if not isinstance(data, dict):
        return default
    merged = dict(default)
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_local_model_config():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return dict(DEFAULT_CONFIG)

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)
    return _deep_merge(DEFAULT_CONFIG, data)


def _normalize_base_url(base_url):
    return str(base_url or "").strip().rstrip("/")


def _json_request(url, method="GET", payload=None, timeout=3):
    body = None
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "LeetCoach LocalModelLab/1.0",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, method=method, headers=headers)
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw else {}


def _error_message(exc):
    if isinstance(exc, error.HTTPError):
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = ""
        if detail:
            return f"HTTP {exc.code}: {detail}"
        return f"HTTP {exc.code}"
    return str(exc)


def _configured_timeout(config, default=120):
    try:
        return max(1, int(config.get("timeout_seconds", default)))
    except (TypeError, ValueError):
        return default


def _is_timeout_error(exc):
    message = str(exc).lower()
    return isinstance(exc, TimeoutError) or "timed out" in message or "timeout" in message


def _parse_embedding_response(data):
    if not isinstance(data, dict):
        raise RuntimeError("Ollama embedding 响应不是 JSON 对象。")
    embeddings = data.get("embeddings")
    if isinstance(embeddings, list) and embeddings:
        first = embeddings[0]
        if isinstance(first, list) and first:
            return first
        if all(isinstance(value, (int, float)) for value in embeddings):
            return embeddings

    embedding = data.get("embedding")
    if isinstance(embedding, list) and embedding:
        return embedding

    raise RuntimeError("Ollama embedding 响应中未找到 embeddings 字段")


def check_local_service():
    config = load_local_model_config()
    embedding_config = config.get("local_embedding", {})
    llm_config = config.get("local_llm", {})
    service_config = embedding_config if embedding_config.get("enabled") else llm_config
    if not service_config.get("enabled"):
        service_config = embedding_config

    provider = service_config.get("provider", "ollama")
    api_type = service_config.get("api_type", provider)
    base_url = _normalize_base_url(service_config.get("base_url"))
    started = time.time()
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "success": False,
        "provider": provider,
        "api_type": api_type,
        "base_url": base_url,
        "embedding_enabled": bool(embedding_config.get("enabled")),
        "llm_enabled": bool(llm_config.get("enabled")),
        "models": [],
        "latency_seconds": 0.0,
        "error_message": "",
    }

    if not base_url:
        result["error_message"] = "本地模型 base_url 为空。"
        return result

    if api_type == "ollama":
        url = f"{base_url}/api/tags"
    else:
        url = f"{base_url}/v1/models"

    try:
        data = _json_request(url, timeout=3)
        models = data.get("models", data.get("data", []))
        names = []
        if isinstance(models, list):
            for item in models:
                if isinstance(item, dict):
                    names.append(item.get("name") or item.get("id") or "")
        result["success"] = True
        result["models"] = [name for name in names if name]
    except Exception as exc:
        result["error_message"] = _error_message(exc)
    finally:
        result["latency_seconds"] = round(time.time() - started, 3)
    return result


def get_local_embedding(text):
    config = load_local_model_config()
    embedding_config = config.get("local_embedding", {})
    provider = embedding_config.get("provider", "ollama")
    api_type = embedding_config.get("api_type", provider)
    base_url = _normalize_base_url(embedding_config.get("base_url"))
    model = embedding_config.get("model", "")
    timeout_seconds = _configured_timeout(embedding_config, default=120)
    started = time.time()
    result = {
        "success": False,
        "embedding": [],
        "model": model,
        "provider": provider,
        "latency_seconds": 0.0,
        "error_message": "",
    }

    if not embedding_config.get("enabled"):
        result["error_message"] = "本地 Embedding 未启用。"
        return result
    if not base_url or not model:
        result["error_message"] = "本地 Embedding base_url 或 model 为空。"
        return result

    try:
        if api_type == "ollama":
            data = _json_request(
                f"{base_url}/api/embed",
                method="POST",
                payload={"model": model, "input": text},
                timeout=timeout_seconds,
            )
            embedding = _parse_embedding_response(data)
        else:
            url = (
                f"{base_url}/embeddings"
                if base_url.endswith("/v1")
                else f"{base_url}/v1/embeddings"
            )
            data = _json_request(
                url,
                method="POST",
                payload={"model": model, "input": text},
                    timeout=timeout_seconds,
            )
            items = data.get("data", [])
            embedding = items[0].get("embedding", []) if items else []

        if not isinstance(embedding, list) or not embedding:
            raise RuntimeError("本地 Embedding 返回空向量。")
        result["success"] = True
        result["embedding"] = embedding
    except Exception as exc:
        if _is_timeout_error(exc):
            result["error_message"] = "Ollama embedding 请求超时。模型首次加载可能较慢，请先执行 warmup 或稍后重试。"
        else:
            result["error_message"] = _error_message(exc)
    finally:
        result["latency_seconds"] = round(time.time() - started, 3)
    return result


def warmup_local_embedding():
    started = time.time()
    result = get_local_embedding("hello")
    embedding = result.get("embedding", [])
    success = bool(result.get("success"))
    latency = round(time.time() - started, 3)
    if success:
        message = "本地 Embedding warmup 成功。首次加载模型可能较慢，后续调用通常会更快。"
    else:
        message = result.get("error_message") or "本地 Embedding warmup 失败。"
    return {
        "success": success,
        "latency_seconds": latency,
        "message": message,
        "embedding_dim": len(embedding) if isinstance(embedding, list) else 0,
        "provider": result.get("provider", ""),
        "model": result.get("model", ""),
        "error_message": "" if success else result.get("error_message", ""),
    }


def call_local_llm(prompt_or_messages):
    config = load_local_model_config()
    llm_config = config.get("local_llm", {})
    provider = llm_config.get("provider", "ollama")
    api_type = llm_config.get("api_type", provider)
    base_url = _normalize_base_url(llm_config.get("base_url"))
    model = llm_config.get("model", "")
    started = time.time()
    result = {
        "success": False,
        "text": "",
        "model": model,
        "provider": provider,
        "latency_seconds": 0.0,
        "error_message": "",
    }

    if not llm_config.get("enabled"):
        result["error_message"] = "本地 LLM 未启用。"
        return result
    if not base_url or not model:
        result["error_message"] = "本地 LLM base_url 或 model 为空。"
        return result

    try:
        if isinstance(prompt_or_messages, list):
            messages = prompt_or_messages
            prompt = "\n".join(
                str(item.get("content", "")) for item in messages if isinstance(item, dict)
            )
        else:
            prompt = str(prompt_or_messages)
            messages = [{"role": "user", "content": prompt}]

        if api_type == "ollama":
            if isinstance(prompt_or_messages, list):
                data = _json_request(
                    f"{base_url}/api/chat",
                    method="POST",
                    payload={"model": model, "messages": messages, "stream": False},
                    timeout=60,
                )
                text = data.get("message", {}).get("content", "")
            else:
                data = _json_request(
                    f"{base_url}/api/generate",
                    method="POST",
                    payload={"model": model, "prompt": prompt, "stream": False},
                    timeout=60,
                )
                text = data.get("response", "")
        else:
            url = (
                f"{base_url}/chat/completions"
                if base_url.endswith("/v1")
                else f"{base_url}/v1/chat/completions"
            )
            data = _json_request(
                url,
                method="POST",
                payload={"model": model, "messages": messages, "temperature": 0.2},
                timeout=60,
            )
            choices = data.get("choices", [])
            text = choices[0].get("message", {}).get("content", "") if choices else ""

        if not text:
            raise RuntimeError("本地 LLM 返回空内容。")
        result["success"] = True
        result["text"] = text
    except Exception as exc:
        result["error_message"] = _error_message(exc)
    finally:
        result["latency_seconds"] = round(time.time() - started, 3)
    return result


def format_local_service_status(result):
    config = load_local_model_config()
    embedding_config = config.get("local_embedding", {})
    fallback_config = config.get("fallback", {})
    cloud_to_local = bool(fallback_config.get("cloud_embedding_fallback_to_local"))
    local_model = embedding_config.get("model", "")
    lines = [
        "===== 本地模型服务检查 =====",
        "",
        f"状态：{'可用' if result.get('success') else '不可用'}",
        f"Provider：{result.get('provider', '')}",
        f"API 类型：{result.get('api_type', '')}",
        f"地址：{result.get('base_url', '')}",
        f"本地 Embedding：{'启用' if result.get('embedding_enabled') else '未启用'}",
        f"本地 LLM：{'启用' if result.get('llm_enabled') else '未启用'}",
        f"耗时：{result.get('latency_seconds', 0)} 秒",
    ]
    lines.extend([
        "",
        "===== Embedding 当前策略 =====",
        "",
        "默认策略：cloud_first",
        f"云端失败是否本地兜底：{'是' if cloud_to_local else '否'}",
        f"本地模型：{local_model or '未配置'}",
        "说明：当前建议保持云端默认，本地作为 fallback。",
    ])
    models = result.get("models") or []
    if models:
        lines.extend(["", "可用模型："])
        lines.extend(f"- {name}" for name in models[:10])
    if not result.get("success"):
        lines.extend([
            "",
            f"错误：{result.get('error_message', '') or '未获取到本地模型服务响应。'}",
            "",
            "提示：如果你使用 Ollama，请先运行 ollama serve，并确认模型已 pull。",
        ])
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_local_service_status(check_local_service()))
