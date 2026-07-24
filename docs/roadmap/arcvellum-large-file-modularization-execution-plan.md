# ArcVellum 大文件模块化拆分执行计划

> 文档性质：强指导性架构迁移计划。先完成本计划规定的基线和行为快照，再移动生产代码。
>
> 审阅时间：2026-07-24
>
> 当前分支：`feat/post-v094-spatial-reliability`
>
> 关联文件：`docs/architecture/module-boundaries.md`、`docs/roadmap/arcvellum-cli-literary-reliability-implementation-directive.md`、`docs/roadmap/arcvellum-remaining-source-directory-allocation-plan.md`

## 1. 目标与边界

本计划的目标不是把所有文件压到任意行数阈值之下，而是消除职责混杂、循环依赖、难以局部测试和一次小改动触发大面积回归的风险。拆分完成后，必须同时保持：

1. Studio 对普通用户仍是唯一产品入口，前端 API 路径和响应模型不变。
2. Embedded Engine 仍是文学状态机的唯一事实来源；Studio Worker 不复制或绕过 Gate。
3. 任务包、工作流事件、正式项目资产、CLI 命令及已有项目目录格式保持兼容。
4. 每次迁移有行为快照、聚焦测试和全量回归证据，不能以“文件可以 import”代替验收。
5. 不把一个巨型文件机械复制成几个彼此循环 import 的新巨型文件。

### 1.1 当前已完成的安全抽取

以下已落地，作为后续迁移的基础，不再回退：

- `literary_engineering_studio.sidecar_protocol`：桌面 sidecar ready-file、端口和 loopback 安全边界。
- `literary_engineering_studio.api_read_models`：revision-aware read model 组合。
- `literary_engineering_studio_engine.task_package_contract`：任务契约、输出所有权、提示词投影和 Markdown 渲染。
- `literary_engineering_studio_engine.task_paths`：任务、submission、事件账本和路径规范化。
- `literary_engineering_studio_engine.route_selection`：route 工作项选择。
- `literary_engineering_studio_engine.route_catalog`：route 的选择、构建和 Gate callback 装配。
- `literary_engineering_studio_engine.task_lifecycle`：route-neutral 的 issue/open/submit/complete/revert/advance/events 生命周期；Registry 仅注入 route 服务并保留公开 facade。
- `literary_engineering_studio_engine.{scene_development,longform_planning,source_ingest,style_engineering,asset,review_audit,export_release}_route`：七条正式 route 的 blueprint 与 Gate；Registry 不再保留第二套实现。

本计划最初建立时，`task_registry.py` 约 4,874 行。它已在本轮迁移中降为约 275 行的稳定 lifecycle/catalog facade；不得再以旧行数作为当前风险判断依据。

## 2. 统一迁移纪律

### 2.1 文件是否必须拆分的判定

同时满足任意两项时，列入本轮拆分目标：

- 超过 700 行且存在两个以上独立职责；
- 外部引用扇入高，修改经常影响无关功能；
- 同时承担 I/O、领域规则、序列化和 API/CLI 装配；
- 有明确可独立测试的子领域；
- 当前代码已出现重复 helper 或迁移遗留 facade。

单一领域但较长的文件可以先保留，例如纯文档渲染器或纯规则表；必须在本计划中说明理由，而不是被忽略。

### 2.2 每一次代码迁移的固定顺序

1. 对旧入口建立 characterization test：锁定公共函数、序列化输出、错误消息类别、文件副作用和调用顺序。
2. 新模块只接收最小依赖协议；不得 import 上层 API、CLI 或 Studio runtime。
3. 旧模块先保留薄 facade，保证外部 import 和 CLI 行为不变。
4. 跑该批次的聚焦测试、全量 Python 测试、`compileall`、`git diff --check`；影响前端时再跑 client test/build，影响桌面时再跑 Rust check。
5. 只有在快照和全量测试都通过后，才删除不可达 legacy body。

### 2.3 依赖方向

```text
Vue / Tauri
  -> Studio API routers / services / Worker
    -> CoreBridge
      -> Embedded Engine route state, task contract and literary domain modules
```

- Engine 不得 import Studio、FastAPI、Tauri、Vue 或 credential/runtime 状态。
- Route definition 只能组合 selector、blueprint builder 和 validator，不能实现文学 gate。
- API router 不得读取工作项目文件后自造状态；只调用 service/read model。
- UI 不得根据 sidecar Markdown 自行推断正式状态。

### 2.4 迁移交付物

每个模块批次必须产生：

- 明确的目标模块职责说明；
- 至少一个旧新等价测试或 fixture snapshot；
- 公开 facade 或迁移说明；
- 更新后的架构边界文档；
- 当前批次命令和结果写入 `docs/verification/cli-literary-reliability-progress.md`。

## 3. 全仓库盘点与决策

### 3.1 P0：状态机与正式任务内核，必须优先拆分

| 当前文件 | 约行数 | 混杂职责 | 目标模块与稳定 facade | 前置证据 |
|---|---:|---|---|---|
| `task_registry.py` | 4,874 | lifecycle、7 条 route blueprint、任务 payload、route gate、legacy bodies | `task_lifecycle.py`、`task_payloads.py`、`routes/{scene,longform,source_ingest,style,assets,review_audit,export_release}.py`、`route_gates/{...}.py`；保留 `task_registry` facade | task sequence、task JSON/MD snapshot、complete/revert 原子性 |
| `cli.py` | 2,561 | parser、70+ command handler、help、打印、参数读取 | `cli_groups/{formal,project,style,assets,review,export,diagnostics}.py`、`cli_parser.py`、`cli_output.py`；保留 `build_parser` / `main` | help surface、parser command matrix、代表命令 stdout/exit code |
| `workflow_state.py` | 1,893 | 7 routes 的 derived state、场景阶段、选择与 approval 解读 | `workflow_routes/{scene,longform,source_ingest,style,assets,review_audit,export_release}.py`、`workflow_steps.py`、`workflow_common.py`；保留 `build_workflow_state` | 每条 route 当前 step snapshot、scene stage ordering |
| `agent_task_status.py` | 1,785 | 任务扫描、7 条 route audit、scene audit、render | `task_inventory.py`、`route_audits/{scene,longform,assets,review,export}.py`、`audit_rendering.py` | route-audit JSON/Markdown fixture、debug waiver negative cases |

