# Phase 45：设定创作 Demo 与回归

本阶段把 Agent 设定创作层纳入 demo 和回归测试。

## Demo

`demo-project` 现在会生成世界观、角色和大纲候选资产，并在 `reviews/agent/demo_walkthrough.md` 中列出。

## 测试

新增 `tests/test_asset_workshop.py`，覆盖：

- 候选资产生成
- 候选审查
- 候选列表
- 无审批禁止晋升
- 内部晋升
- `project-seeding` workflow
- CLI 命令暴露

API 测试也覆盖 `/asset/*` 端点。
