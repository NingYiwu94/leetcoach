# LeetCoach Data Schema

LeetCoach 当前使用 JSON 文件进行本地存储。历史记录类文件的顶层结构为列表；`ai_next_plan_draft.json` 是单个计划草案对象。

## `data/records.json`

刷题记录列表。

| 字段 | 类型 | 含义 | 兼容说明 |
| --- | --- | --- | --- |
| `date` | string | 刷题日期，格式为 `YYYY-MM-DD` | 核心字段 |
| `problem_id` | string | 力扣题号，例如 `"977"` | 核心字段；旧数据中的 `"题号：977"` 会在业务层清洗 |
| `status` | string | 本次完成状态 | 核心字段 |
| `difficulty_feeling` | string | 用户对题目难度的主观感受 | 旧数据缺失时按 `"未知"` 处理 |
| `mistake_type` | string | 错因分类 | 旧数据缺失时按 `"未分类"` 处理 |
| `mistake_note` | string | 本次刷题的问题、卡点或收获 | 旧数据缺失时按空内容处理 |
| `source` | string | 记录来源，自动同步记录为 `"leetcode_auto_sync"` | 可选；兼容旧记录 |
| `raw_status` | string | 导入前的原始提交状态 | 可选；仅导入记录使用 |
| `language` | string | 提交使用的编程语言 | 可选；仅导入记录使用 |
| `submit_time` | string | 原始提交时间 | 可选；仅导入记录使用 |
| `title` | string | 力扣题目标题 | 可选；自动同步记录使用 |
| `title_slug` | string | 力扣题目公开 slug | 可选；自动同步记录使用 |
| `plan_week` | integer/string | 快捷完成时关联的计划周次 | 可选 |
| `plan_start_date` | string | 快捷完成时关联的计划开始日期 | 可选 |

`status` 合法值：

- `AC`
- `看提示后AC`
- `未通过`

任务清单点击完成时，`source` 为 `task_board`，并保存 `plan_week` 与
`plan_start_date`。因此即使提前完成尚未开始的计划题，也能归入正确计划。

旧记录可能包含 `"未知"`，数据校验会给出 warning，但不会阻止程序运行。

## `data/reviews.json`

复习任务列表。

| 字段 | 类型 | 含义 | 兼容说明 |
| --- | --- | --- | --- |
| `problem_id` | string | 待复习题号 | 核心字段；旧题号格式会在业务层清洗 |
| `next_review_date` | string | 下次复习日期，格式为 `YYYY-MM-DD` | 核心字段 |
| `reason` | string | 安排复习的原因或错题说明 | 核心字段 |
| `done` | boolean | 是否已经完成复习 | 核心字段；缺失时业务层通常按未完成处理 |
| `source` | string | 复习记录来源，例如 `"leetcode_auto_sync"` | 可选；兼容旧记录 |
| `priority_score` | integer | 根据逾期、失败、提示后 AC 和重复提交计算的优先级分数 | 可选；旧数据运行时动态计算 |
| `priority_level` | string | 复习优先级：`高`、`中`、`低` | 可选；旧数据运行时动态计算 |
| `failure_count` | integer | 该题历史未通过次数 | 可选 |
| `assisted_count` | integer | 该题历史看提示后 AC 次数 | 可选 |
| `submission_count` | integer | 该题累计学习记录数 | 可选 |
| `consecutive_failures` | integer | 最近连续未通过次数 | 可选 |
| `last_status` | string | 最近一次学习状态 | 可选 |
| `overdue_days` | integer | 当前复习任务逾期天数 | 可选；每天动态更新 |
| `updated_at` | string | 复习任务最近更新时间 | 可选 |
| `completed_at` | string | 完成复习任务的时间 | 可选 |
| `merged_into` | string | 重复任务被合并到的题号 | 可选 |
| `review_round` | integer | 当前间隔复习轮次，从 1 开始 | 旧数据按第 1 轮处理 |
| `interval_days` | integer | 本轮与上一轮之间的间隔天数 | 可选 |
| `scheduled_from` | string | `learning_record` 或 `review_completion` | 可选 |
| `previous_review_completed_at` | string | 上一轮复习完成时间 | 可选 |
| `mastery_result` | string | 本轮结果：`independent`、`assisted` 或 `not_mastered` | 可选 |
| `mastery_label` | string | 本轮结果中文标签 | 可选 |
| `previous_mastery_result` | string | 生成当前任务时上一轮的掌握结果 | 可选 |
| `previous_mastery_label` | string | 上一轮掌握结果中文标签 | 可选 |

