# ArcVellum 文学工程正式路径静态审计与修复实施方案

> 文档性质：代码级静态审计、风险说明与强指导性修复方案
> 审计日期：2026-09-01
> 审计基线：`f562b9a`
> 审计分支：`feat/v099-modular-e2e`
> 审计仓库：`literary-engineering-studio-v099-work`
> 审计范围：Embedded Engine 正式文学路线、Studio 自动推进、任务包、沙箱写回、跨场景连续性、Canon、长篇规划、文风、审查、晋升与交付
> 结论：架构可继续演进，无需整体重写；单场景闭环成熟，多场景无人值守连续创作仍有必须先修复的跨场景断点

---

## 实施记录（2026-09-05）

第一批源码修复已经完成并通过 60 项聚焦回归测试：

- Scene Route 已纳入 Canon review、按需 approval、apply 与 revision/defer 状态；Canon apply 统一使用 `canon/applied/`，同时绑定应用前候选摘要和应用后补丁摘要。
- `scene-handoff` 已进入正式 Scene 状态机和 route audit。Handoff 由确定性投影器在 State、Canon 与 Continuity 各自完成独立语义审查和 apply 后生成，避免额外增加一次重复、昂贵的 Agent 判断。
- Handoff v2 绑定 promoted draft、State、Canon、Continuity 的正式凭据摘要；任一已应用证据被改动后，handoff 会失效。
- Memory Index 升级为带全量源快照的 v2 索引；检索发现源资产变化时自动重建。
- 地点和组织 Canon 已进入 Context Packet 的硬上下文集合。
- 所有路线的未知状态兜底已由 `manual-route-repair` Agent 任务改为 `route-diagnostic-boundary` 人工维护边界，禁止自动调用 Agent、提交空产物或重复重试。

实现与原计划存在一项有意差异：本文早期建议为 Handoff 新增语义 Agent 任务；实际审查源码后确认 State、Canon 与 Continuity 已分别承载所需语义判断，因此 Handoff 采用确定性、摘要绑定的最终投影更符合低成本、高鲁棒性原则。

第二批源码修复已完成并通过 120 项聚焦回归测试：

- 字数预算、场景库存、章节义务均已拆分为 Writer 候选、确定性 review prepare、身份独立 Reviewer、按裁决修订/阻断四段闭环。
- 三类审查以摘要绑定 JSON 为机器权威，Markdown 仅供阅读；Writer 与 Reviewer 会话相同、候选被改动、缺少维度或只写“pass”文字都会被拒绝。
- `revise` 使用锁定的修订前摘要验证旧裁决，候选改变后必须重新生成 review task 并取得新裁决，避免修订流程自锁或沿用旧结论。
- 正式 Writer 身份被纳入沙箱证据集，审查任务复制到临时工作区后仍能核验来源，不会因只看到精简资料集而反复越界读取。
- 长篇 materializer、Scene Route 与 route audit 统一要求三项独立审查通过。
- 本批同步拆分 CLI parser、Canon approval/apply status、Scene writeback gates、handoff 构造与长篇审查蓝图；架构审计重新达到零新增违规。
- 最终验收：Prompt Registry 59 个资产覆盖 73 个任务提示词 ID；架构审计 `ok: true`；全量回归 `1332 tests passed, 1 skipped`。

第三批源码修复完成了 Batch 5 的权威收敛与兼容清理：

- Longform Audit 已将 Scene Handoff 纳入正式快照、摘要和阻断项，并检查相邻场景之间的宏观因果桥；缺失、失效或未覆盖下一场的 handoff 会进入长篇审计结果。
- 对外 Task Package 不再暴露 `next_allowed_states`。下一状态继续由 workflow artifact、Gate 和 route state 推导，Blueprint 内部的声明只作装配提示，不形成第二套状态机权威。
- Scene YAML 统一由 `literary/scene/facts.py` 的 ruamel YAML 边界解析。Context、Scene Route、节奏、字数预算、读者体验、Prompt、人物状态、Canon 和长篇分析不再各自用正则解释同一份正式场景文件。
- 统一解析器保留两项既有公开语义：精简沙箱没有 Scene YAML 时返回可诊断的空事实投影；叙事节奏契约中的 YAML 标量继续按历史字符串类型输出。
- `source-ingest/v2` 仍是所有新导入的默认正式路线。v1 被显式标记为 `migration-only`，任务只读取旧 source chunks 与 evidence index，不再错误要求不存在的 archaeology aggregate；旧项目继续保留候选区、修订和 clean-pass 门禁。
- 删除未接入的 Export audit helper；新增 checkout import 验证和 PowerShell/Bash 统一测试入口，文档不再建议直接调用可能命中其他 editable checkout 的全局 Python。
- Architecture Audit 保持 `16` 个既有 file debts、`104` 个既有 function debts、`0` 新增循环和 `0` Studio-to-Engine 反向依赖；Prompt Registry 仍以 `59` 个资产覆盖 `73` 个任务提示词 ID。

