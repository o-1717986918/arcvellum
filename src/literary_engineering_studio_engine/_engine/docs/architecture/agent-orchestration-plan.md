# Agent 编排实现计划

当前能力：

- `run-workflow`：文件 backed 节点式 runner。
- `run-langgraph`：真实 LangGraph `StateGraph`，当前图为 `START -> scene_loop -> chapter_publish -> END`。
- `serve-api`：Dify 和外部工作流可调用的 HTTP 后端。

推荐分层：

```text
Dify / Reviewer UI
  -> FastAPI serve-api
  -> LangGraph run-langgraph
  -> File-backed workflow runner
  -> Work project files
```

人工确认节点负责 canon 写回、重大剧情转折、分支合并和正式导出。
