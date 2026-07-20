# ArcVellum v0.5.1-v0.7 阅读、顾问与叙事观测计划

## 1. 文档状态

- 当前交付：`ArcVellum v0.7.0`
- 计划状态：已实施并进入发布验证
- 计划范围：`v0.5.1` 桌面稳定性收口、`v0.6.0` 作品库与完整阅读器、`v0.6.1` 顾问人格与主动消息、`v0.7.0` Narrative Observatory v1
- 主要平台：Windows 10/11 桌面客户端
- 架构前提：Tauri 2、Vue 3、FastAPI 本地服务、SQLite 事件与任务存储、内嵌文学工程内核、捆绑 OpenCode Agent Runner
- 评审依据：当前 `v0.5.0` 源码、前端测试、Tauri 配置、桌面打包行为与现有路线图

本计划不重复 `v0.4-v0.5` 已完成的产品化工作，只处理实际代码审查仍然确认存在的缺口。实施结果与发布证据见 `docs/releases/v0.7.0-verification.md`。

仓库内核历史上已经存在“Phase 11：FastAPI / LangGraph / Dify”。为了避免阶段编号冲突，本计划不再使用“Phase 11：视觉体系”，统一命名为 `Narrative Observatory v1`。

## 2. 当前实现结论

### 2.1 已经存在，不应重建

- Vue 3 + TypeScript 客户端；
- Tauri 2 Windows 桌面壳；
- FastAPI 本地应用服务与桌面会话认证；
- 项目创建、打开、最近作品登记；
- Dashboard 与 Library SSE；
- 已晋升正文的基础阅读框；
- 悬浮、流式、只读项目顾问；
- AutopilotController 与 CreativeSteward；
- 正式任务沙箱、写回、审查、晋升、Canon 和发布门禁；
- Narrative Observatory 的颜色 Token 和基础 StoryTrace 组件；
- 签名更新器与 NSIS 发布链路。

### 2.2 当前真实缺口

1. 原生目录选择在本机 HTTP 页面上缺少 Tauri remote capability，失败时界面没有反馈。
2. 新项目没有应用管理的默认作品库，用户必须先选择或填写父目录。
3. 用户作品、应用数据和安装目录的产品边界没有在设置中明确呈现。
4. 部分运行器探测和内核桥接未统一使用 Windows 无窗口进程参数。
5. 启动阶段自动预热模型目录，与“进入连接页后再加载”目标不一致。
6. Tauri 先加载内置页面再导航到本机 HTTP 页面，Vue 又有两套启动页关闭计时，导致过渡不连续。
7. Provider 列表没有稳定高度，连接页会随提供商数量无限增长。
8. 当前阅读器只接收 Library 摘要：最多 12 项，每项正文最多 9000 字符，不能承担整书阅读。
9. 正式正文缺少统一阅读顺序、版本覆盖和去重契约。
10. 顾问只有通用人格；Prompt 不是简单过短，而是缺少模块化角色层与可测试的语言风格约束。
11. 顾问只能回应用户问题，没有基于项目事件的主动消息收件箱。
12. StoryTrace 展示的是下一步任务列表，不是真实的场景、分支、人物、Canon、Promise/Payoff 叙事投影。
13. GitHub 仓库仍使用工程期名称，README、更新器和打包脚本存在硬编码地址。
14. 当前安装包重建可能被已有 bundle 文件或打包进程占用，发布前缺少明确的锁检查和恢复提示。

### 2.3 基线时已有的热修（现已纳入 v0.7.0）

- 目录对话框的 Tauri capability 已收窄授权到 `http://127.0.0.1:*`；
- 目录选择增加进行中状态、错误提示和手动路径回退；
- 新增 DesktopBridge 目录选择单元测试；
- Provider 列表增加固定最大高度和内部滚动；
- 前端 12 个测试、Vue 生产构建与 Tauri `cargo check` 已通过。

