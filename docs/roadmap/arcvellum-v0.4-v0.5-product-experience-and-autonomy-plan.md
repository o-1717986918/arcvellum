# ArcVellum v0.4-v0.5 产品体验与自主创作计划

## 1. 文档状态

- 当前基线：`ArcVellum v0.5.0`
- 英文产品名：`ArcVellum`
- 产品副标题：`Longform Narrative Studio`
- 计划状态：已于 2026-07-21 完成实现与本机发布候选验证
- 计划范围：`v0.4.0` 产品体验重构、`v0.5.0` 顾问与自主创作闭环
- 主要平台：Windows 10/11 桌面客户端
- 架构前提：Tauri 2 桌面壳、FastAPI 本地服务、内嵌文学工程内核、捆绑 OpenCode Agent Runner

`ArcVellum` 是工作名称，不是已完成商标审查的正式品牌。正式发布前必须检查商标、域名、GitHub 仓库名和近似写作产品。品牌升级时应保留现有 Tauri `identifier` 和应用数据迁移身份，避免用户升级后丢失配置、项目登记和任务记录。

## 2. 背景与问题定义

`v0.3.0` 已经完成以下工程底座：

- 内嵌文学工程 CLI 和七条正式路线；
- 任务包、沙箱、预期产物限制、差异预览、正式写回和失败回滚；
- SQLite WAL 持久任务、事件、租约、路由锁、恢复和 SSE；
- 捆绑 OpenCode、模型连接、受限 Worker 和只读顾问；
- 项目管理、总控面板、作品档案、正文阅读、交付中心；
- Tauri Windows 客户端、冻结 Python sidecar 和 NSIS 安装包。

当前版本的主要问题已经从“功能不存在”转为“产品入口、信息架构和连续执行没有收敛”：

1. 项目目录选择依赖 `window.__TAURI__.dialog` 全局对象，桌面桥接检测失败时按钮直接隐藏，只剩手动输入路径。
2. 启动阶段只加载健康状态、运行器和项目；模型 Provider 目录只有打开“连接与模型”页面才加载。
3. 普通界面暴露了 Runtime、Task Package、Route、Canon、Writeback、Schema、JSON、路径和内部状态等开发概念。
4. 缺少完整的“关于应用”、版本信息、更新、发行说明、数据位置、诊断导出和恢复入口。
5. Rust 主程序等待本地服务就绪后才创建窗口，用户启动期间看不到状态。
6. 顾问被严格 JSON 输出和“事实/推断/不确定项”分区束缚，回答正确但不像自然对话。
7. 当前前端是单体 HTML、CSS 和约 2400 行 JavaScript，继续增加悬浮顾问、更新中心和自动模式会快速降低可维护性。
8. Prompt Registry 中的约束元数据没有完整传入最终 Agent Prompt；当前高风险 Prompt 评测也没有真实模型语义基准。
9. Studio Worker 每次只推进一个任务，没有跨任务、跨路线的长期调度器。
10. `waiting_human`、分支选择、风格挂载、Canon 审批和发布审批没有统一的代理决策协议。

## 3. 产品目标

下一阶段要把 Studio 从“开发者能够操作的文学工程控制台”升级为“普通创作者能够长期使用的桌面产品”。

目标用户在不接触 CLI、JSON 和项目文件结构的情况下，应能完成：

1. 安装并启动应用；
2. 通过系统文件夹窗口创建或打开作品；
3. 在启动阶段自动恢复模型、项目和任务状态；
4. 用自然语言提供创作方向；
5. 观察创作、推演、审查和状态维护进度；
6. 在需要时选择分支、风格、修订、扩纲和设定写回；
7. 与随时可用的悬浮顾问自由讨论作品；
8. 在授权后让顶层代理持续推进项目；
9. 阅读完整正文并导出干净的正式作品；
10. 在应用内查看版本、更新、诊断和数据位置。

## 4. 非目标与约束

本阶段不做以下工作：

- 不把文学工程内核重新改成直接 HTTP 调用模型；
- 不让 OpenCode 或顾问直接写正式项目；
- 不把用户项目迁移到云端；
- 不建设账户、计费、团队协作和在线同步；
- 不用隐藏项目结构作为安全边界；
- 不为了动态效果牺牲正文阅读、可访问性和长时间使用体验；
- 不在 `v0.4.0` 一次完成未经验证的整书全自动发布；
- 不改变现有项目格式和正式 CLI 门禁语义，除非提供兼容迁移。

## 5. 设计原则

### 5.1 内核仍是唯一流程权威

- CLI 内核签发任务、输出契约和门禁。
- Agent Runner 只执行一个受限任务。
- Studio 负责调度、沙箱、事件、写回、决策和用户体验。
- 顾问和顶层代理都不能直接编辑正式项目。