力扣自动同步记录会创建或更新复习任务。`source` 字段用于区分数据来源，不影响旧数据兼容。
同一题只保留一个有效待复习任务；历史重复任务会标记为已合并。
Day 6 核心题验收在没有现成复习任务时，会创建
`source = "stage_review"` 的完成记录，并自动安排后续复习。

新的学习提交会创建或重置为第 1 轮复习。完成时根据掌握度安排：

- 独立写出：按第 1 轮 7 天、第 2 轮 14 天、之后 30 天延长间隔。
- 看提示写出：缩短为 3 到 5 天。
- 仍未掌握：不升级轮次，次日再次练习。

最近提交仍未通过时，间隔也会自动缩短。

## `data/hint_logs.json`

AI 分层提示使用记录。

| 字段 | 类型 | 含义 | 兼容说明 |
| --- | --- | --- | --- |
| `date` | string | 提示生成日期，格式为 `YYYY-MM-DD` | 核心字段 |
| `problem_id` | string | 题号 | 核心字段 |
| `user_question` | string | 用户当时的卡点 | 核心字段 |
| `hint_level` | string | 提示层级：`1`、`2` 或 `3` | 核心字段 |
| `hint_title` | string | 提示标题 | 核心字段 |
| `hint_content` | string | 提示正文 | 核心字段 |
| `next_question` | string | 引导用户继续思考的问题 | 核心字段 |
| `do_not_show_code` | boolean | 是否禁止输出完整代码，正常值为 `true` | 核心字段 |

旧版本可能没有 `hint_logs.json`。文件不存在时，系统会按空列表处理并在首次保存时自动创建。

## `data/ai_solution_notes.json`

AI 题解笔记列表。用户在 AI 助手中输入题号生成标准题解，或在题库具体题目页点击
“生成 / 更新 AI 题解”后写入。题库页会按 `problem_id` 读取最近一次生成的笔记。

| 字段 | 类型 | 含义 | 兼容说明 |
| --- | --- | --- | --- |
| `problem_id` | string | 力扣题号，例如 `"704"` | 核心字段；读取时会清洗旧的 `"题号：704"` 格式 |
| `problem_title` | string | 题目名称 | 可选；旧数据缺失时显示空标题 |
| `idea` | string | 解题思路说明 | 核心字段 |
| `language` | string | 代码语言，例如 `Python` 或 `C++` | 核心字段 |
| `code` | string | 带详细中文注释的完整可提交代码 | 核心字段 |
| `common_mistakes` | list[object] | 易错点列表，每项包含 `point` 和 `explanation` | 核心字段 |
| `time_complexity` | string | 时间复杂度及简要推导 | 核心字段 |
| `generated_at` | string | 生成时间，格式为 `YYYY-MM-DD HH:MM:SS` | 核心字段 |
| `source` | string | 固定为 `"ai_solution"` | 核心字段 |
| `parse_fallback` | boolean | 模型输出未完全满足结构时的兜底标记 | 可选 |

同一题同一语言再次生成时会更新为最新笔记，避免同一页面堆积大量旧答案。
文件不存在、为空或损坏时，系统按空列表处理，首次保存会自动创建。

## `data/agent_memory.json`

Agent 每天的学习状态快照。同一天多次生成行动方案时更新当天快照，
不会追加为多个趋势样本。

