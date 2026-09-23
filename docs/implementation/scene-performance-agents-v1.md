# 场景表演素材 Agent：工程实现规格 v1

状态：2026-09-23，v1 工程实现与验证记录。此机制生产**非权威候选素材**；唯一正式正文作者仍是主创 Agent。既有 Canon、人物状态、违禁表达、标点、字数与审查晋升链不得削弱。本版覆盖新作品默认使用的 `lean-v2` 场景事务；`strict-v1` 的正式任务状态由 Engine 管理，未获得新增状态合同前不暗插素材调用。

## 用户可见结果

一场创作先由主创确定已规划剧情内的节拍与角色任务；角色 Agent 以该人物身份、知识边界和当下关系压力，分别提出具体台词与相伴动作；环境 Agent 按视角、空间、文风和节拍独立写候选场景描写。主创在同一场景中拒绝、修改或吸纳素材，并把正文写成统一叙述。用户看到的是更可辨的人物语言、动作和有叙事视角的环境，不应看到拼贴痕迹、后台任务单或新增未经确认的事实。

## 边界裁决

- 当前新作品的 lean-v2 是生产入口；既有正式 route 的任务状态属于 Engine，必须由 Engine 签发可选素材步骤后才能启用，不能由 Studio 偷偷在正式 prose task 前插入模型调用。这个兼容边界是明确的未覆盖范围，不将其伪称为旧项目已升级。
- Pi Worker 是无项目写权限的角色执行器。`character-actor` 与 `environment-writer` 是白名单会话人格，不是新 Provider、可变系统提示或自主工具 Agent。
- 角色与环境输出是候选片段，不得直接形成 `CreativeResult.prose`、资产、Canon 或审查结论；主创明确拥有采用、改写、拒绝权。
- 现行“subagent 不得写正文”规则在本机制中收窄为“不得写**正式正文**或返修、定稿”；允许受限 Agent 产生隔离候选台词、动作与环境描写。仓库内项目规则与开发标准已同步；仓库外已安装的项目技能不是本次源码提交的一部分，不能视作已修改。旧正式任务若未显式签发素材任务仍沿旧规则。
- 每场有上限：导演任务单 1 次、角色表演最多 4 次、环境描写 1 次；失败不放松 Gate，素材可降级为空并由主创独写。无人物资产时不得伪造专属声音。

## 合同与顺序

`PerformancePlan/v1`：`scene_id`、按序排列的 `beats`；每个 beat 绑定 `beat_id`、`speaker`（SceneBrief 参与者的精确字符串）、已确定事件、必须完成的言语行为、必须传递/隐瞒的信息、允许动作、对手反应边界、环境用途。导演不能改 SceneBrief 的 objective、参与者、既定数字或下一场事件。

`ActorMaterial/v2`：现行角色任务每个 beat 只请求一个第一人称候选，包含具体 `spoken`、`first_person_action`、`private_impulse`；角色 Agent 必须从该人物内部表演，不能替别的人说话或决定情节。演员输入带人物稳定声音、当下声音状态、知识/误知、眼前事件和动作边界，不再带导演拟定的具体话术、完整事实清单、全知来源或前一条尚未采用的候选。完整任务单仍交唯一主创兑现。角色的语言差异由词域、句法、礼貌边界、回避方式、反讽/幽默及受压变调体现，不复读口头禅。v1 实跑中演员仍写导演式关系分析，修正依据和边界见 [第一人称角色表演合同修正](first-person-actor-roleplay-v2.md)。

`EnvironmentMaterial/v1`：按 beat 绑定候选 `description`、`focal_character`、`scene_function`。环境 Agent 在文风参考下写可被主创择用的具体描写，空间、物件、声音、触感和时间流动必须受视角与行动约束；不得自行开辟新地点、事件或象征结论。允许有目的的审美停留，不强求每句推进情节。

执行顺序：冻结场景输入和文风版本 → 主创导演计划 → 按 beat 顺序独立角色扮演（不让演员读取前一条尚未采用的候选）→ 环境描写 → 主创全文 → 现有字数补写、确定性验证、独立审读、提交。候选缓存键包括场景输入、表达投射、文风选择、合同版本、所选模型与当前节拍摘要；任一变化使旧缓存失效。候选 JSON 保存在 Studio 数据目录的事务缓存中，绝不直接写入作品目录。缓存只证明**提供过哪些候选**，不能根据文字重合推断主创在语义上采用了它们；主创是否采用需人工/专门审计判断。

## 实际数据流与失败语义

```text
SceneBrief + 已确认来源 + 人物声音投射 + 本场文风选择
    │
    ├─ Engine 纯函数：导演任务单合同、演员/环境任务合同与 JSON 解析
    │       └─ 任何未知参与者、错位 beat、空候选或过大候选均拒绝
    ├─ Studio：导演调用 1 次 → 演员调用 0–4 次 → 环境调用 1 次
    │       └─ Pi Worker conversation_role 白名单、单轮、tools=[]
    └─ 主创：读取隔离候选，独自写 CreativeResult.prose 与 SceneDelta
            └─ 原场景确定性校验、返修、审读与原子提交
```

