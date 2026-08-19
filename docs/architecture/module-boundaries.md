# ArcVellum 模块边界与渐进拆分准则

> v0.99 的统一接口化差距、完整模块清单和分批实施路线见
> `docs/roadmap/arcvellum-v0.99-modular-interface-development-plan.md`。本文继续记录已经落地的
> 模块所有权与拆分准则，不把规划中的目标接口视为现状。
> 当前机器生成的目录所有权摘要见 `docs/architecture/generated-module-map.md`。

> 本文服务于 Studio 维护者。普通创作 Agent 不应把本文件当作操作入口；正式执行仍由 `task-next → task-open → task-submit → task-complete` 的任务包驱动。

v0.96 - v1.0 的功能扩展必须同时遵守本文件与[统一工程实施方案](../roadmap/arcvellum-v0.96-v1.0-integrated-engineering-implementation-plan.md)。统一方案决定新增模块和施工顺序，本文件继续拥有依赖方向、compatibility facade 和目录归位纪律；任何产品路线不得以功能需要为由绕过这些边界。

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

Project Archaeology 的确定性源文本层位于 `src/literary_engineering_studio_engine/literary/ingest/`：

- `contracts.py` 拥有 `SourceDocument`、`SourceRange`、`SourceSegment`、`SourceEvidenceRef` 和 `SourceChunk`；
- `readers/` 只读取 TXT、Markdown 与 DOCX 的正文、标题层级、段落样式和脚注，不推断人物、事件或 Canon；
- `segmentation.py` 只把可靠边界投影为卷、章、节、段落、脚注和语义 chunk；
- `evidence.py` 建立并验证 source/range/hash/extractor/confidence 证据图；
- `importer.py` 负责不可变原文保全、staging/backup 事务和中断恢复；
- `reconstruction.py` 只聚合 chunk 产物并建立 fan-in revision，不执行别名语义合并；
- `reconstruction_contracts.py`、`domain_review.py` 约束全书身份解析、候选项目和五领域审查，保留未决身份、冲突和模式差异；
- `materialization_records.py` 只从通过审查的重建结果构造 Archive 候选记录，`materialization_storage.py` 只负责可回滚磁盘事务，`materialization.py` 负责编排二者；
- `provenance.py` 在共享 Archive promotion Gate 前重新验证来源、aggregate、identity、reconstruction 与 review revision；来源变化后的旧候选不得晋升；
- `projects/source_ingest.py` 继续作为兼容 facade，组装候选输出与平台 Agent sidecar，但不复制 reader、分段或证据算法。

`source-ingest/v1` 继续可读；新导入写 `source-ingest/v2`。v2 正式 Gate 必须验证原始文件与提取文本 hash、range/segment/evidence 对应关系、chunk 引用、导入 revision 和项目相对路径。Agent 只读取 task package 明确列出的项目身份、manifest、evidence index 和 chunks；所有反推结论仍只写候选区。

v2 的正式顺序为 chunk extraction → deterministic fan-in → identity resolution → candidate reconstruction → five-domain review → deterministic materialization。`analysis` 模式在通过 analysis-only review 后结束，不物化可晋升资产；其余模式也只能进入已注册的 Archive candidate 目录，继续复用独立 review、当前内容批准和原子 promotion。

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

### Runtime Capability 与 Resource Boundary

`src/literary_engineering_studio/runtime/capabilities/` 是受控能力的唯一实现边界：

- `contracts.py` 定义稳定能力 ID、Capability Manifest、请求与结果协议；
- `policy.py` 只根据当前 `TaskPackage`、Agent role、route 和显式 policy 派生权限；
- `registry.py` 使用显式 handler 注册，不允许动态 import 任意工具；
- `broker.py` 负责授权、参数/路径/网络边界、结果限额、artifact 与摘要事件；
- `audit.py` 只保存参数摘要、结果 hash、耗时和错误码，不保存正文、密钥或完整工具结果；
- `handlers/` 只实现声明式能力，不得出现通用 Shell、任意文件读写或不受控网络。

