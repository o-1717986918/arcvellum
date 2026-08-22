# ArcVellum 空间操作系统与统一创作星链开发计划

状态：SO-0 至 SO-7 已实现并完成验证，SO-8 进入交付收尾
适用基线：ArcVellum v0.99 及后续版本  
文档性质：产品架构、前端架构、投影合同和实施门禁的统一指导文件

> 实施记录（本轮）：统一创作星链已成为默认前端入口；作品级工作台通过星链节点、底部工作台 dock 和空间窗口进入，独立系统页面继续保留。节点活动状态、工作区注册表、动作分发、SSE 增量投影、多焦点全书图和 2.5D 交互验收已落地。详细验证结果以本轮提交记录和测试报告为准。

## 1. 文档目的

本计划将两项产品方向合并为一项完整工程：

1. 把星仪从“首页中的一个可视化模块”升级为 ArcVellum 的空间操作系统；
2. 将当前星仪重构为一张有层次、可持续生长、所有语义节点均可交互的立体创作星链。

星仪不再与正文、人物、背景、文风、分支、审查、Agent 和交付页面并列。除项目管理、设置、模型连接、关于、更新和协议外，所有作品级能力都从统一星链中的节点进入，并在星仪内部以浮动、吸附或全屏工作台承载。

本计划不是视觉换皮，也不建立第二套工作流。CLI、Creative Execution Plan、Gate、正式资产和运行时仍是唯一事实源；前端只把这些事实编译为可理解、可交互的空间读模型，并把用户动作送回已有应用用例。

## 2. 实际工程基线

### 2.1 已有能力，必须复用

当前仓库已经具备以下基础，后续不得重复建设：

- `client/src/features/workflow/OverviewView.vue` 已将空间星仪作为默认引擎；
- `client/src/features/orrery/OrreryWorkbench.vue` 已拥有聚焦、导航、关系透镜、热力透镜、书签和无障碍列表；
- `client/src/features/orrery/NarrativeParallaxStage.vue` 与 `engine/` 已建立 PixiJS 2.5D 渲染、相机动画、视差和环境运动；
- `client/src/features/orrery/layout/` 已建立确定性布局、构型、曲线和大规模布局测试；
- `SpatialWindowLayer.vue`、`SpatialWindowFrame.vue` 与 `stores/spatialWindows.ts` 已支持多窗口、拖动、调整尺寸、折叠、锚定和持久化；
- `narrative-projection/v3` 已提供稳定节点、关系、人物参与、布局提示、revision 和增量 patch；
- `WorkspaceCommandBus` 已建立跨 feature 命令边界；
- 项目工作区、正文阅读、档案 IDE、文风工坊、创作策略、Agent 观测和交付均已有独立 feature；
- SSE、运行事件、Autopilot、Creative Execution Plan 和 Agent observability 已能提供动态状态。

### 2.2 当前结构的主要缺口

1. 星仪仍由 `/overview` 页面承载，而不是项目打开后的应用壳层；
2. 作品能力仍以并列路由为主要入口，空间窗口只覆盖部分仪表；
3. `SpatialWindowKind` 是固定联合类型，无法按注册表挂载任意作品工作台；
4. Narrative Projection v3 主要描述作品和局部工作状态，尚未完整表达节点可执行动作、解锁原因、工作台入口和创作生命周期；
5. 工作流节点、作品节点和页面功能之间没有统一身份与交互合同；
6. 远、中、近景虽然存在，但还未成为统一的信息密度和创作过程层级；
7. 路由、窗口和节点分别维护导航语义，存在未来形成三套入口的风险；
8. 正文、人物、世界、审查和文风尚未全部成为星链中的一等可交互对象。

### 2.3 必须修正的旧判断

不再建立“作品星图”和“创作科技树”两种并列模式。正式设计只有一张统一创作星链：

- 作品对象是节点；
- 具有文学意义的创作结果和判断是节点；
- 用户交互从节点发生；
- 机械流程藏在节点生命周期内部；
- CLI 状态机仍在后台决定可执行性；
- 星链只是一套空间投影，不拥有第二套状态。

### 2.4 实验稿借鉴边界

第二个 ArcVellum 前端实验稿最有价值的不是具体 WebGL 代码，而是产品构图：天幕占据整个应用，文字节点本身成为视觉对象，工具以悬浮仪器和舱室依附于场景，用户始终感觉自己处在同一作品空间中。正式版本应继承这种“canvas-first shell”，同时保留当前 Vue feature、PixiJS 2.5D、SSE、窗口状态和无障碍实现。

`docs/design/typographic-celestial-field-review.md` 中已经确认的代码级结论继续有效：吸收全方向天幕、文字节点、镜头飞行、HUD 层次和稳定标签机制，只借设计思想，不复制实验代码，不把正式前端退回无法维护的单文件脚本。

## 3. 产品定义

### 3.1 产品命题

ArcVellum 是一座可进入的文学工程空间。用户不是在仪表盘之间跳转，而是在同一部作品内部移动、观察、创作、审查和交付。

星仪的唯一核心视觉是“正在生长的立体创作星链”：作品母题、世界、人物、事件、章节、场景、分支、正文、审查和文风在同一空间中形成具有因果、时间、关系和创作过程的结构。

### 3.2 用户心智模型

用户只需理解四件事：

1. 每个亮起的节点都能进入；
2. 暗节点可以点击查看尚缺什么，但不能绕过前置条件；
3. 正在脉动的节点代表 Agent 或确定性程序正在工作；
4. 一个节点完成后，会在作品空间中凝结为稳定资产或正式正文。