这些改动已经进入 v0.7.0 源码、安装包和发布验证，不再只是工作区热修。

## 3. 总体目标

下一阶段把 ArcVellum 从“能够自主执行文学工程流程的 Beta”提升为“普通创作者可以长期放置作品、边创作边阅读、理解项目变化，并以自己喜欢的顾问人格参与决策的桌面产品”。

目标体验：

1. 用户安装后立即拥有稳定、可理解的默认作品库；
2. 启动不闪终端、不二次白屏，不因模型服务离线而阻塞；
3. 已晋升正文按正式顺序自动进入完整阅读器；
4. 新正文生成时，读者可以继续当前位置并获知新增内容；
5. 顾问拥有可选择、可自定义、权限不变的人格；
6. 关键事件发生时，顾问可以克制地主动提醒；
7. 故事脉络图反映真实场景、分支、角色、Canon 和兑现关系；
8. 视觉更有辨识度，但正文阅读和长期工作仍安静、清晰；
9. 品牌、仓库、更新器和发行流程形成一致身份。

## 4. 非目标与硬边界

- 不把作品默认放进应用安装目录；
- 不自动移动现有作品；
- 不让阅读器读取候选稿、审查记录或工作流痕迹；
- 不让顾问或主动消息服务获得项目写权限；
- 不让人格 Prompt 改变顾问权限、事实来源或动作白名单；
- 不让动态图替代正式 Dashboard、决策面板或审计证据；
- 不为视觉效果引入无意义粒子、光球、持续背景运动；
- 不用位图替代标准功能图标；
- 不在启动健康检查中执行网络模型探测；
- 不改变文学工程内核作为唯一流程与正式写回权威的边界；
- 不在没有迁移与回滚方案时改变 Tauri identifier 或应用数据目录。

## 5. 目标架构

```text
Tauri Desktop Shell
  -> Single-document startup bridge
  -> Native directory dialog
  -> Hidden process launcher
  -> Signed updater

Vue Client
  -> Workspace and project library
  -> Reader Store / Reader Manifest
  -> Advisor Persona and Inbox Store
  -> Narrative Observatory Projection
  -> Settings / About / Diagnostics

FastAPI Application Service
  -> Project Library Service
  -> Reader Projection Service
  -> Advisor Persona Service
  -> Proactive Advisor Event Service
  -> Narrative Projection Service
  -> Cached Runtime Capability Service

Embedded Literary Engine
  -> Formal project facts and workflow gates
  -> Promotion / Canon / state / branch evidence
  -> Release and clean manuscript outputs
```

核心原则：Reader、Advisor 和 Observatory 都消费正式项目的只读投影，不建立第二套文学事实源。

## 6. 版本与实施顺序

### 6.1 `v0.5.1`：桌面可靠性热修

目标：让现有 Beta 的启动、目录和设置操作稳定可信。

必须完成：

1. 合入并回归目录选择 capability、状态反馈和手动路径回退；
2. Provider 列表进入滚动容器；
3. 增加统一 `run_hidden_process()`，替换运行器与 CoreBridge 的直接子进程调用；
4. 缓存 Agent Runner availability/capabilities，避免一次状态读取重复执行版本探测；
5. Bootstrap、health 和 SSE 快照只读取缓存；
6. 模型 Provider 目录改为进入“连接与模型”页或显式刷新时加载；
7. 打包前检测运行中的 Tauri/NSIS/build 进程和被占用的 bundle 文件；
8. 产出可覆盖安装的 Windows 安装包并验证目录对话框。

完成条件：

- 创建和打开作品均能打开系统目录窗口；
- 对话框被策略阻止时立即显示手动路径回退；
- 冷启动不闪出终端窗口；
- 不进入连接页时不启动 Provider 网络探测；
- 安装包可在中文用户名、空格路径和非系统盘覆盖安装。

### 6.2 `v0.6.0`：作品库与完整阅读器

目标：建立稳定作品位置，并把正式正文阅读从摘要卡升级为完整产品能力。

