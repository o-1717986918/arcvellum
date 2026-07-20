# Phase 5：角色推演实验室

命令：`simulate-scene`

读取人物 BDI、恐惧、秘密、道德边界和语言习惯，输出角色行动提案、世界后果、导演评分和 canon 审查提示。

`--agent` / `--agent-tasks` 会把空白工作区改成 `[AGENT_TASK: ...]` 指令，供装载 Skill 的平台 agent 补全。默认不启用，旧输出保持不变。

`v0.67.0` 起，`--agent` 模式会先生成“平台 Agent 执行门禁”：

- 平台 agent 必须先读取 scene、context packet、context trace、正式人物档案和可用 canon/outline/foreshadowing 文件。
- 平台 agent 必须在“读取回执”中列出已读文件、缺失文件、不可突破硬约束和写回边界。
- 缺少关键资料时，仍可提出候选推演，但必须标注依据不足，不得把候选当作 canon。
- RP 输出仍是工作笔记，不是正文；推荐分支必须再经平台 agent 和用户/审批链确认。
