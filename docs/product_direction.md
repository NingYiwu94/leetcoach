# LeetCoach 产品方向

## 北极星目标

LeetCoach 是个人算法学习管家，不是 AI 题解助手。

用户每天打开软件后，应直接知道：

- 今天做什么
- 今天复习什么
- 当前进度如何
- 下一步是否需要调整计划

## 核心闭环

```text
同步力扣记录
→ 更新学习记录
→ 安排复习任务
→ 分析学习状态
→ 生成下一阶段计划
→ 用户确认并应用
→ 首页给出今日行动
→ 完成核心题、阶段复习和周总结
→ 生成下一阶段草案
```

## 产品原则

1. 今日面板始终是主入口。
2. 自动同步优先，减少日常输入。
3. AI 主要用于反思和计划，不替用户解题。
4. AI 计划必须由用户确认后才能应用。
5. 同步或 AI 失败时，本地学习管理仍可运行。
6. GUI 保持简洁，不堆叠统计和技术细节。
7. 先稳定闭环，再考虑复杂框架和基础设施。
8. 学习阶段按完成情况推进，不要求用户等待自然周日期。
9. 完整复习队列保留在后台，首页只展示当天可执行的少量高优先级任务。
10. 计划推进以真实掌握度为准，历史 AC 不能覆盖最近“仍未掌握”的反馈。

## 页面职责

- 今日面板：今日任务、复习、进度、建议和行动方案
- 数据同步：同步记录、最近同步状态和同步组件
- 计划管理：当前计划、AI 草案、应用与备份
- 查看复盘：历史、错因、总结和趋势
- AI 助手：分层提示、AI 周总结和辅助建议
- 系统工具：数据校验、配置检查和诊断

## 近期优先级

1. 稳定 Chrome 同步组件和同步状态反馈。
2. 完善计划切换判断和计划管理体验。
3. 持续校准重复失败、提示后 AC、逾期和重复提交的复习优先级。
4. 让今日建议和计划持续使用自动学习分析结果。
5. 减少需要用户手动维护的配置。

## LLM 应用开发学习目标

LeetCoach 不只是一个刷题 GUI，也用于系统学习大模型应用开发。

当前阶段重点不是继续堆普通业务功能，而是把 AI 能力做成可观察、可评估、可迭代的工程层：

- Prompt 模板化：Prompt 放入 `resources/prompts/`，通过变量渲染，而不是散落在业务代码里。
- Structured Output：关键 AI 输出必须有明确 JSON 结构。
- LLM 调用日志：记录任务、Prompt 名称、Prompt 版本、模型、输入摘要、Prompt 预览、原始输出、解析状态、兜底状态、错误类型和耗时。
- 输出质量评估：AI 计划生成后进行结构校验、学习质量评分和问题归因。
- Prompt 版本迭代：通过日志和评估结果比较不同 Prompt 版本的稳定性。
- Prompt A/B 测试：在同一份学习上下文下对比不同 Prompt 版本的计划质量、合法 JSON 稳定性和 fallback 触发率。
- 规则兜底：解析失败、Schema 不通过或评分过低时，自动回退到规则版计划。
- LLM Lab：在 GUI 设置页查看最近调用、最近评估、当前 Prompt 模板，并手动触发测试计划生成。

这条线服务于学习 Prompt 工程和大模型应用开发，不改变 LeetCoach “个人算法学习管家”的主定位。

## v2.1.4 Prompt 实验统计报告

PromptOps 不只看单次输出，也要看多次实验后的稳定性。LeetCoach 通过 Prompt 实验统计报告观察：

- Prompt 版本评估
- 输出稳定性
- fallback 率
- JSON 解析成功率
- Schema 通过率
- 实验驱动 Prompt 迭代

本阶段只生成推荐，不自动切换默认 Prompt。默认 Prompt 的切换仍需要开发者基于统计报告手动确认。

## v2.2 RAG 检索质量评估

LeetCoach 的 RAG 学习阶段不只关注“能检索”，也关注检索是否真的提升生成质量。

本阶段重点学习：

- RAG 文档质量
- 相似度检索
- 检索相关性评估
- RAG 上下文注入
- 有无 RAG 对比实验
- RAG 是否真正提升 AI 计划生成质量

