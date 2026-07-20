# Phase 79：AgentReview 确定性 Style Lint 证据注入

## 目标

修复场景审查中过度依赖 LLM 语义直觉的问题。平台 Agent 做文学判断前，先把 `anti_ai_style.py` 的确定性 lint 结果注入审查任务，尤其拦截“不是 A——是 B”“不是 A。是 B”“不是 A，是 B”等机械对照变体。

## 实现

- `anti_ai_style.py` 新增 `render_ai_style_lint_block()`，统一输出 `Style Lint (auto-detected)` 证据块。
- `platform_agent_tasks.write_platform_scene_review_task()` 在正式 `.agent_tasks.md` 中加入 lint 证据，要求审查 JSON/Markdown 明确处理 medium 及以上风险。
- `agent_scene_review.review_scene_with_agent()` 在旧兼容 provider prompt 中注入同一 lint 证据。
- dry-run 审查遇到确定性 medium 风险时输出 `revise_required`、warnings 和 revision_actions，避免把干跑契约误当成质量审查通过。

## 边界

- lint 只提供证据，不自动改稿。
- 禁止用正则批量删除“不是”、破折号或心理表达；正文语义修订必须由主平台 Agent 逐句判断。
- 低风险命中允许平台 Agent 保留，但必须在报告中说明语义理由。
