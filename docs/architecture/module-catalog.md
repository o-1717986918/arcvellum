# ArcVellum 模块目录

> 状态：v0.99 M7 事实文档
> 适用对象：维护者、代码 Agent、Runtime/Exporter/Read Model/前端 Feature 开发者
> 机器生成的目录计数见 [generated-module-map.md](generated-module-map.md)，更细的历史拆分说明见
> [module-boundaries.md](module-boundaries.md)。本文只回答“需求归谁、从哪里进入、不能越过什么边界”。
> 已知报错或用户症状请先查 [故障反查与模块定位](troubleshooting-module-index.md)。

## 1. 如何使用本目录

开始改代码前，先定位唯一主模块，再读取该模块的公开入口和测试。不要把仓库文件搜索结果当作接口。

1. 用户行为、应用生命周期或用例编排：从 Studio `application/` 开始。
2. 文学事实、正式路线、Gate、TaskPackage、晋升和导出：从 Engine `public/` 开始。
3. Agent 进程、沙箱、上下文、能力和写回：从 Studio `runtime/` 与 `runtimes/` 开始。
4. SQLite、事件、缓存或进程：先看 `application/*_ports.py`，再看 adapter。
5. HTTP/SSE：从 Studio `api/routers/` 进入，但业务逻辑必须下沉到 application service。
6. Vue：从对应 `client/src/features/<feature>/services/*Client.ts` 进入。
7. 不确定归属时，先填写 [Agent 面向接口开发标准](agent-interface-development-standard.md) 中的 Module Change Packet。

## 2. 全局依赖方向

```text
Vue feature -> feature client / command bus -> HTTP/SSE adapter
                                             -> Studio application use case
                                             -> Studio-owned port
                                             -> infrastructure/runtime/persistence adapter

Studio application -> Engine public API -> Engine domain/tasking/workflow

Engine -> Standard library / Engine-owned domain contracts
Engine -X-> Studio, FastAPI, Vue, Provider SDK, Agent process
```

唯一应用装配入口是 `src/literary_engineering_studio/application/container.py::build_application_container`。
默认 adapter 只在 `src/literary_engineering_studio/infrastructure/composition.py` 选择。禁止新增第二个组合根或 service locator。

## 3. Engine 模块

Engine 是正式文学工程真相的所有者。Studio 只能通过 `src/literary_engineering_studio_engine/public/` 消费 Engine 能力。

| 模块 | 所有权与职责 | 稳定入口 | 允许依赖 | 禁止事项 | 关键验证 |
|---|---|---|---|---|---|
| `foundation/` | 原子写入、资源路径、文本清理、hash 等无业务方向基础设施 | package exports；跨包时优先由 `public/*` 重导出 | 标准库 | Studio、Provider、HTTP、route policy | `test_engine_public_api.py`、原子 I/O 相关测试 |
| `tasking/` | TaskPackage、semantic artifact、agent sidecar、生命周期和 Gate 通用合同 | `public/tasking.py` | foundation、route-neutral contract | 执行 Agent、Studio job、Provider 调用 | `test_task_contract_transport.py`、`test_task_lifecycle_facade.py` |
| `routes/` | 正式 route 目录、任务顺序、route-specific Gate | `routes/catalog.py`；Studio 消费时用 `public/orchestration.py`/`public/workflow.py` | tasking、literary services | Studio 生命周期、Runtime adapter | `test_route_catalog.py`、各 route 测试 |
| `workflow/` | 从项目事实派生 workflow state、dashboard 和审计 | `public/workflow.py` | tasking、routes、项目事实 | 调 Agent、写正式产物 | `test_scene_workflow_order.py`、dashboard/audit 测试 |
| `literary/` | Canon、人物、场景、规划、文风、审查、状态、连续性、导出，以及授权来源合同和只读原文投影 | `public/literary.py`、`public/projections.py` | foundation、task contracts | FastAPI、SDK、Studio persistence、下载受版权保护的正文 | `test_scene_*`、`test_longform_*`、`test_style_*`、`test_asset_*`、`test_authorized_source_contract.py` |
| `prompting/` | 版本化 Prompt Asset、schema 和 payload validation | `public/prompting.py` | Engine 文学合同 | Provider transport、会话复用 | `test_prompt_compiler.py`、`test_prompt_program_v3.py` |
| `orchestration/` | 只读 FormalTask/Gate/route macro 目录 | `public/orchestration.py` | task/gate catalogs | Planner 执行、计划持久化、Worker | `tests/orchestration/test_ao0_foundation.py`、默认路线等价测试 |
| `projections/` | 面向读取的正文、计数和展示投影 | `public/projections.py` | 正式项目事实 | promotion、writeback、隐藏修复 | projection/reader/API 测试 |
| `projects/` | 初始化、现有作品导入、授权单篇演示形式化、项目级原子文件操作 | `public/projects.py` | foundation、literary ingest | Studio data root、UI 生命周期、伪造 Agent 创作或晋升历史 | project init/source ingest、`test_authorized_source_contract.py` |
| `command_line/` | Engine CLI 解析与命令分发 adapter | `command_line/main.py` | Engine public/domain services | 新文学规则、第二套 Gate | CLI/route surface 测试 |
| `director/` | 创作总监的正式任务模板和选择逻辑 | 现有 director facade | Engine contracts | Provider HTTP、Studio 会话 | creative director 测试 |

