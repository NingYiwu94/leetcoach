from copy import deepcopy


TOOL_REGISTRY = {
    "no_action": {
        "name": "no_action",
        "description": "不执行任何操作，用于等待用户确认或保持当前状态。",
        "risk_level": "low",
        "requires_confirmation": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": "Agent 判断无需执行操作的原因。"
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": "是否成功完成 no-op。",
                "message": "执行结果说明。",
            },
        },
    },
    "sync_leetcode_records": {
        "name": "sync_leetcode_records",
        "description": "同步力扣提交记录。当前主要由 GUI 同步页和本地同步服务触发。",
        "risk_level": "low",
        "requires_confirmation": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "trigger": "触发来源，例如 startup、sync、manual。"
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": "executed/skipped/failed。",
                "message": "同步结果说明。",
            },
        },
    },
    "surface_review_tasks": {
        "name": "surface_review_tasks",
        "description": "提示到期复习任务应出现在今日任务中，不直接修改数据。",
        "risk_level": "low",
        "requires_confirmation": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "overdue_review_count": "到期未复习数量。"
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "message": "展示说明。",
            },
        },
    },
    "generate_plan_draft": {
        "name": "generate_plan_draft",
        "description": "生成下一阶段计划草案，但不应用计划。",
        "risk_level": "medium",
        "requires_confirmation": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "trigger": "触发来源。",
                "reason": "Agent 生成草案的原因。",
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "generated": "是否生成新草案。",
                "draft_week": "草案周次。",
                "message": "生成结果说明。",
            },
        },
    },
    "apply_plan_draft": {
        "name": "apply_plan_draft",
        "description": "应用计划草案为正式计划。高风险动作，必须由用户确认，Agent 不自动执行。",
        "risk_level": "high",
        "requires_confirmation": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "draft_week": "待应用计划草案周次。"
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": "pending_confirmation。",
                "message": "确认要求说明。",
            },
        },
    },
    "recommend_review_first": {
        "name": "recommend_review_first",
        "description": "给出先复习再推进新题的轻量建议。",
        "risk_level": "low",
        "requires_confirmation": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": "建议优先复习的原因。"
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "message": "建议文本。",
            },
        },
    },
    "do_not_generate_new_plan": {
        "name": "do_not_generate_new_plan",
        "description": "明确保持当前计划，不提前生成新计划。",
        "risk_level": "low",
        "requires_confirmation": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": "保持当前计划的原因。"
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "message": "执行结果说明。",
            },
        },
    },
}


def get_tool_registry():
    return deepcopy(TOOL_REGISTRY)


def get_tool_definition(tool_name):
    tool = TOOL_REGISTRY.get(str(tool_name or ""))
    return deepcopy(tool) if tool else None


def list_agent_tools():
    return [
        deepcopy(TOOL_REGISTRY[name])
        for name in sorted(TOOL_REGISTRY.keys())
    ]


def format_agent_tools():
    lines = ["===== Agent 工具注册表 =====", ""]
    for tool in list_agent_tools():
        lines.extend([
            f"工具：{tool.get('name')}",
            f"用途：{tool.get('description')}",
            f"风险等级：{tool.get('risk_level')}",
            f"需要用户确认：{'是' if tool.get('requires_confirmation') else '否'}",
            "",
        ])
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    print(format_agent_tools())