必须完成：

1. 默认作品库；
2. Reader Manifest v1；
3. 正文按需读取和增量事件；
4. 连续/分章阅读；
5. 阅读位置、目录、搜索和排版设置；
6. 新晋升正文的非打扰更新；
7. 正式正文去重、版本覆盖和完整性验证。

完成条件：

- 100 章、50 万字样例不会因摘要上限缺章或截断；
- 新场景晋升后自动进入正确顺序；
- 阅读中的用户不会被自动跳到新正文；
- 发布稿、章节稿和场景稿不会重复出现；
- 关闭应用后恢复项目、章节和滚动位置。

### 6.3 `v0.6.1`：顾问人格与主动消息

目标：让顾问成为可选择语言风格的长期创作伙伴，同时保持只读和可审计。

必须完成：

1. 顾问 Prompt 分层；
2. 内置人格库；
3. 自定义人格编辑、预览和校验；
4. 项目级和全局默认人格；
5. 顾问主动消息收件箱；
6. 关键事件触发、去重、节流、免打扰；
7. 主动消息到白名单动作建议的安全闭环。

完成条件：

- 同一事实在不同人格下只改变表达和关注角度，不改变证据与权限；
- 自定义人格无法注入 Shell、文件写入或越权动作；
- 没有用户问题时，关键事件可生成一次可追溯提醒；
- 重复 SSE 和重复事件不会生成重复提醒；
- 用户可以关闭全部主动消息或只保留阻塞提醒。

### 6.4 `v0.7.0`：Narrative Observatory v1

目标：让唯一重点视觉“动态故事脉络”成为真实、可探索、可降级的叙事状态投影。

必须完成：

1. Narrative Projection v1；
2. 场景、章节、分支、人物、Canon、Promise/Payoff 节点与边；
3. 全书、章节、当前场景三级视图；
4. 真实状态驱动的节点生长、分叉、淡出、点亮和凝结；
5. 大型项目的聚合与局部展开；
6. 键盘与列表式替代视图；
7. `prefers-reduced-motion`；
8. 受控视觉资产与启动过渡升级；
9. GitHub 仓库与产品身份收敛。

完成条件：

- 图上每个节点和连线都能追溯到正式项目事实或运行事件；
- 1000 场景项目默认只渲染聚合层，不形成不可读节点团；
- 动画关闭后所有状态仍清楚；
- 图形失败不影响创作、审批、阅读或导出；
- 390x844、1024x768、1440x900、1920x1080 均无重叠和裁切。

## 7. Workstream A：默认作品库与项目生命周期

### 7.1 目录策略

推荐 Windows 默认位置：

```text
%USERPROFILE%\Documents\ArcVellum\Works\
```

应用数据继续位于现有应用数据身份目录，安装目录只保留程序和内置资源。

配置新增：

```json
{
  "application": {
    "projects_root": "C:\\Users\\<user>\\Documents\\ArcVellum\\Works",
    "projects_root_source": "platform-default|user-selected",
    "portable_mode": false
  }
}
```

### 7.2 实现要求

- 由 Tauri/Rust 的平台路径 API 解析 Documents，不在 Python 中猜测本地化目录名；
- 首次启动只创建 ArcVellum 自己的目录；
- 新建作品默认使用 `projects_root`，用户仍可为单个作品改位置；
- 最近作品登记继续支持任意外部目录；
- 设置页显示“默认作品库”和“应用数据位置”，使用用户术语；
- 作品库改变只影响以后新建作品，不移动已有作品；
- 外接磁盘离线时保留登记并显示恢复操作；
- 项目重定位必须单独设计复制、校验、原子切换和回滚，不与默认目录功能混做。

### 7.3 迁移

- 配置 Schema 升级但兼容旧 `v0.3`；
- 缺少 `projects_root` 时在读取阶段派生默认值，保存设置时正式写入；
- 不修改 `projects.json` 中已有绝对路径；
- 不改变 Tauri identifier。

