# 导演 cue 与场景素材修复记录

## Module Change Packet A：导演提示合同

```yaml
module_change_packet:
  objective: "每轮导演 cue 只传递当前可知的新情势与必要剧情事实，角色据此自由回应；主创拿到可辨认的关系变化素材"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "literary_engineering_studio_engine.public.literary 的 render_performance_plan_prompt、render_interaction_direction_prompt、render_actor_interaction_prompt、render_interaction_materials"
  variation_point: none
  inputs: ["SceneBrief", "performance plan", "已发生的 public_log", "人物背景与环境候选"]
  outputs: ["每轮 direction", "角色当前轮输入", "交给主创的候选素材"]
  invariants: ["角色与环境仅产候选", "主创仍可补写", "正式正文仍经原审查和晋升", "不新增文学门禁"]
  allowed_dependencies: ["Engine public/literary", "Engine literary/scene/roleplay", "相应合同测试"]
  forbidden_dependencies: ["Studio Provider transport", "直接正式写回", "第二套 Gate"]
  tests: ["tests.test_scene_interaction", "tests.test_scene_performance_agents", "真实推演记录对照"]
  rollback_unit: "导演提示合同的独立代码差异"
  documentation: ["本记录"]
```

## 实施与复核

1. 规划提示明确开场的因果次序：若误称源于另一人的玩笑，先让那人实际演出；若误称者主动开口，交代可感的依据与对话对象。`opening_direction.cue` 的示例同步改为“面对谁、凭什么开口、关系压力何在”。这是主创的创作判断，不是新增结构门禁。
2. 逐轮导演提示以已发生的公开言行为依据，cue 交代主要对话对象及起因；新外部事件进入 `scene_change`。角色输入保留真实对戏与自主表达，只提醒其听见眼前的人、知道自己主要面对谁。没有新增必填字段，也没有限定说话轮次或台词长度。
3. 推演交给主创时，保留新出现的 `scene_change`，让主创知道角色回应时发生了什么；连续重复的相同变化只交一次，导演备注仍不重复塞给主创。主创创作与修订提示要求把误称、误会、追问的前因和对话对象落实到正文，允许主创重排或补写必要衔接。独立审查只在正文出现具体阅读损害时建议修订，不以素材逐条照录或称呼议题本身作退回依据。
4. `tests.test_scene_interaction` 中以 512 字首轮发言实际跑过三名角色的回合，后两名均得到新的导演 cue，且下一轮能读到长发言；另一回归测试确认主创收到按轮次排列的不同外部变化。三模块定向测试 66 项、全 Python 测试 1611 项通过（1 项跳过），编译、架构审计、模块图检查、提示词注册验证和 `git diff --check` 通过。旧正式场景中的缺席角色与无源事件成因已定位；本轮未重新调用模型生成和晋升新正文，因此暂不能声称文风或对话自然度已由实模证明改善。

本场关于名字的讨论并非一概无意义：称呼确实是作品的核心奇幻机制。失效之处在于阿澍没有听见计划所说的江岫玩笑，也缺少可信误认线索；读者看见的是称呼规则讨论先于人物关系交锋。修复目标是让名字在人物之间产生冒犯、回避、亲近或决断，而非禁止人物谈名字。

## 真实模型窄测

隔离目录 `build/scene-performance-e2e/director-cue-probe-20260925` 第一次使用同类四人场景、并明确注明“江岫玩笑先演出”的来源。`deepseek/deepseek-v4-flash` 规划的首轮为江岫，cue 明确她对阿澍开玩笑；但模型额外发明了“司仪按旧礼单敬酒”的程序性节拍。随后以更简短的正向提示强调节拍从既有人物、场地和事件生长。

第二次在 `build/scene-performance-e2e/director-cue-probe-unassisted-20260925` 不另行提醒先后顺序，只给同类 SceneBrief。模型仍选江岫先说，让阿澍接她的话。真实两轮角色模型输出见该目录 `dialogue`：江岫对阿澍抛出座次玩笑，导演下一轮选阿澍，阿澍明确转向温泠并亲口叫出“陆太太”。这证实窄场景里的受话对象和误称前因比旧正式稿清晰，但角色话语仍偏啰嗦地谈“座次、讲究、规矩”，不构成整场文风目标达成的证据。

