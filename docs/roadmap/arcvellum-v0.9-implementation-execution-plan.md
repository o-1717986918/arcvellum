# ArcVellum v0.9 高效实施执行计划

> 状态：代码实现完成；等待正常 Windows 桌面环境的视觉、性能与安装验收
>
> 设计依据：`docs/roadmap/arcvellum-v0.9-spatial-orrery-and-creative-observability-plan.md`
>
> 基线版本：ArcVellum v0.8.0，提交 `57ccca8`

## 1. 目标与方法

v0.9 的目标不是一次性重写前端，而是在不削弱文学状态机、Agent Worker、正式门禁和桌面交付能力的前提下，把当前固定 SVG 星仪升级为真正可进入、可平移、可缩放、可聚焦的 2.5D 叙事场域，并让所有高频项目管理能力在该场域中完整可用。

实施方法采用四条原则：

1. **契约先行**：先冻结 Projection v3、窗口规格和空间语义，再写渲染代码。
2. **纵向切片优先**：先打通一个真实场景从后端投影到 2.5D 聚焦、窗口、任务和正文入口的完整链路，再扩展全部构型和仪表。
3. **双轨迁移**：v0.8 星仪在开发期保留为回退路径；v0.9 达到功能等价和性能门槛后再默认启用。
4. **视觉只消费正式状态**：PixiJS 多平面场域、动效和窗口不得创造新的作品事实，不得绕开 CLI、审批、Review、Promotion 或 Export 门禁。
5. **伪 3D 优先**：v0.9 的主视觉使用二维 GPU 分层、视差、错切、遮挡与缩放构成纵深；不以真实三维网格、轨道相机或地形作为正式实现。

### 1.1 2026-07-22 实施快照

- 已落地 Projection v3、SSE 观察、PixiJS + pixi-viewport 多平面场域、列表降级与 WebGL context-lost 回退。
- 六种构型已改为稳定语义布局：位置依赖节点稳定序号与项目 seed，不再随着后续场景数量变化而重排旧节点；局部碰撞只移动较轻节点。
- 远中近 LOD 已覆盖节点实体、DOM 标签和关系线：全书视图保留主因果结构，靠近后再释放场景、支线与档案细节。
- Spatial Window Manager 已支持多开、节点锚定、拖动、折叠、复位、项目/构型本地持久化和尺寸调节；默认窗口收束为紧凑规格，超过 12 个展开窗会进入可恢复的最小化轨道，所有空间窗口已切为深矿灰半透明面与独立滚动区。
- 空间与普通交付窗均会启动受控的正式交付 Worker，并通过 delivery SSE 更新后端状态与受权下载条目；它们不再只是展示“可交付”的静态信标。
- 顾问窗已改为可持久化位置与尺寸的窄长对话器；拖动不再改变高度。档案详情、决策弹窗和阅读检索也已统一为主题化深色矿物玻璃，避免出现脱离场景的白色应用面。
- 五套主题均已补齐 orrery-deep 与 orrery-warning 语义 token，空间场域、仪表和顾问不再依赖未定义变量回退。
- 场域偏好已加入“设置 > 场域与动效”：动效（完整、克制、静止）、纵深（深度、平衡、平面）和质量（自动、高质量、性能优先）会实际改变场景动画、伪 3D 投影、层间视差、环境密度与画布 DPR。
- 2026-07-22：全量 Python 回归 223 tests、Prompt Registry（36 assets / 73 task prompt ids）、Vue 类型检查、Rust cargo check --locked 与 git diff --check 通过。
- 2026-07-22：`vite build --configLoader runner` 通过，产物已同步到 `desktop/dist`；Tauri 已完成 NSIS 安装器封装。标准默认 Vite config bundler 与 Vitest 仍受托管沙箱的祖先目录限制，但 `runner` 配置加载器是可重复的生产构建替代路径。
- 仍待正常桌面环境下完成：Playwright/Canvas 像素截图、性能采样、Tauri 冷启动、NSIS clean-install/upgrade smoke test，以及使用现有 `TAURI_SIGNING_PRIVATE_KEY` 生成 updater 发行签名。浏览器自动化内核同样会被主机权限提前终止；这些属于验证环境限制，不是已知产品失败。

