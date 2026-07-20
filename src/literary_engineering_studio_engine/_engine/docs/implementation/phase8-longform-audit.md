# Phase 8：中长篇扩展

命令：`longform-audit`

输出 `reviews/longform/longform_audit.md`、`reviews/longform/longform_audit.json` 和 `plot/longform_graph.json`。

`v0.65.0` 起，审计会读取 `plot/word_budget/word_budget.json`。如果中长篇目标缺少预算、预算状态为 `needs_expansion`，或现有场景库存明显不足，报告会增加 `word_budget` / `scene_inventory` 风险。

`v0.67.0` 起，正文字符数只统计清洗后的可交付正文，不把草稿工作流、状态变化、写回候选、scene 编号、canon 说明或 prompt manifest 算入目标字数进度。