## 8. Workstream B：无窗口进程与启动状态机

### 8.1 统一进程层

新增一个跨平台进程工具，统一处理：

- Windows `CREATE_NO_WINDOW` 和 `STARTUPINFO`；
- UTF-8 stdout/stderr；
- 超时、终止和子进程树清理；
- 可预测的错误分类；
- 测试注入与 fake executable。

替换范围：

- `runtimes/base.py`；
- `runtimes/opencode.py`；
- `runtimes/claude_code.py`；
- `core_bridge.py`；
- 后续所有版本、认证、模型与诊断探测。

### 8.2 Runner 状态缓存

- availability 与 capabilities 一次探测共同生成；
- 结果带 `checked_at`、TTL 和 `stale`；
- 设置变化、安装 Runner、用户刷新时失效；
- Bootstrap 与 health 只读取缓存；
- 无缓存时返回 `unknown/checking`，不在请求线程启动程序。

### 8.3 单文档启动

当前“内置 index -> 本机 HTTP URL”的二次导航应被移除。目标是：

1. Tauri 一次加载打包前端；
2. Rust 注入动态 API base、桌面会话 token 和 backend-ready 事件；
3. Vue 应用壳在加载层后预渲染；
4. 单一启动状态机控制进入；
5. 350-500ms 遮罩淡出，不销毁并重建整个应用；
6. 冷启动保留最低展示时间，热启动快速通过；
7. reduced-motion 使用无位移动画。

启动阻塞项只包含数据库、内核、任务恢复和桌面会话。模型目录、更新检查和非关键索引全部延后。

## 9. Workstream C：Reader Projection 与完整阅读器

### 9.1 Reader Manifest v1

新增只读契约：

```json
{
  "schema": "arcvellum/reader-manifest/v1",
  "project_revision": "...",
  "generated_at": "...",
  "units": [
    {
      "unit_id": "chapter-001/scene-0001",
      "volume_id": "volume-001",
      "chapter_id": "chapter-001",
      "scene_id": "scene-0001",
      "order": 1,
      "title": "...",
      "status": "promoted|published",
      "source_kind": "scene|chapter|release",
      "source_revision": "...",
      "content_hash": "...",
      "chinese_content_chars": 0,
      "body_endpoint": "/reader/units/..."
    }
  ]
}
```

### 9.2 顺序与去重

- 顺序来自正式卷、章、场景清单和晋升证据，不按路径字符串猜测；
- `published > exported > chapter > promoted` 只能用于覆盖选择，不能产生重复阅读单元；
- release/chapter 若覆盖多个 scene，必须声明 coverage；
- 同一 scene 的旧 revision 不进入默认阅读流；
- 缺序号、重复覆盖或正文 hash 不一致时显示完整性警告，不静默拼接；
- 候选稿、修订候选、review、AgentTask、Canon patch 永不进入 Reader Manifest。

### 9.3 API

- `GET /reader/manifest?project_root=...`：轻量目录与版本；
- `GET /reader/units/{unit_id}`：按需返回完整干净正文；
- `GET /reader/stream?project_root=...&cursor=...`：只推送 manifest delta；
- `GET /reader/search?...`：搜索正式正文；
- 阅读位置默认保存在本机 Studio 数据库，不写入文学项目；
- 用户书签和私人笔记与正式作品事实分离。

### 9.4 阅读体验

- 连续阅读与分章模式；
- 卷/章目录抽屉；
- 中文长篇版心控制在约 34-42em；
- 字号、行高、段间距、首行缩进和明暗主题；
- 章节标题后首段不强制缩进；
- 全屏、键盘翻章、搜索、书签和阅读进度；
- 新正文进入时显示“不打断阅读”的新增提示；
- “跟随创作进度”是显式开关，默认关闭；
- 候选/正式状态在产品语言中清楚区分。

### 9.5 性能