导演任务单失败时，整套候选退化为单主创写作；某演员或环境写手失败时跳过该候选，其他有效素材仍可使用；全部候选失败时也是单主创。模型输出不会被当作事实授权：导演/环境写手可读已确认来源，演员只读局部人物声音和眼前节拍，不读取全知来源；各候选 Agent 都不能调用项目工具。角色 Prompt 每节拍只请求一种候选（解析器暂兼容一至两种）、台词上限 300 字、动作上限 220 字；环境候选每段最多 350 字；候选总块超过 16000 字则整体回退，避免把正式正文 Prompt 挤出窗口。正式正文仍受原有硬审查，环境比例、修辞和角色辨识属于生成时的软引导与读者评估，不新增风格硬门禁。

## 配置、可见性与操作

- `application.scene_performance_agents.enabled` **默认关闭，实验性开放**；`max_actor_calls` 为 0–4，默认 4。设置页可开启、限制角色调用次数，并为角色与环境分别选择已连接模型。开关仅影响后续场景创作，不改已生成正文或缓存。真实试跑发现候选可能补造精确信息，盲评和事实误差比较完成前不可默认向全部作品推出。
- `GET/PUT /model-connections/pi-worker/scene-performance` 读写上述设置；写入必须同时提供布尔 `enabled` 与范围内整数上限。旧配置缺项使用默认值；损坏的旧上限安全回退并夹紧到 0–4。
- 角色列表 `worker`、`character-actor`、`environment-writer` 走原有 Pi 模型目录和凭证，默认可同模型，用户可独立切换。Pi Worker `--conversation-role` 只允许三个静态值，专门角色只能运行 conversation 模式，不开放任意系统提示。
- 候选缓存位置为 Studio 数据目录下 `scene-transactions/<transaction_id>/performance-*.json`；`creative_result_<digest>.json` 仍是唯一正文缓存。事件流记录 plan、actor、environment、skip/fallback，便于定位成本与失败。候选模型调用计入当前场景的 provider call 指标；它们不消耗正式 Worker 的任务工具额度，因为 conversation 模式无工具。

## 模块取舍

不新建第二套“文学内核”或审查链。Engine 只定义文学任务单和有界纯合同；Studio 的 `runtimes/scene_performance.py` 仅编排受限候选并缓存；Pi Worker 的 conversation profile 负责固定身份与无工具边界；`pi_scene_transaction.py` 继续拥有唯一正文、补写和审读。人物声音由既有 `creative_plan.py` 投射增加已知背景与价值线，不再另造人物数据库。默认节奏合同允许环境停留，旧项目已有的 scene YAML 不暗改。`strict-v1` 迁移不能仅复用 Studio 编排器：须先为 Engine 的 TaskPackage/状态机定义素材任务、来源、产物及完成条件，再接 Pi 执行器和门禁测试。

## Module Change Packets

```yaml
module_change_packet:
  objective: "定义版本化场景表演任务单和非权威候选的纯合同"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "public/literary.py 中的构建、解析和渲染函数"
  variation_point: "导演计划、角色扮演和环境描写的文学合同"
  inputs: ["SceneBrief", "人物/声音投射", "文风参考", "已确认场景来源"]
  outputs: ["PerformancePlan", "ActorMaterial", "EnvironmentMaterial", "可供主创阅读的候选块"]
  invariants: ["参与者精确匹配", "无正式正文/Canon 写入", "不替代硬审核", "候选可拒绝"]
  allowed_dependencies: ["Engine 场景事实和版本化文风合同"]
  forbidden_dependencies: ["Studio", "Pi SDK", "Provider", "项目持久化"]
  tests: ["合同字段", "越界人物", "空/超长候选", "输入摘要失效"]
  rollback_unit: "Engine 纯合同提交"
  documentation: ["本规格", "模块目录"]
```

```yaml
module_change_packet:
  objective: "在 lean-v2 场景事务内执行独立表演和环境候选，并交主创取舍"
  primary_module: "Studio runtimes/pi_scene_transaction.py"
  public_entry: "PiSceneTransactionRuntime.create_scene"
  variation_point: "受限角色会话与候选缓存"
  inputs: ["SceneBrief", "Engine 表演合同", "RoleConversationGateway"]
  outputs: ["带候选输入的主创 Prompt", "隔离缓存/来源记录", "原 CreativeResult"]
  invariants: ["失败回退单主创", "事务提交不变", "旧作品行为不变", "无隐藏项目写入"]
  allowed_dependencies: ["Engine public/literary.py", "RoleConversationGateway", "既有事务缓存"]
  forbidden_dependencies: ["Engine internal import", "第二套 SceneDelta/Canon Gate"]
  tests: ["调用顺序", "角色/环境失败回退", "缓存失效", "最终正文只由主创返回"]
  rollback_unit: "Studio 场景适配提交"
  documentation: ["本规格", "质量基线"]
```

