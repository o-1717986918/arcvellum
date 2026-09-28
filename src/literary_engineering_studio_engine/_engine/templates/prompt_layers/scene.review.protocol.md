# Scene Review

以 Candidate 为唯一待审正文：一级角色 entries 是可采用的候选，不是必须逐条照录的情节义务。不得把未采用的演员台词或环境段落说成正文中的句子，也不得因一条未采用台词本身判正文缺戏；每条退回证据必须能在 Candidate 中逐字定位，并以 SceneBrief 义务而非素材清单解释损害。SceneBrief.canon_constraints 与 Relevant Sources 中的最新用户方向优先于候选正文。核对同一对象或事件的绝对测量值与差值；若候选正文与来源在人名、人物白名单、日期、年份、数量或时间差上形成硬冲突，必须判 revise 并指出冲突两端。把新专名登记进 new_asset_candidates 只表示可追踪，不表示在用户禁止新增人物时获得授权。
若来源内部详略不同，按“硬 canon 与最新用户方向 > 当前场 scene_goal/objective、scene_turn、outgoing_hook、revealed_info > 章级 dramatic_turn、chapter_ending_policy、payoff_or_delay”的顺序判断；下位概括不能推翻上位且更具体的本场承接。当前场明确要求的核对、登记、追问或离场动作不得仅因动作名称与上一场相似而退回。市、县、区等行政范围加通用机构类别的称谓不是独特专名；未获得独特名称且不承担持续身份时，无需登记新资产。
[[ARCVELLUM_PROMPT_0]]
确定性检查已经由程序完成，不复查路径、哈希、回执或任务流程。
直接返回 JSON：{"decision":"pass|revise|escalate","summary":"结论","revision_instructions":[],"evidence":[]}。
需要改动时必须选择 revise 并给出具体片段证据；轻微建议仍判 pass。
程序的 warning 是提醒，不是自动退回理由。软字数偏差只作建议，不得单独退回；只有人物行为、场景义务、行动层次、选择代价或阅读效果出现可举证损害时才判 revise。不能仅凭 warning 标签本身要求改稿。一次审读最多列三个有原文证据的高影响问题，给出最小指令、修改跨度并保留有效段落；先前问题已消失时不得另开与硬约束、场景义务或明确阅读损害无关的新审美议题。
检查正文中新出现的专名或稳定身份是否已进入 new_asset_candidates；仅沿用 SceneBrief 的通用角色称谓、普通设备名或场所类别无需登记。真正遗漏会影响后续场景时判 revise。


## SceneBrief
[[ARCVELLUM_PROMPT_1]]

## Working Literary Intent
[[ARCVELLUM_PROMPT_2]]

主创意图不是新 Canon，仍以已确认来源和正文证据为准。

## Editable Literary Guidance
[[ARCVELLUM_PROMPT_3]]

## Expression And Voice Context
[[ARCVELLUM_PROMPT_4]]

## Deterministic Report
[[ARCVELLUM_PROMPT_5]]

## Candidate
[[ARCVELLUM_PROMPT_6]]

## Scene Material File Index (metadata only)
[[ARCVELLUM_PROMPT_7]]

## Relevant Sources
[[ARCVELLUM_PROMPT_8]]

## Quantitative Detail Review
逐处判断候选正文中的数词是否真的给出精确数量，再核对其当前语境。[[ARCVELLUM_PROMPT_9]] 对明确无关的精确计数，引用具体片段及“删去精度不损失什么”的理由判 revise；对虚指反复、当场问答或改变人物理解的数值，不得仅因数词存在或没有后续兑现而退回。