- 不把整本书塞进 Dashboard 或 Library SSE；
- Manifest 只包含元数据；
- 正文按当前章节及邻近章节预取；
- 章节正文缓存按 hash 失效；
- 长列表虚拟化；
- 搜索索引可异步重建，失败不阻止阅读。

## 10. Workstream D：顾问 Prompt、人设与主动消息

### 10.1 Prompt 分层

顾问最终 Prompt 由以下固定顺序组成：

1. `Advisor Constitution`：只读、证据、诚实、不越权、不声称执行；
2. `Conversation Policy`：自然对话、追问、不同意见、避免报告腔；
3. `Persona Profile`：语言节奏、关注重点、质疑方式、禁用表达；
4. `Project Context`：只读快照、当前界面和项目状态；
5. `Memory`：会话摘要与用户长期偏好；
6. `Output Transport`：隐藏元数据和动作建议协议。

人格层不得覆盖第 1、4、6 层。

### 10.2 内置人格

首批建议：

- `chief-editor` 严谨总编：结构、因果、删改优先，语气克制直接；
- `dramaturg` 戏剧构筑师：冲突、转向、场景压力和节奏；
- `cold-reader` 冷面读者：只从实际阅读感受判断拖沓、解释和悬念；
- `warm-peer` 温和同行：支持探索但不无条件赞同；
- `mystery-auditor` 悬疑审计员：线索公平性、误导、兑现与逻辑漏洞；
- `custom` 用户自定义。

每个人格应明确：关注优先级、回答节奏、反对方式、追问倾向、禁用套话和示例对话。不是只换名字或头像。

### 10.3 自定义人格

- 结构化表单与高级文本模式并存；
- 限制 Prompt 长度；
- 过滤工具、文件、Shell、网络、越权和系统覆盖指令；
- 保存前展示“会改变什么/不会改变什么”；
- 用固定项目问题预览三轮回答；
- 全局默认与项目级覆盖分离；
- 人格版本进入顾问消息元数据，方便复现。

### 10.4 主动消息

新增 `Advisor Inbox`，消费持久运行事件与正式项目投影，触发条件至少包括：

- 等待用户选择；
- 审查阻塞或多次修订；
- 字数预算显著偏离；
- Canon 冲突或高风险写回待批；
- 新正文晋升；
- 章节/卷完成；
- Autopilot 暂停、预算触顶或重复失败；
- Promise/Payoff 长期未兑现。

主动消息生成流程：

```text
formal event
  -> deterministic trigger and dedupe key
  -> read-only context snapshot
  -> advisor message generation
  -> inbox persistence
  -> SSE unread notification
  -> optional whitelist action
```

关键限制：

- 先由确定性规则决定是否值得提醒，不能让 LLM 自由轮询项目；
- 同一事件只生成一次；
- 普通消息按时间窗口聚合；
- 阻塞和风险消息可即时；
- 支持全部关闭、仅阻塞、标准、积极四档；
- 支持免打扰时段；
- 顾问不能因为主动消息直接批准分支、Canon 或发布；
- 自动模式中的 CreativeSteward 决策仍走独立授权协议。

## 11. Workstream E：Narrative Observatory v1

### 11.1 视觉命题

继续采用 `Narrative Observatory`：精密的叙事观测仪器。

颜色语义固定为：

```text
Midnight Moss   #102621  观测空间
Mineral White   #F5F8F6  阅读与工作表面
Jade Current    #2D7465  当前推进与健康状态
Cinnabar Signal #D95B45  阻塞、冲突和待决定
Brass Memory    #B8954B  正式文本、记忆和兑现
Iris Accent     #71668F  备选分支、不确定性和顾问
```

不得把六种颜色平均装饰在每个页面。颜色必须表示状态。

### 11.2 Narrative Projection v1

投影只从正式数据生成：

