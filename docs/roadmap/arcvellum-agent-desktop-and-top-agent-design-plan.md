# ArcVellum Agent Desktop 与顶层 Agent 分阶段设计方案

> 状态：D2-D4 已完成；只读 Project Agent 产品切片通过，D5 写工具仍需独立接口审查
>
> 日期：2026-09-13
>
> 适用范围：ArcVellum Studio 前端产品外壳、项目级顶层 Agent、既有功能复用和后续迁移
>
> 本文不授权修改文学内核、任务状态机、正式资产写回协议或 Pi Worker 创作职责。

> 第二轮评审结论：产品方向成立，原方案低估了 Pi 与 Python Application Service 之间的双向工具协议、动作幂等与中断恢复成本。本文已把这些问题提升为 D2/D3 的前置门禁。

## 1. 结论

ArcVellum 下一阶段采用双主界面：

1. **Agent 工作台**作为默认入口。用户通过持续对话表达目标、查看执行、修正方向和处理少量高风险确认。
2. **叙事星仪**继续作为空间化项目视图。它显示与 Agent 工作台相同的项目事实、创作进度和当前焦点。

复杂功能由顶层 Agent 通过类型化工具调用现有 Application Service/API 完成。现有阅读器、创作现场、档案 IDE、文风工坊、质量规则、节奏规划、决策、交付、设置、SSE 与星仪投影继续复用。它们不再共同组成要求普通用户逐页操作的主流程，而是以下三类能力：

- Agent 可以调用的项目能力；
- Agent 可以打开的可视工作区；
- 用户可以随时直接进入的展示工作区和高级手动接管界面。

本轮选择制作一个纯 HTML 视觉原型，不生成概念图。桌面 Agent 的成败依赖信息层级、面板比例、长文本滚动、工具反馈和操作连续性，HTML 原型比静态生图更能验证这些约束。

## 2. 实际工程基线

以下判断来自当前仓库，而非未来设想。

### 2.1 已有前端能力

- `client/src/App.vue` 已把常规主导航收敛为作品、创作星链和设置，并在全局挂载 `AdvisorDock`。
- `client/src/router.ts` 仍保留阅读器、档案管理、作品考古、文风工坊、质量规则、创作策略、Agent 观测、交付和说明页。
- `client/src/features/creative-live/` 已拥有正文候选、审查、修订、会话、工具与执行时间线投影。
- `client/src/features/archive/` 已拥有资产树、结构化编辑、影响分析、历史、回收站与候选晋升。
- `client/src/features/style-atelier/` 已拥有作者、作品、语料、版本和挂载工作流。
- `client/src/features/orrery/` 已拥有空间布局、相机、关系线、人物、章节、场景、实时状态与窗口系统。
- `client/src/components/ManuscriptReader.vue` 和 Reader route 已承担正式正文阅读。

结论：前端缺少统一的人机协作外壳，不缺业务页面。新设计应复用功能，避免重写业务组件。

### 2.2 已有顾问能力与限制

- `advisor/service.py` 提供项目会话、持久记忆、人格、快照和完整性检查。
- `advisor/runtime.py` 通过内置 Pi Worker 运行，并把回答以 SSE 增量送往前端。
- `advisor/prompt.py` 明确禁止文件修改、Shell、网络、子 Agent 和直接工作流操作。
- `AdvisorDock.vue` 已支持自由对话、Markdown、人格切换、主动提醒和前端动作卡。
- `workspaceCommands.ts` 只支持导航、记录方向、运行路线和 Autopilot 启停六类客户端命令。

结论：当前顾问适合作为顶层 Agent 的会话与展示基座，不适合作为可执行 Agent 直接扩权。其“只读快照完整性”是明确安全语义，不能靠删除几行提示词把它改造成项目执行器。

### 2.3 已有后端能力

当前 API 已覆盖：

- 作品创建、打开、默认目录和创作方向；
- Workflow dashboard、当前任务和人类选择；
- Worker 准备、运行、停止、重试和写回；
- Autopilot 启停、策略、状态和事件流；
- Creative Live 会话、产物版本和流式事件；
- 档案读取、编辑、影响分析、恢复和候选晋升；
- 文风语料、构建、推进、版本与挂载；
- 质量规则和全文节奏计划；
- Reader、Library、Delivery、Narrative projection；
- Pi Worker provider、credential 和 model 配置。

`runtime/capabilities/` 已实现任务作用域内的 Capability Broker、白名单、路径策略、结果限额和审计。它当前服务正式 Worker 任务，不能直接等同于项目级顶层 Agent 的长期工具面。

### 2.4 不应重复建设的部分

- 不建立第二套文学状态机。
- 不建立第二套项目文件模型。
- 不建立新的正文、档案或星仪数据源。
- 不另建 WebSocket；现有 SSE 足以覆盖单向状态与正文流。
- 不让顶层 Agent 直接编辑项目文件。
- 不让浏览器成为业务事实的最终写入者。
- 不因新的 Agent 工作台而重写 Pi Worker 的正式创作闭环。

## 3. 外部调研带来的约束

### 3.1 桌面 Agent 工作台

OpenAI Codex App 把任务组织为项目内的独立会话，并将并行执行、长期任务、结果审阅和人工接管放在统一工作台中。这说明 ArcVellum 的默认界面应围绕“会话、执行、产物”组织，而非围绕后端模块组织。

参考：<https://openai.com/index/introducing-the-codex-app/>

Cursor Agent 的 checkpoint、消息队列和运行中即时指令表明，用户需要在长任务中拥有三种控制：稍后执行、立即纠偏、回到稳定状态。ArcVellum 应复用现有项目版本和任务 receipt 表达回退，不另造一套文件 checkpoint。

参考：<https://cursor.com/docs/agent/overview>

### 3.2 笔记平台的内容秩序

Notion 2026 页面设计更新强调按相邻块关系调整间距，让混合内容形成稳定的垂直节奏。ArcVellum 的 Agent 对话会同时出现自然语言、执行步骤、正文、审查意见和确认卡，不能对所有块使用同样的卡片和间距。

参考：<https://www.notion.com/en-gb/blog/updating-the-design-of-notion-pages>

Notion 桌面端提供跟随系统、浅色、深色和高对比度外观。ArcVellum Agent 工作台采用同类设置结构，但保留自己的文字与状态语义。

参考：<https://www.notion.com/en-gb/help/account-settings>

### 3.3 Agent 架构

OpenAI 的 Agent 实践指南建议先扩展单 Agent 的工具能力，只有工具重叠、条件逻辑或职责冲突已经造成可靠性问题时再拆分多 Agent；管理者模式适用于只希望一个 Agent 面对用户的产品。

参考：<https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/>

Anthropic 对有效 Agent 的总结强调简单、透明、可组合，并要求工具接口有清晰文档和验证。复杂度只有在可测量地改善结果时才应增加。

参考：<https://www.anthropic.com/engineering/building-effective-agents>

Anthropic 的上下文工程建议进一步指出：工具应尽量自包含、低重叠、参数明确；上下文应追求高信息密度，而非持续累积完整历史。ArcVellum 因而不能把全部项目资料和全部工具长期塞入顶层 Agent。

