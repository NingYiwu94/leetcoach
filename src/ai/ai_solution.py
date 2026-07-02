import json
import os
import time
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
PROBLEM_BANK_PATH = BASE_DIR / "data" / "problem_bank.json"
SOLUTION_NOTES_PATH = BASE_DIR / "data" / "ai_solution_notes.json"
REQUIRED_SOLUTION_FIELDS = {
    "idea",
    "code",
    "common_mistakes",
    "time_complexity"
}
AI_SOLUTION_TIMEOUT_SECONDS = 90
AI_SOLUTION_PROMPT_VERSION = "ai_solution_v2"


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_problem_id(problem_id):
    value = str(problem_id or "")
    for prefix in ("题号：", "题号:", "题号"):
        value = value.replace(prefix, "")
    return value.strip()


def _short_text(value, limit):
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def load_solution_notes():
    notes = load_json(SOLUTION_NOTES_PATH, [])
    return notes if isinstance(notes, list) else []


def get_solution_note(problem_id, language=None):
    problem_id = clean_problem_id(problem_id)
    language = str(language or "").strip().lower()
    notes = [
        note for note in load_solution_notes()
        if (
            isinstance(note, dict)
            and clean_problem_id(note.get("problem_id")) == problem_id
            and (
                not language
                or str(note.get("language", "")).strip().lower() == language
            )
        )
    ]
    notes.sort(key=lambda item: str(item.get("generated_at", "")), reverse=True)
    return notes[0] if notes else None


def get_solution_status(problem_id, language="Python"):
    note = get_solution_note(problem_id, language)
    if not note:
        return {
            "exists": False,
            "generated_at": "",
            "language": language,
            "summary": "尚未生成 AI 题解。"
        }
    return {
        "exists": True,
        "generated_at": note.get("generated_at", ""),
        "language": note.get("language", language),
        "summary": (
            f"已保存 {note.get('language', language)} 题解"
            f" · {note.get('generated_at', '时间未知')}"
        )
    }