- 卷、章、场景与顺序；
- 当前任务和场景状态；
- 分支候选、选中与放弃；
- 参与角色与关系压力；
- Canon 变更候选、批准和写回；
- Promise/Payoff；
- Reader Question；
- 正文候选、审查、晋升与发布；
- 字数预算、实际正文和欠账。

节点必须携带 `source_type`、`source_id` 和可导航目标。缺少正式证据时不画节点。

### 11.3 三层信息密度

1. 全书层：卷、主要人物弧、主线 Promise/Payoff、总体字数长卷；
2. 章节层：场景序列、桥接、张力、分支和兑现；
3. 当前场景层：角色、Canon、候选、审查、晋升与下一步。

大型项目默认聚合，只展开当前章节和相邻关系。不要一次渲染数百个可交互节点。

### 11.4 真实动效映射

- task queued：低权重潜伏节点；
- task running：节点与边产生一次定向流动；
- scene generated：节点从轮廓变为实体；
- branch proposed：线路分叉；
- branch selected：未选线路降权但可回看；
- review blocked：朱砂裂口标记，不持续抖动；
- promoted：节点凝结并进入阅读长卷；
- canon applied：关联人物和世界节点一次性点亮；
- advisor action accepted：建议形成一条进入任务脉络的可追溯边；
- word growth：表现为章节长卷累积，不使用虚假百分比。

### 11.5 技术路线

- 先完成投影 Schema 和静态图，再增加动画；
- 优先评估 Cytoscape.js 等成熟 2D 图渲染方案；
- 布局结果必须稳定，刷新后不能随机乱跳；
- 任何图形库只负责渲染，不拥有文学事实和业务状态；
- 提供等价列表视图、键盘导航和屏幕阅读器摘要；
- Canvas/SVG 做非空像素与边界测试；
- reduced-motion 下禁用路径流动和节点生长，只保留状态切换。

### 11.6 视觉资产策略

可以使用图像生成模型，但只生成少量高价值位图：

1. 启动场景的低对比度“叙事图谱与稿页”背景；
2. 空作品库/空阅读器的主题插画；
3. 顾问人格头像组；
4. 可选的卷封面底图。

禁止：

- 用生成位图做保存、搜索、设置、返回等功能图标；
- 把插画缩成难辨识的小图标；
- 在正文背后放高对比图像；
- 使用与状态无关的光球、粒子和循环背景；
- 未经裁切、压缩、版权和明暗模式验证就打包。

Lucide 继续承担功能图标。所有位图提供用途说明、1x/2x、WebP 和回退背景色。

## 12. Workstream F：设置、关于与产品语言

- Provider 列表使用稳定滚动区域、sticky 搜索与“已连接优先”分组；
- Provider 详情按需展开，不在一个页面展示全部模型；
- 默认作品库、应用数据、缓存、日志和导出目录清楚区分；
- 普通页面不暴露 Schema、Runtime、Task Package、哈希和原始路径；
- 高级诊断保留完整证据和导出；
- 设置更改提供立即生效、需重启和只影响新项目三种清晰反馈；
- 关于页面显示版本、更新通道、发行说明、许可证和诊断入口；
- 更新失败不阻塞创作与阅读。

## 13. Workstream G：品牌、仓库与发布迁移

### 13.1 仓库名称

当前产品已经从工程期 Studio 发展为独立桌面产品，推荐：

```text
GitHub repository: arcvellum
Product name: ArcVellum
Subtitle: Longform Narrative Studio
```

Python 包名、sidecar 文件名和 Tauri identifier 可暂时保留，避免无收益的内部重命名和迁移风险。

### 13.2 改名清单

- GitHub repository；
- 本地 remote；
- README clone/release URL；
- `tauri.conf.json` updater endpoint；
- `packaging/build_desktop.ps1` release base URL；
- GitHub Actions、release 文档和徽章；
- 安装包元数据与产品描述；
- GitHub description、topics 和截图；
- 旧地址跳转验证。

### 13.3 发布可靠性