## 2. 实际基线

### 2.1 已验证能力

2026-07-22 的本地基线验证结果：

- Python：`223 tests` 全部通过。
- Vue：`vue-tsc` 通过；Vitest 仍被受限沙箱阻断。
- Vite production build 通过（`--configLoader runner`）。
- 当前生产主 JS 为约 `298 KB`，gzip 约 `118.77 KB`；星仪延迟块约 `349 KB`，gzip 约 `106.31 KB`。
- 当前生产 CSS 为约 `216 KB`，gzip 约 `39.33 KB`。
- 场域与启动页资源均切为 WebP，单张约 `46–150 KB`；前端源码不再引用主题 PNG。

### 2.2 可以直接复用

- `narrative_projection.py` 已具备 v2 节点、边、revision、delta、motion events 和可访问摘要。
- `/narrative/projection` 与 `/narrative/stream` 已具备 REST 首帧和 SSE 增量观察链路。
- `LiveEventBus`、Read Model Cache、Reader Manifest、Autopilot、Decision、Rhythm 和正式正文读取能力已经存在。
- Vue 3、Pinia、Vite、Lucide、Markdown 安全渲染和 Tauri 2 已稳定工作。
- OpenCode Worker、任务隔离、预检、写回、审查和路线门禁不是本轮重构对象。

### 2.3 必须替换或拆分

- `StoryTrace.vue` 仍是固定 `1400×700` SVG，缩放只是中心 `scale()`，位置由本地二维正弦线和黄金角卫星算法产生。
- `ImmersiveConsole.vue` 仍把完整业务页面放入四边窗口；它没有形成针对任务重新设计的空间仪器。
- `ImmersiveInstrumentWindow.vue` 的拖动、折叠、层级和位置都是组件局部状态，没有统一碰撞、锚定、持久化和复位策略。
- `OverviewView.vue` 同时负责主题、模式、决策、任务启动和沉浸窗口编排，继续叠加会成为新的单体组件。
- `app.ts` 同时管理项目、多个 read model 和五类 SSE，v0.9 不应继续往其中放相机、布局和窗口状态。
- `api_server.py` 已达 1400 行。v0.9 只迁出新投影聚合，不在本轮顺便重写全部 API。
- `v08.css` 与 `components.css` 合计约 159 KB 原始文本，新增空间系统必须采用组件分层样式，不能继续堆全局覆盖。

## 3. 范围控制

### 3.1 v0.9 必须交付

- Projection v3 与兼容的 SSE delta。
- PixiJS 多平面伪 3D 舞台、DOM 节点层、Vue 仪表层。
- 全向平移、指针锚定缩放、惯性、fit、focus 和 reduced motion；不提供自由旋转。
- Spine、Braid、Strata、Constellation、Loop、Stage 六种可复现空间构型。
- 稳定语义色、构型与题材皮肤分离。
- 统一 Spatial Window Manager 与针对不同任务重做的仪表。
- Agent 任务观察、正式决策卡、项目总体进度、正文入口与档案节点。
- 全书节奏、详略和字数配置进入正式 compose/generate/review 契约。
- 键盘等价视图、2D/WebGL 降级、性能门槛和桌面安装验收。

### 3.2 明确不做

- 不把文学地点写实建模成游戏地图。
- 不引入完整游戏引擎、物理引擎或自由漫游第一人称相机。
- 不把中文长文本渲染成 WebGL 纹理。
- 不重写 CLI 状态机、Agent Runtime 或项目文件协议。
- 不让 Agent 输出像素坐标、渲染代码或不可复现的自由几何。
- 不在本轮拆完 1400 行 API Server；只为新投影建立清楚服务边界。
- 不以更多背景图替代空间语义和交互质量。

## 4. 目标架构