所有 RAG 实验只用于分析，不自动应用计划，不改变用户的正式学习流程。

## v2.2.1 RAG A/B 实验统计报告

LeetCoach 从单次 RAG A/B 实验进入多次统计分析，用于判断 RAG 是否真的提升 AI 计划生成质量。

观察重点包括：

- with_rag / without_rag 平均分差异
- fallback 率差异
- 历史上下文引用率
- 胜出次数
- RAG 是否引入噪声或质量提醒

本阶段只做分析和推荐，不自动修改 RAG 默认开关。

## v2.2.2 LLM 批量实验与综合报告

LeetCoach 从单次 Prompt / RAG 实验进入批量采集阶段。

本阶段目标不是自动切换策略，而是通过多次实验观察：

- Prompt v1 / v2 哪个更稳定
- RAG 是否真的提高 AI 计划生成质量
- fallback 是否频繁发生
- JSON 解析和 Schema 校验是否稳定
- 后续是否值得切换默认 Prompt 或继续优化 RAG 文档质量

批量实验会保存到 `data/llm_experiment_batch_reports.json`，只用于分析和学习 PromptOps / RAG Evaluation，不会自动应用任何计划，也不会覆盖正式周计划。

## v2.3 RAG 证据链与引用追踪

LeetCoach 从 RAG A/B 评分进入 RAG grounding / citation trace 阶段。

本阶段关注：

- RAG 检索到了哪些历史记忆
- 每条记忆来自哪个本地数据源
- 哪些记忆被注入 Prompt
- 哪些记忆被最终计划明确引用
- 哪些记忆被检索到但没有被使用
- 是否存在没有真实 RAG 证据支持的“历史依据”表述

目标是让 RAG 的使用过程可解释、可追踪、可评估，让 LeetCoach 从“黑盒上下文注入”推进到“可解释的历史记忆引用”。

## v2.3.1 RAG 证据链统计报告

LeetCoach 从单次 RAG trace 进入多次证据链统计。

本阶段关注：

- 多次 RAG 计划生成中的平均记忆使用率
- 哪些文档类型最常被模型引用
- 哪些题目最常成为计划依据
- 哪些文档经常被检索但没有被使用
- problem_bank 这类背景知识和 record / review 这类个人历史证据的区别

目标是分析 RAG 文档价值和模型实际使用率，为后续优化 RAG 文档构建和 Prompt 使用历史上下文提供依据。
## v2.3.2 RAG 个性化记忆权重优化

LeetCoach 从“RAG 是否被使用”继续推进到“RAG 是否优先使用用户个人学习资产”。

本阶段重点：

- 降低 `problem_bank` 这类通用背景信息在计划生成中的主导性
- 提高 `records`、`reviews`、`problem_notes`、`ai_solution_notes`、`stage_summary`、`agent_memory` 等个人历史文档的优先级
- AI 计划生成的 RAG 上下文分为“用户个性化学习记忆”和“题库背景信息”
- RAG trace 和统计报告会分别展示个性化证据与背景证据的检索数、使用数和使用率

目标是让 RAG 更像“基于用户真实学习资产的记忆系统”，而不是单纯把题库资料塞进 Prompt。

## v2.3.3 RAG 个性化文档质量诊断

LeetCoach 从“优先使用个性化记忆”继续推进到“判断个性化记忆本身是否高质量”。

本阶段新增个性化 RAG 文档质量诊断，用于检查记录、复习、笔记、AI 题解、阶段总结和 Agent 记忆是否包含足够的用户行为、错因、掌握度、专题信息和可引用事实。

如果文档质量较低，系统会用规则生成短版增强记忆，保存为独立 JSON 文件，供后续 RAG 文档构建优化参考。

本阶段不替换现有 RAG，不自动应用计划，也不调用大模型重写记忆。目标是让 RAG 的“记忆来源”本身变得可诊断、可改进。

## v2.3.4 增强版个性化记忆 RAG A/B 实验

LeetCoach 从“诊断并生成增强记忆”进入“验证增强记忆是否真的提升 RAG 效果”的实验阶段。