| 字段 | 类型 | 含义 | 兼容说明 |
| --- | --- | --- | --- |
| `date` | string | Agent 运行日期，格式为 `YYYY-MM-DD` | 核心字段 |
| `stage` | string | 当前学习阶段，例如 `"Week1 Day3"` | 核心字段 |
| `progress_status` | string | 当前进度状态 | 核心字段 |
| `main_problem` | string | 当前主要问题或薄弱点 | 核心字段 |
| `action_plan` | list[string] | Agent 生成的今日行动列表 | 核心字段 |
| `first_seen_at` | string | 当天首次生成行动方案的时间 | 旧数据可缺少 |
| `updated_at` | string | 当天快照最后更新时间 | 旧数据可缺少 |
| `run_count` | integer | 当天 Agent 运行次数，仅用于诊断 | 旧数据默认为 1 |

同一日期只保留一条快照。趋势分析统计最近 7 个有记录的日期，而不是最近
7 次界面刷新。旧版本的同日重复记录会自动合并；文件不存在、为空或损坏时，
系统会按空列表处理。

## `data/learning_analysis.json`

由提交记录和题库信息自动生成的学习分析快照。用户不需要手动维护。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `generated_at` | string | 分析生成时间 |
| `main_weakness` | string | 当前主要薄弱点，例如 `双指针：指针移动逻辑` |
| `main_topic` | string | 自动推断的主要薄弱题型 |
| `main_mistake` | string | 有人工记录时的主要错因 |
| `learning_status` | string | 当前学习稳定性结论 |
| `failure_count` | integer | 累计未通过次数 |
| `assisted_count` | integer | 累计看提示后 AC 次数 |
| `unresolved_count` | integer | 最近仍未通过的题目数量 |
| `topic_scores` | object | 各题型的风险分数 |
| `mistake_scores` | object | 人工错因的风险分数 |
| `risky_problems` | list[object] | 高风险题目及可解释依据 |
| `recommended_actions` | list[string] | 自动生成的复盘行动 |

自动分析只在存在未通过、看提示后 AC、首次完成前重试或人工错因时
增加风险。普通一次 AC 不会被当作薄弱点。该文件可删除，系统会根据
`records.json` 重新生成。

## `data/llm_call_logs.json`

LLM 调用日志列表。用于 PromptOps 调试和失败分析，不保存 API Key。

| 字段 | 类型 | 含义 | 兼容说明 |
| --- | --- | --- | --- |
| `timestamp` | string | 调用记录时间 | 核心字段 |
| `task` | string | 调用任务，例如 `ai_plan_generator` | 核心字段 |
| `prompt_version` | string | Prompt 模板版本 | 核心字段 |
| `model` | string | 使用的模型名称 | 核心字段 |
| `input_summary` | object | 输入摘要，不包含 API Key | 可选 |
| `raw_output` | string | 模型原始输出，最多保留约 4000 字符 | 可选 |
| `parsed_success` | boolean | JSON 解析是否成功 | 核心字段 |
| `schema_valid` | boolean | 结构校验是否通过 | 核心字段 |
| `fallback_used` | boolean | 是否使用规则兜底 | 核心字段 |
| `error_message` | string | 失败原因 | 可选 |
| `latency_seconds` | number | 调用耗时 | 核心字段 |

文件不存在时，首次 LLM 调用后自动创建。JSON 损坏时，系统会尝试备份旧文件并重新初始化。

## `data/llm_eval_results.json`

AI 输出评估结果列表。当前主要记录 AI 计划生成质量评估。

| 字段 | 类型 | 含义 | 兼容说明 |
| --- | --- | --- | --- |
| `timestamp` | string | 评估时间 | 核心字段 |
| `task` | string | 评估任务，例如 `ai_plan_generator` | 核心字段 |
| `score` | integer | 质量评分，0 到 100 | 核心字段 |
| `checks` | object | 各项检查是否通过 | 核心字段 |
| `issues` | list[string] | 发现的问题 | 核心字段 |
| `plan_week` | integer/string | 被评估计划周次 | 可选 |

文件不存在时，首次 AI 计划评估后自动创建。

## `data/ai_weekly_reviews.json`

AI 周总结历史列表。每次成功生成可解析的 AI 周总结后追加一条记录。

