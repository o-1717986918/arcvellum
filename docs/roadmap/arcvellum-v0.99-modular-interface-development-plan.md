# ArcVellum v0.99 模块化接口开发与运行时效率收敛计划

状态：M0-M3 代码与编译门禁已完成，M3 当前实时 A/B 与真实 E2E 在 Provider 402 恢复点暂停，进入 M4
适用范围：`literary-engineering-studio` 开发仓库  
基线版本：v0.98.0，提交 `704c446`  
目标形态：可持续扩展的模块化单体，而不是提前拆成微服务

## 1. 文档目的

本文建立 ArcVellum 从“已经有清晰分层和若干高质量模块”继续演进为“主要变化点均通过稳定接口连接”的统一实施路线。它同时收敛四类问题：

1. 作品规模、功能数量和 Runtime 数量增长后，修改一个模块不应迫使开发者理解整个仓库；
2. Engine、Studio、Agent Runtime、Pi Worker、API、Vue 与桌面壳之间应有可验证的依赖方向；
3. Pi Worker 的效率、预算、缓存、超时和提示词不能继续由零散策略拼接；
4. 模块化不能以增加空接口、重复 DTO、无意义子类或第二套状态机为代价。

本文是实施计划，不把尚未完成的接口描述成现状。现有领域规则仍以正式 Engine Gate、TaskPackage 和已通过的连续文学闭环为准。

## 2. 实际审计证据

### 2.1 仓库规模

本次审查基于实际工作树，而不是历史对话印象：

| 项目 | 数量 |
|---|---:|
| Git 跟踪文件 | 1,873 |
| Studio Python 文件 | 393 |
| Engine Python 文件 | 435 |
| Vue/TypeScript 客户端源文件 | 211 |
| Pi Worker TypeScript 源文件 | 11 |
| Python 测试文件 | 215 |
| Studio 到 Engine 的模块依赖 | 96 个去重目标，分布于 56 个文件 |
| 显式 Python `Protocol` 声明 | 12 |
| 直接依赖通用 `services/api` 的客户端文件 | 41 |

### 2.2 架构审计结果

`python scripts/architecture_audit.py --json` 当前通过：

- import cycle：0；
- dependency violation：0；
- duplicate route：0；
- parse error：0；
- 超过文件预算的既有债务：33；
- 超过函数长度或复杂度预算的既有债务：201；
- 架构审计记录的兼容 facade 依赖项：197。

这意味着架构债务没有突破冻结基线，不意味着债务已经清零。当前审计只强制少数关键依赖方向，还未证明全工程遵循端口/适配器边界。

### 2.3 定向测试结果

以下 29 项定向测试全部通过：

- 架构基线与依赖方向；
- 模块化运行时导入；
- Runtime capability contract；
- API route surface；
- Pi Worker 命令、能力、预算和错误分类。

连续创作与发布证据沿用 v0.98 计划中的正式记录。本文后续实施不得降低这些 Gate 或用单元测试替代真实连续闭环。

## 3. 结论：当前是否支持完全模块化面向接口开发

### 3.1 简短结论

**当前支持继续进行模块化开发，但尚不支持“完全模块化、全面面向接口、模块可任意替换”的开发方式。**

更准确地说，项目已经具备多数模块化基础设施，但不能用一个简单百分比把“目录拆分”、
“合同稳定”和“实现可替换”混为一谈：

- Engine 与 Studio 的单向依赖已经成立；
- Capability Broker、自适应编排、部分应用服务和 API dependency bundle 已经展示了正确模式；
- Runtime 有共同基类和统一结果合同；
- CI、架构债务棘轮和连续 E2E 为重构提供了保护。

但以下问题仍阻止“完全接口化”：

- Studio 有 56 个文件直接依赖 Engine 模块，而不是一组收敛的公开 Engine ports；
- `ApplicationLifecycleManager` 直接构造存储、事件、缓存、进程池、执行协调器和 supervisor；
- Runtime 通过全局 `RUNTIME_TYPES` 和 `isinstance(OpenCodeRuntime)` 装配，新增适配器要修改核心注册代码；
- `create_app()` 是接近 300 行的组合根，并存在模块级 `_STYLE_MOUNTS` 可变服务实例；
- Persistence、事件、时钟、ID、事务和读模型还没有统一端口；
- Vue 中 41 个文件直接依赖通用 API 传输层，feature 边界仍可互相穿透；
- 33 个大文件和 201 个复杂函数使若干模块虽然“目录上拆开”，内部仍是逻辑聚集点；
- Pi Worker 的 Provider 可靠性、缓存身份、推理升级和提示词 IR 仍未形成独立模块。

### 3.2 目标不是“每个类都有接口”

ArcVellum 应采用 **模块化单体 + Ports and Adapters + 显式组合根**：

- 领域内部纯函数、稳定值对象和单实现算法不创建接口；
- 只有跨包、跨进程、外部供应商、持久化、时间/随机性和高变更率边界定义接口；
- 接口由使用方拥有，适配器依赖接口，不让领域层依赖 SDK；
- 同一业务事实只有一个权威写入者，不因模块化产生第二套 workflow、route 或状态；
- 通过注册表和依赖注入获得可扩展性，不通过动态扫描任意 Python 模块获得“插件感”。