### 5.2 普通用户界面不等于隐藏证据

- 项目事实、人物、世界观、场景、分支和审查结果必须完整展示。
- Schema、哈希、CLI、内部路径和原始 JSON 进入“高级诊断”。
- 原始证据可展开查看，但不能成为普通页面的主要语言。

### 5.3 启动完成是“状态已确定”

模型离线或更新服务不可达不能让启动动画无限等待。必须区分：

- 阻塞项：桌面会话、本地服务、数据库迁移、内核加载、项目登记恢复；
- 可降级项：模型 Provider 目录、外部网络探测、更新检查；
- 后台项：完整模型目录刷新、版本公告、非关键缩略图或索引重建。

### 5.4 顾问建议和正式执行分离

顾问可以提出操作，但只能提交白名单动作建议。正式 API、AutopilotController 或用户确认负责执行。

### 5.5 渐进迁移，不做前后端同时大爆炸

Vue 首先替代界面组织和状态管理，FastAPI 静态服务、本地认证、Tauri 动态本地 URL 和后端 API 在 `v0.4.0` 保持稳定。

## 6. 目标架构

```text
ArcVellum Desktop
  -> Tauri Shell
     -> Startup Scene
     -> Native Dialog
     -> Signed Updater
     -> Window and process lifecycle
  -> Vue Client
     -> Application Bootstrap Store
     -> Project Store
     -> Connection Store
     -> Workflow Store
     -> Advisor Store
     -> Autopilot Store
     -> Update Store
  -> FastAPI Application Service
     -> Bootstrap Service
     -> Project Service
     -> Connection Service
     -> Advisor Service
     -> Autopilot Controller
     -> Worker Supervisor
     -> Update/Diagnostic Projection
  -> Embedded Literary Engine
     -> Task Registry and Prompt Registry
     -> CLI workflow state machine
     -> deterministic gates and release policy
  -> Agent Runtime
     -> bundled OpenCode Worker
     -> read-only Advisor
     -> Creative Steward
```

## 7. 版本与里程碑

### 7.1 `v0.4.0`：产品体验基线

必须完成：

- Prompt 传输与显式任务契约修复；
- Vue 3、TypeScript、Vite 客户端壳；
- 原生目录选择；
- 启动聚合与模型自动加载；
- 用户术语和高级诊断分层；
- 创意启动场景；
- 应用信息、版本、更新和诊断中心；
- 现有页面的 Vue 迁移与回归验证。

### 7.2 `v0.4.1`：顾问体验

必须完成：

- 自然对话返回协议；
- 流式顾问输出；
- 会话摘要和偏好记忆；
- 全局悬浮顾问；
- 白名单动作建议；
- “加入创作方向”和“建议下一步”操作。

### 7.3 `v0.5.0`：自主创作 Beta

必须完成：

- AutopilotController；
- Creative Steward；
- DelegationPolicy；
- 通用门禁解析和恢复；
- 跨任务与跨路线调度；
- 费用、时间、任务数和修订上限；
- 循环中止与恢复；
- 全书 Release Manifest；
- 从最小创意到正式交付的端到端样例。

### 7.4 `v1.0.0`：稳定产品

进入条件：

- 完整场景路线真实运行稳定；
- 至少一个多章样例自动推进并通过最终导出；
- 更新安装和回滚通过干净虚拟机验证；
- 长时运行、异常恢复和费用限制通过测试；
- 用户无需修改项目文件或输入 CLI 命令。

### 7.5 实施结果与证据

`v0.4.0`、`v0.4.1` 与 `v0.5.0` 的计划项已经进入正式代码、客户端和发布链路：

- Prompt Asset 元数据与显式任务契约完整传入 Agent Runner；Prompt Registry 校验为 25 个资产、61 个任务映射，零警告。
- Vue 3、TypeScript、Vite、Pinia 与 Router 客户端已经替换旧单文件前端；旧 `/legacy` 入口与静态脚本已移除。
- 原生目录选择、真实 Bootstrap 状态、模型后台恢复、应用信息、诊断导出和签名更新均已接入。
- 悬浮顾问使用只读快照、自然正文加隐藏元数据协议、持久摘要与白名单动作；真实 OpenCode 模型调用和流式回传已验证。
- AutopilotController、CreativeSteward、DelegationPolicy、恢复、限制、代理决定审计和全书交付均已实现。
- 确定性端到端测试覆盖“用户方向 -> 七条路线 -> 三章正式正文 -> Markdown/DOCX -> Release Manifest”；真实模型另以历史、悬疑、现实、幻想四类生成、审查、修订评测验证 Prompt 语义效果。
- 84 个 Python 测试、9 个 Vue 测试、Vue 生产构建、Rust `cargo check`、冻结 sidecar 启动烟测全部通过。
- 390x844、1024x768、1440x900、1920x1080 均完成实际浏览器布局检查，没有页面横向溢出；README 使用本轮实机截图。
- 已生成签名 `ArcVellum_0.5.0_x64-setup.exe`、`.sig`、`latest.json` 与 SHA256 清单。

