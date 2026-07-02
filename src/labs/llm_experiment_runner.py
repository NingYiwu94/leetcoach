import argparse
import json
from datetime import datetime
from pathlib import Path

from labs.prompt_experiment import run_plan_prompt_comparison
from labs.prompt_experiment_report import summarize_prompt_experiments
from rag.rag_ab_experiment import run_rag_plan_ab_experiment
from rag.rag_ab_report import summarize_rag_ab_experiments


from app_paths import BASE_DIR
BATCH_REPORTS_PATH = BASE_DIR / "data" / "llm_experiment_batch_reports.json"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_count(value, default=0):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _load_json_list(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup_path = path.with_name(
            f"{path.stem}.broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        )
        try:
            path.replace(backup_path)
        except OSError:
            pass
        return []
    except OSError:
        return []
    return data if isinstance(data, list) else []


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _append_batch_report(report, limit=100):
    reports = _load_json_list(BATCH_REPORTS_PATH)
    reports.append(report)
    _save_json(BATCH_REPORTS_PATH, reports[-limit:])


def _get_prompt_recommendation(prompt_summary):
    if not isinstance(prompt_summary, dict):
        return "unknown", "Prompt 统计报告暂时不可用。"
    return (
        prompt_summary.get("recommended_default") or "unknown",
        prompt_summary.get("recommendation_reason") or "暂无推荐原因。",
    )


def _get_rag_recommendation(rag_summary):
    if not isinstance(rag_summary, dict):
        return "unknown", "RAG 统计报告暂时不可用。"
    return (
        rag_summary.get("recommended_mode") or "unknown",
        rag_summary.get("recommendation_reason") or "暂无推荐原因。",
    )


def _build_overall_conclusion(prompt_summary, rag_summary):
    prompt_version, _ = _get_prompt_recommendation(prompt_summary)
    rag_mode, _ = _get_rag_recommendation(rag_summary)
    conclusions = []

    if prompt_version == "v2":
        conclusions.append("当前 Prompt v2 可以继续作为候选默认版本观察。")
    elif prompt_version == "v1":
        conclusions.append("当前建议继续保留 Prompt v1 作为稳定版本。")
    else:
        conclusions.append("当前 Prompt 统计数据不足，建议继续积累实验样本。")

    if rag_mode == "with_rag":
        conclusions.append("RAG 已显示一定增益，可以继续观察其在 AI 计划生成中的表现。")
    elif rag_mode == "without_rag_or_improve_docs":
        conclusions.append("RAG 暂未稳定提升生成质量，建议先优化检索文档质量。")
    elif rag_mode == "insufficient_data":
        conclusions.append("RAG 实验样本仍偏少，建议继续观察。")
    else:
        conclusions.append("RAG 当前结论尚不明确，建议继续积累 A/B 实验记录。")

    conclusions.append("后续应重点检查 RAG 检索结果是否真正引用历史错因和已完成题记录。")
    return conclusions


def run_llm_experiment_batch(prompt_runs=3, rag_runs=3):
    prompt_runs = _safe_count(prompt_runs, default=3)
    rag_runs = _safe_count(rag_runs, default=3)

    prompt_success = 0
    prompt_failed = 0
    prompt_errors = []
    rag_success = 0
    rag_failed = 0
    rag_errors = []

    timestamp = _now()

    for index in range(prompt_runs):
        print(f"[{_now()}] Prompt 对比实验 {index + 1}/{prompt_runs} ...")
        try:
            run_plan_prompt_comparison()
            prompt_success += 1
        except Exception as error:
            prompt_failed += 1
            prompt_errors.append({
                "run": index + 1,
                "error": str(error),
            })
            print(f"[{_now()}] Prompt 对比实验失败：{error}")

    for index in range(rag_runs):
        print(f"[{_now()}] RAG A/B 实验 {index + 1}/{rag_runs} ...")
        try:
            run_rag_plan_ab_experiment()
            rag_success += 1
        except Exception as error:
            rag_failed += 1
            rag_errors.append({
                "run": index + 1,
                "error": str(error),
            })
            print(f"[{_now()}] RAG A/B 实验失败：{error}")

    try:
        prompt_summary = summarize_prompt_experiments(limit=20)
    except Exception as error:
        prompt_summary = {
            "recommended_default": "unknown",
            "recommendation_reason": f"Prompt 统计生成失败：{error}",
        }

    try:
        rag_summary = summarize_rag_ab_experiments(limit=20)
    except Exception as error:
        rag_summary = {
            "recommended_mode": "unknown",
            "recommendation_reason": f"RAG 统计生成失败：{error}",
        }

    result = {
        "timestamp": timestamp,
        "prompt_runs_requested": prompt_runs,
        "prompt_runs_success": prompt_success,
        "prompt_runs_failed": prompt_failed,
        "prompt_errors": prompt_errors,
        "rag_runs_requested": rag_runs,
        "rag_runs_success": rag_success,
        "rag_runs_failed": rag_failed,
        "rag_errors": rag_errors,
        "prompt_summary": prompt_summary,
        "rag_summary": rag_summary,
        "overall_conclusion": _build_overall_conclusion(
            prompt_summary,
            rag_summary,
        ),
    }
    _append_batch_report(result)
    return result


def _format_conclusion(conclusion):
    if isinstance(conclusion, list):
        return "\n".join(f"{index}. {item}" for index, item in enumerate(conclusion, 1))
    if conclusion:
        return str(conclusion)
    return "暂无综合结论。"


def format_llm_experiment_batch_report(result):
    if not isinstance(result, dict):
        return "暂无 LLM 批量实验报告。"

    prompt_summary = result.get("prompt_summary", {})
    rag_summary = result.get("rag_summary", {})
    prompt_version, prompt_reason = _get_prompt_recommendation(prompt_summary)
    rag_mode, rag_reason = _get_rag_recommendation(rag_summary)

    lines = [
        "===== LeetCoach LLM 实验批量报告 =====",
        "",
        "本次批量实验：",
        (
            "- Prompt 对比实验："
            f"请求 {result.get('prompt_runs_requested', 0)} 次，"
            f"成功 {result.get('prompt_runs_success', 0)} 次，"
            f"失败 {result.get('prompt_runs_failed', 0)} 次"
        ),
        (
            "- RAG A/B 实验："
            f"请求 {result.get('rag_runs_requested', 0)} 次，"
            f"成功 {result.get('rag_runs_success', 0)} 次，"
            f"失败 {result.get('rag_runs_failed', 0)} 次"
        ),
        "",
        "PromptOps 统计：",
        f"推荐 Prompt：{prompt_version}",
        f"原因：{prompt_reason}",
        "",
        "RAG Evaluation 统计：",
        f"推荐模式：{rag_mode}",
        f"原因：{rag_reason}",
        "",
        "综合结论：",
        _format_conclusion(result.get("overall_conclusion")),
    ]

    prompt_errors = result.get("prompt_errors") or []
    rag_errors = result.get("rag_errors") or []
    if prompt_errors or rag_errors:
        lines.extend(["", "本次失败记录："])
        for item in prompt_errors[:5]:
            lines.append(f"- Prompt 第 {item.get('run')} 次：{item.get('error')}")
        for item in rag_errors[:5]:
            lines.append(f"- RAG 第 {item.get('run')} 次：{item.get('error')}")

    return "\n".join(lines).rstrip()


def load_llm_experiment_batch_reports(limit=3):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 3
    return _load_json_list(BATCH_REPORTS_PATH)[-limit:]


def format_recent_llm_experiment_batch_reports(reports):
    reports = reports if isinstance(reports, list) else []
    if not reports:
        return "暂无 LLM 综合实验报告。"

    lines = ["===== 最近 LLM 综合实验报告 =====", ""]
    for report in reversed(reports[-3:]):
        prompt_summary = report.get("prompt_summary", {})
        rag_summary = report.get("rag_summary", {})
        prompt_version, _ = _get_prompt_recommendation(prompt_summary)
        rag_mode, _ = _get_rag_recommendation(rag_summary)
        lines.extend([
            f"时间：{report.get('timestamp', '未知')}",
            (
                "Prompt："
                f"成功 {report.get('prompt_runs_success', 0)} / "
                f"失败 {report.get('prompt_runs_failed', 0)}，"
                f"推荐 {prompt_version}"
            ),
            (
                "RAG："
                f"成功 {report.get('rag_runs_success', 0)} / "
                f"失败 {report.get('rag_runs_failed', 0)}，"
                f"推荐 {rag_mode}"
            ),
            "综合结论：",
            _format_conclusion(report.get("overall_conclusion")),
            "",
        ])
    return "\n".join(lines).rstrip()


def main():
    parser = argparse.ArgumentParser(description="Run LeetCoach LLM experiments.")
    parser.add_argument("--prompt-runs", type=int, default=3)
    parser.add_argument("--rag-runs", type=int, default=3)
    args = parser.parse_args()

    result = run_llm_experiment_batch(
        prompt_runs=args.prompt_runs,
        rag_runs=args.rag_runs,
    )
    print(format_llm_experiment_batch_report(result))


if __name__ == "__main__":
    main()
