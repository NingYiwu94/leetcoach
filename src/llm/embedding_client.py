import json
import os
import time
from datetime import datetime
from http.client import RemoteDisconnected
from pathlib import Path
from urllib import error, request

from llm.llm_client import ENV_PATH, PARENT_ENV_PATH, load_env_file
from labs.local_model_client import get_local_embedding, load_local_model_config


from app_paths import BASE_DIR
EMBEDDING_LOG_PATH = BASE_DIR / "data" / "local_model_test_logs.json"


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


def _log_embedding_call(record):
    EMBEDDING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logs = _load_json_list(EMBEDDING_LOG_PATH)
    logs.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task": "embedding",
        "primary_provider": record.get("primary_provider", ""),
        "final_provider": record.get("final_provider", ""),
        "fallback_used": bool(record.get("fallback_used")),
        "fallback_direction": record.get("fallback_direction", ""),
        "success": bool(record.get("success")),
        "latency_seconds": record.get("latency_seconds", 0.0),
        "error_message": record.get("error_message", ""),
    })
    EMBEDDING_LOG_PATH.write_text(
        json.dumps(logs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class EmbeddingClient:
    def __init__(self, timeout=45, prefer_local=False):
        load_env_file(ENV_PATH)
        load_env_file(PARENT_ENV_PATH)
        self.api_key = os.getenv("EMBEDDING_API_KEY", "").strip() or os.getenv(
            "LLM_API_KEY",
            "",
        ).strip()
        self.base_url = (
            os.getenv("EMBEDDING_BASE_URL", "").strip()
            or os.getenv("LLM_BASE_URL", "").strip()
        ).rstrip("/")
        self.cloud_model = (
            os.getenv("EMBEDDING_MODEL", "").strip()
            or os.getenv("LLM_EMBEDDING_MODEL", "").strip()
            or "text-embedding-v4"
        )
        self.model = self.cloud_model
        self.timeout = timeout
        self.prefer_local = prefer_local
        try:
            self.max_retries = max(1, int(os.getenv("EMBEDDING_MAX_RETRIES", "1")))
        except ValueError:
            self.max_retries = 1

    def _embedding_url(self):
        if self.base_url.endswith("/embeddings"):
            return self.base_url
        return f"{self.base_url}/embeddings"

    def _ensure_cloud_config(self):
        if not self.api_key:
            raise ValueError("没有读取到 EMBEDDING_API_KEY 或 LLM_API_KEY。")
        if not self.base_url:
            raise ValueError("没有读取到 EMBEDDING_BASE_URL 或 LLM_BASE_URL。")
        if not self.cloud_model:
            raise ValueError("没有读取到 EMBEDDING_MODEL。")

    def _embed_cloud(self, texts):
        self._ensure_cloud_config()
        single_input = isinstance(texts, str)
        inputs = [texts] if single_input else list(texts or [])
        if not inputs:
            return [] if not single_input else []

        try:
            batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
        except ValueError:
            batch_size = 10
        batch_size = max(1, min(batch_size, 10))
        if len(inputs) > batch_size:
            vectors = []
            for index in range(0, len(inputs), batch_size):
                batch = inputs[index:index + batch_size]
                batch_vectors = self._embed_cloud(batch)
                if len(batch_vectors) != len(batch):
                    raise RuntimeError("Embedding batch result count does not match input count.")
                vectors.extend(batch_vectors)
            if len(vectors) != len(inputs):
                raise RuntimeError("Embedding merged batch count does not match input count.")
            self.model = self.cloud_model
            return vectors[0] if single_input else vectors

        payload = json.dumps(
            {
                "model": self.cloud_model,
                "input": inputs,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        http_request = request.Request(
            self._embedding_url(),
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "LeetCoach/1.0",
            },
        )

        raw_text = ""
        for attempt in range(self.max_retries):
            try:
                with request.urlopen(http_request, timeout=self.timeout) as response:
                    raw_text = response.read().decode("utf-8")
                break
            except error.HTTPError as exc:
                detail = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                    data = json.loads(body)
                    if isinstance(data, dict):
                        detail = data.get("error", {}).get("message", "")
                except Exception:
                    detail = ""
                message = f"Embedding 接口返回 HTTP {exc.code}"
                if detail:
                    message += f"：{detail}"
                raise RuntimeError(message) from exc
            except (error.URLError, TimeoutError, RemoteDisconnected) as exc:
                if attempt < self.max_retries - 1:
                    time.sleep(1 + attempt)
                    continue
                raise RuntimeError(f"Embedding 请求失败：{exc}") from exc

        try:
            data = json.loads(raw_text)
            items = data.get("data", [])
            items = sorted(items, key=lambda item: item.get("index", 0))
            vectors = [item.get("embedding", []) for item in items]
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            raise RuntimeError("Embedding 返回结构无法解析。") from exc

        if len(vectors) != len(inputs):
            raise RuntimeError("Embedding 返回数量和输入数量不一致。")
        for vector in vectors:
            if not isinstance(vector, list) or not vector:
                raise RuntimeError("Embedding 返回了空向量。")

        self.model = self.cloud_model
        return vectors[0] if single_input else vectors

    def _embed_local(self, texts):
        single_input = isinstance(texts, str)
        inputs = [texts] if single_input else list(texts or [])
        if not inputs:
            return [] if not single_input else [], {
                "provider": "local",
                "model": "",
                "latency_seconds": 0.0,
            }

        vectors = []
        model = ""
        provider = ""
        total_latency = 0.0
        for text in inputs:
            result = get_local_embedding(text)
            if not result.get("success"):
                raise RuntimeError(result.get("error_message") or "本地 Embedding 失败。")
            vectors.append(result.get("embedding", []))
            model = result.get("model", model)
            provider = result.get("provider", provider)
            total_latency += float(result.get("latency_seconds", 0) or 0)

        if not all(isinstance(vector, list) and vector for vector in vectors):
            raise RuntimeError("本地 Embedding 返回了空向量。")

        self.model = f"local:{model}" if model else "local"
        metadata = {
            "provider": provider or "local",
            "model": model,
            "latency_seconds": round(total_latency, 3),
        }
        return (vectors[0] if single_input else vectors), metadata

    def embed_with_metadata(self, texts):
        started_total = time.time()
        config = load_local_model_config()
        local_config = config.get("local_embedding", {})
        fallback_config = config.get("fallback", {})
        local_enabled = bool(local_config.get("enabled"))

        def success_result(embedding, provider, model, fallback_used=False, fallback_direction=""):
            latency = round(time.time() - started_total, 3)
            result = {
                "embedding": embedding,
                "provider": provider,
                "model": model,
                "fallback_used": fallback_used,
                "fallback_direction": fallback_direction,
                "fallback_reason": "",
                "latency_seconds": latency,
                "error_message": "",
            }
            _log_embedding_call({
                "primary_provider": "local" if self.prefer_local and local_enabled else "cloud",
                "final_provider": provider,
                "fallback_used": fallback_used,
                "fallback_direction": fallback_direction,
                "success": True,
                "latency_seconds": latency,
                "error_message": "",
            })
            return result

        def failure_result(primary_provider, error_message):
            latency = round(time.time() - started_total, 3)
            _log_embedding_call({
                "primary_provider": primary_provider,
                "final_provider": "",
                "fallback_used": False,
                "fallback_direction": "",
                "success": False,
                "latency_seconds": latency,
                "error_message": error_message,
            })
            return {
                "embedding": [],
                "provider": "",
                "model": "",
                "fallback_used": False,
                "fallback_direction": "",
                "fallback_reason": "",
                "latency_seconds": latency,
                "error_message": error_message,
            }

        if self.prefer_local and local_enabled:
            try:
                embedding, local_meta = self._embed_local(texts)
                return success_result(
                    embedding,
                    "local",
                    local_meta.get("model", ""),
                )
            except Exception as exc:
                local_error = str(exc)
                if not fallback_config.get("embedding_fallback_to_cloud", True):
                    return failure_result("local", local_error)
                try:
                    embedding = self._embed_cloud(texts)
                    result = success_result(
                        embedding,
                        "cloud",
                        self.cloud_model,
                        fallback_used=True,
                        fallback_direction="local_to_cloud",
                    )
                    result["fallback_reason"] = local_error
                    return result
                except Exception as cloud_exc:
                    return failure_result(
                        "local",
                        f"Local embedding failed: {local_error}; cloud fallback failed: {cloud_exc}",
                    )

        try:
            embedding = self._embed_cloud(texts)
            return success_result(embedding, "cloud", self.cloud_model)
        except Exception as exc:
            cloud_error = str(exc)
            if not (
                local_enabled
                and fallback_config.get("cloud_embedding_fallback_to_local", False)
            ):
                return failure_result("cloud", cloud_error)
            try:
                embedding, local_meta = self._embed_local(texts)
                result = success_result(
                    embedding,
                    "local",
                    local_meta.get("model", ""),
                    fallback_used=True,
                    fallback_direction="cloud_to_local",
                )
                result["fallback_reason"] = cloud_error
                return result
            except Exception as local_exc:
                return failure_result(
                    "cloud",
                    f"Cloud embedding failed: {cloud_error}; local fallback failed: {local_exc}",
                )

    def get_embedding_with_metadata(self, text):
        return self.embed_with_metadata(text)

    def embed(self, texts):
        return self.embed_with_metadata(texts).get("embedding", [])


def get_embeddings_batch(texts, batch_size=10, timeout=45):
    started = time.time()
    inputs = list(texts or [])
    if not inputs:
        return {
            "success": True,
            "embeddings": [],
            "model": "",
            "provider": "cloud",
            "latency_seconds": 0.0,
            "error_message": "",
        }

    client = EmbeddingClient(timeout=timeout, prefer_local=False)
    try:
        batch_size = max(1, min(int(batch_size or 10), 10))
    except (TypeError, ValueError):
        batch_size = 10

    embeddings = []
    try:
        for index in range(0, len(inputs), batch_size):
            batch = inputs[index:index + batch_size]
            batch_vectors = client._embed_cloud(batch)
            if len(batch_vectors) != len(batch):
                raise RuntimeError("Embedding batch result count does not match input count.")
            embeddings.extend(batch_vectors)
        return {
            "success": True,
            "embeddings": embeddings,
            "model": client.model,
            "provider": "cloud",
            "latency_seconds": round(time.time() - started, 3),
            "error_message": "",
        }
    except Exception as exc:
        message = str(exc)
        if "batch size is invalid" in message.lower():
            message += "；云端 Embedding 批量大小超过接口限制，请确认已启用分批请求。"
        return {
            "success": False,
            "embeddings": [],
            "model": client.model,
            "provider": "cloud",
            "latency_seconds": round(time.time() - started, 3),
            "error_message": message,
        }


def get_embedding_with_metadata(text, timeout=45, prefer_local=False):
    client = EmbeddingClient(timeout=timeout, prefer_local=prefer_local)
    return client.embed_with_metadata(text)


def get_embedding(text, timeout=45, prefer_local=False):
    result = get_embedding_with_metadata(
        text,
        timeout=timeout,
        prefer_local=prefer_local,
    )
    embedding = result.get("embedding", [])
    return embedding if isinstance(embedding, list) and embedding else None
