# Phase 55: Creative Director Conversation Memory

本阶段补齐创作总监的多轮对话上下文能力。

此前创作总监会读取项目状态、最近工作流和最近总监运行记录，但用户与创作总监之间的自然对话并没有作为独立短期记忆持续维护。因此，当用户说“继续”“按刚才方向”时，真实 LLM 只能间接依赖项目状态推断，稳定性不足。

## 新增能力

- 每轮 `director-chat` 完成后写入 `director/conversation/turns.jsonl`。
- `build_director_status()` 新增 `recent_conversation`，默认读取最近若干轮对话。
- `director_user.md` 会把 `recent_conversation` 注入创作总监提示词。
- 当用户说“继续”“按刚才的方向”或引用前文选择时，创作总监应优先从 `recent_conversation` 中恢复偏好、未决问题和创作方向。

## 记录内容

每条对话记忆记录包含：

- `run_id`
- `created_at`
- `user_direction`
- `assistant_headline`
- `assistant_reply`
- `intent`
- `chosen_workflow`
- `status`
- `visible_choices`
- `tool_plan`
- `artifacts`

记录会被截断到适合提示词注入的长度，避免把完整内部报告、过长正文或敏感配置反复塞回模型上下文。

## 与项目状态的关系

`recent_conversation` 是短期对话记忆，负责保留用户刚刚表达的偏好、方向和选择。

项目文件、候选资产、canon、角色状态和 workflow 记录仍是长期事实来源。创作总监可以用对话记忆理解“刚才”指什么，但不能把对话中的设想直接当作 canon；新增设定仍要经过候选、审查和晋升链路。

## 测试

新增回归覆盖：

- 连续两轮 `director-chat` 会写入两条对话记忆。
- 第二轮提示词包含第一轮用户偏好，例如“冷静克制”。
- `/director/status` 会返回 `recent_conversation`。

全量测试：`118 tests OK`。
