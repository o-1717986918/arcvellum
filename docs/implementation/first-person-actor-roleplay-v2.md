# 第一人称角色表演合同修正

状态：2026-09-23，实施记录。适用于实验性 lean-v2 场景表演候选；正式正文、Canon 与审查链不变。

## 问题与验收

上一轮真实试跑中，周鹤的候选台词反复使用“先分开”“这个问题本身要分成两问”等程序解释，动作是第三人称导演描写，`subtext_effect` 还要求分析关系作用。虽然提示写着“扮演”，实际输出合同要求模型同时充当演员和解说员，人物档案则以 JSON 附录出现，未形成持续的第一人称身份。

本轮目标不是提高审美门禁，而是让独立角色 Agent 在生成时始终以“我”为角色的内在位置：从已确认身份、欲望、恐惧、关系和个人语言习惯中说出**一段真实当场台词**，并以第一人称报告相伴动作与未出口的冲动。主创再决定是否将这些候选改写进第三人称或其他正式叙事视角。至少两个角色的同场试跑应有可辨的词域、句法、礼貌/回避方式和受压变调；不能以复述人物卡示例或任务单术语冒充个性。

## Module Change Packets

```yaml
module_change_packet:
  objective: "角色候选从导演式说明转为人物内部的第一人称表演"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_actor_prompt、parse_actor_material、render_performance_materials"
  variation_point: "ActorMaterial/v2 的第一人称素材字段和角色任务提示"
  inputs: ["SceneBrief", "锁定的节拍", "既有人物声音投射", "已确认来源"]
  outputs: ["spoken", "first_person_action", "private_impulse"]
  invariants: ["剧情和事实由任务单锁定", "不替他人说话", "无正式正文/Canon 权限", "候选仍由主创取舍", "不新增风格硬门禁"]
  allowed_dependencies: ["现有 Engine 场景合同和人物声音投射"]
  forbidden_dependencies: ["Studio 内部", "Provider SDK", "项目持久化"]
  tests: ["提示词角色身份/语言机制", "字段解析与长度边界", "主创候选说明"]
  rollback_unit: "与依赖此签名的 Studio/Pi 薄适配合并为一个可运行提交"
  documentation: ["本记录", "scene-performance-agents-v1.md"]
```

```yaml
module_change_packet:
  objective: "Pi 单轮无工具会话维持第一人称演员身份"
  primary_module: "workers/pi-worker conversation"
  public_entry: "conversationSystemPrompt(character-actor)"
  variation_point: "静态演员人格提示，不新增任意系统提示注入"
  inputs: ["白名单 conversation_role", "Engine 渲染的角色任务单"]
  outputs: ["ActorMaterial/v2 JSON 候选"]
  invariants: ["tools=[]", "单轮", "无项目写权限", "非正式正文"]
  allowed_dependencies: ["现有 Pi conversation profile"]
  forbidden_dependencies: ["Engine 内部", "动态 Provider 特判", "项目工具"]
  tests: ["演员系统提示特征", "既有 profile 回归"]
  rollback_unit: "与 Engine/Studio 合并为同一可运行提交"
  documentation: ["本记录"]
```

```yaml
module_change_packet:
  objective: "新版角色候选不复用旧缓存且继续交给唯一主创"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "scene_performance_materials、scene_creative_cache_digest"
  variation_point: "候选合同版本变更对应缓存版本"
  inputs: ["ActorMaterial/v2", "原场景事务配置"]
  outputs: ["隔离候选缓存", "主创候选块"]
  invariants: ["旧缓存不被误读", "失败回退单主创", "场景提交不变"]
  allowed_dependencies: ["Engine public/literary.py", "现有 RoleConversationGateway"]
  forbidden_dependencies: ["Engine 内部 import", "第二套正文或 Canon 写入"]
  tests: ["候选调用顺序", "缓存版本失效", "主创仍唯一写正文"]
  rollback_unit: "与 Engine/Pi 合并为同一可运行提交"
  documentation: ["本记录"]
```

## 设计边界