```text
正式项目 / CLI 状态机
        │
        ├─ Dashboard / Library / Reader / Rhythm / Jobs
        │
Projection Services
        ├─ Narrative Projection v3
        ├─ Decision Projection
        ├─ Agent Observability Projection
        └─ Project Progress Projection
        │
REST 首帧 + SSE delta + revision/source_revisions
        │
Vue Projection Stores
        ├─ liveProjectionStore
        ├─ spatialLayoutStore
        ├─ orreryCameraStore
        └─ spatialWindowStore
        │
OrreryWorkbench
        ├─ PixiJS Parallax Stage + pixi-viewport
        ├─ DOM Node Overlay
        ├─ Vue Instrument Layer
        └─ Accessible List / 2D Fallback
```

### 4.1 后端文件边界

建议新增：

```text
src/literary_engineering_studio/projections/
  __init__.py
  contracts.py
  narrative_v3.py
  decision.py
  agent_observability.py
  project_progress.py
  revision.py
  service.py
```

`api_server.py` 只增加薄路由和依赖装配。原 `narrative_projection.py` 保留 v2，直到 v3 前端完成切换。

### 4.2 前端文件边界

建议新增：

```text
client/src/features/orrery/
  OrreryWorkbench.vue
  NarrativeParallaxStage.vue
  OrreryNodeOverlay.vue
  OrreryAccessibleView.vue
  NarrativeHealthRail.vue
  engine/parallaxRenderer.ts
  engine/entityPool.ts
  engine/qualityGovernor.ts
  layout/contracts.ts
  layout/layoutEngine.ts
  layout/grammars/*.ts
  stores/liveProjection.ts
  stores/camera.ts
  stores/layout.ts
  stores/windows.ts
  instruments/*.vue
  styles/*.css
```

`OverviewView.vue` 只负责页面入口、项目级数据和 v2/v3 切换，不再持有相机、节点布局或窗口坐标。

### 4.3 Projection v3 最小契约

v3 在 v2 基础上增加：

- `source_revisions`：dashboard、library、reader、rhythm、jobs 的来源修订。
- `spatial_grammar` 与 `layout_seed`。
- 节点 `parent_id / cluster_id / time_band / importance / detail_level / world_hint`。
- 边 `strength / direction / temporal_relation`。
- `clusters`、`layout_hints`、`lod_summary`。
- `available_actions` 只引用现有正式前端动作，不携带任意命令。
- `detail_endpoint` 为节点窗口提供按需资料，避免把全文塞进投影。

v3 不发送最终像素或世界坐标。布局器以稳定事实、构型和 seed 计算坐标，用户锁定位置存入 Studio 应用数据，不修改作品事实。

## 5. 关键路径

```text
M0 基线冻结与开关
  ↓
M1 Projection v3 契约与 fixture
  ├─────────────┐
  ↓             ↓
M2 2.5D 技术切片   M3 窗口/仪表基础
  └──────┬──────┘
         ↓
M4 单场景纵向闭环
         ↓
M5 六种构型、LOD 与长篇规模
         ↓
M6 全功能仪表与实时任务/决策
         ↓
M7 节奏、详略、字数正式闭环
         ↓
M8 主题、动效、无障碍、性能
         ↓
M9 桌面迁移、发布与回退验收
```

最多同时推进两个工作流。Projection 契约冻结前，不并行开发多个依赖其字段的仪表；空间内核未通过纵向切片前，不批量制作主题和装饰资产。

## 6. 里程碑与完成门

### M0：冻结基线与建立安全迁移面

实施：

1. 记录当前后端、前端、构建和 Tauri smoke 基线。
2. 增加 `orrery_v3_enabled` 开发开关与用户可见的“使用兼容视图”回退项。
3. 路由改为懒加载，避免所有业务页面和未来 Pixi 场域同时进入启动包。
4. 为背景资产建立按主题动态加载，转换 WebP/AVIF，保留可访问纯色回退。
5. 建立 Playwright 配置、截图目录和 Canvas 像素探针。

完成门：

