

只填写修订中真实发生的文学判断，不得猜测 schema、路径、SHA-256、会话或受保护标准；这些字段由 Studio 在提交前绑定。

- `revision_actions_applied`、`warnings_addressed`、`style_notes_addressed`、`style_adherence_addressed` 分别记录已实际落实到正文的审查项；四组中至少一组非空。
- 不适用的组写空数组；无法落实的项目写入 `waivers`，不能谎报为已完成。
- `evasion_risks_unresolved` 必须为空才能进入复审；若仍有风险，保留具体条目并让任务继续阻塞。
- `anti_evasion_rows` 每项必须使用以下形状，两个 excerpt 都必须逐字存在于精确源正文或修订候选正文：

```json
[[ARCVELLUM_PROMPT_0]]
```

- 源正文存在机械对照或换皮转折风险时，`anti_evasion_rows` 不得为空；确实不存在时才填写具体的 `anti_evasion_not_applicable_reason`。
- 保留显式转折时使用 `verdict=retained_with_proof`，并在 `retained_transition_proofs` 中给出经批判性反驳仍成立的场景功能证据。
- `new_character_register` 必须基于修订正文实际出现的人物填写；不得因 Studio 会补机器字段而省略文学判断。
