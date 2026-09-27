

`proposals` 必须保留并完成 [[ARCVELLUM_PROMPT_0]]场景特定提案。下面是唯一权威的单条机械形状；复制形状可以，复制占位内容不可以：

```json
[[ARCVELLUM_PROMPT_1]]
```

- 不得把字段改名为 `id`、`rationale`、`irreversible_cost`、`next_scene_pressure` 或其他近义词。
- `state_writeback` 保留 `new_facts`、`character_changes`、`relationship_changes`、`foreshadowing_changes`、`next_scene_inputs` 五个字符串列表；至少一个列表必须有具体变化。
- 每条提案通常使用模板中的 2 个 beat；只有因果转向无法在两拍中清楚表达时才增加第 3 拍，不要为了显得完整而扩写。每拍填写全部字段，`serves` 必须是义务名称列表且可以同时承担多项义务。
- 每条提案的全部 beat 合计覆盖 `incoming_bridge`、`goal`、`turn`、`cost`、`reader_effect`、`outgoing_hook`。
- 顶层设置 `status=complete`，`evidence_paths` 与 `findings` 非空；所有 `<replace: ...>` 和 `agent_branch_replace_*` 占位值必须被替换。
- 同时完成任务声明的 `branch_selection.md`，其中 `selected_branch` 必须精确引用本文件的一条 `branch_id`；不要自行创建 completion receipt。