- v0.8 页面视觉和行为无回归。
- 首屏不会加载 Pixi 场域和未选主题背景。
- 后端 212 项、前端 24 项既有测试继续通过。
- 生产构建、桌面开发启动和兼容视图通过。

### M1：Projection v3 与统一修订契约

实施：

1. 编写 JSON fixture 与 TypeScript/Python 对应类型，先覆盖 book/chapter/scene 三层。
2. 创建 `/narrative/projection/v3` 和 `/narrative/stream/v3`；v2 端点不变。
3. 抽出 revision、delta、source revision 和缓存策略。
4. 增加 Decision、Agent Observability、Project Progress 投影的最小只读聚合。
5. 为节点详情增加按需 endpoint，投影只保留摘要。
6. 提供 100、500、1000 场合成 fixture。

完成门：

- 同一项目 revision、构型和 seed 产生稳定结果。
- 增量只更新实际变化实体，不全量制造 motion event。
- 1000 场 book 级投影使用聚合节点，不传输 1000 个完整场景详情。
- 前端可只依赖 fixture 开发，不需要等待真实项目变化。

### M2：多平面伪 3D 空间内核技术切片

实施：

1. 只引入 `pixi.js` 与 `pixi-viewport`，不引入完整游戏引擎；移除 `three` 与真实三维网格作为正式依赖。
2. 建立二维世界相机、ResizeObserver、DPR 上限和 Canvas context lost 恢复。
3. 实现指针锚定缩放、工作面平移、惯性、fit、focus 和明确的二维相机边界。
4. 建立远景/中景/近景容器、二维侧影、遮挡片、缓存背景和 DOM 节点投影；用不同视差倍率表达纵深。
5. 渲染循环采用 invalidate-on-demand；只有相机运动、真实状态动效或环境低频变化时持续刷新。
6. 建立 SVG/列表降级，不支持 WebGL 时仍能完成全部操作。

完成门：

- 静态截图能看出遮挡、前中远景和构图纵深，但不应被误读为游戏地形或真实三维场景。
- 拖动和滚轮的视觉反馈在下一帧出现；焦点飞行不与用户手势争夺控制权。
- Canvas 像素检查确认非空、主题加载和动画前后画面差异。
- 500 候选实体场景在目标桌面达到 55–60 FPS；低配降级不少于 30 FPS。

### M3：窗口管理器与仪表外壳

实施：

1. 建立 `InstrumentWindowSpec` 与集中式 `spatialWindowStore`。
2. 支持锚定、多开、拖动、固定宽高、独立滚动、z-order、碰撞换侧、最小化和复位。
3. 保存每个项目/构型的窗口状态到 Studio 应用数据；不写作品目录。
4. 左侧只保留可收展的 44–52px 健康窄轨；Node Detail、Progress、Manuscript 必须使用三种差异明显的专属仪器结构，验证外壳不是“一种卡片装所有内容”。
5. 小屏改为 bottom sheet；键盘支持窗口循环、关闭、最小化和回到锚点。

完成门：

- 三个窗口同时打开后保留至少 38% 连续叙事视廊。
- 拖动后窗口尺寸和滚动区不改变，不再出现顾问窗类似的高度拉伸。
- 相机移动时锚定窗口平滑跟随；自由窗口不被相机拖走。
- 节点、顶部控制和顾问悬浮窗不互相遮挡。

### M4：单场景纵向闭环

只做一条真实但完整的用户旅程：

1. 用户进入星仪，Projection v3 显示当前章和场景。
2. 用户平移、缩放并聚焦一个真实场景。
3. Narrative Tide 展开该场景的角色、分支、Review、Canon 与当前任务。
4. 点击节点，在节点附近打开专属详情窗。
5. 任务状态通过 SSE 改变局部光和轨迹，不暴露内部推理。
6. 决策节点打开真实 Decision 卡。
7. 已晋升正文从 Manuscript 仪表进入阅读器。
8. 用户切换兼容视图后，功能和状态保持一致。

完成门：

- 上述路径在真实项目和 fixture 项目都可重复完成。
- 前端没有模拟“已完成”“可交付”或伪百分比。
- v2 与 v3 对同一项目的正式状态结论一致。
- 纵向闭环通过后才开始六种构型的横向扩展。