## 4. 目标架构

```text
Vue feature modules / Tauri shell
          |
          v
Interface adapters: HTTP, SSE, desktop commands
          |
          v
Studio application use cases + application ports
          |
          +--------------------------+
          |                          |
          v                          v
Engine public API ports       Runtime execution ports
          |                          |
          v                          v
Formal literary engine        Pi/OpenCode/Claude/Codex adapters
          |                          |
          +-------------+------------+
                        v
Infrastructure adapters: file store, SQLite, event log, process, cache
```

硬依赖方向：

```text
contracts/domain <- application <- adapters <- framework/SDK
```

禁止方向：

- Engine -> Studio；
- 领域合同 -> FastAPI/Vue/Tauri/Pi/OpenCode；
- projection -> promotion/writeback；
- orchestration -> API；
- frontend feature -> 另一个 feature 的具体窗口组件；
- Runtime adapter -> Engine route 实现；
- Agent/Provider -> 正式项目文件直接写入。

## 5. 当前风险与优先级

### P0：必须先处理的结构风险

1. **组合根分散。** `api_server.create_app()`、`ApplicationLifecycleManager` 和若干模块级服务共同承担装配，测试能替换路由依赖，却不能轻易替换整个存储、事件或 Runtime 注册表。
2. **Engine 公开表面不够窄。** Studio 的 96 个去重模块依赖跨越 literary、foundation、orchestration、prompting、tasking、workflow 和 projects，内部文件移动成本高。
3. **架构规则覆盖不足。** 当前脚本只阻止少数已知错误方向，没有强制 application/domain/infrastructure/API、Engine public API 和客户端 feature 的完整边界。
4. **Runtime 开放封闭性不足。** `RUNTIME_TYPES`、具体类判断和探测逻辑耦合，使新 Runtime 无法只通过一个 descriptor/adapter 注册。

### P1：影响效率与稳定性的结构风险

1. **Pi Provider 可靠性未独立。** 请求预算在 payload 时累计，缺少完整的 first-byte/inter-event/total timeout、错误分类重试、熔断和 capability probe 层。
2. **推理预算语义扁平。** `minimal/low/medium/high` 当前映射到同一 `perRequestTokens`；`maxEscalations` 被记录但没有驱动真实升级。
3. **会话身份与缓存身份混在一起。** 每次任务包含 PID 与时间戳生成新 session，隔离是安全的，但无法获得稳定前缀缓存；不能用复用整本对话来粗暴解决。
4. **Prompt 输入仍是文件集合。** 正文完整 Prompt 仍约 30,069 字符，场景、Context Packet、Composition、预算之间存在重复语义。
5. **前端数据访问分散。** feature、组件和全局 store 都可直接调用通用 API，难以替换传输、离线测试或稳定 feature contract。

### P2：持续维护风险

1. 大文件热点集中在 Scene、Canon、Planning、Review、Workflow、Preflight、Worker、Orrery 和 Advisor；
2. 兼容 facade 很多，迁移安全但公共表面过宽，需要版本化退场计划；
3. `CONTRIBUTING.md` 未列出 architecture audit 与 Pi Worker check，`AGENTS.md` 仍引用旧前端 `node --check` 命令；
4. Python DTO、JSON schema、TypeScript type 和 TypeBox 合同尚未形成统一生成/兼容流程。

## 6. 完整模块化清单

状态说明：**稳固**表示边界已清晰且有测试；**部分**表示已有模块但接口或依赖方向不完整；**缺失**表示需要新建正式边界。清单中的接口名是目标名称，可在实施时因代码语境微调，但职责不可合并回巨型服务。

### 6.1 Engine 文学内核

