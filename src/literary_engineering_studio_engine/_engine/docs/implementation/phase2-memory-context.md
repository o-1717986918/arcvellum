# Phase 2：记忆索引和上下文包

命令：

- `index`
- `search`
- `context`

当前实现使用标准库轻量索引 `memory/index.json`、场景上下文包 `memory/context_packets/{scene_id}.md` 和来源证明 `memory/context_packets/{scene_id}.trace.json`。`v0.86.0` 起，正式场景链路要求 packet 与 trace 同时存在。
