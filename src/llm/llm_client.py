import json
import os
import time
from http.client import RemoteDisconnected
from pathlib import Path
from urllib import error, request


from app_paths import BASE_DIR
ENV_PATH = BASE_DIR / ".env"
PARENT_ENV_PATH = BASE_DIR.parent / ".env"


def load_env_file(path=ENV_PATH):
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


class LLMClient:
    def __init__(self, timeout=60, model=None, model_env_key=None):
        load_env_file(ENV_PATH)
        load_env_file(PARENT_ENV_PATH)
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
        selected_model = ""
        if model_env_key:
            selected_model = os.getenv(model_env_key, "").strip()
        self.model = (
            str(model or "").strip()
            or selected_model
            or os.getenv(
            "LLM_MODEL",
            "qwen-plus-2025-07-28"
            ).strip()
        )
        self.timeout = timeout
        try:
            self.max_retries = max(1, int(os.getenv("LLM_MAX_RETRIES", "1")))
        except ValueError:
            self.max_retries = 1

        if not self.api_key:
            raise ValueError(
                "没有读取到 LLM_API_KEY，请检查 .env 文件。"
            )
        if not self.base_url:
            raise ValueError(
                "没有读取到 LLM_BASE_URL，请检查 .env 文件。"
            )
        if not self.model:
            raise ValueError(
                "没有读取到 LLM_MODEL，请检查 .env 文件。"
            )

    def _chat_url(self):
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def chat(
        self,
        user_prompt,
        system_prompt="你是一个耐心、严谨的 AI 助手。",
        temperature=0.7,
        max_tokens=None,
        enable_thinking=None,
        thinking_budget=None
    ):
        payload_data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature
        }
        if max_tokens is not None:
            payload_data["max_tokens"] = int(max_tokens)
        if enable_thinking is not None:
            payload_data["enable_thinking"] = bool(enable_thinking)
        if thinking_budget is not None:
            payload_data["thinking_budget"] = int(thinking_budget)

        payload = json.dumps(
            payload_data,
            ensure_ascii=False
        ).encode("utf-8")

        http_request = request.Request(
            self._chat_url(),
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "LeetCoach/1.0"
            }
        )

        raw_text = ""
        last_connection_error = None
        for attempt in range(self.max_retries):
            try:
                with request.urlopen(
                    http_request,
                    timeout=self.timeout
                ) as response:
                    raw_text = response.read().decode("utf-8")
                break
            except error.HTTPError as exc:
                detail = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                    data = json.loads(body)
                    detail = (
                        data.get("error", {}).get("message", "")
                        if isinstance(data, dict)
                        else ""
                    )
                except Exception:
                    detail = ""
                message = f"模型接口返回 HTTP {exc.code}"
                if detail:
                    message += f"：{detail}"
                raise RuntimeError(message) from exc
            except error.URLError as exc:
                last_connection_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(1 + attempt)
                    continue
                raise RuntimeError(
                    f"无法连接模型接口：{exc.reason}"
                ) from exc
            except TimeoutError as exc:
                last_connection_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(1 + attempt)
                    continue
                raise RuntimeError("模型请求超时，请稍后重试。") from exc
            except RemoteDisconnected as exc:
                last_connection_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(1 + attempt)
                    continue
                raise RuntimeError(
                    "模型接口提前断开连接，请稍后重试。"
                ) from exc

        if not raw_text and last_connection_error is not None:
            raise RuntimeError(
                f"无法连接模型接口：{last_connection_error}"
            )

        try:
            data = json.loads(raw_text)
            choices = data.get("choices", [])
            content = choices[0]["message"]["content"]
        except (
            json.JSONDecodeError,
            IndexError,
            KeyError,
            TypeError
        ) as exc:
            raise RuntimeError("模型返回结构无法解析。") from exc

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("模型返回了空内容。")
        return content
