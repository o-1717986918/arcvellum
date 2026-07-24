# ArcVellum CLI 文学可靠性实施进度

> 权威执行指令：`docs/roadmap/arcvellum-cli-literary-reliability-implementation-directive.md`
> 基线提交：`9cab45e`；工作分支：`feat/post-v094-spatial-reliability`
> 本文件是事实记录，不以“代码已写”代替退出门禁。所有 Batch 仍须经过 Batch 12 的全量验证、桌面候选和最终报告。

## 当前结论

- Batch 0–10：实现与聚焦测试已完成；2026-07-24 的第一次全量运行发现并修复了拆分过程中遗漏的 `hashlib` 导入，以及两项已不符合正式长篇顺序的 Worker 测试断言。
- Batch 11：实现完成，退出门禁待最终报告复核。Sidecar 协议、Task Package Contract、Route Selection 与 Studio Read Models 已按兼容边界拆出；作品档案已投影故事架构、连续性账本、创作决定和 Context Health。
- Batch 12：进行中。确定性全量测试通过；本地固定 OpenCode archive、expanded binary 与 installation receipt 已完成一致性校验，桌面候选已能进入 PyInstaller/Tauri 构建阶段。仍须以当前源代码完成一次完整构建、更新 release staging，并做 clean-install/upgrade smoke，之前不得声称发布级交付完成。
- 工作树包含本轮未提交改动；日志和临时产物由 `.gitignore` 排除，不能批量暂存或删除用户文件。

## Batch 0：冻结基线与建立证据

- Status: complete
- Evidence: 初始记录为 Python 253 tests、Client 54 tests、Prompt Registry 36 assets/73 task ids、Rust `cargo check --locked`；本轮新增契约和可靠性覆盖后，最终计数以 Batch 12 为准。
- Baseline risks retained: 旧任务 Completion Marker 可能无语义内容；任务包和 Worker 写回曾缺少原子恢复与精确任务验证。

## Batch 1：Task Contract Audit 与单一契约源

- Status: implementation complete; final exit gate pending Batch 12 suite
- Added: `semantic_task_contracts.py`、`task_contract_audit.py`、语义产物 schemas。
- Contract: 任务包现在声明 `execution_policy`、Agent role、human gate、runtime capabilities、typed outputs、semantic artifact consumer。
- Evidence: `tests/test_task_contract_audit.py`、`tests/test_task_contract_transport.py`、`tests/test_semantic_task_contracts.py`。

## Batch 2：Roleplay、Composition、State、Canon 语义完成

- Status: implementation complete; final exit gate pending Batch 12 suite
- Added: roleplay/composition/state/canon 的 digest-bound semantic artifact schemas 和 gate validation。
- Evidence: Branch manifest 读取 exact roleplay result；composition/state/canon 任务必须拥有已验证的语义结果，不再只接受 completion marker。
- Evidence tests: `tests/test_semantic_task_contracts.py`、`tests/test_state_writeback_contract.py`、`tests/test_canon_patch_route.py`。

## Batch 3：原子 Task Finalize 与恢复

- Status: implementation complete; final exit gate pending Batch 12 suite
- Added: sandbox 写回备份、事务 journal、失败补偿、`task-revert-submission`。
- Evidence tests: `tests/test_sandbox.py`、`tests/test_task_submission_revert.py`、`tests/test_atomic_read_models.py`。

## Batch 4：RP → Branch → Composition 文学因果链

- Status: implementation complete; final exit gate pending Batch 12 suite
- Added: roleplay semantic evidence 是 branch manifest 的显式输入；branch selection 和 composition readiness 使用已选分支证据。
- Evidence tests: `tests/test_semantic_task_contracts.py`、`tests/test_task_contract_transport.py`、`tests/test_scene_review_revision_loop.py`。

## Batch 5：Context Trace v2、Scene Handoff 与 Memory 信任层

- Status: implementation complete; final exit gate pending Batch 12 suite
- Added: `scene_handoff.py`、Context Trace digest/freshness、memory trust tiers。
- Evidence tests: `tests/test_context_trace_v2.py`、`tests/test_scene_handoff.py`、`tests/test_memory_trust_tiers.py`。

## Batch 6：Story Architecture、独立审查与宏观 Rhythm