| # | 模块 | 当前 | 目标公开接口/合同 | 下一步 |
|---:|---|---|---|---|
| E01 | 项目身份与路径 | 部分 | `ProjectIdentity`, `ProjectLayout` | 统一项目根、相对路径和 revision，禁止散落路径拼接 |
| E02 | 项目 schema/迁移 | 部分 | `ProjectSchemaCatalog`, `ProjectMigrator` | 版本化迁移，不让 route 自行修 schema |
| E03 | TaskPackage 合同 | 稳固 | `TaskPackage`, `TaskEnvelope`, `CompletionEvidence` | 保持 Engine 权威，禁止 Studio 复制判断 |
| E04 | 任务生命周期 | 稳固 | `TaskLifecycleService`, `TaskReceipt` | 将外部依赖收敛为 clock/store callback ports |
| E05 | Route Catalog | 稳固 | `FormalRouteCatalog`, `RouteDefinitionLike` | 只暴露查询与验证，不暴露内部 definition 文件 |
| E06 | Workflow 状态 | 部分 | `WorkflowSnapshot`, `WorkflowStateReader` | 统一 route state 投影，减少调用方直接扫文件 |
| E07 | Route Audit/Gate | 稳固 | `GateEvaluator`, `RouteAuditReport` | Gate ID 版本化并进入兼容测试 |
| E08 | 长篇故事架构 | 部分 | `StoryArchitectureService` | 拆分解析、候选、审查、物化，保留单一物化入口 |
| E09 | 字数预算 | 部分 | `WordBudgetPlanner`, `WordBudgetContract` | 以汉字/标点口径统一规划、生成和 review |
| E10 | 叙事节奏 | 部分 | `RhythmPlanService`, `RhythmContract` | 分离全书曲线、章节投影、场景执行约束 |
| E11 | Reader Question/Promise | 部分 | `ReaderLedgerService` | 统一 question、promise、payoff、delay 的 patch/apply |
| E12 | 场景 Context | 部分 | `SceneContextCompiler` | 从“拼文件”升级为 evidence-aware 写作简报 |
| E13 | RP 推演 | 部分 | `RoleplaySimulationService` | 保留 Agent task，分离数据准备、任务渲染与结果验证 |
| E14 | 分支推演 | 部分 | `BranchSimulationService` | 分离候选、评分、选择和正式决策合同 |
| E15 | 场景 Composition | 部分 | `SceneCompositionService` | 以 `SceneWritingBrief` 作为唯一生成输入 IR |
| E16 | 正文候选与修订 | 部分 | `ProseCandidateService`, `RevisionContract` | 统一 candidate provenance、exact source 和修订闭环 |
| E17 | Agent Review | 部分 | `SceneReviewService`, `ReviewVerdict` | 确定性 lint 先行，Agent 语义审查独立，修订后复核 |
| E18 | Promotion | 稳固 | `CandidatePromotionService` | 保持 exact candidate hash 与全部 Gate 绑定 |
| E19 | 人物资产 | 部分 | `CharacterRepository`, `CharacterCandidateService` | 主/次角色、背景、状态分别版本化，禁止 route 直接覆盖 |
| E20 | 世界/地点/组织资产 | 部分 | `WorldAssetRepository`, `AssetCandidateService` | 复用统一候选-审查-晋升合同 |
| E21 | Canon | 部分 | `CanonRepository`, `CanonPatchService` | 分离提取、审查、审批、原子 apply |
| E22 | 人物状态演化 | 部分 | `CharacterStatePatchService` | 与 Canon/continuity 保持独立 patch，统一 apply receipt |
| E23 | Continuity Ledger | 部分 | `ContinuityLedgerService` | 明确 writer session、delta 和 apply contract |
| E24 | 文风学习 | 部分 | `StyleCorpusService`, `StyleProfileCompiler` | 输入语料、Prompt 生成、回译评估、晋升各自版本化 |
| E25 | 文风挂载 | 部分 | `StyleMountService`, `MountedStyleSnapshot` | 挂载进入生成简报，审查只验证而非首次注入 |
| E26 | Prompt Registry | 稳固 | `PromptAssetCatalog`, `PromptProgramCompiler` | 从模板集合升级为版本化 Prompt Program |
| E27 | 文学质量规则 | 部分 | `CreativeQualityProfile`, `LintRuleSet` | 用户可配置部分与不可关闭底线分层 |
| E28 | 作品倒推/考古 | 部分 | `SourceIngestService`, `EvidenceGraph`, `ReconstructionService` | 保持证据到候选链，避免语义推断混入 reader |
| E29 | 汇编与 DOCX | 部分 | `ManuscriptAssembler`, `DocumentExporter` | 正文过滤合同独立于 DOCX 渲染实现 |
| E30 | 发布与交付 | 部分 | `ReleaseReadinessService`, `PublicationService` | 发布审批与文件导出分开，可重放 receipt |
| E31 | Engine 公开 API | 缺失 | `literary_engineering_studio_engine.public` | 建立稳定 facade，逐步消除 56 个 Studio 文件的内部导入 |

### 6.2 Studio 应用层

| # | 模块 | 当前 | 目标公开接口/合同 | 下一步 |
|---:|---|---|---|---|
| A01 | 应用组合根 | 缺失 | `ApplicationContainer`, `ApplicationPorts` | 由一个工厂装配 concrete adapters，移除模块级可变服务 |
| A02 | 生命周期 | 部分 | `LifecycleService` | 构造函数注入 store/event/process/cache/runtime registry |
| A03 | 项目管理 | 部分 | `ProjectApplicationService` | 只通过 Engine public API 和 ProjectStorePort 操作项目 |
| A04 | 资产工作台 | 部分 | `AssetApplicationService` | 统一 revision、candidate、review、promotion、recycle bin 用例 |
| A05 | 文风工作台 | 部分 | `StyleApplicationService` | 去除 API 层全局 `_STYLE_MOUNTS`，按 app 实例注入 |
| A06 | 考古工作台 | 部分 | `ArchaeologyApplicationService` | 统一导入 job、进度、候选与物化用例 |
| A07 | 顾问 | 部分 | `AdvisorQueryService`, `AdvisorCommandIntent` | 读模型回答与结构化用户指令分离 |
| A08 | Human Decisions | 部分 | `DecisionGateway`, `DecisionReceipt` | 前端、全自动 Steward 和 CLI 共用一个写入入口 |
| A09 | Autopilot/Campaign | 部分 | `CampaignController`, `AutomationPolicy` | 控制循环不直接依赖具体 Worker/JobStore |
| A10 | 自适应编排 | 稳固 | `CreativePlanService`, `PlanCompiler`, `PlanSimulator` | 保持 Future Intent，不形成第二套任务状态 |
| A11 | Workflow 用例 | 部分 | `WorkflowApplicationService` | 统一 status/next/open/submit/complete/advance |
| A12 | 交付用例 | 部分 | `DeliveryApplicationService` | 将 readiness、审批、导出、下载分开 |
| A13 | Read Model | 部分 | `ReadModelProvider`, `ReadModelCachePort` | 投影只读，增量事件驱动失效 |
| A14 | 配置 | 部分 | `ConfigurationService`, `SecretReference` | schema、默认值、迁移、用户覆盖分层；秘密不进入普通配置 |

