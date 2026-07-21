# ArcVellum v0.8 Agent Runtime 与沉浸式叙事星仪执行计划

状态：实现完成，等待最终桌面打包与安装验收
版本目标：0.8.0
交付边界：源码、测试、签名 Windows 安装包、干净安装验证、GitHub 主分支

## 1. 本轮目标

本轮不改写 Literary Engineering 内核，也不引入第二套工作流编排器。ArcVellum 继续以现有 CLI 状态机和 route gate 为唯一正式事实源，重点解决两个真实使用问题：

1. Agent 执行速度慢、反馈稀疏、失败发现过晚，导致自动创作难以持续推进。
2. 叙事星仪虽然已经具备真实数据和动态投影能力，但还没有成为可长期停留的核心视觉场景。

同时完成顾问 Markdown、安全渲染、角色模型配置、读模型增量推送和桌面交付验证。

## 2. 已确认事实

本计划基于代码和真实运行记录，而不是产品设想：

- `OpenCodeRuntime`、`ProjectAdvisor`、`CreativeSteward` 每次调用都会新建 OpenCode 服务、配置目录和会话，调用结束立即销毁。
- OpenCode HTTP 客户端已经支持按 `directory` 访问不同工作区，服务本身可以承载多个会话，因此具备复用基础。
- 一次正式任务耗时约 7 分 43 秒，其中单次文件写入工具参数生成约耗时 3 分 51 秒；确定性 CLI 步骤通常只需 0 到 1 秒。
- 该任务最后因为 `## 结论： pass` 与机器要求的 `- 结论： pass` 不一致而整轮回滚，说明正式写回前缺少可修复预检。
- Studio 包装合同禁止 Agent 执行 `task-submit/task-complete`，核心 task Markdown 又要求执行它们，内部 Worker 任务存在语义冲突。
- Worker 事件逐条写 SQLite，SSE 再轮询 SQLite；工具 pending/running 状态还会重复产生 `tool.started`。
- Autopilot 后端保留了 Worker 事件，前端却只消费 `autopilot.status`，并且当前任务 ID 在任务结束后才写入。
- Dashboard、Library、Reader 和 Narrative 各自定时重建完整读模型；部分流在内容未变化时仍重复传送完整载荷。
- 顾问回答在前端以纯文本插值显示，Markdown 标记不会转成阅读友好的结构。
- 现有叙事星仪已经从项目真实数据构建节点、边和动作事件，可以被同一组件复用于工作台与沉浸模式。

## 3. 架构原则

### 3.1 唯一控制面

正式创作仍遵循：

`task-next -> task-open -> sandbox -> Agent -> preflight -> writeback -> task-submit -> task-complete -> route-audit`

Runtime 只能执行当前 task package。它不能自行选择路线，不能直接写正式项目，也不能绕过 review、promotion 或 release gate。

### 3.2 三种数据寿命

- 正式事实：CLI 产物、route gate、writeback、review、promotion，必须持久化。
- 运行里程碑：任务阶段、工具开始/结束、验证结果、重试、耗时和用量，持久化到 JobStore。
- 高频瞬时信息：文字 delta、重复状态和高频心跳，通过内存事件总线流式传送，不逐条写 SQLite。

### 3.3 三类 Agent 角色隔离

- `worker`：隔离沙箱内可读写 expected outputs。
- `advisor`：只读快照，可维持对话会话。
- `steward`：只读快照，只能在声明的候选项中作出有审计证据的决定。

不同角色使用独立 OpenCode profile 和服务实例，防止权限或上下文串线。

### 3.4 视觉焦点

产品的记忆点只有一个：叙事星仪。工作台模式保留当前信息布局；沉浸模式让星仪占据主要视野，任务、人工决定、正文进度和顾问作为可收起的边缘仪表存在。背景图只承担低对比材质，不画 UI、文字、节点或虚假数据。

深色仪表层级参考 Carbon 的“暗色层级随前景逐级变亮”、Apple Dark Mode 的 base/elevated 背景和全屏 HUD 面板原则；具体颜色仍使用 ArcVellum 的矿物夜色、玉色、黄铜与朱砂语义体系，而不照搬通用组件外观。参考：<https://carbondesignsystem.com/elements/color/overview/>、<https://developer.apple.com/design/human-interface-guidelines/dark-mode>、<https://developer.apple.com/design/human-interface-guidelines/panels>。

## 4. 实施阶段