- Status: implementation complete; final exit gate pending Batch 12 suite
- Added: `story_architecture.py`、Story Architecture schema/prompt assets、上游独立审查与 Word Budget 前置门禁。
- Important migration: longform route 的第一个确定性任务现在生成 `plot/story_architecture.candidate.json`，不是直接生成 `word_budget.json`。Worker integration test 已按这一正式顺序校正。
- Evidence tests: `tests/test_story_architecture_contract.py`、`tests/test_worker_integration.py`。

## Batch 7：Bridge、Reader Question 与 Promise/Payoff

- Status: implementation complete; final exit gate pending Batch 12 suite
- Added: `continuity_ledger.py`、scene handoff、Reader Question / Promise-Payoff ledger 审查与 apply receipt。
- Evidence tests: `tests/test_continuity_ledger.py`、`tests/test_scene_handoff.py`。

## Batch 8：Review 独立性、Revision Map 与 Prompt Compiler

- Status: implementation complete; final exit gate pending Batch 12 suite
- Added: compiled prioritized constraints、writer/reviewer session separation、candidate SHA review binding、revision anti-evasion checks。
- Evidence tests: `tests/test_prompt_compiler.py`、`tests/test_review_session_independence.py`、`tests/test_scene_review_revision_loop.py`。

## Batch 9：State / Canon Decision-Apply 完整闭环

- Status: implementation complete; final exit gate pending Batch 12 suite
- Added: state approval/apply task stages、digest-bound decisions、atomic state and canon writeback receipts。
- Evidence tests: `tests/test_state_writeback_contract.py`、`tests/test_canon_patch_route.py`、`tests/test_choice_effect_materialization.py`。

## Batch 10：性能、安全、SSE 与桌面启动可靠性

- Status: implementation complete after current sidecar regression repair; final exit gate pending Batch 12 suite
- Added: revision/TTL-aware read-model cache；SSE reconnect and stale-project protection；loopback/token policy；OpenCode binary receipt/integrity checks；nonce-bound ready file；autopilot no-progress protections。
- Repair on 2026-07-24: `serve --port 0 --ready-file` previously fell back to configured port because zero was treated as false. It now preserves zero on the private ready-file path and is covered by `tests/test_sidecar_ready_file.py`.
- Evidence tests: `tests/test_read_model_cache.py`、`tests/test_api_server.py`、`tests/test_opencode.py`、`tests/test_cli_security.py`、`tests/test_sidecar_ready_file.py`、`tests/test_autopilot.py`。

## Batch 11：渐进模块化、前端投影与仓库治理

- Status: in_progress
- Safe boundaries already extracted:
  - `literary_engineering_studio.sidecar_protocol`: loopback policy, ready-file IPC, bound-port discovery and nonce contract. CLI compatibility exports are retained.
  - `literary_engineering_studio.api_read_models`: revision-aware Dashboard, Library, Reader, Progress, Delivery and Workspace composition. API routes keep their existing public surface and late-bound Dashboard instrumentation seam.
  - `literary_engineering_studio_engine.task_package_contract`: formal task contract constants, fingerprinting, prompt projection, output ownership and Markdown rendering. Registry compatibility facades are retained; the next safe cleanup is removal of the now-unreachable legacy bodies after an exact task-package snapshot is added.
  - `literary_engineering_studio_engine.route_selection`: route-local work-item selection, including explicit exact-identifier versus path-suffix matching rules.
  - `literary_engineering_studio_engine.task_lifecycle`: route-neutral issue/open/submit/complete/revert/advance/event operations. Registry injects the route definition, payload builder, renderer and Gate services through a compatibility facade; the former duplicate lifecycle bodies were removed after focused lifecycle, task-contract, rollback and Worker integration regressions passed.
  - `literary_engineering_studio_engine.source_ingest_route`: source-ingest blueprint、candidate-only output contract、manifest/extraction/review Gate and revision provenance. Registry only injects its route callbacks; the old duplicate source-ingest body has been deleted.
  - `literary_engineering_studio_engine.longform_planning_route`: story architecture → independent review → budget → scene inventory → chapter obligations → materialization 的正式任务包与 Gate。Route Catalog 已转用该模块，Registry 中的重复 blueprint/Gate 已删除。
  - `literary_engineering_studio_engine.style_engineering_route`、`asset_route`、`review_audit_route`、`export_release_route`: 分别承载文风、资产、项目审查/Canon、交付发布的蓝图和 Gate；候选 SHA、审查、审批与发布证据保持 route-local。
  - `literary_engineering_studio_engine.scene_development_route`: 承载 Context → RP → Branch → Composition → Prose → Review → Promotion → State/Canon/Continuity 的场景主链。`task_registry.py` 已降为约 275 行 lifecycle/catalog facade，不再保存正式 route 的重复实现。
