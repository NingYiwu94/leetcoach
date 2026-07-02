import argparse
from datetime import datetime

from ai.ai_plan_generator import apply_week_plan_next
from agent.agent_pending_actions import create_pending_action
from agent.agent_tools import get_tool_definition
from planning.plan_automation import auto_generate_next_plan_if_needed


def _result(
    tool_name,
    success,
    status,
    message,
    requires_confirmation=False,
    error_type="",
    error_message="",
    extra=None,
):
    data = {
        "tool_name": tool_name,
        "success": bool(success),
        "status": status,
        "message": message,
        "requires_confirmation": bool(requires_confirmation),
        "error_type": error_type,
        "error_message": error_message,
    }
    if isinstance(extra, dict):
        data.update(extra)
    return data


def execute_agent_tool(
    tool_name,
    tool_input=None,
    dry_run=False,
    confirmed_by_user=False,
):
    tool_name = str(tool_name or "no_action")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    definition = get_tool_definition(tool_name)

    if not definition:
        return _result(
            tool_name=tool_name,
            success=False,
            status="failed",
            message=f"未知 Agent 工具：{tool_name}",
            error_type="UnknownTool",
            error_message=f"Tool not registered: {tool_name}",
        )

    if dry_run:
        return _result(
            tool_name=tool_name,
            success=True,
            status="skipped",
            message=f"dry-run：已识别工具 {tool_name}，未实际执行。",
            requires_confirmation=definition.get("requires_confirmation"),
        )

    if definition.get("requires_confirmation") and not confirmed_by_user:
        pending_action = create_pending_action(
            tool_name=tool_name,
            action_type=tool_name,
            title=f"确认执行 Agent 工具：{tool_name}",
            description=definition.get("description", ""),
            reason=tool_input.get("reason", ""),
            risk_level=definition.get("risk_level", "unknown"),
            requires_confirmation=True,
            tool_input=tool_input,
            source_decision_id=tool_input.get("decision_id", ""),
            agent_name=tool_input.get("agent_name", "silent_agent"),
        )
        return _result(
            tool_name=tool_name,
            success=True,
            status="pending_confirmation",
            message="该工具需要用户确认，已创建待确认动作。",
            requires_confirmation=True,
            extra={"pending_action_id": pending_action.get("action_id")},
        )

    try:
        if tool_name == "no_action":
            return _result(
                tool_name,
                True,
                "executed",
                tool_input.get("reason") or "无需执行操作。",
            )

        if tool_name == "generate_plan_draft":
            plan_result = auto_generate_next_plan_if_needed(
                trigger=tool_input.get("trigger") or "agent_tool"
            )
            return _result(
                tool_name,
                True,
                "executed" if plan_result.get("generated") else "skipped",
                plan_result.get("message") or "计划草案生成流程已完成。",
                extra={
                    "generated": bool(plan_result.get("generated")),
                    "draft_week": plan_result.get("draft_week"),
                    "generated_by": plan_result.get("generated_by"),
                    "generated_at": plan_result.get("generated_at"),
                    "fingerprint": plan_result.get("fingerprint"),
                    "plan_status": plan_result.get("status"),
                },
            )

        if tool_name == "apply_plan_draft":
            apply_result = apply_week_plan_next()
            success = bool(apply_result.get("success"))
            return _result(
                tool_name,
                success,
                "executed" if success else "failed",
                apply_result.get("message") or "计划草案应用流程已完成。",
                requires_confirmation=True,
                error_type="" if success else "ApplyPlanDraftFailed",
                error_message="" if success else apply_result.get("message", ""),
                extra={
                    "week": apply_result.get("week"),
                    "backup_path": apply_result.get("backup_path"),
                    "archive_path": apply_result.get("archive_path"),
                    "cleanup_warning": apply_result.get("cleanup_warning"),
                },
            )

        if tool_name == "sync_leetcode_records":
            return _result(
                tool_name,
                True,
                "skipped",
                "同步由 GUI 同步页和本地同步服务触发，Agent 当前不主动同步。",
            )

        if tool_name == "surface_review_tasks":
            count = tool_input.get("overdue_review_count")
            suffix = f" 当前到期复习 {count} 条。" if count not in (None, "") else ""
            return _result(
                tool_name,
                True,
                "executed",
                f"到期复习任务会在今日面板显示。{suffix}".strip(),
            )

        if tool_name == "recommend_review_first":
            return _result(
                tool_name,
                True,
                "executed",
                tool_input.get("reason") or "建议先处理复习任务，再推进新题。",
            )

        if tool_name == "do_not_generate_new_plan":
            return _result(
                tool_name,
                True,
                "executed",
                tool_input.get("reason") or "当前不生成新计划，继续保持现有计划。",
            )

        return _result(
            tool_name,
            True,
            "skipped",
            f"工具 {tool_name} 已注册，但当前执行器尚未实现真实动作。",
        )
    except Exception as error:
        return _result(
            tool_name,
            False,
            "failed",
            "Agent 工具执行失败，已安全停止。",
            error_type=type(error).__name__,
            error_message=str(error),
        )


def format_tool_execution_result(result):
    if not isinstance(result, dict):
        return "暂无工具执行结果。"
    lines = [
        "===== Agent 工具执行结果 =====",
        "",
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"工具：{result.get('tool_name', '')}",
        f"状态：{result.get('status', '')}",
        f"成功：{'是' if result.get('success') else '否'}",
        f"需要确认：{'是' if result.get('requires_confirmation') else '否'}",
        f"说明：{result.get('message', '')}",
    ]
    if result.get("error_message"):
        lines.extend([
            f"错误类型：{result.get('error_type', '')}",
            f"错误信息：{result.get('error_message', '')}",
        ])
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a safe Agent tool dry-run.")
    parser.add_argument("--tool", default="no_action")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()
    print(format_tool_execution_result(execute_agent_tool(args.tool, dry_run=True)))
