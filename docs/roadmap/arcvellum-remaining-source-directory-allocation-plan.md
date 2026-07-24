# ArcVellum 剩余工程文件目录分配与迁移执行指令

> 文档性质：强指导性目录重组执行文件。适用于不了解既有项目的维护 Agent。
>
> 盘点日期：2026-07-24
>
> 前置文件：[大文件模块化执行计划](arcvellum-large-file-modularization-execution-plan.md)、[模块边界](../architecture/module-boundaries.md)、[可靠性实施进度](../verification/cli-literary-reliability-progress.md)

## 1. 目标、范围与不可违反的规则

本轮目标不是继续“整理文件名”，而是让源代码目录本身表达系统边界：维护者看到路径即可判断模块是否可以写项目文件、是否属于正式 Gate、是否可接触外部 Agent、以及该跑哪一组测试。

本文件涵盖当前仍平铺在以下两个包根的**真实实现**：

```text
src/literary_engineering_studio/
src/literary_engineering_studio_engine/
```

已经是 4–52 行兼容 facade 的文件不重复迁移；它们应留在根目录，直到公开迁移窗口结束。新实现一律不得再写到包根。

### 1.1 不可违反的技术边界

1. Studio 可以调用 Embedded Engine；Engine 绝不能 import Studio、FastAPI、Tauri、浏览器状态、桌面凭据或外部 Agent 运行时。
2. 只有 Engine route/Gate 可以决定正式任务是否完成、正文是否晋升、Canon/State 是否写回；Studio runtime 只能领取、隔离、提交和观察任务。
3. `projections/` 只读。任何“看起来像编辑”的操作都必须转为 runtime/Engine 的正式命令或 human choice。
4. `integrations/` 只管理第三方 CLI/API、二进制、进程和协议，不保存文学规则或文件 Gate。
5. 所有移动后的资源定位必须使用显式包锚点，禁止再用 `Path(__file__).parent / "vendor"` 这类会随目录移动失效的相对表达式。
6. 根模块若被测试或外部脚本 monkeypatch，必须使用 `sys.modules[__name__] = implementation_module` 的 alias facade；仅 `from x import *` 不足以保持 patch seam。
7. 禁止一次批量移动多个“写回域”（candidate、review、promotion、state/canon apply）。先迁移只读/渲染，再迁移候选，再迁移写回。

### 1.2 统一迁移步骤

每个批次严格执行：

1. 读取本文件对应行、目标模块的 imports、关联测试和资源定位点。
2. 先写 characterization test；若已有测试能锁住输出、错误与副作用，在记录中引用它而非重复造测试。
3. 创建目标包和一句话 `__init__.py` 职责说明。
4. 移动实现，修复内部 relative import；**新模块直接 import 新目录实现**，不得再依赖旧 facade。
5. 在旧根路径创建 alias facade，或对同名包采用“包 `__init__` alias 到 service”的方案。
6. 显式审计 `__file__`、`vendor/`、模板、打包配置、`importlib` 和延迟 import。
7. 跑本表规定的聚焦测试，随后再进行全量 Python、client、桌面构建验收。
8. 更新模块边界、验证记录和本文件的完成状态；未验证前不得标记完成。

### 1.3 兼容 Facade 模板

无同名目录冲突时使用：

```python
"""Compatibility alias for :mod:`.target.module`."""
import sys
from .target import module as _implementation
sys.modules[__name__] = _implementation
```

若原路径为 `advisor.py` 而目标必须为 `advisor/`，删除旧文件，令 `advisor/__init__.py` alias 到 `advisor.service`。这样 `import literary_engineering_studio.advisor` 和既有 patch target 仍落在同一个真实模块上。

## 2. 当前事实快照

### 2.1 已完成、不得回迁的目录

