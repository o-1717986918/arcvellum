# Phase 66：流程阅读回执、Review Notes 小修闭环与生成硬约束摘要

本阶段强化三个容易漏流程的点：

- Agent 执行任务前必须按 route 读取文档并留下 reading receipt。
- `pass_with_notes` 不能被当作静默通过，必须进入小修闭环。
- 场景生成前把 canon、人物、文风、预算、review notes、标点和输出边界压缩成强约束摘要，提高草稿/候选正文质量。

## Reading Receipt

`references/agent-run-protocol.md`、`references/cli-run-protocol.md`、`AGENTS.md` 和 `.agent_tasks.md` 现在都要求记录：

- selected route
- references read
- project files inspected
- missing context
- pending sidecars

这能降低平台 agent 漏读 route 文档、直接执行命令或跳过审查的概率。

## pass_with_notes 小修闭环

`pass_with_notes` 现在表示“无阻塞，但有必须处理的局部 notes”，不是完全通过。

要求：

- Agent Review JSON 的 `revision_actions` / `warnings` / `style_notes` 必须具体可执行。
- `agent-review-scene` 任务要求 `pass_with_notes` 写明局部小修动作和下一门禁。
- 下一轮 `generate-scene` 会读取 `reviews/agent/{scene_id}_scene_review.json`。
- Prompt manifest 注入 `generation_standards.review_notes`。
- Writing agent 必须执行小修，或在“需要人工确认”中逐条说明豁免原因。

## 生成前最终硬约束摘要

`prompt_pack.py` 新增 `generation_standards.hard_constraints`，并在 user prompt 中追加“生成前最终硬约束摘要”。

执行顺序：

1. Canon / 用户明确约束。
2. 场景目标与 composition。
3. 人物 BDI、信息差、关系压力和 hidden background_story。
4. 已挂载 Style Skill / style profile。
5. 长篇字数预算。
6. AgentReview notes。
7. 标点规范与 AI 腔降低。
8. 输出边界：只写候选正文和状态变化候选，不输出工作流痕迹。

这些约束用于提升生成质量，不能作为自检表、分析过程或工作流痕迹输出到正文候选。

## 变更文件

- `src/literary_engineering_workbench/prompt_pack.py`
- `src/literary_engineering_workbench/agent_tasks.py`
- `src/literary_engineering_workbench/platform_agent_tasks.py`
- `src/literary_engineering_workbench/generation_provider.py`
- `src/literary_engineering_workbench/review_ci.py`
- `references/agent-run-protocol.md`
- `references/cli-run-protocol.md`
- `references/workflows.md`
- `references/artifact-contracts.md`
- `docs/modules/review-ci.md`

## 完成标准

- `.agent_tasks.md` 默认包含 reading receipt 规则。
- Prompt manifest 包含 `review_notes_loaded`、`review_notes_path` 和 `hard_constraints`。
- `pass_with_notes` review 会进入下一轮生成 prompt。
- 回归测试覆盖 `pass_with_notes` 注入和硬约束摘要。