### 6.3 Runtime、Agent 与基础设施

| # | 模块 | 当前 | 目标公开接口/合同 | 下一步 |
|---:|---|---|---|---|
| R01 | Runtime SPI | 部分 | `AgentRuntimePort`, `RuntimeDescriptor` | 用 Protocol/ABC 明确行为，去除具体类分支 |
| R02 | Runtime Registry | 部分 | `RuntimeRegistryPort` | 显式注册 descriptor/factory，测试可注入，不动态扫描 |
| R03 | Runtime 探测 | 部分 | `RuntimeProbePort` | 探测、能力、认证、模型选择分开缓存 |
| R04 | 任务执行策略 | 部分 | `TaskExecutionPolicy` | execution lane、reasoning、timeout、repair 统一编译 |
| R05 | Provider 可靠性 | 缺失 | `ProviderTransport`, `RetryPolicy`, `CircuitBreaker` | first-byte/idle/total timeout、错误分类和有限重试 |
| R06 | Provider 能力探测 | 缺失 | `ProviderCapabilityProbe` | 推理等级、结构化输出、cache、tool call 可验证 |
| R07 | Prompt cache | 缺失 | `PromptCachePolicy`, `PromptCacheKey` | stable prefix 与 task session 分离，不复用整本对话 |
| R08 | Pi Artifact Executor | 部分 | `StructuredArtifactExecutor` | 机械/结构化任务尽量单请求、单提交、机器验证 |
| R09 | Pi Creative Worker | 部分 | `CreativeAgentWorker` | 有界工具循环、正文主 Agent、失败可解释 |
| R10 | Pi Review Worker | 部分 | `IndependentReviewWorker` | 与写作 session/profile 隔离，消费 lint 证据 |
| R11 | OpenCode/外部 CLI | 部分 | 统一实现 `AgentRuntimePort` | 只保留 adapter 差异，不复制 Worker 业务规则 |
| R12 | Capability Broker | 稳固 | `CapabilityBroker`, `CapabilityRegistry` | 未来把 ID catalog 与 handler registry 分离，避免 Enum 封闭扩展 |
| R13 | Sandbox | 部分 | `SandboxPort`, `SandboxManifest` | staging、权限、diff、import 分为可测试阶段 |
| R14 | Writeback | 部分 | `WritebackPort`, `MutationReceipt` | expected outputs、backup、atomic import、receipt 统一 |
| R15 | Preflight | 部分 | `ArtifactValidator`, `ValidationIssue` | canonicalization 与 validation 不互相代替 |
| R16 | Job Store | 部分 | `JobRepository`, `LeaseRepository`, `UnitOfWork` | application 不直接依赖 SQLite 实现 |
| R17 | 事件 | 部分 | `EventPublisher`, `EventStore`, `EventCursor` | durable event 与瞬时 SSE 分层 |
| R18 | 进程管理 | 部分 | `ProcessSupervisorPort` | sidecar 启停、健康、回收、日志由单模块拥有 |
| R19 | 缓存 | 部分 | `PreparedContextCachePort`, `ReadModelCachePort` | 明确 key、TTL、失效、容量和隐私 |
| R20 | Context Broker | 部分 | `EvidenceProvider`, `ContextCompiler` | 按任务证据需求生成语义 IR，不遍历全项目 |
| R21 | 可观测性 | 部分 | `RunTelemetryPort`, `RunTrace` | 会话、请求、tool、repair、Gate、成本统一关联 ID |
| R22 | Benchmark/Eval | 部分 | `RuntimeBenchmarkSuite`, `LiteraryQualityEvaluator` | 质量、成本、延迟、闭环率共同决定默认 Runtime |

### 6.4 API、前端与桌面端