### 3.2 P1：Studio 服务与持久化边界，必须拆但不改变事务语义

| 当前文件 | 约行数 | 目标模块 | 特别约束 |
|---|---:|---|---|
| `literary_engineering_studio/api_server.py` | 1,658 | `api/{application,runners,advisor,autopilot,projects,worker,workflow,reader,narrative,delivery,style_lab}.py` 与 `api/dependencies.py` | 只在 app root 挂认证和 lifecycle；Router 通过明确 service container 注入 |
| `literary_engineering_studio_engine/api_server.py` | 1,599 | `engine_api/{config,style_lab,project,workflow,canon,agent,assets}.py` | 保持 legacy engine HTTP surface，不让其与 Studio API 相互 import |
| `jobs.py` | 620 + mixins | `job_primitives.py`、`job_autopilot.py`、`job_sessions.py`；后续再抽 `job_queries.py`、`job_events.py` | 已具备 create/claim/lock failure injection tests；核心写路径、migration 与 job event 仍留在 `JobStore` |
| `autopilot.py` | 924 | `autopilot_policy.py`、`autopilot_progress.py`、`autopilot_decision.py`、`autopilot_service.py` | 串行锁、授权边界、no-progress stop 语义必须完整快照 |
| `task_preflight.py` | 912 | `preflight/{common,scene,assets,review,source_ingest}.py` | 输入 canonicalization 与 validation 必须同批测试，避免只校验未经规范化的 payload |
| `sandbox.py` | 520 | `sandbox_staging.py`、`sandbox_writeback.py`、`sandbox_diff.py` | copy/rollback journal 必须保持原子、可恢复，先补失败注入测试 |
| `worker.py` | 573 | `worker_run.py`、`worker_recovery.py`；`AgentWorker` 暂作 facade | Worker 不吸收 Engine gate；只做 runtime、sandbox、writeback orchestration |

### 3.3 P1：文学领域内核，按领域凝聚力拆分

| 当前文件 | 约行数 | 拆分方案 | 保持为一个领域的部分 |
|---|---:|---|---|
| `director_agent.py` | 1,487 | `director/{conversation,tool_loop,decisioning,bootstrap,records}.py` | 对外保留 `run_director_turn`、`bootstrap_project_from_direction`、`build_director_status` |
| `word_budget.py` | 1,141 | `budget/{planning,scene_contract,inventory,rendering}.py` | 中文字数统计和预算公式集中在 `planning`，不散落至 route |
| `project_library.py` | 974 | `library/{drafts,assets,story,continuity,decisions,context_health,display}.py` | 单个 item DTO 及 key point 规范归入 `display` |
| `project_interaction.py` | 935 | `interaction/{editable_fields,human_choices,choice_materialization,notes}.py` | 人类选择写回必须保留原子 JSON/JSONL helper |
| `asset_workshop.py` | 921 | `assets/{candidates,review,promotion,rendering,context}.py` | promotion 的 approval 和 schema 规则不得被前端重复实现 |
| `scene_composer.py` | 899 | `composition/{facts,branch_input,beats,prose_seed,agent_task,rendering}.py` | composition digest 留在唯一入口，供下游精确绑定 |
| `platform_agent_tasks.py` | 875 | `agent_tasks/{scene,assets,canon,style,common}.py` | 所有 task markdown 统一使用 common 的 output contract 文字 |
| `candidate_promotion.py` | 864 | `promotion/{generation_gate,review_gate,revision_gate,writeback,rendering}.py` | candidate SHA/review binding 不可拆散 |
| `longform_audit.py` | 800 | `audits/{longform_scan,longform_graph,longform_rhythm,longform_rendering}.py` | 可保留单一 `build_longform_audit` facade |
| `style_lab.py` | 794 | `style/{library,source_ingest,learning,skill_build,mounting}.py` | 只处理合法来源与风格约束，不引入直接 LLM provider |
| `workflow_runner.py` | 755 | `runner/{scene,assets,chapter,artifacts,state_store}.py` | 这是诊断/兼容 runner，不能成为第二条正式 state machine |
| `canon_evolver.py` | 739 | `canon/{patch_task,backlog,apply,approval,rendering}.py` | apply receipt/changelog 必须与 patch digest 绑定 |
| `prompt_pack.py` | 731 | `prompting/{scene_pack,constraints,sources,style,rendering}.py` | 约束优先级编译的来源顺序要做 snapshot |
| `workflow_activity.py` | 724 | `activity/{task_summary,route_lanes,timeline,suggestions}.py` | 前端显示文案和正式状态推断分开 |
| `branch_lab.py` | 718 | `branch/{facts,candidates,scoring,agent_tasks,writeback,rendering}.py` | RP 语义输入和 selected branch provenance 不可丢失 |
| `longform_materializer.py` | 715 | `materialization/{inventory,scene_yaml,rhythm_repair,manifest}.py` | 禁止改动 non-scaffold 正式 scene 的保护语义 |
| `docx_export.py` | 684 | `docx/{markdown_parse,layout,package_writer,inspection}.py` | DOCX 的 XML package 生成保持无第三方依赖和可视化验证 |
| `context_packet.py` | 645 | `context/{scene_refs,retrieval,assets,handoff,trace,rendering}.py` | context trace freshness/digest 是下游 gate，必须留单一来源 |
| `reader_experience.py` | 605 | `reader/{chapter_obligations,scene_contract,adherence,rendering}.py` | reader question/promise ledger 仍由 continuity 模块统一事实源 |
| `narrative_rhythm.py` | 600 | `rhythm/{contract,sequence,parser,rendering}.py` | 全书 tension curve 和场景 rhythm 不能形成两套不一致计算 |
| `anti_ai_style.py` | 587 | `style_lint/{rules,contrast,density,reporting}.py` | hard/soft 阈值与 profile mode 统一在 rules，不散落到 prompt |
| `chapter_pipeline.py` | 588 | `chapters/{records,continuity,rhythm,workspace_rendering}.py` | chapter workspace 是 export 前审查输入，格式快照必须保留 |

