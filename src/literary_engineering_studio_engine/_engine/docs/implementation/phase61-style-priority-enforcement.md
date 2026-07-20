# Phase 61: Style Priority Enforcement

本阶段把文风从“可选 profile”提升为创作链路中的最高优先级表达约束。

`prompt_pack.py` 现在优先读取：

```text
style/active_style_skill.json
style/mounted/{style_id}/prompt.md
```

如果存在挂载文风，场景生成 prompt 会注入“已挂载文风 Style Skill（最高优先级）”块。

Prompt manifest 同时注入 `generation_standards.style`，把文风从审查标准前移到生成标准。生成正文前必须先把文风约束转译为本场景的叙述距离、句法节奏、意象系统、心理呈现、对白密度和标点停顿策略，再开始写正文候选。

优先级边界：

- 文风优先约束表达层：叙述距离、句法节奏、意象系统、感官平衡、对白密度、心理呈现。
- 文风不覆盖 canon、人物事实、剧情因果、安全边界或用户明确约束。
- 冲突时保留事实约束，并写入“需要人工确认”。

`director_agent.py` 也会在项目状态中读取 `active_style_skill`，让创作总监在路由和工具循环阶段就能看到文风约束。