完整证据见 `docs/releases/v0.5.0-verification.md`。干净 Windows 10/11 虚拟机上的首次安装、覆盖升级、卸载和故障回滚仍属于本文件定义的 `v1.0.0` 进入条件，不伪装成本机已完成验证。

## 8. Workstream A：Prompt 与任务契约硬化

### 8.1 当前缺口

`task_registry._prompt_asset_lines()` 当前主要注入 Prompt Asset 身份、`output_contract` 和正文，没有完整下发 Prompt Asset 元数据。Studio 的 `TaskPackage.execution_contract` 仍可能通过兼容规则推断执行策略和门禁。

### 8.2 改动

修改内核任务包生成：

- 注入 `required_inputs`；
- 注入 `context_groups`；
- 注入 `hard_constraints`；
- 注入 `style_constraints`；
- 注入 `review_requirements`；
- 注入 `forbidden_shortcuts`；
- 保留 `output_contract` 和 Prompt Body；
- 在 JSON 任务包中提供相同的结构化字段；
- 给每个字段记录 Prompt Asset ID、版本和摘要。

新增显式任务字段：

```json
{
  "execution_policy": "agent-required",
  "agent_role": "prose-writer",
  "human_gate": [],
  "runtime_capabilities_required": ["read", "edit_expected_outputs"],
  "output_contracts": [],
  "writeback_policy": "preview-required"
}
```

### 8.3 兼容策略

- 旧任务包继续通过兼容适配器读取；
- 新签发任务必须是显式契约；
- 兼容推导时写入 `compatibility_derived=true`；
- 正式发布前统计仍依赖推导的任务 ID，逐项清零；
- 不修改已完成任务的历史证据。

### 8.4 评测

- Registry 完整性测试；
- 最终 Agent Prompt 快照测试；
- OpenCode 和 Claude Runner 的传输一致性测试；
- 真实模型场景生成、审查、修订 A/B 测试；
- 同一提示词至少覆盖历史、悬疑、现实、幻想四种样例；
- 检查字数、文风、节奏、桥接、Canon 和反 AI 腔规则是否真实生效。

### 8.5 验收

- Prompt Registry 的每个约束字段都能在最终沙箱 Prompt 中找到；
- 新任务不再依赖字符串匹配推导 Agent 角色和人工门禁；
- Prompt 评测报告不再只有 `live_semantic_evaluation: not-run`；
- 真实模型失败样例可以回溯到 Prompt、上下文或门禁，而不是只能人工猜测。

## 9. Workstream B：Vue 客户端架构

### 9.1 技术选型

- Vue 3；
- TypeScript；
- Vite；
- Vue Router；
- Pinia；
- Vitest；
- Playwright；
- Tauri 官方 JavaScript 插件包；
- 不通过 CDN 加载运行时依赖。

### 9.2 目录建议

```text
client/
  src/
    app/
    components/
    features/
      projects/
      workflow/
      library/
      delivery/
      connections/
      advisor/
      autopilot/
      settings/
    stores/
    services/
    styles/
    types/
  tests/
src/literary_engineering_studio/frontend/dist/
desktop/dist/
```

`client` 是 Vue 源码；`src/literary_engineering_studio/frontend/dist` 是 FastAPI 打包资源；`desktop/dist` 只保留本地启动场景等桌面壳静态资源。

### 9.3 组件边界

```text
AppShell
ProjectSwitcher
ProjectHome
WorkflowPulse
TaskTimeline
HumanDecisionInbox
ManuscriptReader
StoryArchive
BranchComparison
DeliveryCenter
ConnectionCenter
ApplicationSettings
AdvisorDock
AutopilotPanel
StartupScene
```

### 9.4 迁移顺序

1. 建立 Vue 构建、API Client、认证和路由壳；
2. 迁移项目创建、打开、切换；
3. 迁移连接与模型；
4. 迁移总控与 SSE；
5. 迁移作品档案和正文阅读；
6. 迁移交付中心；
7. 迁移顾问；
8. 删除旧 `app.js` 中已替换逻辑；
9. 删除旧 DOM 查询式状态和重复 CSS；
10. 保留一个版本的静态前端回退入口，验证后移除。

### 9.5 验收

- 页面刷新不丢失当前项目和当前视图；
- SSE 重连后不重复渲染历史事件；
- 没有全局可变状态散落在组件中；
- API 类型和后端响应契约同步；
- 桌面与浏览器开发模式都能启动；
- 390、1024、1440 像素宽度无横向溢出和遮挡。