- 打包前检测目标安装包是否被占用；
- 不静默覆盖正在运行的 NSIS；
- 构建目录锁冲突输出可执行恢复步骤；
- 版本号在 Python、npm、Cargo、Tauri 和更新清单保持一致；
- updater artifact 和安装包签名在发布前交叉验证；
- 真实覆盖升级验证项目登记、配置、顾问记忆和阅读位置。

## 14. 数据与 Schema 迁移

建议新增或升级：

```text
config v0.4
reader_manifest v1
reader_position v1
reader_bookmark v1
advisor_persona v1
advisor_inbox_message v1
advisor_notification_policy v1
narrative_projection v1
runtime_capability_cache v1
```

数据库迁移要求：

- 迁移前备份；
- 幂等；
- 可从旧版本重复打开；
- 失败时保持旧数据库可恢复；
- 不把正文全文复制进 SQLite；
- 只保存阅读位置、索引元数据、消息和投影缓存；
- 投影可从项目事实重建，不成为权威源。

## 15. 测试矩阵

### 15.1 后端

- 默认作品库解析与配置迁移；
- 中文、空格、长路径和无写权限目录；
- Reader 顺序、覆盖、去重、完整性与正文清洁；
- 100 章/50 万字 manifest 性能；
- Runner 探测缓存、失效和并发；
- 主动消息触发、去重、节流和免打扰；
- 人格 Prompt 权限不可覆盖；
- Narrative Projection 来源追溯与重建。

### 15.2 前端

- 目录对话框成功、取消、拒绝和手动回退；
- Provider 滚动、搜索、折叠和键盘操作；
- Reader 连续/分章、目录、搜索、设置、恢复位置；
- Reader SSE 新增正文但不改变当前滚动；
- 顾问人格选择、自定义预览和主动消息；
- Observatory 三层缩放、节点选择和列表替代视图；
- 390x844、1024x768、1440x900、1920x1080 截图；
- reduced-motion、焦点、对比度和屏幕阅读器。

### 15.3 桌面与发布

- 冷启动与热启动录像：无终端闪烁、无二次白屏；
- Windows 10/11 干净虚拟机；
- 无 Python/Node/Rust 环境；
- 非系统盘安装；
- 中文用户名；
- 离线启动；
- Provider 不可用；
- 应用异常退出与任务恢复；
- 覆盖升级与签名更新；
- GitHub 改名后的 updater 下载。

## 16. 交付顺序与依赖

```text
v0.5.1 directory/process/bootstrap hotfix
  -> stable desktop and lazy provider loading
  -> v0.6.0 projects_root + Reader Manifest
     -> complete reader + incremental reading
     -> v0.6.1 persona profiles + advisor inbox
        -> proactive event projection
        -> v0.7.0 Narrative Projection
           -> dynamic Observatory + generated visual assets
           -> repository rename and release identity convergence
```

依赖判断：

- 先修进程和启动，否则后续视觉优化会被窗口闪烁抵消；
- Reader Manifest 必须先于完整阅读器 UI；
- 主动顾问必须先有确定性事件触发和持久 Inbox；
- Narrative Projection 必须先于动态图；
- 图像资产最后制作，避免在布局未稳定时重复生成；
- 仓库改名应与一个正式版本发布一起完成，避免更新器地址长期处于中间态。

## 17. 优先级与范围控制

### Must

- 目录与 Provider 热修正式发布；
- 无窗口进程与启动状态机；
- 默认作品库；
- Reader Manifest 与完整正文读取；
- 阅读顺序、去重和位置恢复；
- 顾问人格权限隔离；
- 主动消息确定性触发、去重和关闭能力；
- Narrative Projection 来源追溯；
- 发布与迁移验证。

### Should

- 阅读搜索、书签与主题；
- 多种内置顾问人格；
- 主动消息分级与免打扰；
- Observatory 三层视图和稳定布局；
- GitHub 仓库改名。

### Could