- Governance completed: `.github/workflows/ci.yml`、`.gitattributes`、logs/temp ignore rules、version-sync script, OpenCode receipt resource placeholder for source builds.
- Added characterization: `tests/test_api_route_surface.py`, `tests/test_route_selection.py`, `tests/test_engine_cli_surface.py`, and `tests/test_task_lifecycle_facade.py`.
- Frontend projection: 作品档案现可展示 Story Architecture、Reader Question / Promise-Payoff ledger、State/Canon 相关的人类决定与 Context Trace 新鲜度；前端只消费 API Read Model，不解析 Sidecar Markdown。
- Completed cleanup: Registry 内不可达的 `_legacy_*` task-package renderer 已在 task package contract 回归保护下删除。
- Batch 11 continued on 2026-07-24:
  - `workflow_state.py`、`agent_task_status.py`、`cli.py` 和 `scene_development_route.py` 已分别降为 164/118/40/90 行的兼容 facade；route calculator、audit、CLI group 与 scene payload/Gate 已迁入明确模块。
  - `word_budget.py`、`project_library.py`、`project_interaction.py` 已分别降为 66/8/13 行 facade。预算公式/库存/场景合同/渲染、资料投影、显示编辑/人工选择/原子写回已分层。
  - `JobStore` 已完成第一阶段安全拆分：`persistence.primitives` 集中 schema/校验/脱敏，`persistence.autopilot_runs` 承载 run/lease/decision/event，`persistence.sessions` 承载顾问、Agent 会话、用户通知与阅读位置；核心 `jobs.py` 保留单一 SQLite connection、migration、任务/锁/资源和 job event 写入协议。
  - 新增三条 SQLite 失败注入特征测试，覆盖 initial event 写入失败时 create 回滚、started event 写入失败时 claim 回滚、lock event 写入失败时 project lock 回滚。
  - 目录收束完成第一批：上述持久化实现归入 `persistence/`；`task_preflight.py` 已成为 facade，其 DTO/common、系统字段规范化、scene/assets/project-review Gate 归入 `preflight/`；Autopilot 的无状态支持归入 `automation/support`。顶层入口保持不变。
  - `automation/policy` 已进一步接管授权模式、额度规范化、revision task 识别与 delegation policy；`autopilot.py` 保留可替换的 controller route order 和完整的串行执行/暂停语义。
  - Studio API 目录重组已启动：`api/models` 承载 request DTO，`api/common` 承载 HTTP error/path/static file helper，`api/streaming` 承载 SSE formatting/read-model stream，`api/routers/application` 已接管启动、桌面 session、health、帮助、诊断、bootstrap 与静态前端资源。`api_server.create_app` 保持为稳定 facade 和 router mount 点。
  - API route surface test 已升级为递归识别 FastAPI 的 lazy included router，避免 router 化后只扫描顶层 route 而误报接口消失；应用 router 迁移后，API/CLI security focused suite 26 tests 通过。
  - 回归过程中发现并修复 export route audit 缺失审批记录 helper；此前只经完整 Dashboard/API 流程暴露，现由 `route_audit_common` 统一提供。
  - Focused evidence: persistence/autopilot/preflight/Worker/API 76 tests through；task/scene contract 39 tests；budget/longform 35 tests；library/API/cache/transport 46 tests；human choice/autopilot/API 45 tests，均通过。
  - Engine legacy API 已完成端点族 router 化：`api_server.py` 从 1,599 行降至 86 行，`application/style_lab/projects/workflow/assets/agents` router 保持 49 条 OpenAPI path；`tests/test_engine_api_route_surface.py` 通过。
  - Engine 目录归位第一批完成：任务基础设施进入 `tasking/`，预算实现进入 `literary/planning/`，只读项目资料进入 `projections/library/`；旧 import 路径改为 facade。task transport、semantic evidence、word-budget、longform route、reader/projection/API 回归均通过。
  - Engine workflow 归位完成：derived state、activity、dashboard 进入 `workflow/`。场景 review/revision loop、task transport、route-local choice 与 Studio API 共 59 项聚焦回归通过；旧 workflow modules 使用 alias facade，验证 legacy patch target 与真实实现同一 module object。
  - Engine creative director 归位完成：原 `director_agent.py` 的项目初始化、状态投影、确定性路由、提示词装配、受控工具循环和记录呈现分别进入 `director/` 领域包；旧 import 路径保留兼容 facade。独立 dry-run 覆盖项目 bootstrap 和“自由偏好 → 方向记忆 → 状态观察 → 报告”闭环，Engine API/CLI surface 回归 3 项通过。
  - 顶层平铺实现已纳入硬性归位清单：除公开入口、兼容 facade 与跨领域 contract 外，所有后续真实实现必须归入 Engine 的 `cli/routes/literary/prompting/foundation` 或 Studio 的 `application/runtime/integrations/projections/advisor/observability`；完整批次表见模块化执行计划 7.5.4.2。
  - Engine `foundation/` 归位完成：`atomic_io`、资源定位、文字/草稿/显示处理、模型配置、知识/记忆索引和 Dify/LangGraph 适配器均以 module alias 保留旧路径；资源根改为显式 Engine 包根，预算/提示词注册相关回归通过。
  - Studio `application/` 与 `integrations/` 第一批归位完成：应用配置/启动/生命周期/项目管理/进度与 OpenCode/model-connection 适配均已迁入；根路径保留 alias facade。OpenCode 的 pinned manifest/NOTICE 资源定位改为显式 Studio 包根，23 项 OpenCode/启动/应用信息回归通过。
