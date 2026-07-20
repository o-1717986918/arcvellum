# Phase 80：Style Lint 分级硬门禁

## 目标

把 Style Lint 从 AgentReview prompt 里的证据块升级为正式机器门禁，防止平台 Agent 或审查 JSON 把机械对照句式、medium+ AI 腔风险误判为 clean pass。

## 分级策略

- `mechanical-contrast-frame`：始终 blocking。包括“不是……而是……”“不是……——是……”“不是……。是……”等变体。
- `severity=medium` 或更高：blocking。用于破折号密度、器官轮岗、万能占位、比喻依赖、抽象总结等模式性失控。
- `severity=low`：notes-only。允许平台 Agent 语义复核后保留，但应写入 AgentReview notes 或保留理由。

## 实现

- `anti_ai_style.py` 新增 `style_lint_gate()`、`is_style_lint_blocking()`、`style_lint_gate_message()`。
- `candidate_promotion.py` 在 promotion 前重跑候选正文 Style Lint Gate，并把 gate 写入 promotion manifest；blocking 时抛出 `FlowGateError`。
- `agent_task_status.py` 的 `route-audit --route scene-development` 新增 `{scene_id}:style-lint-clean` gate。
- `scene_readiness.py` 在 chapter/export readiness 里对 cleaned deliverable body 再跑 Style Lint Gate，blocking 时退回 `needs_revision`。

## 边界

- 低风险命中不阻塞，避免把孤立表达误杀成流程故障。
- gate 只阻塞，不自动改稿；正文修订仍由主平台 Agent 逐句完成。
- debug/waiver flags 仍只保留给维护者回归测试，正式 Skill host 不得用它们绕过本门禁。
