# Phase 38：Agent 角色创作命令

本阶段新增角色相关候选生成命令，统一由 `asset_workshop.py` 调度 `agent_provider.py`。

## 新增命令

- `agent-create-character`
- `agent-create-background-story`
- `agent-create-relationship`

## 输出

候选 JSON 和 Markdown 报告写入：

```text
characters/candidates/
characters/candidates/background_stories/
plot/candidates/relationships/
```

角色背景故事只作为隐性行为因果，影响选择、回避、误判、语气和关系压力，不应在正文中被整段说明。