本阶段比较普通 RAG 与“普通 RAG + enhanced personalized memory”两种模式，观察：

- AI 计划质量评分是否提升
- fallback 是否减少
- 个性化证据使用率是否提升
- enhanced memory 是否真的被计划引用
- problem_bank 背景证据占比是否下降

实验只用于分析，不会自动应用任何计划，也不会修改默认 RAG 策略。目标是用实验数据判断增强记忆是否值得进入后续默认 RAG 设计。

## v2.9 Local Model Lab / 本地模型实验室

LeetCoach 从云端模型实验继续推进到本地模型实验。

本阶段重点不是替换现有云端 LLM，而是建立一个安全、可回退、可观察的本地模型测试层：

- 本地模型默认关闭，不影响现有产品主流程
- 支持检查 Ollama 或 OpenAI-compatible 本地服务
- 支持测试本地 Embedding 向量生成
- 支持比较本地 Embedding 与云端 Embedding 的检索排序差异
- 测试结果保存到 `data/local_model_test_logs.json`

这一步为后续学习本地 Embedding、低成本 RAG、模型速度对比和本地推理能力评估打基础。

## v2.9.1 Local Embedding RAG A/B 实验

LeetCoach 从“本地模型能否调用”继续推进到“本地 Embedding 是否适合 LeetCoach RAG”。

本阶段比较同一批 RAG 候选文档下，云端 Embedding 与本地 Embedding 的检索排序差异：

- Top1 是否一致
- Top3 / Top5 overlap
- 平均相似度
- 云端与本地延迟
- 多次实验成功率

该实验只用于观察和建议，不会自动修改默认 Embedding 策略，也不会替换正式 RAG 流程。

## v2.4 Agent 决策日志与行动选择

LeetCoach 从 RAG 实验阶段转入 Agent 决策系统建设。

本阶段重点不是让 Agent 多说话，而是让后台判断变得可观察、可解释、可调试。

核心链路：

- Observation：收集当前计划、复习、同步、失败记录和薄弱点
- State：判断当前处于 normal、review_due、plan_completed、behind_schedule 等状态
- Decision：选择 wait、continue_current_plan、generate_next_plan_draft 等决策
- Action：执行最小必要动作，例如生成待确认计划草案或不动作
- Reason：记录为什么这么判断
- Confidence：记录规则判断置信度
- User Confirmation：需要用户确认的动作不自动应用

目标是让 LeetCoach 的 Agent 从“后台脚本”升级为可观察、可解释、可复盘的学习管家决策系统，同时继续避免噪声和自动越权。
## v2.6 Human-in-the-loop Pending Actions

LeetCoach Agent 从 Tool Registry 继续进入 Human-in-the-loop 工作流。

本阶段重点是让“需要用户确认的动作”成为正式数据对象，而不是只停留在 `requires_confirmation` 标记上。

核心学习点：

- Pending Actions：Agent 可以创建待确认动作，但不直接执行高风险操作。
- 用户确认机制：用户可以确认、暂缓或拒绝。
- 高风险工具安全边界：例如应用计划草案，必须由用户确认后才执行。
- 用户反馈记录：确认、拒绝和暂缓都会写入本地 JSON，供后续 Agent 分析。
- Agent 不自动越权：Agent 负责观察、建议、记录，最终控制权仍在用户手里。

本阶段仍不改变同步、题库和普通学习主流程，也不让 Pending Actions 出现在今天页制造噪声。

## v2.5 Agent Tool Registry 与工具调用编排

LeetCoach Agent 从“规则决策器”继续升级为可解释的工具调用系统。

本阶段重点不是让 Agent 多做事，而是让每个可执行动作都有清晰边界：

- Tool Registry：所有 Agent 工具集中登记，包含名称、用途、风险等级、输入输出说明。
- Tool Schema：每个工具都有最小输入输出结构，避免 action 字符串散落在业务代码里。
- Tool Execution：Agent policy 输出 action 后，先映射到工具，再由执行器统一处理。
- Tool Call Logs：每次工具调用写入 `data/agent_tool_call_logs.json`，便于回放和调试。
- Human-in-the-loop safety：高风险工具，例如应用计划草案，只能进入待确认状态，不允许 Agent 自动执行。

