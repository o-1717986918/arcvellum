# Phase 4：单场景生成闭环

命令：

- `draft-scene`
- `review-scene`

草稿工作台先稳定结构，审查 CI 输出 `pass`、`pass_with_notes`、`revise_required` 或 `reject`。

`v0.66.0` 起，`draft-scene` 生成的草稿工作台包含“生成前硬约束摘要”，把 canon、场景目标、人物 BDI、背景故事隐性因果、文风、长篇预算、pass_with_notes notes、标点和输出边界前置到写作指令中。

`pass_with_notes` 不再视为静默通过。后续 writing agent 必须处理 notes，或记录明确接受/豁免理由。