参考：<https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>

OpenAI Agents SDK 的 human-in-the-loop 采用可暂停、持久化和继续的 tool approval，而非在每个普通动作前都弹窗。ArcVellum 应把确认集中到高风险、不可逆或用户锁定的操作。

参考：<https://openai.github.io/openai-agents-python/human_in_the_loop/>

OpenAI 的 tool guardrail 文档强调，管理者 Agent 的每次自定义工具调用都应在工具边界执行输入与输出检查。ArcVellum 的风险校验应落在 Action Executor，而非只写在系统提示词里。

参考：<https://openai.github.io/openai-agents-python/guardrails/>

## 4. 产品信息架构

### 4.1 双主界面

```text
ArcVellum
├─ Agent 工作台（默认）
│  ├─ 项目与会话
│  ├─ 对话和执行现场
│  ├─ 正文/档案/审查内嵌预览
│  └─ 当前上下文与待确认事项
├─ 叙事星仪
│  ├─ 同一项目状态
│  ├─ 同一当前章节/场景焦点
│  └─ 同一 Agent 会话和执行活动
└─ 独立设置
   ├─ 模型与连接
   ├─ 外观、可访问性与更新
   └─ 关于、帮助、协议与诊断
```

Agent 与星仪不是两套产品。切换时必须保留：

- 当前作品；
- 当前 Agent 会话；
- 当前任务或场景；
- 打开的产物；
- 等待用户确认的操作；
- Creative Live 的当前 run。

### 4.2 Agent 工作台布局

```text
┌──────────────┬──────────────────────────────────┬──────────────────┐
│ 作品与会话    │ Agent 对话与工作现场              │ 当前作品上下文    │
│              │                                  │                  │
│ 搜索          │ 用户目标                          │ 当前章节/场景      │
│ 新对话        │ Agent 回复与计划                  │ 正在执行          │
│ 最近会话      │ 工具调用与结果                    │ 待确认决定         │
│ 运行状态      │ 正文/档案/差异的内嵌预览           │ 相关人物与约束      │
│              │                                  │                  │
├──────────────┴──────────────────────────────────┴──────────────────┤
│ 附件 / 输入框 / 执行模式 / 发送或停止                               │
└────────────────────────────────────────────────────────────────────┘
```

#### 左栏

- 固定宽度 232–252 px，可折叠为 56 px 图标栏。
- 只显示作品、搜索、新会话、最近会话和运行状态。
- 不陈列文风构建、规则写入、档案晋升等复杂操作流程；保留正文、现场、档案、文风成果、观测和交付状态的直接查看入口。
- 会话显示自然语言标题、活动状态和最后更新时间。

#### 中央工作区

- 对话是主轴，最大阅读宽度 760–860 px。
- Agent 的普通回复不放卡片。
- 工具调用折叠成一组可展开的“行动记录”。
- 正文、人物卡、文风版本、审查结果和 diff 使用各自的内容组件，不以 JSON 代码块展示。
- Creative Live 的候选正文可以嵌入当前回合，正式正文仍由 Reader 权威展示。
- 用户在 Agent 工作时可以选择排队消息或立即纠偏。

#### 右栏

- 宽度 288–328 px，可折叠。
- 默认只显示当前任务、当前作品焦点、等待确认和最近正式变化。
- 详细技术 ID、原始事件和运行日志进入“高级信息”。
- 不把右栏做成第二个控制台。

#### 输入区

- 固定在中央区底部，不遮挡滚动内容。
- 支持文本、附件、停止和执行模式。
- 模式为“协作”“托管”“全自动代理”，描述的是审批行为，不直接改变创作质量规则。
- 当前模型、连接和成本只显示摘要；完整配置进入设置。

### 4.3 保留功能的呈现方式

| 现有能力 | 默认呈现 | 用户手动入口 |
| --- | --- | --- |
| 正文阅读 | Agent 内嵌节选、晋升后提醒 | Reader 全屏工作区 |
| 创作现场 | 当前回合中的实时正文和行动记录 | Creative Live 侧板/全屏 |
| 档案 IDE | Agent 查询、编辑预览和影响摘要 | Archive 全屏工作区 |
| 文风工坊 | Agent 导入、构建、挂载与版本说明 | Style 全屏工作区 |
| 质量与节奏 | Agent 解释并修改配置，显示差异 | Quality 高级工作区 |
| 人类决策 | 对话内确认卡和右栏待办 | 决策历史抽屉 |
| 交付 | Agent 完成预检后展示交付卡 | Delivery 全屏工作区 |
| Agent 观测 | 当前回合中的工具和会话摘要 | Observatory 高级工作区 |
| 设置 | Agent 仅能打开或解释 | 独立设置页面 |

这里的“Agent 接管”指 Agent 调用正式后端能力，不是让 Agent 在前端替用户点击旧页面。

### 4.4 展示入口保留原则

顶层 Agent 统一复杂操作后，原有展示性入口仍是 ArcVellum 的重要产品能力，不能被埋入对话或只允许 Agent 打开。

保留为稳定直达入口：

- 正文长卷与完整 Reader；
- 创作现场和当前候选正文；
- 项目档案浏览与关系查看；
- 文风成果、版本和当前挂载状态；
- Agent 会话与任务观测；
- 叙事星仪；
- 项目健康、交付准备度和已生成文件；
- 设置、帮助、详情和协议。

呈现规则：

- Agent 工作台左栏增加紧凑的“查看工作区”，使用图标和短名称，不展开复杂操作菜单。
- 当前最相关的展示入口也可以出现在回答、产物卡和右栏中。
- 进入展示工作区不改变任务状态、不自动执行操作、不要求 Agent 中转。
- 展示页中已有的高级编辑能力可以继续存在，但默认收起或进入明确的“手动接管”状态。
- D8 清理只能删除重复外壳和失效入口，不能删除仍有独立阅读、观察或展示价值的 route 与组件。

## 5. 视觉系统

### 5.1 视觉命题

**安静的项目笔记台，正在工作的 Agent 留下清晰的手稿边迹。**

工作台借鉴主流桌面 Agent 和笔记平台的秩序，但不复制任何产品。ArcVellum 的记忆点来自“手稿脊线”：中央内容左侧有一条很细的纵向脉络，连接用户目标、Agent 行动、候选正文、审查和正式晋升。它编码真实创作阶段，不是装饰时间线。

### 5.2 色彩令牌

#### 浅色默认

| 令牌 | 色值 | 用途 |
| --- | --- | --- |
| Canvas | `#F7F7F5` | 应用背景 |
| Surface | `#FFFFFF` | 对话和正文表面 |
| Raised | `#F1F1EF` | 工具记录、选择区域 |
| Border | `#E4E4E0` | 分隔线 |
| Ink | `#2F3437` | 主文字 |
| Muted | `#787774` | 次要文字 |
| Blue | `#3F6F9F` | 当前行动、链接 |
| Green | `#4F765F` | 已完成、已晋升 |
| Ochre | `#9A672F` | 待确认、提醒 |
| Red | `#A84D49` | 阻断、失败 |
| Violet | `#71647D` | 文风、记忆和文学资产 |

