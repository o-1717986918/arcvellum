# ArcVellum v0.98 内置 Pi Worker 与连续创作闭环实施方案

日期：2026-08-11

状态：实施中

## 1. 交付目标

本轮只在以下条件同时成立时完成：

1. ArcVellum 主仓库拥有专用 Pi Worker 源码、测试、锁定依赖和第三方声明。
2. Windows 安装包携带可执行 Worker 及其运行时，用户无需安装 Node 或外部 Agent 平台。
3. 用户可在“连接与模型”中启用 Pi、选择模型、验证连接，并在推进仪表选择 Pi 作为创作执行器。
4. 从前端等价的用户路径创建一个新作品，选择全自动模式并明确授权。
5. 同一作品由 Pi 连续推进到第一场正文晋升、人物状态和连续性写回，并领取下一场正式任务。
6. 后台证据包含任务、会话、模型请求、工具、预检、修复、写回、Gate、费用和停止原因。
7. 不允许用分段 benchmark、手工补文件、调试豁免或仅单元测试代替连续闭环。

## 2. 架构决策

### 2.1 所有权

Studio/Engine 永远拥有：

- 作品和路线状态；
- TaskPackage、上下文编译与资源声明；
- 沙箱、确定性前置命令、preflight 和 canonicalization；
- writeback、task-complete、route-audit、promotion、state/canon apply；
- Autopilot、授权、预算、恢复和用户决策。

Pi Worker 只拥有：

- 执行一个已领取的 Agent-required TaskPackage；
- 读取 TASK_CONTEXT 与白名单资料；
- 写 Agent-owned expected outputs；
- 本地格式验证、显式完成或结构化阻断；
- 发出有界运行事件和真实用量。

Pi 不成为第二套工作流引擎，不直接读取正式项目路径，不领取下一任务，不运行 CLI、Shell、Git 或任意网络工具。

### 2.2 源码与上游

主仓库新增 `workers/pi-worker/`，迁入 ArcVellum 专用 Worker 源码与测试。整个 Pi monorepo 不复制进主仓库。

Worker 依赖锁定版本的 `@earendil-works/pi-agent-core`、`@earendil-works/pi-ai` 与 TypeBox。`third_party/pi/` 记录上游仓库、版本、摘要、许可证和升级流程。现有 `arcvellum-pi-agent` fork 保留为上游评估和补丁来源，不承担 Studio 业务逻辑。

这样可使 TaskContext、Worker 和安装器变更在同一 PR/CI 中原子验收，同时避免把 coding-agent、TUI、server 等无关包带入产品源码。

### 2.3 安装边界

首个正式可选版本使用“固定 Node 运行时 + 编译后的 Worker 资源”方案，优先可靠性和可诊断性，不在同一批引入未经验证的单文件打包器。

安装资源：

```text
desktop/src-tauri/resources/pi-worker/
  node.exe
  dist/
  node_modules/
  package.json
  pi-worker-installation.json
  PI-WORKER-NOTICE.md
  PI-WORKER-LICENSE.txt
```

构建脚本只复制 production dependency closure。安装收据绑定 Studio commit、Worker source digest、Pi 包版本、Node 版本、文件摘要和许可证。运行时先验证收据与关键文件，再启动 Worker。

## 3. 用户配置

### 3.1 Runner 配置

Pi Worker 的产品配置至少包含：

- enabled；
- model，格式为 `provider/model`；
- thinking preset；
- max turns、tools、repair、provider requests；
- credential source；
- bundled executable/entrypoint 自动发现结果；
- readiness、provider support 和预算支持收据。

开发环境可发现 `~/.pi/agent/auth.json`；桌面端不复制或回显密钥。正式 UI 只显示 Provider 已连接/未连接。首版复用 Pi 自有 CredentialStore，不建立第二套 HTTP Provider SDK。

### 3.2 前端

“连接与模型”新增 Pi Runner 卡片：

- 内置状态；
- 模型选择；
- 连接测试；
- 推理预设；
- 实验/正式可选成熟度；
- 成本、隐私和回退说明。

推进仪表新增执行器选择。开始、恢复、顾问“推进下一步”和全自动均读取当前项目选定 Runtime，禁止继续写死 `opencode`。运行中锁定 Runtime；切换只影响下一任务或新 run。

## 4. 连续端到端合同

### 4.1 测试作品

使用隔离的新作品，不修改用户现有作品。用户输入保持短而真实：中文近未来短篇，目标一章、至少两场，明确人物、冲突、结尾和字数。项目由正式创建 API 初始化，不复制 benchmark fixture。