第三批最终验收：checkout 验证确认 Studio 与 Engine 均加载当前工作树；全量回归 `1339 tests passed, 1 skipped`。后续批次不得恢复手写 Scene YAML 解析器、公开下一状态提示或 Legacy v1 新建入口。

---

## 0. 文档用途

本文既记录当前代码事实，也给出可以直接实施的修复顺序。负责修复的开发 Agent 即使不了解历史讨论，也应能够通过本文定位模块、建立测试、完成修改并验收。

本文中的优先级含义：

- **P0**：会阻断正式多场景创作，或让后续场景建立在不完整事实之上，必须在下一个稳定版本前完成。
- **P1**：会降低文学可靠性、恢复能力或无人值守成功率，应紧接 P0 完成。
- **P2**：不会立刻阻断主链，但会扩大维护成本、数据分歧或未来回归风险。
- **P3**：清理项，可与相邻模块重构一并完成。

修复时必须遵守以下边界：

1. 不得通过删除 handoff、Canon、审查或上下文门禁来让状态变绿。
2. 不得让 Agent 直接写正式 Canon、正式正文或最终 handoff。
3. Agent 负责文学判断；系统负责身份、摘要、路径、状态、写回和验证。
4. 新增正式产物必须进入任务包、状态机、route audit、长篇审计和恢复链。
5. 修复不得复制第二套状态机或第二套 Canon 服务，应复用现有 Task Package、Gate、Approval、Apply 和 Writeback 能力。
6. 每一批修复都必须先有失败测试，再修改实现，再完成聚焦测试和全量测试。

---

## 1. 审计方法与已验证事实

### 1.1 实际检查范围

本轮逐层检查了：

- `src/literary_engineering_studio/automation/`
- `src/literary_engineering_studio/runtime/`
- `src/literary_engineering_studio_engine/workflow/`
- `src/literary_engineering_studio_engine/routes/`
- `src/literary_engineering_studio_engine/literary/`
- `src/literary_engineering_studio_engine/tasking/`
- `src/literary_engineering_studio_engine/prompting/`
- `tests/`、`tests/contracts/`、`tests/orchestration/`
- 架构质量基线与模块边界审计脚本

### 1.2 正式路线顺序

当前 Studio 自动创作顺序由 `src/literary_engineering_studio/automation/controller.py` 的 `ROUTE_ORDER` 定义：

```text
source-ingest
  -> longform-planning
  -> style-engineering
  -> character-and-world-assets
  -> scene-development
  -> review-and-audit
  -> export-and-release
```

### 1.3 测试与架构基线

在显式绑定当前仓库 `src` 后，全量 Python 测试结果为：

```text
Ran 1318 tests in 261.929s
OK (skipped=1)
```

架构审计结果：

```text
ok: true
violations: []
```

这证明当前模块级契约、绝大多数单步 Gate、任务写回和兼容表面稳定。它不能证明真实多场景生命周期已经闭合，因为现有“三章全自动”测试使用伪 Worker 直接生成章节导出文件，没有执行真实 scene-development 的每一项任务。

对应测试：

```text
tests/test_autopilot.py
  test_full_auto_three_chapter_direction_to_docx
```

### 1.4 已达到较高成熟度的部分

以下能力在代码和测试中已经形成可靠基础，修复时应保留：

- Scene Character Asset 前置解析与资产依赖暂停。
- Context Packet 与 Context Trace。
- RP、分支、构图、正文任务的显式 sidecar。
- 场景字数、读者体验、叙事节奏和文风契约。
- 正文候选来源、精确候选审查、修订和晋升摘要绑定。
- Style Lint、静态审查、状态演化、连续性台账。
- 文风学习的候选、审查、评分、版本和挂载。
- 人物与世界资产的候选、独立审查、审批和晋升。
- Markdown、DOCX、布局检查和最终发布。
- 沙箱读写边界、Preflight、Writeback Preview、Mutation Receipt 和恢复机制。

---

## 2. P0：跨场景 handoff 没有进入正式路线

### 2.1 代码位置

消费端：

```text
src/literary_engineering_studio_engine/literary/scene/context/packet.py
  build_context_packet()
  约第 287 行调用 scene_handoff_status()

src/literary_engineering_studio_engine/literary/scene/context/handoff.py
  scene_handoff_status()
  约第 106-130 行
```

生产端：

```text
src/literary_engineering_studio_engine/literary/scene/context/handoff.py
  build_scene_handoff()

src/literary_engineering_studio_engine/command_line/commands/longform.py
  仅 scene-handoff 手工命令调用 build_scene_handoff()
```

场景状态机：

```text
src/literary_engineering_studio_engine/workflow/state_scene.py
  _scene_state()
  当前最后一步是 continuity-ledger-apply
```

任务蓝图：

```text
src/literary_engineering_studio_engine/routes/scene/writeback_blueprints.py
  continuity-ledger-apply 之后 next_allowed_states 指向 ready
```

### 2.2 当前因果链

