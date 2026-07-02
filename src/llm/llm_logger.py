import json
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
LOG_PATH = BASE_DIR / "data" / "llm_call_logs.json"
MAX_RAW_OUTPUT_LENGTH = 4000
MAX_PROMPT_PREVIEW_LENGTH = 2000


def _load_logs(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup_path = path.with_name(
            path.name
            + f".broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        )
        try:
            path.replace(backup_path)
        except OSError:
            pass
        return []
    except OSError:
        return []
    return data if isinstance(data, list) else []


def log_llm_call(log_record):
    record = dict(log_record or {})
    record.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    raw_output = str(record.get("raw_output", "") or "")
    if len(raw_output) > MAX_RAW_OUTPUT_LENGTH:
        raw_output = raw_output[:MAX_RAW_OUTPUT_LENGTH] + "...[truncated]"
    record["raw_output"] = raw_output

    prompt_preview = str(record.get("prompt_preview", "") or "")
    if len(prompt_preview) > MAX_PROMPT_PREVIEW_LENGTH:
        prompt_preview = (
            prompt_preview[:MAX_PROMPT_PREVIEW_LENGTH] + "...[truncated]"
        )
    record["prompt_preview"] = prompt_preview

    record.setdefault("task", "")
    record.setdefault("prompt_name", "")
    record.setdefault("prompt_version", "")
    record.setdefault("model", "")
    record.setdefault("input_summary", {})
    record.setdefault("parsed_success", False)
    record.setdefault("schema_valid", False)
    record.setdefault("eval_score", "")
    record.setdefault("fallback_used", False)
    record.setdefault("error_type", "")
    record.setdefault("error_message", "")
    record.setdefault("latency_seconds", 0)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logs = _load_logs(LOG_PATH)
    logs.append(record)
    LOG_PATH.write_text(
        json.dumps(logs, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return record


def get_recent_llm_logs(limit=5):
    logs = _load_logs(LOG_PATH)
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 5
    return logs[-limit:]


def format_recent_llm_logs(logs):
    if not logs:
        return "目前还没有 LLM 调用日志。"

    lines = ["===== 最近 LLM 调用日志 =====", ""]
    for index, item in enumerate(reversed(logs), start=1):
        lines.extend([
            f"{index}. {item.get('task', '未知任务')}",
            f"   时间：{item.get('timestamp', '未知')}",
            (
                "   Prompt："
                f"{item.get('prompt_name', '未知')}"
                f" / {item.get('prompt_version', '未知')}"
            ),
            f"   模型：{item.get('model', '未知')}",
            f"   解析成功：{item.get('parsed_success', False)}",
            f"   Schema 通过：{item.get('schema_valid', False)}",
            f"   质量评分：{item.get('eval_score', '未评估')}",
            f"   使用兜底：{item.get('fallback_used', False)}",
            f"   耗时：{item.get('latency_seconds', 0)} 秒",
        ])
        if item.get("error_message"):
            lines.append(f"   错误：{item.get('error_message')}")
        lines.append("")
    return "\n".join(lines).rstrip()