| # | 模块 | 当前 | 目标公开接口/合同 | 下一步 |
|---:|---|---|---|---|
| U01 | FastAPI 组合 | 部分 | `ApiApplicationFactory` | 只消费 `ApplicationContainer`，路由不自行建服务 |
| U02 | Router dependencies | 稳固 | feature `*Dependencies` | 继续保留，改为应用用例接口而非自由 callable 集合 |
| U03 | HTTP/SSE schema | 部分 | versioned API DTO/OpenAPI | 生成 TS 类型并做兼容快照 |
| U04 | Client transport | 部分 | `HttpTransport`, `EventStreamTransport` | 通用传输不包含业务路径 |
| U05 | Frontend feature client | 部分 | 每 feature 的 `*Client` | 41 个直接 generic API 依赖逐步收敛 |
| U06 | Frontend use-case store | 部分 | feature-local store/composable | 组件不直接发网络请求 |
| U07 | 跨 feature 协调 | 缺失 | `WorkspaceCommandBus`, shared read contracts | 禁止 feature 引入另一个 feature 的具体窗口 |
| U08 | 星仪数据投影 | 部分 | `NarrativeProjectionClient` | 图形层只消费稳定 graph DTO |
| U09 | 星仪布局算法 | 部分 | `OrreryLayoutEngine` | 从 934 行 renderer 分离布局、镜头、曲线、主题和交互 |
| U10 | 星仪渲染 | 部分 | `OrreryRenderer` | Pixi 生命周期、节点、边、背景和动画可独立测试 |
| U11 | 档案 IDE | 部分 | `ArchiveWorkspaceService` | 读取、候选编辑、人工晋升保持不同命令 |
| U12 | 阅读器 | 部分 | `ReaderDocument`, `ReaderNavigation` | 正式正文增量拼接和阅读状态独立 |
| U13 | 顾问 UI | 部分 | `AdvisorConversationClient` | Markdown、流式、命令意图与回答展示分离 |
| U14 | Agent 观测台 | 部分 | `AgentRunProjection` | 不读原始日志猜状态，使用统一 telemetry DTO |
| U15 | 设置/模型连接 | 部分 | `ConnectionSettingsClient` | 用户选择持久化，Runtime/Provider/Model 三层分开 |
| U16 | Tauri shell | 部分 | `DesktopHostPort` | 窗口、目录选择、sidecar、更新均通过窄命令合同 |
| U17 | 安装与更新 | 稳固 | `ReleaseManifest`, updater contract | 保持资源摘要、签名、生命周期验收 |

### 6.5 横切工程模块

| # | 模块 | 当前 | 目标 | 下一步 |
|---:|---|---|---|---|
| X01 | 合同版本 | 部分 | 所有跨进程 DTO 带 schema/version | 建兼容矩阵与弃用窗口 |
| X02 | 错误模型 | 部分 | `ErrorCode`, `FailureKind`, user message | 禁止用任意字符串决定重试或 UI 行为 |
| X03 | Clock/ID | 缺失 | `Clock`, `IdGenerator` | 只在需要确定性测试的边界注入 |
| X04 | 日志与隐私 | 部分 | structured redacted logging | 正文、密钥和 raw reasoning 默认不落诊断日志 |
| X05 | 架构 fitness tests | 部分 | 完整层级和 public API 规则 | 扩展当前四条 dependency rule |
| X06 | 兼容 facade | 部分 | `compatibility_manifest` | 每个 facade 有 owner、替代路径和最早移除版本 |
| X07 | 测试金字塔 | 稳固 | contract/unit/integration/E2E | 给每个 port 建 adapter contract suite |
| X08 | 性能预算 | 部分 | latency/token/context/cache budgets | 进入 CI 的确定性部分，真实模型保持 opt-in |
| X09 | Git/发布纪律 | 稳固 | 小批提交、版本同步、可回滚 release | 补齐贡献文档命令和架构变更模板 |
| X10 | 开发者文档 | 部分 | module owner + public API + ADR | 新模块必须说明职责、依赖和非职责 |

## 7. 分阶段实施方案

### M0：冻结模块图与强化架构审计

目标：先让未来改动无法继续扩大耦合。

代码级工作：

1. 扩展 `scripts/architecture_audit_core.py`：
   - Studio `application` 不得 import `api`、Vue/桌面或具体 Runtime adapter；
   - Studio `projections` 不得 import application write services；
   - Studio 只能通过 Engine `public`、`contracts`、`orchestration` 指定 facade 导入；
   - Runtime adapters 不得 import Engine route definition；
   - 客户端 feature 不得导入其他 feature 的 Vue 组件。
2. 增加 import allowlist 迁移基线，按文件逐步减少，不允许新增；
3. 生成 `docs/architecture/generated-module-map.md`，只展示所有权与公开入口；
4. 修正 `CONTRIBUTING.md` 和 `AGENTS.md` 的验证命令漂移。

验收：0 新循环、0 新非法依赖；56 个 Engine 依赖文件形成冻结清单。

#### M0 实施记录（2026-08-20）