用户不需要理解 task sidecar、preflight、completion marker、schema 或 writeback provenance。

### 3.3 单一标志性体验

本产品的设计风险只集中在一个地方：作品创作过程可见地凝结为作品本身。

示例：

```text
人物构想节点完成
  -> 凝结为正式人物节点
  -> 与参与章节建立关系光带

场景方向节点完成
  -> 生长出分支节点
  -> 采用分支汇入正文节点
  -> 审查通过后正文由流动光体变为稳定亮点
```

其他界面必须安静、紧凑、可长期工作，不能与星链争夺视觉主角。

## 4. 范围与非目标

### 4.1 本计划范围

- 星仪成为作品打开后的常驻应用壳层；
- 统一立体创作星链；
- 所有语义节点可检查、导航或执行至少一种合法动作；
- 作品级工作台窗口化并支持全屏；
- 正文、人物、背景、文风、分支、审查和交付成为节点入口；
- 工作流状态、人工决策和 Agent 活动进入同一空间投影；
- 路由深链接、键盘、无障碍和小屏降级仍然可用；
- 旧页面在功能等价前不删除。

### 4.2 明确非目标

- 不把星仪改成真正的三维游戏世界；正式路线继续使用 PixiJS 2.5D、多平面视差和 DOM 交互层；
- 不让 Agent 输出像素坐标；Agent 只能提供语义布局意图；
- 不把每个 CLI 任务画成节点；
- 不把设置、密钥、模型连接和协议伪装成作品内容；
- 不复制 Style、Archive、Reader 等组件建立星仪专用版本；
- 不允许前端根据文件是否存在自行推断 Gate；
- 不通过隐藏项目事实制造安全性；正式写入仍由后端合同和 Gate 保护；
- 不在本阶段更换 Vue、Pinia、PixiJS、FastAPI 或 Tauri 技术栈。

## 5. 空间操作系统信息架构

### 5.1 应用分层

```text
ArcVellum Application
  - System Plane
      - 项目库 / 新建 / 导入 / 备份
      - 设置 / 模型连接 / 更新
      - 关于 / 帮助 / 协议
  - Spatial Work Plane
      - 统一创作星链
      - 空间窗口层
      - 健康窄轨 / 当前运行信号 / 章节时间轴
      - 工作台坞站 / 全局搜索 / 命令面板
  - Authoritative Core
      - CLI 状态机
      - Creative Execution Plan
      - Gate / Review / Promote / State / Canon
      - Agent Runtime / Pi Worker / Autopilot
```

### 5.2 常驻空间壳层

项目打开后，主界面固定为：

```text
┌ 当前作品 · 搜索 · 当前运行 · 系统入口 ┐
│ 健康窄轨       统一立体创作星链       活动信号 │
│                                                │
│   人物 / 世界 / 章节 / 场景 / 正文 / 审查     │
│              [浮动工作台]                     │
│                                                │
│ 章节时间轴       工作台坞站       交付信标     │
└────────────────────────────────────────────────┘
```

常驻元素必须保持克制：

- 顶部：当前作品、全局搜索、运行状态、设置；
- 左侧：只保留窄健康轨，不承载完整页面；
- 底部：全书章节目录与工作台坞站；
- 右下：交付信标；
- 中央：星链始终是视觉主体；
- 顾问：悬浮入口与手机比例聊天窗，不挤压星链布局。

### 5.3 独立系统页面

以下功能保留独立页面，不嵌入作品星链：

- 项目库、新建、导入、备份和迁移；
- 设置；
- Agent Runner、Provider 和 Model Connection；
- 更新、诊断和应用信息；
- 关于、帮助、协议和隐私。

项目设置中与作品内容直接相关的部分，例如目标字数、创作方向和自动创作策略，应从作品节点进入；应用级运行配置继续留在系统页面。

### 5.4 作品工作台

以下功能从对应节点打开为工作台：

| 现有 feature | 星链入口 | 默认形态 | 可全屏 |
|---|---|---|---|
| Reader | 正文、章节、正式作品节点 | 纵向阅读窗 | 是 |
| Archive IDE | 人物、世界、场景、资产节点 | 深色 IDE 工作台 | 是 |
| Style Atelier | 文风节点 | 对比与学习工作台 | 是 |
| Creation Strategy | 母题、全书结构、章节策略节点 | 策略工作台 | 是 |
| Agent Observatory | 正在工作的节点、活动信号 | 会话观测窗 | 是 |
| Quality | 审查、文风、规则节点 | 规则与质量工作台 | 是 |
| Archaeology | 导入作品、背景资产节点 | 反向工程工作台 | 是 |
| Delivery | 作品与交付信标 | 交付准备工作台 | 是 |

路由继续作为深链接和刷新恢复机制，但不再是普通用户的主导航。

## 6. 统一创作星链语义

### 6.1 什么可以成为节点

一个对象只有满足以下至少一项，才进入星链：

1. 它是正式或候选文学资产；
2. 它代表会改变作品方向的创意决策；
3. 它是用户可以阅读、编辑、比较或晋升的创作产物；
4. 它是具有文学语义的审查结论；
5. 它是当前阻塞作品推进且需要用户处理的问题。

所有图节点必须至少拥有一种有效交互：检查、聚焦、打开工作台、比较、编辑、选择、请求 Agent、晋升或交付。纯装饰星点不进入节点数组，只属于背景场景。

### 6.2 节点类型

建议建立版本化枚举 `CreativeNodeKind`：

```text
project-origin
theme
style
world
location
organization
character
relationship
volume
chapter
scene
event
branch
reader-question
promise
payoff
draft
formal-prose
review
revision
human-decision
delivery
```

