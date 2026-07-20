# Reader Experience Contract Module

本模块把“读者为什么继续读”写成正式工程契约。它不是营销文案，也不是事后审查意见，而是长篇正文生成前必须读取的章节义务和逐场读者体验硬属性。

## 解决的问题

长篇项目常见失败不是模型不会写句子，而是大纲和场景只记录“发生了什么”。当正文生成时，平台 Agent 容易把每场写成剧情摘要：事件推进了，但没有读者问题、承诺回报、信息暂扣、兑现或延迟，也没有章节级的功能义务。最后看起来字数不足、节奏发虚、每章没有继续读的理由。

`reader_experience.py` 将这个问题拆成两层：

1. Chapter Obligation Contract：每章必须承担什么功能，兑现什么，设置什么，什么暂时不能解决，章末留下什么钩子。
2. Reader Experience Contract：每个场景必须回答读者问题、承诺回报、暂扣信息、兑现/延迟、情绪曲线、张力来源、新鲜度、反摘要要求和读后余味。

## 正式链路

对于目标达到 100000 中文内容字符以上，或 `scene.yaml` 显式写入 `chapter_obligation_id` 的项目，正式场景生成前必须完成：

```powershell
python -m literary_engineering_workbench word-budget "<work-dir>" --target-words 500000 --volumes 5
python -m literary_engineering_workbench chapter-obligation "<work-dir>" --chapter-id chapter_0001
```

推荐控制面仍然是持续状态机：

```powershell
python -m literary_engineering_workbench task-next "<work-dir>" --route longform-planning
python -m literary_engineering_workbench task-open "<work-dir>" --task-id <task-id>
python -m literary_engineering_workbench task-submit "<work-dir>" --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete "<work-dir>" --task-id <task-id>
```

`word-budget` 会额外创建 `plot/chapter_obligations/chapter_obligations.agent_tasks.md`。平台 Agent 必须处理这份通用章节义务规划侧车，写出 `reviews/word_budget/chapter_obligation_review.md`，并创建 completion marker。单章进入正文前，再运行 `chapter-obligation --chapter-id <chapter_id>`，由平台 Agent 填写对应的 `chapter_*.json` 和 `chapter_*.md`，完成相邻 `.agent_completion.json`。

## 必填字段

章节层字段：

- `chapter_function`
- `must_payoff`
- `must_setup`
- `must_change`
- `must_not_resolve`
- `inherited_hooks`
- `ending_hook`
- `inventory_sufficiency`

场景层字段：

- `reader_question`
- `promised_reward`
- `withheld_information`
- `payoff_or_delay`
- `emotional_curve`
- `tension_source`
- `curiosity_hook`
- `freshness_requirement`
- `anti_summary_requirement`
- `reader_aftertaste`

缺任一字段时，`reader_experience_contract` 状态为 `incomplete` 或 `blocked`，`generate-scene`、prompt pack、AgentReview、promotion、route audit、chapter workspace 和 export readiness 都不能把它视为通过。

## 与字数预算的关系

字数预算回答“每章每场大约应该承担多少中文内容字符”。读者体验契约回答“这些字符为什么值得存在”。二者必须同时满足：

- 不靠拉长句子、堆形容词、重复情绪来凑字数。
- 不把本该展开的场景压缩成摘要。
- 每场至少有明确读者问题和兑现/延迟机制。
- 每章至少有承诺、设置、变化和章末钩子。

计数口径仍以清洗后的中文内容字符为准，计入汉字和中文标点。机器非空白字符只作诊断映射，用来发现正文中是否混入英文路径、JSON key、workflow 痕迹或 Markdown 标记。

## 平台 Agent 责任

CLI 只生成脚手架和确定性门禁。平台 Agent 必须完成真正的文学判断：

- 判断章节义务是否足以支撑目标中文内容字符。
- 把读者问题和承诺回报写成可执行的场景策略。
- 识别摘要化风险，补充角色选择、信息释放、关系压力和后果。
- 在 AgentReview 中审查正文是否实际兑现 reader contract。
- 如正文只复述事件但没有读者推进，要求 `revise-scene` 后重审。

## 验收信号

一个长篇场景进入正式生成前，应能看到：

- `plot/word_budget/word_budget.json`
- `plot/chapter_obligations/chapter_obligations.agent_tasks.md`
- `reviews/word_budget/chapter_obligation_review.md`
- `plot/chapter_obligations/{chapter_id}.json`
- `plot/chapter_obligations/{chapter_id}.agent_completion.json`
- prompt manifest 中的 `generation_standards.reader_experience_contract`
- AgentReview 中的 `reader_experience_adherence`

缺任一关键项时，状态机应把下一步指向补契约或补审查，而不是让平台 Agent 直接写正文。