### Phase A：持久 OpenCode Runtime

1. 新增应用级 Runtime Pool，由 `ApplicationLifecycleManager` 持有和关闭。
2. 为 worker、advisor、steward 建立稳定 profile 目录和独立长驻服务。
3. 服务首次需要时懒启动；后续调用复用进程和 provider 授权，每个正式任务建立新 session。
4. 顾问 Studio session 绑定远程 OpenCode session，快照变化时更新工作目录或安全重建会话。
5. 增加健康检查、并发保护、空闲回收、崩溃重启和指数退避。
6. 应用退出时停止全部服务，不遗留终端窗口或后台进程。
7. 配置增加 worker/advisor/steward 三个模型槽；未单独设置时回退到默认模型。

验收：同一应用生命周期内连续两次调用同一角色只启动一次 OpenCode 服务；角色之间不共享 profile；应用关闭后进程消失。

### Phase B：任务编译、预检与同会话修复

1. 内部 Worker 不再原样拼接平台宿主操作说明，生成专用的 Studio task program。
2. 移除 task Markdown 中要求 Agent 运行 `task-submit/task-complete` 的冲突段落，但保留创作约束、required reading、output contract 和 validation gates。
3. 生成紧凑 `TASK_CONTEXT.json`，明确允许读取、允许写入、精确输出格式和机器行示例。
4. Runtime 初次输出后，在沙箱内执行预检：越界修改、缺失产物、JSON/YAML 可解析性、completion evidence、任务专属机器行和最低结构。
5. 预检失败时，把精确错误作为修复指令发送给同一个 session，最多两轮；修复期间不重启服务、不重建上下文。
6. 预检通过后才生成 writeback preview；正式 core gate 仍是最终裁决。
7. run manifest 记录 session、attempt、repair errors、preflight result 和安全恢复点。

验收：故意把 `- 结论： pass` 写成标题时，系统在正式写回前检出并在同一 session 修复；不再因可修复格式问题回滚整轮。

### Phase C：事件、遥测与恢复

1. 记录 task select/open、sandbox、runtime ready、session create、first event、first text、first tool、Agent 完成、preflight、repair、writeback、core gate、audit 等 span。
2. 计算启动等待、TTFT、模型执行、验证、写回和总耗时；记录 provider/model、token usage、cache、cost 和 retry。
3. 按 tool call ID 去重状态，只让 pending/running 的首次转换产生 `tool.started`。
4. 新增应用级内存事件总线；高频 delta 以 50 到 100 ms 合并推送，里程碑继续持久化。
5. Worker SSE 先读持久事件，再等待内存通知；断线时用 event id 从持久事件恢复。
6. 重启后把未完成 Job 标记为可恢复，并从任务或预检边界重试，不把半成品直接写回正式项目。
7. Runner probe 增加真实 TTFT 和短回答总耗时结果。

验收：前端可看见真实阶段和持续心跳；数据库事件量不再随每个文本 token 线性增长；重连不会丢失正式里程碑。

### Phase D：Autopilot 与读模型反馈

1. Autopilot 在收到 `task.opened` 时立即记录当前 task ID、route、state 和开始时间。
2. 前端消费 Worker 事件，显示当前阶段、已经用时、最近活动、验证/修复次数和是否等待人工，不伪造百分比。
3. Dashboard、Library、Reader、Narrative 使用内容摘要抑制重复载荷；未变化时只发 heartbeat。
4. 对昂贵读模型增加短期缓存和项目修订键，同一轮多个订阅复用计算结果。
5. 保留断线降级和重新同步能力。

验收：长任务期间界面至少持续展示真实心跳和阶段变化；内容未改变时不反复传送相同完整 JSON。

### Phase E：顾问 Markdown 与会话体验

1. 使用 `markdown-it` 解析 Markdown，关闭原始 HTML。
2. 使用 DOMPurify 做第二层清洗，禁止脚本、事件属性、远程图片和危险 URL。
3. 允许标题、列表、引用、行内/块级代码、表格和安全链接，并为悬浮顾问面板设计紧凑排版。
4. 流式文本以短暂节流重新渲染，兼容未闭合代码围栏，结束后执行最终渲染。
5. 顾问远程会话复用；保留 Studio 已有摘要、固定偏好和人格合同。

验收：常见 Markdown 正确显示；XSS 和危险链接测试通过；流式回答无明显闪烁，元数据标记不泄露。

