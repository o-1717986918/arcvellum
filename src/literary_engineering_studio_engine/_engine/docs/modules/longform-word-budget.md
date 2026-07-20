# Longform Word Budget Module

本模块解决长篇生成中常见的“目标 50 万字，实际一卷只有 2 万字”问题。核心判断是：字数不是靠要求场景更啰嗦来完成，而是靠足够的剧情库存、关系压力、信息推进、后果链和场景数量支撑。

## 适用场景

- 用户要求中长篇、50 万字、百万字、多卷、多季、多篇章。
- 大纲只有少量事件，却要求极长正文。
- 章节或场景生成明显压缩成摘要。
- `longform-audit` 发现正文规模与目标差距过大。

## 标准链路

1. 选择 `longform-planning` route。
2. 读取 `references/agent-run-protocol.md`、`references/cli-run-protocol.md`、`references/artifact-contracts.md` 和 `references/workflows.md`。
3. 运行或等价执行预算拆分：

```powershell
python -m literary_engineering_workbench protocol longform-planning
python -m literary_engineering_workbench word-budget "<work-dir>" --target-words 500000 --volumes 5 --genre mystery
```

4. 读取 `plot/word_budget/word_budget.agent_tasks.md`。
5. 读取 `plot/word_budget/scene_inventory_expansion.agent_tasks.md`。
6. 读取 `plot/chapter_obligations/chapter_obligations.agent_tasks.md`。
7. 平台 agent 写出预算化大纲候选、预算审查、分章分场景库存候选、库存审查、章节义务规划和章节义务审查。
8. 预算化大纲、分场景库存与章节义务通过审查与用户批准前，不得覆盖正式 `plot/outline.md` 或 `scenes/*.yaml`。
9. 将预算落到正式 scene 库存：每个正式 `scenes/*.yaml` 必须有能映射预算行的 `chapter_id`；需要时写入 `word_count_target`、`word_count_min`、`word_count_max`。
10. 单章正文生成前运行 `chapter-obligation --chapter-id <chapter_id>`，让平台 agent 填写本章承诺、设置、变化、暂不解决项、章末钩子和逐场读者体验契约。
11. 后续 context packet、`compose-scene`、`generate-scene` 的 prompt manifest 和 `.agent_tasks.md` 自动加载本场景预算契约和读者体验契约。
12. AgentReview、`promote-candidate`、`route-audit`、`chapter-workspace`、`longform-audit` 和正式导出都会用清洗后的可交付正文复核字数、叙事负载和 reader promise/payoff。

## 计数口径

用户说“50 万字”“每场 1400 字”时，正式门禁解释为清洗后中文正文字符：

- 计入汉字和中文标点。
- 不计入 Markdown 标记、英文路径、代码围栏、workflow 说明、scene/chapter 编号、canon 注释、review notes、状态变化候选、写回候选或 `[AGENT_TASK: ...]`。
- 机器非空白字符数只作为诊断映射，记录在 `machine_count_mapping`、`clean_body_machine_chars` 等字段中。
- 若机器非空白字符数与中文内容字符数不一致，正式 pass/fail 使用中文内容字符数。

粗略映射原则：中文文学正文通常机器非空白字符数接近中文内容字符数；但一旦正文混入英文标签、路径、JSON key、Markdown 标记或工作流痕迹，机器数会被抬高。因此预算审查要同时看 `clean_body_chinese_chars` 和 `clean_body_machine_chars`，并优先追问差异来源。`machine_count_mapping` 会给出两组辅助值：`baseline_machine_chars_1_to_1_range` 是普通中文正文的 1:1 基准，`rough_expected_machine_chars_range` 是按当前清洗正文的机器/中文比例推导出的粗略机器范围。两者都只是诊断桥，不是正式通过条件。

## 文学理论约束

长篇字数由叙事单位累积而来。一个有效叙事单位通常至少完成以下一种功能：

- 推进行动：角色做出不可轻易撤销的选择。
- 改变信息：读者、角色或世界状态获得新信息。
- 制造代价：行动留下损失、债务、误解或新约束。
- 加深关系：人物之间的信任、敌意、依赖或误判发生变化。
- 改变空间/时间：场景切换带来新的风险、资源或规则。
- 建立回收：设置、延宕或兑现伏笔。

如果目标是 50 万字，项目不能只拥有十几个“剧情点”。它需要成百上千个可拆分的场景功能点：主线推进、关系线、世界信息、后果链、喘息段落和伏笔回收要形成网状结构，而不是把每个事件拉长。