不得使用任意字符串在前端决定渲染或权限。新增节点类型必须同时补充：合同、投影、布局角色、视觉语法、动作注册和测试。

### 6.3 不成为节点的机械步骤

以下内容默认隐藏在节点内部：

- Context Packet；
- Prompt Program 编译；
- Schema validation；
- Task submit / complete；
- Preflight；
- Style Lint 的逐条机器结果；
- Completion Marker；
- State/Canon patch 的机器生命周期；
- Provenance 和 hash；
- 缓存、lease、进程与 provider retry。

这些步骤只通过节点状态环、运行脉冲、异常标记和“工程详情”抽屉呈现。正常完成时不占据空间；失败且需要用户处理时，才投影为 `human-decision` 或附着于原节点的错误入口。

### 6.4 节点生命周期

建立 `CreativeNodeLifecycle`：

```text
latent        尚未进入当前创作视野
locked        已可见但缺少前置条件
available     可以执行或编辑
active        Agent 或程序正在处理
awaiting      等待用户决定
reviewing     正在审查
revision      需要修订
formal        已成为正式资产
blocked       出现必须处理的阻断
superseded    已被新版本替代
delivered     已进入正式交付物
```

生命周期由后端投影，前端不能自行升级。前端只可以根据 `available_actions` 发出命令。

### 6.5 关系类型

保留现有 `RelationFamily`，并补齐统一星链需要的关系：

```text
narrative-spine       卷章场景主脉络
chapter-scene         章节与场景
character-scene       人物参与
world-influence       背景与规则影响
event-causality       事件因果
scene-branch          场景分支
promise-payoff        承诺与兑现
reader-question       读者问题与答案
draft-review          正文与审查
review-revision       审查与修订
revision-formal       修订与正式资产
workflow-prerequisite 有文学意义的前置关系
evidence-claim        可解释证据
```

机械任务依赖不直接画线。`workflow-prerequisite` 只用于用户能理解的创作前置关系，例如“人物基础尚未完成，因此场景正文未解锁”。

## 7. 一张图上的空间层级

### 7.1 语义缩放，而不是模式切换

全书始终处于同一张星链中。用户缩放和聚焦时只改变信息密度：

- 远景：作品母题、文风、世界锚、主要人物、卷和章节星簇；
- 中景：所有章节仍可见，当前章展开场景、事件、人物参与和主要伏笔；
- 近景：当前场景展开分支、正文、审查、修订和正式晋升过程。

远景中的细节点按稳定规则聚合到章节或语义重心，不能从数据模型中删除。聚焦结束后可随相机移动平滑进入其他章节。

### 7.2 空间角色

- 主叙事脊柱：卷、章和场景沿有节奏起伏的主曲线生长；
- 稳定引力层：世界、Canon、文风位于较深空间，影响多个章节；
- 人物轨道：人物是跨章节长期节点，连接参与场景，不在每章复制；
- 创作前景：分支、正文、审查和修订靠近当前焦点；
- 长距离弦：伏笔、承诺和兑现跨章节连接；
- 活动光：Agent 工作附着于目标节点，不生成漂浮任务墙。

### 7.3 构型兼容

继续支持 Spine、Braid、Strata、Constellation、Loop、Stage。构型只改变空间组织，不改变节点身份、动作、正式状态和窗口。

每种构型必须同时满足：

- 章节顺序清晰；
- 所有章节可导航；
- 同章场景形成簇；
- 节点最小间距符合密度预算；
- 主曲线具有节奏但不回绕自交；
- 关系线可分级聚合；
- 同 revision 和 seed 可复现；
- 新节点只触发局部松弛。

### 7.4 节点过载控制

大型长篇不能一次渲染全部细节点。采用以下组合：

1. 层级聚合；
2. 视口裁剪；
3. 标签碰撞与优先级；
4. 边 bundle；
5. 当前焦点邻域优先；
6. 按章节延迟装载细节；
7. DOM 只渲染可交互标签和焦点邻域；
8. PixiJS 渲染远景实体与关系。

“所有节点可交互”指所有已投影节点都具有命中区和动作，不代表所有节点必须同时展开。

## 8. 交互合同

### 8.1 基础操作

- 单击节点：选中、强调直接关系、打开轻量信息环；
- 双击或 Enter：聚焦并展开下一层语义节点；
- 再次打开：弹出对应紧凑窗口；
- 窗口中的“展开工作台”：进入大型或全屏工作台；
- Shift + 单击：加入比较；
- 左键拖动空白天幕：围绕当前语义焦点旋转观察；节点命中仍由 DOM 交互层拥有；
- 中键拖动：全向平移空间；`Alt + 中键` 可作为旋转等价手势；
- 滚轮：以指针为锚缩放；
- 搜索结果：沿空间路径飞行到目标；
- Esc：逐层退出工作台、窗口、聚焦，最终回到全书视野。

不得把主要创作动作藏在右键菜单中。右键只承载固定、隐藏弱关系、复制链接等辅助命令。

相机不得发生 Z 轴方向反转，旋转不得设置影响自由观察的硬角度边界。文字和命中区始终保持面向屏幕；节点不能仅因透视距离变化而完全消失，必须由语义 LOD 决定聚合、简化或展开。

### 8.2 节点动作合同

新增版本化 `NodeActionDescriptor`：

```json
{
  "action_id": "open-character-workspace",
  "kind": "open-workspace",
  "label": "维护人物",
  "target_id": "character:lin",
  "enabled": true,
  "blocked_reason": "",
  "requires_confirmation": false,
  "workspace_id": "archive.character"
}
```

