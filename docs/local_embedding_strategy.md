# LeetCoach 本地 Embedding 策略说明

## 当前本地模型

当前本地 Embedding 实验模型：

```text
nomic-embed-text
```

运行方式基于 Ollama：

```text
POST http://localhost:11434/api/embed
```

## 当前用途

本地 Embedding 当前只用于 RAG 实验和策略评估，不是默认正式策略。

LeetCoach 不会因为本地模型可用就自动替换云端 Embedding。

## 如何启用

配置文件：

```text
config/local_model_config.json
```

关键字段：

```json
{
  "local_embedding": {
    "enabled": true,
    "provider": "ollama",
    "base_url": "http://localhost:11434",
    "model": "nomic-embed-text",
    "api_type": "ollama",
    "timeout_seconds": 120
  }
}
```

## 当前评估指标

LeetCoach 使用以下指标评估本地 Embedding 是否适合作为正式策略：

- 本地 Embedding 成功率
- 云端 Embedding 成功率
- 本地平均耗时
- 云端平均耗时
- Top1 一致率
- Top3 overlap
- Top5 overlap

## 当前推荐策略

当前推荐策略来自命令：

```bash
python local_embedding_rag_report.py
```

报告会输出：

- `recommended_strategy`
- `recommendation_reason`
- `confidence`
- 行动建议

可能策略包括：

- `keep_cloud_default`
- `use_local_default`
- `use_local_fallback`
- `insufficient_data`
- `continue_observing`

## 注意事项

不建议仅凭一次实验切换默认 Embedding。

推荐至少累计 5 次以上实验，并观察不同专题查询下的成功率、延迟和 Top-K overlap 后，再决定是否调整默认策略。
## v2.9.4 当前实验结论

最近一轮本地 / 云端 Embedding RAG 对比实验结论：

- 本地 Embedding 成功率较高，稳定性好于当前云端连接。
- 云端 Embedding 速度更快，但连接波动明显。
- 本地与云端 Top-K 排序差异仍然明显，Top1 一致率较低。
- 当前推荐策略：`use_local_fallback`。
- 不建议直接使用 `use_local_default`。

当前正式策略：

```text
云端 Embedding 优先。
云端 Embedding 失败时，如果 config/local_model_config.json 中
cloud_embedding_fallback_to_local=true，则尝试本地 Ollama Embedding。
```

这个策略只作为可靠性兜底，不会自动修改 `.env`，也不会把本地 Embedding 切换为默认。