#### 深色

| 令牌 | 色值 | 用途 |
| --- | --- | --- |
| Canvas | `#191919` | 应用背景 |
| Surface | `#202020` | 对话和正文表面 |
| Raised | `#292929` | 工具记录、选择区域 |
| Border | `#383836` | 分隔线 |
| Ink | `#ECECEA` | 主文字 |
| Muted | `#A8A8A3` | 次要文字 |
| Blue | `#75A7D8` | 当前行动、链接 |
| Green | `#76A889` | 已完成、已晋升 |
| Ochre | `#D0A05E` | 待确认、提醒 |
| Red | `#D77A73` | 阻断、失败 |
| Violet | `#A99BB7` | 文风、记忆和文学资产 |

颜色只表达语义。禁止使用大面积单色状态卡、彩色渐变、光球和装饰性发光。

### 5.3 字体

- UI：`Segoe UI Variable`、`PingFang SC`、`Microsoft YaHei UI`、`Noto Sans SC`。
- 正文与作品片段：`Iowan Old Style`、`Source Han Serif SC`、`Noto Serif SC`、`Songti SC`。
- 技术摘要：`Cascadia Code`、`SFMono-Regular`，只用于时间、digest 缩写和高级信息。
- Agent 普通回复使用无衬线；引用作品和正式正文才切换衬线，建立清晰身份差异。

### 5.4 形状与层级

- 面板圆角 4–6 px。
- 普通回复、段落和列表不放卡片。
- 卡片只用于可重复条目、待确认、产物预览和错误。
- 边栏和右栏用分隔线划分，不用悬浮大卡包住整个区域。
- 阴影只用于浮层、命令面板和拖出的工作区。

### 5.5 动效

- 流式回答按段落增量显示，禁止伪造打字动画。
- 工具组展开使用 140–180 ms 位移与淡入。
- 当前任务在手稿脊线上缓慢呼吸；无任务时静止。
- 正文晋升时，候选标记平滑转为正式标记，不播放庆典式动画。
- Agent/星仪切换保留当前焦点并使用一次 220–300 ms 场景过渡。
- 尊重 `prefers-reduced-motion`，所有信息在无动画时仍完整。

### 5.6 第二轮视觉审查

当前 HTML 原型适合作为信息架构和密度基线，尚不足以成为生产视觉定稿。

主要风险：

1. 三栏 Agent 桌面是成熟模式，也容易让 ArcVellum 看起来像通用聊天客户端；手稿脊线和作品内容字体需要在真实组件中证明品牌辨识度。
2. 右栏一旦承载项目健康、规则、人物、任务和确认，会重新长成旧仪表盘；默认只能显示“当前焦点、当前运行、待确认”三类信息。
3. 把 Reader、Archive 或 Creative Live 整页嵌入消息，会造成嵌套滚动、重复订阅和狭窄正文；消息中只展示摘要与只读预览，完整工作区继续独立打开。
4. Notion-like 中性工作台与深色星仪视觉差异很大；两者应共享字体、状态色、窗口 chrome 和焦点身份，不强行共享背景与空间材质。
5. 长会话若把每个 token、工具事件和正文版本永久挂在 DOM，会比现有前端更卡；消息分段、工具组折叠、虚拟列表和 SSE 合并是生产前置条件。

修订后的视觉出口：原型先验证“用户能否自然对话、看见行动、打开作品工作区”；品牌动效与最终皮肤在 D7 接入真实数据后评审。D1 不以一张静态截图宣告视觉完成。

## 6. 顶层 Agent 架构

### 6.1 职责

顶层 Agent 负责：

- 理解用户目标并持续维护项目级对话；
- 查询项目状态、作品资料和当前阻断；
- 选择并调用现有项目能力；
- 启动、暂停、恢复和纠偏创作任务；
- 解释 Agent、审查和内核结果；
- 对低风险、可逆操作自动行动；
- 在高风险操作前取得确认；
- 发现空转或失败后改变策略或交还用户。

顶层 Agent 不承担正式正文创作。正式正文继续由主创 Worker 生成，审查和文学判断继续由对应角色完成。顶层 Agent 是项目管理者、解释者和工具调度者。

### 6.2 目标调用链

```text
Agent Desktop UI
  -> Project Agent Session API + SSE
  -> ProjectAgentService
  -> AgentTurnCoordinator（一次有界对话回合）
  -> Pi Project-Agent Process
  <-> 双向 stdio 工具桥
  -> ProjectToolRegistry（本回合可见工具）
  -> ProjectActionExecutor（政策、幂等、并发、审计）
  -> Domain Tool Adapters
  -> Existing Application Services / Read Models
  -> Lean Literary Kernel / Worker / Archive / Style / Delivery
  -> Existing Jobs / Events / Receipts
  -> Creative Live + Agent UI + Orrery
```

工具边界采用 API 形状的类型化合同。内置 Agent 与后端处在同一应用时，Domain Tool Adapter 直接调用 Application Service 或 Read Model，避免绕 loopback HTTP 产生重复认证、序列化和错误翻译。外部 Agent 或未来远程客户端可以通过同一请求/响应模型调用 HTTP API。

当前 `PiWorkerRuntime` 把 prompt 一次写入 stdin 后关闭管道，`conversation.ts` 又是单回合、无工具执行器，因此不能直接承担上述调用链。顶层 Agent 需要一个独立的有界进程协议：

1. Python 启动项目 Agent 进程并发送本回合消息、精简上下文和工具 schema；
2. Pi Core 产生工具调用时输出带 `call_id` 的 `project.tool.request`；
3. Python 完成政策检查与业务执行，再通过 stdin 返回 `project.tool.result`；
4. Pi Core 在同一回合继续推理，直至回答、申请确认或达到运行保护边界；
5. 回合结束后进程退出，会话、消息、行动记录和长任务句柄由 Studio 持久化。

进程生命周期与会话生命周期必须分开。一个项目会话可以持续数周，但每次模型回合都使用可取消、可回收的有界进程，避免长期驻留的 Node 进程泄漏。需要人工确认时，不维持进程等待：持久化待确认调用并结束回合；用户确认后由 Studio 以相同 `call_id` 执行，再启动后续回合。

这条双向桥接协议必须先做最小技术原型。若无法稳定完成“模型调用工具 -> Python 返回结果 -> 模型继续回答 -> 进程正常退出”，D4 不得开始。

桥接协议还必须限制单帧大小、验证 schema、拒绝未知事件和重复 `call_id`，并对 stdout/stderr 做路径与凭证脱敏。Node 进程只接收会话上下文、工具 schema 和公开项目 ID，不取得项目目录的任意文件权限；provider credential 继续由现有只读 credential store 管理。

### 6.3 为什么不直接扩展 WorkspaceCommandBus

`WorkspaceCommandBus` 是浏览器内的导航与少量动作分发器：