允许的动作种类必须枚举化：

```text
inspect
focus
open-workspace
compare
propose-edit
request-agent
run-creative-step
choose-branch
request-revision
promote
approve
export
```

动作描述来自后端。执行时由 `ConstellationActionDispatcher` 转换为已有的 application use case 或 `WorkspaceCommandBus` 命令。禁止前端根据节点类型拼接 URL、CLI 命令或文件路径。

### 8.3 解锁解释

暗节点仍然可点击。信息窗必须使用自然语言说明：

- 尚缺什么；
- 哪一步可以解决；
- 是否能交给 Agent；
- 是否需要用户决定；
- 会影响哪些作品对象。

不得只显示 gate id 或原始错误字符串。

### 8.4 创作过程示例

选择一个场景后，同一空间内展开：

```text
场景意图
  -> 参与人物与背景
  -> 分支推演
  -> 方向选择
  -> 正文草稿
  -> 文学审查
  -> 修订
  -> 正式正文
```

这些节点均对应真实文学对象、真实选择或真实产物。Context、Prompt、Schema、Preflight 和写回收据继续隐藏在节点内部。

## 9. 空间窗口与工作台协议

### 9.1 从固定窗口种类迁移到注册表

现有 `SpatialWindowKind` 不能继续承担全部作品工作台。目标合同：

```ts
type SpatialSurface = "node" | "instrument" | "workspace";
type SpatialDisplayMode = "floating" | "docked" | "fullscreen";

interface WorkspaceDescriptor {
  workspaceId: string;
  title: string;
  component: () => Promise<Component>;
  defaultSize: { width: number; height: number };
  minimumSize: { width: number; height: number };
  allowMultiple: boolean;
  supportsFullscreen: boolean;
  supportedNodeKinds: CreativeNodeKind[];
}
```

建立 `WorkspaceRegistry`，按需加载现有 feature 组件，不复制业务实现。

### 9.2 窗口状态

`SpatialWindow` 增加：

- `surface`；
- `workspace_id`；
- `display_mode`；
- `route_state`；
- `target_node_ids`；
- `return_geometry`；
- `dirty`；
- `close_guard`。

所有窗口在拖动前后必须保持相同尺寸语义。全屏退出后恢复原位置和滚动状态。窗口状态按项目和用户保存，切换作品时隔离。

### 9.3 多窗口纪律

- 默认只展开一个大型工作台和两个紧凑窗口；
- 超出后进入底部坞站，不继续遮挡星链；
- Node、档案和比较窗口允许多开；
- Reader、Style、Strategy、Delivery 默认单实例；
- 窗口避让顶部、健康轨、章节栏、顾问和交付信标；
- 全屏工作台保留“返回星链”按钮和当前节点面包屑；
- 小屏改为全屏或 bottom sheet，不提供自由拖动。

### 9.4 路由兼容

阶段迁移期保留现有路由。访问 `/style`、`/archive`、`/reader` 等路由时：

1. 若有活动项目，加载空间壳层并直接打开相应全屏工作台；
2. URL 保留工作台、目标节点和显示模式；
3. 刷新后恢复同一状态；
4. 无活动项目时返回项目库并保留待打开意图。

设置、关于和模型连接继续使用独立页面。

## 10. 后端投影架构

### 10.1 唯一事实源

```text
Engine / CLI / Creative Plan / Runtime events
  -> Application read services
  -> Narrative Projection v4
  -> SSE snapshot / patch
  -> Frontend spatial read model
```

Narrative Projection v4 是只读空间投影，不是状态机。它不得：

- 修改项目文件；
- 推进 task；
- 自行批准 Gate；
- 推断正式状态；
- 缓存不可失效的业务结论。

### 10.2 v4 合同

在现有 v3 基础上演进，不另建并列“科技树 API”。建议新增：

```json
{
  "schema": "arcvellum/narrative-projection/v4",
  "revision": "...",
  "focus_scope": {},
  "hierarchy": {},
  "nodes": [
    {
      "node_id": "scene:scene_0001",
      "kind": "scene",
      "parent_id": "chapter:chapter_0001",
      "lifecycle": "available",
      "importance": 0.86,
      "depth_role": "mid",
      "available_actions": [],
      "workspace_hints": [],
      "source_revision": "..."
    }
  ],
  "edges": [],
  "layout_hints": {},
  "activity": [],
  "patch_endpoint": "..."
}
```

### 10.3 投影所有权

现有 `projections/narrative/` 继续作为领域包，按职责扩展：

```text
projections/narrative/
  contracts.py          节点、关系、生命周期、动作枚举
  inventory.py          作品事实库存
  hierarchy.py          卷章场景与语义父子关系
  literary_assets.py    人物、世界、风格、事件、承诺
  creative_artifacts.py 草稿、正文、审查、修订
  workflow_state.py     只读映射 CLI/Plan 状态
  interactions.py      可执行动作和阻塞原因
  layout_hints.py       确定性语义布局提示
  service.py            v4 组合服务
  patches.py            revision-bound 增量传输
```

具体文件可在实施时按现有规模微调，但不得重新形成单文件 God Projection。

### 10.4 增量事件

SSE 至少支持：

```text
node.upsert
node.lifecycle.changed
node.activity.started
node.activity.progressed
node.activity.finished
edge.upsert
edge.removed
focus.recommended
decision.required
workspace.invalidated
projection.reset
```

前端只在 revision 连续时应用 patch；断档后重新拉取快照。动画由事件差异触发，不允许用定时器伪造推进。