| 包 | 已归位目录 | 说明 |
|---|---|---|
| Studio | `api/` | FastAPI 模型、common、streaming 和 router family；根 `api_server.py` 是 app factory/facade |
| Studio | `application/` | config、bootstrap、lifecycle、application info、project manager/progress |
| Studio | `integrations/` | model connections 与 `integrations/opencode/` |
| Studio | `observability/` | Agent 会话、运行事件、live event、观测投影 |
| Studio | `projections/` | Reader、Narrative、Dashboard/Library、delivery、read cache、whole-book release |
| Studio | `advisor/` | Advisor service、persona、inbox、snapshot、creative steward；同名 package 兼容旧入口 |
| Studio | `persistence/`、`preflight/`、`automation/` | 先前已拆的事务、规范化与 Autopilot 支持 |
| Engine | `api/`、`director/`、`foundation/` | legacy HTTP、顶层总监、跨领域确定性基础设施 |
| Engine | `tasking/`、`workflow/`、`projections/library/`、`literary/planning/` | 任务生命周期、派生状态、资料投影、长篇预算 |

### 2.2 当前仍允许位于根目录的文件

这些不是待搬迁的业务实现：

- Studio：`__init__.py`、`__main__.py`、`api_server.py`、`contracts.py`、以及迁移期 `autopilot.py`、`jobs.py`、`worker.py`、`task_preflight.py` 的公开 facade。
- Engine：`__init__.py`、`__main__.py`、`api_server.py`、`cli.py`、`director_agent.py`、`word_budget.py`、`project_library.py`、`project_interaction.py`、`workflow_state*.py`、`task_*.py`、`foundation` facade，以及暂时仍承担公开契约的 `protocol.py`。

其中 `autopilot.py`、`jobs.py`、`worker.py` 目前仍有真实控制/事务实现，属于下文 Studio P0；其最终目标是 facade，但不能机械移动。

## 3. Studio 剩余文件：完整分配表

### Studio P0：运行时写路径，先补证据再迁移

| 当前文件 | 目标实现位置 | 目标职责 | 迁移前必须锁定 | 完成条件 |
|---|---|---|---|---|
| `jobs.py` | `persistence/job_store.py` | SQLite connection、migration、job/lock/resource 事务和事件账本 | create/claim/lock 的失败注入、lease、migration、event ordering | 根 `jobs.py` 仅 alias；`JobStore` 单一连接/锁协议未分裂 |
| `autopilot.py` | `automation/controller.py` | 授权、串行推进、no-progress、route loop 编排 | authorization、retry、pause/resume、delegation、quota、no-progress | 根 `autopilot.py` facade；controller 不 import API/router |
| `worker.py` | `runtime/worker.py` | sandbox task 执行、submission、recovery、event emission | sandbox rollback、preflight、任务提交、cancel/retry | Worker 不复刻 Engine Gate，只通过 CoreBridge/CLI |
| `sandbox.py` | `runtime/sandbox.py`，后续再拆 `staging/writeback/journal` | temporary workspace、diff、writeback、rollback journal | failure injection、path escape、copy/restore | 原子 journal 仍可恢复，路径白名单不变 |
| `process_manager.py` | `runtime/process_manager.py` | 受控子进程启动、停止、记录 | hide window、cleanup、timeout、pid ownership | OpenCode/worker 都经同一进程协议 |
| `execution_coordinator.py` | `runtime/execution_coordinator.py` | 项目级并发与互斥 | multi-run denial、release on failure | 不引入任务逻辑 |
| `task_program.py` | `runtime/task_program.py` | task package 执行程序与结果汇总 | task allowed reads/writes、submit/complete sequencing | 不直接编辑正式项目文件 |
| `supervisor.py` | `runtime/supervisor.py` | worker 生命周期与恢复 | restart、stop、status projection | API 只观察，不直接驱动内部状态 |
| `sidecar_protocol.py` | `runtime/sidecar_protocol.py` | ready-file、nonce、loopback/port policy | `port=0`、nonce、token、atomic ready-file | desktop 打包资源与 CLI import 均通过 |
| `subprocess_utils.py` | `runtime/subprocess_utils.py` | 无业务的 subprocess helper | error/timeout/stdout contracts | 不保留隐性 shell 注入通道 |

