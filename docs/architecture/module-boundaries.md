# ArcVellum 模块边界与渐进拆分准则

> 本文服务于 Studio 维护者。普通创作 Agent 不应把本文件当作操作入口；正式执行仍由 `task-next → task-open → task-submit → task-complete` 的任务包驱动。

## 原则

模块拆分的目标不是压低文件行数，而是把可独立验证的职责放到明确边界中。每次拆分必须同时满足：

1. 外部 CLI、HTTP 路由、任务 JSON 和现有项目文件格式不变。
2. 拆分前后有 characterization test，至少锁住调用入口和关键输出。
3. 正式文学顺序、门禁和写回原子性不迁移到 Studio UI 或 Agent 自觉。
4. 不形成 Engine → Studio 的反向依赖；Studio 可以调用 Embedded Engine，Engine 不得导入 Studio。
5. 不能为了“干净”一次移动所有 route；每个小批次要能单独运行全量测试。

## 已落地边界

### Desktop Sidecar Protocol

`src/literary_engineering_studio/sidecar_protocol.py` 负责：

- loopback bind 判定；
- 非本地绑定的 token 要求；
- `--port 0` 的 OS 分配端口发现；
- nonce-bound ready-file 的原子写入；
- Uvicorn sidecar 的启动等待。

`cli.py` 保留 `_is_loopback_host`、`_validate_serve_binding`、`_write_ready_file` 等兼容导出，避免已有测试、脚本和冻结端调用断裂。相关验收：`tests/test_cli_security.py`、`tests/test_sidecar_ready_file.py`。

### Studio Read Model Composition

`src/literary_engineering_studio/api_read_models.py` 的 `ProjectReadModels` 负责 Dashboard、Library、Reader、Progress、Delivery 与 Workspace 的同一 revision/cache 语义。

`api_server.py` 继续只负责：认证、路由、写操作、SSE 端点和应用生命周期。Dashboard builder 以延迟绑定方式传入，保留诊断和测试替换点。相关验收：`tests/test_api_server.py`、`tests/test_read_model_cache.py`、`tests/test_api_route_surface.py`。

### Formal Task Package Contract

`src/literary_engineering_studio_engine/task_package_contract.py` 负责：

- task contract revision 与 task type execution policy；
- executable contract fingerprint；
- prompt asset 的可执行投影；
- output ownership / approval policy；
- 对人类可读的任务 Markdown。

`task_registry.py` 保留 `_enrich_task_payload` 和 `_render_task_markdown` 兼容 facade；正式 route 蓝图和门禁由各自 route 模块拥有。相关验收：`tests/test_task_contract_transport.py`、`tests/test_task_contract_audit.py`、`tests/test_semantic_task_contracts.py`。

### Task Storage and Event Ledger

`src/literary_engineering_studio_engine/task_paths.py` 负责：

- task/submission/sidecar/event 的稳定相对路径；
- task identity 与路径规范化；
- 正式任务 JSON 的 schema 识别；
- append-only event ledger 的读写与人类可读渲染。

它不选择 route，也不执行文学 gate。Registry、CLI 和后续 `task_lifecycle.py` 只通过该模块读取或写入任务基础设施。相关验收：`tests/test_task_paths.py`、`tests/test_task_contract_transport.py`、`tests/test_task_submission_revert.py`。

### Task Lifecycle

`src/literary_engineering_studio_engine/task_lifecycle.py` 现在负责 route-neutral 的 `issue/open/submit/complete/revert/advance/events` 生命周期。它只接收 `LifecycleServices` 注入的 route definition、workflow payload、task contract renderer、Gate、completion marker 与 workflow state builder；因此不会反向 import route blueprint 或 Studio runtime。

`task_registry.py` 保留同名 public facade，供 CLI、Worker 与既有测试继续调用。任务 JSON/Markdown、event ledger、提交回滚和正式 route 回归全部通过后，重复的 lifecycle body 已删除；Registry 不再保存第二套生命周期实现。相关验收：`tests/test_task_lifecycle_facade.py`、`tests/test_task_paths.py`、`tests/test_task_contract_transport.py`、`tests/test_task_submission_revert.py`。

### Route Work-item Selection

`src/literary_engineering_studio_engine/route_selection.py` 负责从派生 workflow state 选择当前工作项，不产生任务、不写文件、不定义门禁。

标识符匹配必须保持 exact；只有声明为目录路径的字段才允许 suffix 匹配。相关验收：`tests/test_route_selection.py`。

### Route Catalog