## 11. 前端模块架构

### 11.1 目标模块

```text
client/src/features/spatial-os/
  SpatialOperatingShell.vue
  SpatialSystemBar.vue
  WorkspaceDock.vue
  DeliveryBeacon.vue
  services/spatialOsClient.ts
  model/workspaceRegistry.ts
  model/actionDispatcher.ts

client/src/features/orrery/
  CreativeConstellationStage.vue
  ConstellationNodeLayer.vue
  ConstellationRelationLayer.vue
  ConstellationInteractionLayer.vue
  ConstellationAccessibleView.vue
  engine/
  layout/
  model/
  workspaces/
```

`OrreryWorkbench.vue` 在迁移期作为兼容编排层，最终退化为薄 facade 或由 `CreativeConstellationStage.vue` 替代。不得一次性重写 Pixi renderer。

### 11.2 Feature Ports

每个作品工作台提供窄接口：

```ts
interface NodeWorkspaceContext {
  projectRoot: string;
  nodeIds: string[];
  readonly: boolean;
  initialTab?: string;
}

interface WorkspacePort {
  open(context: NodeWorkspaceContext): Promise<void>;
  canClose(): Promise<boolean>;
  serializeState(): Record<string, unknown>;
}
```

工作台不导入星仪的 renderer、store 或具体窗口组件。星仪也不导入 feature 内部服务，只通过 registry 和 command bus 协调。

现有路由组件不得直接塞进窗口。每个迁移 feature 应拆成两层：

```text
FeatureView.vue       路由、独立页面壳层和深链接适配
FeatureWorkspace.vue  可复用的实际工作区内容
```

两者共享同一 feature client、store 和 use case。空间窗口只懒加载 `FeatureWorkspace.vue`；路由只负责提供 context 并选择独立或全屏空间壳层。这样既避免复制，也防止 route 生命周期、全页 padding 和导航组件被错误嵌入浮动窗口。

### 11.3 状态所有权

- Projection Store：只拥有最新 v4 快照、revision 和 patch 应用；
- Camera Store：只拥有相机、聚焦和书签；
- Window Store：只拥有窗口几何、层级、显示模式和工作台状态；
- Interaction Store：只拥有选中、比较、悬停和当前动作；
- Feature Store：继续拥有各工作台自己的编辑和请求状态；
- Router：只保存可分享的导航状态，不拥有业务事实。

禁止建立一个同时拥有投影、相机、窗口、Agent 和项目状态的全局 store。

### 11.4 动作分发

扩展现有 `WorkspaceCommandBus`，但保持命令枚举化：

```text
open-node-workspace
focus-node
compare-nodes
request-agent-action
choose-branch
promote-candidate
open-review
open-reader
open-delivery
```

命令处理器只能调用应用 client，不得操作项目文件或直接生成 CLI shell command。

## 12. 视觉与动效系统

### 12.1 视觉主题

产品视觉继续以“精密的叙事观测仪器”为方向，但星链本身比仪表外壳更有生命感。主题只改变材质、光色和背景，不改变节点语义。

五套现有主题继续保留，并必须保证跨主题完整性：

- Moss：矿物绿、朱砂信号、黄铜记忆；
- Iris：深紫与冷青，辅以暖金；
- Obsidian：低明度黑石与高对比信号；
- Bookcase：米白、木质黄、墨色与铜色；
- Modern：冷灰、清蓝、白金与少量警示色。

不得让一个主题只由同一色系组成。窗口采用低明度半透明矿物玻璃，不使用突兀纯白面板。

### 12.2 节点视觉

- 节点主体以文字、光核和单层状态环为主；
- 禁止节点与背景叠加三层无语义几何形状；
- 已完成节点稳定明亮，未完成节点清晰但低亮；
- 可执行节点有克制呼吸；
- 活动节点显示方向性流动；
- 审查节点使用环形印记，不使用通用勾选框；
- 正文节点具有可辨认的长卷或文本光带特征；
- 人物节点使用长期轨道和关系颜色，而不是每章复制头像。

### 12.3 动效编舞

只保留与真实状态对应的动效：

- 节点创建：由上游节点方向生长；
- 节点解锁：遮罩退去，动作入口亮起；
- Agent 执行：局部活动光进入目标节点；
- 分支生成：曲线分叉并保持未采用路径低亮；
- 正文晋升：流动态收束为稳定正文节点；
- Canon/人物状态写回：相关长期节点被短暂照亮；
- 工作台打开：从节点 shared-origin 展开；
- 搜索定位：相机沿路径飞行；
- 作品切换：旧星链退远，新星链进入。

`prefers-reduced-motion` 下保留状态可辨识性，取消长距离飞行、视差和持续脉冲。

### 12.4 关系曲线

- 主脉络使用节奏感受约束的平滑三次 Bezier 或 Catmull-Rom 转 Bezier；
- 同章场景围绕章节锚点形成疏密有序的簇；
- 远景关系聚合到章节重心；
- 人物关系保留全景长曲线；
- 聚焦章节时主脉络降低亮度，章内关系增强；
- 伏笔、承诺、审查和证据关系不能因性能优化被完全移除；
- 边交叉、曲率突变、局部密度和自交进入布局质量评分。

## 13. 功能保真迁移矩阵