- 工具面过窄；
- 页面刷新后不拥有执行真相；
- 无法安全承载长任务、审批恢复和正式写回；
- 不能供桌面后台 Agent 独立运行。

它继续负责 Agent 返回的 `open_view`、`focus_artifact`、`focus_scene` 等纯界面动作。项目动作由后端工具完成。

### 6.4 初始工具面

工具注册表可以容纳约 12–18 个项目级能力，但单个回合默认只暴露 6–10 个高区分度工具。工具名面向用户任务，不暴露底层 route、CLI 命令和文件路径。首批只读回合固定暴露三个工具，先验证工具选择和事实正确性。

| 阶段 | 工具域 | 工具 | 对应现有能力 |
| --- | --- | --- | --- |
| D4 | 项目 | `project_overview` | dashboard、progress、current project |
| D4 | 资料 | `project_search` | library、reader search、archive projection |
| D4 | 现场 | `creation_observe` | creative-live、Agent session、run snapshot |
| D5 | 项目 | `project_record_direction` | projects/directions |
| D5 | 创作 | `creation_continue` | task package、worker、autopilot |
| D5 | 创作 | `creation_control` | start/pause/resume/stop/retry |
| D5 | 决策 | `decision_list` / `decision_resolve` | current choice、human choice |
| D5 | 资料 | `asset_change_preview` / `asset_change_commit` | validate、impact、commit、promotion |
| D5 | 风格 | `style_manage` | source、build、advance、mount、version |
| D5 | 质量 | `quality_manage` | creative-quality、rhythm-plan |
| D6 | 交付 | `delivery_prepare` | readiness、export、download |

原方案中的 `asset_manage` 范围过大，读取、修改、影响分析、提交和晋升混在一个 schema 中，容易成为“万能工具”。修订后将高风险修改固定为 preview/commit 两阶段；`style_manage`、`quality_manage` 只允许保留不超过五个、语义互斥的 `operation`，超出后再按实际错误数据拆分。项目状态决定本回合暴露哪些工具，暂不引入额外模型做工具路由，也不预建动态插件系统。

### 6.5 权限与确认

| 风险层 | 行为 | 默认策略 |
| --- | --- | --- |
| R0 | 查询、搜索、观察、打开视图 | 自动执行 |
| R1 | 记录方向、生成预览、启动可暂停任务 | 协作模式提示；托管/全自动自动执行 |
| R2 | 编辑可恢复资产、选择分支、挂载文风、申请修订 | 协作模式确认；托管/全自动按策略执行并提供 receipt 与恢复说明 |
| R3 | 正式资产晋升、Canon 写回、正文晋升、交付构建 | 依据模式和现有 Gate；操作结果必须可审计 |
| R4 | 删除、覆盖用户锁定内容、发布到外部、修改密钥 | 始终要求用户明确确认 |

权限宽松体现在 Agent 能主动查询、计划和执行大量 R0–R2 行为。提示词负责角色与判断原则；确定性 policy 负责 R3–R4 边界。不能仅靠提示词保护不可逆操作。

每次写工具调用还必须满足以下程序合同：

- `call_id`：模型工具调用的稳定身份；重复请求返回同一结果，不重复写入；
- `idempotency_key`：由 Studio 根据会话、回合、工具和规范化参数生成，模型不能自行伪造；
- `concurrency_token`：使用领域已有的 `preview_digest`、`content_revision`、`choice_id`、`run revision` 或 `style preview_revision`，拒绝陈旧写入；
- `actor` 与 `mode`：记录用户、顶层 Agent、全自动策略及确认来源；
- `outcome`：返回 receipt、实际变更、受影响对象和恢复语义。

“可恢复”必须精确区分：`reversible` 表示存在确定性逆操作，`compensatable` 表示可以创建补偿变更，`final` 表示只能通过新版本继续。界面只有在真实逆操作存在时才显示“撤销”，不能把停止任务、再次修订或版本回退统称为撤销。

所有工具调用执行输入 guard、业务 policy、领域并发检查和输出裁剪。项目文本、作品正文、档案字段和搜索结果一律视为不可信资料，其中出现的命令、权限请求或工具调用说明不能改变 Agent 宪法。

### 6.6 会话与上下文

- 每部作品拥有多个项目 Agent 会话；一个会话可以持续数周。
- 当前项目摘要、用户固定偏好和最近对话复用现有 Advisor 的持久化能力；首选对现有表做向后兼容扩展，并由 D2 characterization test 验证，不能另建第二个数据库。
- 逻辑会话持久化，Pi 进程按回合创建和回收；首版不把 provider 原生 session 当作正确性依赖。
- 每轮只注入短项目摘要、当前焦点和可用工具说明。
- 作品事实通过工具按需读取，不把整个项目快照重复塞进提示词。
- 工具结果返回用户可读摘要、稳定 ID 和必要结构，不返回绝对路径或整份 JSON。
- 长任务由 run ID 和 SSE 继续观察，不让一次 Agent 回合同步等待整部作品完成。
- 对话消息和最终行动结果必须持久化；高频 token delta 只进入现有有界 LiveEventBus，重连后以持久消息、job event 和 Creative Live snapshot 恢复。
- 同一会话一次只执行一个模型回合；同一项目一次只允许一个正式写操作，查询可以并发。
- 顶层 Agent 不监听每个 Creative Live 事件并持续调用模型。普通进度由确定性投影更新；只有用户消息、待确认节点、可配置的异常接管或明确的自动决策节点才触发 Agent 回合。
- 不设置文学修订次数上限；使用无进展检测、用户停止和运行级资源保护防止空转。

首版上下文预算建议：持久角色与政策不超过 3,000 个中文字符，动态项目摘要不超过 2,000 字符，最近对话保留 6–10 条并配合不超过 6,000 字符的摘要，单个工具结果默认不超过 4,000 字符并支持分页。预算是观测告警和裁剪合同，不得用静默截断破坏事实。前端可以展示 Agent 的决策摘要、上下文清单、工具参数、结果和成本；完整私有思维链不作为产品合同，也不作为恢复依据。

首选持久化方案：

- 在现有 SQLite 中扩展 Advisor 会话的物理表和 repository，增加 `session_kind`，并允许 `user`、`assistant`、`tool` 三类 Project Agent 消息；旧 Advisor 对外语义保持不变；
- 每个用户回合复用 JobStore 记录 job 和 durable run events，`client_message_id` 形成回合幂等键；
- 写操作继续使用现有 mutation receipt，领域 preview token 负责陈旧状态检查；
- 待确认动作以 `call_id` 写入对话事件，确认或拒绝后追加对应 tool message，由投影折叠为当前状态；
- 同一会话的回合使用现有 lock/job 机制串行化，同一项目的正式写操作使用项目 lease；
- 只有 characterization test 证明现有表无法表达上述语义时，才允许增加一张最小 action 表；禁止建立第二个会话数据库或第二套通用 event store。

### 6.7 Prompt 分层

