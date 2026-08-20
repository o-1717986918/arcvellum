# ArcVellum 模块所有权图

> 本文件由 `python scripts/generate_module_map.py` 生成。它描述模块所有权与依赖边界，
> 不描述创作 Agent 的操作流程，也不替代正式 TaskPackage。

| 路径 | 文件数 | 所有者 | 公开入口 | 可依赖 | 不得拥有 |
|---|---:|---|---|---|---|
| `src/literary_engineering_studio_engine/foundation` | 11 | Engine foundation | `package exports` | standard library | Studio runtime or UI |
| `src/literary_engineering_studio_engine/tasking` | 19 | Formal task contracts | `tasking/__init__.py` | Engine foundation | Agent execution |
| `src/literary_engineering_studio_engine/routes` | 32 | Formal route catalog | `routes/catalog.py` | tasking and literary services | Studio lifecycle |
| `src/literary_engineering_studio_engine/workflow` | 29 | Workflow projections | `workflow_state facade` | tasking and routes | Runtime adapters |
| `src/literary_engineering_studio_engine/literary` | 125 | Literary domain | `domain package exports` | foundation and task contracts | FastAPI or Provider SDKs |
| `src/literary_engineering_studio_engine/prompting` | 11 | Prompt programs | `prompt registry/compiler` | literary contracts | Provider transport |
| `src/literary_engineering_studio_engine/orchestration` | 6 | Read-only orchestration catalog | `orchestration/__init__.py` | task and Gate catalogs | Planner execution |
| `src/literary_engineering_studio_engine/projections` | 13 | Engine read projections | `projection facades` | formal project facts | promotion/writeback |
| `src/literary_engineering_studio_engine/command_line` | 22 | Engine CLI adapter | `command_line/main.py` | Engine public services | literary business rules |
| `src/literary_engineering_studio/application` | 47 | Studio use cases | `application services` | ports and Engine contracts | API/framework adapters |
| `src/literary_engineering_studio/automation` | 11 | Campaign control | `automation/controller.py` | application/runtime ports | Engine route implementations |
| `src/literary_engineering_studio/orchestration` | 51 | Adaptive plan domain | `orchestration services` | Engine catalog and ports | API or task lifecycle |
| `src/literary_engineering_studio/runtime` | 92 | Controlled execution | `runtime worker/bundle ports` | contracts and infrastructure ports | literary route policy |
| `src/literary_engineering_studio/runtimes` | 18 | Agent adapters | `runtimes registry` | Runtime SPI and external SDKs | Engine route implementations |
| `src/literary_engineering_studio/persistence` | 27 | Durable adapters | `repository facades` | SQLite and file storage | literary decisions |
| `src/literary_engineering_studio/projections` | 27 | Studio read models | `projection services` | read ports and Engine facts | promotion/writeback |
| `src/literary_engineering_studio/preflight` | 18 | Writeback validation | `task_preflight facade` | contracts and deterministic validators | Agent creativity |
| `src/literary_engineering_studio/observability` | 24 | Events and telemetry | `observability projections` | event contracts | task mutation |
| `src/literary_engineering_studio/integrations` | 17 | External integrations | `integration-specific facades` | external SDKs and ports | literary policy |
| `src/literary_engineering_studio/api` | 24 | HTTP/SSE adapters | `router factories` | application use cases | direct project mutation |
| `src/literary_engineering_studio/advisor` | 6 | Read-only advisor | `advisor service` | read models and Runtime port | formal project writeback |
| `workers/pi-worker/src` | 14 | Bounded Pi Worker | `main.ts / worker.ts` | Pi SDK and task contract | formal project access |
| `desktop/src-tauri/src` | 1 | Desktop host | `main.rs` | Tauri commands and sidecar protocol | literary logic |

## Vue Feature 所有权

| Feature | 文件数 | 规则 |
|---|---:|---|
| `advisor` | 8 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `archaeology` | 14 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `archive` | 24 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `delivery` | 2 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `details` | 2 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `help` | 1 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `library` | 1 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `observatory` | 2 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `onboarding` | 0 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `orrery` | 58 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `projects` | 2 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `quality` | 5 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `reader` | 1 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `settings` | 4 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `strategy` | 8 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `style-atelier` | 19 | 只通过 feature client、共享只读合同或命令总线跨域协作 |
| `workflow` | 2 | 只通过 feature client、共享只读合同或命令总线跨域协作 |

## 机器检查

- `python scripts/architecture_audit.py`：依赖方向、债务棘轮、循环和复杂度；
- `python scripts/generate_module_map.py --check`：本图是否与目录同步；
- `python -m unittest tests.test_architecture_audit tests.test_module_dependency_direction -v`：边界行为。