```text
scene_0001 晋升并完成 State/Canon 候选与 continuity ledger
  -> scene_0001 在 scene-development 中变为 ready
  -> Autopilot 选择 scene_0002
  -> context 为 scene_0002 调用 scene_handoff_status()
  -> 发现 scene_0001 已有 promoted draft
  -> 强制要求 workflow/handoffs/scene_0001.json
  -> 正式路线从未创建该文件
  -> scene_0002 context trace 阻断
```

### 2.3 影响

- 单场景测试可以全部通过，多场景真实运行仍会在第二场 Context 处停止。
- Agent 可能反复重跑 Context，形成 no-progress 或额度浪费。
- 用户手工运行 `scene-handoff` 可以暂时绕过，但与 CLI 状态机唯一入口原则冲突。
- 当前全自动能力无法被视为可靠的整书连续生产能力。

### 2.4 目标设计

新增正式三段式 handoff：

```text
continuity-ledger-apply
  -> scene-handoff-prepare       # 确定性事实骨架
  -> scene-handoff-agent-task    # 主 Agent 补全文学语义
  -> scene-handoff-ready         # 系统合并、绑定摘要并验证
  -> scene ready
```

推荐产物：

```text
workflow/handoffs/scene_0001.machine.json
workflow/handoffs/scene_0001.agent_tasks.md
workflow/handoffs/scene_0001.semantic.json
workflow/handoffs/scene_0001.agent_completion.json
workflow/handoffs/scene_0001.json
```

其中：

- `machine.json` 由确定性代码生成，记录正式正文、晋升、State apply、Canon apply、continuity apply 的路径与摘要。
- `semantic.json` 由主 Agent 填写文学解释，只能写任务声明的语义字段。
- 最终 `.json` 由系统合并并写入，Agent 不直接写最终文件。
- `scene_handoff_status()` 只接受最终 `.json`。

### 2.5 建议 Schema

```json
{
  "schema": "arcvellum/scene-handoff/v2",
  "source_scene_id": "scene_0001",
  "successor_scene_id": "scene_0002",
  "evidence": {
    "promoted_draft": {"path": "...", "sha256": "..."},
    "promotion_manifest": {"path": "...", "sha256": "..."},
    "state_apply": {"path": "...", "sha256": "...", "status": "applied"},
    "canon_apply": {"path": "...", "sha256": "...", "status": "applied_or_not_required"},
    "continuity_apply": {"path": "...", "sha256": "...", "status": "applied"}
  },
  "time_after": "...",
  "location_after": "...",
  "character_state_deltas": [],
  "relationship_debts": [],
  "unresolved_actions": [],
  "objects_in_motion": [],
  "information_distribution": [],
  "outgoing_hooks": [],
  "emotional_aftertaste": "...",
  "causal_pressure_for_next_scene": "...",
  "writer_session_id": "...",
  "source_digest": "...",
  "status": "complete"
}
```

所有列表允许为空，但必须给出 `none_reason` 或由任务明确判断为无此类变化。系统不能把“Agent 没填写”与“本场确实没有”视为同一状态。

### 2.6 代码级修改清单

1. 在 `literary/scene/context/handoff.py` 拆分：
   - `prepare_scene_handoff_machine()`
   - `prepare_scene_handoff_task()`
   - `finalize_scene_handoff()`
   - `scene_handoff_status()`
2. 新增 `literary/scene/context/handoff_contract.py`：
   - Schema 常量。
   - 路径函数。
   - 语义字段校验。
   - apply 摘要校验。
3. 在 `workflow/state_scene.py::_scene_state()` 加入三个正式步骤。
4. 在 `routes/scene/writeback_blueprints.py` 增加三个蓝图。
5. 在 `routes/scene/gates.py` 增加 handoff Preflight 和 Task Complete Gate。
6. 在 `workflow/audit/scene.py` 增加 handoff 路线门禁。
7. 在 `tasking/semantic_contracts.py` 注册 handoff semantic artifact。
8. 新增 Prompt Asset，例如：
   - `route.scene-development.handoff.semantic.v1.md`
9. 保留 `scene-handoff` 兼容命令，但让其调用同一正式服务，禁止生成未完成最终文件。

### 2.7 必须新增的测试

```text
tests/test_scene_handoff.py
  test_missing_semantic_handoff_cannot_pass
  test_handoff_binds_all_apply_manifests
  test_handoff_rejects_stale_state_or_canon_apply
  test_handoff_distinguishes_empty_from_unanswered

tests/test_scene_workflow_order.py
  test_scene_one_ready_requires_formal_handoff
  test_scene_two_context_opens_after_scene_one_handoff

tests/test_task_contract_transport.py
  test_handoff_task_has_exact_sources_outputs_and_semantic_contract

tests/test_two_scene_formal_e2e.py
  test_two_scenes_cross_context_state_canon_and_continuity
```

### 2.8 验收条件