1. **持久角色层**：顶层 Agent 的职责、禁止代写正文、事实诚实性和交互方式。
2. **工具政策层**：工具含义、风险层、确认和失败处理。
3. **项目记忆层**：作品身份、用户偏好、对话摘要。
4. **当前状态层**：本轮焦点、正在执行的 run、待确认事项。
5. **工具观察层**：Agent 实际查询结果。

禁止重复注入完整 Skill、项目目录、全部 API 文档和历史任务证据。工具 schema 是调用合同，prompt 只解释选择原则。

### 6.8 单 Agent 优先

初期只实现一个面对用户的顶层 Agent，并把正式创作 Worker 当作工具背后的执行能力。暂不建立顶层 Agent、总编 Agent、任务 Agent、路由 Agent、审批 Agent 的多级网络。

只有出现以下可测问题才拆分：

- 工具选择错误率无法通过命名和 schema 改善；
- 项目规划上下文与普通对话长期冲突；
- 某一领域需要独立模型或独立数据权限；
- 并行专家确实降低时延或提高审查质量。

### 6.9 本轮架构预审

结论：**方向有条件通过，可以进入合同设计，暂不进入运行时代码实现。**

已经成立的条件：

- 现有 API 和 Application Service 覆盖了顶层 Agent 所需的大部分项目能力；
- Pi Worker 已提供 provider、model、streaming、usage、可靠性和进程级事件基础；
- Advisor 已证明项目级持久对话、人格、记忆和 SSE 前端链路可用；
- Creative Live 已能承载长任务状态和正式产物变化；
- Lean Kernel 继续拥有文学创作与正式写回，不需要移入顶层 Agent。

实现前必须解决的边界问题：

1. **Router 不能成为内部业务依赖。** `api/routers/` 中的 endpoint 只是 HTTP facade。Project Agent tool 应调用 router 已注入的 Application Service 或提取最小共享 service，不能在本地进程中发 HTTP 请求，也不能导入 route handler 复用实现。
2. **Advisor 不能原地取消只读限制。** 当前 `ProjectAdvisor.ask()` 在调用前后验证项目 hash，这是它的安全合同。新 Project Agent 复用会话、人格和流式组件，但需要独立 service；迁移完成后再决定保留 Advisor 为编辑顾问或删除旧 facade。
3. **正式 Worker loop 不能直接复用。** Pi Worker 的 task mode 以 expected outputs、tool lease、preflight 和 `complete_task` 为中心；顶层 Agent 需要多轮对话、项目工具、长任务句柄和 approval interruption。两者共享 provider/runtime adapter，不共享执行协议。
4. **Capability Broker 只能复用机制。** 当前 `CapabilityManifest` 绑定正式 task、route、读写路径和 agent role。项目级 Agent 应共享 capability registry、policy、audit 的思想与基础类型，不能伪造一个永久 task manifest 获取全项目权限。
5. **API 接管不能移除人工接管面。** Agent 是默认操作者，Reader、Archive、Style、Quality、Creative Live 和 Delivery 仍应作为可打开的检查与高级编辑工作区，避免模型故障时用户失去控制。
6. **提示词不能承担全部权限。** 顶层 Agent 可以拥有较宽的 R0–R2 权限；R3–R4 的确认、用户锁定、凭证和外部发布仍由确定性 policy 执行。
7. **长任务不能占住对话回合。** `creation_continue` 返回 run handle，Agent 回合可以结束；前端和后端通过现有 SSE 观察任务，并允许用户继续对话、排队或纠偏。

D2 必须用 characterization test 锁定这些边界。任一条无法满足时，D4 不得开始。

### 6.10 第二轮批判性设计审查

本轮审查继续对照当前源码，重点读取了 Advisor 会话持久化、Pi `conversation`、`PiWorkerRuntime`、Creative Live、JobStore、Archive/Style 路由和 Application Container。结论为：**产品方向保留，运行时方案需要完成四项结构修正后才能编码。**

#### 保留

- Agent 工作台与星仪共享一个项目事实源的双主界面；
- 复杂功能由 Agent 调用后端能力，Reader、现场、档案、文风成果和观测仍可直接查看；
- 复用内置 Pi Core、provider、credential、streaming 和 usage 能力；
- 顶层只设一个面对用户的项目 Agent，正式正文继续委托主创 Worker；
- R3–R4 由确定性 policy 和既有文学 Gate 管理；
- 长任务返回 handle，由既有 Autopilot、Worker 和 Creative Live 持续执行。

#### 修改

| 原设想 | 审查问题 | 修订决定 |
| --- | --- | --- |
| `ProjectToolFacade` 统一全部能力 | 容易演化为复制路由逻辑的巨型类 | 改为 Registry、Action Executor、Domain Adapter 三个职责；初始仍可放在少量文件中 |
| 一次暴露约 12 个工具 | 工具重叠和大 operation enum 会降低选择稳定性 | 注册表可更大，单回合暴露 6–10 个；D4 固定三个只读工具 |
| 复用 Advisor 存储 | 当前 repository 的角色与 API 都以 advisor 命名，直接扩展会污染语义 | 先做兼容性测试；优先复用 SQLite、消息、摘要和偏好能力，新增最小 session kind 与回合记录 |
| 复用 Creative Live SSE | LiveEventBus 有界且只在内存中，不能承担恢复依据 | 消息、tool call、approval 和结果持久化；SSE 只投影实时变化 |
| 每个写操作可撤销 | 现有操作的恢复能力不同 | 精确声明 reversible、compensatable 或 final，不承诺通用撤销 |
| Pi Project-Agent Loop | 当前 stdin 在 prompt 后关闭，无法回送 Python 工具结果 | 先实现双向 stdio 协议原型，保持每回合进程有界 |
| 持久 Agent 会话 | 当前 Pi conversation 以 prompt hash 建临时 session，每轮重建 | Studio 持有逻辑会话；Pi 原生 session 首版只作性能优化，不作正确性依赖 |
| Agent 与现有页面共享功能组件 | 直接把复杂页面组件嵌入对话会复制 store 生命周期和布局问题 | 对话只嵌轻量只读 presenter；复杂编辑器打开原有 route/工作区 |
| 复用 Advisor SSE | 当前 `/ask/stream` 使用请求内线程和 Queue，断线后无法按 cursor 恢复 | Project Agent SSE 从 durable job events 回放，再接现有 LiveEventBus；支持 `Last-Event-ID` |
| 复用 Advisor 动作元数据 | 当前回答尾部 marker + JSON 适合无工具顾问，项目 Agent 中会与原生工具调用重复 | 最终回答保持纯文本；行动、确认和结果使用独立结构化事件 |

#### 删除

- 删除“顶层 Agent 必须一直运行并观察所有项目事件”的隐含假设；
- 删除“只靠提示词即可安全扩大正式写权限”的路径；
- 删除“用一个万能工具覆盖整个档案/文风/质量模块”的倾向；
- 删除“人工确认时长期保留 Node 进程”的实现选择；
- 删除“新 Agent UI 上线时同时重写所有业务页面”的并行范围。

#### 延后