## CLI 负责什么

CLI 只做可重复计算：

- 从 `project.yaml` 或参数读取目标中文内容字符、类型、卷数。
- 用类型预设拆分卷、章、场景、平均字数和叙事负载比例。
- 扫描 `plot/outline.md` 和 `scenes/*.yaml` 的现有库存。
- 读取已写草稿的清洗后正文字数，排除流程说明、canon 注释、编号、路径和 `[AGENT_TASK: ...]`。
- 把每章目标中文内容字符、实际正文中文内容字符、机器字符诊断、已有场景数、推荐场景数和缺失场景数写入 `scene_inventory_binding`。
- 输出预算报告、JSON 和平台 agent 任务侧车。
- 生成每个场景的字数预算契约，并把它注入 context packet、composition、prompt manifest、AgentReview 和 route gate。
- 输出章节义务规划侧车，并为单章 `chapter-obligation` 提供可校验脚手架。

CLI 不负责判断“这个故事怎样才好看”，也不自动改写正式大纲。

## 平台 Agent 负责什么

平台 agent 必须完成主观和创造性判断：

- 判断类型、时间跨度与目标中文内容字符是否匹配。
- 将预算转化为可写的大纲候选和分场景库存。
- 为欠账章节设计扩场景任务：补什么事件、补哪条关系/线索/后果链、预计字数、不能触碰哪些 canon。
- 检查是否存在灌水、重复桥段、无后果场景或机械扩写。
- 决定是否建议用户缩短目标、增加卷数、增加人物线、扩大时间跨度或改结构。
- 审查预算化大纲是否能支撑正式生成。
- 审查每章是否有足够读者问题、承诺兑现、信息暂扣、章末钩子和反摘要策略。

## 关键文件

- `plot/word_budget/word_budget.md`
- `plot/word_budget/word_budget.json`
- `plot/word_budget/word_budget.agent_tasks.md`
- `plot/word_budget/scene_inventory_expansion.agent_tasks.md`
- `plot/chapter_obligations/chapter_obligations.agent_tasks.md`
- `plot/chapter_obligations/{chapter_id}.json`
- `plot/chapter_obligations/{chapter_id}.agent_tasks.md`
- `plot/candidates/outlines/word_budget_expansion.md`
- `plot/candidates/scenes/word_budget_scene_inventory.md`
- `reviews/word_budget/word_budget_review.md`
- `reviews/word_budget/scene_inventory_review.md`
- `reviews/word_budget/chapter_obligation_review.md`

## 生成前门禁

正式场景生成前，平台 agent 应检查：

- 当前目标中文内容字符是否超过 100000。
- 是否存在 `plot/word_budget/word_budget.json`。
- `plot/word_budget/word_budget.agent_tasks.md` 是否已有 `.agent_completion.json` 完成标记。
- 是否存在 `reviews/word_budget/word_budget_review.md`。
- 是否存在 `reviews/word_budget/chapter_obligation_review.md`。
- 预算状态是否为 `pass`，且不是 `needs_expansion`。
- 当前 `scene.yaml` 是否有能映射预算行的 `chapter_id`。
- 当前 `scene.yaml` 的 `word_count_target/min/max` 是否与章节预算一致，或已有人工说明的合理 override。
- 当前章节的 `plot/chapter_obligations/{chapter_id}.json` 是否由平台 agent 填写并完成 sidecar marker。
- 该 JSON 是否完整填写逐场 `reader_experience_by_scene`，并能映射当前 `scene_id`。
- prompt manifest 是否包含“长篇字数预算标准”和“本场景字数预算硬属性”。
- prompt manifest 是否包含 `generation_standards.reader_experience_contract`。
- AgentReview 是否写入 `word_budget_adherence`，且使用清洗后的可交付正文统计。
- AgentReview 是否写入 `reader_experience_adherence`，并确认读者承诺已满足或说明必须修订。

如果预算缺失、预算任务未完成、预算为 `needs_expansion`、场景 `chapter_id` 无法映射预算、章节义务未完成、读者体验契约缺失，或 `route-audit --route longform-planning` 显示场景库存/章节义务门禁未完成，不得直接批量生成正文；先扩充大纲、场景库存和章节义务。不能用状态变化候选、canon 说明、workflow 痕迹、scene 编号、路径或 prompt manifest 内容凑字数。