`src/literary_engineering_studio_engine/route_catalog.py` 仅连接每条正式 route 的 selector、task builder 与 gate validator；它不导入具体蓝图或生命周期实现。Registry 以显式 callback 注入已有 route 行为，因此迁移前后 CLI 的 route 名称、任务顺序和 validation 语义不变。相关验收：`tests/test_route_catalog.py`、`tests/test_route_selection.py`、`tests/test_task_contract_transport.py`。

### Source-Ingest Route

`src/literary_engineering_studio_engine/source_ingest_route.py` 负责 source-ingest 的 state blueprint、候选输出计算、source manifest / extraction completion / clean-review Gate，以及修订候选的哈希变化判定。

该 route 只写候选资产，不能直接覆写正式 Canon、人物或大纲。`task_registry.py` 仅在 Route Catalog 中注入该 route 的 builder 和 validator；原有 source-ingest 的重复实现已经删除。相关验收：`tests/test_source_ingest_route.py`、`tests/test_task_contract_transport.py`、`tests/test_worker_integration.py`。

### Longform-Planning Route

`src/literary_engineering_studio_engine/longform_planning_route.py` 负责长篇规划任务包、故事架构 Gate、字数预算/场景库存/章节义务的候选-审查链，以及物化前的保护性约束。其文学顺序必须保持为：story architecture → independent review → word budget → inventory → chapter obligations → reviewed materialization。

Route Catalog 已指向该模块，Registry 中原有长篇 blueprint 与 Gate 副本已经删除。相关验收：`tests/test_longform_planning_route.py`、`tests/test_longform_revision_loop.py`、`tests/test_story_architecture_contract.py`。

### Remaining Formal Routes

`style_engineering_route.py`、`asset_route.py`、`review_audit_route.py` 与 `export_release_route.py` 分别拥有文风挂载、角色/世界资产、Canon/委员会审查和交付发布的 task blueprint 与 Gate。每个模块保持其候选 SHA、独立审查、审批或发布回执的绑定；Registry 只在 Route Catalog 中注入 builder/validator。

`scene_development_route.py` 承载场景的 Context → RP → Branch → Composition → Prose → Review → Promotion → State/Canon/Continuity 顺序。Registry 重新导出少量历史私有名称，避免已安装的 Worker、CLI 脚本和测试在迁移期失效，但不再保存第二份场景实现。

### Workflow, Audit, CLI and Scene Payload Facades

`workflow_state.py`、`agent_task_status.py` 与 `cli.py` 现在均为稳定 facade：

- `workflow_state_common` 加七个 `workflow_state_<route>` calculator 只计算派生状态；
- `agent_task_inventory`、`route_audit_common`、`route_audit_<route>` 与 `agent_task_rendering` 分别扫描证据、评估 Gate、渲染审计；
- `cli_policy`、`cli_support`、`cli_parser` 与 command group 仅负责命令注册和分发；
- `scene_route_support`、`scene_route_blueprints`、`scene_route_gates` 分别处理路径/摘要、状态到任务蓝图、正式 Gate。

`cli_parser.py` 和 `scene_route_blueprints.py` 是有意保留的单职责规则表：前者不执行命令，后者不写文件或作 Gate 判断。除非先建立完整 command/blueprint fixture matrix，不得仅因行数继续切碎。

### Longform Budget, Library and Interaction Projections

`word_budget.py` 仅保留公共兼容入口；预算服务已按以下方向拆开：

- `word_budget_planning`：卷章场景分配公式；
- `word_budget_inventory`：大纲/scene 文件和正文库存扫描；
- `word_budget_contracts`：中文内容字符的场景门禁与正文达标计算；
- `word_budget_rendering`：报告与 Agent sidecar 任务文本；
- `word_budget_service`：一次完整预算构建的编排。

`project_library.py` 的只读资料投影位于 `project_library_{drafts,assets,story,continuity,common,service}`；`project_interaction.py` 则把低风险展示编辑、人工决定物化与原子存储分离到 `project_interaction_{editing,choices,common}`。这些模块不直接晋升正文或覆盖 Canon，仍由正式 CLI Gate 决定。

## 当前大文件的正确处理方式

### Studio 目录约定

Studio 顶层只保留应用装配、公共兼容 facade 和明确的跨领域服务。新拆出的实现不得继续平铺在 `literary_engineering_studio/` 下，而应归入下列领域包：

