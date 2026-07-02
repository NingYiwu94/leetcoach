import json
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
EVAL_PATH = BASE_DIR / "data" / "llm_eval_results.json"
EMPTY_WEAKNESS_VALUES = {
    "",
    "none",
    "null",
    "未分类",
    "暂无",
    "暂无明确分类",
    "未知",
    "无",
}
HARD_SOLUTION_PATTERNS = {
    "```python",
    "```cpp",
    "```c++",
    "class Solution",
    "#include",
    "public:",
    "vector<",
    "ListNode",
    "TreeNode",
}
SOFT_SOLUTION_PATTERNS = {
    "完整代码如下",
    "代码如下",
    "具体实现如下",
    "时间复杂度 O(",
    "空间复杂度 O(",
    "时间复杂度：O(",
    "空间复杂度：O(",
}
GENERIC_TITLES = {
    "算法基础",
    "学习计划",
    "核心题巩固与验收周",
    "数组与指针控制",
    "基础巩固",
    "综合复习",
}
WEAKNESS_RELATED_WORDS = {
    "哈希表": {"哈希", "计数", "映射", "字典", "频次"},
    "双指针": {"双指针", "左右指针", "快慢指针", "指针"},
    "指针移动逻辑": {"双指针", "指针", "左右指针", "快慢指针"},
    "滑动窗口": {"滑动窗口", "窗口", "收缩", "扩张"},
    "边界条件": {"边界", "越界", "边界条件", "特殊情况"},
    "模板不熟": {"模板", "套路", "模式", "题型"},
    "题意理解": {"题意", "理解", "建模"},
    "代码实现错误": {"实现", "代码", "调试"},
    "复杂度分析": {"复杂度", "时间复杂度", "空间复杂度"},
}


def _load_results():
    if not EVAL_PATH.exists():
        return []
    try:
        data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup_path = EVAL_PATH.with_name(
            EVAL_PATH.name
            + f".broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        )
        try:
            EVAL_PATH.replace(backup_path)
        except OSError:
            pass
        return []
    except OSError:
        return []
    return data if isinstance(data, list) else []


def _plan_problem_ids(plan):
    ids = []
    days = plan.get("days", {}) if isinstance(plan, dict) else {}
    if not isinstance(days, dict):
        return ids
    for day in days.values():
        if not isinstance(day, dict):
            continue
        problems = day.get("problems", [])
        if not isinstance(problems, list):
            continue
        for problem_id in problems:
            problem_id = str(problem_id).strip()
            if problem_id and problem_id not in ids:
                ids.append(problem_id)
    return ids


def _context_ids(context, key):
    values = context.get(key, []) if isinstance(context, dict) else []
    result = set()
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict):
                problem_id = str(item.get("problem_id", "")).strip()
                if problem_id:
                    result.add(problem_id)
            else:
                value = str(item).strip()
                if value:
                    result.add(value)
    return result


def _has_clear_weakness(value):
    text = str(value or "").strip()
    return text.lower() not in EMPTY_WEAKNESS_VALUES


def _weakness_terms(weakness):
    text = str(weakness or "").strip()
    terms = {text} if text else set()
    terms.update(WEAKNESS_RELATED_WORDS.get(text, set()))
    for key, values in WEAKNESS_RELATED_WORDS.items():
        if key in text:
            terms.add(key)
            terms.update(values)
    return {item for item in terms if item}


def _recommended_focus_text(plan):
    focus = plan.get("recommended_focus", []) if isinstance(plan, dict) else []
    if isinstance(focus, list):
        return " ".join(str(item) for item in focus)
    return str(focus)


def _detect_solution_content(plan_text):
    normalized = str(plan_text or "")
    hard_hits = [
        pattern for pattern in HARD_SOLUTION_PATTERNS
        if pattern in normalized
    ]

    code_like_hits = []
    for line in normalized.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("def ", "return ")):
            code_like_hits.append(stripped[:80])
        if (
            stripped.startswith(("for ", "while ", "if "))
            and stripped.endswith("{")
        ):
            code_like_hits.append(stripped[:80])

    soft_hits = [
        pattern for pattern in SOFT_SOLUTION_PATTERNS
        if pattern in normalized
    ]
    if "第一步" in normalized and "最后返回" in normalized:
        soft_hits.append("步骤化完整题解")

    return {
        "hard_hits": hard_hits + code_like_hits,
        "soft_hits": soft_hits,
    }