- Remaining: Studio/Engine API router、Job core query/event 抽取、Autopilot/Preflight/Worker、其余文学领域与前端大文件仍按模块化计划渐进拆分；不能以本批 facade 化代替最终全量验证报告。

## Batch 12：Golden Projects、全量验收、安装与发布准备

- Status: complete for the current v0.9.4 candidate; fresh packaging, isolated installation, installed-sidecar startup, and same-version repair are verified. A future version cut still requires a real cross-version upgrade migration check.
- Golden catalog scaffold added: six required literary shapes in `tests/fixtures/golden_projects/catalog.json` and deterministic preflight coverage in `tests/test_golden_project_catalog.py`.
- Passed 2026-07-24: `python -m unittest discover -s tests -v` (299 tests), `python -m compileall -q src`, Studio `doctor`, Studio/Engine CLI help, Prompt Registry (41 assets / 78 task prompt ids), prompt evaluation (17 deterministic cases), client tests (54), client production build, Rust `cargo check --locked`, version sync and `git diff --check`.
- Supply-chain status: the local pinned v1.18.3 archive SHA-256 now matches the manifest (`cd987a...770d9e`); the expanded executable and installation receipt are verified by `opencode-install`. This removes the earlier archive-hash block, but does not itself prove a releasable installer.
- Still required: run `packaging/build_desktop.ps1` against the final source, verify that `dist/release` is refreshed from the produced NSIS bundle, desktop packaging smoke, clean-install/upgrade validation, viewport acceptance, and `cli-literary-reliability-final-verification.md`.

### Final-source regression after directory allocation (2026-07-24)

- `python -m unittest discover -s tests -q`: **305 passed** in 49.819s after the complete Studio/Engine source-directory allocation.
- `python -m compileall -q src`: passed.
- `python -m literary_engineering_studio_engine prompt-registry-validate --json`: passed (`41` prompt assets, `51` declared task prompt IDs).
- `python -m literary_engineering_studio.cli doctor`: passed; embedded Engine is ready and the bundled OpenCode runtime is discoverable.
- `git diff --check`: passed. The working tree contains expected source moves and compatibility facades, not whitespace errors.
- Source encoding audit: **0** Python source files retain a UTF-8 BOM. This specifically protects AST-based dependency-direction tests after the Windows-side mechanical moves.
- Remaining Batch 12 gates are now strictly cross-stack and packaging gates, rather than unresolved source allocation work.

### Final candidate verification (2026-07-24)