### Engine `public/*` 的使用规则

- `public/literary.py`：Studio 所需的文学验证、文风、导出和资产能力。
- `public/tasking.py`：签发任务、semantic artifact 和 completion marker。
- `public/workflow.py`：workflow state 与 dashboard。
- `public/orchestration.py`：只读能力/Gate/route macro 目录。
- `public/projects.py`：初始化和导入。
- `public/projections.py`：展示文本和计数。
- `public/prompting.py`：Prompt Asset 与结构化输出 schema。

新增 Studio 对 Engine 的需求时，先在相应 `public/*.py` 建最小重导出并补 public API 测试；不得直接 import Engine internal 目录。

## 4. Studio 应用与领域模块

| 模块 | 所有权与职责 | 稳定入口 | 允许依赖 | 禁止事项 | 关键验证 |
|---|---|---|---|---|---|
| `application/` | 用户用例、生命周期、项目管理、资产事务、文风挂载，以及授权演示包的安装、恢复和克隆 | `application/container.py`、具体 application service | application ports、Engine public API | FastAPI Request、SQLite row、Provider payload、解释或扩大授权范围 | `test_application_container.py`、application/service tests、`test_authorized_source_contract.py` |
| `application/ports.py` | 事件、缓存、进程、Runtime pool、执行协调器等替换边界 | `ApplicationPorts` | DTO、Protocol | adapter 构造、业务默认值 | `test_application_container.py`、composition tests |
| `application/persistence_ports.py` | job/autopilot/session/ledger/receipt/lease/plan/asset/event/UoW 合同 | `PersistencePorts` | DTO、Protocol | SQL、路径布局、文学决策 | `test_persistence_ports.py` |
| `automation/` | 自动创作 Campaign、授权窗口、推进与恢复 | `automation/controller.py`、`campaign_runtime.py` | application/runtime ports、Engine state | 重写 Engine Gate、隐式批准高风险事实 | `test_autopilot.py`、`tests/automation/*` |
| `orchestration/` | CreativeExecutionPlan、Plan Lint/Compile/Simulate/Review/Recovery | package services；Engine 目录从 `public/orchestration.py` 读取 | Engine public catalog、ports | 第二套 task lifecycle、直接写项目事实 | `tests/orchestration/*` |
| `advisor/` | 只读项目顾问、persona、会话、动作建议与通知 | `advisor/service.py`、answer contract | read models、Runtime port、session repository | 直接写项目、隐式执行任意命令 | advisor/inbox/persona tests |
| `preflight/` | 写回前确定性规范化与验证 | `preflight/task_preflight.py` facade | contracts、deterministic validators | 代替 Agent 作文学判断、偷偷修复失败产物 | preflight/worker writeback tests |
| `projections/` | Library、Archive、Orrery、Agent 会话、模型连接等只读模型 | projection service/facade | read ports、Engine public facts | promotion、task completion、请求时隐藏写入 | API/read-model/observability tests |
| `observability/` | session、context ledger、mutation receipt、telemetry、安全预览与 Creative Live 项目投影 | `observability/creative_live/*`、observability contracts/projectors | event/session ports | 正式 task mutation、保存秘密或隐藏推理正文 | `test_agent_observability.py`、`tests/observability/test_creative_live_*.py`、context ledger tests |