- 架构基线升级为 `arcvellum/architecture-quality-baseline/v2`；既有依赖债务允许减少，但任何新增文件或新增目标依赖都会使审计失败；
- 冻结 1 个 application -> concrete adapter 文件、56 个 Studio -> Engine 文件、6 个 projection -> application 文件，以及 3 个跨 feature Vue 具体组件依赖文件；
- 对零容忍方向增加即时失败规则：projection 不得依赖写服务，Runtime 不得依赖 Engine route implementation；原有 Engine -> Studio、orchestration -> API 等规则继续生效；
- 新增 `scripts/architecture_boundaries.py`，将依赖提取、分层规则和债务比较从主审计器中分离；
- 新增 `scripts/generate_module_map.py` 与自动生成的 `docs/architecture/generated-module-map.md`，CI 同时检查架构债务和模块图漂移；
- `CONTRIBUTING.md`、`AGENTS.md`、CI 与 Release workflow 已使用同一组正式验证命令；
- 验证通过：13 项架构定向测试、1099 项 Python 全量测试（1 项 Windows symlink 测试跳过）、163 项 Vue 测试、Pi Worker 43 项测试、客户端生产构建和架构审计；
- 首轮全量 Python 测试与 Vite 构建并行时有 1 项 Engine 后台启动等待超时；隔离用例与串行全量复验均通过。后续重型验收必须串行，避免资源竞争制造假回归。

M0 只建立防扩散棘轮，不把既有依赖伪装成已解耦。下一批必须从 M1 的组合根与应用端口开始，不能直接跳到大规模 Engine import 搬迁。

### M1：统一组合根与应用端口

目标：一个测试或新客户端能够替换基础设施，而不修改业务用例。

代码级工作：

1. 新建 `application/container.py`：`ApplicationPorts`、`ApplicationServices`、`build_application_container()`；
2. `ApplicationLifecycleManager` 接受 ports，不再自行构造所有 concrete；
3. `create_app(container=None, config_override=None)` 只装配路由；
4. 删除模块级 `_STYLE_MOUNTS`，Style 服务归 app 生命周期；
5. 为 store、event、process、runtime registry、cache 建最小 Protocol；
6. 现有默认行为由 `infrastructure/defaults.py` 组合，不改变安装版配置。

验收：两个并行 `TestClient` 不共享 Style/Cache 状态；应用服务可使用内存 adapter 测试。

### M2：Runtime SPI 与 Pi 可靠性层

目标：Runtime 可替换，Provider 慢、断流或限额时有一致语义。

代码级工作：

1. 将 `AgentRuntime` 收敛为 `AgentRuntimePort` + 可复用 `SubprocessRuntimeBase`；
2. 新建 `RuntimeDescriptor`、`RuntimeFactory`、`RuntimeRegistry`，去除 `isinstance(OpenCodeRuntime)`；
3. 将 Runtime pool/role/settings 作为 factory context；
4. Pi Worker 新建 Provider reliability wrapper：
   - first-byte、inter-event、total timeout；
   - transient/auth/quota/model/validation 错误分类；
   - 只对 transient transport 错误有限重试；
   - circuit breaker 和 capability probe；
5. 修正推理预算：不同 level 有真实递增预算；实现有证据的有限 escalation，或删除伪配置；
6. 把 `run_session_id` 与 `prompt_cache_key` 分开；默认仍保持 task-scoped session；
7. 建立 `PiArtifactExecutor`、`PiCreativeWorker`、`PiReviewWorker` 三种策略，不创建三套 Engine route。

验收：所有 Runtime 通过同一 contract suite；超时、断流、配额、取消、repair、进程回收有确定性测试。

### M3：Literary IR 与 Prompt Program

目标：模型收到的是经过编译的任务语义，而不是重复的项目文件转储。

代码级工作：

1. 定义 `SceneWritingBrief`：目标、冲突、参与者状态、Canon、节奏、桥接、字数、文风、禁止项、输出合同；
2. 定义 `ReviewBrief`、`StateEvolutionBrief`、`AssetBrief`；
3. `EvidenceProvider` 只提供与 brief 字段有关的带 provenance 证据；
4. Prompt compiler 将稳定 profile/static rules 置于可缓存前缀，task brief 置于动态后缀；
5. exact source paths 和 hashes 保留在机器合同，不把长路径清单反复写进自然语言；
6. 建 Prompt 静态分析：重复段落、冲突规则、无效宿主说明、缺少输出合同、超预算；
7. 以 v3 A/B 数据为基线，同时比较闭环率、首产物时间、总成本、修复次数和文学盲评。

验收：正文 Prompt 重复语义显著下降；任何压缩都不能降低 Gate 通过率和文学质量。

### M4：Engine Public API 收敛

目标：Studio 不再依赖 Engine 内部文件布局。

代码级工作：

1. 新建 `literary_engineering_studio_engine/public/`：
   - `projects.py`；
   - `tasking.py`；
   - `workflow.py`；
   - `literary.py`；
   - `prompting.py`；
   - `projections.py`；
   - `orchestration.py`。
2. public 层只重导出稳定 DTO/服务，不复制实现；
3. 按调用簇迁移 56 个 Studio 文件，每批减少 direct internal import baseline；
4. 给 public API 做 symbol snapshot 和行为合同测试；
5. 旧 facade 按兼容 manifest 保留至最早移除版本。

验收：Studio 对 Engine internal imports 降为 0；Engine -> Studio 继续为 0。

### M5：持久化、事件与读模型端口