### 3.4 P2：长但暂不急拆，先保持内聚并补测试

| 文件 | 约行数 | 当前决定 | 原因 |
|---|---:|---|---|
| `protocol.py` | 561 | 保留 | 主要是 route 协议表和渲染；拆分收益低，先用 schema test 保护 |
| `roleplay_lab.py` | 533 | 只提取 markdown task fragments | 角色加载、推演任务和结果写入高度相连；过早拆开会削弱 RP 语义链 |
| `narrative_projection.py` / `narrative_projection_v3.py` | 571 / 505 | 先统一 projection contract，再择机共享 graph extraction | 当前同时重构可能损害已验收的星图视觉；只抽无状态 graph facts |
| `contracts.py` | 423 | 保留 | DTO 与 schema 的中心边界，保持集中可减少版本漂移 |
| `desktop/src-tauri/src/main.rs` | 222 | 不列入拆分 | 未达到大文件或职责混杂阈值；只需保持 sidecar integration test |

### 3.5 P1：前端与样式层

| 当前文件 | 约行数 | 拆分目标 | 验收重点 |
|---|---:|---|---|
| `features/orrery/engine/parallaxRenderer.ts` | 939 | `camera.ts`、`scene_layers.ts`、`node_renderer.ts`、`edge_renderer.ts`、`interaction.ts`、`render_math.ts` | camera pan/zoom/rotation、时间定位、节点/曲线布局回归 fixture |
| `styles/v08.css` | 902 | `styles/layout/{shell,sidebar,startup}.css`、`styles/themes/*.css`、`styles/legacy-overrides.css` | 不增加全局覆盖；视觉回归截图覆盖四主题和小屏 |
| `styles/components.css` | 755 | `styles/components/{forms,panels,reader,advisor,workflow}.css` | 同组件拖动前后尺寸、色彩 token 不漂移 |
| `styles/orreryV3.css` | 333（实际包含高密度追加覆盖） | `styles/orrery/{stage,spine,nodes,windows,dock,accessibility}.css` | 星图全景、窗口多开、深浅主题、reduced-motion |
| `components/AdvisorDock.vue` | 632 | `advisor/{AdvisorDock,AdvisorConversation,AdvisorComposer,AdvisorInbox,advisorMarkdown}.vue` | 流式输出、拖拽后尺寸、自然语言命令不丢失 |
| `stores/spatialWindows.ts` | 423 | `spatial/{windowModels,windowLayout,windowInteractions}.ts` | 多窗口、最小化、恢复、锚点位置和持久化 |
| `NarrativeParallaxStage.vue` | 409 | `stage/{StageShell,StageControls,StageGestureBridge}.vue` | 手势事件不重复绑定、滚轮不穿透面板 |
| `layout/layoutEngine.ts` | 387 | `layout/{clusterLayout,spineCurves,collision,focusTransition}.ts` | 同一输入 deterministic，节点不过密、章节簇稳定 |
| `SettingsView.vue` | 364 | `settings/{Connections,Appearance,Directories,ApplicationInfo}.vue` | provider 长列表使用 scroll，保存与回读不变 |
| `NarrativeSpineLayer.vue` | 358 | `spine/{ChapterAnchors,StoryCurves,EvidenceLinks,CharacterThreads}.vue` | 高亮/淡出、章节聚焦、关系线逻辑保持 |
| `AutopilotPanel.vue` | 348 | `autopilot/{RunModes,Authorization,ExecutionFeed}.vue` | 授权卡消失/物化、停止与恢复可观测 |
| `stores/app.ts` | 337 | `stores/{bootstrap,projectSession,theme,apiState}.ts` | startup 到 ready 无闪烁、project revision 不串项目 |
| `ManuscriptReader.vue` | 329 | `reader/{ReaderShell,ReaderContents,ReaderControls,ReaderBookmarks}.vue` | 边推进边阅读、Markdown 安全渲染、位置持久化 |
| `RhythmCurveEditor.vue` | 326 | `rhythm/{CurveCanvas,GlobalControls,ChapterControls,Legend}.vue` | 宏观曲线和章曲线共用同一 API contract |

### 3.6 测试模块也要按行为边界整理

大测试文件不是生产架构风险，却会让迁移时难以定位失败原因。本轮不追求把每个测试压到固定行数，而是按被验证的行为拆出专题 fixture：

| 当前文件 | 约行数 | 目标拆分 |
|---|---:|---|
| `tests/test_autopilot.py` | 669 | `test_autopilot_policy.py`、`test_autopilot_progress.py`、`test_autopilot_authorization.py`、`test_autopilot_recovery.py` |
| `tests/test_task_contract_transport.py` | 597 | `test_task_contract_payload.py`、`test_task_contract_semantics.py`、`test_task_contract_human_boundaries.py` |
| `tests/test_api_server.py` | 495 | `test_api_application.py`、`test_api_projects.py`、`test_api_worker.py`、`test_api_streams.py` |
| `tests/test_asset_review_revision_loop.py` | 357 | `test_asset_review_contract.py`、`test_asset_revision_writeback.py` |
| `tests/test_task_preflight.py` | 348 | `test_preflight_scene.py`、`test_preflight_assets.py`、`test_preflight_review.py` |

这些拆分只能在生产模块接口稳定后进行；测试 fixture 共享时，提取到 `tests/support/`，不得形成跨测试的隐式全局状态。

## 4. 实施批次与顺序

### M0：冻结行为与建立迁移护栏