这次对戏又发现导演在 `scene_change` 中让未参演的侍者说出“陆先生”，借无人获得 cue 的配角台词完成关键铺垫。已将提示改为：关键人物言行须先由参与者获得轮次，`scene_change` 承载环境、物件及已演言行的外部后果；背景配角留给主创正文斟酌补写。以同一江岫真实首轮输出重放新版导演提示，下一轮仍选阿澍并交付关键误称，`scene_change` 不再安插侍者的关键台词。重放记录在该目录 `direction-v2`。这些窄测没有加载完整人物档案，也没有生成或晋升正式正文；其中阿澍性别的误判和次要席位细节不应当被当作正式链路已修复或已退化的证据。

最后的提示词微调后，定向测试 66 项与架构审计再次通过；本地开发后端已重启，`http://127.0.0.1:8796/health` 返回 `ok=true`、`engine_ready=true`。旧正式正文保留原状，新的提示只影响之后启动的推演与创作。

## 现有证据

事务 `scene-tx-e5ff278d57214da3a8bbbee5a7d7e217` 的持久会话显示：阿澍、温泠、陆听澜、江岫依次得到导演 cue 并各完成一条表演；邵九、席婆婆尚未进入轮次。并非“只有第一名角色有 cue”。第 4 轮江岫的 `spoken` 长 512 字，旧转述校验上限为 500 字，下一轮生成 cue 前触发 `actor relay public_log entry is malformed`，场景退回四轮已有素材。转述层长度修复已经通过真实记录重放，四轮均可接纳，但尚无修复后的完整模型续演验证。

已送出的 cue 内容也有问题：陆听澜被指定手在活物“半寸处停住、收回去”，于是人物长段谈“半寸、认领、旧邮局”；江岫 cue 把活物此前并未在公开轮次中说出的假话当作已发生。演员得到的情势在微动作层过满，关系和心理反应空间反而被挤窄。首场约 1800 字规划六人，少数配角未必需要发言，但若主创需要其主动选择，必须能请他们续演，不应因为一名演员的长话让后续轮次整体回退。

新增因果核对：正式场景计划写阿澍是“顺着江岫的玩笑”误称温泠；实际 opening_direction 却让阿澍先说，且刻意把江岫的玩笑当作尚未发生。阿澍并不认识在座者，也没有听见可让他误判二人关系的先前台词。cue 给了他“温泠和陆听澜之间不对味的安静”，却没有可信的误认依据。虽然首轮“陆太太”明确叫向温泠，误称的来源与陆听澜在其中的位置仍不清；温泠随后纠字、陆听澜谈名字、江岫提议逐一报名字，便从人物冒犯滑向称呼规则辩论。这是对话目标与来由不足，不是只靠增加文风标签能修复的问题。修正应先让真正的挑头人演出可被听到的玩笑或线索，再让误称者回应；若无前置线索，改成有情境依据的主动试探，而非让人物无缘无故判断亲属关系。每轮 cue 须交代主要对话对象和可知依据，其他言行留给角色。

## 验收观察

- 逐轮记录能分辨“谁已获得 cue”和“谁尚未出场”；一个长回应不会让后续角色失去机会。
- 下一轮 cue 引用已公开言行时有对应来源；新外部事件以新情势引入，不冒充演员曾说过的话。
- 既定关键称呼可交由人物自己说出，动作细节及情绪语势由角色选择；主创必要时仍能补写。
- 主创组织正文时以实际关系变化而非候选条目的数量和顺序为依据；正式审查与晋升不绕过。

## Module Change Packet B：主创素材组织

```yaml
module_change_packet:
  objective: "主创把角色与环境候选组织成有视角、有关系转折的场景，而不把推演当对白实录"
  primary_module: "Studio runtimes/pi_scene_author_prompt"
  public_entry: "render_scene_create_prompt、render_scene_revision_prompt"
  variation_point: none
  inputs: ["SceneBrief", "一级候选素材", "用户方向与文风参考"]
  outputs: ["主创正文候选与 SceneDelta"]
  invariants: ["主创是唯一正式正文作者", "可补写必要言行", "沿用原审查、硬规则和晋升"]
  allowed_dependencies: ["Studio runtimes prompt renderer", "Engine public/literary", "对应 prompt 测试"]
  forbidden_dependencies: ["第二套文学 Gate", "候选直接晋升", "Provider 特判"]
  tests: ["tests.test_lean_kernel_v2_pi_runtime", "真实成稿人工对照"]
  rollback_unit: "主创提示合同的独立代码差异"
  documentation: ["本记录"]
```