目标：SQLite、文件系统和 SSE 不再渗透应用用例。

代码级工作：

1. 拆分 `JobRepository`、`LeaseRepository`、`PlanRepository`、`AssetRevisionIndex` 与 `UnitOfWork`；
2. durable `EventStore` 与 ephemeral `LiveEventPublisher` 分开；
3. Read Model 通过 event/revision 失效，不由 UI 请求触发隐藏写入；
4. file-backed project repository 只负责文件事务，文学验证仍归 Engine；
5. Clock/ID 只在 lease、receipt、event 和 plan revision 边界注入。

验收：automation、advisor、worker 和 API 测试可使用内存 repositories；SQLite adapter 通过同一合同测试。

### M6：Vue Feature Ports 与星仪拆分

目标：组件只负责交互与显示，业务调用留在 feature client/use case。

代码级工作：

1. 为 workflow、projects、delivery、settings、quality、orrery、advisor 建 feature client；
2. 把 41 个通用 API 直接依赖收敛到 services/client 层；
3. 生成 OpenAPI TypeScript DTO，人工类型只保留 UI view model；
4. 引入 shared `WorkspaceCommandBus`，跨 feature 只发命令或消费只读合同；
5. 拆分 `parallaxRenderer.ts`：camera、layout、curves、nodes、edges、background、animation、interaction；
6. 拆分 `AdvisorDock.vue`：conversation state、stream transport、Markdown renderer、drag shell；
7. 为每个 feature 建 mock client 与视觉回归用 fixture。

验收：Vue 组件不直接调用 generic API；跨 feature 具体组件依赖为 0；星仪行为与截图回归通过。

### M7：领域热点偿债

目标：在行为合同保护下逐项降低 33/201 债务，不做一次性大重写。

优先顺序：

1. `runtime/worker.py`、`runtime/sandbox.py`、`preflight/canonicalization.py`；
2. Scene composition/context/branching/state；
3. Canon、Planning、Reader Experience、Longform Audit；
4. Workflow runner/activity/state；
5. Orrery renderer 与 Advisor；
6. CLI parser 只在 command descriptor fixture 完整后拆分。

每个热点使用同一方法：冻结输入输出 -> 提取值对象/纯函数 -> 建 facade -> 迁移调用 -> 删除重复 -> 重跑 E2E。不得只为行数把同一个巨大函数机械切成多个互相修改共享状态的小函数。

阶段目标：超长文件从 33 降至不高于 20，复杂函数从 201 降至不高于 120；数字是方向指标，正式行为不允许为指标退化。

### M8：扩展 SDK（1.0 后候选）

只有 M0-M7 稳定后才考虑：

- 第三方只读 projection；
- 受控 Capability handler package；
- 自定义 exporter；
- 自定义 Runtime descriptor；
- 自定义前端面板 manifest。

不得开放任意 Python import、Shell、项目根写权限或绕过 Gate 的插件 API。

## 8. Pi Worker 效率专项并入模块化路线

### 8.1 立即修复

- Provider request 计数在发起前检查，避免预算多发一次；
- 将 transport retry 与 semantic repair 分开；
- 无 Provider activity 的 first-event timeout 不再依赖总 timeout；
- 对 quota/auth/validation 不重试；
- 删除无实际执行效果的 reasoning escalation 配置，或完成真实实现；
- reasoning level 使用不同预算，不再四档同值。

### 8.2 缓存策略

- 不复用包含旧正文和旧状态的跨任务完整对话；
- 稳定前缀：Worker profile、工具定义、作品稳定文风/Canon 摘要；
- 动态后缀：task brief、当前 scene、候选和修复反馈；
- `prompt_cache_key = project + profile_revision + stable_context_digest`；
- `run_session_id = task + attempt + runtime instance`；
- 缓存命中、写入、失效和节省 token 进入 telemetry。

### 8.3 并发边界

- 可并发：独立只读研究、不同资产提取、审查维度、未来场景预热；
- 不可并发：同一正式正文写入、Canon apply、state apply、promotion、release；
- 并发前同时满足 DAG、ResourceClaim 和文学 barrier；
- subagent 只做只读证据提取/机械分析，正文仍由主创 Agent 完成。

## 9. 接口设计纪律

每个新 port 必须回答：

1. 谁拥有接口；
2. 哪个变化点需要隔离；
3. 输入输出是否为稳定 DTO；
4. 错误语义是否结构化；
5. 是否存在至少两个 adapter，或明确的测试替身价值；
6. 是否能避免调用方知道路径、SDK、进程或数据库细节；
7. 是否会制造第二套业务真相。

不满足这些问题时，优先使用普通函数、dataclass 或模块，不新建抽象基类。

禁止：

- 为每个 Provider 建 Runtime 子类；
- 为每个任务类型建 Worker 子类；
- 为只有一个稳定纯算法的类创建 Repository；
- 用 `dict[str, Any]` 充当跨层万能合同；
- 用 service locator 隐藏依赖；
- 在接口里泄漏 FastAPI Request、Pi SDK payload、SQLite row 或 Vue component；
- 在 facade 中复制业务逻辑。