- 建立 `tests/snapshots/` 或 fixture JSON，覆盖 CLI parser/help、task package、route audit、workflow state、Studio API route surface、autopilot event stream 和前端关键 projection。
- 对每个待拆文件建立“唯一入口、写入路径、外部 import、测试文件”的 inventory 表。
- 先移除 `task_registry.py` 已不可达 legacy body 的前提是新增 exact task package Markdown/JSON snapshot。
- 退出门禁：所有现有测试加新 snapshot test 通过。

### M1：Engine 状态机内核

按这个顺序，且每个子批次单独验证：

1. 完整迁移 `task_lifecycle`：issue/open/submit/complete/revert，通过 `LifecycleServices` 注入 route definition、payload、gate、completion marker 和 workflow state，不让 lifecycle import route blueprint。
2. 拆 `task_registry` 的 route blueprint：先 longform、source-ingest；后 style、assets、review/export；最后 scene-development。
3. 拆 `workflow_state` 为 route state calculators；每迁移一条 route 都对其状态 JSON 做 snapshot。
4. 拆 `agent_task_status` 为 inventory 和 per-route audit；scene audit 最后迁移。
5. 拆 `cli` 的 parser registration 和 command dispatch；公开 CLI 命令、help 与 exit code 不变。

#### M1.2 的实际拆分图（2026-07-24 确认后执行）

本节以当前源文件函数锚点为准，避免后续维护者把“route state”误拆成另一套 Gate。

```text
workflow_state.py (public facade / payload assembly / rendering)
  -> workflow_state_common.py
       只放路径、JSON、时间、step record 与 Markdown 渲染等无 route 归属工具
  -> workflow_state_scene.py
       scene selection、scene state、candidate/review/promotion/state/canon/ledger steps
  -> workflow_state_longform.py
       architecture、budget、inventory、chapter obligation、materialization state
  -> workflow_state_source_ingest.py
       source manifest、extraction candidate and review state
  -> workflow_state_style.py
       profile、prompt、evaluation and readiness state
  -> workflow_state_assets.py
       candidate intake、creation/review/approval/promotion state
  -> workflow_state_review_audit.py
       canon backlog/lint/review/committee state
  -> workflow_state_export_release.py
       chapter workspace/export/approval/publish state
```

迁移规则：

1. route 模块只能依赖 `workflow_state_common` 与既有文学领域模块；不得 import facade、CLI、Studio 或其他 route 模块。
2. `workflow_state.py` 只组合 route 的公开 calculator，并维持 `build_workflow_state`、`next_scene_workflow_state`、`current_scene_candidate` 的稳定导出；现有私有 helper 以兼容 alias 过渡，测试逐步迁至所属 route 模块。
3. 所有 `status`、`current_step`、`next_action`、step 顺序及输出 JSON schema 是行为契约；移动中不得顺便改文案、Gate 或文件路径。
4. 先迁移没有 scene candidate 绑定风险的 longform/source/style/assets/review/export；scene 最后迁移，避免 candidate SHA、review 和 promotion Gate 因循环依赖失真。
5. 每一条 route 迁移后执行对应 focused tests；全部迁移后执行 workflow-state snapshot、全量 Python suite、`compileall` 与 `git diff --check`。

`agent_task_status.py` 随后按相同边界拆为：inventory scan、common evidence、per-route audit、Markdown/JSON rendering，且不复用 `workflow_state` 的内部 helper。`cli.py` 最后拆为 parser group、dispatch group 与 output adapter，保持命令矩阵不变。

退出门禁：七条 route 任务顺序、task package、route audit、CLI help matrix 和自动任务执行的 golden fixture 全部通过。

### M2：Studio 的 API、持久化与 Worker

1. 抽取 Studio API dependency container 与 endpoint routers，先只迁移只读 endpoints，再迁移写操作和 SSE。
2. 对 `jobs.py` 先做 transaction failure tests；已安全抽出 primitives、autopilot 和 session/read state。下一步才是 query/event 分层，仍不抢先迁移 SQL core write/lease。
3. 拆 autopilot 的 policy、progress fingerprint、decision 和 run service。
4. 拆 task preflight、sandbox 与 worker；用失败注入证明回滚有效。
5. 对 embedded engine legacy API 重复上述 router 分层，但绝不把其 endpoint 合并入 Studio API。

退出门禁：API route surface、不跨项目 SSE、Worker rollback、autopilot no-progress、桌面 ready-file 回归通过。

### M3：文学领域模块

按“纯读取/渲染优先，候选/审批/写回最后”的规律迁移：

1. project library、word budget、prompt pack、reader experience、narrative rhythm；
2. branch、composition、candidate promotion、canon、asset workshop；
3. director agent、style lab、workflow runner、chapter pipeline、longform audit/materializer、DOCX；
4. 最后处理 cross-domain helper，杜绝把 `utils.py` 变成无边界垃圾桶。

退出门禁：语义 artifact 上游到下游的 digest chain、Agent task expected outputs、review/promotion、state/canon apply 和 longform audit 全部有回归。

### M4：前端空间场景与样式

1. 先提取 CSS tokens、themes 和 component scopes，再拆 Vue/renderer；不在代码迁移中顺便换视觉设计。
2. 将空间渲染的相机、布局算法、连接线、节点渲染和交互分开，`parallaxRenderer` 保留 render coordinator facade。
3. 将窗口状态、窗口布局、拖拽/缩放行为从组件视图抽出。
4. 将 Advisor、Reader、Rhythm、Autopilot 拆成视图 shell、数据 composable 和小组件。

退出门禁：Playwright 或等价截图验证桌面/移动端；pan/zoom/rotate、章节目录、窗口多开、Markdown、四主题、reduced-motion 可用。

### M5：清理、发布和长期治理

- 删除全部已经由 snapshot 证明不可达的 legacy 实现。
- 所有 facade 标注计划删除版本，但本轮不破坏兼容。
- 添加 import-lint：Engine 不得 import Studio，router 不得 import UI，前端不得直接解析工作项目文件。
- 增加 CI matrix：Python、client test/build、Rust、contract snapshots、route golden projects、desktop packaging smoke。