```yaml
module_change_packet:
  objective: "为两个候选 Agent 提供不可注入的独立系统身份"
  primary_module: "workers/pi-worker conversation"
  public_entry: "受限 conversation_role 参数"
  variation_point: "普通主创、角色演员、环境写手的白名单系统提示"
  inputs: ["会话角色枚举", "Studio 已构造的任务单"]
  outputs: ["无工具文本/JSON 回答", "现有执行回执"]
  invariants: ["tools=[]", "单轮", "无项目写权限", "无任意 system prompt 参数"]
  allowed_dependencies: ["Pi Agent Core", "现有会话 transport"]
  forbidden_dependencies: ["Engine 文学规则", "Provider 特判", "自主项目工具"]
  tests: ["白名单", "系统人格选择", "工具仍为空", "旧会话兼容"]
  rollback_unit: "Pi conversation profile 提交"
  documentation: ["本规格"]
```

## 附带优化与验收

同时修正默认叙事节奏合同中过低的环境比例和“每段必须推进”的机械措辞；按本场而非章级未来情节选文风参考，控制来源篇幅和顺序，保留完整参考块。正式 Prompt 与 lean Prompt 使用同一 Engine 人物声音投射；审查仍核验角色事实、数字、违禁词和标点，不把“有修辞”“有环境段”设为机械硬门禁。

定向合同测试必须通过；完整 Python、Pi Worker、Prompt 注册、架构审计及 `git diff --check` 必须通过。真实创作最少两个连续场景，保存各角色原始候选、环境候选、主创最终文本、调用记录与人工逐段评语；同题单主创 A/B 至少核对去名对白辨识、环境是否从视角生长、语言起伏、Canon 错误及费用。未完成真实模型与读者验证时，不可宣称文风已解决或发布。

## 本轮工程与创作验证

源码已实现 Engine 纯合同、Studio 编排/缓存/回退、Pi 三种静态会话身份、模型选择与设置页开关；人物声音投射、默认环境比例、主创吸纳素材指令和项目规则同步调整。验收结果：Python 全量 `1530` 通过、`1` 跳过；Pi Worker `106` 通过；设置页定向 `4` 通过；前端生产构建通过；Prompt Registry `59` 资产、`73` ID 均有效；架构审计无新增跨层违规，模块图与 diff 格式检查通过。未创建发行版本。

真实模型验证使用现有《shoreline》测试项目的相邻场景 brief，输出与候选保存在 `build/scene-performance-e2e/scene-transactions/`（非正式作品，未向原项目提交）。调用模型为本机所选 `deepseek/deepseek-v4-flash`；一次启用场景最多出现 8 次模型调用（导演 1、演员 4、环境 1、主创及长度补写），单主创对照 1 次。环境候选起初越界写人物动作和对白，后改为只产空间感知；角色候选一度造出来源不存在的精确钟点、节目时刻和设备读数，主创有时又将其写入正文。导演和演员 Prompt 随之收窄“只能按来源给信息、不得用精确值填清单”，但单靠提示仍不能保证零幻觉。因此机制保持**默认关闭**。

| 对照 | 结果 | 阅读观察 |
| --- | --- | --- |
| 场景二启用，数轮 Prompt 迭代 | 首稿约 2.8k–3.8k 字符；每版有机械对照句或逗号链等硬项；最后一次经五轮返修及独立审读才 pass | 部分角色话语有职业特征和转折，但也复读人物卡示例、把程序说明拉成长对白；环境有局部视角质感，正文仍有拼贴和解释性尾句风险。 |
| 场景三启用，复用候选重写主创 | 3668 字符的旧主创输出有两个硬项；加入“候选不照搬”后 2860 字符首稿仍有破折号硬项，一轮返修后可通过确定性检查；最终任务单 Prompt 的新采样为 3517 字符、7 次调用，仍有两个硬项 | 角色/环境候选确实进了主创 Prompt，写作变化可观察；程序性叙述、机械对照句与无依据数值尚未稳定解决。 |
| 场景三关闭开关 | 3208 字符、1 次模型调用，机械对照句硬项 | 单主创本来也不达成文风目标；不能把多 Agent 的全部问题归因于新链路，也不能凭一组采样断言新链路胜出。 |

这轮是工程冒烟与定性阅读，不是同题多次随机采样、读者盲评或严谨消融。场景二测试拷贝带有既有 commit receipt，因此虽然独立正文最终审读通过，未伪装成新事务的连续正式提交；相邻场景仅验证了输入与候选链，不算严格的新稿 handoff E2E。真实读者的去名对白辨识、整体续读意愿和事实误差率尚无数据。工程闭环已交付为可关闭的实验能力，**“文风问题解决、可默认上线”不在本轮结论内**。

默认启用前至少补齐四项证据：同一批场景单主创/演员/演员加环境的盲评；逐处核对新精确事实是否来自 SceneBrief 或来源；统计首稿及返修的硬项、角色重复句式与环境越界率；记录各模型实际调用数、耗时与费用。若角色/环境组不能同时改善阅读评分且不增加事实错误，保留开关关闭并回滚相应候选步骤，而不是继续加审美硬门禁。
