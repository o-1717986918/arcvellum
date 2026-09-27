

这不是可选记录，初始化的 `pending_agent_judgment` 不能原样提交。完成判断后必须设为 `status=complete`。

- 顶层 `evidence_paths` 是证据文件路径列表；存在变化时必须包含已晋升正文路径。
- `reader_question_changes` 和 `promise_changes` 的每一条变化都必须另写非空字符串字段 `evidence`，填写来自本场正文的具体事实、原句或可核验概述。条目内部的 `evidence_paths` 不能替代 `evidence`。
- 每条开放中的读者问题必须有 `target_window`、`target_scene` 或 `responsibility`；每条开放中的承诺必须有 `due_window`、`due_scene`、`target_scene` 或 `responsibility`。
- 确实没有任何账本变化时：两个 changes 列表保持空数组，并写出具体的 `no_change_reason`，说明正文为什么没有产生新的读者责任。
- `source_draft_sha256` 与 `writer_session_id` 由 Studio 绑定到本次任务；不要编造或以 completion receipt 代替正文判断。
- 只编辑 delta，不要编辑 `plot/reader_questions/ledger.json` 或 `plot/promises/ledger.json`。