- 多 Agent 管理网络、subagent、Web 研究、Shell、任意文件访问和第三方 skill；
- provider 原生长会话与跨设备同步；
- Agent 工具插件市场和用户自定义工具；
- 自动生成新工作流和修改文学 Gate；
- 将所有旧页面重构为可嵌入 Agent 的微前端。

#### 新增的不可跳过门禁

1. **桥接原型门禁**：一个只读工具完成完整的 request/result/continue/exit 循环，并验证取消、超时和进程清理。
2. **幂等门禁**：相同 `call_id` 连续提交两次，只产生一次领域变更和一个稳定结果。
3. **陈旧写入门禁**：preview 后外部修改资产，commit 必须拒绝并返回新的领域 revision。
4. **恢复门禁**：服务在工具请求、等待确认和长任务启动后分别重启，UI 能从持久状态恢复。
5. **事件单源门禁**：同一工具行动在 Agent UI、Creative Live 和星仪中共享 identity，不生成三份相互冲突的状态。
6. **成本门禁**：项目无新用户消息、无待确认和无异常时，顶层 Agent 不产生后台模型请求。
7. **降级门禁**：关闭 Project Agent feature flag 后，现有 Reader、Archive、Style、Autopilot、Creative Live 和 Delivery 仍可独立使用。

#### 设计审查结论

D2 可以开始，范围仅限合同、持久化复用 characterization、工具桥 spike 和三只读工具的 scripted model 测试。D4 仍处于阻断状态。只有上述门禁的前四项在无真实业务写入的原型中通过，才允许进入只读产品实现。

## 7. 建议模块边界

### 7.1 后端新增边界

```text
src/literary_engineering_studio/project_agent/
  contracts.py        # 会话事件、工具请求、确认和结果 DTO
  prompt.py           # 精简持久 prompt 与动态状态装配
  policy.py           # 风险等级、模式和确认判定
  tools.py            # 初始 Registry、Action Executor 与领域适配器
  runtime.py          # 双向 Pi 工具桥、取消、超时和流式事件
  service.py          # 会话、回合、持久行动记录与应用编排
```

先保持六个内聚文件。`tools.py` 内以三个小类保持职责隔离；只有 handler 达到明显独立维护规模或三个领域以上发生并行修改后，才拆为 `tools/` 子目录。禁止先为每个 endpoint 建 adapter 类。

Pi Worker 只新增两个内聚模块：

```text
workers/pi-worker/src/
  project-agent.ts             # Pi Core 多轮工具循环，不含业务逻辑
  project-agent-protocol.ts    # stdin/stdout envelope、call/result 和错误合同
```

Python 使用独立的 `ProjectAgentRuntime`，不修改通用 `AgentRuntime.execute()` 的单向 stdin 合同，避免影响已经稳定的正式 Worker。Node 侧只持有工具 schema 和桥接 callback，不读取项目文件、不实现 Archive/Style/Workflow 业务。

复用：

- Advisor 的 persona、memory、session repository、可见 delta 过滤与前端消息呈现；
- Pi Worker 的 provider/model 连接和事件适配；
- 现有 Application Service、API request model、JobStore、Creative Live 与审计；
- 现有 Capability Broker 的 policy 思路和审计格式。

`api_server.py` 当前仍负责 Archive、Style、Quality、Workflow 等大量依赖装配，而 `ApplicationContainer` 尚未集中拥有全部业务服务。D2 先在 composition root 创建一个轻量 `ProjectAgentDependencies`，引用已经实例化的 service/read model。不得从 router 反向导入 handler，也不得在 Agent 进程内重新构造一套 Archive/Style 依赖。

不直接复用：

- Advisor 的只读 snapshot integrity contract；
- Advisor 的请求内 Queue SSE 和回答尾部 metadata marker 协议；
- 正式 Worker 的 expected-output sandbox 和 task tool lease；
- 任务级 CapabilityManifest 作为项目级长期权限清单。

### 7.2 前端新增边界

```text
client/src/features/project-agent/
  AgentWorkspaceView.vue
  components/
    AgentThreadRail.vue
    AgentConversation.vue
    AgentComposer.vue
    AgentContextInspector.vue
    AgentActionGroup.vue
    AgentArtifactPreview.vue
    AgentApprovalCard.vue
  composables/
    useProjectAgentSession.ts
    useAgentWorkspaceState.ts
  services/
    projectAgentClient.ts
  types.ts
```

共享而非复制：

- `SafeMarkdown`；
- Advisor 的消息滚动与流式合并逻辑；
- Creative Live 的 artifact presentation；
- Reader、Archive、Style、Quality 和 Delivery 的现有组件；
- workspace registry 和空间窗口系统；
- API transport、SSE、错误文案和项目 store。

生产迁移时，对话内只复用无副作用 presenter 和只读卡片。档案 IDE、文风工坊、Reader、Creative Live 与交付页通过现有 route 打开；避免把完整页面组件重新挂载到消息列表造成重复请求、重复 Pinia watcher 和滚动性能问题。

## 8. 分阶段实施

### D0：基线与调研

状态：本设计阶段完成。

产物：

- 当前组件、API、Advisor 和 Capability 边界清单；
- 一手产品与 Agent 架构资料；
- 不重写清单。

退出条件：能明确说明哪些能力复用、哪些边界需要新增。

### D1：视觉原型

状态：本设计阶段完成第一版。

产物：

- `docs/design/arcvellum-agent-desktop-reference.html`；
- 浅色 Notion-like 中性视觉；
- 左会话、中对话、右上下文和底部输入；
- 手稿脊线、工具组、正文产物、确认卡和模式切换示例。

审查问题：

- 对话是否始终是主角；
- 长正文是否有足够阅读宽度；
- 工具过程是否可见但不喧宾夺主；
- 用户能否在十秒内理解当前作品、当前任务和下一步；
- Agent 与星仪切换是否足够显眼。

本阶段不接 API，不进入生产 Vue。

#### D1 第一轮视觉审查记录

已在 1440×900 下实际渲染浅色与深色版本：

- HTML 页面无 console error 和 page error；
- 三栏实际宽度为 `244 / 892 / 304 px`，中央对话仍拥有可用正文宽度；
- 右侧上下文拥有独立滚动，不会增长整个页面；
- 普通对话保持无卡片，工具过程和正文产物才使用有边界容器；
- 明暗模式都保持中性灰阶，状态颜色没有主导页面；
- 手稿脊线能区分 ArcVellum 与普通 Agent 聊天产品。

生产迁移前需要修正：

1. 视口小于 1180 px 时自动收起右栏，小于 920 px 时再折叠左栏；不能缩小正文和控件来硬塞三栏。
2. 真实会话的工具记录和正文需要虚拟化或分段挂载；原型中的有限内容不能代表长会话性能。
3. 右栏只保留当前焦点和真正待确认事项，避免随着功能接入再次膨胀为仪表盘。
4. 所有符号按钮在 Vue 生产版替换为现有 `lucide-vue-next` 图标，并具备 tooltip、键盘焦点和 accessible name。
5. 需要补测 125%/150% Windows 缩放、超长中文标题、长错误文案、空项目和断线恢复状态。
6. Notion-like 中性色很容易失去品牌性；生产版必须保留手稿脊线、正文身份字体切换和真实创作阶段标记，不能再叠加装饰性色块弥补。