`runtime/execution_boundaries.py` 只负责把 Capability Manifest 与 `ResourceClaim`
装配到每次 Worker run、`_task/` 控制副本和 `TASK_CONTEXT.json`。它不选择任务，
不调用 Agent，不解释文学 route，也不把运行合同写进正式作品项目。

`src/literary_engineering_studio/runtime/resources/` 只拥有：

- `ResourceClaim` 合同；
- 项目内读写集、全局 barrier 与网络等级的确定性冲突判断；
- 从正式任务包派生资源声明的兼容投影。

任务依赖与动态顺序继续归 `orchestration/`；持久化锁、lease 和恢复继续复用
`JobStore`。不同场景的不同正文路径不会仅因同属 `drafts/scenes/` 被强制互斥；
是否可以并发必须同时满足 DAG 依赖、读写冲突和文学阶段 barrier。

`runtimes/base.py::AgentRunnerCapabilities` 保留所有旧字段，并增加版本、上下文窗口、
tool call、取消、本地执行和能力 ID 投影。Adapter 仍只执行任务，不理解文学 route。
Capability Broker 的结构化调用通道由 W6 编排/Runtime 接入；未提供通道的外部 Runner
不得用 Shell、网络或目录遍历模拟受控能力。

### Adaptive Orchestration Boundary

自适应编排遵守 [ADR-001](adr-001-adaptive-plans-are-future-intent.md)：计划属于
`Future Intent`，不得成为 Canon、当前人物状态、历史正文或任务完成事实。

`src/literary_engineering_studio_engine/orchestration/` 是只读协议边界：

- `task_catalog.py` 拥有可编排节点枚举、正式 route/task type 绑定和角色/资源模板；
- `gate_catalog.py` 拥有稳定 Gate ID 与基于风险的机器注入规则；
- `route_macros.py` 投影现有固定 route 顺序；
- Engine 不调用 Planner、Runtime 或 Studio persistence。

`src/literary_engineering_studio/orchestration/` 是 Studio 计划域：

- 只消费 Engine catalog 和正式 workflow state；
- 生成候选计划、Lint、CompiledTaskGraph、Simulation 与安全投影；
- 不直接调用 route 实现，不拥有 task lifecycle，不直接写正式项目事实；
- Scheduler 只能通过既有 `AgentWorker` 运行 Engine 已签发的 task package。

旧 `tasking/orchestration.py` 已迁往
`platforms/orchestration_blueprint.py`；旧路径只是兼容 facade。静态 LangGraph/Dify
蓝图不是运行时计划，新的 Studio 编排实现不得依赖该 facade。

配置中的自适应 feature 默认关闭。关闭时 `effective_mode` 必须为 `fixed`，即使配置里
残留其他 mode，也不能改变当前 Autopilot 行为。AO-0 至 AO-2 期间禁止直接开放
`assisted`、`supervised_adaptive` 或 `full_adaptive`。

AO-1 合同进一步固定：

- `contracts.py` 只拥有不可变计划 DTO、枚举与 JSON-safe 投影；
- `candidate.py` 是模型候选输入边界，机器字段只会被删除并形成 warning，节点中的任意
  command/path 字段直接拒绝；
- `constitution.py` 是不可被模型候选覆盖的规则源；
- `defaults.py` 只把现有 route 顺序包成 `fixed-formal-route.v1`，不自行创建任务节点；
- `protocol/orchestration/` 保存跨语言 schema 和宪法投影；运行时真相仍由版本化 Python
  contract 与 Engine catalog 验证。

默认计划使用空 `task_nodes` 加 machine-owned route macro 表达兼容行为。这是有意设计：
它把每一步继续交给现有 Task Registry 动态领取，避免把当前 route 内部状态复制成静态
DAG。AO-2 Compiler 只会把显式自适应节点编译为绑定；默认 macro 仍沿用正式 lifecycle。

AO-2 的确定性前置层进一步固定：