- 完成 scene_0001 后，无需任何手工 CLI，`task-next` 自动返回 scene handoff 任务。
- handoff 完成后，scene_0002 Context Trace 通过。
- 修改 scene_0001 正文、State apply、Canon apply 或 continuity apply 中任意一个文件都会使 handoff 失效。
- Agent 未填写任意强制语义字段时 Preflight 明确指出字段，而不是给出通用 deterministic preflight 错误。

---

## 3. P0：handoff 的 Canon apply 路径错误

### 3.1 代码位置

错误读取：

```text
src/literary_engineering_studio_engine/literary/scene/context/handoff.py
  build_scene_handoff()
  canon/patches/{scene_id}_canon_apply.json
```

实际写入与 Gate：

```text
src/literary_engineering_studio_engine/routes/review/canon_gates.py
  canon_patch_apply_gate_errors()
  canon/applied/{patch_id}_apply.json
```

### 3.2 修复方案

不要在 handoff 中再次拼接路径。建立一个 Canon 公共路径接口：

```text
src/literary_engineering_studio_engine/literary/assets/canon/paths.py
```

建议接口：

```python
def canon_patch_path(root: Path, patch_id: str) -> Path: ...
def canon_apply_manifest_path(root: Path, patch_id: str) -> Path: ...
def canon_approval_path(root: Path, patch_id: str) -> Path: ...
def canon_patch_id_for_scene(root: Path, scene_id: str) -> str: ...
```

所有 Canon route、handoff、审计和 Library Projection 统一调用该接口。

### 3.3 验收条件

- 全仓库不再出现第二处手工拼接 Canon apply 路径。
- handoff 引用的 Canon apply 文件与 `canon_patch_apply_gate_errors()` 验证的是同一文件。
- Patch ID 不等于 Scene ID 时仍能正确解析。

---

## 4. P0/P1：Canon 生效时序晚于后续场景

### 4.1 代码位置

```text
src/literary_engineering_studio_engine/workflow/state_scene.py
  _canon_writeback_step()
  仅验证 Canon 候选写回状态

src/literary_engineering_studio_engine/workflow/state_review_audit.py
  _canon_backlog_step()
  在所有 scene-development 之后处理 approval 与 apply

src/literary_engineering_studio/automation/controller.py
  ROUTE_ORDER
```

### 4.2 当前风险

scene_0001 已经确定的地点变化、组织变化、世界事实和时间线事实，可能只存在于待审批 Patch。scene_0002 的 Context Packet 直接读取正式 Canon，因此无法保证看见 scene_0001 的新事实。

这会产生一种危险状态：每个场景自身都通过门禁，场景之间仍可能发生事实回退。

### 4.3 推荐修复

将“场景来源的 Canon Patch”改为 scene-local commit：

```text
canon-evolve candidate
  -> independent canon patch review
  -> approval or delegated approval
  -> canon apply
  -> continuity ledger
  -> scene handoff
```

`review-and-audit` 继续负责：

- 全项目 Canon Lint。
- 跨场景冲突与时间线审查。
- 委员会终审。
- 对发现的问题发起新的修订 Patch。

它不再是场景 Canon 第一次生效的位置。

### 4.4 复用现有能力

不得复制 `state_review_audit.py` 的审批和 apply 逻辑。应把以下能力提取为共享服务：

```text
literary/assets/canon/backlog.py
literary/assets/canon/approval.py
literary/assets/canon/apply.py
routes/shared/canon_writeback.py 或 application 层 CanonWritebackCoordinator
```

Scene Route 和 Review Route 只组合同一服务。

### 4.5 自动模式与人工模式

- `assisted`：Canon 变更在场景边界暂停，等待用户批准、修订、拒绝或延期。
- `full_auto`：由已存在的 Delegation Policy 和 Steward 产生摘要绑定的决定。
- `defer`：不得允许后续场景直接忽略。系统必须把延期 Patch 作为显式 provisional context，并把它标为未正式生效；更推荐暂停自动场景推进。

### 4.6 必须新增的测试

- scene_0001 Canon apply 后 scene_0002 Context 必须包含新事实。
- rejected/revise/deferred Patch 不得被当成正式 Canon。
- full_auto 可产生合法 delegated approval，并继续进入 handoff。
- assisted 模式正确显示 Human Gate，不空转。

---

## 5. P1：长篇规划的三项自写自审

### 5.1 代码位置

```text
src/literary_engineering_studio_engine/routes/longform/blueprints.py
  budget-agent-task
  scene-inventory-agent-task
  chapter-obligation-agent-task
  当前候选和 Markdown review 同属一个任务

src/literary_engineering_studio_engine/workflow/state_common.py
  _longform_review_step()
  只解析 “结论：pass”

src/literary_engineering_studio_engine/routes/longform/gates.py
  _validate_candidate_review()
  缺少候选摘要、Reviewer 身份和结构化审查契约
```

### 5.2 文学影响

Scene Route 会非常严格地执行这些宏观产物。如果场景库存因果量不足、章节义务空泛或预算扩纲只是数字拼接，后续系统会高成本地生成一部结构上已经先天不足的作品。

