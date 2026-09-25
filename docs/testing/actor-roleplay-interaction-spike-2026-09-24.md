# 角色对戏最小工程试验（2026-09-24）

## 人物类型词对照：变更约定

```yaml
module_change_packet:
  objective: "按用户澄清，以简短人物类型词初始化角色，对比抽象文学气质词的实际效果"
  primary_module: "workers/pi-worker/scripts 实验脚本；不接入产品执行链"
  public_entry: "node scripts/actor-roleplay-spike.mjs <new-output-dir> --archetype-voice"
  variation_point: "角色初始化里的风格词"
  inputs: ["现有人物档案支持的类型特征", "相同身份、沉浸要求、模型和七轮场景来话"]
  outputs: ["独立 transcript.json", "逐轮候选原文清单"]
  invariants: ["已有变体不变", "无工具持久角色会话", "不写正式正文、Canon 或 expected_outputs", "不增加 Gate"]
  allowed_dependencies: ["现有 Pi Agent Core 实验脚本"]
  forbidden_dependencies: ["正式任务写回", "项目资产修改", "不符合人物年龄身份的标签"]
  tests: ["语法检查", "真实模型试跑", "原文清单核对", "与抽象气质词版定性比较"]
  rollback_unit: "人物类型词可选变体及本记录"
  documentation: ["本记录"]
```

## 人物类型词对照：实跑结果

**“傲娇／御姐”这类标签比文学气质词更像一个能立刻上场的人物，但本次没有带来可靠的设定理解。** 周岑的提示只加了“严肃、傲娇、冷幽默、执拗”，许遥只加了“御姐、泼辣、嘴毒幽默、重情”。开场后，许遥会呛他“你那辆破皮卡上次就没打着火”，两人围绕姐姐的签字和载体是否算人争论；对话确有你来我往，也没有逐字复述这些类型词。

破皮卡、签字协议和“七十二小时内不许回头”都不是已给定事实；人物还把原定的记忆载体交接变成了读协议。标签带来的是容易识别的性格姿态，不是独一无二的声音，更不能替代场景事实。单次试跑不足以证明它比无风格版稳定更好。原文与初始化提示见 `build/scene-performance-e2e/interactive-roleplay-archetype-voice-20260924/`。

## 抽象短提示对照：变更约定

```yaml
module_change_packet:
  objective: "把鲜明口吻提示改为简短、抽象的定性描述，观察是否减少词语照搬而保留人物差异"
  primary_module: "workers/pi-worker/scripts 实验脚本；不接入产品执行链"
  public_entry: "node scripts/actor-roleplay-spike.mjs <new-output-dir> --abstract-voice"
  variation_point: "角色初始化里的风格段落"
  inputs: ["同一人物身份、沉浸规则、模型与七轮场景来话"]
  outputs: ["独立 transcript.json", "逐轮候选原文清单"]
  invariants: ["既有变体保持不变", "两名角色各用持久无工具会话", "不写正式正文、Canon 或 expected_outputs", "不增加 Gate"]
  allowed_dependencies: ["现有 Pi Agent Core 实验脚本"]
  forbidden_dependencies: ["正式任务写回", "项目资产修改", "新 Provider 抽象"]
  tests: ["语法检查", "真实模型试跑", "逐轮原文核对", "与无风格和鲜明具体提示定性比较"]
  rollback_unit: "抽象口吻可选变体及本记录"
  documentation: ["本记录"]
```

## 抽象短提示对照：实跑结果

**“沉郁而敏锐／机敏而锋利”这类气质词没有被直接照搬，人物关系却仍会因场景信息不足而走样。** 七轮对戏继续推进到飞行终端，但许遥在第二轮把周岑的姐姐误称为“我姐”，周岑随后也顺着这个错误作答。后段又出现未经给定的协议、缺格和航线细节。两人的话没有再围绕提示中的固定意象打转，不过人物语言差异仍较有限。

两版均沿用同一模型、角色身份、沉浸要求和七轮来话结构；每名角色各有一个持续会话，候选清单逐字收录回复。Pi Worker 108 项测试和架构审计通过。原文与初始化提示见 `build/scene-performance-e2e/interactive-roleplay-abstract-voice-20260924/`。这些输出没有写进正式正文或人物档案。

## 鲜明人物口吻对照：变更约定

```yaml
module_change_packet:
  objective: "依据已有人物档案，为两名角色加入各不相同的鲜明语言倾向并验证实际对白"
  primary_module: "workers/pi-worker/scripts 实验脚本；不接入产品执行链"
  public_entry: "node scripts/actor-roleplay-spike.mjs <new-output-dir> --vivid-voice"
  variation_point: "角色初始化中的语言风格段落"
  inputs: ["周岑与许遥的人物档案", "原有沉浸规则、场景来话、模型与轮次"]
  outputs: ["新变体 transcript.json", "逐轮候选原文清单"]
  invariants: ["既有默认和无风格变体不变", "角色会话持久且无工具", "不写正式正文、Canon 或 expected_outputs", "不增加 Gate"]
  allowed_dependencies: ["现有 Pi Agent Core 实验脚本", "两份人物档案的已确认设定"]
  forbidden_dependencies: ["正式任务写回", "项目资产修改", "新 Provider 抽象"]
  tests: ["语法检查", "真实模型试跑", "原文清单核对", "与无风格试跑定性比较"]
  rollback_unit: "实验脚本的鲜明口吻变体及本记录"
  documentation: ["本记录"]
```