- `normalizer.py` 只把候选转换为机器拥有的正式计划：归一 ID/枚举、绑定 revision 与项目
  fingerprint、压缩 Freedom Budget，并重新注入 Gate；它不读写项目、不调用模型；
- `budget_policy.py` 单独拥有 Freedom Budget 数值域，避免设置、Lint 和未来 Compiler
  形成三份边界规则；
- `lint.py` 只做纯确定性验证，覆盖 DAG、scope、capability、Gate、文学前置链、
  Progress Contract、单 Writer 和 Freedom Budget；它不修复计划，也不签发任务；
- `gate_catalog.py` 是 Gate 的唯一机器来源。Candidate 中的 Gate 解释不能覆盖目录结果；
- Normalizer 与 Plan Lint 通过后仍不代表计划已执行或产物已晋升；Compiler、Simulator、
  审批和现有 task lifecycle 都是后续独立阶段。

AO-2 编译与模拟边界：

- `compiler_registry.py` 只把 Engine `FormalTaskCapability` 投影为 command-free
  `TaskBinding`，并按版本化 parameter schema 拒绝未知参数；
- `compiler.py` 只接受与当前 plan digest 精确匹配的 passing Lint receipt；输出 sealed
  `CompiledTaskGraph`，保留动态风险 Gate，并为 state/canon/release mutation 增加确定性
  串行边；
- fixed macro 编译结果保持空节点与原 route sequence。它不是静态复制 task-next，也不会
  在 Studio 中形成第二套任务状态；
- `simulator.py` 只消费显式 `FormalTaskObservation` 和 Runtime 拥有的 `ResourceClaim`，
  不自行搜索项目或推断路径；它预演 binding、scope、revision、资源冲突、产物消费和
  no-progress；
- graph digest、Plan Lint plan digest 和项目 fingerprint 是三道独立完整性检查；
- Compiler/Simulator 不创建 task、不调用 Worker、不改变 lifecycle、不批准 Gate、不写
  SQLite 或项目文件。未来 Scheduler 只能把 compiled binding 与 Engine 当前签发的正式
  task package 做匹配。

AO-2 持久化边界：

- `persistence/creative_plans.py` 只拥有计划身份、不可变 revision 索引和 activation 的
  optimistic concurrency；
- `orchestration/plan_events.py` 拥有固定 plan event enum/schema。Planner 流式 delta
  永远是 display-only，只有 `plan.candidate.completed` 才能成为 Lint 输入；
- `persistence/creative_plan_events.py` 只拥有 enum 验证后的 append-only plan event；
  display-only delta 拒绝持久化，计划节点不建立第二套可写运行状态，未来执行态必须投影
  Engine 正式 task receipt；
- `persistence/creative_plan_activation.py` 只协调已验证 revision 的 SQLite activation 与
  `active_plan.json` 投影；单项目通过唯一索引只允许一个 active plan；
- `persistence/creative_plan_artifacts.py` 在 revision 进入 ready 前验证全部索引文件真实
  存在且 hash 匹配；低层调用方不能凭空伪造 ready；
- SQLite 中的 candidate/plan/graph/lint/simulation/review 字段保存 path、hash、status
  摘要，不复制完整规划上下文；
- `orchestration/persistence.py` 协调便携项目审计文件与 SQLite 索引。完整 JSON 位于
  `workflow/orchestration/plans/{plan_id}/`，使用 Engine atomic metadata writer；
- revision 先以 digest 预留，再原子写文件，最后标记 ready；相同 revision/digest 可从
  reserved 状态恢复，不同 digest 在任何文件写入前冲突；
- 验证不只比较文件 hash，还绑定 candidate digest、normalized plan、Plan Lint receipt、
  compiled graph digest、simulation fingerprint 与 provenance 语义链；
- `shadow.py` 只量测 Normalize/Lint/Compile/Simulate，Lint 失败即停止。它不持久化、
  不执行、不激活，也没有 Autopilot 调用入口；
