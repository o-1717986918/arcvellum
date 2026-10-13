[NATURAL_SOURCE_REFERENCES_V1]
[NATURAL_TASK_FIELDS_V2]

把创作者已经交付的自然文字登记为 JSON 记录。交付对象的顶层字段由 task_contract 定义，另附 source_sha256。例如素材交付为 {"source_sha256":"本次摘要","candidates":[{"text":{"$source":{"first_block":"b0001","last_block":"b0003"}},"focus":"素材主题"}],"no_material_reason":""}；正文交付以 prose、scene_delta、material_decisions 等字段直接开头。source_index、context 和 task_contract 是本次阅读资料，交付的是其中定义的文学记录。按原文明示的内容登记任务、来源、取舍、交接与审读结论，保留创作者的原意和判断。

原文全文在 source_text，source_index 提供段落编号及首尾文字。长文本字段使用原文引用，程序据此逐字取回正文、委托、卡片和素材。记录顶层 source_sha256，使用形如 {"$source":{"first_block":"b0001","last_block":"b0003"}} 的引用。需要段落内片段时，加 start_anchor 与 end_anchor，分别写出该片段开头、结尾的独特原文；程序包含两端锚点，并保留中间所有文字。段落编号与摘要采用本次提供的值。

source_index.blocks 的每行依次给出编号、开头和结尾。delivery_guidance 说明本次交付阶段与各领域素材的登记方法。

local_fields 和 known_cards 是已从本次原文确定的记录。补齐 remaining_fields；角色卡按 target 对应本地已有卡。返回的文学内容通过引用记录，类别和编号采用本次合同提供的标识，空缺项按合同记录为空或待补充。

角色当轮回应由程序完整保存在一个候选中。为这个候选填写 focus 和 annotations；annotations 依原文顺序列出目标角色的 kind（spoken、first_person_action、private_impulse）与 text 原文引用，台词穿插动作分成多个片段，每个片段保留其原位置。目标角色见 context.request.target。世界与历史素材包含制度、风俗、设定、传闻和长过程，各段按其来源状态登记为候选。

局部修复任务包含 repair_paths。使用 {"source_sha256":"本次摘要","patches":[{"path":"给定字段路径","value":"修复后的值或原文引用"}]} 补交相应字段，成功记录由程序沿用。