## 5. 文件级测试矩阵

| 迁移主题 | 必须新增或保持的测试 |
|---|---|
| Task lifecycle | issue/open stale refresh/submit exact outputs/complete gate failure/revert archive/event stream |
| Route blueprint | 每 route 一份 task JSON 与 Markdown snapshot；scene sequence snapshot |
| Workflow state / audit | 每 route state 和 audit JSON fixture；等待态不得误报失败 |
| CLI | `--help`、formal-help、主要 subcommand exit code 与 stdout JSON schema |
| Jobs/sandbox/worker | SQLite rollback、writeback failure、lease、idempotent retry、path traversal negative cases |
| API routers | 既有 route surface、auth、SSE headers、project isolation、startup/shutdown |
| Literary domain | semantic artifact digest consumer、review candidate binding、approved apply receipt |
| Frontend | unit、API mock、layout deterministic fixture、viewport screenshot、keyboard/reduced-motion |

## 6. 禁止事项

1. 不得一次性移动一个 1,000 行以上文件的全部函数后再尝试修测试。
2. 不得用 wildcard import、global singleton 或 `utils.py` 消解依赖问题。
3. 不得把 Studio API 的安全检查复制到每个 router；应由 dependency 层复用。
4. 不得让 frontend component 直接从 project worktree 读取 JSON/Markdown 以规避 API。
5. 不得把 Engine 的文学 Gate 提升到 Worker/Autopilot 里重新实现。
6. 不得在没有 transaction characterization tests 的前提下重排 `jobs.py` 的写路径。
7. 不得把“测试通过”理解为“包装已可发布”；OpenCode 上游 digest 不一致仍是独立发布阻塞项。

## 7. 当前执行状态与本轮实际拆分图

### 7.1 已完成的 P0/M1 迁移

下列迁移已经落地，并保留原入口作为稳定 facade：

| 原入口 | 当前职责 | 已迁移模块 | 兼容与验收 |
|---|---|---|---|
| `task_registry.py` | lifecycle/catalog facade | `task_lifecycle`、`task_paths`、`task_package_contract`、route catalog 与七条 route | task package、submit/complete/revert、route contract tests |
| `workflow_state.py` | route state facade | `workflow_state_common` 与 7 个 route calculator | scene order、review/revision、style/asset/canon/release tests |
| `agent_task_status.py` | inventory/audit facade | `agent_task_inventory`、`route_audit_*`、`agent_task_rendering` | route-audit、debug waiver、transport tests |
| `cli.py` | parser/dispatch facade | `cli_policy`、`cli_support`、`cli_parser`、7 个 command group | `--help`、`formal-help`、CLI surface/security tests |
| `scene_development_route.py` | scene task payload facade | `scene_route_support`、`scene_route_blueprints`、`scene_route_gates` | context → RP → branch → composition → review/revision order tests |

`cli_parser.py`（纯参数注册表）与 `scene_route_blueprints.py`（纯状态到任务蓝图规则表）仍略高于建议行数，但两者均不写文件、不执行 Gate、不持有运行状态。为了避免把一张可审计的规则表切成难以追踪的碎片，本轮明确将它们保留为**单职责长表例外**；任何进一步拆分必须先引入 command/blueprint fixture matrix，而不能按行数切割。

M1 的退出门禁已在本轮通过：正式任务顺序、task package、route audit、CLI surface、预算/资料投影/人工决定与 Worker 集成均已覆盖；全量 Python suite 通过。后续工作从 M2/M3 的事务和领域模块开始。

### 7.2 已复核的大文件与执行批次

本表以 2026-07-24 的实际行数和 AST 函数清单为准。`拆分`表示本轮要实施；`冻结后拆分`表示必须先补充事务或行为快照；`保留`表示当前内聚度高，先只建立测试与边界文档。

| 批次 | 文件 | 当前问题 | 决策与目标边界 |
|---|---|---|---|
| M2-A | Studio `api_server.py`（1,344，迁移中） | 应用装配、十余 endpoint family、SSE/HTTP helper 与剩余 handler 混杂 | **进行中**：`api/models`、`api/common`、`api/streaming` 已迁出；`api/routers/application` 已接管启动/健康/帮助/静态资源。后续按 read/project/runner/advisor/autopilot/reader/narrative/settings router 迁移；root 最终仅保留 middleware、lifecycle、依赖组装与 router mount |
| M2-B | Engine `api_server.py`（86 facade） | legacy HTTP surface 与 director/style/asset/project helper 曾混杂 | **已完成**：`api/models`、`api/common` 与 application/style_lab/projects/workflow/assets/agents routers 已迁移；`create_app` 只挂载 router，不得与 Studio router 共用实现 |
| M2-C | `jobs.py`（620）+ mixins | 核心 job SQL、migration、lock/resource、job event 仍在 facade；autopilot/session 已分离 | **进行中**：已加 transaction failure fixture，已提 `job_primitives`、`job_autopilot`、`job_sessions`；下一步提只读 query/event projection，写路径最后迁移 |
| M2-D | `autopilot.py`（682）+ support/policy | controller、串行锁、授权、no-progress 与 route loop 仍应保持同一编排面 | **第一阶段完成**：`automation/support` 与 `automation/policy` 已承载无状态工具和 policy/delegation；controller facade 暂保留，不按行数继续机械切碎 |
| M2-E | `task_preflight.py`（兼容 facade） | canonicalization、route validation、error rendering 曾混杂 | **第一阶段完成**：common/canonicalization + scene/assets/review validators 已迁入 `preflight/`；每种 payload 的 worker/revision loop 仍是回归门禁 |
| M3-A | `word_budget.py`（1140） | planning、inventory binding、scene contract、task rendering 混杂 | **拆分**：planning formula、inventory scan、scene contract/adherence、rendering；统一中文字数规则只保留一处 |
| M3-B | `project_library.py`（973） | 项目卡、草稿、资产、节奏、连续性、决定等 read projection 混杂 | **拆分**：display common + drafts/assets/story/continuity/decisions/context sections；保留 `build_project_library` facade |
| M3-C | `project_interaction.py`（934） | editable field、human choice、approval materialization、atomic store 混杂 | **拆分**：editable fields、choice builders、choice materialization、interaction storage；审批写回仍保持单一原子入口 |
| M3-D | `asset_workshop.py`、`scene_composer.py`、`candidate_promotion.py`、`branch_lab.py`、`canon_evolver.py` | 候选、审查、writeback 与渲染交织 | **拆分**：先只读/渲染与 candidate plan，最后迁移 approval/apply/writeback；精确 SHA/digest Gate 不可跨模块复制 |
| M3-E | `director_agent.py`、`style_lab.py`、`prompt_pack.py`、`workflow_runner.py`、`longform_audit.py`、`longform_materializer.py` | 领域规则表和运行/渲染混杂 | **拆分**：按各自表中定义的领域边界逐个推进；先对外稳定入口做 characterization |
| M4 | frontend renderer/CSS/Vue 大组件 | 渲染、布局、交互、主题、窗口状态相互耦合 | **另批实施**：先 token/theme，再 parallax camera/layout/edge/node，最后窗口/Advisor/Reader；必须带截图与交互回归 |