### 4.2 启动路径

```text
POST /projects
PUT  /autopilot/policy  mode=full_auto
POST /autopilot/start   runtime=pi-worker, authorized=true
```

该路径与前端按钮相同。测试不得直接调用内部 Worker、runtime benchmark 或 Engine 私有函数推进作品。

### 4.3 完成证据

必须同时观察到：

- Pi Runner 探测为 installed/available；
- Autopilot run 的 runtime 为 pi-worker；
- 至少一个真实 Pi session 和 provider request；
- `scene_0001` 正文候选通过 Style Lint 和独立 AgentReview；
- candidate 被 promote 为正式正文；
- state patch 通过语义审查并 apply；
- continuity ledger delta 完成并 apply；
- route-audit 对 scene_0001 完成项通过；
- Autopilot 随后领取 scene_0002 或下一正式场景任务；
- 正式项目无 expected_outputs 之外的写入；
- 无未回收 Worker 进程；
- 前端可看到正文和推进状态。

### 4.4 后台监测

测试期间持续读取：

- `/autopilot/status`；
- `/agent-observability`；
- `/autopilot/runs/{id}/events`；
- workflow dashboard/route audit；
- 最新 run manifest、runtime JSONL、preflight 和 writeback receipt；
- promoted draft、state、continuity 和下一 task identity；
- Worker/Node 进程列表。

以下情况立即判定阻断并停止盲目重试：

- 同一 progress digest 连续出现；
- 只产生 reasoning、没有工具或文件活动；
- 读取未授权资料；
- prompt 与实际可读集合不一致；
- preflight 相同 issue 重复；
- writeback 后状态不前进；
- Runtime 被静默切回 OpenCode；
- 任务已完成但回合预算误判失败；
- 进程退出后仍被报告为运行。

## 5. 实施批次

### B1：源码与供应链

- 迁入 `workers/pi-worker`。
- 建立独立 package/lock、测试和 build 命令。
- 添加 third-party manifest、NOTICE、LICENSE、provenance builder。
- 保持现有 Pi fork 可同步。

门禁：Worker 单测、TypeScript build、Studio architecture audit、Git diff check。

### B2：运行时产品化

- 增加 bundled Worker locator/verification。
- 默认配置从 bundle 自动发现 executable、entrypoint 和 auth source。
- Pi probe API、配置保存和模型选择。
- 取消 experiment-only 构建级阻断，但保留用户显式启用。

门禁：无 Node PATH 也可探测 bundle；错误收据、缺文件、错误模型和缺凭证给出稳定错误码。

### B3：前端与全自动接线

- Runner 选择 store/API/UI。
- AutopilotPanel、AdvisorDock 和手动 Worker 使用选定 Runtime。
- Pi 设置卡、连接测试和运行状态。
- 运行中禁止无提示切换 Runtime。

门禁：Vitest、类型检查、生产构建、前端路径 API 断言。

### B4：连续 E2E 与系统修复

- 创建隔离作品并从用户 API 启动全自动 Pi。
- 持续监测直到下一场。
- 每个阻断先记录 root cause，再做最小系统修复。
- 修复后从干净测试作品重跑，不在损坏项目上手工续接冒充通过。

门禁：保存脱敏 E2E 报告、事件时间线、产物摘要和进程收据。

### B5：安装与发布

- 全量 Python/Vitest/visual/architecture/prompt tests。
- 本地生产构建。
- 干净安装后从 UI 验证 Pi installed/available。
- 自动更新、卸载和进程残留检查。
- 版本、README、CHANGELOG、Release notes、Git 提交与 GitHub Release。

## 6. 质量与回滚

- 每批独立 Git commit；不把 B1-B5 压成单次不可回滚提交。
- 任何问题都不得通过关闭 Gate、扩大文件权限、增加无限重试或自动切回 OpenCode解决。
- 机械字段继续由 Studio canonicalization 生成；Pi 只提交语义产物。
- 正文只能由 Pi 主创 Worker 生成，任何未来子 Agent 仍禁止写正文。
- 若 Pi 连续闭环质量低于现有 Runtime，允许作为正式可选能力发布，不宣布为默认能力。

## 7. 当前进度

- [x] 已完成 Pi 真实规划、RP、正文和审查任务矩阵。
- [x] 已完成 Worker 终轮验证与 Studio 有界修复。
- [ ] 未完成同一作品连续全自动闭环。
- [ ] 未迁入主仓库。
- [ ] 未进入安装包。
- [ ] 未接入普通用户前端配置与 Runtime 选择。