## 鲜明人物口吻对照：实跑结果

**个性冲突更醒目，但提示中的比喻也会被演员当成现成台词反复使用。** 这版像给两位演员不同的说话冲动，而不是让他们共用一张操作清单：周岑追究话里的空白，许遥抓住他的回避反击。人物档案提供了依据——周岑把失踪与交付当作尚未结案的旧事，许遥尤其反感别人替她决定去留。

七轮对戏中，许遥问周岑“你要我留的是人，还是签收单？”周岑回应“单子在这儿，人也在。你要我撕哪张，我都能撕。”随后许遥回击“单子不敢递，人倒是敢认”。这几句比原先的流程核对更能区分两人的关系位置。周岑也有了较长的自我辩白，许遥不再只靠短命令回应。

**这不是可直接沿用的最终口吻。** 初始化写了“旧港玩笑”和“荒唐账单”，输出就重复旧港意象、账单说法，局部像在完成提示词里的修辞任务。角色还自行添加空白签收单、手套、播放装置等细节，并把记忆放出来，偏离本场预定的终端交接和信息保留。个性提示能增强辨识度，却不能代替主创决定情节、筛选台词。后续调整宜保留两人截然不同的说话冲动，减轻会被逐字照搬的意象和现成措辞。

同前两版，这只是一个模型、同一开场、七轮交替的独立候选试跑；后续来话引用对方即时回复，不能视为严格重复实验。原文、初始化提示和会话记录在 `build/scene-performance-e2e/interactive-roleplay-vivid-voice-20260924/`。七段清单与模型回复逐字一致，角色各自保持同一会话；Pi Worker 108 项测试与架构审计通过。未改动正式人物档案、创作流程或正文。

## 无语言风格提示对照：变更约定

```yaml
module_change_packet:
  objective: "在同一对戏流程中只移除角色初始化里的语言风格要求，观察文风变化"
  primary_module: "workers/pi-worker/scripts 实验脚本；不接入产品执行链"
  public_entry: "node scripts/actor-roleplay-spike.mjs <new-output-dir> --free-voice"
  variation_point: "初始化提示的风格要求有或无"
  inputs: ["相同角色身份、沉浸规则、场景来话与模型设置"]
  outputs: ["独立 transcript.json 与逐轮原文清单"]
  invariants: ["原版调用行为不变", "角色会话持久且无工具", "无正式正文、Canon 或 expected_outputs 写入", "不修改 Gate"]
  allowed_dependencies: ["现有 Pi Agent Core 实验脚本及只读认证"]
  forbidden_dependencies: ["正式任务写回", "项目资产修改", "第二套文学审查规则"]
  tests: ["语法检查", "真实模型试跑", "逐轮原文和清单核对", "与原版同流程定性比较"]
  rollback_unit: "本实验脚本的可选开关及本记录"
  documentation: ["本记录"]
```

## 无语言风格提示对照：实跑结果

**去掉预设口吻后，人物更愿意表达和顶撞；但自由发挥也让剧情明显跑偏。** 这像让演员放下“说话必须像流程单”的要求：他们终于能听见对方的话，也开始自己发明道具和下一幕。对本轮文风问题，删去压抑性的风格指令是有价值的；它不是可直接替换正式创作链的完整方案。

这次仍是同一个 DeepSeek V4 Flash 模型、两名各自保持会话的无工具角色、同样的开场和七轮交替顺序。后续来话会引用上一轮角色的实际回答，因此无法逐字保持相同。唯一主动改变的提示变量是：两人的初始化删去“流程句”“检查单”“越逼近核心越断在半句”等语言风格要求；身份信息与原有角色沉浸要求不变。没有给模型另加“要写得生动”的补偿指令。

周岑在新版本里先说“你现在走，还来得及”，后来坦白“我不想你走”；许遥没有机械地确认交接，而是问“是让我选，还是替我把答案摆好了？”，随后拒绝他代飞。旧版则主要围绕“第三段”“图放平”“离线校验”打转。新对话出现了更明确的情绪与立场冲突，句长和节奏也不再清一色短促。这支持“原风格提示把表达压窄了”的判断，但只是同场景各一次采样，不是统计结论。

**新的主要问题是演员擅自改写了场景。** 周岑发明“三号舱”，许遥发明废跑道航图，随后两人把故事推进到代飞争执，许遥直接离场。原本需要处理的记忆交接反而悬置。飞行终端在许遥并未放下时被周岑拿起，周岑还补写了“她刚才进来时搁下的”；道具连续性也不稳。许遥仍大量使用括号动作，周岑的“没人替得了”等台词也有现成戏剧腔。松开风格指令增加了表现空间，不等于自动获得鲜明人物语言。

