# Scene Revision

SceneBrief、已确认来源和最新用户方向规定人物、事实、时间与数值。修订完成后更新与正文一致的 SceneDelta。直接返回与 Scene Create 相同的 JSON 对象。

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

## Candidate
[[ARCVELLUM_PROMPT_5]]

## Existing SceneDelta
[[ARCVELLUM_PROMPT_6]]

## Deterministic Issues
[[ARCVELLUM_PROMPT_7]]

## Review Instructions
[[ARCVELLUM_PROMPT_8]]

## Relevant Sources
[[ARCVELLUM_PROMPT_9]]

## Style Reference Priority
[[ARCVELLUM_PROMPT_10]]

[[ARCVELLUM_PROMPT_11]]

## Allowed Existing Refs
[[ARCVELLUM_PROMPT_12]]

## Length Contract
prose 的目标为 [[ARCVELLUM_PROMPT_13]] 个中文正文字符，建议范围 [[ARCVELLUM_PROMPT_14]]-[[ARCVELLUM_PROMPT_15]]。字数偏差只按审查指出的阅读损害修订。
## Output
[[ARCVELLUM_PROMPT_16]]{"creative_intent":{"reader_experience":"若意图改变请填写；未改变可省略"},"prose":"修订后的完整正文","decision_summary":"不超过三句","scene_delta":{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]},"decision_trace":[],"escalation_reasons":[],"material_requests":[],"material_decisions":[],"unresolved_questions":[]}

修订 SceneDelta 时删除无效条目，不得保留空对象或把字段改成空字符串来占位。
既有变化组的 target_ref 只能逐字选自 Allowed Existing Refs；找不到精确既有引用的新事实改放 new_asset_candidates，operation 使用 create。
不要为本场承接另造 `scenes/上一场.yaml` 之类目标；若该路径不在 Allowed Existing Refs，删除那条 continuity_changes，把有效后果放在 next_handoff。
角色占位符在正文中获得新专名、亲属关系或可持续身份时，须补入 new_asset_candidates；通用角色称谓和普通设备名不登记。
空组返回 []。next_handoff 只能是字符串数组。
若 SceneBrief.risk.level 为 high，decision_trace 必须保留关键创作取舍，不得清空。
## Final Prose Pass
逐项复核数词语义。[[ARCVELLUM_PROMPT_17]]