- AO-2 在 schema 12 建立计划索引；schema 13 增加 Context Ledger 元数据；schema 14
  增加 Worker Mutation Receipt 索引与 plan event session binding；当前 schema 15
  增加 execution context digest 与 visibility tier 索引，继续沿用
  JobStore migration backup。删除 Studio 编排/可观测索引不得删除或改变正式作品与项目
  审计文件。
- plan `status` 是机器字段，初始值固定为 `shadow`；只有通过完整审计协调器验证的 revision
  才能激活。激活使用显式 transaction，普通 SQL/event/commit 失败均恢复文件投影。

AO-3 Agent 协议边界：

- `orchestration/truth_partition.py` 拥有计划资料的事实分区；Future Intent 与
  Evidence/Opinion 永远不能单独满足正式 Gate；
- `orchestration/profiles.py` 拥有 Planner/Reviewer 的机器 profile。Profile 只能引用
  Runtime Capability ID，不拥有 Capability Handler、sandbox 或 writeback；
- `orchestration/agent_protocol.py` 只拥有结构化请求、模型 judgment candidate 和机器
  seal 后的 review receipt；Planner/Reviewer 不能通过输出声明正式路径、激活状态或
  reviewer 身份；
- `orchestration/context_builder.py` 负责规划资料选择、顺序、字符预算和精确 context
  装配；它不做持久化和会话追踪；
- `observability/context_ledger.py` 只拥有可观测 metadata 合同，不反向依赖
  `orchestration/`；`redaction.py` 统一生成有界安全预览；
- `runtime/context_selection.py` 是 prompt 与 Agent workspace 的唯一资料选择合同；
  `context_materialization.py` 把 prompt、task context、Capability/Resource 控制和 Ledger
  作为同一装配操作；`runtime/context_ledger.py` 只从装配后的可读视图生成证据；
- `persistence/context_ledgers.py` 只保存 metadata/hash/preview，完整来源文本不进入
  SQLite；schema 13 给 Agent session 增加精确 ledger ID/digest 关联；
- `worker_observability.py` 与 `observability/context_ledger_tracking.py` 以
  `sandbox.context_ready` 作为真实持久化边界。核心命令前的临时上下文不冒充模型已见
  上下文，同一 run 重装配后的资料变化产生新 identity；
- Planner 与 Reviewer session 必须分离。模型 judgment 只有经过 digest 绑定和机器
  sealing 后才是 orchestration review evidence，仍不能自行激活计划。
- `observability/mutation_receipts.py` 与 `change_groups.py` 只拥有机器回执和聚合合同；
  Worker 回执使用独立 `arcvellum/worker-mutation-receipt/v1`，不覆盖 Archive 已存在的
  owner mutation receipt 协议；
- `runtime/mutation_tracking.py` 只在 run control 根记录 candidate/preflight/preview/
  apply/rollback/promotion 事实；回执不进入 Agent workspace、expected outputs 或正式
  项目写回清单；
- `runtime/worker_writeback.py` 复用 Sandbox backup/atomic replace 和 Engine
  submit/complete/revert Gate，不取得第二套正式写回所有权；rollback 回执的
  `formal_effect` 固定为 `none`；
- `persistence/mutation_receipts.py` 只保存可追踪回执及 digest 索引。API Worker 与
  Autopilot 经现有 event/session 汇聚入口持久化，CLI 直跑仍保留 run-root 便携回执；
- `runtime/worker.py` 继续负责领取、准备、Runner 执行和恢复编排；结果 DTO、路径验证、
  run manifest 读取与写回生命周期分别归入小模块，禁止重新堆回单文件。

W6-4G 上下文与 Token 效率边界进一步固定：

- `runtime/context_budget.py` 只拥有任务预算分类、模式、不可变 DTO、shadow report 与
  `ContextBudgetExceeded`；它不选择资料、不组装 Prompt、不拥有 task lifecycle；
- `runtime/prompt_context.py` 只加载 Agent 已获许可的文本，执行完整文件级选择并生成
  report；不得半截断文件，也不得自行推断 Canon 或文学重要性；