```text
literary_engineering_studio/
  persistence/   SQLite schema、事务、run/session/read state
  preflight/     sandbox 规范化与确定性 Gate
  automation/    Autopilot policy、progress、decision、execution support
  api/           FastAPI dependencies、routers、SSE adapters（后续迁移）
  runtime/       runtime adapters 与 worker orchestration（后续迁移）
```

顶层 `jobs.py`、`task_preflight.py`、`autopilot.py` 是兼容入口与运行编排点，不是新实现的投放位置。包内模块只能向下依赖通用 DTO/contract，不能反向 import API 或 UI。

### 拆分完成后的目录归位

模块拆分不是终点。新实现不能长期平铺在 Studio 或 Engine 包根。完成某领域的 characterization、迁移和回归后，按下列稳定目录归位；既有顶层模块保留为兼容 facade，直到明确的迁移版本结束。

```text
Studio
  api/            app factory、dependencies、models、SSE、routers
  application/    config/bootstrap/lifecycle/application info
  automation/     Autopilot policy、progress、decision support
  persistence/    SQLite state and transaction boundaries
  runtime/        worker、sandbox、writeback、recovery
  integrations/   external agent/CLI adapters and credentials
  projections/    read-only dashboard/library/reader/narrative projections
  advisor/        advisor sessions/personas/inbox
  observability/  agent and execution feeds

Engine
  tasking/        task contracts, lifecycle, paths and ledger
  routes/         route catalog and route blueprints/gates
  workflow/       derived state, audits and activity
  literary/       planning, scene, assets, style, review and export domains
  prompting/      prompt compilation and platform Agent task contracts
  api/            legacy Engine HTTP surface

Client
  app/            startup, routing, global session/theme/API state
  features/       orrery, workflow, reader, projects, settings, library, quality
  shared/         UI primitives, composables, styles and typed view contracts
```

详细迁移顺序、compatibility facade 策略和退出门禁见 `docs/roadmap/arcvellum-large-file-modularization-execution-plan.md` 的 7.5 节。禁止以目录美化为理由跨多个领域一次性移动文件；每批移动都必须保留旧 import 路径、更新打包规则，并通过对应运行时回归。

### `task_registry.py`

它现在只承载 lifecycle facade、route catalog 注入、workflow payload refresh 与极少量兼容导出；正式 route 的 blueprint/Gate 已全部迁出。`workflow_state.py`、`agent_task_status.py` 和 `cli.py` 也已经完成相应 facade 化。禁止把迁出的 route 实现重新复制回 Registry。

### Studio `api_server.py`

它仍是应用组装根。下一批只能按 endpoint family 提取 FastAPI routers，并通过依赖对象注入 `config/lifecycle/autopilot/ProjectReadModels`：

1. `/projects` 和 project metadata；
2. `/workflow`、human choices 与 activity；
3. `/worker`、`/autopilot`、agent observability；
4. `/reader`、`/project/library`、`/project/delivery`；
5. `/settings`、model connections、application info。

任何 Router 提取前必须扩展 `tests/test_api_route_surface.py`，并保留身份认证 middleware 只在应用根注册一次。

### Engine `api_server.py`

Engine 的 legacy HTTP adapter 也已经完成同样的端点族拆分。顶层
`literary_engineering_studio_engine.api_server.create_app` 只创建应用并挂载
router；它继续 re-export 历史 request DTO 和少量私有兼容 helper。实现位于
`literary_engineering_studio_engine/api/`：

- `models`：legacy workflow client 的 request DTO；
- `common`：token、allowed-root、相对路径和静态资源策略；
- `routers/application`、`style_lab`、`projects`、`workflow`、`assets`、`agents`：互不重复注册路径的 endpoint family；
- `routers/agents` 同时拥有 director conversation 的新项目解析、用户可见过滤和响应投影，避免这些展示规则回流进 app factory。

验证入口为 `tests/test_engine_api_route_surface.py`。它以 OpenAPI path set 锁住 legacy API；不要只扫描 FastAPI 的顶层 `app.routes`，因为新版 FastAPI 的 included router 可能是 lazy wrapper。

### Engine `tasking/`、`workflow/`、`literary/planning/` 与 `projections/library/`

下列目录已经完成物理归位，根目录旧文件均只保留 import-compatible facade：

- `tasking/paths`、`lifecycle`、`package_contract`、`semantic_contracts`、`contract_audit`：任务身份、事件账本、可执行任务信封与语义证据；
- `workflow/state*`、`activity`、`dashboard`：跨 route 的派生态、总控活动投影和仪表盘；根目录 legacy module 使用 module alias，使 monkeypatch 仍作用在真实实现；
- `literary/planning/common`、`allocation`、`inventory`、`contracts`、`rendering`、`service`：长篇字数预算与章节/场景义务；
- `projections/library/common`、`assets`、`drafts`、`story`、`continuity`、`service`：只读项目档案，不得执行 promotion、approval 或 writeback。