当前原则保持不变：

- 不自动应用计划
- 不改变同步主流程
- 不改变题库主流程
- 不让 Agent 变成聊天机器人
- 需要用户确认的动作，最终控制权仍在用户手里
## v2.8.1 Agent Policy Benchmark

LeetCoach 从单次 Rule vs LLM 对比进入多场景 Agent Policy Benchmark。

本阶段重点学习：

- Agent scenario design
- policy evaluation
- tool safety validation
- rule-based Agent 与 LLM-based Agent 的系统性对比
- 如何发现 LLM 在哪些状态下容易越权或分歧

Benchmark 不会执行任何工具，不会修改正式计划，不会替换规则 Agent。
它只用于评估 LLM Tool Selector 在固定学习状态集合中的安全性、一致性和合理性。

## v2.8 LLM-driven Tool Selection Sandbox

LeetCoach 从 v2.8 开始进入 LLM Agent 工具选择实验阶段。

正式执行策略仍然由 rule-based `silent_agent` 控制；LLM Tool Selector 只在沙盒中运行，用于学习和比较：

- Tool schema 如何设计
- LLM 如何根据 observation 选择工具
- 用户反馈记忆如何影响工具选择
- Rule Policy 与 LLM Policy 是否一致
- LLM 推荐是否安全、是否需要人工确认

本阶段不会让 LLM 自动执行工具，也不会自动应用计划。
LLM 的建议必须经过 `llm_tool_selection_validator.py` 校验，并通过 `agent_policy_compare.py` 与规则 Agent 对比后记录。

## v2.7 User Feedback Memory / 用户反馈记忆系统

LeetCoach 从 v2.7 开始把 Human-in-the-loop 的确认、暂缓和拒绝反馈沉淀为长期偏好记忆。

目标不是让 Agent 更频繁地输出建议，而是让 Agent 学会：

- 用户是否倾向确认 Agent 建议
- 用户是否经常暂缓计划切换
- 用户是否经常拒绝某类动作
- 后续计划生成是否应该更保守
- 后台 Agent 是否应该降低主动性

偏好记忆保存到 `data/user_learning_profile.json`，由 `agent_feedback_memory.py` 生成。
该记忆会被 Agent Policy 和 AI 计划生成上下文引用，但不会自动应用任何计划。
## v3.0 本地模型实验阶段收尾

LeetCoach 本地部署阶段的目标不是强行替换云端模型，而是学习本地模型调用、fallback 策略和效果评估。

当前阶段已经完成：

- 本地 Embedding 调用实验
- Ollama `nomic-embed-text` 接入
- 云端 / 本地 Embedding RAG 对比
- 本地 Embedding fallback 策略评估
- 本地 LLM 解题能力初步观察

当前取舍：

- 本地 Embedding 可以作为云端 Embedding 失败时的 fallback。
- 本地 LLM 暂不进入 AI 解题或 AI 计划主流程。
- 正式 AI 解题和 AI 计划生成仍继续使用云端模型。
- 后续除非本地模型质量、速度和结构化输出稳定性明显提升，否则不继续扩展本地 LLM 主流程接入。

本阶段完成后，LeetCoach 将停止继续扩展本地模型实验功能，转入项目整理、展示和阶段总结。

## GitHub 公开发布取舍

LeetCoach 公开展示版本优先呈现稳定产品能力，而不是把所有实验入口暴露给普通用户。

当前取舍：

- GUI 默认隐藏 LLM Lab、PromptOps、RAG 实验、Agent Benchmark 和本地模型实验入口。
- 实验代码和历史能力保留在项目中，供开发者继续学习大模型应用工程。
- 公开 README 聚焦产品定位、快速启动、隐私说明和开发者模式。
- 真实个人配置、学习记录、同步日志、LLM/RAG/Agent 实验日志不建议提交到公开仓库。
- 如需继续实验，可在 `config/app_settings.json` 中开启 `developer_mode` 或 `show_llm_lab`。

这个阶段的目标不是删除实验能力，而是把 LeetCoach 从“内部研究项目”整理成“可以公开展示、可以继续开发、不会泄露隐私”的版本。