- `runtime/context_materialization.py` 是预算、资料选择、Prompt、Task Context、
  Execution Boundary 与 Context Ledger 的单一装配入口；bounded 模式只有在任务包
  显式提供 `context_must_inline_paths` 后才可继续；
- `runtime/execution_context.py` 只拥有不可变 `ExecutionContextEnvelope`、四级资料
  枚举、摘要引用、内容身份与安全投影；它不能选择正式任务、扩大 Sandbox 权限或写回；
- `must_inline`、`exact_on_demand`、`summary_reference` 与 `excluded` 必须互斥。
  Prompt、`TASK_CONTEXT.json`、Run Manifest 和 Context Ledger 必须绑定同一 envelope
  digest；模型实际可见层级与 SQLite ledger tier 必须一致；
- `runtime/context_selection.py` 拥有 Agent 可见资料和操作手册排除策略；
  `runtime/task_program.py` 只能消费信封并渲染程序，不能重新建立第二套 source/reference
  选择；
- `routes/scene/context_contract.py` 只声明正文生成、精确审查和语义修订任务族的文学
  mandatory 资料；`tasking/context_contract.py` 只做 Engine 侧协议规范化，
  `protocols/task_context.py` 由 Studio 独立验证消费端合同，三者不得拥有预算或 Runtime
  配置；
- `literary/review/context_evidence.py` 只生成 digest-bound 候选审查紧凑证据；
  `protocols/review_context.py` 只在 Studio 侧独立验证该证据和任务声明，二者不得相互
  导入。完整审查 sidecar 保持 CLI/Engine 所有并留在授权 workspace，不能被紧凑证据
  替代或删除；
- `context_exact_on_demand_paths` 是正式任务合同而非 Runtime 猜测；它与
  `context_must_inline_paths` 必须互斥并共同进入任务指纹。只有 bounded 模式按该声明
  延迟首轮内联，off/shadow 必须保持兼容行为；
- `observability/throughput_aggregation.py` 只消费事件并维护临时聚合状态，
  `throughput_facts.py` 只计算 Token/context/attribution 数值，
  `throughput_metrics.py` 只输出用户安全的只读投影；
- throughput projection 可暴露计数、digest、task/scene/role/model attribution，
  不能暴露 Prompt、正文、推理、凭证或绝对路径；
- `runtime/repair_context.py` 只把 deterministic preflight issue 映射为同 session
  的有界 Repair Context，拥有 issue identity、目标选择、片段预算和已通过输出保护；
  它不能判定文学质量、扩大 expected outputs 或直接写回正式项目；
- `runtime/repair_rendering.py` 只渲染有界修复提示，`runtime/repair_snapshots.py`
  只保存和恢复 run-local protected outputs；两者都不能读取正式项目权限之外的资料；
- `runtime/sandbox_hygiene.py` 只恢复可由 staged baseline 与 control workspace
  digest 证明的非输出改动。无法证明可恢复的路径必须继续由 sandbox preflight
  fail closed，不能把“自动清理”变成权限豁免；
- `runtimes/opencode_repair.py` 只拥有 transport-level 同 session repair loop。
  TaskPackage、Sandbox、preflight、Gate 和 writeback 所有权继续留在 Worker；
- `runtime/context_rollout.py` 只消费请求模式、Engine contract status 和配置白名单，
  输出带稳定 policy digest 的灰度决策；它不选择资料、修改 task 或拥有 writeback。
  `off` 不得被覆盖，显式 bounded 遇非 `bounded-ready` 合同必须 fail closed；
- `runtime/context_ab.py` 和 `context_ab_reporting.py` 只在临时项目副本中组合正式
  Worker 生命周期与安全观测投影。每一实验臂必须独占并关闭 RuntimePool /
  ProcessManager，不得把临时产物直接复制回正式项目；
- `runtime/context_access_policy.py` 只解释 protected output 与 Execution Context
  tier 的读取义务；`runtime/context_access.py` 只从完成消息投影脱敏读取计数。两者
  都不能选择文学资料、修改 task contract 或保存 Prompt、正文、工具输出和绝对路径；