故事架构已经使用独立 Reviewer、精确摘要和 revision loop，说明仓库中已有正确范式。

### 5.3 目标状态机

三种规划产物分别采用：

```text
candidate-prepare
  -> candidate-agent-task
  -> review-prepare
  -> independent-review-agent-task
  -> pass | revision | block
  -> exact-candidate revision
  -> fresh review
```

### 5.4 结构化审查 Schema

```json
{
  "schema": "arcvellum/longform-planning-review/v1",
  "artifact_kind": "scene_inventory",
  "candidate_path": "...",
  "candidate_sha256": "...",
  "budget_sha256": "...",
  "writer_session_id": "...",
  "reviewer_session_id": "...",
  "status": "complete",
  "verdict": "pass|revise|block",
  "checked_dimensions": [],
  "findings": [],
  "required_changes": []
}
```

最低审查维度：

- `word_budget_expansion`：目标字数闭合、事件库存、卷章功能、因果密度、详略分配、支线负载。
- `scene_inventory`：精确场景数、ID 连续性、参与者身份、场景功能、冲突、信息释放、后果、承诺兑现、节奏角色。
- `chapter_obligation`：读者问题、承诺回报、暂扣信息、兑现窗口、反摘要要求、章间压力和章末功能。

### 5.5 代码级修改

1. 新增 `literary/planning/review_contract.py`，复用故事架构审查的摘要和会话独立逻辑。
2. 将 `workflow/state_longform.py` 中三项 review 拆成 prepare、review、revision。
3. 修改 `routes/longform/blueprints.py`，Writer 不再写 review。
4. 修改 `routes/longform/gates.py`，要求 JSON Review、候选摘要和独立会话。
5. Markdown Review 改为 JSON 的只读渲染，不再是权威状态。
6. `materializer.py` 的输入摘要应纳入通过的 Review JSON 摘要。
7. 添加三个独立 Prompt Asset，明确 Reviewer 不得改候选。

### 5.6 验收条件

- Writer 与 Reviewer session 相同必定失败。
- 修改候选后旧 review 自动 stale。
- 只把 Markdown 结论改成 pass 不能推进。
- revise 后必须修改精确候选，再生成新 review。
- Materialization Manifest 能追溯三个候选及其 review 摘要。

---

## 6. P1：`manual-route-repair` 无法通过正式写回修复

### 6.1 代码位置

```text
src/literary_engineering_studio_engine/tasking/package_contract.py
  TASK_TYPE_EXECUTION
  manual-route-repair -> agent-required

src/literary_engineering_studio_engine/routes/*/blueprints.py
  多数 fallback 声明 expected_outputs: []

src/literary_engineering_studio/runtime/capabilities/policy.py
  writable_paths 来自 task.expected_outputs
```

### 6.2 失败机制

Agent 收到“检查并修复路线”的任务，但沙箱没有任何合法写入路径。Agent 即使正确判断根因，也不能产出会被 Writeback 接受的修复。任务完成后正式状态不变，Autopilot 重复领取相同任务，最终触发 no-progress。

### 6.3 修复原则

未知状态不能自动变成泛化 Agent 修复任务。应分成：

1. `route-diagnostic`：确定性只读任务，输出结构化诊断，不声称修复。
2. `human-maintenance-boundary`：数据迁移或未知破损需要维护者处理时暂停。
3. `typed-route-repair`：系统知道目标时，声明明确 `repair_targets`、`expected_outputs` 和 Gate。

### 6.4 代码级修改

- 从 `TASK_TYPE_EXECUTION` 移除或弃用 `manual-route-repair`。
- 为每条 Route 的 fallback 返回 `route-diagnostic`，包含稳定错误码与定位信息。
- 在 `tasking/contract_audit.py` 增加不变量：
  - `agent-required` 且无 expected output 时，除纯决策语义任务外视为错误。
- 在 Autopilot 中将 `route-diagnostic` 视为可解释阻断，不进入 Agent 重试循环。
- 对已知迁移问题建立一任务一迁移命令，禁止使用自然语言命令充当修复入口。

### 6.5 验收条件

- 任意未知状态最多产生一次诊断事件。
- UI 显示稳定错误码、目标模块、建议动作。
- 不会因为 expected outputs 为空而启动创作 Agent。
- 所有真正的 Agent Repair 均有至少一个可写目标和精确完成 Gate。

---

## 7. P1：Memory Index 可能静默过期

### 7.1 代码位置

```text
src/literary_engineering_studio_engine/literary/scene/context/packet.py
  仅在 rebuild_index=True 或索引不存在时重建

src/literary_engineering_studio_engine/foundation/memory_index.py
  索引保存源文本块

src/literary_engineering_studio_engine/literary/scene/context/trace.py
  Trace 记录当前文件摘要，但没有证明检索块来自当前源版本
```

### 7.2 风险

Canon、人物、世界或大纲文件被修改后，检索可能仍返回旧文本。Context Trace 对当前源文件计算摘要，因此会出现“Trace 看起来新，检索内容实际旧”的假新鲜状态。

