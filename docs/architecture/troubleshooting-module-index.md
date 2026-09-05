# ArcVellum 故障反查与模块定位

> 用途：从用户可见症状定位唯一主模块、稳定入口和最小验证集。
> 本文只负责导航，不替代 [模块目录](module-catalog.md) 和
> [Agent 面向接口开发标准](agent-interface-development-standard.md)。

## 使用方式

1. 按症状找到唯一 `primary_module`；
2. 读取稳定入口、对应合同测试和一个真实 adapter；
3. 填写 Module Change Packet；
4. 先用最小复现证明归属，再修改；
5. 修复后先跑定向测试，再按影响面扩大验证。

不要通过放宽 Gate、扩大 `expected_outputs`、伪造 completion、删除审查或提高重试次数来掩盖根因。

## 运行与推进

| 用户可见症状 | 主模块 | 首读入口 | 最小验证 |
|---|---|---|---|
| `sandbox output still fails deterministic preflight` | Studio `preflight/` | `preflight/task_preflight.py` | `tests/test_task_preflight.py`、对应文学合同测试 |
| Agent 改了允许输出之外的文件 | Studio `runtime/` | `runtime/sandbox.py`、`runtime/sandbox_writeback.py` | `tests/test_sandbox.py` |
| `Studio run already exists` | Studio `runtime/` | `runtime/sandbox.py::stage_task` | `SandboxTests.test_generated_run_ids_are_unique_within_the_same_second` |
| 同一任务反复出现、无正式进展 | Studio `automation/`，必要时 Engine `workflow/` | `automation/run_loop.py`、`automation/run_result_handler.py`、`public/workflow.py` | `tests/test_autopilot.py`、对应 route 状态测试 |
| 已完成审查仍回到同一审查 | 对应 Engine `routes/<route>/` 与 `workflow/state_*` | 当前 route definition/blueprint 与状态派生函数 | 对应 route contract + workflow order 测试 |
| 任务产物存在但 completion 无效 | Engine `tasking/` | `public/tasking.py`、sidecar lifecycle | `test_task_lifecycle_facade.py`、task contract tests |
| 自动创作启动后才发现模型未配置 | Studio `runtime/` | `runtime/readiness.py`、`runtime/runtime_selection.py` | `tests/runtime/test_runtime_readiness.py` |
| 模型长时间无可见活动或流断开 | 对应 `runtimes/` adapter | `runtimes/base.py::AgentRuntimePort`、具体 adapter | adapter contract、runtime benchmark、连续 E2E |
| 本地测试看似修改无效、堆栈指向另一个 checkout | 仓库测试入口 | `scripts/verify_checkout_import.py`、`scripts/run_tests.ps1` / `.sh` | `tests/test_checkout_verifier.py`，随后使用统一脚本跑目标测试 |

## 文学工程

| 用户可见症状 | 主模块 | 首读入口 | 最小验证 |
|---|---|---|---|
| 场景库存行数、字数或章节分配不符 | Engine `literary/planning/` | `materialization_parser.py`、`materializer.py` | `test_longform_materializer.py` |
| `participants` 含括号说明或无法匹配人物 | Engine `literary/planning/`，随后是场景人物资产 Gate | `materialization_parser.py::_participant_errors`、`workflow/state_scene.py` | `test_longform_materializer.py`、`test_scene_character_assets.py` |
| 文风评估完成后仍循环 | Engine `literary/style/` 与 `routes/style/` | `literary/style/review.py`、`routes/style/definition.py` | `test_style_evaluation_loop.py` |
| 故事架构审查要求 revise 后卡住 | Engine `routes/longform/` | `routes/longform/gates.py`、`blueprints.py`、`workflow/state_longform.py` | `test_story_architecture_contract.py` |
| 正文审查、修订、晋升相互错位 | Engine `routes/scene/` | `routes/scene/blueprints.py`、`gates.py` | scene workflow、promotion、revision tests |
| Canon 或人物状态无法写回 | Engine `routes/review/` 或 scene state | 对应 blueprint/gate 与 `literary/scene/state/` | canon/state writeback contract tests |
| 正文字数看似够但 Gate 判断不一致 | Engine `foundation/` 与 planning/review | `foundation/text_counts.py`、`foundation/draft_text.py` | text-count、target-length tests |
| 同一 Scene YAML 在 Context、字数、节奏或人物模块中得到不同结果 | Engine `literary/scene/` | `literary/scene/facts.py` | `tests/test_scene_facts.py` 加对应消费模块合同测试 |
| 前场已经完成但长篇审计未发现缺失交接或后场未承接 | Engine `literary/review/` | `literary/review/longform_handoffs.py`、`longform_contract.py` | `tests/test_longform_quality_contract.py`、`tests/test_scene_handoff.py` |
| 旧 source-ingest 项目要求读取不存在的 archaeology aggregate | Engine `routes/source_ingest/` | `routes/source_ingest/blueprints.py`、`support.py` | `tests/test_source_ingest_route.py`；确认 v1 为 `migration-only`，新导入使用 v2 |

## 产品、桌面与前端

| 用户可见症状 | 主模块 | 首读入口 | 最小验证 |
|---|---|---|---|
| 页面 `Cannot fetch` 或 API 不可用 | Studio `application/` 生命周期与 `api/` adapter | `application/bootstrap.py`、`api/routers/application.py` | bootstrap、API surface tests |
| 安装器缺 sidecar、Pi Worker 或资源 | `packaging/` 与 Tauri resources | `packaging/build_desktop.ps1`、`desktop/src-tauri/tauri.conf.json` | bundle verify、desktop build |
| Linux/macOS 打包测试误用 Windows 假设 | `packaging/` | 目标参数与 receipt contract | `tests/test_pi_worker_bundle.py` |
| 星仪节点、关系或交互错误 | Vue `features/orrery/` | `services/orreryClient.ts` 与 camera/layout/curves/nodes/edges | Orrery unit + Playwright visual checks |
| 前端选择未传入后端 | 对应 Vue feature client 与 API router | `features/<feature>/services/*Client.ts`、对应 router | feature client contract + API test |

## 跨模块升级规则

只有稳定合同确实变化时才扩大修改面：

1. Engine 先提交 public/task contract；
2. Studio application/runtime adapter 再迁移；
3. API 只适配 DTO；
4. Vue 只通过 feature client 消费；
5. 每层保持独立提交和可回滚测试证据。
