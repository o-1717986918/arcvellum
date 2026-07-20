# Phase 7：章节级流水线

命令：`chapter-workspace`

扫描章节场景、读取 context / simulation / branch / composition / draft / review 产物，输出章节 Markdown 和 `plot/chapters/{chapter_id}.json`。

`v0.73.0` 起，章节 ready 改为强门禁：

- 必须存在 context packet 和相邻 context trace。
- 必须存在带平台 Agent 读取回执且无未处理 `[AGENT_TASK: ...]` 的 roleplay simulation。
- 必须存在 branch manifest、正式 `branch_selection.md` 和 ready composition。
- 静态 review 必须是 clean `pass`。
- 平台 AgentReview 必须满足 `scene_review.v1`、clean `conclusion=pass`、引用当前 `drafts/scenes/{scene_id}.md`，且没有 warnings / revision_actions / style_notes / style_adherence 偏差。
- `pass_with_notes` 不再进入 ready，而是 `needs_revision`。