## 5. Runtime 与外部集成

| 模块 | 所有权与职责 | 稳定入口 | 允许依赖 | 禁止事项 | 关键验证 |
|---|---|---|---|---|---|
| `runtimes/` | Agent Runner SPI、descriptor/factory、adapter 注册 | `runtimes/base.py::AgentRuntimePort`、`runtimes/registry.py` | subprocess/SDK adapter、Runtime DTO | 文学 route 判断、项目正式写入 | `test_runtime_registry.py`、adapter contract tests |
| `runtime/` | Worker 执行、bundle、沙箱、上下文、写回、修复、恢复 | `runtime/worker.py` 与显式子模块 | Runtime port、ports、Engine public API | Provider-specific 分支散入 Worker、绕过 preflight | `test_worker_integration.py`、`tests/runtime/*` |
| `runtime/capabilities/` | 明确 allowlist 的受控工具能力 | manifest/policy/registry/broker | 当前 TaskPackage、显式 handlers | 通用 Shell、任意读写、动态 import | runtime capability contract tests |
| `runtime/resources/` | ResourceClaim 与读写/Barrier 冲突判断 | resource contracts/conflict functions | immutable DTO | task ordering、数据库 lease 实现 | `test_runtime_resources.py`、orchestration resource tests |
| `integrations/opencode/` | OpenCode 客户端、事件、池和会话 adapter | integration facade；由 Runtime descriptor 使用 | OpenCode protocol | 文学规则、直接项目写回 | OpenCode execution/pool/event tests |
| `integrations/pi_rpc/` | Studio 与内置 Pi Worker 的 JSON-RPC/framing | Pi RPC facade | framed transport、typed payload | 项目路径自由访问、Gate 判断 | `test_pi_rpc.py`、`test_pi_continuous_e2e.py` |
| `workers/pi-worker/` | 有界 Pi Agent Core 执行器，只消费任务包并产出 expected outputs | `src/main.ts`、`src/worker.ts` | Pi SDK、task contract | 正式项目访问、task lifecycle、subagent 写正文 | `npm run pi-worker:check`、Pi Worker Python integration tests |

### 新 Runtime 的正确扩展点

1. 实现 `AgentRuntimePort`；
2. 提供 `RuntimeDescriptor` factory；
3. 在应用组合时注册 descriptor；
4. 复用 Worker 的 TaskPackage、sandbox、preflight 和 writeback；
5. 通过统一 adapter contract suite。

不得为每个 Provider 建 Worker 子类，也不得在 Worker 中添加 `if provider == ...`。Provider 认证、stream event 和模型选择属于 adapter。

## 6. Persistence、Infrastructure 与 API

| 模块 | 所有权与职责 | 稳定入口 | 禁止事项 | 关键验证 |
|---|---|---|---|---|
| `persistence/` | SQLite/file adapter、事务、repository 实现 | `PersistencePorts` 的 adapter 组合 | 文学判断、UI DTO、隐式文件修复 | persistence/lease/time identity tests |
| `infrastructure/` | 默认 adapter 选择与应用 composition | `infrastructure/composition.py` | 新用例、第二组合根、全局可变 service | composition/application container tests |
| `api/` | FastAPI router、请求验证、SSE transport、response DTO | router factory + application container | 直接改项目文件、直接 import Engine internal | `test_api_route_surface.py`、`test_api_server.py` |
| `protocols/` | 跨进程/跨语言稳定 schema 资源 | versioned schema files | Python 对象序列化细节、未版本化变更 | contract/schema tests |