### M5：六种构型、稳定布局与 LOD

实施分两批：

- Alpha：Spine、Braid、Strata。
- Beta：Constellation、Loop、Stage。

每种构型均实现：

1. 结构事实到世界锚点的确定性算法。
2. 新节点局部松弛、用户位置锁定和稳定 seed。
3. 远景聚合、中景主结构、近景详情三级 LOD。
4. 视锥裁剪、实例池、DOM 按需挂载和标签碰撞。
5. 构型切换动画与原视角恢复。
6. 自动推荐理由和用户锁定，不按题材名称机械选择。

Agent `orrery-layout-intent/v1` 在六种确定性构型稳定后再接入，并默认关闭。Agent 只输出 cluster、亲疏、强调、分离和构型建议；非法建议回退到确定性布局。

完成门：

- 五类结构样例不会全部排成同一幅地图。
- 同一输入重复计算坐标稳定；新增一个节点不会导致全图洗牌。
- 1000 场项目远景可读，聚焦章/场后只挂载可见详情。
- 构型切换不改变作品正式状态和窗口内容。

### M6：全功能空间仪表

按优先级实现：

1. **推进**：当前任务轨道、Agent 会话、阶段、暂停/继续和失败解释。
2. **决策**：真实候选、差异、后果、推荐证据和提交状态。
3. **规则**：文风、标点、Lint、节奏、详略和字数规则，显示对当前场景的影响。
4. **健康**：左侧常驻窄栏，显示 route gate、Review、Canon、字数和节奏风险。
5. **正文**：书脊入口、纵向长卷、章节目录、阅读位置和新正文提示。
6. **档案**：人物、世界、场景、分支和 Review，按相关节点锚定并可多开。
7. **交付**：单一信标、可交付证据、缺失项和正式导出。
8. **项目与设置**：新建入口、顶部作品带、独立设置页；帮助、详情和协议归入设置。

完成门：

- 每种仪表使用专属信息结构，不嵌入完整旧业务页面。
- 沉浸模式具备普通模式的全部正式功能。
- 未完成决策必然产生可见卡片；可交付状态严格来自后端门禁。
- 所有长文本使用统一 SafeMarkdown 或正文阅读器，不暴露原始 JSON/Markdown 标记。

### M7：节奏、详略与字数正式闭环

实施：

1. 扩展项目、卷、章、场景四级节奏曲线和 detail level。
2. 将场景功能、incoming/outgoing bridge、reader effect、目标字数和允许偏差写入正式 composition/generation task package。
3. AgentReview 强制检查节奏角色、桥接、详略和字数债务。
4. 规则仪表编辑后先展示影响范围；确认后走正式保存和需要重审的场景清单。
5. longform audit 聚合张力曲线、场景纹理重复、Promise/Payoff 和字数债务。

完成门：

- 用户在前端调整曲线后，下一场正式生成任务能读取该约束。
- Review 能对 exact candidate 给出节奏/桥接/字数证据。
- 已晋升正文不会因普通 UI 编辑被静默改写；涉及正式内容时必须进入修订路线。

### M8：视觉、动效、主题与无障碍

实施：

1. 统一语义色，题材皮肤只改变环境、材质、光线和背景。
2. 只保留生长、分叉、锚定、潮汐、沉静五种语义动效。
3. 对每种构型完成一次反模板截图评审，删除无语义装饰和循环动画。
4. 背景改为按需 WebP/AVIF；每个主题只加载当前资源。
5. 增加 motion、depth、quality 三项可访问设置；支持 reduced motion、低深度和 2D 模式。
6. 完成键盘、焦点、对比度、缩放、屏幕阅读摘要和列表等价操作。

完成门：

- 星仪获得第一眼至少 68% 视觉重力，其他模块安静服务。
- 静止十秒后仍适合工作；打开正文时环境活动降到 15%。
- 现实主义、历史、科幻样例都成立，不依赖古典奇幻材质。
- 1280×720 到 2560×1440 无重叠和横向溢出；窄屏功能不缺失。