- 便携模式；
- 私人阅读笔记；
- 卷封面生成；
- 更复杂的图布局和导出图片；
- 人格分享与导入。

范围削减时不得删除 Reader 正式性、顾问权限边界、事件去重、reduced-motion 和迁移回滚。

## 18. 主要风险与对策

### 风险 1：Reader 建立第二套正文事实

对策：Manifest 只引用晋升、章节和 release 证据，可重建，不编辑正文。

### 风险 2：主动顾问变成打扰

对策：确定性触发、事件去重、聚合、频率限制、免打扰和默认克制模式。

### 风险 3：人格覆盖安全 Prompt

对策：Prompt 分层、固定优先级、自定义内容校验、只读快照前后哈希检查。

### 风险 4：动态图成为不可读关系团

对策：三级 LOD、当前邻域展开、稳定布局、节点上限和列表替代视图。

### 风险 5：启动重构破坏桌面认证

对策：先定义 Tauri-to-frontend bootstrap bridge 集成测试，再移除 HTTP 二次导航；保留回退开关一个小版本。

### 风险 6：仓库改名中断更新

对策：同版本验证旧 URL 跳转和新 URL 直连，发布清单只写新地址，保留迁移说明。

### 风险 7：视觉投入挤压核心功能

对策：投影和阅读先行；图片资产与高级动效只有在数据契约、性能和可访问性通过后进入。

## 19. Definition of Done

本阶段只有同时满足以下条件才算完成：

1. 源码、安装包和已安装客户端行为一致；
2. 用户无需选择目录即可在默认作品库创建作品，也可选择外部位置；
3. 启动无终端闪烁、无二次白屏，离线模型不阻塞进入；
4. 50 万字项目可以完整、按序、无重复阅读；
5. 创作推进中新增正文能进入阅读器而不打断当前位置；
6. 顾问人格可选、可自定义、不可越权；
7. 顾问可在关键节点主动提醒，且可关闭、去重、追溯；
8. 故事脉络图只展示有正式来源的节点和关系；
9. 动效、图形或图片加载失败不影响核心操作；
10. 桌面、前端、后端、迁移、安全、可访问性和发行测试通过；
11. GitHub、README、更新器、安装包和产品名称一致；
12. 所有新投影都可重建，不削弱文学工程内核门禁。

## 20. 下一步执行入口

实现从 `v0.5.1` 开始，不应并行启动 Reader、顾问主动消息和动态图三个大型改造。

第一批任务顺序：

1. 合入现有目录与 Provider 热修；
2. 新增无窗口进程工具并替换全部探测调用；
3. 增加 Runner 状态缓存与惰性 Provider 加载；
4. 完成单文档启动技术验证；
5. 构建、安装并回归 `v0.5.1`；
6. 再开始 `projects_root` 与 Reader Manifest v1。

每个版本完成后更新本文件状态、`implementation-route.md`、发行说明和验证记录，不用一次性打包全部版本后才验收。

## 21. 实施结果

ArcVellum v0.7.0 已按本计划的数据依赖顺序完成：

1. 桌面侧统一隐藏进程、Runner 探测缓存、Provider 延迟加载、单文档启动桥和打包锁检查；
2. 默认作品库、Reader Manifest v1、正文按需读取、搜索、书签、位置恢复、连续/分章阅读与增量通知；
3. 顾问 Prompt 分层、五种人格、自定义人格、持久主动消息、去重、免打扰和安全动作建议；
4. Narrative Projection v1、全书/章节/场景视图、真实状态动画、聚合、列表替代视图和减少动态支持；
5. GitHub 身份、更新器地址、README、版本号和 Windows 发布产物统一到 ArcVellum v0.7.0。

发布验证结果：105 个 Python 测试、13 个 Vue 测试、Prompt Registry 25 个资产/61 个任务 Prompt ID 零警告，冻结 sidecar 和签名 NSIS 安装包烟测通过。详见 `docs/releases/v0.7.0-verification.md`。
