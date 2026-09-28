# 场景素材库、事件叙述器与文学提示修订

## 调用与目的所有权

`LeanSceneRunCoordinator.advance_one/advance_transaction` 由自动创作推进或项目 Agent 的创作工具触发，调用 `SceneTransactionService.create`，后者调用 `PiSceneTransactionRuntime.create_scene`。场景主创模型先根据 SceneBrief、正式来源、作品方向拟定 `CreativeIntentV1`；Studio 的 `SceneCreatorMemoryV1` 按交易保存、重载并记录其修订和素材取舍。项目级 Agent/用户方向与 SceneBrief 是意图的上游约束；它们不替场景主创决定每个镜头或把未确认的读者误会写进 Canon。审读与修订重读同一场意图，下一场只承接已提交正文、SceneDelta 和交接。

## 文学判断

取材启用时，主创首次若不请求 agent，须给出 `material_skip_reason`，运行时要求它是具体、非空的文学理由。事件叙述候选逐条给出 `basis=confirmed|attributed|proposed` 与 `source_note`；新设定可以被提议，但候选不得冒充已确认事实，也不能自动获得 Canon 资格。

人物描写处理可见特性与生活痕迹；场面描写处理同一时刻已发生言行的空间关系；环境 Agent 处理空间、感官、时间与气氛；角色 Agent 以人格化身份作选择和回应。原“事物描写”定位错置：它改为**事件叙述器**，负责场外已发生事件的转述、设定的适时说明和世界观展开。它可决定信息何时进入读者视野、从何种叙述距离进入、留下哪些可推想的空白；不得把设定候选伪装为已确认事实。这个划分沿用 [文学判断依据](00-literary-basis.md) 对人物、日常、留白和叙事速度的观察。

主创应积极考察是否需要角色续演、环境、人物、事件或场面素材。每次请求必须描述阅读效果和准确时刻；直接成稿须说明不取材的文学理由。素材可被采用、改写、舍弃，但不能自动进入正文或 Canon。

## Module Change Packet A：事件叙述合同

```yaml
module_change_packet:
  objective: "事件叙述器取代物件描写器，形成独立可续接的文学角色"
  primary_module: "Engine literary.scene.roleplay"
  public_entry: "public.literary.MaterialRequestV2 / render_describer_initialization / render_describer_turn"
  variation_point: "kind=event-narration, role=event-narrator"
  inputs: ["场外事件或设定主题", "purpose", "scene_moment", "confirmed_sources"]
  outputs: ["0–3 条带焦点的事件叙述候选"]
  invariants: ["已确认、转述与提案逐条标识", "不发起角色关键言行", "候选不写 Canon"]
  allowed_dependencies: ["Engine prompting layers", "public.literary"]
  forbidden_dependencies: ["Studio I/O", "Provider SDK"]
  tests: ["事件请求 target 与权限", "初始化和逐轮提示", "候选合同"]
  rollback_unit: "事件 kind、提示层与注册元数据"
  documentation: ["本文件", "03-describer-design.md", "04-prompt-inventory.md"]
```

## Module Change Packet B：主创素材文件权限

```yaml
module_change_packet:
  objective: "候选写入交易素材文件，主创凭 ID 只读调用，提示词只含目录"
  primary_module: "Studio runtimes/pi_scene_transaction"
  public_entry: "PiSceneTransactionRuntime.create_scene/revise_scene; SceneMaterialLibrary.write/index"
  variation_point: "Pi Worker scene-creator conversation 的唯一只读素材工具"
  inputs: ["render_interaction_materials 的受视角过滤候选包", "交易 ID"]
  outputs: ["materials/index.json", "每候选 JSON 文件", "不含候选正文的主创目录"]
  invariants: ["角色私念仍按视角过滤", "路径只在交易素材目录", "无写工具", "失败重启不重复已完成调用"]
  allowed_dependencies: ["Studio RoleConversationGateway", "Pi Worker bounded conversation"]
  forbidden_dependencies: ["任意项目文件读取", "正式 TaskPackage 写入", "把候选正文内联回主创提示"]
  tests: ["文件目录及 ID 读取", "路径逃逸和缺失拒绝", "主创提示不含候选正文", "重启续接"]
  rollback_unit: "素材文件库和主创只读工具"
  documentation: ["本文件", "01-current-callgraph.md"]
```

文件示例：`scene-transactions/<transaction>/materials/index.json` 保存 `candidate_id → digest 文件名`；每项文件只保存一个候选。主创系统提示规定先按需列目录、再按 ID 读取。候选生成失败时不登记空壳文件；已有完整文件保持可读。场景审读以正文和意图为主，只收到素材目录标识，不把候选正文复制入审读提示。

## Module Change Packet C：文学提示审阅与流程树

```yaml
module_change_packet:
  objective: "逐一审阅活动创作提示，重写主创、审读及各独立创作角色的文学任务"
  primary_module: "Engine prompting"
  public_entry: "public.prompting.list_prompt_layer_specs / PromptWorkbenchService.catalog"
  variation_point: "作品>全局>随包提示版本，场景交易固定快照"
  inputs: ["活动创作层 ID", "文学判断依据", "职责边界"]
  outputs: ["分级流程树", "可编辑身份/阶段默认文本", "不可编辑结构模板"]
  invariants: ["协议结构固定", "角色人格化初始化保留", "没有旧物件描写入口", "提示快照不随中途编辑改变"]
  allowed_dependencies: ["Engine prompt layers", "Studio prompt workbench", "settings feature client"]
  forbidden_dependencies: ["在运行时代码内嵌第二份文学提示", "前端绕过 feature client"]
  tests: ["目录每层一次", "预览与快照", "活动层验证", "前端类型和构建"]
  rollback_unit: "创作提示资产及目录"
  documentation: ["本文件", "04-prompt-inventory.md"]
```

文学审阅逐项看：角色特性是否可见、日常细节是否有选择、留白是否有线索、事件说明是否改变读者知识、叙述距离是否符合视角、信息分配是否产生趣味或误读、段落速度是否由情境决定、跨场景事实是否明确。审阅不是给模型一张必填评分表；不同场景可只使用其中少数手段。

## 实施验收（2026-09-28）

- Python 全量回归：1,671 项通过，1 项跳过；事件候选合同、素材文件、主创意图和交接的定向测试包含在内。
- Pi Worker：12 个测试文件、118 项通过；包括仅按索引读取、路径逃逸拒绝和较长导演记录可读取。
- 客户端：76 个测试文件、247 项通过；构建成功。提示词流程树的桌面与 390px 移动视图已做截图和横向溢出检查。
- 提示资产注册：仓库虚拟环境中的 59 个资产、73 个任务提示 ID 校验通过，无错误或警告。架构审计与模块地图检查通过。
- 开发版 API：`/health`、`/projects`、`/runtime/adapters`、可读模型端点与 SSE 已核验；工作台目录可见事件叙述器与固定结构模板，旧物件描写项不再出现。

一次场景交易的 Engine 合同、Studio 调用和 Pi Worker 素材权限互相依赖；本轮将它们作为一个可整体回退的功能边界提交。文学质量仍须用同一作品样本做盲评；上述程序验收只证明合同、权限和界面行为。