def save_solution_note(solution):
    solution = normalize_solution(solution)
    problem_id = clean_problem_id(solution.get("problem_id"))
    if not problem_id:
        raise ValueError("AI 题解缺少题号，无法保存。")
    quality = evaluate_solution_quality(
        solution,
        expected_problem_id=problem_id,
        language=solution.get("language", "")
    )
    if not quality.get("valid"):
        raise ValueError(
            "AI 题解质量不足，未保存："
            + "；".join(quality.get("issues", []))
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note = {
        **solution,
        "problem_id": problem_id,
        "generated_at": solution.get("generated_at") or now,
        "source": "ai_solution",
        "quality_check": quality
    }

    notes = load_solution_notes()
    language = str(note.get("language", "")).strip().lower()
    filtered = [
        item for item in notes
        if not (
            isinstance(item, dict)
            and clean_problem_id(item.get("problem_id")) == problem_id
            and str(item.get("language", "")).strip().lower() == language
        )
    ]
    filtered.append(note)
    save_json(SOLUTION_NOTES_PATH, filtered)
    return note


def parse_solution_response(raw_text):
    if not isinstance(raw_text, str):
        raw_text = str(raw_text or "")

    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                result = json.loads(text[start:end + 1])
                return normalize_solution(result if isinstance(result, dict) else {})
            except json.JSONDecodeError:
                pass
        return {
            "problem_id": "",
            "problem_title": "AI 题解",
            "idea": raw_text,
            "language": "",
            "code": "",
            "common_mistakes": [],
            "time_complexity": "解析失败",
            "space_complexity": "解析失败",
            "parse_fallback": True
        }
    return normalize_solution(result if isinstance(result, dict) else {})


def normalize_solution(solution):
    if not isinstance(solution, dict):
        solution = {}

    complexity = solution.get("complexity", {})
    if not isinstance(complexity, dict):
        complexity = {}

    mistakes = solution.get("common_mistakes", [])
    if not isinstance(mistakes, list):
        mistakes = [mistakes] if mistakes else []

    normalized_mistakes = []
    for item in mistakes:
        if isinstance(item, dict):
            point = str(item.get("point", "")).strip()
            explanation = str(item.get("explanation", "")).strip()
        else:
            point = str(item).strip()
            explanation = ""
        if point or explanation:
            normalized_mistakes.append({
                "point": _short_text(point or "注意事项", 16),
                "explanation": _short_text(
                    explanation or "请在实现时重点检查。",
                    50
                )
            })

    return {
        **solution,
        "problem_id": str(solution.get("problem_id", "")).strip(),
        "problem_title": str(
            solution.get("problem_title", "")
        ).strip(),
        "idea": str(solution.get("idea", "")).strip(),
        "language": str(solution.get("language", "")).strip(),
        "code": str(solution.get("code", "")).strip(),
        "common_mistakes": normalized_mistakes,
        "time_complexity": str(
            solution.get("time_complexity", "")
            or complexity.get("time", "")
        ).strip(),
        "space_complexity": str(
            solution.get("space_complexity", "")
            or complexity.get("space", "")
        ).strip()
    }


def is_complete_solution(solution):
    if not isinstance(solution, dict) or solution.get("parse_fallback"):
        return False
    if any(not solution.get(field) for field in REQUIRED_SOLUTION_FIELDS):
        return False
    if len(solution.get("common_mistakes", [])) < 3:
        return False
    return has_detailed_code_comments(
        solution.get("code", ""),
        solution.get("language", "")
    )


def has_detailed_code_comments(code, language=""):
    lines = [
        line.strip()
        for line in str(code or "").splitlines()
        if line.strip()
    ]
    if not lines:
        return False

    language = str(language or "").lower()
    if "python" in language:
        comment_count = sum("#" in line for line in lines)
    else:
        comment_count = sum(
            "//" in line or "/*" in line or "*/" in line
            for line in lines
        )

    required_count = max(3, len(lines) // 4)
    return comment_count >= required_count


def evaluate_solution_quality(solution, expected_problem_id="", language=""):
    issues = []
    solution = normalize_solution(solution)
    expected_problem_id = clean_problem_id(expected_problem_id)
    code = solution.get("code", "")
    idea = solution.get("idea", "")
    mistakes = solution.get("common_mistakes", [])
    time_complexity = solution.get("time_complexity", "")
    space_complexity = solution.get("space_complexity", "")
    actual_language = str(solution.get("language") or language or "").lower()

    if solution.get("parse_fallback"):
        issues.append("模型没有返回合法 JSON")
    if expected_problem_id and clean_problem_id(solution.get("problem_id")) != expected_problem_id:
        issues.append("题号与请求题号不一致")
    if not idea or len(idea) < 20:
        issues.append("解题思路过短或为空")
    if not code:
        issues.append("缺少完整代码")
    if "python" in actual_language:
        if "class Solution" not in code:
            issues.append("Python 代码缺少 LeetCode class Solution")
        if "def " not in code:
            issues.append("Python 代码缺少方法定义")
    elif "c++" in actual_language or "cpp" in actual_language:
        if "class Solution" not in code:
            issues.append("C++ 代码缺少 LeetCode class Solution")
        if "public:" not in code:
            issues.append("C++ 代码缺少 public 方法区域")
    elif code and "class Solution" not in code:
        issues.append("代码不像 LeetCode 可提交格式")

    if code and not has_detailed_code_comments(code, actual_language):
        issues.append("代码中文注释不足")
    if not isinstance(mistakes, list) or len(mistakes) < 3:
        issues.append("易错点少于 3 条")
    if not time_complexity or "O(" not in time_complexity:
        issues.append("缺少时间复杂度大 O 表达")
    if any(word in code for word in ("伪代码", "略", "TODO")):
        issues.append("代码中出现伪代码或未完成标记")

    score = max(0, 100 - len(issues) * 12)
    return {
        "valid": not issues,
        "score": score,
        "issues": issues
    }


def generate_solution(problem_id, language="Python"):
    from llm_client import LLMClient
    from llm_logger import log_llm_call
    from rag_engine import get_problem_rag_context

    problem_id = clean_problem_id(problem_id)
    if not problem_id:
        raise ValueError("请输入力扣题号。")

    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    problem = (
        problem_bank.get(problem_id, {})
        if isinstance(problem_bank, dict)
        else {}
    )
    if not isinstance(problem, dict):
        problem = {}

    context = {
        "problem_id": problem_id,
        "title": problem.get("title", ""),
        "difficulty": problem.get("difficulty", ""),
        "topics": problem.get("topics", []),
        "key_points": problem.get("key_points", [])
    }
    try:
        rag_context = get_problem_rag_context(problem_id, top_k=3, max_chars=900)
        rag_context_text = rag_context.get("context_text", "")
    except Exception as error:
        rag_context = {"matched_count": 0, "error": str(error)}
        rag_context_text = "RAG retrieval failed. Use only basic problem metadata."
    system_prompt = (
        "你是 LeetCoach 的算法教练。"
        "面向初学者，输出简洁、准确、可保存的题解笔记。"
        "必须只返回严格 JSON，不要 Markdown，不要额外解释。"
        "只讲一种推荐方法，代码完整可提交，关键逻辑写中文注释。"
    )
    user_prompt = f"""
/no_think

题目：
{json.dumps(context, ensure_ascii=False)}
使用语言：{language}

本地学习资料摘要：
{rag_context_text or "暂无"}

只返回 JSON，字段必须完整：
{{
  "problem_id": "{problem_id}",
  "problem_title": "题目名称",
  "idea": "150 字以内，先讲核心思路，再讲关键边界",
  "language": "{language}",
  "code": "完整可提交代码，关键逻辑带中文注释",
  "common_mistakes": [
    {{
      "point": "易错点标题",
      "explanation": "一句话说明怎么避免"
    }}
  ],
  "time_complexity": "O(...)，一句话说明",
  "space_complexity": "O(...)，一句话说明"
}}

要求：
- code 必须完整可提交，不能是伪代码。
- Python 使用 LeetCode 标准 class Solution 写法；没有必要 import 时不要 import。
- C++ 使用 LeetCode 标准 class Solution 写法。
- 注释控制在 4 到 8 条，解释变量、循环条件、边界处理。
- common_mistakes 必须 3 到 4 项，短句即可。
- 不确定题目内容时，明确说明需要题目描述，不要编造。
""".strip()

    client = LLMClient(
        timeout=_env_int(
            "AI_SOLUTION_TIMEOUT_SECONDS",
            AI_SOLUTION_TIMEOUT_SECONDS
        ),
        model_env_key="LLM_MODEL_FAST"
    )
    result = None
    last_raw_text = ""
    error_message = ""
    quality_result = {
        "valid": False,
        "score": 0,
        "issues": ["尚未生成"]
    }
    start_time = time.time()
    try:
        retry_feedback = ""
        max_attempts = max(1, _env_int("AI_SOLUTION_MAX_ATTEMPTS", 2))
        min_score = _env_int("AI_SOLUTION_MIN_SCORE", 76)
        for attempt in range(max_attempts):
            attempt_prompt = user_prompt
            if retry_feedback:
                attempt_prompt += (
                    "\n\n上一次题解未通过质量检查，请修正以下问题。"
                    "只返回完整 JSON，不要解释：\n"
                    + retry_feedback
                )
            last_raw_text = client.chat(
                user_prompt=attempt_prompt,
                system_prompt=system_prompt,
                temperature=0.15,
                max_tokens=_env_int("AI_SOLUTION_MAX_TOKENS", 1400),
                enable_thinking=False
            )
            result = parse_solution_response(last_raw_text)
            if not result.get("problem_id"):
                result["problem_id"] = problem_id
            if not result.get("problem_title"):
                result["problem_title"] = problem.get("title", "")
            if not result.get("language"):
                result["language"] = language
            quality_result = evaluate_solution_quality(
                result,
                expected_problem_id=problem_id,
                language=language
            )
            if (
                quality_result.get("valid")
                and quality_result.get("score", 0) >= min_score
            ):
                break
            retry_feedback = "\n".join(
                f"- {issue}"
                for issue in quality_result.get("issues", [])[:8]
            ) or "- 题解质量不足，请补全结构、代码、易错点和复杂度。"
    except Exception as error:
        error_message = str(error)
        try:
            log_llm_call({
                "task": "ai_solution",
                "prompt_version": AI_SOLUTION_PROMPT_VERSION,
                "model": getattr(client, "model", ""),
                "input_summary": {
                    "problem_id": problem_id,
                    "language": language,
                    "rag_matched_count": rag_context.get("matched_count", 0),
                    "quality": quality_result
                },
                "raw_output": last_raw_text,
                "parsed_success": False,
                "schema_valid": False,
                "fallback_used": False,
                "error_message": error_message,
                "latency_seconds": round(time.time() - start_time, 3)
            })
        except Exception:
            pass
        raise

    if not (
        quality_result.get("valid")
        and quality_result.get("score", 0)
        >= _env_int("AI_SOLUTION_MIN_SCORE", 76)
    ):
        error_message = (
            "AI 题解未通过质量检查："
            + "；".join(quality_result.get("issues", []))
        )
        try:
            log_llm_call({
                "task": "ai_solution",
                "prompt_version": AI_SOLUTION_PROMPT_VERSION,
                "model": getattr(client, "model", ""),
                "input_summary": {
                    "problem_id": problem_id,
                    "language": language,
                    "rag_matched_count": rag_context.get("matched_count", 0),
                    "quality": quality_result
                },
                "raw_output": last_raw_text,
                "parsed_success": bool(result) and not result.get("parse_fallback"),
                "schema_valid": False,
                "fallback_used": False,
                "error_message": error_message,
                "latency_seconds": round(time.time() - start_time, 3)
            })
        except Exception:
            pass
        raise ValueError(error_message)

    result.setdefault("problem_id", problem_id)
    result.setdefault("problem_title", problem.get("title", ""))
    result.setdefault("language", language)
    result.setdefault("common_mistakes", [])
    if not result.get("problem_id"):
        result["problem_id"] = problem_id
    if not result.get("problem_title"):
        result["problem_title"] = problem.get("title", "")
    if not result.get("language"):
        result["language"] = language
    result["rag_used"] = bool(rag_context.get("matched_count"))
    result["rag_matched_count"] = rag_context.get("matched_count", 0)
    try:
        log_llm_call({
            "task": "ai_solution",
            "prompt_version": AI_SOLUTION_PROMPT_VERSION,
            "model": getattr(client, "model", ""),
            "input_summary": {
                "problem_id": problem_id,
                "language": language,
                "rag_matched_count": rag_context.get("matched_count", 0),
                "quality": quality_result,
                "complete": quality_result.get("valid", False)
            },
            "raw_output": last_raw_text,
            "parsed_success": not result.get("parse_fallback"),
            "schema_valid": quality_result.get("valid", False),
            "fallback_used": False,
            "error_message": error_message,
            "latency_seconds": round(time.time() - start_time, 3)
        })
    except Exception:
        pass
    return result


def generate_and_save_solution(problem_id, language="Python"):
    solution = generate_solution(problem_id, language=language)
    return save_solution_note(solution)


def get_or_generate_solution(problem_id, language="Python", force=False):
    if not force:
        cached = get_solution_note(problem_id, language)
        if cached:
            cached = dict(cached)
            cached["cache_hit"] = True
            return cached

    solution = generate_and_save_solution(problem_id, language=language)
    solution = dict(solution)
    solution["cache_hit"] = False
    return solution


def format_solution(solution):
    if not isinstance(solution, dict):
        return "AI 题解暂时不可用。"

    lines = [
        f"力扣 {solution.get('problem_id', '')} "
        f"{solution.get('problem_title', '')}".strip(),
        "",
        "一、解题思路",
        str(solution.get("idea", "")).strip() or "暂无思路说明。",
        "",
        f"二、完整代码（{solution.get('language', '')}，含详细中文注释）",
        str(solution.get("code", "")).rstrip() or "暂无可用代码。",
        "",
        "三、易错点",
    ]

    mistakes = solution.get("common_mistakes", [])
    if not isinstance(mistakes, list):
        mistakes = []
    if mistakes:
        for index, item in enumerate(mistakes[:4], start=1):
            if not isinstance(item, dict):
                continue
            point = _short_text(item.get("point", ""), 16)
            explanation = _short_text(item.get("explanation", ""), 50)
            lines.append(f"{index}. {point}：{explanation}")
    else:
        lines.append("暂无：模型未返回易错点")

    lines.extend([
        "",
        "四、时间复杂度",
        "时间复杂度："
        + (
            str(solution.get("time_complexity", "")).strip()
            or "模型未返回时间复杂度。"
        ),
    ])
    return "\n".join(lines)