| 字段 | 类型 | 含义 | 兼容说明 |
| --- | --- | --- | --- |
| `date` | string | 总结生成日期，格式为 `YYYY-MM-DD` | 核心字段 |
| `week` | integer/string | 对应周次 | 核心字段 |
| `summary_title` | string | 周总结标题 | 核心字段 |
| `overall_progress` | string | 本周整体完成情况 | 核心字段 |
| `main_weaknesses` | list[string] | 主要薄弱点 | 无明确薄弱点时可为空列表 |
| `representative_problems` | list[string] | 代表题目编号 | 数据不足时可为空列表 |
| `learning_feedback` | string | AI 学习反馈 | 核心字段 |
| `next_week_focus` | list[string] | 下周学习重点 | 核心字段 |
| `recommended_actions` | list[string] | 可执行行动建议 | 核心字段 |

文件不存在时数据校验只给 warning。首次成功生成 AI 周总结时会自动创建。

## `data/ai_next_plan_draft.json`

AI 生成的下一周计划草案。顶层结构是单个 JSON object，不是列表。

| 字段 | 类型 | 含义 | 兼容说明 |
| --- | --- | --- | --- |
| `plan_title` | string | 下一周计划标题 | 核心字段 |
| `strategy` | string | 下一周整体学习策略 | 核心字段 |
| `days` | object | Day 1 到 Day 7 的每日安排 | 核心字段 |
| `reason` | string | 计划调整原因 | 核心字段 |

`days` 中每天包含：

- `goal`：当天目标
- `tasks`：题号列表；新题未确定时为空列表
- `task_type`：`review`、`redo`、`new` 或 `summary`

该文件只是草案，不会覆盖 `config/week_plan.json`。文件不存在时数据校验只给 warning，首次成功生成 AI 计划时自动创建。

## `config/leetcode_config.json`

力扣公开提交记录自动同步配置。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `leetcode_username` | string | 公开力扣用户名；为空时跳过同步 |
| `site` | string | 站点：`leetcode.cn` 或 `leetcode.com` |
| `auto_sync_on_start` | boolean | 启动 GUI 时是否自动尝试同步 |
| `sync_limit` | integer | 每次最多读取的最近提交数量 |

示例：

```json
{
  "leetcode_username": "",
  "site": "leetcode.cn",
  "auto_sync_on_start": true,
  "sync_limit": 20
}
```

自动同步产生的刷题记录使用：

```text
source = leetcode_auto_sync
```

该功能通过本地 `extensions/chrome` 在用户正常使用的 Chrome 页面中
读取最近提交记录。LeetCoach 不保存账号密码，也不读取、导出或记录
Cookie；同步结果仅通过本机 `127.0.0.1:18777` 传递。接口不可用时继续
使用本地数据。

## `data/leetcode_sync_state.json`

记录最近一次成功同步状态。成功过一次后，LeetCoach 后续只静默尝试使用
已安装扩展或已有力扣标签页，不再主动弹出 Chrome。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `success` | boolean | 最近同步是否成功 |
| `username` | string | 同步用户名 |
| `site` | string | 同步站点 |
| `last_success_at` | string | 最近成功时间 |
| `fetched` | integer | 最近读取记录数 |
| `imported` | integer | 最近新增记录数 |

## `config/week_plan_next.json`

AI 或规则生成的下一阶段计划草案。顶层结构是单个 JSON object。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `week` | integer | 下一阶段周次 |
| `title` | string | 计划标题 |
| `start_date` | string | 计划开始日期，格式为 `YYYY-MM-DD` |
| `days` | object | Day 1 到 Day 7 的每日安排 |
| `generated_by` | string | `ai_plan_generator` 或 `rule_fallback` |
| `reason` | string | 生成整份计划的原因 |
| `recommended_focus` | list[string] | 下一阶段推荐重点 |
| `generated_at` | string | 草案生成时间，格式为 `YYYY-MM-DD HH:MM:SS` |
| `generated_for_week` | integer | 生成草案时对应的当前周次 |
| `generation_trigger` | string | 生成来源，例如 `sync`、`manual` |
| `context_fingerprint` | string | 学习状态摘要，用于避免重复生成和误覆盖 |
| `mastery_review_ids` | list[string] | 因最近复习未独立掌握而必须重做的题号 |
| `priority_review_ids` | list[string] | 下一阶段优先安排的全部复习题号 |
| `adaptive_reason` | string | 根据掌握度调整专题、题量和顺序的原因 |

