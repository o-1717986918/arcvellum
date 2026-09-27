# 全仓清理候选清单（滚动核查）

日期：2026-09-27。范围：当前仓库的 Engine、Studio、Vue 客户端、Pi Worker、桌面宿主、脚本、测试、协议与打包入口。每发现一项立即记入本表；“候选”不等于可以直接删除。判断时同时核查静态引用、运行注册、公开 API、持久化读取、测试和已发布兼容承诺。既有 [旧表面退役审计](../arcvellum-legacy-surface-retirement-audit-2026-09-14.md) 的兼容限制仍有效。本轮只列清单，不删除用户文件或旧项目读者。

| 编号 | 类别与位置 | 已核实证据 | 建议和清理前门槛 |
| --- | --- | --- | --- |
| C01 | 旧自动补长：`src/literary_engineering_studio/runtimes/scene_length_completion.py` | 全仓符号搜索中 `complete_first_draft_length` 只有本文件定义；`render_scene_length_completion_prompt` 只在该文件和 `tests/test_lean_kernel_v2_pi_runtime.py` 使用。新交易路径已将软字数不足交独立审读。 | **高可信可退役候选**。移除模块与专属测试前确认没有外部插件按私有路径导入；保留“软下限只提示”回归。 |
| C02 | 旧预先全套对演：`scene_performance_materials`、`perform_scene_interaction`、`render_interaction_direction_prompt` | `pi_scene_transaction.py` 只导入 `scene_performance_materials`，没有运行调用；`perform_scene_interaction` 的唯一生产调用来自前者；旧导演提示只在该链使用。新路径走 `fulfill_scene_material_requests`，按主创请求执行。大量旧测试仍直接验证该链。 | **高可信生产死路径、测试仍在**。作为独立退役包删旧入口及其专属测试；迁移仍有价值的人格、历史、权限断言到按需路径，并核对 Engine `public.literary` 导出承诺。 |
| C03 | 未挂载 Advisor 前端服务：`client/src/features/advisor/services/advisorClient.ts` | 排除测试与测试 harness 后，`createAdvisorClient` / `advisorClient` 在 `client/src` 只由本文件声明，当前 `App.vue` 无 Advisor 挂载。`/advisor/*` 仍列入 OpenAPI，后端兼容入口仍在；2026-09-14 退役审计明确要求保留一个兼容窗口。 | **前端可退役候选、API 暂保留**。到兼容窗口后，先核对外部前端调用，再移除客户端与专属 harness/测试；HTTP、持久化表及 Project Agent 共用会话存储要分别评估，不连带删除。 |
| C04 | Studio 顶层导入转发：`autopilot.py`、`whole_book_release.py` | 两文件只把 `sys.modules[__name__]` 指向 `automation.controller`、`projections.whole_book_release`。对 `src/scripts/workers/desktop/packaging` 的全路径导入搜索只见同名子包的不同模块；显式顶层导入及补丁目标集中于 `tests/test_autopilot.py`。先前退役审计将其列为延期包 C3。 | **中高可信冗余别名**。迁移测试导入/patch 目标到规范模块后，检查动态导入、公开兼容清单和外部消费者，再独立删除别名；不触碰同名子包的实现。 |
| C05 | 断开的旧策略前端：`client/src/features/strategy/`（视图、store、client、投影、类型） | `CreationStrategyView.vue` 是该功能链唯一视图入口，但全仓生产代码没有导入它；`router.ts` 的 `/strategy` 已重定向到 Project Agent 的 `quality` 工作区。其内部模块仅相互引用，测试仍存在。 | **高可信未挂载功能簇**。成组退役旧前端与专属测试，确认旧投影是否另有外部消费；后端策略/编排 API 需要单独查证，不能随前端删除。 |
| C06 | 断开的旧 Agent 观测视图：`client/src/features/observatory/AgentObservatoryView.vue` | 生产导入搜索没有调用点；`router.ts` 的 `/observatory` 已重定向 Project Agent，创作工作区的 `observatory` 实际加载 `CreativeLiveView.vue`。该视图测试仍在。 | **高可信单视图死代码**。移除视图和专属测试前确认其展示字段已由 Project Agent/Creative Live 覆盖；底层观测数据与 API 仍供其他页面使用，不随之清理。 |
| C07 | 旧 Orrery 工作台底栏：`client/src/features/orrery/WorkspaceDock.vue` 与专属 CSS | 从 `main.ts` 追踪静态和字面量动态导入，组件不可达；全仓生产引用只见自身。`WorkspaceDock.spec.ts` 单独挂载它；`spatialOperatingSystem.css` 的 `.spatial-workspace-dock`、`delivery-dock-ready` 及移动端选择器只服务该组件。 | **高可信前端死组件及孤立样式**。成组退役组件、专属测试和专属样式选择器；保留同文件中其他当前 Orrery 样式。 |
| C08 | 未使用 Orrery 背景加载器：`client/src/services/orreryAssets.ts` 与 `assets/orrery/mineral-astrarium.webp` | `loadOrreryBackground` 在生产及测试源均无调用；该 WebP 只在加载器的动态 import 中出现。当前 `orreryPreferences.ts` 仍使用 `mineral` 作为持久化偏好值，不能据此删除偏好迁移。 | **高可信孤立加载器和资源**。若不计划重新启用图像背景，可一起移除加载器与 WebP；保留偏好读取和旧值归一化直到完成数据迁移。 |
| C09 | 角色会话旧顺序调用：`runtimes/scene_conversation_invocation.py::invoke_role_sequence` | Python 源码符号扫描中只见函数声明和同文件 `__all__` 字符串；调用侧使用 `invoke_role`、`invoke_actor_turn`、`invoke_initialized_role_turn`。 | **中高可信未调用适配器**。检查外部按名称导入后移除函数和 `__all__` 项；保留 Gateway 的 `run_sequence`，它可能有其他消费者。 |
| C10 | 旧演员归属修复提示：`runtimes/scene_performance_ownership.py::ownership_repair_instruction` | 只见定义及同文件 `__all__`，现有 `repair_actor_ownership` 接收修订回调而不调用该提示生成器。 | **中高可信未调用提示词**。先核对外部测试/插件导入；清理时同步从提示目录核销其用途，不影响实际归属审计逻辑。 |
| C11 | 未连接的自定义供应商请求模型：`api/models.py::CustomProviderModelRequest`、`CustomProviderConnectionRequest` | 全仓 Python 代码中前者只作为后者字段类型，后者只有类声明；HTTP 路由、客户端、API 测试、导出的 OpenAPI 和 TypeScript schema 均无这两个模型名。 | **高可信未使用 API DTO**。可一起删除并重导 OpenAPI；实际供应商配置接口如使用别的合同，应保持原样。 |
| C12 | 未使用的 Canon changelog 写入包装：Engine `literary/assets/canon/evolver.py::_append_changelog` | 全仓 Python 符号扫描只有函数声明；它只是读取旧日志并调用 `_render_changelog_entry` 与 `atomic_write_batch`，但没有调用入口。 | **高可信私有死函数**。确认日志写入当前另有路径后删除该包装；`_render_changelog_entry` 及现行 Canon 账本路径单独核查。 |
| C13 | 未使用的风格评测历史聚合：Engine `workflow/state_style.py::_accepted_style_evals` | 只有函数定义；当前状态流程使用 `_style_eval_reference` 等其他读者，没有引用该聚合结果。 | **高可信私有死函数**。删除前核对是否原拟用于多次评测判定，并保留现有当前候选风险门槛。 |
| C14 | 未调用的编排 warning 构造器：Studio `orchestration/lint.py::_warning` | 只有定义；同文件 `_error` 仍被调用，warning 级别值仍用于排序和合同，不能一并移除。 | **高可信私有死函数**。只清理该包装，保持 `PlanIssueSeverity.WARNING` 的合同支持。 |
| C15 | 未调用的 V4 流转换包装：Studio `api/routers/narrative.py::_v4_transition` | 只有定义；SSE 路径按版本直接调用 `_spatial_transition(..., version=version)`；`_v3_transition` 仍由 `tests/test_narrative_stream_patch.py` 直接测试。 | **高可信私有重复包装**。可移除 V4 包装；V3 包装若要一起归并，先迁移直接依赖它的测试。 |
| C16 | 未使用的变更凭据分组函数：Studio `observability/change_groups.py::group_mutation_receipts` | 全仓 Python 调用搜索只见定义，`change_group_id` 则仍在用。 | **中可信孤立辅助函数**。确认没有外部分析脚本按模块导入后单独清理，不改变凭据 ID 生成与存储。 |
| C17 | 未使用的事件持久化布尔包装：Studio `observability/event_policy.py::should_persist_runtime_event` | 除定义和 `__all__` 外无调用；现行代码使用 `classify_runtime_event` / `is_ephemeral_runtime_event`。 | **中可信重复 API**。检查外部导入后撤掉布尔包装及导出，保留统一事件分类器。 |
| C18 | Studio 根目录兼容转发簇：`agent_observability.py`、`api_read_models.py`、`application_info.py`、`config.py`、`core_read_models.py`、`delivery.py`、`live_events.py`、`model_connections.py`、`narrative_projection*.py`、`project_manager.py`、`reader.py`、`supervisor.py`、`worker.py` 等 | 这些根文件均是 5–7 行 `sys.modules` 转发；`api_server.py` 仍用相对导入把其中多项当内部入口，规范实现已在 `application/`、`projections/`、`runtime/` 等包。先前退役审计已成功移除十个无清单转发，但这一簇还有测试 patch 与可能的外部导入。`task_preflight.py` 是实际实现，不属此簇。 | **中可信重复模块层，分批处理**。先把 `api_server.py` 内部导入改到规范模块并迁移测试 patch，再逐个核查外部兼容；不可整簇删除，尤其 `config`、`worker` 可能被外部使用。 |
| C19 | 双份 v1 Agent 任务 JSON Schema：`protocol/schemas/agent_*.v1.json` 与 Engine `_engine/schemas/agent_*.v1.json` | 三对文件中 `agent_submission`、`agent_completion` 的 SHA-256 完全相同；`agent_task` 已分叉：Engine 副本比 `protocol` 副本多 `schema_name`、`consumed_by` 和 `semantic_artifact` 定义。搜索不到代码对 `protocol/schemas` 的直接读取，Engine 副本列于 `pyproject.toml` 包资源，路线文档仍引用两处。 | **明确重复且已漂移**。先定唯一规范源并确认安装包/外部合同，再由构建生成另一份或改引用；加一致性校验。不要直接删 v1 schema，旧项目/任务包仍使用该身份。 |
| C20 | 旧策略/观测页的孤立样式：`client/src/styles/components.css`、`agentWorkspaces.css`、`creativeLive.css` 中 `.strategy-*`、`.observatory-*` 专属规则 | Vue/TS 模板搜索中 `strategy-grid/card/events` 和 `observatory-diagnostics/sessions` 只在 C05、C06 的未挂载视图出现；`components.css` 更早的 `.observatory-canvas/node/list` 已无任何 Vue 模板使用。三个样式文件仍由 `main.ts` 加载。 | **高可信冗余 CSS，需选择器级清理**。随 C05/C06 删除对应块及响应式覆盖；先筛出与当前页面共用的普通选择器，不能整体删除 CSS 文件。 |
| C21 | 不可从当前 CLI 到达的旧命令处理器：Engine `command_line/commands/legacy.py` | `command_line/entry.py` 的派发器没有导入其 `handle`，`parser.py` 不注册 `director-chat`、`run-langgraph`、`dify-dsl` 等命令；`policy.py` 明确列为禁用，CLI 表面测试验证禁用集合与 parser 选择无交集。旧顶层 `cli_legacy_commands.py` 仍转发到该模块，兼容清单规定不早于 1.0.0 移除。 | **生产 CLI 死路径，但公开别名受保护**。待 1.0.0 与外部消费者审计后成包退役处理器、别名、禁用命令清单的冗余项及专属测试；当前不能先删别名所指实现。 |
| C22 | 随旧 CLI 才可到达的 Dify/LangGraph 适配：Engine `foundation/dify_dsl.py`、`foundation/langgraph_adapter.py` | `build_dify_workflow_dsl`、`run_literary_graph` 在源码中的唯一调用来自 C21；当前正式 Engine CLI 与 Studio runtime 均不触达。`director` 本身另被旧 HTTP API 调用，不能与这两项混同。 | **中可信退役候选**。随 C21 核对外部 Python API、维护者实验和文档后成包处理；尤其保留旧 HTTP 导演依赖，不能以 CLI 禁用推断整个 director 包无用。 |
| C23 | 分层提示目录与旧 Engine 直连 Provider 提示并存：`prompting/pack.py`、`literary/assets/workshop.py`、`director/*` 等 | 当前 Studio 活动场景、项目 Agent、顾问、Steward、正式任务与 Worker 已纳入 129 个静态层和 59 个正式资产正文；旧直连 Provider 模块仍通过代码拼接模型可见文案，且不能从 Studio 正式入口调用。`scene.interaction.direction` 与 `scene.length.legacy` 已标记旧路径。 | **旧功能退役候选及注册边界**。随 C01/C02、C25–C28 核查并退役旧直连模块；如决定保留独立 Engine CLI 能力，再将其拼接文案迁入只读注册资源并补独立调用验收。避免把不可消费的旧文案误列为可编辑活动层。 |
| C24 | Orrery 客户端未调用的旧 V2 方法：`client/src/features/orrery/services/orreryClient.ts::projection/observeProjection` | 生产端搜索没有任何对这两个方法的调用；当前空间视图使用同 client 的 `spatialProjection/observeSpatialProjection`，请求 `/narrative/*/v4`。服务端仍注册无版本号的 V2 和 V3 HTTP 路由，V4 投影内部还调用 V2 构建函数。 | **客户端高可信冗余方法，服务端仅作兼容评估**。可先删两个客户端方法及其专属测试；旧 HTTP 是否移除需外部消费者/版本窗口证明，V2 内部构建代码不能因客户端不用旧端点而删除。 |
| C25 | 旧直连式文风学习：Engine `literary/style/lab.py::run_author_style_learning` | 全仓 Python 只见定义；正式 CLI 和 HTTP 均使用旁边的 `run_author_style_learning_platform_task`。两函数重复准备作者语料与编译资料，前者再直接调用 Provider 生成提示词。 | **中高可信旧功能实现**。迁移任何维护者直调脚本后退役直连函数，并提取两条路径仍共用的确定性语料准备，避免复制；正式 Task 路线保持。 |
| C26 | 旧直连式文风提示与效果评测：Engine `literary/style/prompt_agent.py::build_agent_style_prompt`、`prompt_eval.py::run_style_prompt_eval` | 两个顶层入口在全仓源码/测试均无调用；前者直接 `run_agent_task`，后者自己调用模型 HTTP，现行文风入口使用正式任务与后续审查。 | **中高可信旧功能簇**。先核对项目资产是否仍依赖它们生成的文件格式和外部 Python 调用，再分别退役；不能因此删除当前 `style_prompt.md` 资产读取。 |
| C27 | 无调用的 Agent JSON patch 规划：Engine `prompting/agents/json_builder.py` | `plan_agent_patch` 只有定义，`build_agent_json` 的唯一调用来自 `plan_agent_patch`，模块内仍有旧直连 `run_agent_task` 提示。 | **高可信内部孤岛**。检查外部维护者入口后整模块退役或归档研究代码；保留其他模块仍使用的 `prompting.agents.schema` 校验器。 |
| C28 | 无调用的 Agent run 返修：Engine `prompting/agents/schema.py::repair_agent_run` | 只有定义；同文件 `validate_agent_run` 仍被其他旧 HTTP/任务路径调用。 | **中高可信孤立函数**。删除修复函数及只供它使用的辅助类型/提示后重跑该模块测试；不要移除 schema 校验。 |
| C29 | 无调用的旧多 Agent 审查委员会：Engine `literary/review/committee.py::run_agent_committee` | 全仓 Python 只有定义，模块内部独立调用 `run_agent_task` 生成多位 reviewer 意见；当前场景审读走 Studio 的独立 review 交易。 | **中高可信未接线功能**。检查外部 Python 消费和既有委员会产物读取后成包退役，不把它误作现行场景审读。 |
| C30 | 无调用的直连 Canon Agent 审查：Engine `literary/assets/canon/agent_review.py::review_canon_with_agent` | 全仓 Python 只有定义；内部直接调用 Provider 并写 `reviews/agent/canon_review.*`，当前 Canon 正式任务与确定性 lint 另有路径。 | **中高可信未接线功能**。核查旧审查产物读取与外部调用后退役本模块；保留 Canon lint、正式审查及持久化迁移。 |
| C31 | 无调用的项目种子批量生成包装：Engine `literary/assets/workshop.py::create_project_seed_candidates` | 只有定义，内部固定连续调用三次 `create_asset_candidate`；后者仍被旧 Engine HTTP 资产路由与 director 工具使用。 | **高可信孤立包装**。核对外部 Python 入口后只删这个批量包装；不能删 workshop 中仍被 HTTP/正式资产合同使用的单项能力。 |
| C32 | 写死旧实验运行目录的复现实验脚本：`workers/pi-worker/scripts/actor-task-sheet-spike.py` | `SOURCE` 和 `OUTPUT` 固定指向 `build/scene-performance-e2e/*-20260924`，代码只重放两名特定角色的冻结任务单；未被 Worker build/test/package 引用。`docs/testing/actor-task-sheet-archetype-2026-09-24.md` 保留了该实验入口。 | **低优先级研究档案候选**。若要保留可重复性，应参数化输入/输出并随测试夹具保存冻结样本；否则将脚本与结果说明一起归档。`actor-roleplay-spike.mjs` 被多份现行实验笔记引用，不能按同一证据删除。 |
| C33 | 无引用的能力登记数据类：Studio `runtime/capabilities/registry.py::RegisteredCapability` | 只有 `@dataclass` 定义，注册表实际将 `CapabilityHandler` 直接存在 `_handlers`，所有检索返回 handler；全仓无构造/类型引用。 | **高可信死类型**。核查外部插件是否按此私有路径导入后移除类型和不再需要的 dataclass import；保持注册表行为。 |
| C34 | 无调用的旧 CLI 提示参数读取：Engine `command_line/support.py::read_prompt_arg` | 全仓只有函数定义；当前 CLI parser/命令组没有引用它，函数仍解析旧 `--<label>-text` 风格文件参数。 | **高可信未用 helper**。核查维护者直调后移除，保留同模块仍被当前 CLI 使用的输出提示函数。 |
| C35 | v0.2 Runtime 状态别名：Studio `runtimes/__init__.py::runtime_status` | 函数只是转发 `agent_runner_status(config)`，自身注释标为 “Compatibility alias for the v0.2 API”；除 `__all__` 外没有内部调用。 | **低优先级兼容冗余**。先查旧客户端/外部 Python 使用和公布的移除窗口，再撤别名；当前 UI/runtime 使用 `agent_runner_status`。 |
| C36 | 受版本控制的派生前端入口：`desktop/dist/index.html` | 文件由 `scripts/sync-desktop-frontend.mjs` 每次构建从 `src/literary_engineering_studio/frontend/dist/index.html` 覆盖，记录含构建哈希的 JS/CSS 名；对应 `desktop/dist/ui/assets` 被忽略，未跟踪。`npm run client:build` 和桌面打包都执行同步。 | **明确冗余构建产物**。研究将该 HTML 也从 Git 移出、在首次桌面构建前生成；先验证 Tauri dev/CI 对空 `frontendDist` 的行为，避免新 checkout 缺入口。 |
| C37 | 旧场景直连生成 Provider：Engine `literary/scene/generation_provider.py` 与顶层 `generation_provider.py` | `generate_scene_candidate` 在仓库内只有定义和 `tests/test_style_mount_scene_chain.py` 调用；正式 scene 命令被 `verify_compatibility_surface.py` 明确禁止导入该 Provider。兼容清单将 `HttpChatProvider` 定为仅旧手工使用、`DryRunProvider` 定为仅测试，并保护顶层别名到 1.0.0。 | **生产死路径、公开兼容受保护**。1.0.0 以后结合外部消费者与旧项目审计退役；在此之前不能删顶层别名或其实现。正式 Task 生成路线保持。 |