| 功能 | 现有入口 | 目标入口 | 迁移完成条件 |
|---|---|---|---|
| 项目创建与切换 | Projects / 顶部切换 | 独立项目库 + 星仪切换带 | 桌面目录、最近项目和恢复可靠 |
| 项目总控 | Overview | 空间操作系统 | 所有当前操作均可完成 |
| 正文阅读 | Reader | 正文/章节节点工作台 | 章节目录、搜索、位置和增量阅读等价 |
| 作品档案 | Library | 任意资产节点 | 搜索、筛选、Markdown 和关键影响等价 |
| 档案维护 | Archive | 人物/世界/场景节点 IDE | 编辑、候选、diff、晋升和回收站等价 |
| 文风工坊 | Style | 文风节点工作台 | 语料、学习、评测、挂载和版本等价 |
| 创作规则 | Quality | 审查/规则节点工作台 | Lint、标点、节奏、阈值和审查等价 |
| 创作策略 | Strategy | 母题/结构/章节节点 | 计划、预演、审批和重规划等价 |
| Agent 观测 | Observatory | 活动节点/信号窗 | 会话、事件、上下文和停止重试等价 |
| 交付 | Delivery | 作品节点/交付信标 | readiness、预览、导出和历史等价 |
| 设置 | Settings | 独立系统页面 | Provider、Runtime、Model 和主题等价 |
| 帮助与协议 | Help/Details/Legal | 设置内独立标签或页面 | 深链接和离线内容可用 |

任何旧页面只有在对应工作台通过功能等价测试后才能从主导航移除。

## 14. 实施阶段

### SO-0：合同冻结与设计基线

目标：在改 UI 前冻结事实源、功能矩阵和视觉验收对象。

工作：

1. 建立 ADR：星仪是空间操作系统，Narrative Projection 是唯一空间读模型；
2. 冻结 v3 节点、关系、revision、patch 和现有路由快照；
3. 为当前所有页面建立功能保真清单；
4. 固定至少三个验收项目：短篇、长篇密集场景、群像多关系；
5. 保存当前桌面与 Web 截图、性能数据和交互录屏；
6. 明确 v4 feature flag 和回退条件。

验收：没有实现改动；所有基线可自动复验。

### SO-1：Narrative Projection v4

目标：让正文、人物、背景、文风、审查、修订和用户决定进入同一合同。

工作：

1. 增加 `CreativeNodeKind`、`CreativeNodeLifecycle`、`NodeActionKind`；
2. 增加 hierarchy、available actions、blocked reason、workspace hints；
3. 将 Strategy、Workflow、Runtime activity 以只读方式投影到现有节点；
4. 增加 v4 snapshot、node detail 和 patch；
5. 保留 v3 adapter，证明同一作品节点 ID 稳定；
6. 生成 OpenAPI 与 TypeScript 类型。

验收：v4 不产生隐藏写入；同 revision 输出稳定；现有 v3 测试继续通过。

### SO-2：统一前端读模型

目标：前端只消费一套节点、关系、生命周期和动作合同。

工作：

1. 新增 v4 feature client；
2. 建立 projection store 与 revision-safe patch；
3. 将 v3 数据适配器隔离在兼容层；
4. 建立 Interaction Store 和 typed action dispatcher；
5. 完成节点、关系、动作 fixture；
6. 禁止组件直接请求 generic API。

验收：快照、patch、断线恢复和版本不匹配均有测试。

### SO-3：语义缩放与立体星链布局

目标：将书、章、场景和创作过程放在同一连续空间。

工作：

1. 把现有 book/chapter/scene 切换改为同图语义缩放；
2. 建立章节星簇和章节重心；
3. 角色轨道、世界锚、正文与审查前景分层；
4. 调整六种构型，使节点分布、主曲线和局部簇均达到密度预算；
5. 建立局部增量松弛与稳定坐标缓存；
6. 建立 LOD、边 bundle 和标签碰撞；
7. 为 1000 场项目增加性能基准。

验收：所有章节和场景仍在同一图中；节点不靠隐藏解决拥挤；构型可复现。

### SO-4：节点交互与创作过程

目标：所有语义节点都能自然进入其功能。

工作：

1. 实现信息环、聚焦、比较和动作菜单；
2. 正文、人物、背景、文风、分支、审查节点分别接入真实动作；
3. 暗节点提供自然语言解锁解释；
4. Agent 活动绑定目标节点；
5. Human Decision 绑定选择卡并在成功提交后消失；
6. 正文晋升和审查修订形成真实生长动画；
7. 错误只附着目标节点，不生成全局骚扰卡。

验收：至少一个场景从意图、分支、正文、审查、修订到晋升可完全在星链中完成。

### SO-5：空间操作系统壳层

目标：星仪成为项目打开后的应用主体。

工作：

1. 新增 `SpatialOperatingShell.vue`；
2. 收敛顶部系统栏、健康窄轨、章节时间轴、工作台坞站和交付信标；
3. 项目打开后默认进入空间壳层；
4. 独立系统页面与空间壳层共享项目和返回状态；
5. 当前 Overview 退化为兼容路由；
6. 建立加载、作品切换和恢复动画。

验收：不进入其他作品页面，也能完成现有 Overview 的全部能力。

### SO-6：工作台窗口化

目标：在不复制功能的前提下把作品页面迁入星仪。

工作：

1. 建立 WorkspaceRegistry 和 WorkspaceWindowHost；
2. 扩展窗口 `floating/docked/fullscreen`；
3. 依次接入 Reader、Archive IDE、Style Atelier；
4. 再接入 Strategy、Quality、Observatory、Delivery、Archaeology；
5. 深链接打开对应全屏工作台；
6. 建立 dirty state、关闭保护和状态恢复；
7. 移除跨 feature 具体组件依赖。

验收：功能保真矩阵逐项通过；窗口拖动前后几何一致；全屏退出状态不丢失。

### SO-7：实时性、动效和创作可观测性