- 系统身份用第一人称角色表演，而非“作为助手描写角色”；JSON 只作为交付容器，不允许 `spoken` 自带导演批注。
- 人物卡的稳定声音是可执行的语言机制：词域、句法节拍、称呼、礼貌边界和紧张时偏移。角色输入不再带 `signature_patterns` 的成句范例，`rhythm` 中带引号的范例也替换为概括措辞，防止复读。
- 导演任务单仍决定必须发生的事件、事实、言语目标和边界；演员只收到眼前事件、动作/他人反应边界及自己的身份、关系、欲望和知识，不读取导演拟定的 `speech_act`、`information` 清单、全知来源或**尚未采用的**其他演员候选。演员在该空间内自行决定微观话术、姿态与是否先回避。`first_person_action` 与 `private_impulse` 是后台第一人称素材，主创不可照抄为正式叙述；主创仍须兑现完整任务单中的剧情义务。
- 不用“必须含我字”等机械门禁评文学个性。解析器只校验目标、结构和长度。缺少角色资产时不得自造背景，试跑要单独标记此类失败。
- 角色素材合同升级后刷新候选缓存和主创正文缓存，避免旧字段/旧提示结果混入。角色缓存键还绑定当前节拍内容，而不再绑定未采用的前一候选。

## 检索参考与工程判断

- [CoSER（ICML 2025）](https://proceedings.mlr.press/v267/wang25dk.html)使用 *given-circumstance acting*，把角色经历、内部念头、场景中的言语与行动一起建模。这支持“给演员可感知的当下与人物经历”，但其报告的是数据、训练和评测结果，不能直接当成某一条提示词已在本项目生效的证明。
- [Thinking in Character](https://arxiv.org/abs/2506.01748)指出推理式角色 Agent 可能出现注意力从角色转向任务、语言变得正式僵硬；其角色身份激活思路可借鉴，但论文的训练/蒸馏方法没有被本项目照搬。当前代码以角色身份系统提示加情境化输入实现轻量实验，效果必须另测。
- [DeepSeek JSON 输出说明](https://api-docs.deepseek.com/guides/json_mode/)要求明确提示 JSON 与所需形状；本项目保留结构化外壳来维持隔离候选合同，但这可能让演员偏向填表。是否改为自由表演文本再提取，需要同题盲测和解析失败率数据，不能因个别样本直接改。DeepSeek [Responses API](https://api-docs.deepseek.com/api/create-response/)说明 thinking mode 下 temperature 不生效，因此不把升温视为此问题的主要修复。
- 一份[DeepSeek 社区角色扮演原始提示](https://github.com/fxsunix/deepseek-r1-0528-roleplay-prompt/blob/main/prompt.md)强调角色有独立目标、偏见、误判、主动回应和知识边界；这与本项目的“演员只决定微观反应”相容。但它也允许角色推进世界与其他 NPC、篇幅很长，与唯一主创和 Canon 边界冲突，只取身份/自主性原则，不整段移植。

## 验证记录

2026-09-23 使用上轮《shoreline》场景三的同一组人物和节拍，以本机 `deepseek/deepseek-v4-flash` 抽样。完整导演任务单下，周鹤反复说“分开”“程序”等，与原候选相似；遮去演员输入的 `speech_act` 和 `information` 后，同场周鹤的一轮对话变成对沈照月的具体追问，证明任务单措辞会强烈进入台词，但不是风格胜出的统计证据。最新版输入只保留眼前事件和硬边界，候选已能保持第一人称内部冲动与动作、一个候选的结构；周鹤和沈照月仍常落回其职业流程口吻，且候选出现未经来源确认的手套、接线盒、登记细目。这些不能直接进入正文。原人物卡也同时把两人说话写成“程序语言”，所以提示词单独无法保证对白显著分化。

本轮代码与模型试跑只证明**身份/输入分工和缓存合同已修正**，不宣称人物语言问题已解决。下一轮若做质量裁决，应在相同场景比较完整任务单与情境精简输入，去名对白盲辨角色，并逐句核对新事实、记录主创采用/拒绝情况；若仍像填表，再测试自由表演文本与结构化提取的两阶段方案，而不是继续堆叠禁句。

工程验收：Python 全量 `1532` 项完成、`1` 项跳过；Pi Worker `106` 项通过；架构审计通过（无新增循环/禁止依赖）、模块图检查通过、Prompt Registry `59` 资产/`73` ID 有效、`compileall` 与 `git diff --check` 通过。第一次全量运行曾因新增函数超出复杂度预算失败；提取纯身份整理函数后，定向架构测试和第二次全量运行均通过。此次没有把候选提交到正式作品，也没有发布版本。