### 7.3 本轮可靠执行顺序

1. 完成 M1 的剩余验证与文档，禁止回拉 route 代码。
2. M2-C 已完成 create/claim/lock 的失败注入测试和 autopilot/session 安全抽离；继续前先补 query/event output snapshot，绝不移动 core write/lease。
3. 先执行 M3-A、M3-B、M3-C：这些模块可用 facade + fixture 保持输出稳定，且能降低后续 API router 的依赖复杂度。
4. 再执行 M2-A、M2-D、M2-E；每个 router family 迁移后运行 API surface 与 SSE/project-isolation 测试。
5. 最后按 M3-D/M3-E 的“只读 → candidate → review → approval/writeback”顺序迁移；M4 与发布构建单独验收，避免在同一批次混入视觉变更。

### 7.3.1 M2-E `task_preflight` 的精确拆分图

`task_preflight.py` 的公共入口只保留 `PreflightIssue`、`PreflightResult`、`canonicalize_task_outputs` 与 `validate_task_outputs`。其余实现按如下职责迁移：

```text
task_preflight.py (facade + deterministic dispatch)
  -> preflight_common.py
       completion schema、issue/result DTO、JSON/file checks、completion marker、review conclusion
  -> preflight_canonicalization.py
       scene review identity 与 candidate manifest 的系统字段规范化
  -> preflight_scene.py
       scene review、candidate provenance、scene revision 的 Gate
  -> preflight_assets.py
       asset candidate 与 asset review 的 Gate
  -> preflight_review.py
       project review 与 source extraction revision 的 Gate
```

迁移约束：

1. `canonicalize_task_outputs` 只能补齐 task-owned deterministic metadata，绝不把 Agent 的 review conclusion、正文或创作判断改写为 pass。
2. `validate_task_outputs` 保持现在的固定调用顺序；每个子模块只向同一个 `issues` 列表追加问题，不自行 short-circuit 后续 Gate。
3. common 不得 import scene/assets/review validator；validator 可以依赖 common 和既有 Engine Gate，但不得反向 import facade。
4. 每迁移一类 validator，运行 `test_task_preflight` 加对应 scene/asset/review revision-loop 测试与 Worker integration；最后跑 API/Worker 和全量 suite。

### 7.4 本轮退出门禁

只有同时满足以下条件，才能称为“本轮大文件拆分完成”：

1. 所有标记为 **拆分** 的文件均已转为 facade 或已证明的单职责模块；冻结后拆分文件至少具备其前置 characterization tests 和明确不动写路径的记录。
2. 每个新模块在 `docs/architecture/module-boundaries.md` 有职责、依赖方向、稳定入口和测试链接。
3. 聚焦测试、`python -m unittest discover -s tests -v`、`python -m compileall -q src`、`git diff --check` 通过；受影响时补充 client build、Rust check 或 API surface 验证。
4. 不出现 Engine → Studio、router → UI 或 Worker → Engine Gate duplicate 的反向依赖。

### 7.5 拆分后的目录归位蓝图（新增硬目标）

大文件拆分完成后，不能把新模块继续平铺在包根目录。目标结构必须让新维护者可以从目录名判断职责、依赖方向和改动风险，同时仍保留既有 import 路径的兼容 facade。该整理不是一次性重命名工程，而是在每一个领域拆分验收后做受控归位。

#### 7.5.1 Studio：应用、接口、运行时与持久化分层

```text
src/literary_engineering_studio/
  api/                    FastAPI app factory、依赖容器、request models、SSE 与 routers
    routers/              application、runners、advisor、autopilot、projects、workflow、reader、narrative、delivery、style_lab
  application/            config、bootstrap、lifecycle、application info、诊断与默认目录策略
  automation/             Autopilot policy、progress、decision support；不持有 HTTP request
  persistence/            SQLite schema、事务、job/run/session/read state
  runtime/                Worker、sandbox、process/task orchestration、writeback/recovery
  integrations/           OpenCode/Claude Code binary、client、credential/control、runner probe
  projections/            dashboard、library、reader、narrative、progress、delivery 的只读投影
  advisor/                顾问会话、persona、inbox、snapshot；不直接组装 HTTP response
  observability/          agent session、worker/live event、diagnostic feed
  jobs.py                 兼容 facade：JobStore 的公开入口
  worker.py               兼容 facade：AgentWorker 的公开入口
  task_preflight.py       兼容 facade：preflight DTO 与 dispatch
  autopilot.py            兼容 facade：AutopilotService 与可 patch 的 controller seam
  api_server.py           兼容 facade：create_app
```

归位约束：