本轮只验证了角色候选输出，没有调用主创、环境写手、正文修订或晋升。下一步若接入正式机制，更合理的是保留语言自由，同时让主创掌握已定情节和素材取舍；不必再用“流程句”一类口吻规定，也不必为这次跑偏新增文学门禁。

依据：原版与无风格版的逐轮原文、初始化提示和会话 ID 分别在 `build/scene-performance-e2e/interactive-roleplay-spike-20260924/` 与 `build/scene-performance-e2e/interactive-roleplay-free-voice-20260924/`。新清单逐字包含全部七段原回复；两个会话各自贯穿对应角色回合。语法检查、Pi Worker 108 项测试及架构审计通过。

## Module Change Packet

```yaml
module_change_packet:
  objective: "验证自然对戏与逐轮原文清单是否比整场结构化任务单更有角色语言差异"
  primary_module: "workers/pi-worker/scripts 实验脚本；不接入产品执行链"
  public_entry: "node scripts/actor-roleplay-spike.mjs <output-dir>"
  variation_point: none
  inputs: ["雨港离航 scene_0001 已确认的开场与情境变化", "上一轮两人的原始初始化提示", "当前 DeepSeek V4 Flash 认证"]
  outputs: ["隔离的逐轮 transcript.json", "供主创阅读的逐轮原文清单.md"]
  invariants: ["两个角色各用同一个无工具 Pi Agent 实例", "主持者不代角色说话或行动", "只转递对手可见可闻的回应", "不生成正式正文、Canon 或 expected_outputs", "不修改现行 Gate"]
  allowed_dependencies: ["Pi Agent Core", "Pi AI provider registry", "只读 credential store"]
  forbidden_dependencies: ["正式 TaskPackage 写回", "Studio 项目状态", "额外模型 Provider 抽象", "新的文学 Gate"]
  tests: ["真实模型试跑", "检查每角色会话 ID 连续性", "逐轮清单与原回复逐字一致", "与上一轮整场任务单输出作定性比较"]
  rollback_unit: "单个实验脚本及本记录"
  documentation: ["本记录"]
```

## 判定边界

这不是产品机制的完成实现，也不是正式场景测试。只判断：角色能否听见对方后产生不同于预制整场 JSON 的回应；人物身份与空间是否更稳定；短句、程序化说明、无根据数值是否减少；逐轮原文清单是否足以供主创取材。一个场景的一次试跑只能提供方向性证据，不能证明普遍改善。

## 结果

**对戏让人物开始接对方的话，却没有自动带来更好的文学语言。** 两人分别保持一个会话，轮流回应七次。周岑四次，许遥三次；两份初始化提示与上轮整场任务单测试逐字相同。主持者只给雨夜、广播、巡逻骚动和交接受阻等已有场景情况，不替任何角色说话。逐轮清单完整包含七段角色原文，没有转述或补写。

像两位演员隔着耳返对戏，许遥听到周岑问“第三段，还是名字”，回答“第三段。名字在反面”；周岑接着要求“图放平”，许遥再说“折角别松”。这比上轮两人分别预写整场，更清楚地呈现即时回应。明确写出对方身份与性别后，本次未再出现上轮那种反复错用“他／她”的情况，但这一变化不能单独归功于对戏方式。

**剧情漂移比语言收益更明显。** “名字在反面”、航路图、塔台自动匹配、生物签名等细节并非本场已确认事实。一个角色即兴提出，另一个角色接着当真，七回合后仍纠缠在图纸和签名上，尚未抵达原定的载体锁定后果。角色能听见彼此，同时也会共同放大未经确认的设定。

**原先的短促技术口吻依旧在。** 周岑反复操作主控板、线头和确认框；许遥反复按图角、等校验。双方虽然比整场 JSON 更能接话，仍有大量括号动作和短命令句。两条首轮语言特点本来就分别写成“流程句”和“检查单”；只把后续交互改为自然对戏，不足以抵消这层共同倾向。

## 判断

值得继续验证，但不宜据这一次结果替换正式角色链。最小的下一步不是加门禁：让主持者只转递角色已发生的公开言行，并在合适时刻引入已定的外部事件；给角色的自然开场补足必要的人物关系与已知事实，但不交付整场待完成事项。角色发言仍只作为主创候选，原始会话长期保留以便核对。若这样仍大量产生未经确认的设定或流程短句，对戏本身就不是主要解法。

本次只是一次、一个场景的方向性试验；先后两轮的输出形式和回合数不同，不能计算成严谨的文风胜率。也未调用环境写手、主创正文、正式审查或晋升。

## 依据

- 原始对戏与会话 ID：`build/scene-performance-e2e/interactive-roleplay-spike-20260924/transcript.json`。
- 供主创取材的逐轮原文：`build/scene-performance-e2e/interactive-roleplay-spike-20260924/materials.md`。
- 上轮结构化任务单输出：`build/scene-performance-e2e/role-init-creative-test-20260924/studio-data/actor-only/character-actor/runs/`。
- 验证：清单逐字包含全部七段角色回复；两个会话 ID 各自贯穿所属角色回合；`node --check`、Pi Worker 108 项测试、架构审计、模块图检查和 `git diff --check` 均通过。