### 7.3 修复方案

给 Memory Index 增加内容寻址清单：

```json
{
  "schema": "arcvellum/memory-index/v2",
  "source_snapshot_sha256": "...",
  "sources": [
    {"path": "canon/world_rules.yaml", "sha256": "..."}
  ],
  "chunks": [
    {"chunk_id": "...", "source_path": "...", "source_sha256": "...", "text_sha256": "..."}
  ]
}
```

Context 构建前：

1. 计算可索引源的轻量快照。
2. 与 Index Manifest 比较。
3. 仅重建变更文件的 chunks。
4. 原子替换 Index。
5. Trace 记录 `memory_index_digest` 和每个命中块的 `source_sha256`。

### 7.4 验收条件

- 修改一个人物文件后，下一次 Context 自动更新对应 chunks。
- 未修改源时复用索引，不能造成明显吞吐退化。
- 伪造旧 chunk 或修改索引后 Trace 必须失败。

---

## 8. P1/P2：地点与组织约束未被保证进入硬上下文

### 8.1 代码位置

```text
src/literary_engineering_studio_engine/literary/scene/context/packet.py
  _packet_sections()
  直接嵌入 world_rules、timeline、facts、forbidden_changes
```

`canon/locations.yaml`、`canon/organizations.yaml` 目前主要依赖 Memory top-k，无法保证当前场景涉及的地点和组织必然命中。

### 8.2 修复方案

1. 使用结构化 Scene Facts 读取当前场景的 location、organization 和显式 asset refs。
2. 建立 Canon Asset Resolver：稳定 ID、别名、引用路径和歧义错误。
3. Context Packet 增加 `scene_bound_canon_assets` 硬区段。
4. 未解析的显式地点/组织引用在正式模式下阻断 Context，而不是退回模糊检索。
5. Memory top-k 继续作为补充资料，不承担硬事实完整性。

### 8.3 验收条件

- 当前场景声明地点后，该地点资产无论 top-k 结果如何都进入 Context。
- 同名地点或组织必须产生歧义错误。
- Prompt Projection 不得把硬 Canon 资产降级成可选摘要。

---

## 9. P2：`next_allowed_states` 未被消费且存在漂移

### 9.1 代码位置

`next_allowed_states` 广泛存在于：

```text
routes/style/
routes/assets/
routes/source_ingest/
routes/longform/
routes/scene/
routes/review/
routes/export/
```

当前没有正式消费者据此验证 Task Complete 后的新状态。

### 9.2 修复选择

推荐采用单一 Transition Registry：

```python
RouteTransition(
    route="scene-development",
    state="composition-agent-task",
    allowed_next=("candidate-generation-provenance",),
)
```

- Workflow State 和 Task Blueprint 从 Registry 派生状态顺序。
- `task-complete` 后重新计算状态，并验证它属于允许集合。
- 动态分支使用命名策略，例如 `review_outcome`，由系统展开允许状态。
- 如果短期不实施，则从任务包删除该字段，避免向 Agent 和 UI 提供不可信信息。

### 9.3 验收条件

- 不再由多个蓝图手工重复维护同一跃迁。
- CI 能检测不存在的状态名、逆序跃迁和死状态。

---

## 10. P2：Longform Audit 未纳入 handoff

### 10.1 代码位置

```text
src/literary_engineering_studio_engine/literary/review/longform_contract.py
  LONGFORM_AUDIT_SOURCE_PATHS
  _INPUT_GLOBS
```

当前输入快照不包含 `workflow/handoffs`。

### 10.2 修复方案

新增：

```text
workflow/handoffs/*.json
workflow/handoffs/*.semantic.json
workflow/handoffs/*.agent_completion.json
```

并增加审查维度：

- 每个已晋升且存在后继的场景必须有 handoff。
- handoff source/successor 顺序必须和正式 scene timeline 一致。
- 每个 handoff 的正文、State、Canon、continuity 摘要必须当前有效。
- outgoing hooks 与下一场 incoming pressure 至少存在一个可解释的因果连接。

不得把 Agent Tasks 文本本身作为文学输入；只纳入最终语义产物和完成凭据。

---

## 11. P2：核心 YAML 存在多套正则解析

### 11.1 当前事实

仓库已有基于 `ruamel.yaml` 的结构化 Scene Facts，但 handoff、state、rhythm、角色资产和部分 planning 仍使用 `_scalar()`、`_list_value()`、`_yaml_scalar()` 等正则读取。

示例：

```text
literary/scene/context/handoff.py
workflow/state_scene.py
literary/planning/narrative_rhythm.py
literary/scene/roleplay/lab.py
literary/scene/state/*
```

### 11.2 风险

- 多行字符串、引号、内联列表、注释和嵌套结构可能被不同模块解释成不同值。
- Scene Composer 使用结构化值，Handoff 使用正则值时，两个正式模块可能对同一场景产生不同理解。
- 格式变化可能通过单模块测试，却在跨模块路径中失效。