### D2：顶层 Agent 架构合同

状态：已完成。实现与验证证据见 `docs/architecture/arcvellum-project-agent-runtime-contract.md` 和 `docs/verification/project-agent-d2-d3-review-2026-09-13.md`。

工作：

- 定义 Project Agent session、event、tool、approval 和 result schema；
- 完成双向 stdio bridge spike，只接一个固定只读工具；
- 对 Advisor session、JobStore/run events 和 mutation receipt 做复用 characterization；
- 建立 `ProjectAgentDependencies` composition contract，把现有 Application Service 映射为首批工具；
- 定义三种委托模式和风险矩阵；
- 明确暂停、恢复、排队消息、立即纠偏和失败处理；
- 制作 prompt 字符预算与工具结果预算。

退出条件：合同可以用 scripted model 独立测试；bridge spike 可用一个真实 Pi provider 完成只读往返；不写正式项目。

### D3：架构审查门

状态：有条件通过。D4 必须先完成既有会话仓库的向后兼容扩展和基于 JobStore 的 durable event cursor；不得另建数据库或事件系统。

D2 完成后暂停实现，执行一次正式审查：

- 是否形成第二套状态机；
- 是否复制 Application Service 逻辑；
- 是否混淆 Advisor 与正式 Worker 的安全语义；
- 是否存在工具重叠和万能工具；
- 是否允许绕过既有文学 Gate；
- 是否能从持久消息、action event 和 receipt 恢复对话与长任务；
- 是否存在重复工具执行和陈旧 preview 写入；
- 是否错误地把有界 LiveEventBus 当作持久事实；
- 是否在等待确认时泄漏 Node 进程；
- 是否能在关闭顶层 Agent 时继续使用现有应用；
- 是否有量化的 token、时延和工具成功率基线。

只有审查通过才进入 D4。

### D4：只读顶层 Agent

状态：已完成。现已具备独立 Project Agent 会话、三项只读工具、既有顾问人格复用、每回合持久 Job/Event、异步执行、基于 durable cursor 的 SSE，以及生产 Vue Agent UI；写工具仍未开放。

工作：

- 建立 ProjectAgentService 和 session SSE；
- 接入 `project_overview`、`project_search`、`creation_observe`；
- 复用 Advisor persona/memory；
- 新 Agent UI 接入真实会话和工具活动。
- 每个 Agent 回合形成可持久恢复的 job/event 记录，实时 delta 只作为投影；
- SSE 以 durable event cursor 回放并通过 `Last-Event-ID` 重连，不复用 Advisor 的请求内 Queue；
- 验证同一会话并发发送时的排队、停止和顺序一致性。

退出条件：能自然回答项目问题、查询真实资料、持续会话，不修改项目。

#### D4 生产前端实施切片

本切片只完成只读 Project Agent 的真实产品入口，不提前实现 D5 写工具。代码按以下边界落地：

```text
client/src/features/project-agent/
  types.ts                              # 会话、消息、Job、流事件的前端合同
  services/projectAgentClient.ts        # 六个 Project Agent HTTP/SSE 接口
  composables/useProjectAgentSession.ts # 会话选择、发送、流合并、断线恢复
  components/                           # 会话栏、对话、活动组、输入与上下文栏
  AgentWorkspaceView.vue                # 只负责编排布局和现有工作区跳转
client/src/styles/projectAgent.css       # 独立的中性编辑桌面令牌和响应式布局
```

实施顺序与依赖方向：

1. `types.ts` 固定 API 数据形状，不修改当前仍有并行工作的全局 `types/api.ts`。
2. `projectAgentClient.ts` 复用 `featureTransport`；`POST turn` 只取得 durable job，随后读取 Job SSE，不复用 Advisor 的请求内流。
3. `useProjectAgentSession.ts` 负责最近会话、乐观用户消息、批量文本 delta、工具活动、终态重载与错误恢复；组件不得自行拼接协议事件。
4. `AgentWorkspaceView.vue` 只读取 `useAppStore` 的 dashboard、progress、reader 和 observability 投影；复杂展示通过现有 route 打开。
5. `router.ts` 与 `App.vue` 增加可逆的 `/agent` 顶层模式；星仪仍是平级入口，旧 Advisor 暂不删除。
6. 定向组件测试、TypeScript 检查与生产前端构建通过后，再进行真实 API 和桌面尺寸视觉验收。

首版明确不做：取消 API、写工具、审批恢复、第二个 Pinia store、会话全文搜索、项目树读取、旧工作区重写。若 D4 使用数据证明需要，再进入 D5 设计。

#### D4 实施结果

- `/agent` 已成为与星仪平级的全屏工作模式，旧阅读器、现场、档案、文风、质量和交付入口继续可达。
- 前端协议集中在 `features/project-agent/services` 与 `composables`；组件不解析底层事件，也不复制后端业务判断。
- 会话选择、乐观用户消息、64 ms 文本批处理、工具活动分组、durable SSE 游标恢复和终态重载已经接通。
- 真实 Project Agent 回合成功调用 `project_overview` 与 `creation_observe`，回答准确定位当前场景、阻断原因和后续建议。
- 浅色桌面尺寸下完成视觉验收：三栏均独立滚动，工具活动可折叠，输入区在长回答后保持可达，没有面板遮挡。
- 本阶段未增加写权限、审批系统、第二状态机、第二事件流或额外 Agent 框架。

详细证据见 `docs/verification/project-agent-d4-product-checkpoint-2026-09-14.md`。

### D5：受控项目操作

工作：

- 接入记录方向、启动/暂停/恢复、预览、节奏配置和文风管理；
- 建立 approval interruption 与恢复；
- 每个写操作返回 receipt、领域 concurrency token 和真实恢复语义；
- 对话内展示真实工具结果。

退出条件：协作、托管和全自动三种模式的审批差异可验证。

### D6：复杂功能接管

工作：

- 接入档案编辑/晋升、决策、质量、交付；
- Agent 能根据用户自然语言组合多个工具；
- 复杂操作从主导航收敛到 Agent 工具；原有展示工作区继续保留稳定直达入口，页面内的高级编辑作为手动接管；
- Creative Live、Reader 和 Orrery 与当前 Agent run 同步。

退出条件：普通用户可以只通过 Agent 完成从作品方向到连续推进和交付的主要流程。

### D7：双主界面与视觉迁移

工作：

- Agent 成为默认项目页；
- 星仪成为顶层平级模式；
- 替换旧 Moss/Brass 主配色为中性笔记配色；
- 保留星仪自身深色空间背景，但统一窗口和文字令牌；
- 建立浅色、深色、系统和高对比度模式。

退出条件：双界面共享选择、会话、run 和待确认状态。

### D8：收敛与删除

工作：