### M9：迁移、桌面验收与发布

实施：

1. v0.9 Beta 默认启用 v3，但保留“兼容视图”一键回退。
2. 验证旧项目零迁移可读；布局偏好缺失时自动生成，不修改作品事实。
3. 验证断线、SSE 重连、WebGL context lost、后台任务恢复和 OpenCode 未配置状态。
4. 完成 Tauri dev、NSIS 安装、升级、卸载保留项目、冷启动和诊断导出。
5. 编写 v0.9 release note、验证报告和升级说明。
6. v3 达成功能等价、性能和桌面验收后才移除默认 v2；v2 代码至少保留到下一个稳定版本。

完成门：

- 用户可从安装、建项目、推进、决策、阅读到交付全程不离开客户端。
- 任何视觉状态都能追溯到正式 read model 或用户本地偏好。
- 回退兼容视图不会丢失项目、窗口外的正式状态或当前 Agent 任务。
- 安装版通过发布签名、更新 manifest 和干净环境 smoke test。

## 7. 性能与资源预算

### 7.1 加载预算

- 启动主 JS 目标不高于 `180 KB gzip`；Pixi 场域与星仪 v3 必须懒加载。
- Pixi 场域 chunk 目标不高于 `120 KB gzip`（渲染器按需分包），避免预取不必要的滤镜或资源。
- 首次进入星仪只加载当前主题；单张环境资源目标不高于 `900 KB`。
- 未使用主题、正文全文和节点详情不得预取。
- CSS 新增采用 feature scope；生产 CSS 原始体积不超过当前基线的 20% 增长。

### 7.2 渲染预算

- DPR 默认上限 `1.5`，高质量模式最多 `2`。
- DOM 节点标签按 LOD 挂载，默认同时不超过 80；窗口默认不超过 12 个，更多进入最小化轨道。
- 500 个候选实体只渲染视锥内实体；1000 场远景使用聚合与 impostor。
- 空闲状态停止连续 60 FPS；真实任务活动使用低频环境更新，交互/动画期间恢复高帧率。
- 窗口拖动、相机移动和节点投影不得触发全局 Vue 树重渲染。

### 7.3 数据预算

- v3 book 首帧不携带正文、完整人物档案或 Review 正文。
- SSE 发送 revision/delta；无变化时只保活，不重复完整 payload。
- 节点详情按需读取并按 source revision 缓存。
- 项目切换时取消旧请求、关闭旧流并清空旧世界实体，防止跨项目闪现。

## 8. 测试矩阵

### 8.1 后端

- Projection v3 schema、三层 LOD、六种构型提示和 source revision。
- 100/500/1000 场聚合、稳定 seed、delta 与缓存失效。
- Decision、Agent Observability、Progress 投影与正式 gate 一致。
- SSE 重连、Last-Event-ID、无变化保活和跨项目隔离。
- Rhythm/detail/word target 从前端保存到 task package、Review 和 audit 的契约测试。

### 8.2 前端单元与组件

- 相机世界/屏幕坐标互转、指针锚定缩放和边界。
- 六种布局稳定性、局部松弛、标签碰撞和 LOD。
- Window Manager 多开、锚定、拖动、复位、持久化和小屏降级。
- Projection Store 的 delta 合并、乱序丢弃、断线恢复和项目切换。
- 决策、交付、任务和节奏仪表不得伪造后端状态。

### 8.3 Playwright 与视觉

- 视口：1280×720、1440×900、1920×1080、2560×1440、390×844。
- 流程：进入星仪、平移、滚轮缩放、聚焦、开三窗、拖窗、切构型、切主题、打开正文、提交决策。
- Canvas 像素：非空、运动前后差异、背景加载、WebGL 降级。
- 截图：前中远景、窗口避让、无突兀空白、无控件遮挡、主题语义色一致。
- 可访问：键盘完成同等任务、reduced motion、列表等价视图和焦点恢复。

### 8.4 桌面

