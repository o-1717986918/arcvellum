# 剧情与场景引擎

场景是工程单元，必须说明：

- 场景目标
- 冲突和阻碍
- 出场人物
- 输入 canon
- 输出变化
- 伏笔和后续债务

场景推演可以产生多条分支。使用 `branch-simulate` 生成结构化分支候选、五维评分和人工选择记录，但分支进入正稿前必须经过人物合理性、世界观一致性和剧情推进价值评估。

平台 agent 必须先在 `branch_selection.md` 中记录正式分支选择，再使用 `compose-scene` 生成场景创作编排包。该产物把场景目标、人物 BDI、背景故事隐性动因、分支行动链和风格约束整理为节拍、潜台词、对白意图、感官意象和正文种子。`compose-scene` 不是正稿生成器，输出仍需进入 `generate-scene`、主 Agent 亲自写正文、`review-scene` 和 canon 审查链路。推荐分支只是启发式提示，默认不能进入 composition；正式 Skill 宿主不得使用放行参数跳过分支门禁。

`generate-scene` 使用 prompt pack 写入平台 Agent 任务 sidecar，不调用本地 provider、`dry-run`、`http-chat` 或外部 agent。平台 Agent 读取 `.prompt.json`、场景、context packet、context trace 和 composition 后，写入 `drafts/candidates/{scene_id}-platform-agent.md` 与对应 manifest。候选 manifest 必须包含 `new_character_register`：一次性路人写豁免理由，持久新角色走 `characters/candidates/`、资产审查和 approval/promotion。候选进入正稿前仍需 `review-scene`、平台 Agent 场景审查、canon 审查和审批链路。