## 10. Workstream C：原生目录与项目入口

### 10.1 当前问题

页面已经有“选择”按钮，但只在 `window.__TAURI__.dialog.open` 存在时显示。这种全局探测对动态外部本地 URL、构建配置和插件版本敏感。

### 10.2 改动

- 在前端正式安装 `@tauri-apps/plugin-dialog`；
- 通过模块导入调用 `open({ directory: true, multiple: false })`；
- 保留 Rust `tauri-plugin-dialog` 和 `main` 窗口 capability；
- 封装 `DesktopBridge.selectDirectory()`，不让业务组件直接访问 `window.__TAURI__`；
- 在浏览器开发模式提供明确的手动路径回退；
- 保存最近使用目录；
- 为创建和打开分别设置默认目录；
- 增加项目目录验证接口。

建议接口：

```text
POST /projects/validate-location
POST /projects/create
POST /projects/register
```

目录验证返回：

```json
{
  "valid": true,
  "mode": "create",
  "resolved_path": "...",
  "writable": true,
  "exists": false,
  "conflicts": [],
  "warnings": []
}
```

### 10.3 用户体验

- 普通桌面模式以系统文件夹选择为主；
- 路径只作为确认信息，不要求用户理解；
- 自动生成安全目录名；
- 目录冲突时提供“更换名称”“选择其他位置”；
- 打开错误目录时说明“这里没有找到 ArcVellum 作品”，不显示 `project.yaml missing`；
- 高级设置允许手动粘贴路径。

### 10.4 验收

- 全新用户不输入 Windows 路径即可创建和打开项目；
- 取消选择不会报错或清空已有值；
- 中文、空格和较长目录名可正常工作；
- 浏览器开发模式仍能手动填写；
- 非项目目录不会被登记。

## 11. Workstream D：启动聚合与模型自动加载

### 11.1 新服务

新增 `ApplicationBootstrapService`：

```text
GET  /application/bootstrap
GET  /application/bootstrap/stream
POST /application/warmup
```

返回结构：

```json
{
  "schema": "arcvellum/application-bootstrap/v0.1",
  "ready": true,
  "degraded": false,
  "version": "0.4.0",
  "steps": [],
  "project": {},
  "engine": {},
  "runner": {},
  "model_connection": {},
  "jobs": {},
  "update": {}
}
```

### 11.2 启动步骤

```text
desktop_session
application_database
engine_registry
job_recovery
project_registry
opencode_binary
model_auth_state
selected_model
provider_catalog
updater
```

每一步必须有：状态、开始时间、结束时间、是否阻塞、用户文案、诊断代码和可恢复动作。

### 11.3 模型加载策略

- 启动时读取本地模型连接和上次选择；
- Provider 目录后台刷新并缓存；
- 连接页面使用全局 Store，不再首次触发加载；
- 模型目录设置 TTL；
- 失败时保留上次成功目录并标记过期；
- 连接、断开或切换模型后立即刷新 Worker 和顾问状态；
- 不把 API Key 放入 Studio 配置或项目文件。

### 11.4 验收

- 不打开“连接与模型”页面也能看到当前模型；
- 进入连接页面时内容已经存在或正在明确刷新；
- Provider 暂时不可达不会阻塞进入主界面；
- 不会因为页面切换重复启动 OpenCode 探测；
- 模型变更后新任务使用新模型，既有任务保留原始执行记录。

## 12. Workstream E：用户语言与信息架构

### 12.1 一级导航

建议收敛为：

```text
作品总览
创作进度
作品档案
正文
交付
设置
```

“项目顾问”移出一级导航，成为全局悬浮入口。“连接与模型”进入设置，但在未连接时可从首页状态卡快速进入。

### 12.2 术语映射

| 内部术语 | 普通用户文案 |
| --- | --- |
| Runtime | 创作引擎 |
| Agent Runner | 智能执行器 |
| Task Package | 当前工作 |
| Route | 创作流程 |
| Canon | 已确认设定 |
| Writeback | 应用创作结果 |
| AgentReview | 编辑审查 |
| Expected Outputs | 本次产物 |
| Route Audit | 流程检查 |
| State Patch | 人物状态更新 |
| Provider | 模型服务 |
| waiting_human | 等待你的决定 |
| waiting_writeback | 等待应用结果 |

### 12.3 高级诊断

以下内容只在“设置 > 高级 > 开发与诊断”显示：

- Task ID、Prompt Asset ID、Schema；
- 原始 JSON；
- CLI 命令和退出码；
- 文件绝对路径和沙箱路径；
- 哈希、租约、事件游标；
- Runner 原始事件；
- API 健康详情；
- 内核和数据库迁移版本。

### 12.4 文案规范