### Phase F：双模式叙事星仪

1. `workbench`：保留现有总览和下面的创作模块。
2. `immersive`：星仪成为全视口主体；四侧仪表打开后仍必须保留连续、可辨认的中央故事脉络区。
3. 左侧承载作品与档案，右侧承载推进、决策、规则与节奏、健康、交付，顶部承载设置与帮助，底部承载正文；作品生命体征移到时间轴上方，避开标题和场景选择。
4. 顾问保持悬浮，不占据星仪固定布局。
5. 模式和背景偏好存入本机 UI preference；小屏自动回退工作台。
6. 五套完整主题分别使用独立低对比生成式背景：苔夜星仪、靛紫航图、黑曜黄铜、米白书柜、冷峻现代。每套采用主材质、互补功能色与半透明层，不用单色铺满；仍允许手动改选纯色、夜航档案和活墨宇宙等材质。
7. 动效只由真实 motion event 驱动；遵守 reduced-motion，不用随机动画伪装进度。
8. 沉浸模式保留自动推进、人工决策、规则与叙事节奏、正式正文、作品档案、交付和路线健康度，以边缘控制坞和原生仪表承载，不做功能缩水版。
9. 顾问作为受控自然语言项目控制台，把明确用户意图转换为白名单动作卡；文件写入、全自动授权、发布与 Canon 正式写回仍由专门门禁保护。
10. 仪表使用与星图同源的矿物/木质/玻璃层级，可多开、折叠、拖动、置顶、自动约束在视口内并一键复位；默认四区网格不允许按钮或窗口互相遮挡，普通页面不得以原尺寸直接嵌入仪表。
11. “足够华丽、吸睛、沉浸且有趣味”作为正式视觉验收，而不是装饰数量指标：叙事星仪必须是唯一主视觉，开窗、切页、任务推进和 Canon 写回的动效必须对应真实状态，正文与长时间操作区域仍需安静清晰。

验收：桌面两种模式可即时切换且共用同一投影数据；主题背景不影响文字和节点识别；推进、决策、规则、节奏、正文、健康、档案和交付在全景内完整可用；仪表可多开、折叠、拖动与复位；1024x768、1366x768、1600x900 和窄屏无默认重叠。至少进行静态构图、交互动效、安装版截图三轮视觉回看，并按“华丽、美观、沉浸、趣味、清晰、稳定”六项逐一验收。

## 5. 测试矩阵

- Python：Runtime Pool、角色隔离、健康恢复、任务编译、预检、修复、事件去重、摘要缓存、Autopilot 阶段传播。
- Vue：Markdown XSS、安全链接、流式片段、模式偏好、沉浸面板、面板拖动/复位、无目录阅读器全宽布局、Autopilot 阶段呈现。
- 契约：Prompt Registry、CLI task package、writeback 和 route gate 回归。
- 性能：冷启动与暖启动对比，两个连续任务的服务启动次数，未变化读模型的传输次数。
- 桌面：Vue build、Cargo check、PyInstaller sidecar、Tauri NSIS、签名与校验和。
- 安装：静默覆盖安装到 `D:\ArcVellum`，验证无终端窗口、前端可连后端、项目可打开、顾问入口可用、两种星图模式可见。
- 视觉：安装版截图检查主视觉、边缘面板、文本适配、图标尺寸、滚动区域和 reduced-motion。

## 6. 不做事项

- 不引入 LangGraph、Dify 或另一套正式状态机。
- 不让 Runtime 直接写正式项目根目录。
- 不在前端展示模型隐藏推理过程。
- 不把高频 token delta 全部写入数据库。
- 不让顾问拥有文件写权限。
- 不用背景图替代真实 SVG 星仪，不把生成图片中的虚假节点当项目数据。

## 7. 最终完成定义

只有以下证据同时成立，v0.8 才能交付：

1. 本计划所有 Phase 的代码和针对性测试存在且通过。
2. 全量 Python/Vue 测试、类型检查、Vite build、Cargo check 和 Prompt Registry 校验通过。
3. 连续 Agent 调用证明服务复用，任务格式故障证明同会话修复有效。
4. 安装版在真实桌面进程中启动，前后端连接正常，没有弹出的终端窗口。
5. 工作台与沉浸星图均经过安装版截图验收。
6. 安装包、签名、`latest.json` 和校验和均为最终源码重新生成。
7. 所有源码、文档和发布元数据提交并推送 GitHub 主分支。