**Studio P0 迁移顺序：** `sidecar_protocol → subprocess_utils → process_manager → execution_coordinator → sandbox → task_program → worker → jobs → autopilot → supervisor`。其中 `jobs` 和 `autopilot` 最后，因为它们是当前写路径/授权面。

### Studio P1：跨域桥与评估

| 当前文件 | 目标实现位置 | 原因 | 聚焦验证 |
|---|---|---|---|
| `core_bridge.py` | `runtime/engine_bridge.py` | Studio 对 Engine 的唯一调用边界；避免散落 subprocess/CLI 调用 | `test_core_bridge.py`、Worker integration、path allowlist |
| `prompt_evaluation.py` | `automation/prompt_evaluation.py` | 用于任务/提示词质量评估，不是 API 或文学事实源 | `test_prompt_evaluation.py`、不触发真实 provider |
| `cli.py` | `application/cli.py` | Studio 本地管理命令；根 `__main__`/旧 `cli.py` 只保留入口 | `test_cli_commands.py`、serve/security/help |

### Studio P2：目录与命名收束

1. 保留现有 `runtimes/`：它是 Host/Claude Code/Codex/OpenCode runtime adapter 的稳定协议包，不与 `runtime/` 合并。`runtime/` 管理进程和执行；`runtimes/` 表达 Agent 能力协议。
2. `contracts.py` 保留根目录，作为 Studio DTO/version contract 的唯一公共位置；只有当 schema 可按 request/runtime/projection 明确拆分且客户端类型同步后才迁移。
3. `api_server.py` 保持根 app factory。其真实 router 已在 `api/`，不得再把 endpoint implementation 回填。

## 4. Embedded Engine 剩余文件：完整分配表

### Engine P0：CLI 与任务操作面

> **命名例外（已确认）**：Engine 必须保留根 `cli.py` 作为
> `python -m literary_engineering_studio_engine`、console entry point 和旧导入的
> 兼容入口。因此实现目录使用 `command_line/`，而不是与 `cli.py` 同名的
> `cli/` 包，避免 Python 的 module/package 解析歧义。此例外不改变 CLI 的
> 公开契约或本表的职责分配。

| 当前模块族 | 目标目录 | 归属文件 | 特别约束与聚焦测试 |
|---|---|---|---|
| `cli_parser.py`、`cli_policy.py`、`cli_support.py`、`formal_mode.py` | `command_line/` | `parser.py`、`policy.py`、`support.py`、`formal_mode.py` | 先建立 parser/help/exit code fixture matrix；`cli_parser` 是规则表，允许暂时不继续细拆 |
| `cli_agent_commands.py`、`cli_asset_commands.py`、`cli_formal_commands.py`、`cli_legacy_commands.py`、`cli_longform_commands.py`、`cli_project_commands.py`、`cli_scene_commands.py` | `command_line/commands/` | 按现有文件名 | 所有命令从 CLI 领取；不得让开发调试命令变成正式 bypass |
| `task_registry.py`、`workflow_contract.py`、`protocol.py`、`orchestration_blueprint.py`、`flow_gates.py` | `tasking/` | `registry_facade.py`、`workflow_contract.py`、`protocol.py`、`orchestration.py`、`gates.py` | 正式 route 顺序与 task JSON/Markdown 不变；`protocol.py` 先保持集中，不要按行数切碎 |
| `agent_tasks.py`、`agent_task_inventory.py`、`agent_task_rendering.py` | `tasking/agent_tasks/` | `writer.py`、`inventory.py`、`rendering.py` | sidecar completion、task ownership、human gate 文案和路径不变 |
| `approval.py` | `tasking/approval.py` | 通用批准/授权契约 | human choice materialization 与 route audit 通过 |