- 真实用户路径 E2E；
- 桌面端长会话、SSE 重连、休眠恢复和更新验证；
- 比较改造前后请求数、token、首响应时间和完成率；
- 删除被替代的 Advisor UI 外壳、重复动作卡和不再使用的样式；
- 建立展示入口保护清单，Reader、Creative Live、Archive browser、Style results、Observatory、Orrery 和 Delivery status 不得因默认路径简化被删除；
- 保留必要兼容期后再删除旧 facade。

退出条件：功能没有削减，默认路径显著简化，代码和运行复杂度没有上升失控。

## 9. 反过度工程约束

每一批都必须回答“为什么现有模块不能承担这项职责”。没有证据时禁止新增抽象。

硬约束：

1. Vue 3、Pinia、Tauri、FastAPI、Pi Worker 和 SSE 保持不变。
2. 不引入新的通用 Agent 框架。
3. 不新增第二个事件总线、任务仓库或审批数据库。
4. 不把全部 API endpoint 一比一包装为工具。
5. 不建立多 Agent，直到单 Agent 的实际评测证明需要。
6. 不以“未来可扩展”为由预建插件系统。
7. 不让顶层 Agent 读取完整项目树或任意文件。
8. 不在前端重写后端业务判断。
9. 不一次删除旧顾问；先以 feature flag 灰度，再在稳定后收敛。
10. 每批独立提交、独立回滚，只跑与改动面匹配的测试；阶段出口再跑完整 E2E。
11. 顶层 Agent 不因 Creative Live heartbeat、普通进度 delta 或 UI 打开而自动调用模型。
12. 同一项目同时只允许一个正式 mutation action；只读查询可以并发，长任务继续使用现有 lease。
13. 不修改 `AgentRuntime.execute()` 来兼容双向协议；使用独立 runtime，保护正式 Worker 稳定性。
14. 项目内容和工具结果始终按不可信资料处理，任何嵌入指令不得扩大能力。

复杂度预算：

- 工具注册表首期不超过 18 个，单回合可见工具不超过 10 个；
- 顶层 Agent 新后端模块不超过一个 feature package；
- 不新增项目文件格式；
- 不增加正式文学 Gate；
- 不增加正文生成模型调用；
- 无用户消息、异常或确认需求时，不增加后台顶层 Agent 模型调用；
- 项目状态查询优先复用 read model cache；
- 每轮 prompt 只包含当前状态和必要工具，不重复项目快照。

## 10. 评测方案

### 10.1 视觉

- 1280×720、1440×900、1920×1080 和窄窗口截图。
- 浅色、深色、高对比度和 reduced motion。
- 2,000 字正文内嵌、20 条工具活动、30 个会话和长错误信息。
- 工具展开、右栏折叠、侧栏折叠和输入区不遮挡正文。
- 用户第一次打开后十秒内能指出当前作品、Agent 状态和主要输入位置。

### 10.2 Agent

- 20 个项目问答任务的事实与引用准确率不低于 95%，且不能声称执行未发生的动作。
- 20 个自然语言项目操作的首选工具准确率不低于 95%；剩余案例必须能通过澄清或安全拒绝收敛。
- R3/R4 操作确认召回率必须为 100%。
- 工具失败后能解释、重试或改变路径，不能重复空转。
- 同一工具 `call_id` 重放不会重复写入，陈旧 preview 无法提交。
- 项目文本内的伪指令不能触发额外工具或改变风险层。
- 长任务中排队消息和立即纠偏都能进入同一会话。
- Agent 不生成正式正文，不绕过 Worker、Review、Promotion 或 Delivery Gate。
- 应用重启后，已完成消息、待确认 action、长任务 handle 和最终 receipt 可恢复。

### 10.3 效率

- 普通用户完成“继续创作”所需显式操作数下降。
- 顶层 Agent 不增加正文 Worker 的 prompt 体积。
- 查询类工具优先命中现有 read model，不扫描整个项目。
- 会话恢复不重复发送完整历史。
- 空闲项目的顶层 Agent 模型请求数保持为零。
- 每回合结束、取消、超时或待确认后，Project Agent 子进程数量回到零。
- D4 的常规问答输入上下文中位数不超过 12k token，P95 不超过 20k token；超过时必须给出可解释的 context receipt。
- Agent UI 渲染不因 Creative Live delta 每 token 全量重排。

## 11. 第一实施批建议

在进入生产代码前，下一批只做两件事：

1. 对本 HTML 原型进行视觉审查，确定布局、配色、信息密度和工作区打开方式。
2. 编写 Project Agent 合同与工具映射 ADR，并完成双向 stdio bridge spike、持久化复用 characterization 和 D3 架构审查。

这两个结果稳定后再接真实 API。视觉与架构并行探索，但实现顺序保持“架构合同 → 审查 → 只读工具 → 可逆操作 → 高风险能力”。

## 12. 最终评审结论

### 12.1 值得实施的部分

顶层 Agent 能直接解决当前产品最明显的认知成本：用户无需理解 Autopilot、任务包、候选、审查、晋升、文风版本和交付预检之间的内部关系。ArcVellum 已有可复用的文学内核、项目 API、Pi provider、会话、SSE、审计和展示工作区，新增工作集中在“对话编排与受控工具桥”，无需重写创作系统。

### 12.2 成本最高的部分

成本中心是双向 Pi 工具桥、跨进程取消、幂等 action、审批后的继续以及现有 Application Service 装配，不是聊天界面。若跳过这些部分，只给 Advisor 增加几个动作卡，会很快得到一个看似全能、实际无法稳定管理项目的 Agent。

相对工作量：

| 阶段 | 工作量 | 主要不确定性 |
| --- | --- | --- |
| D2–D3 | 中高 | 双向桥、持久化复用、业务 service 装配 |
| D4 | 中 | 工具选择准确率、SSE 重连、长会话成本 |
| D5 | 高 | 幂等写入、审批、并发和恢复语义 |
| D6 | 高 | 档案、文风、质量和交付领域差异 |
| D7 | 高 | 现有前端迁移、长列表性能、星仪状态同步 |
| D8 | 中高 | 桌面恢复、兼容删除、完整用户路径验证 |

### 12.3 推荐交付切面

第一个可用版本停在 D4：Agent 能回答项目问题、定位阻断、查看正文和现场、打开正确工作区。第二个版本只增加创作启停、记录方向和决策确认。档案编辑、文风工程和正式交付放到后续，不把全部能力压进首发。

### 12.4 停止条件

出现以下任一情况，应停止扩权并保留现有 Advisor + 动作卡路线：

- bridge spike 无法在取消、超时和异常帧下稳定回收进程；
- D4 的自然语言工具选择准确率低于既定验收线，且通过命名、schema 和少量示例无法改善；
- 顶层 Agent 每次查询都需要重新扫描项目或显著增加正文 Worker 上下文；
- 为接入一个工具必须复制 router 业务或建立第二套正式状态；
- Agent UI 使 Reader、Creative Live 或星仪的实际使用体验退化。

综合判断：**方案可以实施，且产品收益明确；应从“有界 Pi 回合 + 小工具集 + 既有业务服务”开始。一次性重写前端、扩大所有权限或把顶层 Agent 做成常驻监督者，都会把刚削减的工程复杂度重新引回来。**