### 11.3 修复方案

1. 扩展 `literary/scene/facts.py` 为唯一 Scene YAML 读取入口。
2. 定义只读数据类：
   - `SceneIdentityFacts`
   - `ScenePlanningFacts`
   - `SceneRhythmFacts`
   - `SceneBridgeFacts`
   - `SceneAssetReferences`
3. 第一批迁移正式路径：Handoff、Context、Scene State、Composition、Rhythm。
4. 第二批迁移 UI Projection 和兼容命令。
5. 架构审计增加规则：正式 Engine 模块不得新增针对 YAML 键的正则解析。

### 11.4 验收条件

- 同一 Scene 文件的所有正式模块共享一份解析结果。
- 覆盖 quoted、multiline、inline list、nested map、Unicode 和注释测试。

---

## 12. P2：开发测试入口可能串到相邻旧仓库

### 12.1 本轮复现

在当前机器直接运行系统 Python 时：

```text
tests 来自 literary-engineering-studio-v099-work
被测包却来自 outputs/literary-engineering-studio/src
```

原因是系统环境保留了另一个 checkout 的 editable install。仓库 `.venv` 和显式 `PYTHONPATH=src` 使用的是当前代码。

### 12.2 当前文档风险

以下文件直接建议运行 `python -m unittest discover -s tests -v`：

```text
AGENTS.md
README.md
CONTRIBUTING.md
```

### 12.3 修复方案

- 新增唯一测试入口：

```text
scripts/run_tests.ps1
scripts/run_tests.sh
```

- 启动时验证 `literary_engineering_studio_engine.__file__` 位于当前仓库 `src`。
- 文档统一调用脚本或 `.venv` Python。
- CI 明确执行 `pip install -e ".[test]"`，随后打印包路径。
- 可增加 `scripts/verify_checkout_import.py`，在测试与构建前运行。

### 12.4 验收条件

- 当前机器即使存在其他 editable install，统一测试入口仍只加载当前 checkout。
- 测试报告打印 Commit、Python、Package Root 和工作树状态。

---

## 13. P2：架构基线通过，但现存复杂度债务较多

### 13.1 审计结果

架构审计没有发现新增边界违规，但基线允许 16 个超过 500 行的 Python 文件。优先关注：

```text
prompting/platform_tasks.py
literary/assets/workshop.py
routes/scene/blueprints.py
literary/style/lab.py
literary/assets/canon/evolver.py
workflow/runner.py
prompting/pack.py
workflow/state_scene.py
```

高复杂度热点包括：

```text
routes/scene/blueprints.py::_blueprint_for_state
workflow/state_scene.py::_scene_state 及其 Gate helpers
literary/planning/contracts.py::scene_word_budget_contract
literary/scene/promotion/readiness.py::scene_readiness_status
tasking/contract_audit.py::_audit_task
```

### 13.2 收敛原则

- P0 修复优先通过新建聚焦模块实现，不继续扩大上述大文件。
- Route State 只组合 Step Provider，不承担领域解析。
- Blueprint 只组装 Task Contract，不计算文学状态。
- Gate 只验证，不修复、不写文件。
- Application/Coordinator 编排共享服务，不复制领域逻辑。
- Compatibility Alias 只重导出，不承载新实现。

### 13.3 P0 修复后的重构目标

```text
routes/scene/
  generation_blueprints.py
  review_blueprints.py
  writeback_blueprints.py
  handoff_blueprints.py
  gates/
    generation.py
    review.py
    writeback.py
    handoff.py

workflow/
  scene_steps/
    context.py
    dramaturgy.py
    prose.py
    review.py
    writeback.py
    handoff.py
```

重构必须保持现有公共 Facade，避免把模块拆分变成大范围调用方迁移。

---

## 14. P2/P3：其他静态问题

### 14.1 Legacy Source Ingest Review 较弱

新 archaeology v2 路线已经有结构化、摘要绑定的领域审查。Legacy extraction route 仍主要依赖同任务输出与 Markdown `pass`。

处理建议：

- 新项目默认只走 archaeology v2。
- Legacy 标记为 migration-only。
- 若仍支持正式使用，复用 archaeology review contract。

### 14.2 Export State 存在未接入 helper

`workflow/state_export_release.py` 中 `_export_route_audit_step()` 未进入正式步骤列表，也没有调用者。

处理建议：

- 若 export route 已由其他 Gate 完整覆盖，删除 dead helper。
- 若设计意图是发布前再次核验 route audit，则正式接入并增加测试。
- 不保留看似提供保护、实际从不执行的函数。

### 14.3 Adaptive Orchestration 仍属 feature-gated 能力

Creative Execution Plan、rolling horizon 和 shadow planning 已有较多实现，但正式默认路线仍以固定状态机为主。文档和 UI 不应把 shadow/measured 能力描述成普遍生效的自适应编排。

处理建议：继续保持 ADR 中“未来意图”的边界，只有通过真实 Campaign 验证后再提升为默认路径。

---