- 用用户能控制的对象命名，不用实现术语；
- 按钮使用明确动词，如“开始创作”“应用修改”“稍后决定”；
- 空状态说明下一步，不展示内部错误；
- 错误必须包含影响、原因类别和修复动作；
- 不用营销文案解释功能；
- 同一动作在按钮、提示和历史记录中使用同一名称。

### 12.5 验收

- 普通模式页面不出现 Schema、TaskPackage、Runtime、Route Audit 等内部术语；
- 项目内容和审查证据没有被隐藏；
- 所有错误都能指向用户可执行的恢复动作；
- 高级用户仍可导出完整诊断。

## 13. Workstream F：启动场景与桌面生命周期

### 13.1 当前问题

Tauri 目前先启动 sidecar，等待本地服务，再创建主窗口。服务启动较慢或失败时用户看不到任何状态。

### 13.2 目标流程

```text
Tauri 进程启动
  -> 立即创建 StartupScene
  -> 异步启动 sidecar
  -> 接收后端 readiness
  -> 完成桌面安全会话
  -> Vue 获取 bootstrap 状态
  -> 创建并显示主窗口
  -> 关闭 StartupScene
```

### 13.3 启动场景：The Living Manuscript

视觉过程：

1. 一行文字出现；
2. 文字延展为段落；
3. 段落折叠成章节页；
4. 章节页连接成故事脉络；
5. 每个真实启动阶段点亮一个节点；
6. 脉络展开为作品总览。

状态文案：

```text
正在整理创作空间
正在恢复作品资料
正在连接创作引擎
正在准备上次的工作
```

### 13.4 失败处理

- 45 秒硬等待改为可视状态和分阶段超时；
- 阻塞步骤失败时进入启动诊断页；
- 提供“重试”“打开日志位置”“重新启动应用”；
- 模型离线是降级状态，不是启动失败；
- 数据库迁移失败必须停止进入主界面并显示备份状态。

### 13.5 验收

- 点击应用后 500 毫秒内出现可见窗口；
- 主界面只在核心状态明确后显示；
- 启动场景不伪造进度；
- 减少动态效果设置下使用静态过渡；
- 服务启动失败时用户不会面对无限动画或空白窗口。

## 14. Workstream G：应用信息、更新与诊断

### 14.1 设置与关于

新增页面内容：

- 产品名称、图标、版本和构建号；
- 更新通道和最后检查时间；
- 发行说明；
- 内核版本；
- OpenCode 版本；
- 当前模型；
- 默认项目位置；
- 应用数据和日志位置；
- 许可证与第三方声明；
- 隐私与本地数据说明；
- 导出诊断报告；
- 重启应用；
- 恢复界面默认设置。

### 14.2 更新机制

引入：

- `tauri-plugin-updater`；
- `tauri-plugin-process`；
- 签名更新产物；
- GitHub Releases 更新元数据；
- 稳定和预览更新通道；
- 下载进度；
- 安装后重启；
- 更新失败保留旧版本。

签名私钥不得进入仓库、构建产物或 CI 日志。公钥进入 Tauri 配置。发布流程必须同时输出安装包、更新包、签名、SHA256、版本说明和更新 JSON。

### 14.3 诊断包

诊断导出应包含：

- 应用、内核、OpenCode、操作系统版本；
- 配置摘要，不含凭证；
- 最近任务和错误分类；
- 数据库健康与迁移状态；
- 日志节选；
- 更新状态；
- 项目路径只保留用户确认后的版本或进行脱敏。

### 14.4 验收

- 用户能在客户端确认版本和更新状态；
- 更新包经过签名验证；
- 更新失败不破坏当前安装；
- 诊断包不包含 API Key、令牌和正文全文；
- 产品改名后旧安装可以原位升级。

## 15. Workstream H：顾问自由对话与悬浮窗

### 15.1 当前问题

顾问当前要求模型只返回一个 JSON 对象，并把回答强制拆为 `answer`、`facts`、`inferences`、`uncertainties` 和 `suggested_next_action`。前端又把这些字段全部展开，导致回答像审计报告而不是对话。

### 15.2 新回答契约

```json
{
  "schema": "arcvellum/advisor-answer/v0.2",
  "message_markdown": "自然、连贯、先回答问题的正文",
  "citations": [
    {
      "label": "引用名称",
      "path": "项目相对路径",
      "excerpt": "短摘要"
    }
  ],
  "uncertainties": [],
  "suggested_actions": [],
  "confidence": "medium"
}
```

结构化协议保留在传输层，界面默认只展示 `message_markdown`。引用、不确定项和行动建议按需展开。

### 15.3 对话能力

- 允许讨论作品事实；
- 允许讨论尚未写入项目的创作想法；
- 允许给出文学理论和结构建议；
- 清楚区分项目事实与一般建议，但不机械分栏；
- 记住当前项目、近期对话摘要和用户固定偏好；
- 支持流式输出、中止、重试、编辑重发；
- 项目发生变化后更新只读快照；
- 不在每次回答中重复权限免责声明。