持久事件与实时事件是两个接口：`DurableEventStorePort` 记录可恢复事实，`LiveEventPublisherPort` 只负责在线通知。不得用 SSE 事件代替正式 receipt，也不得为展示请求产生隐藏写入。

## 7. Vue 客户端

跨 feature 调用只能经 feature client、共享只读合同或 `WorkspaceCommandBus`。组件不得直接使用 generic API transport。

| Feature | 稳定调用入口 | 主要职责 |
|---|---|---|
| `projects` | `services/projectsClient.ts` | 项目建立、选择、生命周期 |
| `workflow` | `services/workflowClient.ts` | 总控状态、推进、自动创作 |
| `strategy` | `services/strategyClient.ts` | 创作策略、节奏和计划 |
| `quality` | `services/qualityClient.ts` | Gate、审查、质量证据 |
| `advisor` | `services/advisorClient.ts` | 顾问对话、流式消息、动作卡 |
| `orrery` | `services/orreryClient.ts` | 星仪只读数据与交互命令；渲染拆在 camera/layout/curves/nodes/edges/background/animation |
| `archive` | `services/archiveClient.ts` | 资产档案、修订、候选晋升 |
| `archaeology` | `services/archaeologyClient.ts` | 已有作品导入与反推 |
| `style-atelier` | `services/styleAtelierClient.ts` | 作家语料、文风工程、挂载 |
| `delivery` | `services/deliveryClient.ts` | 交付就绪与导出 |
| `settings` | `services/settingsClient.ts` | Runtime、Provider、模型和应用设置 |
| `creative-live` | `services/creativeLiveClient.ts` | 候选产物、Agent 会话、审查证据、修订快照与项目级 SSE |

通用 transport 位于 `client/src/services/api.ts`；跨 feature 用户命令位于 `workspaceCommands.ts`。新增 feature 必须提供 mock client/fixture，并在 `client/src/testing/featureClients.contract.spec.ts` 或同等级合同测试中验证。

## 8. Desktop 与构建工具

| 模块 | 职责 | 稳定入口 | 禁止事项 | 验证 |
|---|---|---|---|---|
| `desktop/src-tauri/` | 桌面窗口、sidecar 生命周期、更新器、资源声明 | Tauri commands/config | 文学逻辑、Provider secrets 写入前端包 | desktop build、sidecar/bundle verify |
| `packaging/` | Python sidecar、Pi Worker、installer 和 provenance | PowerShell/Python build scripts | 引用开发机绝对路径、打包未验证二进制 | `desktop:verify-*`、生产打包 |
| `scripts/` | 架构、版本、OpenAPI、模块图和构建验证 | 每个脚本 CLI | 成为运行时业务入口 | 对应 script tests/check mode |
| `tests/` | 合同、单元、集成、连续 E2E 与架构棘轮 | unittest/vitest/playwright | 使用生产秘密、伪造真实 E2E 通过 | 全量测试矩阵 |

## 9. 受控遗留债务

M7 结束时机器审计为 16 个超长文件、120 个复杂函数、0 forbidden dependency、0 import cycle。16/120 是只减不增的历史债务，不是新代码额度。

- 新文件默认不超过 350 行；超过 450 行必须先写 ADR。
- 新函数默认不超过 60 行、复杂度不超过 12。
- 规则表、schema 目录和声明式蓝图不能仅为行数机械切碎。
- facade 只能转发、适配或稳定导出，不能保存第二套业务实现。

## 10. 最小验证索引

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest <本模块测试> -v
python -m compileall -q src
python scripts/architecture_audit.py
python scripts/generate_module_map.py --check
python -m literary_engineering_studio_engine prompt-registry-validate --json
git diff --check
```

跨模块、Runtime、Prompt、正式文学路线或前端行为变更，还必须执行 `AGENTS.md` 和 `CONTRIBUTING.md` 中的完整矩阵。