目标：星链的变化与真实创作同步。

工作：

1. 接入 v4 SSE patch；
2. 统一活动节点、Agent 会话和任务进度；
3. 建立开始、完成、失败、决策和晋升动画；
4. 断流时降级轮询并明确显示连接状态；
5. 不展示隐性思维链，允许展示任务输入、上下文摘要、工具和产物；
6. 建立动画节流和后台标签页降频。

验收：真实任务推进时不需刷新；无虚假进度；断线后能恢复正确 revision。

### SO-8：导航迁移与旧入口收敛

目标：从并列页面产品转为星仪主体产品。

工作：

1. 主导航只保留项目、星仪和系统；
2. 旧作品路由转为打开指定工作台；
3. 顾问命令、搜索结果和通知均能定位节点或工作台；
4. 删除已完成迁移的重复导航组件；
5. 保留兼容 redirect 和版本化书签迁移；
6. 更新帮助、新手引导和 README 截图。

验收：普通用户不再面对十余个并列模块入口；深链接仍可用。

### SO-9：性能、无障碍、桌面和发布验收

目标：把视觉原型收敛为稳定产品。

工作：

1. Web 与 Tauri 分别做性能和动画验收；
2. 建立列表式完整替代视图；
3. 键盘完成聚焦、打开、执行、关闭和返回；
4. reduced motion、主题、高 DPI 和窄屏验收；
5. 长篇压力测试、持续 SSE 和多窗口内存测试；
6. 完成安装、升级、项目迁移和崩溃恢复测试；
7. 更新产品截图、README、帮助和发布说明。

验收：达到本文件第 17 节交付门槛。

## 15. 代码级改动清单

### 15.1 后端

优先修改或新增：

- `src/literary_engineering_studio/projections/narrative/contracts.py`；
- `src/literary_engineering_studio/projections/narrative/hierarchy.py`；
- `src/literary_engineering_studio/projections/narrative/interactions.py`；
- `src/literary_engineering_studio/projections/narrative/workflow_state.py`；
- `src/literary_engineering_studio/projections/narrative/creative_artifacts.py`；
- `src/literary_engineering_studio/projections/narrative/service.py`；
- `src/literary_engineering_studio/projections/narrative/patches.py`；
- `src/literary_engineering_studio/api/routers/narrative.py`；
- `src/literary_engineering_studio/application/strategy_projection.py`；
- `src/literary_engineering_studio/projections/api_read_models.py`。

所有 application write action 必须经过现有用例或新增窄端口，不得让 projection package 导入写服务。

### 15.2 前端

优先修改或新增：

- `client/src/features/spatial-os/`；
- `client/src/features/orrery/CreativeConstellationStage.vue`；
- `client/src/features/orrery/model/creativeNodes.ts`；
- `client/src/features/orrery/model/nodeActions.ts`；
- `client/src/features/orrery/model/semanticZoom.ts`；
- `client/src/features/orrery/layout/hierarchicalLayout.ts`；
- `client/src/features/orrery/workspaces/workspaceRegistry.ts`；
- `client/src/features/orrery/workspaces/WorkspaceWindowHost.vue`；
- `client/src/services/workspaceCommands.ts`；
- `client/src/stores/spatialProjection.ts`；
- `client/src/stores/spatialWindows.ts`；
- `client/src/types/spatial.ts`；
- `client/src/types/spatialWindows.ts`；
- `client/src/router.ts`。

`parallaxRenderer.ts` 继续按当前 engine 子模块拆分，不得重新合并为 God Renderer。

### 15.3 合同与工具

- 更新 OpenAPI snapshot；
- 生成 TypeScript DTO；
- 增加 v3 到 v4 兼容 fixture；
- 更新架构审计，禁止 spatial-os 导入 feature 内部组件；
- 新增工作台注册完整性检查；
- 新增所有节点均有交互描述的合同测试；
- 新增所有动作均映射到允许用例的注册表测试。

## 16. 测试与验收矩阵

### 16.1 合同测试

- CreativeNodeKind 和 Lifecycle 枚举完整；
- 每个节点 ID 稳定且来源可追溯；
- 每个投影节点至少拥有 inspect/focus/open/action 之一；
- locked 节点具有 blocked reason；
- available action 不包含任意 shell、路径或 URL 拼接；
- v4 patch 必须绑定 base revision 和 target revision；
- v3 adapter 行为保持兼容。

### 16.2 布局测试

- 同 seed 和 revision 坐标一致；
- 新增一场不会导致全书重新洗牌；
- 同章场景形成簇；
- 全书章节顺序可辨；
- 主曲线无不可解释回绕；
- 节点最小间距满足 LOD 预算；
- 关系线密度受控但语义不丢失；
- 1000 场、200 人物、500 承诺下仍可导航。

### 16.3 窗口测试

- 浮动、吸附、全屏、恢复；
- 拖动前后尺寸一致；
- 多窗口不遮挡关键系统入口；
- dirty state 阻止误关闭；
- 切换项目隔离窗口状态；
- 深链接刷新后恢复；
- 小屏正确降级。

### 16.4 创作 E2E

至少覆盖：

1. 从母题节点进入创作策略；
2. 创建并晋升人物和世界资产；
3. 完成全书节奏和字数规划；
4. 进入章节与场景；
5. 完成分支选择；
6. 生成正文；
7. 查看审查并修订；
8. 晋升正式正文；
9. 更新人物状态与 Canon；
10. 从星链阅读全文并交付。

每一步必须由真实后端状态驱动，禁止用前端 mock 作为最终验收证据。

### 16.5 视觉验收