### 15.4 会话记忆

当前“最近八条原始消息”升级为：

```text
recent_messages
session_summary
pinned_user_preferences
current_view_context
project_snapshot_digest
```

摘要只能保存对话语义，不得把项目中不可信指令变成系统指令。

### 15.5 悬浮窗

- 全局右下角入口；
- 380-440 像素侧滑抽屉；
- 支持左右停靠；
- 跨视图保留会话；
- 自动附带当前人物、场景、分支或正文位置；
- 不遮挡正文主阅读面；
- 显示未读和运行状态；
- 支持快捷键；
- 移动宽度下切换为全屏对话层。

### 15.6 白名单动作

顾问不能直接写文件，只能建议：

```text
record_direction
open_project_view
open_character
open_scene
open_branch_choice
start_next_task
pause_autopilot
request_revision
```

动作包含 label、arguments、影响说明和确认级别。协作模式必须由用户点击；授权自动模式可交给 DelegationPolicy 判断。

### 15.7 验收

- 普通回答读起来像自然对话；
- 事实引用仍可追溯；
- 顾问无法创建、编辑或删除项目文件；
- 顾问建议不能绕过 Studio API；
- 对话能把建议安全加入创作方向；
- 项目变化后不会继续引用过期快照而不提示。

## 16. Workstream I：Autopilot 与代理用户

### 16.1 角色分离

新增两个不同角色：

`AutopilotController` 是确定性调度器，负责循环、状态、恢复和限制，不负责文学判断。

`CreativeSteward` 是顶层创作代理，负责分支、风格、修订、扩纲和设定候选等二级决策，不拥有文件和 Shell 权限。

只读顾问不直接升级为可写 Agent。顾问和 CreativeSteward 可以共享模型与部分对话上下文，但必须拥有不同权限、Prompt、会话和审计身份。

### 16.2 运行循环

```text
读取项目级目标
  -> 选择下一条正式路线
  -> task-next
  -> Worker 执行一个任务
  -> 校验终态
  -> 如需决定，生成 DecisionProposal
  -> DelegationPolicy 判断是否可代理
  -> 记录 DelegatedDecision
  -> 恢复任务或进入下一任务
  -> route-audit
  -> 跨路线推进
  -> 全书审查与交付
```

### 16.3 授权策略

```yaml
schema: arcvellum/delegation-policy/v0.1
mode: supervised_auto
delegated_routes:
  - longform-planning
  - scene-development
  - review-and-audit
delegated_decisions:
  - branch_selection
  - style_mount
  - revision_direction
  - budget_expansion
limits:
  max_tasks: 500
  max_runtime_hours: 24
  max_consecutive_revisions: 3
  max_failures_per_task: 2
  max_cost: 100
release_policy: require_user
```

### 16.4 决策身份

代理决策不得写成用户批准。必须记录：

```text
principal_type=delegated-agent
principal_id
delegation_id
policy_version
decision_type
selected_option
rationale
evidence
alternatives
confidence
created_at
revoked_at
```

### 16.5 模式

- 协作创作：所有高影响选择由用户决定；
- 监督自动：普通选择由 CreativeSteward 决定，冲突和发布暂停；
- 全自动交付：用户一次授权后持续推进到完整交付，仍受预算、循环和质量中止条件约束。

### 16.6 必须暂停的条件

- Canon 冲突无法通过候选补丁解释；
- 同一场景连续修订超过限制；
- 字数预算和剧情库存持续不匹配；
- 审查结论互相矛盾；
- 模型、费用或上下文预算不可用；
- 任务输出反复不符合 Schema；
- 用户方向发生互斥变化；
- 更新或迁移期间；
- 授权已撤销或过期。

### 16.7 全书交付

新增 `WholeBookReleaseCoordinator`：

- 汇总章节正式稿；
- 检查缺失章节和场景；
- 检查章节顺序、标题、字数和版本；
- 执行全书长程一致性审查；
- 过滤工作流痕迹、Scene ID、Canon 注释和审查记录；
- 生成全书 Release Manifest；
- 导出 DOCX、Markdown 和交付报告；
- 记录使用的项目快照和正式审查证据。

### 16.8 验收

- 一个三章样例能从创意方向持续运行到 DOCX；
- 中途关闭应用后可恢复；
- 顾问对话可以暂停、改变方向和继续；
- 费用、任务数和修订次数不会越界；
- 所有代理决定可追溯且可以撤销；
- 全自动模式不能调用 debug waiver、unreview 或绕过正式门禁。

## 17. Workstream J：品牌、视觉与动态体验

### 17.1 品牌方向

工作品牌：`ArcVellum`

解释：

