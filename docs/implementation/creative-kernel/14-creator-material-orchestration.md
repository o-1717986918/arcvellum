# 场景主创取材调度修正：代码级实施记录

## 已确认事实

《吵架》的五类 agent 均已启用，但主创四次返回 `material_requests: []`。第一次先读取空目录，然后把“无候选可读”写成跳过取材的理由。当前 `read_scene_material` 只能读取已生成候选；真正委托 agent 的入口是主创输出的 `material_requests`，由 Studio `fulfill_scene_material_requests` 执行。已有候选只读落盘，最终 prose 与 SceneDelta 仍由主创生成。

## Module Change Packet A：文学提示词

```yaml
module_change_packet:
  objective: "主创按作者意图明确决定取材种类与委托内容，并在候选回来后组织、取舍和补写"
  primary_module: "Engine prompting/"
  public_entry: "public.prompting 的分层提示词"
  variation_point: "五类 agent 的文学用途随作品和场景变化，权限、JSON 和事实边界固定"
  inputs: ["CreativeIntentV1", "SceneBrief", "MaterialRequestV2", "候选文件索引"]
  outputs: ["含文学目的、精确时刻和事实 cue 的 material_requests", "material_decisions", "主创正文"]
  invariants: ["角色人格初始化保留", "事件叙述的提案不能伪称 Canon", "候选无正文及 Canon 写权"]
  allowed_dependencies: ["Engine prompt layer registry", "Engine literary request parser"]
  forbidden_dependencies: ["Studio runtime", "Provider SDK", "正式写回与 Gate"]
  tests: ["提示模板含请求与取舍边界", "提示词注册校验"]
  rollback_unit: "Engine 取材合同与提示词修改"
  documentation: ["本记录", "提示词层版本"]
```

入口落点：`prompting/layers.py` 调整版本；`scene.creator.identity.md`、`scene.creator.create.md`、`scene.creator.revise.md`、`scene.creator.material-request.protocol.md`、`scene.material.selection.md` 说明主创主动编排与补写；两个新增固定补救层登记无效独写理由和虚空素材决策。

## Module Change Packet A2：取材请求合同

```yaml
module_change_packet:
  objective: "每次委托都由主创指定文学目的与观察时刻"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "public.literary.parse_scene_material_requests"
  variation_point: "actor、environment 与三类描写器共享请求字段"
  inputs: ["MaterialRequestV2", "SceneBrief", "performance plan"]
  outputs: ["验证后的有界请求"]
  invariants: ["角色仍有自主回应空间", "cue 只能交已知事实与提案边界"]
  allowed_dependencies: ["Engine prompting layer"]
  forbidden_dependencies: ["Studio runtime", "Provider SDK"]
  tests: ["speaker 旧字段也不能绕过 purpose/scene_moment"]
  rollback_unit: "Engine 取材请求验证"
  documentation: ["本记录"]
```

## Module Change Packet B：Studio 场景交易

```yaml
module_change_packet:
  objective: "空目录不能充当独写理由，候选必须有真实取舍"
  primary_module: "Studio runtimes/ 场景交易"
  public_entry: "PiSceneTransactionRuntime.create_scene/revise_scene；SceneCreatorMemoryV1"
  variation_point: "场景可先请求一至八项候选，也可在确无阅读收益时直接独写"
  inputs: ["冻结的 SceneBrief/来源/提示词快照", "主创取材计划 JSON", "素材文件目录"]
  outputs: ["保存的意图、请求、候选 ID 与取舍", "CreativeResult"]
  invariants: ["同一请求重启不重复生成", "素材正文不嵌入主创提示", "主创独有正文写权", "零取材仍可用于无需候选的场景"]
  allowed_dependencies: ["public.literary", "public.prompting", "SceneMaterialLibrary", "RoleConversationGateway"]
  forbidden_dependencies: ["Engine internal import", "Provider 直接客户端", "正式 Gate 副本"]
  tests: ["空目录首次不导致无意义读取", "请求后读取并取舍", "直接独写的文学理由", "重启恢复"]
  rollback_unit: "Studio 场景交易取材调度修改"
  documentation: ["本记录", "运行时调用图"]
```

保持现有两阶段 JSON 委托路线：主创以 `material_requests` 指定 agent、时刻、预期读者效果与可知事实；Studio 负责安全执行和只读落盘；主创读候选后以 `material_decisions` 记录至少一条真实候选的取舍，并自行补充衔接、视角、心理与叙述。首次不取材的理由必须是文学判断；“目录为空”是正常初态，不能成为跳过依据。无效跳过理由与虚空候选决策各允许一次有界补救；再次无效则停止。若模型选择取材但候选尚未生成，主创只返回请求，不同时提交正文。

## Module Change Packet C：Pi Worker 文件读取工具

```yaml
module_change_packet:
  objective: "空素材目录明确告诉主创应发起生成请求，而非把空数组误作不可用"
  primary_module: "workers/pi-worker/"
  public_entry: "createSceneMaterialTool/readSceneMaterial"
  variation_point: "空目录和已有候选的返回形式"
  inputs: ["场景交易允许读取的 material_root", "candidate_id"]
  outputs: ["只读候选目录或单份候选文件", "明确的空目录状态"]
  invariants: ["不得写候选", "不得越过 material_root", "非主创无该工具"]
  allowed_dependencies: ["Node 文件系统", "Pi SDK 工具类型"]
  forbidden_dependencies: ["Studio 数据库", "角色生成调用", "正式正文写回"]
  tests: ["空目录返回可操作说明", "已存在文件仍按精确 ID 读取"]
  rollback_unit: "Pi Worker 空目录语义修改"
  documentation: ["本记录"]
```

## 验收要点

- 对《吵架》一类双人高压场景，主创能据意图请求角色自主回应，并可组合环境、人物或场面观察；事件叙述仅在场外事实或设定需要进入读者知识时请求。不能用“凑齐五类”代替判断。
- 请求里的 `purpose` 说明希望改变哪种读者经验，`scene_moment` 定位一次观察，`cue` 只传 agent 可知的事实。
- 候选由各 agent 生成并保存为只读素材文件；主创查阅、采用、改写或舍弃，并补写承接与叙述；审读只审成稿及来源边界。
- 无素材需求的短场可以独写；空素材目录或缺少现存候选不构成独写理由。

## 实施与验证

- 提示层明确 `material_requests` 是委托入口、`read_scene_material` 是只读入口；主创负责确定读者效果、观察时刻、事实 cue，并在候选落盘后组织、取舍和补写。新的固定补救提示层已注册，场景交易仍固定每层版本。
- Engine 对五类请求一律要求 `purpose` 与 `scene_moment`，不能用旧 `speaker` 写法跳过文学目的。
- Studio 对首次独写的空目录理由和候选后的虚空 ID 取舍各进行一次有界补救；再次无效则拒绝该结果，不把无效选择写入场景记忆。候选文件与正式正文的权限未扩大。
- Pi Worker 的空目录读取返回明确的 `empty_before_request` 状态；Python 素材目录提示同步说明先委托再读取。
- 已通过：场景相关 139 项测试，定向轻内核与公开 API 15 项测试，Pi Worker 119 项测试，提示词注册校验、模块图核对和架构审计。补充的空目录与虚空取舍集成测试已通过。
- 尚未用真实模型重跑《吵架》；该场已有正式正文，本次不改写历史成稿。真实模型是否会在一次补救后选择哪类取材，需要在新场景交易中观察。