- Status: source allocation and current-version release-candidate verification complete.
- Fresh desktop package: packaging/build_desktop.ps1 -SkipPythonInstall -SkipNodeInstall passed after the final source changes. It rebuilt the PyInstaller sidecar, Vue assets, Tauri executable, NSIS installer, updater signature, provenance receipt, latest.json, and SHA256SUMS.txt.
- Packaging repair: the windowed PyInstaller bootloader caused the Uvicorn sidecar to exit before creating its ready-file. The sidecar now retains a console subsystem so Uvicorn has usable standard streams; Tauri's tauri-plugin-shell uses Windows CREATE_NO_WINDOW, so normal desktop launches still do not show a terminal. tests/test_sidecar_spec.py protects this boundary.
- Frozen sidecar smoke: the rebuilt binary published a nonce-bound arcvellum-sidecar/v1 ready-file on an OS-assigned loopback port.
- Installer smoke: a silent install into an isolated build/installer-smoke-* directory included the desktop executable, renamed external sidecar, bundled OpenCode executable, and receipt; the installed sidecar also passed the ready-file smoke. A second silent in-place reinstall passed with all required files intact.
- Final cross-stack evidence: Python suite **306 passed**; prompt registry **41 assets / 51 task IDs**; client suite **54 passed**; client production build, Rust cargo check --locked, version synchronization, compilation, provenance verification, and git diff --check passed.
- Residual release validation: a true migration from a separately installed older signed version must be repeated when the next version number is cut. The present candidate validated clean install and same-version in-place repair, which are the meaningful checks available without fabricating an older release.

## Last Verified Commands

## Batch 11：目录归位收尾（2026-07-24）

- Status: implementation complete; final cross-stack and packaging exit gates remain in Batch 12.
- Studio runtime/application completion: the sidecar, subprocess, process coordinator, sandbox, task program, Worker, JobStore, Autopilot Controller, Supervisor, Engine bridge, prompt evaluation and Studio CLI implementations now live under `runtime/`, `persistence/`, `automation/`, and `application/`. Root paths remain import-compatible aliases; the Studio CLI compatibility module also preserves `python -m literary_engineering_studio.cli` execution.
- Engine command surface completion: command groups, parser, policy, formal-mode rules and dispatch now live in `command_line/`. The implementation intentionally avoids an `engine/cli/` package because it would collide with the stable root `cli.py` module and make Python module/package resolution ambiguous.
- Engine workflow completion: route catalog/selection are in `routes/`; route definitions are grouped by business route; route audit and sidecar status are in `workflow/audit/`; the compatibility workflow runner is `workflow/runner.py`; registry, protocol, gates, blueprint and workflow contract are in `tasking/`.
- Engine literary completion: scene context/RP/branch/composition/promotion/state, assets/Canon/continuity, planning/rhythm, style, review, export, prompting/provider contracts and project initialization now have explicit domain homes. Root modules remain compatibility aliases only.
- Registry repair: prompt registry task discovery now reads the seven formal route definition implementations rather than root facade files. It reports 41 assets and 51 declared task prompt IDs, restoring prompt-coverage validation after directory migration.
- Root-boundary check: no unclassified root business implementation remains. Intentional Studio exceptions are `api_server.py`, `contracts.py`, and the `task_preflight.py` facade; intentional Engine exceptions are API/CLI/public facade modules and the compact project-library compatibility exports.
- Focused evidence after the directory completion: runtime/persistence/autopilot 36 tests; Bridge/Worker/security 23 tests; Studio CLI/sidecar 11 tests; Engine task sidecars/approvals 35 tests; Engine CLI 33 tests; audit 42 tests; scene 20 tests; assets/planning 16 tests; style/review/export/API 39 tests; prompting/route/task transport 42 tests; tasking/protocol 34 tests, all passed.

- `python -m unittest discover -s tests -v`: **304 passed** after Studio API routerization; `python -m compileall -q src` and `git diff --check` passed in the same run. Engine API/tasking/planning/projection directory moves will receive a fresh final full-suite count in the next Batch 12 run.

- `python -m unittest tests.test_task_contract_transport tests.test_semantic_task_contracts tests.test_task_contract_audit tests.test_sandbox tests.test_cli_security tests.test_sidecar_ready_file -v`: 38 passed after contract/sidecar extraction.
- `python -m unittest tests.test_asset_review_revision_loop tests.test_canon_patch_route tests.test_longform_revision_loop tests.test_style_evaluation_loop -v`: passed after restoring the Registry hash dependency.
- `python -m compileall -q src`: passed after the focused extraction.
- `python -m unittest discover -s tests -v`: 299 passed after source-ingest and longform route execution-path extraction, including Golden catalog, formal contract transport, semantic artifacts, atomic rollback, autopilot no-progress, API/SSE, Read Model cache, Reader projection and new Library literary projections.
- `npm.cmd run client:test`: 54 passed; `npm.cmd run client:build`: passed.
- `cargo check --locked`, `python scripts/verify_version_sync.py`, `python -m literary_engineering_studio_engine prompt-registry-validate --json`, and `git diff --check`: passed.