- `Arc` 表示人物弧、剧情弧和长篇结构；
- `Vellum` 表示承载作品的书写介质；
- 品牌同时表达文学感和工程秩序。

不采用已经存在明显近似产品的 `VellumArc`、`Narralume`、`ArcQuill` 和 `Quillora`。

### 17.2 视觉命题

视觉主题：`Narrative Observatory`，即“叙事观测台”。应用不是羊皮纸装饰品，也不是黑色代码控制台，而是一台观察长篇作品如何生长、分叉、修订和收束的创作仪器。

### 17.3 色彩

```text
Midnight Moss   #102621
Mineral White   #F5F8F6
Jade Current    #2D7465
Cinnabar Signal #D95B45
Brass Memory    #B8954B
Iris Accent     #71668F
```

深色只用于应用壳和观测区域；正文阅读面保持冷白。朱砂只用于需要决定或风险，玉绿用于正常推进，黄铜用于正式作品和长期记忆，Iris 只作少量分支和顾问识别色。

### 17.4 标志性元素

唯一重点视觉是“动态故事脉络”：

- 当前任务是活跃节点；
- 场景生成表现为节点增长；
- 分支推演表现为线路分叉；
- 分支选择后非选线路降低权重；
- Canon 写回点亮受影响的人物和世界节点；
- Promise/Payoff 形成跨章节连线；
- 正文完成后节点凝结为章节页。

### 17.5 动效规则

- 动效必须表达真实状态；
- 不使用持续漂浮光球和无意义粒子；
- 页面切换、列表变化和任务推进使用短过渡；
- 正文阅读区域不持续运动；
- 提供 `prefers-reduced-motion`；
- 动画失败不影响任何操作；
- 长任务使用事件驱动进度，不伪造百分比。

### 17.6 视觉资产

- 生成一张“故事脉络与稿纸层叠”的主视觉位图；
- 为启动场景生成低对比度背景纹理；
- 继续使用 Lucide 作为功能图标；
- 品牌图标独立设计，不把插画缩成工具图标；
- 所有位图提供 1x/2x 和深浅背景版本；
- 视觉资产必须在桌面和 390 像素宽度验证裁切。

### 17.7 验收

- 首页第一屏能明确识别当前作品和当前创作进度；
- 正文仍是总控与档案中的主要内容；
- 不出现红蓝黑主导的通用 AI 控制台观感；
- 动效不会遮挡、延迟或改变布局；
- 键盘焦点、对比度和减少动态效果通过检查。

## 18. API 与数据迁移

### 18.1 API 版本策略

- 现有 API 在 `v0.4.0` 保持兼容；
- 新接口使用版本化 Schema；
- Vue Client 通过集中 API Client 访问；
- 不允许组件直接拼接大量 URL 和原始 JSON；
- 后端错误返回 `code`、`user_message`、`diagnostic_message` 和 `recovery_actions`。

### 18.2 数据迁移

- 项目格式保持兼容；
- Studio 数据库迁移前自动备份；
- 新增顾问摘要、授权策略、代理决定和更新状态表；
- 旧顾问消息读取时转换为 v0.2 显示结构，不重写原始历史；
- 旧配置中的模型选择继续有效；
- 产品改名不改变应用数据目录身份。

### 18.3 建议新表

```text
advisor_session_summaries
advisor_pinned_preferences
advisor_action_proposals
autopilot_runs
delegation_policies
delegated_decisions
application_bootstrap_events
update_history
```

## 19. 测试计划

### 19.1 后端

- Unit：契约、Prompt 注入、目录验证、Bootstrap 状态、授权策略；
- Integration：OpenCode 模型加载、顾问流式输出、Worker 写回、更新元数据；
- Recovery：进程中断、数据库迁移失败、Provider 超时、SSE 重连；
- Security：路径越界、意外文件、顾问写入、伪造代理身份、凭证泄漏；
- E2E：完整场景路线、三章自主创作、全书导出。

### 19.2 前端

- Vitest：Store、API Client、术语投影、动作确认；
- Playwright：创建项目、目录选择、连接模型、启动任务、顾问、更新页；
- SSE：重连、重复事件、丢失事件和终态；
- Accessibility：键盘、焦点、ARIA、对比度、减少动态效果；
- Screenshot：390x844、1024x768、1440x900、1920x1080；
- Canvas/SVG pixel check：故事脉络非空、无越界、节点可见。

### 19.3 桌面安装

- 干净 Windows 10/11 虚拟机；
- 无 Python、Node、Rust、OpenCode 环境；
- 首次安装、覆盖升级、卸载、重装；
- 单实例、窗口状态、异常退出；
- WebView2 下载失败；
- 更新签名错误和网络中断；
- 中文用户名、中文路径、空格路径；
- 离线启动和模型离线。