def evaluate_ai_plan(plan, context, save=True):
    context = context if isinstance(context, dict) else {}
    problem_bank = context.get("problem_bank", {})
    if not isinstance(problem_bank, dict):
        problem_bank = {}

    days = plan.get("days", {}) if isinstance(plan, dict) else {}
    plan_ids = _plan_problem_ids(plan)
    plan_text = json.dumps(plan, ensure_ascii=False) if isinstance(plan, dict) else ""

    pending_reviews = _context_ids(context, "pending_reviews")
    unfinished = set(context.get("unfinished_problem_ids", []) or [])
    failed = set(context.get("failed_problem_ids", []) or [])
    weakness = str(context.get("main_weakness", "") or "")
    expected_week = context.get("expected_week")
    completed_ids = set(str(item) for item in context.get("completed_problem_ids", []) or [])
    title = str(plan.get("title", "") if isinstance(plan, dict) else "").strip()
    errors = []
    warnings = []
    infos = []

    if not isinstance(plan, dict) or not plan:
        errors.append("计划为空或不是 JSON object")
    if not isinstance(days, dict):
        errors.append("days 缺失或不是 object")

    completed_as_new = []
    for day in days.values() if isinstance(days, dict) else []:
        if not isinstance(day, dict):
            continue
        task_type = str(day.get("task_type", "new") or "new").strip().lower()
        if task_type not in {"new", "practice"}:
            continue
        for problem_id in day.get("problems", []) or []:
            problem_id = str(problem_id).strip()
            if problem_id and problem_id in completed_ids:
                completed_as_new.append(problem_id)

    missing_bank_ids = [
        problem_id for problem_id in plan_ids if problem_id not in problem_bank
    ]
    has_summary_day = any(
        str(day.get("task_type", "")).lower() in {"summary", "summary_day"}
        or "总结" in str(day.get("goal", ""))
        for day in days.values()
        if isinstance(day, dict)
    )

    has_7_days = isinstance(days, dict) and all(
        str(index) in days for index in range(1, 8)
    )
    daily_limit_ok = True
    day_problem_list_ok = True
    short_reason_days = []
    if isinstance(days, dict):
        for day_index in range(1, 8):
            day = days.get(str(day_index), {})
            if not isinstance(day, dict):
                continue
            problems = day.get("problems", [])
            if not isinstance(problems, list):
                day_problem_list_ok = False
                daily_limit_ok = False
            elif len(problems) > 2:
                daily_limit_ok = False
            reason = str(day.get("reason", "") or "").strip()
            if reason and len(reason) < 8:
                short_reason_days.append(str(day_index))

    if not has_7_days:
        errors.append("缺少完整 7 天计划")
    if not day_problem_list_ok:
        errors.append("某些 day 的 problems 字段不是 list")
    if not daily_limit_ok:
        errors.append("某些 day 的题目数量超过 2 道")
    if not has_summary_day:
        errors.append("缺少总结日")
    if title in GENERIC_TITLES or not title:
        warnings.append("计划标题略空泛")
    if short_reason_days:
        warnings.append(
            "部分 day 的 reason 过短：Day "
            + "、".join(short_reason_days[:5])
        )

    has_review_day = any(
        str(day.get("task_type", "")).lower() in {"review", "review_day"}
        or "复习" in str(day.get("goal", ""))
        for day in days.values()
        if isinstance(day, dict)
    )
    if not has_review_day:
        warnings.append("计划中没有明显复习日")

    uses_unfinished = not unfinished or bool(set(plan_ids) & unfinished)
    if not unfinished:
        infos.append("当前没有未完成题，因此跳过未完成题引用检查")
    elif not uses_unfinished:
        warnings.append("AI 计划没有明显安排当前未完成题")

    uses_failed = not failed or bool(set(plan_ids) & failed)
    if not failed:
        infos.append("当前没有未通过题，因此跳过未通过题引用检查")
    elif not uses_failed:
        warnings.append("AI 计划没有明显安排未通过题")

    uses_pending = not pending_reviews or bool(set(plan_ids) & pending_reviews)
    if not pending_reviews:
        infos.append("当前没有待复习题，因此跳过待复习引用检查")
    elif not uses_pending:
        warnings.append("AI 计划没有明显安排待复习题")

    has_clear_weakness = _has_clear_weakness(weakness)
    weakness_terms = _weakness_terms(weakness) if has_clear_weakness else set()
    focus_text = _recommended_focus_text(plan)
    weakness_source_text = plan_text + " " + focus_text
    uses_weakness = (
        True
        if not has_clear_weakness
        else any(term in weakness_source_text for term in weakness_terms)
    )
    if not has_clear_weakness:
        infos.append("当前没有明确薄弱点，已跳过薄弱点引用检查")
    elif not uses_weakness:
        warnings.append(f"AI 计划没有明显引用当前薄弱点：{weakness}")

    solution_detection = _detect_solution_content(plan_text)
    if solution_detection["hard_hits"]:
        errors.append(
            "计划中出现明显代码或完整题解内容："
            + "、".join(solution_detection["hard_hits"][:3])
        )
    elif solution_detection["soft_hits"]:
        warnings.append(
            "计划中出现疑似题解表达："
            + "、".join(solution_detection["soft_hits"][:3])
        )

    if missing_bank_ids:
        warnings.extend(
            f"推荐题目 {problem_id} 不在 problem_bank 中"
            for problem_id in missing_bank_ids[:8]
        )

    if completed_as_new:
        unique_completed_as_new = sorted(set(completed_as_new))
        errors.append(
            "已完成题被当作新题安排："
            + "、".join(unique_completed_as_new[:8])
        )

    checks = {
        "week_increment_ok": (
            expected_week in (None, "", 0)
            or str(plan.get("week", "")) == str(expected_week)
        ),
        "title_specific": bool(title) and title not in GENERIC_TITLES,
        "has_7_days": has_7_days,
        "daily_limit_ok": daily_limit_ok,
        "has_review_day": has_review_day,
        "has_summary_day": has_summary_day,
        "uses_unfinished_problems": uses_unfinished,
        "uses_failed_problems": uses_failed,
        "uses_pending_reviews": uses_pending,
        "uses_weakness": uses_weakness,
        "no_solution_content": not solution_detection["hard_hits"],
        "completed_not_new": not completed_as_new,
        "problem_bank_ids_ok": not missing_bank_ids,
    }

    if not checks["week_increment_ok"]:
        errors.append("计划周次没有按当前 Week 自动递增")

    hard_count = 0
    for problem_id in plan_ids:
        problem = problem_bank.get(problem_id, {})
        if isinstance(problem, dict) and problem.get("difficulty") == "Hard":
            hard_count += 1
    learner_level = context.get("learner_profile", {}).get("level", "")
    if learner_level in {"beginner", "developing"} and hard_count:
        warnings.append("新手或基础进阶阶段不应安排 Hard 题")

    score = 100
    for error in errors:
        if any(word in error for word in {"days", "7 天", "计划为空", "problems"}):
            score -= 35
        elif any(word in error for word in {"代码", "题解", "class Solution"}):
            score -= 35
        else:
            score -= 25
    score -= len(warnings) * 6
    score = max(0, min(100, score))
    quality_level = (
        "good"
        if score >= 85
        else "warning"
        if score >= 70
        else "fallback_candidate"
    )
    issues = errors + warnings
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task": "ai_plan_generation",
        "plan_title": title,
        "score": score,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "issues": issues,
        "plan_week": plan.get("week", "") if isinstance(plan, dict) else "",
        "quality_level": quality_level
    }

    if save:
        try:
            EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
            results = _load_results()
            results.append(result)
            EVAL_PATH.write_text(
                json.dumps(results, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except OSError:
            pass

    return result


def get_recent_plan_evaluations(limit=5):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 5
    return _load_results()[-limit:]


def format_recent_plan_evaluations(results):
    if not results:
        return "目前还没有 AI 计划评估结果。"

    lines = ["===== 最近 AI 计划评估 =====", ""]
    for index, item in enumerate(reversed(results), start=1):
        lines.extend([
            (
                f"{index}. Week {item.get('plan_week', '')} "
                f"{item.get('plan_title', '')}"
            ).rstrip(),
            f"   时间：{item.get('timestamp', '未知')}",
            f"   评分：{item.get('score', 0)}",
            f"   状态：{item.get('quality_level', '未知')}",
        ])
        if any(key in item for key in {"errors", "warnings", "infos"}):
            errors = item.get("errors", []) or []
            warnings = item.get("warnings", []) or []
            infos = item.get("infos", []) or []
            lines.append("   严重问题：")
            if errors:
                lines.extend(f"   - {issue}" for issue in errors[:5])
            else:
                lines.append("   - 无")
            lines.append("   质量提醒：")
            if warnings:
                lines.extend(f"   - {issue}" for issue in warnings[:5])
            else:
                lines.append("   - 无")
            lines.append("   说明：")
            if infos:
                lines.extend(f"   - {issue}" for issue in infos[:5])
            else:
                lines.append("   - 无")
        else:
            issues = item.get("issues", [])
            if issues:
                lines.append("   问题：")
                lines.extend(f"   - {issue}" for issue in issues[:5])
            else:
                lines.append("   问题：无")
        lines.append("")
    return "\n".join(lines).rstrip()
