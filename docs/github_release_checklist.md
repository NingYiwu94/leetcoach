# GitHub 发布前检查清单

发布 LeetCoach 公开版本前，请逐项确认：

- [ ] `.env` 没有被提交
- [ ] API Key / Token / 密码没有被提交
- [ ] 真实力扣用户名没有被提交
- [ ] `config/leetcode_config.json` 没有被提交
- [ ] `config/local_model_config.json` 没有被提交
- [ ] `config/app_settings.json` 没有被提交
- [ ] 真实 `records.json` / `reviews.json` / `problem_notes.json` / `ai_solution_notes.json` 没有被提交，或已脱敏
- [ ] LLM / RAG / Agent / 本地模型实验日志没有被提交
- [ ] LLM Lab 默认隐藏
- [ ] `config/*.example.json` 示例配置存在
- [ ] `examples/` 示例数据存在
- [ ] README 是公开用户能读懂的版本
- [ ] `python coach_app.py` 可以启动
- [ ] `python -m tools.data_validator` 可以运行
- [ ] `git status` 已检查

建议发布前命令：

```bash
git status
python -m tools.data_validator
python coach_app.py
```

如发现敏感文件已经被 Git 跟踪，请使用：

```bash
git rm --cached <file>
```

这只会从 Git 跟踪中移除文件，不会删除本地文件。
