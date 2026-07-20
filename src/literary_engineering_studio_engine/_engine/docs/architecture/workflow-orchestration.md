# 工作流编排

MVP 使用 Python CLI + 文件产物。Phase 10 加入 `run-workflow`，Phase 11 加入 `run-langgraph` 和 `serve-api`。

核心链路：

```text
任务输入
  -> 读取项目状态
  -> 检索记忆
  -> 构建上下文包
  -> 角色推演
  -> 草稿工作台
  -> 审查 CI
  -> 章节工作台
  -> 长篇审计
  -> 多格式导出
  -> 人工确认
```

Dify 只作为前台展示和决策收集，不直接修改 canon。LangGraph 包装同一套 runner 节点，不另建一套业务逻辑。
