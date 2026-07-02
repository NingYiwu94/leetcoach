# LeetCoach 项目结构

LeetCoach 公开版本采用“入口文件 + src 源码 + resources 资源”的结构，减少 GitHub 根目录噪声。

## 根目录入口

| 路径 | 说明 |
| --- | --- |
| `coach_app.py` | GUI 推荐入口 |
| `main.py` | 备用命令行入口 |
| `README.md` | GitHub 展示说明 |

## 核心源码

| 目录 | 说明 |
| --- | --- |
| `src/app/` | Tkinter 主界面、今日任务面板、首页数据 |
| `src/core/` | 刷题记录、复习调度、学习分析、阶段总结 |
| `src/planning/` | 周计划、阶段推进、计划状态和计划自动化 |
| `src/library/` | 题库能力地图、题目笔记和题目详情资产 |
| `src/ai/` | AI 解题、AI 计划、AI 周总结和 AI 任务队列 |
| `src/llm/` | LLM 客户端、调用日志、输出校验、Prompt 加载和 Embedding |
| `src/sync/` | 力扣同步、本地同步服务和 Chrome 扩展辅助逻辑 |
| `src/agent/` | 静默 Agent、工具注册、决策日志和 human-in-the-loop 动作 |
| `src/rag/` | RAG 检索、证据链追踪、RAG 评估和增强记忆实验 |
| `src/labs/` | PromptOps、RAG A/B、本地模型、工具选择等实验入口 |
| `src/tools/` | 数据校验等维护工具 |

## 资源与配置

| 目录 | 说明 |
| --- | --- |
| `resources/assets/` | 图标等静态资源 |
| `resources/prompts/` | Prompt 模板 |
| `resources/schemas/` | 结构化输出说明 |
| `extensions/chrome/` | 力扣同步 Chrome 扩展 |
| `config/` | 示例配置、专题配置和默认计划 |
| `data/` | 公开基础题库；真实个人运行数据不提交 |
| `docs/` | 产品说明、发布检查、实验总结和路线文档 |
| `examples/` | 脱敏示例数据 |
| `tests/` | 自动化测试 |

## 常用命令

```bash
python coach_app.py
python main.py
```

开发者维护命令：

```powershell
$env:PYTHONPATH="src"
python -m tools.data_validator
python -m unittest discover -s tests
```

开发者实验入口默认隐藏。如需打开 LLM Lab，请配置 `config/app_settings.json`。