**Engine P0 顺序：** 先 `agent_task_*` 和 `approval`，再 CLI command implementation，最后 parser。`cli.py` 根 facade 必须保留，且 `formal-help` / `help-all` 测试不变。

### Engine P1：Route 定义与派生审计

| 当前模块族 | 目标目录 | 归属文件 | 特别约束与聚焦测试 |
|---|---|---|---|
| `route_catalog.py`、`route_selection.py` | `routes/` | `catalog.py`、`selection.py` | exact id/path suffix 语义保持；`test_route_catalog.py`、`test_route_selection.py` |
| `workflow_runner.py` | `workflow/runner.py` | diagnostic/compatibility workflow runner | 只能调用既有正式 task/Gate，不得成为第二条 state machine；`test_worker_integration.py`、route/scene focused suite |
| `scene_development_route.py`、`scene_route_support.py`、`scene_route_blueprints.py`、`scene_route_gates.py` | `routes/scene/` | `definition.py`、`support.py`、`blueprints.py`、`gates.py` | Context → RP → Branch → Compose → Candidate → Review → Promote → State/Canon 次序不可变 |
| `asset_route.py`、`style_engineering_route.py`、`longform_planning_route.py`、`source_ingest_route.py`、`review_audit_route.py`、`export_release_route.py` | `routes/{assets,style,longform,source_ingest,review,export}/` | 各自 `definition.py` | 每条 route 独立 task package/gate snapshot；不混到 literary implementation |
| `route_audit.py`、`route_audit_common.py`、`route_audit_evidence.py`、`route_audit_assets.py`、`route_audit_export.py`、`route_audit_longform.py`、`route_audit_review.py`、`route_audit_scene.py`、`agent_task_status.py` | `workflow/audit/` | `service.py`、`common.py`、`evidence.py`、各 route audit | `route-audit`、debug waiver negative、review/promotion evidence tests |

**Engine P1 顺序：** 先 catalog/selection；再 audit evidence/common；之后 route definition；scene route 作为最后一个 route 迁移。所有根路径均使用 alias facade，尤其 `route_audit_scene` 的 Gate patch seam。

### Engine P2：文学场景域

| 目标目录 | 当前待归位文件 | 内部职责边界 | 不可破坏的证据 |
|---|---|---|---|
| `literary/scene/context/` | `context_packet.py`、`context_broker.py`、`scene_handoff.py` | context refs/retrieval/trace 与 handoff contract | trace digest/freshness、memory trust、handoff tests |
| `literary/scene/roleplay/` | `roleplay_lab.py` | BDI/RP task、agent directive、结果读取 | roleplay semantic evidence、agent task sidecar |
| `literary/scene/branching/` | `branch_lab.py` | branch facts/candidates/score/selection/writeback | selected branch provenance、composition input |
| `literary/scene/composition/` | `scene_composer.py`、`scene_draft.py` | facts/beat plan/prose seed/composition digest | compose task digest、scene contract order |
| `literary/scene/promotion/` | `candidate_promotion.py`、`scene_revision.py`、`scene_readiness.py` | candidate hash、review/revision gates、formal promote | exact candidate SHA、revision anti-evasion、promotion manifest |
| `literary/scene/state/` | `character_state_evolver.py`、`character_state_apply.py`、`scene_character_assets.py`、`new_character_register.py` | BDI/state patch、approved apply、新角色登记 | state patch digest、approval/apply receipt、new character gate |
| `literary/scene/` | `generation_provider.py` | provider-neutral prose generation contract | producer provenance、provider dry-run/real call tests |

**迁移顺序：** context → roleplay → branching → composition → promotion → state。`generation_provider` 在 composition 后、promotion 前归位，但不得绕开生成 sidecar/Gate。

### Engine P3：资产、Canon、长篇结构与连续性