## 遍历范围与判断方式

本轮枚举了 **2391 个 Git 已跟踪文件**（源码 `src/` 1260、客户端 312、测试 305、文档 377、Worker 41、脚本 27、桌面 14、协议 13、基准 9、打包 8，其余为合同、示例、CI 和许可证）。对 Python 顶层符号做词元引用扫描，对 Vue/TypeScript 从 `client/src/main.ts` 做静态与字面量动态导入可达性扫描，对 Worker 从 `main.ts` 做相同检查，再用逐项源码阅读、全仓引用、路由注册、包资源和兼容清单复核候选。扫描只用于发现线索；动态反射、第三方插件和外部消费者无法由仓库内零引用证明不存在。

| 域 | 本轮检查结果 |
| --- | --- |
| Engine／Studio | 核对主入口、公开 API、根目录转发、CLI、场景路径、旧直连 Agent 工具、读模型版本、历史数据读者；候选见 C01–C02、C04、C09–C19、C21–C31、C33–C35、C37。架构审计无新增依赖违规或循环；16 个超大文件与 76 个函数债务是重构压力，不能直接等同死代码。 |
| Vue 客户端 | 在 202 个非测试 TS/Vue/声明/JSON 源文件中，188 个从入口可达；14 个不可达项里 `env.d.ts`、生成类型和测试 harness/夹具属于构建或测试输入，其余经人工复核进入 C03、C05–C08。C20、C24 另由模板和方法调用核查得出。 |
| Pi Worker | 21 个 `src` TS/声明文件中，20 个从 Worker 入口可达；唯一未由 import 到达的 `assets.d.ts` 是 TypeScript 类型声明，不能删除。两个 spike 脚本按研究记录核对，只有写死历史输出的 C32 是整理候选。 |
| 桌面、打包、CI | 检查 Tauri 启动、sidecar 和 Pi Worker 资源、平台打包脚本及 CI/发布调用；未见可直接删除的运行模块。C36 是可再生且被 Git 跟踪的 HTML。第三方 Pi 许可证与 notice 被打包器复制，必须保留。 |
| 协议、基准、脚本、合同 | 编排/观测 schema 有测试读取；v1 Agent schema 双份见 C19。基准与多数脚本是显式维护者入口，不能因运行时不 import 就归为死代码。导出的 OpenAPI 与客户端类型是生成合同。 |
| 测试与文档 | 将只覆盖旧实现的测试与其生产候选绑定，避免单独删除有价值的行为断言。历史方案/实验笔记是审计证据，不因文件名旧而清理。 |