`days` 中每天包含：

- `date_note`：日期说明，例如 `Day 1`
- `problems`：题号列表，每天最多 2 道
- `goal`：当天学习目标
- `reason`：当天安排原因

该文件仅是草案，不会自动覆盖 `config/week_plan.json`。用户在 GUI
确认应用后，系统会先生成
`config/week_plan_backup_YYYYMMDD_HHMMSS.json`，再更新当前计划。

同步后的学习状态达到计划切换条件时，系统可以自动生成下一周草案。
已有待确认草案时不会自动覆盖；当前计划仍然只有在用户确认后才会更新。

计划完成度使用 `start_date` 作为周期边界。刷题记录的 `submit_time`
优先于 `date`；只有记录日期不早于计划开始日期，且状态为 `AC` 或
`看提示后AC` 时，才计入该计划的已完成题目。缺少 `start_date` 的旧计划
继续使用兼容模式。

运行时会根据 `start_date` 将计划判断为 `upcoming`、`active`、
`ended` 或 `unknown`。该状态由程序动态计算，不需要写回 JSON。

## `config/plan_archive/`

用户确认应用计划后，草案会归档到：

`config/plan_archive/week_plan_week_<week>_<timestamp>.json`

归档保留计划原有字段，并增加：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `activated_at` | string | 计划被确认应用的时间 |
| `archive_status` | string | 当前固定为 `applied` |

应用成功后，`config/week_plan_next.json` 会被移除，避免已应用草案继续显示为
待确认状态。原当前计划仍会备份为
`config/week_plan_backup_YYYYMMDD_HHMMSS.json`。

## `config/plan_review_state.json`

用户在今日面板选择“明天再提醒”时创建，用于暂缓当前草案的首页提醒。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `draft_identity` | string | 当前草案身份摘要，只对该草案有效 |
| `draft_week` | integer | 草案目标周次 |
| `snoozed_until` | string | 恢复提醒日期，格式为 `YYYY-MM-DD` |
| `updated_at` | string | 暂缓操作时间 |

新草案的身份变化后，旧暂缓状态自动失效。计划应用成功后该文件会被清理。

## `data/plan_task_state.json`

保存周计划中非题目任务的完成状态，例如 Day 6 阶段复习和 Day 7 周总结。
这些记录不会写入 `records.json`，因此不会干扰刷题统计。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `plan_key` | string | 计划周次、开始日期和启用时间组成的唯一标识 |
| `plan_week` | integer | 所属计划周次 |
| `plan_start_date` | string | 所属计划开始日期 |
| `task_id` | string | 阶段任务唯一标识 |
| `day_index` | integer | Day 1 到 Day 7 |
| `task_type` | string | `review_day` 或 `summary` |
| `title` | string | 阶段任务标题 |
| `completed` | boolean | 是否完成 |
| `completed_at` | string | 完成时间，格式为 `YYYY-MM-DD HH:MM:SS` |
| `stage_summary` | object | Day 7 确认后保存的阶段总结快照，仅总结任务存在 |

`stage_summary` 包含：

- `generated_at`：总结生成时间
- `week`、`plan_title`、`weekly_theme`：所属学习阶段
- `planned_count`、`completed_count`：计划题完成情况
- `status_counts`：AC、看提示后 AC、未通过次数
- `mastery`：独立写出、看提示写出、仍未掌握、尚未验收题号
- `needs_review`：下一阶段优先复习题号
- `conclusion`、`recommendation`：阶段判断与下一步建议

下一阶段 AI 计划会读取最近 3 次阶段总结。

自定进度模式会把题目、阶段复习和周总结都纳入完成条件。只有所有任务完成后，
系统才会生成下一阶段计划草案。