| 目标目录 | 当前待归位文件 | 迁移边界 | 聚焦验证 |
|---|---|---|---|
| `literary/assets/` | `asset_workshop.py`、`asset_context.py` | candidate creation/review/promotion/rendering，先拆只读与 rendering | asset review/revision loop、candidate approval |
| `literary/assets/canon/` | `canon_lint.py`、`canon_evolver.py`、`agent_canon_review.py` | candidate patch、lint、review、approval/apply backlog | Canon patch route、lint、apply receipt |
| `literary/assets/continuity/` | `continuity_ledger.py`、`story_architecture.py` | promise/payoff、reader question、架构约束 | continuity ledger、story architecture contract |
| `literary/planning/` | `longform_materializer.py`、`chapter_pipeline.py`、`rhythm_plan.py`、`narrative_rhythm.py` | inventory materialization、chapter obligations、宏观/章节节奏；现有 budget 子包不得重复实现 | longform route/revision、rhythm plan、materialization guard |

`longform_materializer.py` 是非 scaffold 正式 scene 覆盖保护的唯一实现；迁移后仍必须拒绝覆写正式 scene。

### Engine P4：文风、审查、读者体验与交付

| 目标目录 | 当前待归位文件 | 规则 |
|---|---|---|
| `literary/style/` | `style_lab.py`、`style_compiler.py`、`style_evaluator.py`、`style_prompt.py`、`style_prompt_agent.py`、`style_prompt_eval.py`、`anti_ai_style.py`、`punctuation_standard.py` | 风格学习/挂载、可执行约束、AI 味 lint、标点标准同属一个优先级编译方向；不能让 cleanup 正则替代 LLM review |
| `literary/review/` | `agent_scene_review.py`、`agent_committee.py`、`creative_quality.py`、`reader_experience.py`、`longform_audit.py`、`review_ci.py` | deterministic lint → independent Agent review → revision map → longform audit；reviewer/writer session 必须独立 |
| `literary/export/` | `docx_export.py`、`export_package.py`、`publish.py`、`release_fingerprint.py` | final body filtering、DOCX package、delivery receipt、release fingerprint；不携带工作流/Cannon 痕迹 |

### Engine P5：Prompting、Agent Provider 与项目辅助

| 目标目录 | 当前待归位文件 | 说明 |
|---|---|---|
| `prompting/` | `prompt_pack.py`、`prompt_compiler.py`、`prompt_registry.py`、`platform_agent_tasks.py` | 约束优先级、prompt asset registry、platform Agent task package；不得直接写正式项目资产 |
| `prompting/agents/` | `agent_provider.py`、`agent_schema.py`、`agent_json_builder.py`、`agent_committee.py`（迁移时与 review 的 committee adapter 分层） | provider/JSON/schema 是执行通道；审查政策仍放 `literary/review` |
| `projections/interaction/` | `project_interaction_choices.py`、`project_interaction_common.py`、`project_interaction_editing.py` | 人类选项、展示编辑和 choice materialization；正式 effect 仍走 Engine route |
| `projects/` | `init_project.py`、`demo_project.py`、`source_ingest.py` | 项目 shell、demo、源文本接入；source-ingest route definition 留 `routes/source_ingest` |

## 5. 实施批次与依赖顺序

```text
S0  建立 characterization / import / resource inventory（本文件完成后执行）
S1  Studio runtime 基础：sidecar + process + coordinator + sandbox
S2  Studio runtime 写路径：task program + worker + jobs + autopilot + supervisor
S3  Engine tasking 辅助与 CLI command implementation
S4  Engine route catalog/audit/definition
S5  Engine literary scene（只读 → candidate → promotion/state）
S6  Engine assets/planning/style/review/export/prompting/projects
S7  Studio bridge/evaluation/CLI 与剩余 facade 收束
S8  全量验证、client build、Tauri packaging、clean install/upgrade smoke
```

