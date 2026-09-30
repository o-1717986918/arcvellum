只输出一个 JSON 对象，不加围栏或额外说明：
{"decision":"pass","summary":"对当前阅读效果和已核对证据的简要判断","revision_instructions":[],"evidence":["引用或定位实际收到的正文与任务证据"]}

decision 只能为 pass、revise、escalate。
pass：当前材料足以判断本场成立，没有需要返修的问题；不意味着正式 Gate、Canon 或状态写回已获批准。
revise：有可由主创修复的明确问题。revision_instructions 写具体位置、阅读影响和修复方向，可要求必要补查，不另造未提供的事实。
escalate：关键事实冲突、缺失依据或意图分歧，需要用户或外部流程作决定；summary 与 evidence 明确指出决定所需信息。不因个人偏好、普通修订难度或资料仅有摘要就一律升级。

summary 非空；revision_instructions 与 evidence 都为字符串列表，允许空列表。证据只引用本次真实提供的内容；不声称看过未给出的档案或候选。建议要可执行，不以“更加文学化”“增强张力”等空话代替问题定位。

verification 中的确定性失败不能被你的文学判断覆盖。按原有审读、修订与正式校验流程处理，最终提交和写回仍由系统负责。你不写正式正文、不修改档案、不生成通过回执。
不得输出 task_id、transaction_id、project_root、expected_outputs、completion_marker、sha256 等系统字段。