### 19.4 文学质量

- 场景功能和叙事节奏；
- 相邻场景桥接；
- Canon 与人物状态；
- 风格挂载；
- 标点和反 AI 腔；
- 字数预算；
- 同模型写作与独立模型审查对比；
- 长上下文下的角色、伏笔和 Promise/Payoff 回收。

## 20. 发布流程

每个正式版本执行：

```text
Python tests
Prompt Registry validation
Prompt deterministic evaluation
Prompt live semantic evaluation
Vue typecheck
Vue unit tests
Vue production build
Playwright desktop screenshots
Rust cargo check
PyInstaller sidecar build
Tauri NSIS build
clean-VM install and smoke test
SHA256 and updater signature
Git tag and GitHub Release
```

版本号必须同步：

- `pyproject.toml`；
- Python `__version__`；
- `package.json` 和 lockfile；
- Tauri `Cargo.toml` 和 lockfile；
- `tauri.conf.json`；
- Vue UI 版本投影；
- 发布说明；
- Updater 元数据。

## 21. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| Vue 与 Tauri、本地 FastAPI 同时改造 | 认证或资源加载回归 | `v0.4.0` 保留 FastAPI 静态服务和本地 URL |
| Provider 目录启动探测过慢 | 启动长时间卡住 | 阻塞/降级/后台步骤分层与缓存 |
| 顾问自然化后引用能力下降 | 回答不可追溯 | 自然正文与隐藏结构化证据并存 |
| 顶层代理拥有过大权限 | 绕过门禁或错误发布 | 决策代理无文件权限，执行由 Controller 和 CLI 完成 |
| 自动模式无限修订 | 成本和时间失控 | 任务、费用、时间、失败和修订上限 |
| 产品改名破坏升级 | 用户配置和数据分裂 | 保留 Tauri identifier 和数据迁移身份 |
| 动效妨碍长时间写作 | 疲劳、卡顿和可访问性问题 | 只让真实状态驱动动效，正文面保持静态 |
| Prompt 文件通过但模型效果差 | 形式合规、创作失败 | 增加真实模型、类型和长程质量基准 |
| 更新私钥泄漏 | 供应链风险 | 私钥只在安全发布环境，日志与仓库禁止保存 |

## 22. 开发依赖顺序

```text
A Prompt/Task Contract
  -> D Bootstrap and Model Warmup
  -> B Vue Shell
  -> C Native Project Entry
  -> E User Language
  -> F Startup Scene
  -> G About/Updater
  -> H Advisor Dock
  -> I Autopilot
  -> J Final Visual Polish
```

依赖说明：

- Autopilot 必须依赖显式任务契约和通用门禁；
- 顾问动作必须依赖 Vue 全局状态和安全 API；
- 启动动画必须依赖真实 Bootstrap 事件；
- 更新机制必须在版本与数据迁移策略稳定后启用；
- 最终视觉重构应在信息架构稳定后进行，避免反复重做。

## 23. Definition of Done

### `v0.4.0`

- 用户通过系统目录窗口创建和打开项目；
- 模型连接在启动期间自动恢复；
- 页面不需要打开设置才知道 Agent 是否可用；
- 普通界面不暴露开发协议；
- 启动立即可见且状态真实；
- 应用内可以查看版本、数据位置、更新和诊断；
- Vue Client 完成主要功能迁移；
- Prompt 和任务契约传输缺口关闭；
- 现有 53 项测试保持通过并新增对应覆盖。

### `v0.4.1`

- 顾问自然流式对话；
- 顾问悬浮窗跨页面工作；
- 引用折叠但可追溯；
- 顾问可以提交白名单动作建议；
- 顾问仍不能修改项目。

### `v0.5.0`

- 用户可以选择协作、监督自动或全自动；
- CreativeSteward 可以作为受委托决策主体；
- AutopilotController 可以跨任务持续推进；
- 用户通过顾问可以改变方向、暂停和恢复；
- 一个三章样例完成从方向到正式 DOCX 的闭环；
- 所有代理决定、成本、失败和发布均可审计。

## 24. 首轮实施清单

第一轮只启动以下工作，避免同时展开所有模块：

1. 修复 Prompt Asset 元数据注入；
2. 让新任务签发显式执行契约；
3. 新增 Bootstrap Service 和测试；
4. 建立 Vue/Vite/TypeScript 构建；
5. 封装 Tauri DesktopBridge；
6. 修复原生目录选择；
7. 启动时自动恢复模型目录；
8. 建立普通术语与高级诊断分层；
9. 完成项目中心和连接中心的 Vue 迁移；
10. 用桌面截图和干净安装验证首轮成果。

完成这十项后，再进入启动场景、更新中心和顾问重构。Autopilot 不应在任务契约和启动状态仍依赖启发式推断时提前实施。