仓库还有未跟踪的 `onetake-film/`、`hw10/`、`work/`、`docs/video/` 等目录，以及本轮创作内核新文件；它们可能是并行工作或用户材料，不作为清理候选，也未执行移动或删除。

## 建议退役顺序

1. 先处理私有死函数、未连接 DTO、未挂载前端及其样式（C07–C08、C11–C15、C20、C33–C34），每包只改一个所有者模块并保留有用断言。
2. 再处理旧场景预演与补长（C01–C02、C09–C10、C23），在按需路径补足人格续演、候选权限和审读回归。
3. 最后按版本化兼容退役 Advisor、顶层别名、旧 CLI/直连 Provider、旧 HTTP 与 v1/strict-v1。C19 先解决双份 schema 漂移；C36 先验证空 checkout 的桌面构建。

## 保护条件

`strict-v1` 仍是旧作品与回退路线；Engine 公开别名与旧 HTTP 有 `remove_not_before: 1.0.0`；Advisor 会话表被 Project Agent 复用。角色 Agent 的人格化身份初始化是文学创作要求，不能以“提示较长”或“重复人物资料”为由裁撤。历史项目迁移读者、正式 PromptProgram v3、Worker 的 `assets.d.ts`、第三方许可证及已被正式入口调用的代码也不属可删除项。它们不能因名称含 `legacy` 或静态扫描不可达就删除。