1. `api/` 只能依赖 application、automation、runtime、projection、advisor、observability 和 CoreBridge；不得读取项目文件来重算 Engine 状态。
2. `runtime/` 可以调用 Engine bridge 和 persistence，但不得 import API router 或 Vue 资源。
3. `integrations/` 只解决外部 Agent/CLI 的发现、凭据、子进程和协议适配；不得混入文学 Gate 或前端状态。
4. `projections/` 只读；任何审批、任务提交和 Canon 写回仍走 runtime/Engine 正式链路。
5. 旧的顶层模块先缩为 re-export facade；只有在发布说明中给出迁移窗口后才允许移除。测试中的 patch target 视为兼容 API，迁移时必须保留。

#### 7.5.2 Embedded Engine：任务状态机与文学领域分开归位

```text
src/literary_engineering_studio_engine/
  tasking/                task paths、contract、lifecycle、inventory、submission/event ledger
  routes/                 route catalog 与七条 route blueprint/gate
  workflow/               derived workflow state、route audit、activity/dashboard
  literary/
    planning/             word budget、longform materialization、chapter obligations
    scene/                context、roleplay、branch、composition、promotion、state/canon handoff
    assets/               characters/world/location/organization candidate-review-promotion
    style/                style learning、mounting、prompt/style lint/anti-AI constraints
    review/               scene review、canon lint/evolution、longform audit、reader experience
    export/               chapter pipeline、DOCX、release package
  prompting/              prompt pack、platform agent tasks、generation/provider contracts
  api/                    legacy Engine API models/dependencies/routers；与 Studio API 隔离
  compatibility facades   现有顶层模块名，逐步变为稳定 re-export
```

归位约束：

1. 不用一个泛化的 `utils.py` 或 `services.py` 收容跨领域代码；每个 helper 必须属于 tasking、workflow、文学领域或 prompting 中的一个。
2. Scene 的 candidate SHA、review binding、promotion receipt、state/canon patch digest 必须在同一依赖方向内可追踪，不能因目录移动断开。
3. Engine 顶层 facade 只可向内导入；任何 `literary/*` 不能导入 Studio、FastAPI、Tauri 或 runtime credential。
4. `cli.py` 与 `cli_*` 继续作为命令入口/规则表例外，待 parser fixture matrix 完整后才考虑归入 `tasking/cli/`，不得为目录整洁提前破坏可审计性。

#### 7.5.3 Client：按功能域而非组件类型归位

```text
client/src/
  app/                    bootstrap、routing、theme、project session、API state
  features/
    orrery/               camera/layout/renderer/stage/windows/spine
    workflow/             task status、autopilot、human decision、agent observability
    reader/               manuscript reader、contents、bookmarks、search
    projects/             create/open/project configuration
    settings/             connections、appearance、directories、application info/help/legal
    library/              project archive/detail projection
    quality/              creative quality、rhythm configuration
  shared/
    ui/                   无业务含义的基础窗口、按钮、Markdown renderer
    composables/          可复用的异步/SSE/drag/resize behavior
    styles/               tokens、themes、component primitives、accessibility
    types/                API and view-model contracts
  assets/                 多主题静态背景与图标；由 theme token 引用
```

归位约束：

1. `components/` 仅保留迁移期 facade；新组件必须先归属一个 feature 或 `shared/ui`。
2. `stores/` 拆入 `app/` 或相应 feature；不得继续成为跨功能的全局状态堆栈。
3. Orrery renderer 的 camera、layout、edge/node render 和 interaction 不得互相直接修改状态，统一通过明确的 scene model/interaction contract。
4. 样式按 token/theme/component scope 分层；不得继续追加全局 override 来解决局部视觉问题。

#### 7.5.4 实施顺序与回滚策略

1. 先创建目标包及 `__init__.py`，仅移动已经拆出的实现；顶层 facade 原样保留。
2. 先归位 Studio 的 `persistence/`、`preflight/`、`automation/`（已完成），下一批是 `api/` 的 models/dependencies/SSE/只读 routers。
3. 每迁移一个 API family，先更新 route surface tests，再把原 handler 缩为注册调用；不要在 `create_app` 中留双份 endpoint。
4. Engine 仅在对应 M3 领域完成 characterization 后归位；先移动纯读取/渲染模块，最后移动审批与 writeback。
5. Client 先形成 `shared/ui` 与 token/theme，再迁移 feature；每次改目录后跑 typecheck、build 和关键视图截图。
6. 每个归位批次建立 import inventory，确认旧 import、猴子补丁 target、CLI entry point 和打包收集规则仍可用。回滚只回滚当前批次，不回滚已通过验证的前一领域。

#### 7.5.4.1 2026-07-24 已完成归位批次

1. **Engine legacy API**：原 1,599 行 `api_server.py` 现为 86 行 facade；OpenAPI 仍为 49 条公开路径，`tests/test_engine_api_route_surface.py` 锁定端点族。
2. **Engine tasking**：`paths`、`lifecycle`、`package_contract`、`semantic_contracts`、`contract_audit` 已迁入 `tasking/`；旧模块名仍可导入，并保留私有 helper 的导入兼容。
3. **Engine longform planning**：原 `word_budget_*` 实现迁入 `literary/planning/`；`word_budget.py` 继续是唯一稳定公开入口。
4. **Engine library projection**：原 `project_library_*` 实现迁入 `projections/library/`；该包只读，正式写回仍留在 task/runtime route。
5. **Engine workflow projection**：`workflow_state*`、`workflow_activity`、`workflow_dashboard` 迁入 `workflow/`；历史 module path 采用 alias facade，以保留 review loop 对 `workflow_state_scene` 的 monkeypatch seam。
6. **Engine creative director**：原 1,486 行 `director_agent.py` 现为兼容 facade；真实实现归入 `director/{contracts,bootstrap,status,routing,prompts,loop,records,service}.py`。项目初始化、只读状态、确定性路由、模型提示词、工具观察循环与运行记录不再相互混杂。