## 15. 实施批次

### Batch 0：建立失败证据与测试隔离

目标：先证明问题，避免在错误包或伪 E2E 上修复。

任务：

1. 新增 checkout import 验证与统一测试脚本。
2. 新增两场景真实状态机测试骨架。
3. 复现 scene_0001 ready 后 scene_0002 handoff 缺失。
4. 保存当前全量测试和架构审计结果。

退出门禁：失败测试只因预期的 handoff/Canon 时序问题失败。

### Batch 1：正式 Scene Handoff

目标：完成第 2、3 节全部内容。

任务：

1. 建立 handoff contract、paths、machine、semantic、finalize。
2. 接入 State、Blueprint、Gate、Audit、Semantic Contract。
3. 修正 Canon apply 路径。
4. 扩展 Context Trace 摘要绑定。

退出门禁：两场景确定性生命周期可从第一场 continuity apply 自动进入第二场 Context。

### Batch 2：Scene-local Canon Commit

目标：后续场景读取已经批准的前场事实。

任务：

1. 提取共享 Canon Writeback Coordinator。
2. 在 Scene Route 加入 review、approval、apply。
3. Review Route 改为全项目复核与修订。
4. 对 assisted/full_auto/defer 建立独立测试。

退出门禁：第二场 Context 中的正式 Canon 与第一场 Apply 完全一致。

### Batch 3：独立长篇规划审查

目标：三个宏观产物全部使用独立、摘要绑定的结构化 Review。

任务：完成第 5 节全部内容。

退出门禁：修改 review 文本、复用 Writer 会话或修改候选后复用旧 review 均无法推进。

### Batch 4：恢复任务、Memory 与硬 Canon Context

目标：消除空转和静默旧上下文。

任务：

1. 替换 `manual-route-repair`。
2. 建立 Memory Index v2 快照。
3. 保证地点与组织资产直接进入 Context。
4. 增加稳定错误码和 UI 可解释投影。

退出门禁：未知状态不重试；源资产改变后下一任务读取新内容。

### Batch 5：Transition、Audit 与 YAML 统一

目标：减少重复事实源和审计遗漏。

任务：

1. 建立 Transition Registry 或删除未消费字段。
2. Longform Audit 纳入 handoff。
3. 迁移关键正式路径到 Scene Facts。
4. 处理 Legacy Review 与 Export dead helper。

退出门禁：状态跃迁、Scene 解析和审计输入均只有一个权威来源。

### Batch 6：架构收敛与最终验证

目标：P0/P1 修复不扩大大文件和依赖债务。

任务：

1. 拆分本轮触及的超大 Route/State 文件。
2. 更新 module map、troubleshooting index 和 architecture baseline，只允许债务减少。
3. 跑全量测试、架构审计、Prompt Registry、版本校验。
4. 完成真实两场景、短多章节和最终交付验证。

---

## 16. 最终验收矩阵

| 目标 | 必须证明的证据 |
| --- | --- |
| 单场景闭环 | 正文生成、独立审查、晋升、State、Canon、continuity、handoff 全部完成 |
| 两场景连续性 | 第二场 Context 读取第一场最终 handoff 和已批准事实 |
| Canon 时序 | 第一场 Apply 在第二场 Context 之前发生 |
| 文学规划可靠性 | 三项宏观规划均由独立 Reviewer 审查且绑定候选摘要 |
| 防空转 | 未知状态只产生一次诊断，不反复调用模型 |
| Context 新鲜性 | 修改源文件后索引和 Trace 自动更新 |
| 审计完整性 | Longform Audit 覆盖 handoff、State、Canon、continuity 和正文摘要 |
| 自动模式 | 无人工时 delegated decision 能继续；遇到不可委托事项明确暂停 |
| 人工模式 | Human Gate 可见、可恢复、决定写入后状态推进 |
| 工程质量 | 全量测试通过，架构违规为零，既有复杂度债务不增加 |
| 真实运行 | 至少完成一次真实 Runtime 的两场景闭环和一次短多章节 Campaign |

建议最终验证命令统一由仓库脚本提供，不再依赖全局 Python 环境。验证报告至少记录：

```text
commit
branch
python executable
package root
test count
architecture audit result
prompt registry result
two-scene E2E result
campaign result
```

---

## 17. 最终可行度判断

ArcVellum 当前架构具备继续完成目标的基础。Task Package、Sandbox、Preflight、Writeback、Approval、Evidence Digest 和 Route Gate 已经构成可靠内核。主要缺口集中在已有模块之间的正式交接，而非基础设施缺失。

完成 Batch 0 至 Batch 3 后，项目可以达到“正式多场景连续创作可用”的最低门槛。完成 Batch 4 至 Batch 6 后，才适合把“无人值守长篇生产、可恢复推进和工程级文学连续性”作为稳定能力对外描述。

本轮建议继续沿现有架构修复，避免整体重写。整体重写会丢失已经通过 1318 项测试验证的单步门禁和证据契约，成本远高于补齐跨场景正式路径。
