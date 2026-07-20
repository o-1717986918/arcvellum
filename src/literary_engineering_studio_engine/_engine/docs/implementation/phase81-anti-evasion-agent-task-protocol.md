# Phase 81：反规避修订协议与生成任务程序强化

本阶段解决两个实际使用中暴露的问题：

1. 审查发现“不是……而是……”后，修订可能把它换成“并不是……只是……”“看似……其实……”等同功能转折，看起来绕过了原规则，实质仍是机械对照。
2. 正文生成虽然已有 prompt manifest 和 `.agent_tasks.md`，但反规避规则没有以统一程序进入生成、审查、修订和 route audit。

## 决策

正式 `generate-scene` 继续保持项目型 Skill 架构：CLI 只生成 prompt manifest 和平台 Agent task sidecar，不直接调用本地 provider 写正文。真正创作由加载 Skill 的主平台 Agent 完成。

反规避不是“禁止一切转折”。它只阻止模型用另一种显式对照模板替代原有问题。真实的信息反转、人物误判、因果揭示、视角校正或讽刺顿挫，应优先通过动作、事实顺序、信息差、物证、对话错位或人物选择完成。

## 实现

- `anti_ai_style.py` 新增 `ANTI_EVASION_REVISION_PROTOCOL`、`ANTI_EVASION_SHORT_RULE` 和 `contrast-evasion-frame`。
- `style_lint_gate()` 将 `contrast-evasion-frame` 与 `mechanical-contrast-frame` 一样视为 blocking。
- `prompt_pack.py` 在 `generation_standards` 中写入 `anti_evasion`，并把换皮转折禁区纳入生成前硬约束。
- `platform_agent_tasks.py` 强化 `write_platform_scene_generation_task()` 和 `write_platform_scene_review_task()`：生成任务必须读取反规避标准，审查任务必须写反规避负担证明。
- `scene_revision.py` 在修订 prompt manifest 中加入修订前 Style Lint 证据和反规避协议；修订任务要求输出反规避表、保留转折负担证明和 `anti_evasion_protocol_applied=true` manifest 字段。
- `candidate_promotion.py` 支持从 `## 修订正文候选` 提取候选正文，允许正式修订候选进入同一 promotion gate。
- `agent_task_status.py` 的 `route-audit --route scene-development` 新增静态 `review-scene` clean pass gate，并在修订候选参与时要求 `revision-evasion-clean`。
- `scene_review.v1` schema 增加推荐字段 `revision_integrity`，用于记录 anti-evasion 检查。

## 边界

- 不用脚本批量改写语义。确定性 lint 只做检测和门禁，正文修订仍由主平台 Agent 逐句完成。
- 不禁止正常转折词。只有形成机械对照或换皮对照结构时 blocking；孤立低风险词仍按语义复核处理。
- 不让 subagent 写正文。subagent 可以列证据、列风险、做连续性表或字数表；修订正文由主平台 Agent 完成。

## 回归点

- “不是 C 营的——是那个 E 营的年轻人”必须触发 `mechanical-contrast-frame`。
- “看似 C 营的人，其实是那个 E 营的年轻人”必须触发 `contrast-evasion-frame`。
- “他袖章上是 E 营。先前那件 C 营雨衣，是别人丢下的。”不应因同一反规避规则阻塞。
- 修订候选 `## 修订正文候选` 可以进入 `promote-candidate`。
- `route-audit` 能发现缺失静态 review 和缺失反规避修订 manifest。