## 10. 架构验收指标

### 10.1 依赖与接口

- Engine -> Studio：0；
- Studio -> Engine internal：从 56 个文件逐批降至 0；
- 新跨包边界必须通过 public API/Protocol；
- application -> API/framework：0；
- frontend cross-feature concrete component imports：0；
- 运行时新增 adapter 不修改 Worker/Engine route 业务代码。

### 10.2 质量与复杂度

- import cycle、forbidden dependency、duplicate route、parse error 始终为 0；
- 任何新文件默认不超过 350 行，超过 450 行需 ADR；
- 任何新函数默认不超过 60 行、复杂度不超过 12；
- 既有 33/201 债务只减不增；
- public contract 有 schema/version/compatibility test。

### 10.3 创作效率与鲁棒性

- 同一 benchmark 的闭环完成率不低于 v0.98；
- 统计 time-to-first-artifact、总延迟、Provider 请求数、输入/输出 token、repair 次数、成本；
- 传输失败不污染正式项目；
- retry 不重复写入；
- cancellation 后进程、lease 和临时目录可回收；
- Prompt 压缩必须通过文学盲评、Gate 和 exact output contract。

### 10.4 用户体验

- 普通用户不需要理解接口或文件树；
- UI 能解释当前 Agent、任务、等待原因、失败类别和下一步；
- 设置中的 Runtime、Provider、Model 选择持久；
- 全自动模式只在真正 Gate 或不可恢复错误时停；
- 高级观测可以看到上下文摘要、工具、token、缓存和 retry，但默认不泄漏秘密。

## 11. 测试矩阵

每批最低验证：

```powershell
python -m unittest <本批定向测试> -v
python scripts/architecture_audit.py
python -m compileall -q src
python -m literary_engineering_studio_engine prompt-registry-validate --json
git diff --check
```

跨模块批次再运行：

```powershell
python -m unittest discover -s tests -v
npm run client:test
npm run client:build
npm run pi-worker:check
python scripts/verify_version_sync.py
```

Runtime、Worker、Prompt 或文学路线变更必须补：

- adapter contract suite；
- sandbox/preflight/writeback integration；
- 一个真实模型 opt-in benchmark；
- 一个完全用户路径的连续场景闭环；
- scene promotion -> state/canon/continuity -> next scene 衔接证据。

## 12. Git 实施序列

每个提交只处理一个可回滚边界：

```text
docs(architecture): freeze modular interface plan and current dependency map
test(architecture): enforce layered dependency and engine public-api baselines
refactor(application): introduce explicit application composition root
refactor(runtime): replace concrete runtime registry with descriptor factories
feat(pi-worker): add provider reliability and effective reasoning policies
feat(prompting): compile literary IR into versioned prompt programs
refactor(engine): publish stable engine API and migrate studio consumers
refactor(persistence): introduce repositories events and unit-of-work ports
refactor(client): introduce feature clients and generated API contracts
refactor(orrery): split layout rendering camera and interaction engines
refactor(domain): retire protected complexity debt in behavior-locked batches
docs(architecture): record final dependency and compatibility state
```

每批流程：回读本文 -> 写批次计划 -> 修改 -> 定向测试 -> 架构审计 -> 必要时全量/E2E -> 更新本文状态 -> 独立提交。禁止一批同时重写 Engine、Runtime、API 和前端。

## 13. 完成交付定义

v0.99 模块化收敛只有同时满足以下条件才算完成：

1. `ApplicationContainer` 成为唯一应用装配入口，没有模块级可变业务服务；
2. Runtime 通过 descriptor/factory 注册，所有 adapter 通过统一合同测试；
3. Provider 可靠性、推理预算、缓存身份和 telemetry 有独立模块与测试；
4. 正文、审查和状态任务使用版本化 literary brief，不再重复转储同一资料；
5. Studio 对 Engine internal import 降为 0；
6. Persistence、event、process、cache 的 application ports 可使用内存替身；
7. Vue 组件不直接依赖通用 API，feature 之间不导入具体窗口；
8. 架构审计覆盖目标依赖方向，债务低于新阈值且不靠放宽 baseline；
9. 全量 Python、Vue、Pi Worker、桌面构建和连续文学 E2E 通过；
10. 项目可以在不理解全仓库的前提下，按模块公开接口完成新 Runtime、新 exporter、新 read model 或新前端 feature 的开发。

## 14. 最终判断

ArcVellum 当前不是架构失控的项目。它已经具备清晰的 Engine/Studio 单向边界、强 TaskPackage/Gate、成熟测试和多个优秀接口化样板，因此适合继续做模块化收敛，不需要推倒重写。

但它也还不是“所有模块都可以只面向接口独立开发”的系统。最关键的下一步不是继续增加目录，而是统一组合根、收窄 Engine public API、建立 Runtime/Provider ports、把 Prompt 编译成文学 IR，并让前端 feature 通过稳定 client 合同工作。完成 M0-M6 后，项目才可以合理宣称主要开发路径已支持模块化、面向接口和独立测试；M7-M8 则负责偿还热点债务并建立安全扩展生态。
