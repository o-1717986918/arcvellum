# Scene Create

SceneBrief、已确认来源和最新用户方向规定事实边界；逐字沿用已确定的人名、日期、年份、数量和时间差。最后以 JSON 交付正文和正文实际造成的变化。

## Editable Literary Guidance
[[ARCVELLUM_PROMPT_0]]

## SceneBrief
[[ARCVELLUM_PROMPT_1]]

## Working Literary Intent
[[ARCVELLUM_PROMPT_2]]

## Creator Scene Memory
[[ARCVELLUM_PROMPT_3]]

## Expression And Voice Context
[[ARCVELLUM_PROMPT_4]]

## Relevant Sources
[[ARCVELLUM_PROMPT_5]]

## Style Reference Priority
[[ARCVELLUM_PROMPT_6]]

[[ARCVELLUM_PROMPT_7]]## Allowed Existing Refs
[[ARCVELLUM_PROMPT_8]]

## Length Contract
prose 的目标为 [[ARCVELLUM_PROMPT_9]] 个中文正文字符，建议范围 [[ARCVELLUM_PROMPT_10]]-[[ARCVELLUM_PROMPT_11]]。首轮写出完整场景；软下限不构成强制补段，由审读判断阅读效果。
[[ARCVELLUM_PROMPT_12]]
本场实现 SceneBrief 的 objective、participants、scene_function 与 incoming_handoff。章级义务提供方向；上一场已发生的后果进入此场。使用中文引号与标点。

## Output
[[ARCVELLUM_PROMPT_13]]{"creative_intent":{"reader_experience":"希望读者怎样经历这一场","reader_knows":"可选","reader_misreads":"可选","withheld":"可选"},"prose":"完整正文；取材请求时可省略","decision_summary":"不超过三句","scene_delta":{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]},"decision_trace":[],"escalation_reasons":[],"material_requests":[],"material_decisions":[],"unresolved_questions":[]}

首次回答无论直接成稿还是请求素材，都请给出 creative_intent。收到候选后可修订意图并简述缘由；material_decisions 按 candidate_id 记录采用、改写或舍弃的理由。候选未采用不构成缺戏。不要把有意误导写成已确认世界事实。

既有对象变化项使用 {"target_ref":"Allowed Existing Refs 中的精确字符串","summary":"变化","evidence":"正文证据","operation":"update","attributes":{}}。
character_changes、canon_candidates、continuity_changes、promise_updates、reader_question_updates 的 target_ref 只能逐字选自 Allowed Existing Refs，禁止自造同义 ID。
若不能确定精确 ref，就不要填写该组；不要为了让变化看起来完整而创造 target_ref。
上一场文件只是来源，不能把未列入 Allowed Existing Refs 的 `scenes/上一场.yaml` 自造为 continuity_changes 目标；承接结果可写进 next_handoff。
正文出现的新人物、新地点、新组织或尚无精确引用的新事实，只能放入 new_asset_candidates，operation 使用 create；不得塞进既有对象变化组。
若正文给“幸存者”“旧搭档”等角色占位符新增专名、亲属关系或可持续身份，也必须在 new_asset_candidates 登记该身份。仅沿用 SceneBrief 中的通用角色称谓不算新增身份。
空组必须返回 []，禁止用空对象占位。next_handoff 只能是字符串数组，不得返回对象。
只提出正文确实发生的变化；无法确认、需要人工判断的内容放进 escalation_reasons。
若 SceneBrief.risk.level 为 high，decision_trace 必须用少量条目记录关键创作取舍。

## Final Prose Pass
核对破折号、数词和量化单位的实际语义。[[ARCVELLUM_PROMPT_14]][[ARCVELLUM_PROMPT_15]]
