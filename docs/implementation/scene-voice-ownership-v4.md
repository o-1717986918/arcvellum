# 场景声音归属与环境表演：持续实验计划

状态：2026-09-24，目标进行中。本文件保留历次 opt-in `lean-v2` 场景候选实验；早期“演员槽位／每人整场一轮”是历史方案，以后文的角色接力与“底线内自主性”修正为准。默认创作链、Canon 权限和既有硬审查不变。

## 从 v3 得到的经验

1. 通用“你是角色”系统提示已经存在；缺口是本场人物声音和关系变化没有被主创组织成足够鲜明的个人扮演上下文。逐拍独立调用又让角色每次重入，容易退回同一种中性、程序性的句法。v3 按人物一轮跨节拍输出减少了重入，但只覆盖导演规划的至多四个关键节拍。
2. 强化静态系统指令与人物输入后，同一人物两节拍能够一次输出不同压力下的台词；仍出现职业术语堆积和把职业惯例说成现场事实。人物资产本身的同质化不能靠叠加“鲜明”指令完全抵消。模型样本不能充当因果证明。
3. 当前环境 Agent 收到的是 SceneBrief、节拍、文风参考和通用“写环境”指令；它不知道本场哪些空间事实可被视角感知。`150—300 字`的固定目标易诱发灌水。环境候选必须由视角和行动触发，但不应被强迫每句推进情节，也不能凭装饰性“五感清单”制造丰富。
4. 当前主创正文提示仍允许自行写人物对白和动作；候选又明言可全部丢弃。因此 v3 **不满足**“所有人物发言、行为都由一级角色 Agent 先生成”的新要求。只改提示词无法给出这个保证。

## 外部方案的可取与不可取之处