以下依赖必须先满足：

- S1 结束前，禁止移动 `worker.py`。
- S2 结束前，禁止将 `jobs.py` 变为 facade。
- S3 结束前，禁止移动 `cli_parser.py`；command groups 先迁移。
- S4 结束前，禁止移动 scene route；必须先锁住 route audit/blueprint snapshots。
- S5 结束前，禁止跨目录拆 candidate SHA/review/promotion/state digest。
- S6 中，style/prompting 只能向文学事实读取，不向 Studio runtime 反向依赖。

## 6. 资源、动态 import 与打包审计清单

每个移动批次必须执行以下搜索并逐项处理：

```powershell
rg -n "__file__|importlib|sys\.modules|vendor/|vendor\\|templates|references|_engine" src packaging desktop tests
rg -n "patch\(\"literary_engineering_(studio|studio_engine)\." tests
rg -n "from \.|import \." src/<moved-package>
```

重点已知风险：

1. Engine `foundation.resources` 已从 `Path(__file__).parent` 改为 Engine 包根；任何新增 resource helper 必须复用它。
2. Studio OpenCode manifest/NOTICE 已改为显式 Studio 包根 `vendor/`；打包脚本仍从 `src/literary_engineering_studio/vendor/` 收集资源。
3. Advisor 是同名 package/module 迁移特例；根 package alias 必须继续支持 API 与测试 patch。
4. PyInstaller hidden import、Tauri resource copy、OpenCode receipt 和 sidecar ready-file 均属于 S8 发布门禁，不能因为 Python import 通过就忽略。

## 7. 每批验证矩阵

| 范围 | 最小命令 |
|---|---|
| 任意 Python 移动 | `python -m compileall -q src`、`git diff --check` |
| Studio application/integration/projection | 对应 `tests/test_config.py`、`test_bootstrap.py`、`test_opencode*.py`、`test_reader.py`、`test_narrative_projection*.py`、`test_api_server.py` |
| Studio runtime/persistence | `test_sandbox.py`、`test_jobs.py`、`test_worker_integration.py`、`test_autopilot.py`、`test_runtime_foundation.py` |
| Engine CLI/tasking/routes | `test_engine_cli_surface.py`、`test_cli_commands.py`、`test_task_contract_transport.py`、`test_task_lifecycle_facade.py`、`test_route_*.py` |
| Engine scene | `test_semantic_task_contracts.py`、`test_scene_contract_order.py`、`test_scene_review_revision_loop.py`、`test_state_writeback_contract.py` |
| Engine assets/style/review/export | `test_asset_review_revision_loop.py`、`test_canon_patch_route.py`、`test_style_evaluation_loop.py`、`test_longform_*.py`、`test_reader_experience_contract.py` |
| 每个阶段结束 | `python -m unittest discover -s tests -v` |
| 客户端/API 受影响 | `npm.cmd run client:test`、`npm.cmd run client:build`、API route surface |
| 运行时/安装受影响 | `cargo check --locked`、`packaging/build_desktop.ps1`、clean install/upgrade smoke |

## 8. 退出门禁

只有全部满足才可称为“目录重组完成”：

1. 两个包根中不再存在未经说明的业务实现；根目录只含入口、compatibility facade、跨域 contract 和有明确例外说明的规则表。
2. 本表中每个真实文件已进入目标目录，或有一条记录说明为什么必须保持根路径与何时复审。
3. 所有 facade 的旧 import 和必要 patch seam 都有 characterization test。
4. 不存在 Engine → Studio 反向 import；Studio projection 不写项目；runtime 不复制 Gate。
5. 全量 Python、prompt registry、client test/build、Rust check、桌面打包和 clean-install/upgrade smoke 均通过。
6. `docs/architecture/module-boundaries.md`、本文件和验证进度记录同步为事实，不包含“计划已完成”式虚假状态。