后续归位严格遵循同一模式：先完成职责拆分和 characterization，再移动实现，最后将根目录改为 facade。不得为了目录齐整移动仍被 monkeypatch 的具体实现模块。

#### 7.5.4.2 顶层平铺实现全量归位清单（新增硬目标）

“已拆大文件”不等于“目录已可维护”。除明确的 facade、包入口、兼容 CLI/API
入口和基础 contract 外，以下仍平铺在包根的**真实实现**必须按领域归位。任何新增
工程文件也必须先选择下列目录，而不能继续投放在包根。

| 范围 | 目标目录 | 当前待归位模块族 | 兼容策略与迁移风险 |
|---|---|---|---|
| Engine 命令面 | `command_line/` | `cli_parser`、`cli_policy`、`cli_support`、所有 `cli_*_commands`、`formal_mode` | 根 `cli.py` 必须保留 module entry point，故实现域不用同名 `cli/` 包；其余根 `cli_*` 仅保留 facade；先锁定 parser/help/exit-code matrix，避免 command handler 因相对 import 漂移 |
| Engine 路线定义 | `routes/` | `route_catalog`、`route_selection`、`scene_development_route`、`*_route`、`scene_route_*`、`route_audit_*` | route Gate 不得改写为 UI/Worker 逻辑；根路径需要保留 patch seam |
| Engine 场景文学 | `literary/scene/` | context、roleplay、branch、composition、candidate promotion、revision、state apply/evolve、scene handoff/readiness/draft | 按 Context → RP → Branch → Compose → Candidate → Review → Promotion → State 的依赖顺序迁移；SHA/digest 和 scene file guard 必须回归 |
| Engine 资产与 Canon | `literary/assets/` | asset workshop/context、character assets、new character register、canon lint/evolver/review、continuity ledger、story architecture | approval/apply/writeback 最后迁移；不得把候选与正式资产写回混为一处 |
| Engine 文风与审查 | `literary/style/`、`literary/review/` | style lab/compiler/evaluator/prompt、anti-AI style、punctuation、creative quality、agent scene review、longform audit、reader experience、rhythm | 文风挂载、lint hard gate、独立 review 与节奏/读者契约均需保持单一事实源 |
| Engine 交付 | `literary/export/` | chapter pipeline、docx export、export package/publish、release fingerprint、materializer | 文档格式、export receipt 与 release fingerprint 的输出快照必须保持 |
| Engine 提示词与 Agent 契约 | `prompting/` | prompt pack/registry/compiler、platform agent tasks、agent provider/schema/json builder/committee、generation provider | 提示词优先级、Agent task sidecar 与 provider 配置必须单向依赖文学事实，不得反向调用 Studio |
| Engine 基础设施 | `foundation/` | atomic IO、draft text、text counts、resources、model config、knowledge/memory store、Dify/LangGraph adapters | 只容纳跨领域无业务判断的机制；不建立泛化 `utils.py` |
| Studio 应用面 | `application/`、`projects/` | bootstrap/config/lifecycle/application info/project manager/project progress | 顶层只保留兼容 facade；默认目录、项目隔离与版本升级行为需测试 |
| Studio 运行时 | `runtime/` | worker、sandbox、process manager、execution coordinator、task program、supervisor | 运行时只能调用 CoreBridge/Engine，不能复制 Gate；sandbox/writeback/recovery 迁移需 failure-injection |
| Studio 集成 | `integrations/opencode/` | OpenCode binary/client/server/control/profiles/runtime pool、runner probe、model connections | 安装包资源、绝对路径、进程关闭与凭据脱敏是迁移门禁 |
| Studio 只读投影 | `projections/` | reader、narrative projection、core/api read models、whole book release、delivery | 只读投影不得产生正式写回，SSE revision/cache 语义不得改变 |
| Studio 顾问与可观测性 | `advisor/`、`observability/` | advisor/personas/inbox/snapshot/creative steward、agent observability/session tracking/runtime/live events | 对话、自然语言指令和 Agent 事件分开，但共享稳定的只读 session contract |

执行批次固定为：**先迁移没有写回职责的 projection/prompt/CLI 实现，再迁移候选、审查和写回；每一批完成后把根模块缩为 facade，并将依赖边界和验证记录写入架构文档。**

完整到逐文件级别的目标目录、迁移顺序、alias facade、资源定位审计和测试矩阵，见
[`arcvellum-remaining-source-directory-allocation-plan.md`](arcvellum-remaining-source-directory-allocation-plan.md)。

#### 7.5.4.3 2026-07-24 全量根级归位完成记录

本轮已按 `arcvellum-remaining-source-directory-allocation-plan.md` 完成 Studio 与
Engine 剩余根级业务实现的物理归位。Studio 的执行、持久化、自动化、应用、集成、
投影、顾问和可观测性实现均在各自领域目录；Engine 的命令、任务、路线、审计、
文学、提示词、项目服务均已归位。根模块只保留稳定公共 API、CLI/API entry point、
跨客户端 contract 或 import-compatible facade。

唯一命名例外是 Engine 的 `command_line/`：保留根 `cli.py` 以维持 console 与
`python -m` 入口，因此不创建会与它冲突的同名 `cli/` package。Prompt Registry 已改为
扫描七条正式 route definition，避免 facade 化后遗漏 task prompt 覆盖。

#### 7.5.5 目录重组退出门禁

1. `src/literary_engineering_studio/` 包根只剩兼容 facade、版本/CLI/CoreBridge/contract 和明确的顶层装配；业务实现按上述领域包归位。
2. `src/literary_engineering_studio_engine/` 的任务、route、workflow、文学、prompting、legacy API 具备可读目录边界；不形成 Engine → Studio 反向 import。
3. Client 新功能不再写入泛化 `components/`、`stores/` 或全局 CSS 文件；现有遗留文件都有迁移说明或 facade 标记。
4. 通过 import boundary check、Python 全量测试、client typecheck/build、桌面 packaging smoke，并确认 PyInstaller/Tauri 的 hidden imports 和静态资源仍被收集。