- [SillyTavern 官方人物卡与提示结构](https://docs.sillytavern.app/usage/characters/)把人物性格、场景、对白例句、角色注释分开；[提示检查器说明](https://docs.sillytavern.app/usage/prompts/)强调看到最终组装的提示。这支持本项目拆出“稳定人物身份/声音”“本场关系压力”“导演分配的行动边界”，并保留最终 prompt 的可检视记录。其完整角色卡例句直接复制会污染本作事实与口癖，不照搬。
- [NovelAI 官方 Story Settings API](https://docs.novelai.net/en/scripting/story-settings-api/)区分持久 Memory、靠近故事尾部的 Author's Note 和开头 System Prompt；社区对强烈局部注释的经验并不一致。我们的对应做法是静态系统层放角色/环境职责，项目资产作有边界的数据，本场主创任务贴近交付请求；不把人物卡任意文本抬升为系统指令。
- [In Search of an Author 开源项目](https://github.com/dexmac221/InSearchOfAnAuthor)让人物有独立声音与个体记忆，展示“角色先表演”的可能；其故事可由角色自主涌现，与本项目既定剧情和唯一主创相冲突，只借独立人物视角和候选编排，不借 Canon 决定权。
- [alex-tavern 开源项目](https://github.com/al4xdev/alex-tavern)将人物的 speech、thought、action_intent 与导演物理结果分开，并用类型化交接。它的工程启发是：若要声称全部对白/行为由演员先生成，必须有可追溯的结构化交接，而非主创提示里一句“尽量采用”；但本项目不需要移植完整模拟时钟或复杂记忆内核。
- [角色扮演社区原始讨论](https://www.reddit.com/r/WritingWithAI/comments/1q9xkto/my_updated_guide_for_ai_roleplay/)提到人格实例、第一人称对白例句、自主但合乎角色的选择；这是使用者经验，不是控制试验。[写作社区关于描写的讨论](https://www.reddit.com/r/writing/comments/ypeqt3/description_vs_purple_prose/)提示具体细节应经视角选择、彼此流动，且丰富不等于固定字数或全感官铺陈。环境 Agent 应按本场需要选择少数感知线索，不统一套“光—声—气味—主题解释”。
- [CoSER 原论文](https://arxiv.org/abs/2502.09082)的 given-circumstance acting 给演员场景、角色经历、动机与内在想法，让角色在对话中行动；这支持给“处境”而非给“台词配方”。一项[作者人物声音访谈研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC7068700/)记录到，有作者感到自己掌控情境而人物掌控其言语和动作；这不是 AI 系统的效果试验，但准确指出本项目应分开的控制权。2026 年 [RPGAgent 论文摘要](https://doi.org/10.1145/3772318.3790326)还报告多 Agent 创作中的“约束级联”可能以流程效率换取表达空间，建议可选择地放松约束；它的任务是游戏生成，不能直接推断本项目收益，却是对继续加导演字段的警示。角色扮演社区也有[减少叠加指令的经验帖](https://www.reddit.com/r/SillyTavernAI/comments/1twgc77/my_view_on_model_prompting_for_rp/)；评论里存在模型依赖和反例，因此必须实测。

## 目标架构

```text
SceneBrief + 人物/世界/文风来源
          │
          ▼
唯一主创（导演阶段）：结构化 ScenePerformancePacket
  ├─ 每个角色的本场处境、关系压力、完整发言/行动槽位
  └─ 环境任务：视角可感知范围、已确认空间事实与边界
          │
          ├─ 一级角色 Agent：每人物一轮，产生该人物全部计划发言与行为
          └─ 一级环境 Agent：整场一轮，产生非权威环境段落
          │
          ▼
唯一主创：组织候选、补写非角色行为的叙述，输出正文及来源收据
          │
          ▼
结构核对：每句人物对白与每项人物行为均可回指一级角色素材；
           无法回指则补充角色表演或退回本实验路径，不能假报覆盖
```

## 2026-09-24：短场景端到端复跑与“惜字”问题

忽略目录 `build/scene-performance-e2e/mini-literary-e2e-live/` 中的合成姐弟场景使用真实 Pi Worker/DeepSeek 调用，测试了主创编排、两名首级演员、独立环境、正文、审读与修订。最初主创把“关系未修复”误拆成短而非事件性的里程碑，解析拒绝；模型收到原输出、具体错误与来源边界后重新编排，成功继续。演员有时输出超过本轮条目数，现同样只允许一次格式修复；二次仍不合格明确失败。这里修的是随机格式错，不放宽事实合同或文学门禁。

第一版短场景的演员只产出四条言行，主创为了追求篇幅另写大量对白和行为。即使提示里已有“一级归属”，审读仍误称全部可回指。将字数置于角色归属之后、明确条目不是待续写的开头，并把原素材给审读，单次复跑改善但并不稳定：后续同素材复跑又出现主创自创后续问答。因此必须把人物话语归属与文风判断分开。仅对明确的对白引号做来源比对；检测到无首级 spoken 来源的台词时，主创按原素材最多返修两次，仍越权则失败。叙述中作为概念被引用的短语不当成对白，心理和环境不按此规则审查；动作的语义归属仍须由主创和审读判断。此处不是“文学味”自动门禁，不能证明所有动作都被严格归源。

另一个来源不稳定点是“结果已发生”不等于人物余波已经表演。接力在结果获得证据后，各给在场演员一轮无新剧情命令的自主余波；可说、可做、可沉默。第一次真实复跑的余波把演员素材增加到十八条、主创 1329 字且无未授权引号对白，但正文错误进入非视角角色的私念。现在交给正文的材料保留全场公开言行，只交当前视角的 private_impulse；其他角色私念仍存于表演过程，不直接作为正文视角知识。下一次十四条素材的复跑得到约 1900 字，但角色在余波擅自抛出与本场无关的新秘密；审读识别了偏移，却一度指示主创改写角色台词。审读/修订合同改为只能删选或重新组织已演素材，需要新台词则请求原角色续演。未解决的风险仍是演员把“自主”误解成制造跨场悬念、主创在可见微动作上越权，以及审读偶发过度乐观；不得把短场景成功等同于长篇端到端质量达标。

再次清空接力缓存并在角色系统画像加入“自由发挥不靠无来源的另一桩秘密”后，十二条演员素材支持了约 1800 字候选，未再出现另一桩秘密；但主创仍插入四句无一级来源的对白，审读却再次误报“无越权”。限定引号比对命中后，单轮修订未必成功；现最多两次来源定向返修，第二次仍失败就不交候选。最新短场景的两句越权对白经返修后消失，正文约 1787 字，有更多柳烟视角的回忆与迟疑，但仍呈现同类问答的重复、修辞风险和缺少风格差异的问题。审读还错误要求主创改写演员说过的“凉了半天”；程序只能核对引号文本来源，不能自动证明所有可见动作和人物心理的语义归属。下一轮须测试原有长篇项目中的复杂人物资产与真实场景，处理素材不足时主创如何发起**来源支撑的情境重构和原角色续演**，而不是继续加硬字数、盲目延长回合或把修订权偷换成代演权。

按中文去 AI 味审阅准则重新读这份候选，最影响读感的不是短，而是过量收录同类问答：例如“你想让我先问哪句”“你是怕我看见封口，还是怕自己先开口”都在推动同一个问题；“她没去接信”已经出现多次，场尾又重复一次，环境水珠也被用于过于可预期的悬停。主创的新提示因此强调**选材**：演员可以充分表演，主创不必把每条都刊入正文；删掉没有关系位移的回合，把篇幅给人物视角里的误读、自辩和感知变化。这不同于要求角色少说或要求主创多写固定数量的心理句。固定演员素材、只改主创提示的一次复跑仍出现约 1859 字正文、少量无来源对白与同类重复；一次样本不足以宣称“选材”已奏效。

同一真实候选另以 `deepseek-v4-pro` 作为审读模型做对照：Flash 与 Pro 都判 `pass`，都声称“无越权”，而来源比对明确抓到“你先坐。”这句演员未给出的台词。提高审读模型档位不能单独修复来源判定，也没有提供可信的文风改善证据。下一阶段应避免继续堆“请更有文学性”的提示或只换更强模型；要在主创编排层安排有根据的删选与再表演机会，并用盲读样本对比人物辨识、心理运动、环境必要性与重复结构。

对另一真实测试场 `scene_0002` 的来源审计显示，长接力反复卡住并不单是调用次数不足：场景 `revealed_info` 要周鹤承认“有人要求删去一段点名内容”，但其人物往事写的是他“主动划掉上级加进来的点名批评内容”，世界 `open_questions` 又明确把“是否受谁要求”保留未确认。三者未必逻辑互斥，却没有提供足以让角色在本场真诚说出“有人要求我删”的已知事实与转折条件。角色还有“维持技术取舍说法”“不会编造完全虚构经过”的动机与底线；无限追加提示或回合，会把可信防御误判为格式故障。未来的主创重构应先拿这些原文作来源对照，提出“补证具体请求及其来源”或“修订场景揭示为他主动删改”的候选，由正式剧情决策确认；不能在角色扮演或环境描写里现场创造那个请求者。此处记录的是测试资产的材料充分性缺口，不擅自改写正式剧情事实。

默认高优先级文风模板也仍含“只有行为无法承载且对当前决定必要时，才简短直述”。这会与最新“心理不应长期缺席、不要惜字”的方向相冲突。模板现在将心理呈现改成与动作并列的可用叙述资源，允许在真正承压处写出误读、自辩、记忆与念头转向；保留禁止视角越界和证据之后重复解释。旧项目已挂载的风格版本不被悄悄覆盖，Studio 当前创作/修订提示明确说明旧模板的“简短直述”不是硬上限，优先执行最新用户方向。此次改动通过默认风格的 500–2500 中文内容字符限制与挂载测试；它解决的是**上游压缩倾向**，不是单凭模板就能保证文笔多样。

把新模板显式放入同一合成场景的主创提示后，真实复跑得约 1845 字，台词来源比对通过，柳烟视角中有了“怕一开口便像母亲审问”“信像从前倒扣的考卷”等联想。但这份正文仍反复追问“想先问哪句／为什么不早拿出来”，结尾重复“放那儿吧”，水珠停在窗沿的意象也有可预测的收束感；还出现尚未转身便“一眼看见”他手中物件的视角瑕疵。两档审读都判通过，说明模板解压只提高了写法的许可度，尚未解决主创的选材判断、视角语义和审读敏感度。不可把单次篇幅增加当作去 AI 化的证明。

```yaml
module_change_packet:
  objective: "移除默认高优先级文风提示对心理描写的单向压缩"
  primary_module: "Engine _engine/templates/style/default-clear-plain"
  public_entry: "新项目默认风格版本构建"
  variation_point: "心理可外显也可在视角内充分叙述；停笔只针对重复解释"
  inputs: ["默认风格模板", "最新用户文风方向"]
  outputs: ["新建项目的文风提示与现有项目的本轮覆盖说明"]
  invariants: ["旧挂载版本不被覆盖", "硬违禁词与标点审查不移除", "不新增审美计数门禁"]
  allowed_dependencies: ["现有 Engine style version 合同", "Studio 主创提示"]
  forbidden_dependencies: ["直接写正式项目风格快照", "修改 Canon"]
  tests: ["默认挂载 500–2500 字符", "现有项目优先级提示", "prompt registry", "架构审计"]
  rollback_unit: "模板与当前创作覆盖提示分别回退"
  documentation: ["本文件"]
```

## 2026-09-24：外显动作的来源审计与收敛边界

选材对照中，主创即使只取十条角色素材，仍让柳烟在正文里“伸手，把信封拿起来”，而她的全部一级动作都没有拿信，其中两条明确写“没碰信／没翻”。这不是文风偏好，而是角色行动归属越权。旧版引号对白核对与 Flash、Pro 综合审读均未捕获该动作。聚焦审计的真实模型试跑以同一批角色条目为证据，指出该句及来源差别；完全由条目支持的简短对照返回空问题。生产提示的再次试跑也得到相同阳性与阴性结果。但用它实际返修后，主创又写出未经演员表演的“他往那个方向看了一眼”；独立复核发现，第一次审计没有发现。加强微动作提示后，同一篇候选的多次审计仍有时漏报，有时把原动作的同义改写误报；Pro 模型也没稳定抓到“看一眼”。因此聚焦审计只减少明显越权，**不证明全部人物行为均有来源**。

Studio opt-in 场景创作现在把“动作来源”与“对白来源”放在同一有限返修循环：先排除无一级 spoken 的引号对白，再让聚焦审计只核对同一角色已发生、会改变互动或物件状态的可见动作。审计不评价修辞、心理、环境、字数和数字；返回值必须引用正文连续原句、合法 speaker，若引用最接近条目则必须属于同一人物。发现越权时主创只可删去或重新组织已有表演；确需新行为须在 escalation_reasons 请求原角色续演。最多四轮返修，仍有问题即失败；未启用试验功能的默认单主创路径不增加审计调用。批量素材的角色名与条目 ID 由原分组稳定投影，旧创作缓存不冒充经过新审计的候选，但原一级素材缓存仍可复用。

这仍是模型语义审计，不是形式证明。主创生成和修订提示现明确指出“看向某处／又抹一下”也不能由主创顺手补造；同一冻结候选的一次新提示返修不再拿起信封，局部动作审计返回空，但人工通读仍看到可能没有被选中一级条目支撑的抹布、手搭水池边沿等微动作，不能宣称已解决。下一步应从正文交接结构减少主创自由增添外显动作的空间，而非继续堆审计指令或提高审读模型档位。综合文学审读继续承担场景事实、人物可信度、视角和风格判断；不因聚焦审计就声称文风多样化已被保证，也不增加抽象审美 lint。复杂测试场 `scene_0002` 的“受人要求删改”与人物往事来源缺口仍需剧情决策；本轮不靠角色临场发明请求者来强行完成。

```yaml
module_change_packet:
  objective: "减少主创把无一级角色来源的可见行动编入试验场景正文，并保留可解释缺口"
  primary_module: "Studio runtimes/scene_performance_ownership"
  public_entry: "PiSceneTransactionRuntime create_scene/revise_scene 的一级言行归属修复"
  variation_point: "窄范围语义动作审计，与既有确定性对白比对共用有限返修"
  inputs: ["同一候选正文", "原始一级角色素材", "聚焦审计输出"]
  outputs: ["可解释的动作来源问题与修订候选，或明确失败"]
  invariants: ["动作归属同一角色", "环境不决定人物行为", "Canon 与硬 lint 不变", "默认路径不增加模型调用"]
  allowed_dependencies: ["Studio Pi conversation gateway", "Engine public literary DTO"]
  forbidden_dependencies: ["Provider 专有语法", "Engine 内部 import", "正式项目直接写入", "审美计数门禁"]
  tests: ["阳性/阴性真实模型对照", "batch/relay 来源映射", "返修上限", "全量 Python 与架构审计"]
  rollback_unit: "Studio 归属检查与调用方缓存版本提交"
  documentation: ["本文件", "generated-module-map"]
```

```yaml
module_change_packet:
  objective: "让接力从一次格式失误恢复，并给已经兑现剧情的角色自主余波"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "mode=relay 的编排、演员调用与材料交接"
  variation_point: "编排/演员只重试一次；完成后每名在场角色最多一轮无指定结果的余波"
  inputs: ["SceneBrief", "原首级演员日志", "既定结果核对"]
  outputs: ["完整的首级表演候选或明确失败"]
  invariants: ["不改判事实", "不截断超额条目", "不让主创代演", "不无限加回合"]
  allowed_dependencies: ["Engine 纯合同", "现有 Pi Gateway"]
  forbidden_dependencies: ["新增审美门禁", "Provider 专有补丁"]
  tests: ["格式修复限一次", "角色余波", "缓存与真实短场景"]
  rollback_unit: "Studio relay adapter 提交"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "以窄范围来源检查阻止主创把自创对白冒充一级角色表演"
  primary_module: "Studio runtimes/scene_performance_ownership"
  public_entry: "create/revise 出口的角色对白来源校验"
  variation_point: "只比对实际对白引号和 actor spoken；最多两次返修，不处理抽象文风"
  inputs: ["正文", "原首级角色素材"]
  outputs: ["无越权对白的候选，或明确失败"]
  invariants: ["不检查数字和审美", "叙述性引号不当对白", "不默默删除台词", "原角色言行仍由首级生成"]
  allowed_dependencies: ["Studio transaction adapter", "Engine 的 CreativeResult 合同"]
  forbidden_dependencies: ["Engine 内部 import", "Canon 自动写入"]
  tests: ["合法拆句", "非法新台词", "叙述性引号", "返修二次失败"]
  rollback_unit: "Studio ownership 检查提交"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "避免非视角人物的未出口私念被主创写成全知正文"
  primary_module: "Engine literary/scene/roleplay 的材料交接"
  public_entry: "render_relay_materials 与 render_performance_materials"
  variation_point: "保留全场公开言行；正文材料只保留当前视角角色 private_impulse"
  inputs: ["角色表演候选", "SceneBrief.viewpoint"]
  outputs: ["视角相容的首级素材包"]
  invariants: ["不修改演员原输出", "不影响剧情核对", "不删其他角色公开言行"]
  allowed_dependencies: ["Engine 纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK"]
  tests: ["非视角私念遮蔽", "公开言行仍在", "原候选不变"]
  rollback_unit: "Engine material handoff 提交"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "让主创有心理、环境、节奏的真实修订空间，同时不越过角色台词归属"
  primary_module: "Studio runtimes/pi_scene_transaction 与 pi_scene_review_prompt"
  public_entry: "创作、审读、修订提示及原素材缓存"
  variation_point: "把内心的动态变化与环境回返写进生成；审读只对有证据的损害返修；角色坏台词可删选不可代改"
  inputs: ["SceneBrief", "角色与环境材料", "候选正文", "审读意见"]
  outputs: ["可保留人物声音且不压缩心理的正文候选"]
  invariants: ["不设心理段落或修辞数量门禁", "软字数服从一级归属", "修订不代角色发言"]
  allowed_dependencies: ["Engine public/literary", "现有场景交易合同"]
  forbidden_dependencies: ["新增 Canon", "固定文风模板", "审美计数硬门禁"]
  tests: ["提示合同", "原素材传至审读", "真实短场景", "架构审计"]
  rollback_unit: "Studio prompts/transaction 提交"
  documentation: ["本文件"]
```

## 2026-09-24：纠正“多给导演约束便能提高多样性”的推论

用户指出，多样性的关键不是让导演再细化角色的语言、心理与逐轮任务，而是给角色**事实和情节底线内的自主性**。前述检索不能证明“增加约束会改善文风”；[IBSEN](https://aclanthology.org/2024.acl-long.88/)等只说明导演—演员协作可以维持总体情节方向，[角色按时间顺序模拟再改写的研究](https://aclanthology.org/2025.in2writing-1.9/)也不等于本项目中逐结果催交更自然。对此修正工程假设：导演提供起始局面、角色已知与不可越过的事实、场景最终必须成立的结果；人物自行决定策略、语言、行动、沉默及何时让关系发生变化。固定结果不等于给定台词，也不等于每轮必须交付结果。

当前 `scene-relay-plan/v1` 仍有危险：`m1..m4` 与 `speaker` 容易在运行层变成固定轮流发言表；`pending_outcome` 被称为“本轮待兑现”，会把人物推成完成任务的工具。因此接力实现不得按里程碑机械轮询角色，也不得每轮做结果审查或催同一句话。先让角色基于对方真实公共言行开放互动；情节结果只作为**场景边界**和必要时的方向提示，允许本轮抵抗、回避、提出条件或没有外显反应。仅在一个自然互动片段结束后核对既定结果；缺口先判断是否该改变外部处境或再邀请原角色，而不是自动重复结果要求。若已锁 SceneBrief 无法在人物逻辑内兑现，应报告冲突，不让主创伪造角色言行。角色可自由形成语气、话题、非证据性的微动作；不能把未经来源支持的物证、过去、世界规则变成事实。这是控制权边界，不是新的文风 lint。

验证时须与现有提示在同一场景和模型上比较：去名对白的人物可辨性、重复职业/流程话术比例、角色主动改变互动方向的次数、主创保留角色原句的比例，以及事实错误和剧情完成率。没有对照结果前不宣称“自主性方案”已经解决文风。

忽略目录里的同题 A/B（`build/scene-performance-e2e/autonomy_prompt_probe.py`，同一 DeepSeek 模型、周鹤面对同一段已发生公共对话）显示了不稳定性：首轮旧的“本轮待兑现”让他立即给出节目次序并自纠，却编出了雪、听众来信、金婚点歌等未确认事实；改成场景边界后，他反问、岔开，未在这一轮完成自纠，但仍编出台标和天气预报的顺序。追加“允许主观误记、不把未定细节写成确凿记忆”后复跑，新旧提示仍都可能编造节目次序，新提示也可能立刻自纠；说明文字上的“自主”还不构成稳定干预。第三次加了**暂不告知角色剧情结果**的开放回合，周鹤先要求时间回忆、没有报具体节目顺序，但也尚未推进到自纠。三个单轮非盲样本不能证明总体文风更好。较有希望的工程变量是*剧情结果披露的时机*与真实对手反馈，而非继续堆叠自主口号；后续须以连续互动检验剧情完成、人物辨识和无根据实写之间的权衡。角色可以说谎或误记，但私有思绪不应把没有来源的节目细节升级成确定记忆。

```yaml
module_change_packet:
  objective: "把接力提示中的本轮交差式结果要求改为场景级底线，为角色留下实际选择空间"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_relay_plan_prompt、render_relay_context、render_actor_scene_prompt"
  variation_point: "仅 opt-in 接力提示；默认整场调用不变"
  inputs: ["已确认 SceneBrief", "角色自己的声音和已知事实", "已发生公共言行"]
  outputs: ["场景级剧情边界与开放式第一人称角色提示"]
  invariants: ["不新增事实", "不把结果当已发生", "不规定每轮台词、动作或完成义务", "默认路径不变"]
  allowed_dependencies: ["现有 Engine 纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["接力提示不再称本轮待兑现", "仍保留结果来源核对", "角色可拒绝或沉默", "公共日志无私人冲动"]
  rollback_unit: "独立 Engine 提示提交"
  documentation: ["本文件"]
```

## 2026-09-24：自然互动后的场景核对合同

上一轮 A/B 显示，把剧情结果改称“场景边界”仍不能稳定改变角色行为；因此下一工程批次不继续给导演加细任务，而是把结果核对移到角色真实接力之后。这个核对只回答已有结果是否有一级角色素材支持，不评价措辞，也不决定谁下一句该怎么说。`missing` 和 `uncertain` 留给 Studio 编排下一段互动；不能当作强制角色立刻服从的台词命令。`private_impulse` 仅可证明原本就是内在认知的结果，不能证明可见行动或说出口的承认。

合同测试通过后，用同一 Pi Worker 主创模型做了两次隔离试探（`build/scene-performance-e2e/relay_scene_check_probe.py`）：人物心里想“信是我拿的，我该承认”、口中只说“你先让我想想”时返回 `missing`；补上该人物真正说出的“信是我拿的”后返回 `fulfilled`，且证据指向那条发言。这证明该小样本中的外显/内在区分有效，不证明长场景语义核对已经可靠，也不评价语言风格。

```yaml
module_change_packet:
  objective: "开放角色互动后，按 SceneBrief 已锁结果核对一级角色素材是否真的覆盖场景变化"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_relay_scene_check_prompt、parse_relay_scene_check，经 public/literary.py 导出"
  variation_point: "独立 scene-relay-check/v1；不改正式 Gate、静态 lint 或默认候选路径"
  inputs: ["scene-relay-plan/v1", "按发生顺序的一级角色条目"]
  outputs: ["每个 milestone 的 fulfilled/missing/uncertain 与条目证据"]
  invariants: ["只核对剧情结果", "未满足不补造角色言行", "私有思绪不能证明可见行为", "不写 Canon/正文"]
  allowed_dependencies: ["Engine 场景纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["结果与计划一一对应", "证据 ID 必须属于原角色", "外显与内在结果区分", "缺口不被填补"]
  rollback_unit: "独立 Engine 合同提交"
  documentation: ["本文件"]
```

导演的 `actor_task` 必须按作品事实而不是通用模板组织：这一场面对谁、当前已知/误知、不得外泄的事、压力沿节拍怎样变化。它**不得**给“语气该怎样变”“要用什么词”“先做哪个动作”之类配方；稳定声音来自人物资产，具体话语和微观行为由演员在事实底线内自主选择。主创即使有清晰戏剧目的，也只锁结果和边界，不预写标准台词。演员输入应像第一人称处境，而不是把几十项表格全文交给角色逐条复述；结构信息先由引擎校验，再选择性渲染成沉浸式提示。

导演的 `environment_task` 只给已确认空间事实、视角可感知范围，以及哪些地理、天气、器物、历史未获来源支持。环境 Agent 自行选择视觉或非视觉线索、停留时间、句长与修辞；可选择零到数段，不强制每个节拍、每种感官、每段固定字数，也不创作人物动作、对白或心理。主创可拒绝环境候选，但不能把新事实从候选中直接升级为世界设定。

“全部人物发言与行为先由角色 Agent 生成”需要超越 v3 的四个关键节拍：导演先规划足以覆盖本场的交互槽位；每名角色一次生成自己跨槽位的对白和行动意图，允许一个槽位含连续数句或行动，并保留与其他角色交错的顺序 ID。主创不得临时自造额外人物对白或行为。正文必须回传所采用的演员条目及其片段映射；仅有模型自报不算证明，还要检查正文中的对白和关键行为有无无来源内容。若场景需要临时新回合，先由角色 Agent 补演，再由主创续写；效率目标是通常每人一轮，补演是异常路径。

## Module Change Packets

```yaml
module_change_packet:
  objective: "主创生成本场角色处境与环境事实边界，角色/环境写法由一级 Agent 自主决定"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "ScenePerformancePacket/v4 的渲染与解析"
  variation_point: "actor_tasks、environment_task、完整交互槽位的版本化 DTO"
  inputs: ["SceneBrief", "人物声音投射", "文风参考", "已确认来源"]
  outputs: ["可校验的角色/环境任务", "演员/环境提示输入"]
  invariants: ["剧情与事实由主创锁定", "不从候选提升 Canon", "主创任务不预写标准对白", "没有硬审美门禁"]
  allowed_dependencies: ["现有 Engine 场景/资产公开合同"]
  forbidden_dependencies: ["Studio 私有实现", "Provider SDK", "项目持久化"]
  tests: ["任务字段边界与人物/槽位一致性", "角色沉浸式渲染", "环境视角渲染"]
  rollback_unit: "opt-in 场景候选机制的一次可运行提交"
  documentation: ["本文件", "试跑评估记录"]
```

```yaml
module_change_packet:
  objective: "让主创交接保留一级角色/环境生成来源并可检查覆盖"
  primary_module: "Studio runtimes/scene_performance + pi_scene_transaction"
  public_entry: "scene_performance_materials、render_scene_create_prompt"
  variation_point: "候选缓存与正文编排的来源收据；缺口时补演/实验回退"
  inputs: ["ScenePerformancePacket/v4", "角色/环境候选"]
  outputs: ["按槽位的素材", "正文与来源映射"]
  invariants: ["正式正文只由主创提交", "候选无写权限", "失败不得伪装成角色覆盖成功", "默认路径行为不变"]
  allowed_dependencies: ["Engine public/literary.py", "现有 RoleConversationGateway"]
  forbidden_dependencies: ["Engine 内部 import", "第二套 Canon 写入", "任意系统提示注入"]
  tests: ["全槽位/多人物交错", "额外对白和行为的覆盖缺口", "缓存/回退", "主创最终取舍"]
  rollback_unit: "opt-in 场景候选机制的一次可运行提交"
  documentation: ["本文件", "试跑评估记录"]
```

```yaml
module_change_packet:
  objective: "环境 Agent 以本场视角和语言运动创作，而非固定字数的通用风景段"
  primary_module: "workers/pi-worker conversation"
  public_entry: "conversationSystemPrompt(environment-writer)"
  variation_point: "静态环境写手职责与 v4 本场环境任务配合"
  inputs: ["白名单 conversation_role", "Engine 渲染的本场任务"]
  outputs: ["非权威环境素材"]
  invariants: ["tools=[]", "无项目写权限", "单轮", "不生成角色对白/行为", "事实边界优先"]
  allowed_dependencies: ["现有 Pi conversation profile"]
  forbidden_dependencies: ["任意项目文本注入系统提示", "项目工具"]
  tests: ["环境系统提示", "其他 profile 回归"]
  rollback_unit: "与 Engine/Studio 同一可运行提交"
  documentation: ["本文件"]
```

## 2026-09-24：角色接力的时间事实合同

v8—v10 对照表明，整场独立预演与“未来必发生的剧情被写成已发生事件”共同制造虚假的互动：先出场者会回应后出场者尚未说过的话。下一批先在 Engine 收敛角色提示合同：公共日志只收此前由一级角色实际交付的 `spoken` 与 `first_person_action`；剧情底线须是 SceneBrief 中可逐字核对的既有事实，明确标作**待兑现，不代表已经说出口**；当前角色保留说法、停顿、行动和是否需要额外话语的自主权。v11 用正式合同复跑后又出现抢跑：周鹤在尚未轮到漏歌的开场就自行纠正，沈照月凭空提到“我姐”。原因之一是角色仍收到含完整未来目标的 SceneBrief。接力模式须只给当下场景信息及从原始 SceneBrief 逐字核对的、该角色可知的少量事实；未来结果只在分配给当轮角色时出现，不能通过完整目标或 Canon 列表提前泄露。这仍是事实视野，不是说话方式处方。该批仅建立稳定提示与验证接口，不宣称整条 runtime 接力链已打通。

v12 将未来目标从早期角色提示中移走，仅保留当下地点、人物、逐字可核的角色已知事实、实际公共日志与本轮结果。两次同配置试跑（`build/scene-performance-e2e/v12-knowledge-relay/` 和 `v12-knowledge-relay-repeat/`）均未再出现 v11 的开场提前承认和“我姐”错误；周鹤一次说“店关了，人还在。街又不会自己走”，另一次借“口淡”回避节目记忆，声音比逐项念稿更有变化。但仍会虚构节目环节、随身物件或未确认的过去；沈照月最终一次只站起身，没有明确走出场景。两次样本只能证明时间视野修复值得继续，不足以证明稳定去 AI 化。下一批应由 Studio 编排真实接力并在缺少既定离场等结果时请**原角色**续演，同时让主创把角色主观声称与世界事实分开；不能让正文作者替她添上未由角色 Agent 生成的动作。

```yaml
module_change_packet:
  objective: "角色在接力中只把真实公共言行当已发生，剧情底线来自 SceneBrief 且不变成台词模板"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_actor_scene_prompt"
  variation_point: "可选 public_log、pending_outcome、knowledge_quotes 与每轮条目上限；现有整场调用不变"
  inputs: ["SceneBrief", "人物声音投影", "已解析的一级角色公共日志", "SceneBrief 原文中的角色已知事实及待兑现结果"]
  outputs: ["带时间事实区分的一级角色提示"]
  invariants: ["不改 Canon", "不把未来结果写成已发生", "只对应角色生成自己的言行", "不增审美门禁", "默认路径不变"]
  allowed_dependencies: ["现有 Engine 场景纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["日志仅含 spoken/action", "未来目标不泄漏进早期角色视野", "越界说话者与伪造结果拒绝", "默认整场提示兼容", "同题真实模型接力对照"]
  rollback_unit: "独立 Engine 合同提交"
  documentation: ["本文件"]
```

### v6 真实试跑反证与 v7 减法

2026-09-24 在同一《shoreline》第二场、同一 DeepSeek 模型上完成 v6 一级候选链（忽略目录 `build/scene-performance-e2e/v6-live/`，未写正式正文）。导演选出了歌名、被删名字、要求者身份、到场先后四个留白；两名角色分别交付 4、11 条言行，歌名和人名没有被编造。但台词仍主要在窗口／稿面流程中回旋；沈照月补出碗、筷筒、杯子和“登记满三十天”的旧物，周鹤补出潮湿天气、节目单中间节目的具体次序、手套与表。特别是“物主留空只能暂存”已在 SceneBrief，角色仍说成“登记满三十天没人认领”：长篇事实提示没有转化为可靠约束。环境写手自造收音机、价目表、灯泡、路上的纸角等；价目表上“包”“粥”两个**非对白引号**被当前解析器误判为对白，导致整份环境候选跳过。

这次反证不支持“再给导演增加更多未定槽位”作为文风主路线。留白可保留为少量关键事实的提醒，但角色的私人压力、关系误判和环境感知焦点已在资产／SceneBrief／来源中，导演再次转写它们会重复放大程序性语言，还会让未经证实的“同桌或邻座”等安排获得任务单权威。v7 先作减法：导演只给情境锚点和少量事实留白；每名演员从自己的档案、眼前情境、已知/误知中选择语言和行为；环境写手自行决定是否观察与何时写。不得把“鼓励自主”理解为角色有权制造新证据，也不把未经证实的普通质感逐项列成禁令。环境解析器只拒真正的对白形式，容纳标牌文字等带引号的环境描写。必须对比同题真实输出及来源错误，不能因候选数增加就宣称成功。

v7 同题复跑（忽略目录 `build/scene-performance-e2e/v7-live/`）也**未达标**。导演把带袋子赴会、带走“签名栏空白”等无来源安排写成情境锚点；两名角色分别交付 9、7 条，但一个凭空拿出登记簿，另一个凭空拿出旧节目单，互相预想对方的道具和台词，仍满是窗口／稿面流程。环境候选四段虽不再被标牌引号误杀，却堆出雨棚、修车铺、风铃、挂钟快“七八分钟”等与情节无关的实写。**减任务字段消除了部分导演占有，但没给角色真实的对手反馈；独立整场预演会迫使每人猜另一个人做了什么。** v7 仅保留 opt-in 实验，不作文风改善结论。下一步以角色接力为主要对照，让角色看见对方已实际说出的公共行为，再自主反应；主创只在检查既定情节缺口时决定是否继续接力或换外部局面，不替角色写标准台词。若仍程序化，要回到人物资产本身检查是否把职业话术重复写成了唯一语言资源。

新检索只能作为机制线索，不是本项目效果保证：[《Multi-Agent Based Character Simulation for Story Writing》](https://aclanthology.org/2025.in2writing-1.9/)明确区分按时间顺序由人物模拟戏剧过程、以及之后的叙述改写；[StoryBox](https://ojs.aaai.org/index.php/AAAI/article/view/40288)用动态环境中的角色互动产生事件，而非单向填细脚本。[IBSEN](https://aclanthology.org/2024.acl-long.88/)的角色保留对话日志并根据真实历史回应，但它的导演还生成细对话脚本；本项目只借鉴实际互动与剧情目标检查，不照搬其逐轮台词指令。上述论文研究设置不同，必须用本项目同题实验验证。

随后又对同一面馆场景做三次仅写入忽略目录的角色接力对照：`v8-relay/` 让六次一级角色调用读取前人真实公共言行，接话比整场独立预演连贯，但仍虚构歌曲《东方红》、约五分钟与节目次序；`v9-compact-relay/` 只给当场相关事实和简短人物处境，具体歌曲未再命名，但仍虚构节目次序，而且“周鹤已漏歌”的未来节拍被先调用的沈照月误当作已发生事实；`v10-compact-relay/` 把节拍改成当前局面，只将真实公共日志标为已发生，按必要时刻把**既定剧情结果**交给对应角色自主兑现。周鹤这次以自己的话漏歌后纠正、承认删点名；沈照月回应“你记得”，比流程化解释更有张力。但周鹤仍称当天下雨（来源未确认），沈照月最后没有离场。**结果底线与微观表演可分离；若结果未兑现，应由对应角色继续演，而非导演预写标准台词，也不能把角色主观回忆升格为 Canon。** 目前仅为一场、一模型、小样本观察；不能推出稳定的风格提升。下一工程候选是“已发生公共日志 + 待兑现剧情结果 + 角色自主回应 + 缺口定向续演”，并检查角色资产是否把职业口癖写成唯一语言资源。

```yaml
module_change_packet:
  objective: "减少导演重复规定角色心理和环境焦点，修复环境标牌引号误判"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "parse_performance_plan、render_actor_scene_prompt、render_environment_prompt、parse_environment_material"
  variation_point: "scene-performance/v7 的 beats + unknown_slots；角色/环境自主选择微观表达"
  inputs: ["SceneBrief", "已有人物投影", "确认来源", "导演情境锚点"]
  outputs: ["不带 actor_tasks/environment_task 的计划", "一级角色/环境提示", "环境非对白引号合法"]
  invariants: ["剧情和 Canon 边界不变", "每位角色一级生成自己的言行", "不增文学硬门禁", "默认路径不变"]
  allowed_dependencies: ["现有 Engine 纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["导演不能暗置角色任务", "角色/环境保有留白", "真正对白仍拒绝、标牌引号接受"]
  rollback_unit: "v7 opt-in 合同与 adapter 联动提交，可整体回滚"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "运行层把 v7 情境与事实底线交给全部一级创作 Agent，不再转递导演的心理任务"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "scene_performance_materials"
  variation_point: "opt-in 调用与缓存版本"
  inputs: ["Engine v7 plan", "SceneBrief", "角色声音投影"]
  outputs: ["每角色整场候选与独立环境候选"]
  invariants: ["全部在场人物均获一级调用", "主创不补造角色言行", "默认关闭", "缓存不复用旧合同"]
  allowed_dependencies: ["Engine public/literary.py", "现有 RoleConversationGateway"]
  forbidden_dependencies: ["Engine 内部 import", "新的项目写回路径"]
  tests: ["运行层无导演心理任务", "同一留白到达角色与环境", "同题真实模型对照"]
  rollback_unit: "v7 opt-in 合同与 adapter 联动提交，可整体回滚"
  documentation: ["本文件"]
```

## 分阶段验收（早期路径与当前修正）

早期第一阶段把导演生成的角色、环境任务落地；v6/v7 同题对照已证明，这一路径会占用角色自主性，现不再扩张。当前第二阶段改为角色基于真实对手言行接力、必要时由对应角色补演，并给主创增加来源收据；主创不得直接自造角色发言/行为。第三阶段至少用三类不同场景、两种语言风格、多名人物做盲辨人物、环境辨识度、事实错误、AI 套语/解释尾句、调用数与耗时对比；逐处看主创是否保留或抹平演员声音。只有覆盖审计和阅读证据都成立，才考虑默认开启；否则保持 opt-in 并继续修正。环境与人物改进应在生成阶段落实，违禁词、标点和硬事实审查继续存在，但不把抽象“去 AI 味”加成词表门禁。

## 第一阶段真实试跑与路线修正

2026-09-23 用《shoreline》旧控制室场景、实际人物声音投射、`deepseek/deepseek-v4-flash` 试跑了导演→两名演员→环境的 v4 候选链。首次导演输出给三名人物任务，但只在节拍中安排两名说话者；解析器只允许说话者任务，导致安全回退。合同改为每名参与者一份本场处境，重试后结构通过：叶归舟一轮生成两个节拍，沈照月一轮生成一个节拍，周鹤没有被调用。这再次证明四节拍机制无法履行“全部角色发言与行为先由演员生成”。

更重要的是，导演虽未预写台词，却把每拍“必须说什么”和他人不能如何回应写成了细密的脚本。叶归舟候选继续解释检修结论，沈照月候选继续宣布登记流程，还新增未经来源确认的登记板、编码和控制面板动作。环境候选几乎把四拍写成等量设备说明，凭空补了灰尘、铁环、磨痕、灯管和吸音板；其中“旋钮周围异常干净”尤其像新物证，不能入正文。结构成功不等于文风成功。

因此下一轮不再给导演更多可规定演员语言/动作的字段，而要减少导演对微观互动的占有：剧情必须成立的事实可以由物证和叙述承载，不必都塞进人物口中。演员应获得锁定事实及可自主选择的反应空间；环境应有非情节质感的创作自由，但新线索/关键物证必须有来源。需要对照更自由的整场表演形式，而非沿当前任务单继续加禁句。当前试跑资料保存在忽略目录 `build/scene-performance-e2e/pi-conversations-v4/` 和 `scene-transactions/v4-probe/`；不属于正式作品或 Canon。

## 2026-09-24：纠正“更多导演约束带来多样性”的误判

用户指出，关键是底线内的自主性，而非导演再为每个角色指定更多语言特征。这个纠正与试跑一致：在第二次试跑中，导演把四拍写成了逐项检修流程，却只指定叶归舟在一拍发言；沈照月和周鹤没有获得演员调用。叶归舟遂补造万用表、断路器辅助接点、继电器动作痕迹、欠压脱扣等未获来源支持的设备事实；环境写手同样补造灯、屏幕等现场物件。**减掉表面上的文风禁令，若仍由导演规定每回合说什么、做什么，并不给角色真正的自主性；同时，允许选择自己的表达也不等于允许创造世界事实。**

[Mateas 的交互戏剧研究](https://www.cs.cmu.edu/afs/cs/project/oz/web/papers/CMU-CS-97-156.html)把控制粒度分成直接规定角色动作、控制场景方向、控制更大情节点；场景级控制保留了角色活动的变异空间。它是架构启发，不是本项目质量效果的证据。下一轮采用以下职责分界：

| 谁有决定权 | 锁定什么 | 可自主选择什么 |
| --- | --- | --- |
| SceneBrief / 唯一主创 | 已确认的世界事实、必须成立的戏剧变化、禁止越过的结果 | 为这一场挑出少量外部情境锚点；不代写人物台词与微动作 |
| 一级角色 Agent | 不改人物背景、已知/误知与情节底线 | 何时开口或沉默、说多少、如何绕开或抵抗、身体怎样回应；同一角色一轮连续表演全场 |
| 一级环境 Agent | 视角、已确认地点/物件与未知事实边界 | 选择感知焦点、段落有无与长短、意象和句群节奏；不能把新物证写成事实 |
| 唯一主创正文阶段 | 组织演员和环境候选、验明来源、达成场景结果 | 衔接与取舍；不能补造未经一级角色 Agent 生成的角色言行 |

具体工程变更不是在现有 `speech_act / information / response_boundary` 上再增字段，而是逐步**删去这些逐拍导演命令**，改为“情境锚点 + 人物私有处境 + 来源可追溯事实底线”。参与者即使尚未被导演指定发言，也必须各自获得整场一级演员调用；每个人可在锚点间自行分配话语和行动，而不是每拍被迫填一句。为了防止“自主性”滑成事实幻觉，现场可操作物和可断言的证据另由已有来源供给，不接受导演或演员新写的技术细节自动变成事实。先对三种情境做角色候选的盲辨与事实错误对比，再考虑正文强制来源收据；不把这些软文学判断做成硬门禁。

文风参考不再进入导演阶段：导演只管理场景条件，语言资源应直接面对表演者和环境写手，不能先被导演转译为逐拍话术。当前角色 Prompt 尚未直接挂载参考选段，这是待验证的下一项形成机制，不应宣称参考语料已在一级角色表演上生效。

### v5 同场试验结果与下一次路线切换

本地 opt-in 原型删掉导演的逐拍 `speaker / speech_act / information / response_boundary`，将 beats 缩成情境锚点；三位参与者各得到一次覆盖整场的角色调用，返回可在任一锚点生成多条言行、也可不作反应的来源条目。定向合同测试通过。在同一《shoreline》控制室试跑中，沈照月、周鹤、叶归舟分别交付 9、9、7 条，环境写手交付 3 段，角色覆盖从之前仅调用一人提升为三人，但**表现未达标**：台词仍大量复述登记、摘录、检修规程；叶归舟又引入万用表、钥匙登记板等未核实现场物件；环境继续补出纸带、拨杆痕迹等似乎会成为新线索的细节。缓存保存在忽略目录 `build/scene-performance-e2e/v5-live/`。这是候选链试验，不是正式正文或品质验收。

额外对同一角色做了两次开放式第一人称试写：自由连续文本比逐条 `entries` 有更自然的停顿、转向与语言起伏，但仍可能照搬人物卡中的签名句；移除稳定声音字段后，职业腔并未可靠消失，反而出现替其他人物编对白、雨伞、精确时长、带子所在位置与既定事实冲突。**不能把自由文本直接接入正文；结构化条目也不是创造多样性的充分条件。** 当前原型保持默认关闭，下一步不再微调“说话要更生动”一类提示，而是试验“演员先自由排演、再从自己的排演中交付可追溯言行”的单调用载体，并给现场事实一个与角色选择分离的来源包。主创只提供情境和结果底线，不审美裁判每句话；缺乏事实支持的排演可弃而不升为 Canon。该候选须与现有条目式及单主创式同题比较，特别记录越权代演、事实幻觉和去名对白辨识。未拿到这些证据前，不开启默认、不发布文风已解决的结论。

“每角色一轮整场”原本是效率偏好，不是艺术或真实性公理。它迫使角色预想其他人物尚未说出的话，开放式试写出现替别人发言正是这个代价的信号。如果自由排演加来源包仍不能兼顾角色独立和事实一致，改试**小规模角色接力**：主创只给共同情境，某角色给出自己的言行，下一个角色看到已发生的真实言行后回应；必要时回到前一角色补一轮，环境写手仍独立观察。接力轮数由场景冲突和收益控制，不能把轮流发言写成新的固定模板。所有角色言行仍由对应一级 Agent 产生，主创仅编排。比较指标须同时包括新增调用成本与人物语言的真实互动收益。

工程回归：当前原型保持 opt-in / 默认关闭；Python 全量 1539 项通过（1 项跳过），Pi Worker 106 项通过，架构审计与 `git diff --check` 通过。上述结果只证明实现与既有功能未出现已测出的回归，**不证明文风改善或事实边界已可靠守住**。

## 2026-09-24：同场接力对照与 v6 留白合同

《shoreline》第二场面馆试跑：现有整场独立表演让两位演员各给 6 条言行，周鹤擅自给遗漏歌曲命名、定时长，环境写手补出具体钟点、其他顾客和未获确认的店内陈设。六轮依次交接**真实对方台词**后，人物接话更连贯，且没有给歌曲命名；但两人仍围绕“登记流程／稿面流程”打转，未自发完成场景必须发生的承认。把结局直接明示给周鹤后虽完成事实揭示，台词却像交付义务；改为只给沈照月“冒险施压”则又诱出未经来源支持的替签、签到表等新线索。接力不是自动解药，也不能靠导演一味命令角色坦白。

单独给同一角色补一份**本场明确留白**（歌曲名字、时长、精确节目次序、尚无来源的现场道具等）后，角色没有再编歌名或时长，但仍补出公文包等物件。因此这是缩小一类事实幻觉的信号，不是完成证明。试跑原始会话位于忽略目录 `build/scene-performance-e2e/v6-relay/`，正式作品与 Canon 未变。下一步让唯一主创在导演阶段选择真正未定、又容易被模型“具体化”的少量事实槽位，分别贴近角色和环境的交付请求；槽位只写**不能擅自断言的内容**，不规定说话方式或微动作。若留白仍漏检，后续再设计来源收据，不把审美判断硬编码为 lint。

这一划分与 [SillyTavern 官方 World Info](https://docs.sillytavern.app/usage/core-concepts/worldinfo/)的按情境插入知识而非永久塞满人物卡的做法相近；其文档也明确注入信息不保证模型使用。2026 年一篇[角色扮演预印本](https://arxiv.org/html/2606.25632)把“知道了不该知道的事实”和“固定人物卡压平声音”分列为两种问题，并使用人物视角限定事实、随情境变化的行为模式；它研究的是书本角色模拟，不能直接证明本项目有效，也不支持照搬其完整三层记忆架构。本项目先做更小的来源／留白分离，再用实际小说候选验证。

```yaml
module_change_packet:
  objective: "让场景角色与环境提示携带主创选出的明确未定事实，不占用角色的语言和行动自主权"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "parse_performance_plan、render_actor_scene_prompt、render_environment_prompt"
  variation_point: "scene-performance/v6 的 unknown_slots，纯提示边界而非审美 Gate"
  inputs: ["SceneBrief", "表达/人物投影", "已有来源", "导演返回的任务单"]
  outputs: ["有界、可检视的未定事实槽位", "角色与环境生成提示"]
  invariants: ["不改 Canon", "不代角色决定发言和动作", "违禁词/标点等原有硬审查仍在", "默认路径不变"]
  allowed_dependencies: ["现有 Engine 场景纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["unknown_slots 校验", "角色与环境提示可见留白", "过量与重复槽位拒绝"]
  rollback_unit: "独立 Engine 合同提交"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "将同一份留白合同传到每个一级演员与环境写手并做同场试跑"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "scene_performance_materials"
  variation_point: "opt-in 候选缓存版本与本场任务的传递"
  inputs: ["Engine v6 plan", "SceneBrief", "角色声音投影"]
  outputs: ["每角色一轮候选、环境候选及可追踪事件"]
  invariants: ["全部在场人物仍需一级调用", "候选无项目写权", "失败不得假报来源覆盖", "默认关闭"]
  allowed_dependencies: ["Engine public/literary.py", "现有 RoleConversationGateway"]
  forbidden_dependencies: ["Engine 内部 import", "新的 Canon 写回路径"]
  tests: ["runtime 传递同一留白", "缓存版本隔离", "真实模型同场复跑"]
  rollback_unit: "独立 Studio adapter 提交"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "让自然互动后的双方演员看见同一个未完成场景边界，不只对结果归属者催交"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "mode=relay 的接力回合编排"
  variation_point: "初始自由回合不变；缺口后的对手回合也收到尚未发生的边界"
  inputs: ["核对出的第一个未完成结果", "现有角色公共日志"]
  outputs: ["双向反应所需的非强制戏剧方向"]
  invariants: ["不把结果当角色知识或已发生事实", "不写具体对白动作", "不泄漏私念", "失败仍阻断未获支持的正文"]
  allowed_dependencies: ["Engine public/literary.py", "现有角色调用"]
  forbidden_dependencies: ["Engine 内部 import", "新 Provider 抽象"]
  tests: ["初始回合不见终点", "对手缺口回合可见同一终点", "角色私念不外泄"]
  rollback_unit: "独立 Studio 接力适配提交"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "让 Pi Worker 第一人称画像与普通现场细节的候选权限一致"
  primary_module: "Pi Worker conversation profile"
  public_entry: "conversationSystemPrompt(character-actor)"
  variation_point: "由一概禁止新道具改为区分生活质感与证据事实"
  inputs: ["同轮角色表演任务单"]
  outputs: ["仍无工具和写权限、但可自由选择非证据现场细节的系统画像"]
  invariants: ["不新增核心物证、身世、规则或 Canon", "不替他人发言行动"]
  allowed_dependencies: ["现有 Pi Worker conversation"]
  forbidden_dependencies: ["Engine 内部", "项目文件写入"]
  tests: ["系统画像断言", "Pi Worker check"]
  rollback_unit: "独立 Worker 提交"
  documentation: ["本文件"]
```

## 2026-09-24：接力导演只选既定结果，不编排台词

目前已验证的接力提示合同尚缺少能由运行层调用的主创任务单。新任务单不再生成逐拍人物心理、台词或动作，也不把尚未发生的剧情写成“场景现状”。主创只从 SceneBrief 中逐字挑选最多四个必须在本场兑现的原子结果，指明承担角色与顺序；角色轮到该结果时才看见它。角色可独立选择措辞、延迟、抵抗或短暂沉默，但若结果最终未出现，须请原角色续演，不让正文作者代写。每人可见的补充事实只准选 `incoming_handoff` 中已经发生的内容；人物私有记忆仍来自自身档案。环境写手独立在真实公共互动之后取景，不接受主创逐项指定光、声、器物。源引验证只能防止凭空新增任务事实，不能证明文学表现优良。

在第二场实际模型试填中，首版主创把“漏歌并纠正”和“承认删点名”合在同一条长源引里，这会让角色在一轮抢先完成两个本应由互动隔开的变化。改成“最短完整事实分句、分号连接的结果必须拆开”后，主创返回四个有序且来源可核的结果：漏歌纠正、承认删点名、沈照月认定主动回避、离场不亮带子。两次原始会话保存在忽略目录 `build/scene-performance-e2e/relay-plan-live*/`。仍有两项局限：主创给沈照月的开场知情摘录过长，并把叶归舟检修条真实性列为本场留白；结构校验不等于选材精准，后续须看接力正文是否因此受干扰。

```yaml
module_change_packet:
  objective: "给接力运行层一份只含已锁剧情结果及角色既有知情的来源可核任务单"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_relay_plan_prompt、parse_relay_plan，经 public/literary.py 导出"
  variation_point: "独立 scene-relay-plan/v1，不替换默认 v7 整场计划"
  inputs: ["SceneBrief"]
  outputs: ["有序、逐字来源可核的里程碑", "每角色已发生知情", "少量事实留白"]
  invariants: ["不规定角色微观言行", "不把未来结果当已发生", "不新增 Canon", "默认路径不变"]
  allowed_dependencies: ["现有 Engine 纯合同与 relay_context"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["公共 API", "结果来源与角色核对", "知情只来自 incoming_handoff", "重复/超量拒绝"]
  rollback_unit: "独立 Engine 合同提交"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "在 opt-in 模式串联一级角色实际公共言行、原角色缺口续演和独立环境候选"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "scene_performance_materials 的 relay 模式"
  variation_point: "仅新模式的缓存及调用序列，不改默认整场模式"
  inputs: ["Engine relay plan", "SceneBrief", "角色声音投影", "Pi tool-free invoke"]
  outputs: ["按发生顺序的来源条目", "环境候选", "失败/缺口事件"]
  invariants: ["所有角色言行须由对应一级角色生成", "主创只编排候选", "不写项目或 Canon", "失败不伪装成功", "默认关闭"]
  allowed_dependencies: ["Engine public/literary.py", "既有 RoleConversationGateway"]
  forbidden_dependencies: ["Engine 内部 import", "第二套 Gate 或正式写回"]
  tests: ["两角色及三角色接力", "未达标时只问原角色", "无私有思绪泄漏", "环境独立", "真实模型及连续场景"]
  rollback_unit: "独立 Studio adapter 提交"
  documentation: ["本文件"]
```

2026-09-24 修正该 Studio 批次的编排原则：先让在场角色各有一次不披露未来结果的开放互动，之后按整段公共言行做场景核对。若尚缺 SceneBrief 已锁结果，只向归属角色披露一个场景级边界，并让另一角色根据其真实回应接续；每段再核对一次，而非每个角色回合追单。角色可以抵抗，不能由主创代说或假报完成。接力模式属于显式 opt-in 实验，失败应停止该模式下的正文生成，不回退到单主创偷偷补全。调用上限只限制费用和日志容量，不指挥话语数量或具体行动。

首次真实接力试跑使用忽略目录 `build/scene-performance-e2e/project-two-scenes` 的第二场、已存在的 DeepSeek 配置，结果**失败并停止正文生成**：结构化 `SceneBrief.location` 为空，导演虽然在 `scene_function` 中能看到“旧街面馆”，演员提示却只拿到空地点与上一场窗口登记交接，于是十回合都在窗口/登记簿话题里打转；全部剧情结果仍是 `missing`。仅在忽略试跑脚本中把来源可核的地点补为“旧街面馆”再试，角色已说到面碗，但第一句仍是“旧广播站那批东西有没有人认领”，后续又回到登记、移交、检修条和月份，仍无漏歌或删点名承认。原始调用与候选保存在 `build/scene-performance-e2e/relay-runtime-live/`、`relay-runtime-location-live/`。这说明失败不只在运行调度：场景开端的**私人会面处境**没有传给角色，上一场交接与人物卡中的程序习惯反而成为最显眼的当前事件。下一批要补来源可核的“开场处境”而非导演台词，并把交接标明为过去，不是现场道具；随后重跑同题，不应继续盲目增加轮数或催促次数。当前 relay 模式保持 opt-in，不能作为已通过的文风方案。

```yaml
module_change_packet:
  objective: "从 SceneBrief 选出可逐字核对的当前会面处境，避免角色把上一场交接误演成此刻场所"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "scene-relay-plan/v2 的 opening_situation 与 render_actor_scene_prompt 的可选 opening_situation"
  variation_point: "接力提示读取开场锚点；默认整场候选保持不变"
  inputs: ["SceneBrief.scene_function/location", "导演只做来源摘录的 plan", "角色已发生公共日志"]
  outputs: ["来源可核的开场处境", "过去交接与当前场所分离的演员提示"]
  invariants: ["不规定具体台词、动作和心理", "不把未来结果或过去道具写成已发生", "无新增 Canon", "角色仍能自主回应"]
  allowed_dependencies: ["现有 Engine 场景纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["开场锚点来源核对", "缺失/伪造拒绝", "接力角色可见而默认路径不变", "真实同题复跑"]
  rollback_unit: "独立 Engine 合同提交"
  documentation: ["本文件"]
```

在同一第二场的真实主创试填中，v2 `opening_situation` 逐字选中了“在周鹤日常买早点的旧街面馆，沈照月以私人身份试探……”这一整句；人物已知事实仍选中完整的上一场窗口交接。前者修复了开场处境缺失，后者仍须由演员提示明确视作过去，而不是眼前登记簿。此试填只验证导演任务单可被模型生成与解析，不是角色/环境文风验收。

Studio 接上 v2 后再次在同一忽略项目试跑（`build/scene-performance-e2e/relay-runtime-opening-live/`）：面馆处境进入角色，开场即谈播音，但沈照月凭空说排班墨色不同，周鹤把收播时间说成“晚间十点整”、把墨色说成蓝黑两笔；后续又补出被划掉的名字、无编号旧物及交接程序。十回合后全部场景结果仍未由角色素材支持，系统停止正文创作。这说明开场锚点修复了地点，不修复事实来源及人物卡职业话术的占优；继续加轮数会放大无根据细节。下一实验要在同一场景对照完整人物卡与精简角色身份/欲望/关系输入，并检查已有 `sources` 是否实际到达一级角色；不以增加导演逐句要求代替事实资料。

忽略目录 `build/scene-performance-e2e/role_identity_ab_probe.py` 对同一开场做了完整人物卡+交接、核心身份/欲望+交接、核心身份/欲望且不提供交接三个版本，每版让沈照月先表演、周鹤读到真实公共回应后再表演。完整卡并非总会陷入程序腔，样本里她也能自然说“周老师，拼个桌”；精简后少提窗口，却出现两人相互等待、泛泛谈早点或完全沉默。少量随机样本不能证明哪版风格更好，但**直接删资料没有稳定增加人物辨识度**，还可能使角色行动乏力。更值得验证的是：当前角色收到的 `sources` 实际为零，`SceneBrief` 只给剧情终点而不给节目细节的已证实范围；同时 JSON 条目式交付可能让表演变成短任务回答。下一步分别检验“可追溯事实包”和“先沉浸排演再交付来源条目”两个变量，不把二者混为一次改动。

```yaml
module_change_packet:
  objective: "将 v2 来源可核的开场处境传给每次接力角色及环境写手"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "scene_performance_materials 的 mode=relay"
  variation_point: "relay 独立缓存版本升级；旧 batch 不变"
  inputs: ["Engine scene-relay-plan/v2", "SceneBrief", "角色/环境公共提示"]
  outputs: ["当前会面处境明确的演员/环境候选"]
  invariants: ["不预写台词或动作", "不把上一场道具当此刻事实", "默认路径不变", "不读 Engine 内部"]
  allowed_dependencies: ["Engine public/literary.py", "现有缓存/RoleConversationGateway"]
  forbidden_dependencies: ["Engine 内部 import", "正式项目写入", "Provider 直连"]
  tests: ["角色/环境都见同一开场锚点", "缓存不复用 v1", "同题真实模型复跑"]
  rollback_unit: "独立 Studio adapter 提交"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "在可选 Studio 运行模式中让一级角色按真实公共互动接力，再由主创组织有来源的素材"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "scene_performance_materials 的 mode=relay"
  variation_point: "旧 batch 模式保持；relay 模式拥有独立缓存版本和失败语义"
  inputs: ["Engine relay plan/check/materials 公共合同", "SceneBrief", "人物声音投影", "tool-free Pi invoke"]
  outputs: ["有全局来源 ID 的按时间顺序角色条目", "独立环境候选", "主创素材块或明确失败"]
  invariants: ["角色只生成自己的言行", "私有冲动不泄漏给其他角色/环境", "未完成结果不得进入正文", "默认关闭", "无项目或 Canon 写入"]
  allowed_dependencies: ["Engine public/literary.py", "既有 RoleConversationGateway 与缓存工具"]
  forbidden_dependencies: ["Engine 内部 import", "第二套 Gate", "Provider 专有直连"]
  tests: ["开放回合先于结果披露", "公共日志顺序与隐私", "片段核对与原角色续演", "失败阻断正文", "环境读取真实公共互动", "缓存隔离"]
  rollback_unit: "独立 Studio adapter 提交"
  documentation: ["本文件"]
```

角色可以选择自己的语言与即时动作，但已有 SceneBrief 的结果不能由主创正文阶段替角色虚构。运行层仍需要窄义、非审美的语义核对，不过应在一段自然互动之后检查整场结果，而非每轮拿单个 source_quote 追着角色催交。只把角色的私有冲动写为“想离开”不等于可见的离场；只暗示删改不等于既定承认。若有缺口，先判断是人物仍在抵抗、外部处境尚未成熟，还是确实需要请原角色续演；不得让主创代写，也不得把自动重复目标当作唯一修复路径。若仍不能在人物逻辑内兑现，接力候选不能宣称完整。该核对不评价辞藻和“AI 味”，也不取代正式 AgentReview。

```yaml
module_change_packet:
  objective: "自然互动片段结束后区分已兑现、未兑现和不确定的场景结果，避免逐轮催交"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_relay_gap_prompt、parse_relay_gap_check，经 public/literary.py 导出"
  variation_point: "场景片段结束后的结果核对；不进入静态文学 lint"
  inputs: ["SceneBrief 来源核对后的 milestones", "按真实时间排序的一级角色候选 entries"]
  outputs: ["fulfilled/missing/uncertain 与确切 entry_id 证据"]
  invariants: ["不代写角色言行", "不把 private_impulse 当外显动作", "不改 Canon", "不替代正式 review"]
  allowed_dependencies: ["Engine 场景纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["缺口检查 JSON 合同", "不明证据拒绝", "已兑现须有条目证据"]
  rollback_unit: "独立 Engine 合同提交"
  documentation: ["本文件"]
```

## 2026-09-24：接力素材交接合同

独立环境写手需要知道角色实际说过、做过什么，但不能见到 private_impulse 或把人物主张当成已证实的世界事实。唯一主创收到的角色条目须按真实调用顺序交错，而不是按人物分组；旧的“一轮连续扮演整场”说明对接力并不成立。此批只改 Engine 的纯提示/材料合同，不改变 Studio 调用序列或正式正文写回。

```yaml
module_change_packet:
  objective: "环境与主创消费真实接力顺序，同时保留角色公共言行与私有冲动的边界"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_environment_prompt 的可选 public_log、render_relay_materials，经 public/literary.py 导出"
  variation_point: "仅 opt-in 接力输入和素材渲染，默认整场行为不变"
  inputs: ["SceneBrief", "已解析的公共日志", "按调用先后的一级角色条目", "独立环境候选", "场景结果核对"]
  outputs: ["环境写手提示", "可追踪的主创素材块"]
  invariants: ["不泄漏 private_impulse 给环境/其他角色", "主创不补造角色言行", "候选不晋升为 Canon", "不增加文学审美门禁"]
  allowed_dependencies: ["Engine 场景纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["环境只见公共言行", "主创见时间顺序及条目来源", "未完成结果不伪装成完整素材", "默认路径兼容"]
  rollback_unit: "独立 Engine 合同提交"
  documentation: ["本文件"]
```

## 2026-09-24：自由排演与系统角色画像复核

同一第二场的忽略试验 `build/scene-performance-e2e/free_rehearsal_probe.py` 让周鹤先以第一人称自由排演，再抽取 JSON。排演有较连续的观察和心理，但交付只剩“坐。这个点人多。”及一次腾桌动作；且排演仍误用沈照月的性别代词，凭空添加碗、筷子、醋壶，把心理又导向职业手续。**自由排演不是已验证的文风修复**：抽取步骤损失了可用的情绪与句法，事实误写仍在；不能直接将其接入正式流水线。

Pi Worker 的 `character-actor` 系统画像仍宣称每轮“从本场第一个时刻到最后一个时刻”经历整场，但 relay 实际只请求当前一轮。此冲突可能鼓励角色预演结局、压缩当前回应；系统画像应按请求跨度行动，把真实公共互动当作当前事实，同时保留完整场景 batch 的兼容性。是否改善角色声音仍须真实模型复跑，不凭提示词改动宣称有效。

```yaml
module_change_packet:
  objective: "消除 Pi Worker 角色系统画像与 relay 当前回合请求的跨度冲突"
  primary_module: "Pi Worker conversation profile"
  public_entry: "conversationSystemPrompt(character-actor)"
  variation_point: "由当前请求确定表演跨度；batch 与 relay 共用稳定画像"
  inputs: ["角色任务单", "已发生公共互动", "本轮输出格式"]
  outputs: ["第一人称且不预演未发生情节的角色画像"]
  invariants: ["角色自主发言与行动", "不替别人发言", "不创建事实或 Canon", "无工具和项目写权限"]
  allowed_dependencies: ["现有 Pi Worker conversation"]
  forbidden_dependencies: ["Engine 内部", "Provider 专有逻辑", "项目文件写入"]
  tests: ["系统画像断言", "Pi Worker check", "同题真实模型复跑"]
  rollback_unit: "独立 Worker 提交"
  documentation: ["本文件"]
```

## 2026-09-24：由角色素材到有情绪层次的正文

最新复核发现：`render_relay_materials` 将主创职责缩成“组织、取舍和叙述衔接”，并说 `private_impulse` “不得直接写入正文”；旧 batch 材料甚至说“绝不可写入正文”。本意是不让后台字段原样泄漏或主创代写角色言行，但模型容易把它读成**不得创作心理层与情绪层**。此外角色 JSON 交付没有明确要求保留连续发言的完整语势，环境候选每段硬限 350 字。自由排演试验中有层次的文字最终被抽成一句话，印证“素材压缩”风险，而非证明单纯增加字符上限能改善文风。

修订方向：角色仍独占外显对白与动作；允许角色在一个 `spoken` 内保留同一发言的自然延展，`private_impulse` 是未说出口的体验线索而非必须照抄的台词。主创据已确认事实和选择的视角，自行决定哪里深入心理、哪里让环境、句法与沉默承担情绪；可改写并组织角色私有体验为视角内的心理叙述，但不得把另一角色不可知的心事写成全知事实、把未出口念头变成台词/动作，或把角色主观猜测写成世界事实。环境候选可停留较长，但不能靠无关细节灌水。修订权覆盖文学渲染、心理缺席、语势贫乏及情节问题，不只修复硬失败；仍以有证据的阅读损害为依据，不加新的风格门禁或机械篇幅指标。

```yaml
module_change_packet:
  objective: "保留一级角色外显言行所有权，同时允许主创发展心理、情绪和环境的文学层次"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_actor_scene_prompt、render_environment_prompt、render_performance_materials、render_relay_materials"
  variation_point: "素材表达及交接措辞；不改角色/环境调用顺序和 Canon 边界"
  inputs: ["角色已发出的台词/动作与未出口体验", "环境候选", "SceneBrief 与已确认来源"]
  outputs: ["保留语势的一级候选", "授权主创在限定视角内创作心理和情绪的素材合同"]
  invariants: ["外显言行仍由角色一级 Agent 生成", "角色私念不泄露给其他角色/环境", "猜测不晋升事实", "不新增审美门禁"]
  allowed_dependencies: ["现有 Engine 纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["角色交付不强制短答", "环境较长候选解析", "主创心理使用边界", "提示词与模块审计"]
  rollback_unit: "独立 Engine 合同提交"
  documentation: ["本文件"]
```

## 2026-09-24：主创生成与修订连续使用一级素材

运行时目前仅在首轮 `create_scene` 给主创角色/环境素材。`complete_first_draft_length` 只见正文和布尔 `actor_owned`，`revise_scene` 完全不见素材；主创在补写和返修时既缺少心理候选，也没有逐条对照外显言行的依据。修复应把同一创作候选的素材随交易缓存，并供补写、修订使用；修订能主动改变叙述距离、心理组织、环境停留和句法，而不能因审查要求“对白更有个性”就自行替角色加台词。若一级素材确实不足，应明确报告需要角色重演，而不是隐性越权。旧缓存若没有素材，不应伪造一份不同的来源。

```yaml
module_change_packet:
  objective: "让主创首稿、补写和返修共享同一份一级素材及外显言行边界"
  primary_module: "Studio runtimes/pi_scene_transaction"
  public_entry: "create_scene、revise_scene 与场景提示渲染"
  variation_point: "启用表演素材时缓存候选材料；默认单主创路径保持原行为"
  inputs: ["SceneBrief", "同一 transaction 的角色/环境材料", "审查意见与候选正文"]
  outputs: ["富于情绪和心理的正文生成/修订提示", "来源一致的补写/返修"]
  invariants: ["外显言行不由主创补造", "未缓存来源不静默伪造", "不改变正式提交和 Canon Gate", "不以字数取代文学判断"]
  allowed_dependencies: ["Engine public/literary.py", "现有 Studio 缓存和 Pi Gateway"]
  forbidden_dependencies: ["Engine 内部 import", "Provider SDK 直连", "正式项目文件写入"]
  tests: ["首稿/补写/修订素材连续性", "缺失缓存可解释失败", "提示词心理与情绪权限", "全量 Python/架构/Prompt 检查"]
  rollback_unit: "独立 Studio adapter 提交"
  documentation: ["本文件"]
```

## 2026-09-24：真实接力复跑后的演员输入修订

`relay-runtime-literary-live` 用更新后的 Pi 系统画像与角色交付提示复跑第二场：演员不再只交极短对白，周鹤一轮可连续说几句，私念也较具体；但二人绕着钥匙、登记、值夜表和虚构手续盘旋，八轮后“漏歌再纠正”“承认点名删改”仍缺席。候选反复新增未确认的道具和程序细节。一次结果核对把“暴露动机”判 `fulfilled` 并列出八个证据 ID，超过解析合同上限四个，导致流程中断。此轮**没有形成可用正文**，不可称作风格验收通过。观察显示：缩短/延长角色语言并不足以让固定剧情自然到达；角色看到的人物投影偏职业语言和行为惯性，未见完整的成长经历，当前场冲突也未作为“未发生的压力”显式区分。

修订只增加已有资产的生活史与本场冲突可见性：角色可凭自身经历和关系压力自主决定绕、问、说，不让导演规定具体句子、动作或每轮交付。生活史只供本人，其他角色和环境仍只见公共言行；场景冲突不能当作已经发生的事实。不能把人物卡中“平时带笔、纸”当作本场确实带着。之后同题复跑，比较是否仍迷失在职业手续。

```yaml
module_change_packet:
  objective: "让一级角色看见本人已建档的生活史和当前场冲突，而不被导演逐句控制"
  primary_module: "Engine literary/scene/composition"
  public_entry: "project_brief_expression_context 的 dialogue_intents 与角色表演提示"
  variation_point: "在既有角色投影内加入有来源的 lived_history；relay 当前压力只标为尚未发生"
  inputs: ["正式人物 CharacterCard", "SceneBrief.external_conflict", "真实公共互动"]
  outputs: ["更完整的第一人称角色经验边界"]
  invariants: ["只给本人历史", "不把未来动作当已发生", "不分配台词、动作、轮次", "不新增事实或 Canon"]
  allowed_dependencies: ["现有 Engine 人物卡投影与角色提示"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["人物经历来源投影", "relay 压力与公共事实区分", "真实同题复跑"]
  rollback_unit: "独立 Engine 投影提交"
  documentation: ["本文件"]
```

第二次复跑仍未完成已锁定结果：沈照月与周鹤在“节目单/值机日志/排班科/调档”上反复拉扯，十轮对白比旧版长，却依旧缺少漏歌与删改承认。这说明“给更多背景”若不改编排，只会让人物更有理由重复自己的防御话术。角色被禁止发明任何道具或节目内容，也使它不敢用尚未定名的歌实际演出“漏掉—纠正”；与此同时另一个演员只看见对方真实公共言行，不看见待完成的场景边界，缺少推动对手离开程序话术的戏剧方向。

需要把自主性划在恰当边界：角色可创作不承担证据和持续设定的普通现场细节、自己的措辞与情绪动作；由此产生的细节仍是候选，主创有权拒绝。已有 Canon、神秘线索、精确读数、稳定身世与不可逆剧情不得凭空确定。自然互动之后，未完成的宏观场景结果同时对双方作为**戏剧方向**可见，而不是只告诉结果归属者；对手不知道未来会发生什么，演员仍自由选择如何试探、拒绝、绕开或沉默。这样让二人共同参与抵达剧情，而不是反复让同一个人独自接任务。

```yaml
module_change_packet:
  objective: "扩大角色的现场表达自主性，并让互动双方共享尚未兑现的戏剧方向"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_actor_scene_prompt 与角色素材交接合同"
  variation_point: "区分可弃现场细节与证据/Canon；结果边界不等于角色已知事实"
  inputs: ["SceneBrief 结果引文", "真实公共日志", "角色本人经验"]
  outputs: ["可供首级演员自由表演的边界提示"]
  invariants: ["不规定台词或动作", "不把未来当已发生", "不发明核心证据或世界规则", "角色言行仍归本人"]
  allowed_dependencies: ["现有 Engine 纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目写入"]
  tests: ["普通现场细节被允许", "核心证据仍待来源", "他人结果不当成角色知识"]
  rollback_unit: "独立 Engine 提示合同提交"
  documentation: ["本文件"]
```

真实复跑另有一处编排故障：结果核对模型返回了八个证据 ID，虽然文字上仍是在判断剧情，解析器按既有上限拒绝，接力直接终止。只对这种**格式或来源合同错误**做一次带原因的原模型重试；第二次仍不合格就明确失败，不默默判已完成，不放松剧情证据标准。
角色系统画像、演员提示和人物投影发生变化后，batch 与 relay 的素材缓存版本同步前进；旧候选不冒充新实验结果。

```yaml
module_change_packet:
  objective: "让模型可从一次结果核对格式错误恢复，避免无正文的偶然中断"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "mode=relay 的结果核对调用"
  variation_point: "仅失败核对增加一次有错误原因的重试；成功路径不变"
  inputs: ["既有检查提示", "解析器错误", "同一角色条目"]
  outputs: ["合同合格的核对或明确失败"]
  invariants: ["不篡改 evidence", "不把缺失改成已完成", "不增加文学审美门禁", "不新增项目写入"]
  allowed_dependencies: ["Engine public/literary.py", "现有 Pi Gateway"]
  forbidden_dependencies: ["Engine 内部 import", "Provider 专有逻辑"]
  tests: ["单次恢复", "二次无效明确失败", "缓存正确"]
  rollback_unit: "独立 Studio adapter 提交"
  documentation: ["本文件"]
```

## 2026-09-24：重复防御话术与戏剧终点的角色自主性

共享戏剧方向后的真实试跑，沈照月终于问到节目顺序，周鹤说了轻音乐，却仍把“记不清”重新导回时长、稿面、日志；十回合上限触发，四个结果没有一个被可靠核为已完成。随后的隔离对照 `build/scene-performance-e2e/role_breakthrough_probe.py` 固定同一 t1–t10 公共日志，只改变周鹤下一回合的附加提示：默认版继续说“得看监听记录上的签名”；追加“别把同一职业辩解换说法，自己找人物逻辑内的松动处”后，他开始纠正节目顺序，并自己提到中间忘了一首歌。一个随机样本不能证明整体风格过关，但这比继续增加身份、职业词汇或导演台词更有针对性：明确固定剧情终点需要人物自己寻找因果路径，允许抵抗而不允许原地重播。

完整复跑表明固定十二轮仍偏早：第三回合周鹤补提漏掉的歌，核对将该结果判 `fulfilled`；第十一回合他开始承认稿件被改，第十二回合沈照月追问递稿人，场景停在此处。隔离的第十三回合让周鹤至少说出“递稿走的是站里的手”“改动不是我提的”，但仍未明确“点名内容被要求删去”。回合边界应受现有二十四条公共证据容量和素材总预算限制，而不把四结果硬算成十二次调用。仍有有限上限；超过或材料过大明确失败，不把接近目标当完成。测试场景对歌曲内容未提供确切来源，主创后续须解决物料充分性，不能编造歌名后宣称 Canon。

```yaml
module_change_packet:
  objective: "使一级角色用自身逻辑寻找既定场景终点，停止重复相同防御话术"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_relay_context 的尚未发生场景边界说明"
  variation_point: "仅自然互动后的缺口提示；初始开放回合不变"
  inputs: ["已发生公共互动", "SceneBrief 来源锁定的结果"]
  outputs: ["允许拖延但不鼓励无限同义回避的角色扮演提示"]
  invariants: ["不指定台词动作", "不制造证据或 Canon", "人物可自主选择松动条件"]
  allowed_dependencies: ["现有 Engine 纯合同"]
  forbidden_dependencies: ["Studio", "Provider SDK"]
  tests: ["提示词合同", "同题角色 A/B", "完整接力复跑"]
  rollback_unit: "独立 Engine 提示提交"
  documentation: ["本文件"]
```

## 2026-09-24：省字倾向的上游节奏合同

除角色素材压缩外，项目模板 `scene.yaml` 还预填 `reflection_ratio: low`、`description_ratio: low`，并要求“每段至少承担行动推进、信息改变、关系压力、选择代价或场景衔接之一”；规划默认和物化模板也把心理比例预设为低。这与用户希望在心理、环境和对白里充分渲染情绪直接抵触。它们不是文字 lint，却会以 SceneBrief/Relevant Sources 的上游软合同身份压住主创提示。新模板和缺省值改为心理与环境的可变中性起点（`medium`），将“每段都须有情节功能”改成“整场须有变化，局部允许视角内停留”。保留现有项目里用户自己明确写的节奏选择，不把 `medium` 当固定配额；旧项目既有场景仍可按用户方向或主创修订，而不批量篡改。
为覆盖已经由旧模板初始化的场景，主创生成与修订提示同时注明这些 `low` 只是全场软建议，不得把它们当成心理、环境和对白起伏的硬上限；是否停留仍由最新用户方向和具体场景决定。

```yaml
module_change_packet:
  objective: "移除新场景模板对心理与环境的默认压缩倾向"
  primary_module: "Engine literary/planning narrative rhythm"
  public_entry: "DEFAULT_RHYTHM、scene.yaml 模板与物化渲染"
  variation_point: "只改缺省软引导；显式项目节奏和 Canon 不变"
  inputs: ["新建场景", "缺省叙事节奏合同"]
  outputs: ["允许局部情绪与环境停留的场景节奏"]
  invariants: ["不设置心理/环境硬配额", "不改既有项目资产", "不加静态审美门禁"]
  allowed_dependencies: ["现有 Engine 规划合同与模板"]
  forbidden_dependencies: ["Studio", "Provider SDK", "正式项目文件写入"]
  tests: ["默认合同", "模板字段", "显式用户选择优先", "架构/全量回归"]
  rollback_unit: "独立 Engine 规划提交"
  documentation: ["本文件"]
```

## 2026-09-24：角色系统画像中的终点与自主性

角色扮演系统画像目前强调“主创锁定场景边界”和“自主决定如何回应”，却没有把两者的关系说清。面对底层场景任务，模型容易把角色的防御惯性演成无限循环。固定结果应是整场戏的边界，而不是下一句命令；角色拥有选择何时、怎样以及在什么压力下失守的自主权，但不能把同一推辞重播到场景结束。调整系统画像后必须真实复跑，核对角色是否在保持独特声音的同时抵达已锁结果；若素材或动机不足，仍应失败并请主创重构情境，不许强行填空。

```yaml
module_change_packet:
  objective: "在角色系统层明确固定场景终点与人物自由应对的关系"
  primary_module: "Pi Worker conversation profile"
  public_entry: "conversationSystemPrompt(character-actor)"
  variation_point: "角色扮演画像；不改外显言行的一级归属或 Provider transport"
  inputs: ["已确认场景边界", "真实公共互动", "角色欲望和误判"]
  outputs: ["自主寻找可信剧情转折的角色提示"]
  invariants: ["不指定台词动作", "不把未来当已发生事实", "无法合理抵达时不编造证据"]
  allowed_dependencies: ["现有 Pi Worker conversation"]
  forbidden_dependencies: ["Engine 内部", "Provider SDK 直连"]
  tests: ["画像合同", "Pi Worker check", "真实同题试跑"]
  rollback_unit: "独立 Worker 提交"
  documentation: ["本文件"]
```

```yaml
module_change_packet:
  objective: "让接力按真实证据容量而非固定回合数终止，给形成方向变化的互动继续发展的机会"
  primary_module: "Studio runtimes/scene_performance"
  public_entry: "mode=relay 的轮次边界"
  variation_point: "最多二十四回合且二十四条公共证据；每回合条目数随剩余容量收窄"
  inputs: ["参与者数", "场景结果数", "真实角色条目"]
  outputs: ["未完成结果的有限续演机会"]
  invariants: ["不超过二十四条公共日志", "未完成或素材超预算不交正文", "默认 batch 不变"]
  allowed_dependencies: ["现有 Engine 接力合同"]
  forbidden_dependencies: ["新增审美门禁", "无限轮次"]
  tests: ["剩余条目容量", "未完成仍失败", "真实同题复跑"]
  rollback_unit: "独立 Studio 编排提交"
  documentation: ["本文件"]
```