使用固定项目和实际项目进行：

- 短篇空白初始项目；
- “你好新世界”视觉基准；
- 群像、多章节、多关系压力项目；
- 已完成正文和大量审查记录的长篇项目。

桌面和 Web 分别截取远景、中景、近景、三窗口、全屏工作台和 reduced-motion。验收必须由截图和实际交互确认，不能只凭 DOM 测试。

## 17. 性能与质量预算

### 17.1 性能预算

- 星链首次可交互：开发机冷启动目标不高于 2.5 秒；
- 节点点击到信息环：低于 100ms；
- 工作台懒加载后打开：缓存命中低于 200ms；
- SSE 事件到可见状态：本地目标低于 250ms；
- 相机交互：桌面常态 50–60 FPS，压力场景不得持续低于 40 FPS；
- 远景可见实体建议不超过 350；
- 中景建议不超过 900；
- 近景只展开焦点邻域；
- 后台标签页停止持续动画和高频布局。

### 17.2 工程质量预算

- 不新增跨 feature 具体 Vue 组件依赖；
- projection 不依赖 application write service；
- renderer 不拥有业务状态；
- 单个新增核心 Vue 文件建议不超过 500 行；
- 单个新增 TypeScript engine 文件建议不超过 400 行；
- 单个新增 Python projection 文件建议不超过 450 行；
- 新合同必须有 enum、schema 和兼容测试；
- 新窗口必须通过 registry 注册，禁止散落条件分支；
- 新节点必须通过 NodeRenderer/NodeAction registry 注册。

### 17.3 视觉质量预算

- 中央星链始终是第一视觉焦点；
- 不出现大片无意义空白；
- 不用纯白大型面板破坏空间；
- 打开三个窗口后仍有连续叙事视廊；
- 静止十秒仍适合阅读和工作；
- 换题材后结构仍成立；
- 所有动画都能解释对应的真实状态；
- 所有图节点都可交互，所有装饰都明确不属于图节点。

## 18. 风险与对策

### 18.1 节点爆炸

风险：正文、人物、背景、审查都进入同一图后数量急剧增长。  
对策：层级投影、章节簇、语义缩放、按需详情、边 bundle、视口裁剪。

### 18.2 星链变成工程调试图

风险：机械任务和 Gate 淹没文学对象。  
对策：机械步骤只进入节点内部状态；默认不成为节点；只有需要用户处理的文学问题才显式化。

### 18.3 窗口吞没星链

风险：所有页面窗口化后又回到多面板仪表盘。  
对策：大型窗口数量预算、底部坞站、全屏模式、shared-origin 动画、默认紧凑窗口。

### 18.4 前端形成第二套状态机

风险：前端根据节点和文件自行判断解锁。  
对策：Lifecycle、available actions 和 blocked reason 均由后端投影；前端只分发动作。

### 18.5 大重写造成回归

风险：同时替换投影、renderer、路由和页面。  
对策：按 SO-0 至 SO-9 垂直切片；v3 adapter、旧路由和现有工作台保留至功能等价。

### 18.6 视觉优先损害效率

风险：用户为常见操作频繁飞行和展开。  
对策：全局搜索、命令面板、章节栏、键盘快捷入口、最近工作台和 reduced motion 始终可用。

## 19. Git 与执行纪律

每个阶段开始前必须：

1. 重读本文件对应阶段；
2. 检查当前实现与功能保真矩阵；
3. 写出本批变更计划和明确非目标；
4. 建立或更新测试 fixture；
5. 确认工作区状态。

每个阶段结束必须：

1. 完成定向测试；
2. 更新阶段实施记录；
3. 运行 `git diff --check`；
4. 使用单一职责提交；
5. 记录回退点；
6. 只有跨阶段集成时才做大范围回归和生产构建。

建议提交序列：

```text
docs(spatial): freeze operating-system contracts
feat(projection): add narrative projection v4 contracts
feat(orrery): add unified constellation read model
feat(orrery): implement semantic zoom hierarchy
feat(spatial-os): add workspace registry and shell
feat(spatial-os): migrate literary workspaces
feat(orrery): bind live creative actions and activity
refactor(router): make spatial shell the project default
test(spatial): add visual, performance and desktop gates
```

## 20. 最终交付定义

本计划完成必须同时满足：

1. 用户打开作品后以星链为唯一作品主界面；
2. 正文、人物、背景、文风、分支、审查、修订和交付均能从节点进入；
3. 所有可见图节点至少有一种真实交互；
4. 机械步骤没有污染主视觉，但阻断仍可解释；
5. 星链在远、中、近景下始终是同一张图；
6. 全书所有章节可定位，当前章可展开全部场景；
7. 作品工作台支持浮动、吸附和全屏；
8. 设置、模型连接、关于和协议作为独立系统页面保留；
9. 不存在第二套前端状态机；
10. 一个场景和一个完整章节能在星链中完成正式闭环；
11. 功能保真矩阵全部通过；
12. Web、桌面、无障碍、性能和视觉验收通过；
13. README、帮助、截图和发布说明反映新产品形态。

## 21. 最终判断

这项重构值得实施，但它的成功标准不是“做出更复杂的星图”，而是让 ArcVellum 的产品结构与文学工程思想终于一致：

> 作品不是许多页面中的数据；作品本身就是用户进入、创作、审查和维护的空间。

实现时必须坚持一套投影、一套状态权威、一套动作合同和一套窗口协议。星链负责把复杂文学工程变成可以看见、理解和参与的创作过程，CLI 和 Agent Runtime 继续负责把这个过程可靠地推进到底。