兼容 facade 需要保留私有符号的可导入性，因为已有测试和第三方脚本会导入
`_read`、`task_json_path`、`workflow_state_scene.candidate_review_gate` 等历史 helper 或 patch seam。新代码必须直接 import 领域目录，不能再以
compatibility facade 作为内部依赖。

### `jobs.py`

`JobStore` 仍是 SQLite connection、migration、核心 job/lock/resource 事务和 job event 的唯一宿主；它不再混入自动创作、顾问、Agent 会话或阅读器状态。

### 顶层兼容 Facade 纪律

包根目录中的旧模块名不再是新实现的默认投放位置。它们只承担三种责任之一：

1. 公开 package/CLI/API 入口；
2. 有迁移窗口的 import-compatible facade；
3. 极少量跨领域 contract 或基础协议。

所有真实实现必须归入对应领域目录：Engine 使用 `tasking/`、`routes/`、`workflow/`、`director/`、`literary/`、`prompting/`、`projections/`、`foundation/`；Studio 使用 `application/`、`persistence/`、`runtime/`、`integrations/`、`projections/`、`advisor/`、`observability/`。顶层平铺文件的完整迁移清单、顺序和风险见 [arcvellum-large-file-modularization-execution-plan.md](../roadmap/arcvellum-large-file-modularization-execution-plan.md)。

compatibility facade 不得成为新代码的依赖入口。新代码应直接 import 所属目录中的实现；只有 CLI、旧 API、外部脚本或测试 patch seam 可以通过 facade 访问旧路径。

- `persistence.primitives`：schema 常量、ID 校验、序列化和脱敏；
- `persistence.autopilot_runs`：run、lease、policy snapshot、delegated decision 与 autopilot event；
- `persistence.sessions`：顾问对话、Agent session、通知收件箱、delegation policy 和阅读位置/书签；
- `jobs`：公开 `JobStore` facade，持有连接/锁协议、迁移、job lifecycle、project lock/resource 和 job event。

拆分前已增加 job create、claim event、project lock 三条失败注入测试，证明 SQLite context manager 的 rollback 不会留下半写入行。后续若继续抽取 job core 查询或 event store，必须保持这些写路径、lease 和 migration 都只经过同一连接/锁协议。

### `task_preflight.py`

顶层 facade 固定保留 `PreflightIssue`、`PreflightResult`、`canonicalize_task_outputs` 与 `validate_task_outputs`。具体实现位于 `preflight/`：

- `common`：DTO、completion evidence、通用 JSON 与 review conclusion 检查；
- `canonicalization`：只补 task-owned deterministic metadata；
- `scene`、`assets`、`review`：各自 route 的 Gate，只向统一 issue list 追加结果。

规范化和验证不能互相绕过：任何新 Gate 都要由 facade 纳入固定顺序，并用 Worker sandbox 真实链路覆盖。

### `autopilot.py`

`autopilot.py` 仍持有串行控制器、授权边界与 no-progress stop。`automation/policy` 承载模式、额度规范化、revision 识别和委托判断；`automation/support` 承载无状态的进度 fingerprint、资产依赖检查、Steward 调用兼容、决定物化和时间工具。保留顶层 `ROUTE_ORDER` 仅用于 controller 的可测试运行顺序，不能让 support 反向依赖 Worker 或 API。

## 不可破坏的依赖方向

```text
Vue/Tauri
   -> Studio API / Worker / Read Models
      -> CoreBridge
         -> Embedded Engine CLI / modules
```

- 前端只消费 API read models，不解析 sidecar Markdown 作为状态。
- Studio Worker 只在 sandbox 中调用 task package，不能重写 Engine gate。
- Embedded Engine 不能读取 Studio credential、runtime 或桌面窗口状态。

## 拆分提交检查表

1. 新模块有一句话职责说明和最小公开 API。
2. 旧入口保留 facade 或明确的迁移版本。
3. 新旧调用输出有测试。
4. `python -m unittest discover -s tests -v`、`python -m compileall -q src`、`git diff --check` 通过。
5. 若影响 API：运行 client tests/build 与 API route surface test。
6. 若影响 sidecar：运行 ready-file integration 和 `cargo check --locked`。