- `runtime/context_ab_suite.py` 与 `context_ab_suite_facts.py` 只聚合既有安全 A/B
  报告并计算退出事实；`runtime/context_rollout_drill.py` 只验证策略切换和合同不变，
  均不能执行 Worker、复制 preflight 或写正式项目；
- `preflight/scene_review_metadata.py` 只绑定候选审查的 task-owned 机械身份，不得
  修改 candidate digest、Agent conclusion、文学证据、问题或修订动作；
- `budget-shadow` 不改变旧 180000 字符执行上限。四级资料选择、
  `ExecutionContextEnvelope`、首批高成本场景任务合同、candidate-review 多样本真实
  A/B 与 rollback 已建立退出证据；生产默认仍为 shadow，灰度开关仍关闭，避免升级时
  静默改变既有用户配置。其他任务族仍是 shadow-ready，不得从 candidate-review 的
  结果推断其已具备 bounded 生产资格。

W6-5B Active Plan 生产激活边界进一步固定：

- `orchestration/active_plan.py` 是生产 active-plan 的唯一读取入口；它验证项目投影、
  SQLite active revision、不可变审计文件、authorization、normalized plan、compiled
  graph 和 planning fingerprint，返回已经验证的不可变值；
- `orchestration/activation.py` 只协调显式 assisted activation，
  `persistence/creative_plan_authorization.py` 只验证并记录授权；两者都不能创建 task、
  调用 Worker 或写正式文学资产；
- `orchestration/project_fingerprint.py` 只哈希规划事实，排除候选、patch、state patch
  和 run 产物；不能把执行产物纳入后造成计划自我失效，也不能排除 Canon、人物、场景
  和正式规划事实；
- `runtime/worker.py` 只在 Engine 已签发正式 task 后附加已验证的 scene plan binding；
  task ID、task type、expected outputs 和 formal lifecycle 不可被替换；
- `runtime/task_snapshot.py` 是 run-scoped bound task 的唯一冻结和重载入口；
  `runtime/run_manifest_factory.py` 只组装 manifest。Recovery、preflight、approval 和
  writeback 禁止重新读取可变的项目 task JSON；
- `observability/context_ledger.py` 和 `runtime/mutation_tracking.py` 只记录同一
  plan/revision/node 身份，不把计划意图冒充成 task completion 或 formal effect；
- 缺少有效 active plan 时只能发出可观察的 fixed fallback；active projection、审计
  文件或 snapshot 被篡改时必须 fail closed，不能以回退掩盖完整性错误；
- Scene 节点绑定继续复用 Engine Capability/Gate Catalog。Revision、promotion、
  state/canon approval/apply 和 release 的正式效果仍归原 Engine lifecycle；
- W6-5B 不包含 Scheduler、Execution Bundle、Rolling Horizon、跨场景并发或并发正式
  写回。这些只能在后续阶段复用上述证据链增量实现。

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

Project Archaeology 的 Studio 边界位于：

- `application/archaeology/contracts.py`：传输无关的上传、模式、权利声明和大小限制；
- `application/archaeology/import_service.py`：只负责把上传内容交给 Engine 的原子 source-ingest 事务；
- `application/archaeology/projection.py`：把 Engine workflow、证据、冲突、重建和候选物化结果投影为不泄露绝对路径的用户读模型；
- `application/archaeology/service.py`：面向 API 的用例组合，不复制 Engine route 或 Archive Gate；
- `api/routers/archaeology.py`：只处理 HTTP DTO、错误码和项目根解析；
- `api/dependencies.py`：组装 Archaeology/Style 应用依赖，避免 `create_app()` 膨胀。

Archaeology API 不得直接写重建 JSON、完成回执或正式资产。导入后的全部语义工作继续由
`source-ingest` 状态机与受控 Worker 领取；候选晋升继续进入共享 Archive 生命周期。

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
