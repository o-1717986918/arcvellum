# 场景声音归属与环境表演：持续实验计划

状态：2026-09-23，目标进行中。本文件记录下一代 opt-in `lean-v2` 场景候选机制，不改变默认创作链、Canon 权限或既有硬审查。

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

### v6 真实试跑反证与 v7 减法

2026-09-24 在同一《shoreline》第二场、同一 DeepSeek 模型上完成 v6 一级候选链（忽略目录 `build/scene-performance-e2e/v6-live/`，未写正式正文）。导演选出了歌名、被删名字、要求者身份、到场先后四个留白；两名角色分别交付 4、11 条言行，歌名和人名没有被编造。但台词仍主要在窗口／稿面流程中回旋；沈照月补出碗、筷筒、杯子和“登记满三十天”的旧物，周鹤补出潮湿天气、节目单中间节目的具体次序、手套与表。特别是“物主留空只能暂存”已在 SceneBrief，角色仍说成“登记满三十天没人认领”：长篇事实提示没有转化为可靠约束。环境写手自造收音机、价目表、灯泡、路上的纸角等；价目表上“包”“粥”两个**非对白引号**被当前解析器误判为对白，导致整份环境候选跳过。

这次反证不支持“再给导演增加更多未定槽位”作为文风主路线。留白可保留为少量关键事实的提醒，但角色的私人压力、关系误判和环境感知焦点已在资产／SceneBrief／来源中，导演再次转写它们会重复放大程序性语言，还会让未经证实的“同桌或邻座”等安排获得任务单权威。v7 先作减法：导演只给情境锚点和少量事实留白；每名演员从自己的档案、眼前情境、已知/误知中选择语言和行为；环境写手自行决定是否观察与何时写。不得把“鼓励自主”理解为角色有权制造新证据，也不把未经证实的普通质感逐项列成禁令。环境解析器只拒真正的对白形式，容纳标牌文字等带引号的环境描写。必须对比同题真实输出及来源错误，不能因候选数增加就宣称成功。

v7 同题复跑（忽略目录 `build/scene-performance-e2e/v7-live/`）也**未达标**。导演把带袋子赴会、带走“签名栏空白”等无来源安排写成情境锚点；两名角色分别交付 9、7 条，但一个凭空拿出登记簿，另一个凭空拿出旧节目单，互相预想对方的道具和台词，仍满是窗口／稿面流程。环境候选四段虽不再被标牌引号误杀，却堆出雨棚、修车铺、风铃、挂钟快“七八分钟”等与情节无关的实写。**减任务字段消除了部分导演占有，但没给角色真实的对手反馈；独立整场预演会迫使每人猜另一个人做了什么。** v7 仅保留 opt-in 实验，不作文风改善结论。下一步以角色接力为主要对照，让角色看见对方已实际说出的公共行为，再自主反应；主创只在检查既定情节缺口时决定是否继续接力或换外部局面，不替角色写标准台词。若仍程序化，要回到人物资产本身检查是否把职业话术重复写成了唯一语言资源。

新检索只能作为机制线索，不是本项目效果保证：[《Multi-Agent Based Character Simulation for Story Writing》](https://aclanthology.org/2025.in2writing-1.9/)明确区分按时间顺序由人物模拟戏剧过程、以及之后的叙述改写；[StoryBox](https://ojs.aaai.org/index.php/AAAI/article/view/40288)用动态环境中的角色互动产生事件，而非单向填细脚本。[IBSEN](https://aclanthology.org/2024.acl-long.88/)的角色保留对话日志并根据真实历史回应，但它的导演还生成细对话脚本；本项目只借鉴实际互动与剧情目标检查，不照搬其逐轮台词指令。上述论文研究设置不同，必须用本项目同题实验验证。

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