- Tauri sidecar 冷启动、端口恢复、目录选择、项目默认位置和本地会话认证。
- OpenCode 未配置、配置后启动、长任务、暂停、恢复、重试和退出清理。
- NSIS 全新安装、覆盖升级、更新失败回退和诊断导出。

## 9. 风险与控制

| 风险 | 早期信号 | 控制方式 |
|---|---|---|
| 伪 3D 变成纯背景 | 节点仍在独立二维层随机排布 | 先完成单场景纵向切片；每个空间实体必须对应语义 |
| 构型过多拖慢交付 | 六套布局同时半成品 | Alpha 先做 Spine/Braid/Strata，接口稳定后扩展后三种 |
| Projection v3 过载 | 首帧携带长文本或全部细节 | 摘要投影 + detail endpoint + LOD 聚合 |
| Vue 与 render loop 相互拖慢 | 相机移动触发大量组件更新 | Pixi mutable state 留在 renderer；Pinia 只存稳定交互状态 |
| 窗口再次压住星仪 | 多窗后中心不可见 | 视廊约束、碰撞换侧、最小化轨道和窗口上限 |
| 主题资产拖慢启动 | 构建包含所有大图且首屏预加载 | 路由/资源懒加载、WebP/AVIF、单主题预算 |
| Agent 创意布局不可复现 | 同一项目每次位置不同 | Agent 仅输出语义 intent；确定性布局器裁决并保留 seed |
| v0.9 破坏正式流程 | UI 显示成功但 route gate 失败 | 所有状态来自投影；正式动作继续调用既有 API/CLI |
| 大重构无法回退 | v2 被过早删除 | v2/v3 双轨、兼容视图、分阶段默认开关 |

## 10. 提交与集成纪律

建议按可回退的小提交推进：

```text
chore(v0.9): freeze baseline and add feature flag
feat(projection): add narrative projection v3 contracts
feat(orrery): add camera and world renderer vertical slice
feat(windows): add spatial window manager
feat(orrery): complete one-scene workflow slice
feat(layout): add semantic spatial grammars and lod
feat(instruments): add project workflow instruments
feat(rhythm): connect longform rhythm contracts
perf(orrery): lazy assets and adaptive rendering
test(v0.9): add visual and desktop acceptance
release: ArcVellum v0.9.0
```

每个里程碑结束必须：

1. 更新路线文档和完成状态。
2. 运行后端、前端、构建和该里程碑专项测试。
3. 保存桌面与窄屏截图。
4. 执行 `git diff --check`。
5. 不把测试日志、临时服务器日志和未压缩概念资产加入发布提交。

## 11. 第一批可直接执行的任务

按以下顺序开始，不需要再次做大范围架构讨论：

1. 新增 v0.9 feature flag、兼容视图和路由懒加载。
2. 建立 Projection v3 Python/TypeScript 契约与三组 fixture。
3. 增加 v3 REST/SSE 端点及 contract tests。
4. 安装 `pixi.js` 与 `pixi-viewport`，建立独立 `NarrativeParallaxStage` 技术样机。
5. 在 fixture 上完成二维纵深、DOM 投影、平移缩放和一个节点详情窗。
6. 接真实 scene projection，完成 M4 单场景闭环。
7. 截图与性能验收通过后，再进入六种构型和全部仪表。

## 12. v0.9 最终完成定义

只有同时满足以下条件才可发布：

1. 2.5D 场景具有真实空间体积、遮挡、视差和受控相机，不是地图加阴影。
2. 不同叙事结构可采用不同构型，且布局稳定、可回退、可解释。
3. 沉浸星仪具备推进、决策、规则、健康、正文、档案、项目、设置和交付的完整能力。
4. Agent 活动和任务进度实时可见，但不暴露内部推理。
5. 节奏、详略、桥接和字数约束真正进入正式创作与审查链路。
6. v0.8 正式文学流程、项目兼容性和安装版能力没有退化。
7. 性能、视觉、无障碍、断线恢复和桌面发布全部通过验收矩阵。
