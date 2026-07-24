# ArcVellum CLI 文学可靠性完整优化执行指令

> 文档性质：强指导性开发与交付手册
> 面向对象：第一次接触 ArcVellum、不了解历史对话和项目结构的开发 Agent
> 审阅基线：`9cab45e`
> 基线版本：`0.9.4`
> 关联分析：`docs/roadmap/arcvellum-cli-literary-reliability-and-engineering-optimization-plan.md`
> 权威范围：本文件规定本轮优化的实施顺序、模块边界、数据契约、迁移方法、测试、验收、提交和交付要求
> 最终目标：完整实施本文件全部批次，使 ArcVellum 的正式 CLI 创作链同时具备工程可靠性、文学因果可靠性、长篇连续性和可恢复交付能力

---

## 0. 如何使用本文件

本文件不是建议清单。负责本轮开发的 Agent 必须把它当作执行合同。

### 0.1 零背景 Agent 的第一条指令

如果你对项目完全不了解，不要先全仓库搜索并自行设计新架构。按以下顺序工作：

1. 阅读本文件第 1 至第 7 节。
2. 阅读根目录 `AGENTS.md`。
3. 阅读 `src/literary_engineering_studio_engine/_engine/AGENTS.md`。
4. 阅读关联分析文档。
5. 运行第 5 节基线命令。
6. 创建进度证据文件。
7. 从 Batch 0 开始，按编号执行。
8. 每个 Batch 达到退出门禁后才能进入下一 Batch。
9. 每个 Batch 单独提交，不得把全部改动压成一个不可审查的大提交。
10. 全部 Batch 结束后执行 Final Gate，不通过则不得声称交付。

### 0.2 发生上下文压缩或换 Agent 时

新的 Agent 只需要重新读取：

```text
AGENTS.md
本文件
docs/verification/cli-literary-reliability-progress.md
最近一个未完成 Batch 的 git diff
```

随后：

1. 运行 `git status --short`。
2. 核对进度文件记录的最后提交。
3. 重跑当前 Batch 的聚焦测试。
4. 从未完成的最小工作项继续。

禁止因为上下文丢失而从头重构已通过验收的 Batch。

### 0.3 规范词

- **MUST**：必须完成，不满足不得进入下一批次。
- **MUST NOT**：绝对禁止。
- **SHOULD**：原则上应完成；若不做，必须在验证报告中说明。
- **MAY**：可选实现，不得阻塞主目标。
- **Formal Artifact**：由正式 CLI 任务声明、通过 Schema 与门禁并写入项目的产物。
- **Semantic Artifact**：包含下一环节真正需要的文学或工程信息，不能只是一枚完成标记。
- **Candidate**：尚未晋升或应用的候选。
- **Review**：绑定精确候选摘要的审查结果。
- **Apply**：将已批准候选原子写入正式资产。

---

## 1. 项目是什么

ArcVellum 是独立的长篇文学 Agent 创作平台，不是外部 Skill 的薄壳。

系统分为两层：

### 1.1 Studio 层

路径：

```text
src/literary_engineering_studio/
client/
desktop/
packaging/
```

职责：

- 项目创建、打开和作品库管理；
- 用户创作方向；
- Agent Runtime 发现与连接；
- 隔离任务工作区；
- Worker 调度、写回和恢复；
- 自动创作；
- 人类决策；
- SSE 与 Read Model；
- Vue 前端；
- Tauri 桌面壳；
- OpenCode、Claude Code、Codex CLI 等 Runtime Adapter；
- 安装、更新和发布。

### 1.2 Embedded Engine 层

路径：

```text
src/literary_engineering_studio_engine/
src/literary_engineering_studio_engine/_engine/
```

职责：

- 正式文学路线；
- Task Package；
- Prompt Assets；
- Schemas；
- Context；
- Word Budget；
- Roleplay；
- Branch；
- Reader Experience；
- Rhythm；
- Composition；
- Prose Generation；
- AgentReview；
- Revision；
- Promotion；
- Character State；
- Canon；
- Longform Audit；
- Export 与 Release Gate。

### 1.3 不可破坏的产品边界

1. MUST NOT 重新依赖外部 `literary-engineering-project-skill` 仓库。
2. MUST NOT 引入 `LEW_CORE_REPO` 或运行时源码检出依赖。
3. MUST NOT 新增 Studio 自己的模型 API Key 存储或直接 HTTP LLM Provider。
4. 智能能力继续来自连接的 Host Agent 或已安装的 Agent Runtime。
5. Studio Worker 负责隔离、验证与写回；Embedded Engine 负责文学状态机。
6. 前端是普通用户的主要客户端。
7. 用户不应被要求直接编辑 JSON、YAML、Task 文件或数据库。
8. 正式正文只能由主 Agent 创作；Subagent 不得代写正文。

---

## 2. 当前正式工作方式

### 2.1 Studio 用户入口

普通用户通过前端创建项目、选择模型、提交创作方向、启动推进、处理决策、阅读正文并交付作品。

### 2.2 Studio Worker 入口

Studio 内部调用：

```text
task-next
→ task-open
→ 创建隔离工作区
→ Agent 读取 task package
→ Agent 只写 expected_outputs
→ Worker 验证差异
→ task-submit
→ task-complete
→ route-audit
```

### 2.3 Embedded Engine 正式宿主循环

开发与诊断时可执行：

```powershell
python -m literary_engineering_studio_engine workflow-dashboard "<project>"
python -m literary_engineering_studio_engine task-next "<project>" --route scene-development
python -m literary_engineering_studio_engine task-open "<project>" --task-id "<task_id>"
python -m literary_engineering_studio_engine task-submit "<project>" --task-id "<task_id>" --artifact "<path>"
python -m literary_engineering_studio_engine task-complete "<project>" --task-id "<task_id>"
python -m literary_engineering_studio_engine route-audit "<project>" --route scene-development
```

本轮优化不得把普通用户重新暴露到这组命令。

### 2.4 当前主要正式路线

```text
scene-development
longform-planning
source-ingest
style-engineering
character-and-world-assets
review-and-audit
export-and-release
```

---

## 3. 为什么要做这轮优化

当前系统的步骤已经很多，问题不在“少一步”，而在少数任务可能出现：

```text
任务说明要求 Agent 完成复杂文学判断
→ expected_outputs 只允许完成标记
→ Agent 无法合法写入判断结果
→ 完成标记仍可通过
→ 下游拿不到真正语义内容
→ UI 和路线显示已完成
```

已确认的代表性问题：

1. Roleplay Sidecar 要求回填行动、后果和分支，但正式任务只允许 Completion。
2. Branch Lab 只检查 RP 完成，不读取 RP 结果。
3. Composition Agent Task 没有结构化 verdict 和正式返修路线。
4. State 与 Canon Agent Task 的说明要求修订 Patch，但正式输出白名单可能不允许。
5. State Patch 缺少与 Canon 对等的 Decision/Apply 闭环。
6. Longform Candidate 与 Review 可能由同一 Agent 同时生成。
7. Context Trace 没有输入摘要，旧 Context 可能继续通过。
8. 上一场的状态、关系和后果不能稳定进入下一场。
9. 宏观节奏计划没有完全进入正式 CLI 状态机。
10. Reader Question 与 Promise/Payoff 缺少全书持久账本。
11. Worker 文件写入、Submit 和 Complete 不完全原子。
12. Read Model、API、OpenCode 验证、SSE、启动与 CI 仍有工程风险。

本轮完成后，系统必须从“步骤被执行”升级为“语义被验证并被下游消费”。

---

## 4. 总体成功标准

最终交付必须证明：

### 4.1 工程可靠性

- 空 Completion 不能让语义任务通过。
- Agent 只能写正式契约允许的文件。
- Agent 被要求修改的文件一定在允许输出中。
- 任一正式产物都有 Schema。
- 任一正式语义产物都有明确下游消费者。
- Submit、Complete、文件写回和路线 revision 原子一致。
- 失败可以恢复，不留下半提交。
- 非本地 API 必须鉴权。
- OpenCode 二进制必须通过可信摘要。
- SSE、项目切换和自动创作不会因竞态重复执行。

### 4.2 文学可靠性

- RP 结果真实进入 Branch。
- Branch 能追溯角色动机、世界反应、代价和不可逆点。
- Composition 接收已选 Branch、Reader、Rhythm、Bridge、Budget 和 Style。
- 下一场显式接收上一场的后果与状态。
- 全书具有 Story Architecture Contract。
- 字数预算、剧情库存与节奏曲线互相一致。
- Reader Questions 与 Promises 有生命周期。
- Writer 和 Reviewer 至少会话隔离。
- Review 与精确候选摘要绑定。
- State 和 Canon 在下一场前完成决策与应用，或明确阻塞。

### 4.3 产品可靠性

- 普通用户仍只使用前端。
- 决策、节奏、审查和补丁以人类可读界面展示。
- UI 不直接修改正式项目文件。
- 长时间自动创作能识别等待、失败和无进展。
- 旧项目可迁移，不要求删除作品重建。
- Windows 安装、首次启动、升级和交付可验证。

---

## 5. 开发环境与基线命令

### 5.1 仓库根目录

本文件中的命令默认在：

```text
C:\Users\26532\Documents\Codex\2026-07-16\c-users-26532-documents-codex-2026\outputs\literary-engineering-studio
```

执行。其他机器上使用仓库实际根目录，不得硬编码上述绝对路径进源码、测试、配置或安装包。

### 5.2 安装依赖

```powershell
python -m pip install -e ".[api,test]"
npm ci
```

Rust/Tauri 需要本机 Rust 工具链。只有构建桌面候选时才需要 PyInstaller 和完整打包依赖。

### 5.3 全量基线

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src
python -m literary_engineering_studio doctor
python -m literary_engineering_studio --help
python -m literary_engineering_studio_engine prompt-registry-validate --json
npm run client:test
npm run client:build
Push-Location desktop/src-tauri
cargo check --locked
Pop-Location
```

### 5.4 Windows 候选构建

只在 Final Gate 使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/build_desktop.ps1 -SkipPythonInstall -SkipNodeInstall
```

### 5.5 PowerShell Profile 警告

如果命令输出含有：

```text
profile.ps1 cannot be loaded because running scripts is disabled
```

但命令本身 Exit Code 为 0，可记录为环境噪声。不要为了消除该警告修改用户系统策略。

---

## 6. Git 与工作区纪律

### 6.1 开始前

```powershell
git status --short
git branch --show-current
git rev-parse --short HEAD
```

### 6.2 当前仓库已知工作区情况

基线存在多个未跟踪 `.log` 文件和临时输出。它们不是本轮功能代码。

MUST：

- 精确暂存文件。
- 使用 `git add <明确路径>`。
- 提交前执行 `git diff --cached --stat`。
- 保留用户已有未提交改动。

MUST NOT：

- 使用 `git add .`。
- 删除来源不明的用户文件。
- 使用 `git reset --hard`。
- 使用 `git checkout --` 覆盖用户改动。
- 把运行日志、临时项目、模型输出或安装器缓存提交进 Git。

### 6.3 分支建议

如果当前分支不是本轮专用分支，新建：

```powershell
git switch -c feat/cli-literary-reliability
```

如果用户已指定当前分支继续开发，不要擅自切换。

### 6.4 进度证据

Batch 0 创建：

```text
docs/verification/cli-literary-reliability-progress.md
```

每个 Batch 记录：

```markdown
## Batch X

- Status:
- Start commit:
- End commit:
- Changed contracts:
- Changed modules:
- Migration:
- Focused tests:
- Full tests:
- Manual acceptance:
- Known residual risk:
- Next batch:
```

---

## 7. 模块导航

零背景 Agent 只需按当前 Batch 读取相关模块。

### 7.1 Studio 执行链

| 职责 | 文件 |
|---|---|
| Worker | `src/literary_engineering_studio/worker.py` |
| Core Bridge | `src/literary_engineering_studio/core_bridge.py` |
| 执行互斥 | `src/literary_engineering_studio/execution_coordinator.py` |
| 任务预检 | `src/literary_engineering_studio/task_preflight.py` |
| 任务程序 | `src/literary_engineering_studio/task_program.py` |
| Sandbox | `src/literary_engineering_studio/sandbox.py` |
| Jobs | `src/literary_engineering_studio/jobs.py` |
| Autopilot | `src/literary_engineering_studio/autopilot.py` |
| API | `src/literary_engineering_studio/api_server.py` |
| Runtime Base | `src/literary_engineering_studio/runtimes/base.py` |
| OpenCode Runtime | `src/literary_engineering_studio/runtimes/opencode.py` |
| Runtime Pool | `src/literary_engineering_studio/opencode_runtime_pool.py` |
| Binary Verification | `src/literary_engineering_studio/opencode_binary.py` |
| Read Model Cache | `src/literary_engineering_studio/read_model_cache.py` |
| Core Read Models | `src/literary_engineering_studio/core_read_models.py` |
| Live Events | `src/literary_engineering_studio/live_events.py` |

### 7.2 Embedded Engine 正式链

| 职责 | 文件 |
|---|---|
| Task Registry | `src/literary_engineering_studio_engine/task_registry.py` |
| Workflow State | `src/literary_engineering_studio_engine/workflow_state.py` |
| Task Status | `src/literary_engineering_studio_engine/agent_task_status.py` |
| Context | `context_broker.py`, `context_packet.py` |
| Roleplay | `roleplay_lab.py` |
| Branch | `branch_lab.py` |
| Scene Composition | `scene_composer.py` |
| Reader Experience | `reader_experience.py` |
| Rhythm | `narrative_rhythm.py`, `rhythm_plan.py` |
| Prose Prompt | `prompt_pack.py` |
| Candidate | `scene_draft.py` |
| Scene Review | `agent_scene_review.py`, `review_ci.py` |
| Revision | `scene_revision.py` |
| Promotion | `candidate_promotion.py`, `scene_readiness.py` |
| State | `character_state_evolver.py`, `character_state_apply.py` |
| Canon | `canon_evolver.py`, `canon_lint.py`, `agent_canon_review.py` |
| Longform | `word_budget.py`, `longform_materializer.py`, `longform_audit.py` |
| Memory | `memory_index.py`, `knowledge_store.py` |
| Interaction | `project_interaction.py` |
| Export | `export_package.py`, `docx_export.py`, `publish.py` |
| Schemas | `src/literary_engineering_studio_engine/_engine/schemas/` |
| Prompt Assets | `src/literary_engineering_studio_engine/_engine/templates/prompt_assets/` |

### 7.3 前端

| 职责 | 文件 |
|---|---|
| API Client | `client/src/services/api.ts` |
| Global Store | `client/src/stores/app.ts` |
| Human Choices | `client/src/stores/humanChoices.ts` |
| Overview | `client/src/features/workflow/OverviewView.vue` |
| Quality/Rules | `client/src/features/quality/` |
| Reader | `client/src/features/reader/ReaderView.vue`, `client/src/components/ManuscriptReader.vue` |
| Rhythm Editor | `client/src/components/RhythmCurveEditor.vue` |
| Agent Windows | `client/src/features/orrery/SpatialWindowLayer.vue` |
| Settings | `client/src/features/settings/SettingsView.vue` |
| API Types | `client/src/types/api.ts` |

### 7.4 主要现有测试

优先复用：

```text
tests/test_worker_integration.py
tests/test_task_contract_transport.py
tests/test_sidecar_provenance.py
tests/test_scene_contract_order.py
tests/test_context_packet_compaction.py
tests/test_longform_materializer.py
tests/test_longform_revision_loop.py
tests/test_scene_review_revision_loop.py
tests/test_canon_patch_route.py
tests/test_choice_effect_materialization.py
tests/test_reader_experience_contract.py
tests/test_narrative_rhythm_curve.py
tests/test_prompt_evaluation.py
tests/test_read_model_cache.py
tests/test_api_server.py
tests/test_autopilot.py
tests/test_opencode.py
tests/test_bootstrap.py
tests/test_update_manifest.py
```

---

## 8. 唯一允许的实施顺序

```text
Batch 0   冻结基线与建立证据
   ↓
Batch 1   Task Contract Audit 与单一契约源
   ↓
Batch 2   修复 Roleplay / Composition / State / Canon 假完成
   ↓
Batch 3   原子 Task Finalize 与恢复
   ↓
Batch 4   接通 RP → Branch → Composition 文学因果链
   ↓
Batch 5   Context Trace v2、Handoff 与 Memory 信任层
   ↓
Batch 6   Story Architecture、Longform 独立审查与宏观 Rhythm
   ↓
Batch 7   Bridge、Reader Question、Promise/Payoff 持久账本
   ↓
Batch 8   Review 独立性、Revision Map 与 Prompt Compiler
   ↓
Batch 9   State / Canon Decision-Apply 完整闭环
   ↓
Batch 10  Runtime 性能、安全、SSE 与启动可靠性
   ↓
Batch 11  渐进模块化、前端投影与仓库治理
   ↓
Batch 12  Golden Projects、全量验收、安装与发布准备
```

不能跳 Batch。允许在同一 Batch 内并行开发互不重叠的测试和实现，但集成顺序必须保持。

---

## 9. 所有 Batch 共用的设计规则

## 9.1 单一 Task Contract

当前 Task 要求可能分散在：

- Task Registry；
- Sidecar；
- Prompt Asset；
- Worker；
- Route Gate；
- 前端解释。

本轮必须收敛为单一机器可读 Task Contract。推荐扩展 `agent_task.v1` 为向后兼容的 v2，至少包含：

```json
{
  "schema": "agent_task.v2",
  "task_id": "",
  "task_type": "",
  "route": "",
  "source_paths": [],
  "source_digests": {},
  "expected_outputs": [],
  "output_schemas": {},
  "allowed_write_roots": [],
  "semantic_acceptance": [],
  "consumed_by": [],
  "review_policy": {},
  "approval_policy": {},
  "next_allowed_states": []
}
```

Sidecar 和 Agent Prompt 由该 Contract 渲染。不得反过来从 Markdown 猜正式要求。

## 9.2 Semantic Artifact Envelope

新的结构化语义产物 SHOULD 共享以下元信息：

```json
{
  "schema": "<artifact>.vN",
  "artifact_id": "",
  "project_id": "",
  "route": "",
  "task_id": "",
  "scene_id": "",
  "created_at": "",
  "created_by": {
    "runtime": "",
    "session_id": "",
    "role": ""
  },
  "source_digests": {},
  "content": {}
}
```

不要求一次性迁移所有旧 Schema，但本轮新增 v2 产物必须包含来源摘要和创建者。

## 9.3 Review Contract

所有正式 Review 至少包含：

```json
{
  "schema": "semantic_review.v2",
  "review_id": "",
  "candidate_path": "",
  "candidate_sha256": "",
  "reviewer_session_id": "",
  "writer_session_id": "",
  "verdict": "pass|revise|block",
  "findings": [],
  "required_changes": [],
  "allowed_exceptions": [],
  "checked_dimensions": [],
  "created_at": ""
}
```

规则：

1. `candidate_sha256` 不匹配时 Review 失效。
2. `pass_with_notes` 不再作为可晋升状态；有必须修改内容就用 `revise`。
3. `pass` 只能包含非阻断建议。
4. Reviewer Session 与 Writer Session 相同则默认不通过独立性门禁，除非任务显式声明无需独立审查。

## 9.4 Apply Contract

State、Canon 和其他正式资产应用必须记录：

```json
{
  "apply_id": "",
  "candidate_sha256": "",
  "review_sha256": "",
  "decision_id": "",
  "target_before_sha256": "",
  "target_after_sha256": "",
  "changed_paths": [],
  "applied_at": ""
}
```

目标文件摘要变化时，必须重新审查或明确合并，不得覆盖。

## 9.5 任务完成定义

正式任务完成条件：

```text
Agent process ended
AND expected outputs exist
AND no unexpected writes
AND all schemas pass
AND source digests match
AND semantic acceptance passes
AND required review passes
AND required decision exists
AND task finalize commits atomically
```

`agent_completion.json` 只满足第一项。

## 9.6 文件写入

- 手工编辑代码使用 `apply_patch`。
- 运行格式化器或生成器可以机械写入。
- 不使用临时 Python 脚本代替简单文件编辑。
- 写 JSON 使用标准序列化，不手拼字符串。
- 正式项目写入使用 `atomic_io.py` 或新的事务层。

---

# Batch 0：冻结基线与建立证据

## 0.1 目标

建立可重复的开发起点，不改变运行行为。

## 0.2 必读

```text
AGENTS.md
src/literary_engineering_studio_engine/_engine/AGENTS.md
docs/roadmap/arcvellum-cli-literary-reliability-and-engineering-optimization-plan.md
docs/architecture/current-core-review.md
```

## 0.3 执行步骤

1. 记录分支和 HEAD。
2. 运行第 5.3 节全量基线。
3. 记录已有失败，不得把既有失败伪装成本轮引入。
4. 创建进度文件。
5. 创建 Golden Project 工作目录，但不要把用户真实作品复制进测试。
6. 记录当前：
   - `formal-help`；
   - `workflow-dashboard`；
   - 七条 route 的 `task-next` 结果；
   - Prompt Registry 数量；
   - Task Contract 样例；
   - RP、Composition、State、Canon 当前 expected outputs。
7. 为 P0 问题写 characterization tests，先证明旧行为。

## 0.4 建议新增测试

```text
tests/test_task_contract_audit.py
tests/test_semantic_task_outputs.py
```

初始测试应能明确失败或标记已知缺陷：

- RP Prompt 要求写入 Roleplay 内容，但 expected outputs 不包含该内容。
- Branch 不消费 RP 语义产物。
- Composition、State、Canon 只有 Completion 时仍可能推进。

## 0.5 退出门禁

- 全量基线已记录。
- 进度文件已创建。
- 已知缺陷被测试精确描述。
- 尚未修改正式行为。

## 0.6 建议提交

```text
test: freeze CLI literary reliability baseline
```

---

# Batch 1：Task Contract Audit 与单一契约源

## 1.1 目标

让机器自动发现 Task 指令、允许输出、Schema、下游消费者和状态转换之间的不一致。

## 1.2 必读模块

```text
src/literary_engineering_studio_engine/task_registry.py
src/literary_engineering_studio_engine/workflow_state.py
src/literary_engineering_studio_engine/agent_task_status.py
src/literary_engineering_studio_engine/agent_tasks.py
src/literary_engineering_studio/task_program.py
src/literary_engineering_studio/contracts.py
src/literary_engineering_studio/worker.py
src/literary_engineering_studio_engine/_engine/schemas/agent_task.v1.json
```

## 1.3 新增模块

推荐：

```text
src/literary_engineering_studio_engine/task_contracts.py
src/literary_engineering_studio_engine/task_contract_audit.py
src/literary_engineering_studio_engine/_engine/schemas/agent_task.v2.json
tests/test_task_contract_audit.py
```

## 1.4 实施步骤

1. 定义 v2 Task Contract 数据结构。
2. 保留读取 v1 的兼容层。
3. 让 Task Registry 输出 v2 所需字段。
4. Sidecar 从 Contract 渲染 expected outputs 和禁止事项。
5. Prompt Asset 继续提供语义指令，但不能声明 Contract 不允许的写入。
6. 实现 Contract Audit：
   - expected output 为空；
   - 唯一输出是 completion；
   - output 缺 Schema；
   - Prompt/Sidecar 提到写入未列入 output；
   - Formal Artifact 没有 `consumed_by`；
   - `next_allowed_states` 与 Workflow State 不一致；
   - Review 没有候选摘要；
   - Apply 没有 Decision；
   - 路径越界；
   - 同一 task type 多处不一致定义。
7. 将审计加入 Prompt Registry/CI 类似的确定性命令。
8. 普通用户 CLI 不必显示该维护命令；可放在 `help-all` 或开发命令面。

## 1.5 测试

聚焦：

```powershell
python -m unittest tests.test_task_contract_audit tests.test_task_contract_transport tests.test_scene_contract_order -v
```

必须覆盖：

- 合法 Contract 通过。
- Completion-only 语义任务失败。
- Markdown 声明隐式输出失败。
- 无消费者产物失败。
- 错误 next state 失败。
- v1 可读取但产生迁移警告。

## 1.6 禁止捷径

- 不允许只对四个已知任务写硬编码例外。
- 不允许用字符串搜索替代正式 Contract 字段。
- 不允许让审计只输出 warning 而 CI 仍通过。

## 1.7 退出门禁

- P0 双重契约能被机器识别。
- 所有现有正式任务都有明确审计结果。
- 未迁移任务被列入 allowlist，并注明清除 Batch；allowlist 不得无限保留。

## 1.8 建议提交

```text
feat: add authoritative task contracts and contract audit
```

---

# Batch 2：修复 Roleplay、Composition、State、Canon 假完成

## 2.1 目标

让四类任务产生真实结构化产物，而非只提交 Completion。

## 2.2 Roleplay

### 必读

```text
roleplay_lab.py
task_registry.py 中 roleplay 任务
workflow_state.py 中 roleplay steps
templates/prompt_assets/route.scene-development.roleplay.execute.v1.md
```

### 新 Schema

```text
_engine/schemas/roleplay_result.v2.json
```

至少包含：

- scene_id；
- source_digests；
- reading_receipt；
- 每个角色的 belief、avoidance、intended_action；
- rejected_convenient_action；
- moral_line 影响；
- background_story 的间接影响；
- next_scene_cost；
- world_consequences；
- canon_conflicts；
- candidate_pressures。

### 正式输出

```text
roleplay_result.v2.json
roleplay_report.md
roleplay_agent_completion.json
```

### Gate

- 参与角色必须有对应结果。
- 每个行动必须有来源角色。
- 不允许仅复述角色卡。
- Canon 冲突必须显式列出。
- Empty list 只能在有合理解释时接受。

## 2.3 Composition Review

### 新 Schema

```text
_engine/schemas/composition_review.v2.json
```

### 正式输出

```text
composition_review.v2.json
composition_review.md
composition_agent_completion.json
```

### Verdict

```text
pass
revise
block
```

`revise` 进入新的 `composition-revision` 任务。Agent 不得直接改已审 Composition；Revision 生成新 Candidate 和新 SHA。

## 2.4 State Patch

### 新输出契约

State Agent 必须被允许写：

```text
<scene>_state_patch.candidate.json
<scene>_state_patch.review.json
<scene>_state_patch.report.md
<scene>_state_patch.agent_completion.json
```

### Gate

- 每项变化引用 promoted draft 证据。
- 区分事实变化、推断变化和不应写入的瞬时情绪。
- 不允许把作者解释写成人物已知。
- 不允许无依据地改变 belief、relationship、secret、moral_line。

## 2.5 Canon Patch

### 新输出契约

```text
<scene>_canon_patch.candidate.json
<scene>_canon_patch.review.json
<scene>_canon_patch.report.md
<scene>_canon_patch.agent_completion.json
```

### Gate

- 每项新增 Canon 引用正文证据。
- 区分新增、澄清、冲突修订和禁止变更。
- 目标文件必须明确。
- 不直接写正式 Canon。

## 2.6 Worker 修改

Worker 必须：

1. 从 v2 Contract 获取允许输出。
2. 接受上述合法产物。
3. 继续拒绝其他修改。
4. 先 Schema 验证，再接受 Completion。
5. Semantic Acceptance 失败时不 Submit。

## 2.7 测试

新增或扩展：

```text
tests/test_semantic_task_outputs.py
tests/test_worker_integration.py
tests/test_sidecar_provenance.py
tests/test_canon_patch_route.py
tests/test_scene_contract_order.py
```

聚焦命令：

```powershell
python -m unittest tests.test_semantic_task_outputs tests.test_worker_integration tests.test_sidecar_provenance tests.test_canon_patch_route -v
```

必须覆盖：

- 只写 Completion 时失败。
- 合法语义产物可写回。
- 修改 Source Artifact 被拒绝。
- Schema 错误不 Submit。
- Prompt、Sidecar、Contract 对输出要求一致。

## 2.8 迁移

- 旧 RP Markdown 可尝试解析为 v2。
- 解析失败则重新签发 RP Task。
- 旧 State/Canon Patch 保留，不覆盖。
- 旧 Completion 标记为 `legacy_unverified`。

## 2.9 退出门禁

- 四类任务不再存在空心完成。
- Contract Audit 对四类任务全部通过。
- Worker 不误拒合法输出。

## 2.10 建议提交

```text
fix: require semantic outputs for literary agent tasks
```

---

# Batch 3：原子 Task Finalize 与恢复

## 3.1 目标

文件写回、Submit、Complete 和 Route Revision 要么一起成功，要么一起失败。

## 3.2 必读

```text
src/literary_engineering_studio/worker.py
src/literary_engineering_studio/core_bridge.py
src/literary_engineering_studio/sandbox.py
src/literary_engineering_studio/execution_coordinator.py
src/literary_engineering_studio_engine/task_registry.py
src/literary_engineering_studio_engine/atomic_io.py
tests/test_worker_integration.py
```

## 3.3 新设计

推荐新增：

```text
src/literary_engineering_studio/task_finalize.py
tests/test_atomic_task_finalize.py
```

事务过程：

```text
validate workspace
→ calculate write set
→ calculate precondition digests
→ acquire project lock
→ verify route revision
→ write transaction journal
→ stage target temp files
→ atomically replace expected outputs
→ record submission
→ record completion
→ bump route revision
→ mark journal committed
```

## 3.4 Journal

Journal 至少记录：

- transaction_id；
- task_id；
- project；
- before/after digests；
- write set；
- submission state；
- completion state；
- route revision；
- committed/rolled_back；
- recovery action。

不得记录凭证或正文全文。

## 3.5 恢复

应用启动或 Worker 开始新任务前：

1. 扫描未完成 Journal。
2. 判断是否尚未替换、部分替换或状态已提交。
3. 按摘要恢复。
4. 无法自动判断时阻塞项目并输出诊断，不继续创作。

## 3.6 失败注入测试

必须模拟：

- 第一文件写入失败；
- 多文件中途失败；
- `task-submit` 失败；
- `task-complete` 失败；
- Route Revision 冲突；
- 目标文件被外部修改；
- 进程在写回后、提交前退出；
- 重复 Finalize。

重复 Finalize 必须幂等。

## 3.7 测试

```powershell
python -m unittest tests.test_atomic_task_finalize tests.test_worker_integration tests.test_execution_coordinator -v
```

## 3.8 禁止捷径

- 不允许只回滚文件而不回滚任务状态。
- 不允许依赖“通常不会失败”。
- 不允许把整个项目目录复制一份作为长期事务实现。

## 3.9 退出门禁

- 所有失败注入后，项目文件与任务状态一致。
- 恢复可幂等执行。
- 同一项目仍保持串行。

## 3.10 建议提交

```text
feat: finalize formal tasks atomically
```

---

# Batch 4：接通 RP → Branch → Composition 文学因果链

## 4.1 目标

角色推演必须成为分支的真实输入，分支必须成为 Composition 的真实输入。

## 4.2 必读

```text
roleplay_lab.py
branch_lab.py
scene_composer.py
workflow_state.py
task_registry.py
reader_experience.py
narrative_rhythm.py
```

## 4.3 Branch Candidates v2

新增：

```text
_engine/schemas/branch_candidates.v2.json
```

每个分支至少包含：

```json
{
  "branch_id": "",
  "rp_action_refs": [],
  "trigger": "",
  "character_actions": [],
  "world_reactions": [],
  "relationship_changes": [],
  "information_changes": [],
  "costs": [],
  "irreversible_change": "",
  "canon_risks": [],
  "reader_effect": "",
  "next_scene_pressures": [],
  "inventory_contribution": ""
}
```

## 4.4 确定性 Branch Lab 的定位

现有算法 MAY 保留，但只能输出：

```text
branch_seeds.v2
```

标记 `seed_only: true`。

Agent Task 负责：

- 读取 Roleplay Result；
- 评估 Seed；
- 扩展、融合、淘汰或新增分支；
- 输出 Branch Candidates v2。

不能把模板标签直接当最终分支。

## 4.5 Branch Review

Branch Review 必须检查：

- 每个角色行动是否由 RP 支撑；
- 是否存在为了推进剧情而违背人物的便利行为；
- 各分支是否真正不同；
- 是否有代价；
- 是否有不可逆变化；
- 是否制造足够后续压力；
- 是否新增未授权 Canon；
- 是否破坏 Story Architecture；
- 是否只有“强冲突”而没有人物选择。

## 4.6 Branch Selection

正式 Selection 记录：

- 选中分支；
- 融合来源；
- 放弃原因；
- 用户/Steward 决策；
- 被选 Candidate SHA；
- 必须保留元素；
- 禁止 Composition 擅自改变的核心。

## 4.7 Composition v2

Composition 必须引用：

- selected_branch_id；
- roleplay_result SHA；
- branch_candidates SHA；
- budget contract；
- reader contract；
- rhythm contract；
- bridge contract；
- style mount；
- context trace。

Composition 中每个关键 Beat SHOULD 引用上游条目。

## 4.8 Gate

- RP 改动使 Branch 失效。
- Branch 改动使 Selection 和 Composition 失效。
- Selection 改动使 Composition 和 Candidate 失效。
- Composition Review 非 Pass 不得生成正文。

## 4.9 测试

新增：

```text
tests/test_roleplay_branch_causality.py
tests/test_branch_candidate_schema.py
tests/test_composition_provenance_v2.py
```

聚焦：

```powershell
python -m unittest tests.test_roleplay_branch_causality tests.test_branch_candidate_schema tests.test_composition_provenance_v2 tests.test_scene_contract_order -v
```

文学 Fixture：

- 一个角色的 moral_line 禁止某行动。
- Seed 故意建议该行动。
- Branch Review 必须拒绝或要求充分人物变化依据。

## 4.10 退出门禁

- Branch 文件中能追溯 RP 条目。
- RP 内容删除后路线失败。
- Composition 能追溯已选 Branch。
- 模板分支不再伪装成最终文学分支。

## 4.11 建议提交

```text
feat: connect roleplay decisions to branch and composition
```

---

# Batch 5：Context Trace v2、Scene Handoff 与 Memory 信任层

## 5.1 目标

保证每一场使用最新正式信息，并明确承接上一场后果。

## 5.2 必读

```text
context_broker.py
context_packet.py
memory_index.py
knowledge_store.py
character_state_evolver.py
canon_evolver.py
scene_readiness.py
candidate_promotion.py
```

## 5.3 Context Trace v2

新增 Schema：

```text
_engine/schemas/context_trace.v2.json
```

每个来源记录：

- relative_path；
- sha256；
- role；
- trust_tier；
- required；
- loaded_at；
- project_revision。

顶层记录：

- scene_id；
- previous_promoted_scene_sha；
- state_revision；
- canon_revision；
- style_mount_revision；
- word_budget_revision；
- rhythm_plan_revision；
- retrieval_digest。

## 5.4 Context Policy

不再把大多数资料固定为可选。

动态规则：

- Scene 有 participants，则角色资料 required。
- Longform 目标超过阈值，则 Word Budget 和 Chapter Obligations required。
- 挂载 Style，则 Style Prompt required。
- Scene 引用组织、地点、规则，则对应 Canon required。
- 非第一场必须有 Previous Scene Handoff。
- 已存在 approved State/Canon Delta，则必须加载。

## 5.5 Scene Handoff v1

新增：

```text
_engine/schemas/scene_handoff.v1.json
```

至少包含：

- previous_scene_id；
- promoted_draft_sha；
- time_after；
- location_after；
- character_state_deltas；
- relationship_debts；
- unresolved_actions；
- objects_in_motion；
- information_distribution；
- outgoing_hooks；
- approved_state_apply；
- approved_canon_apply；
- emotional_aftertaste。

下一场 Context 必须读取。

## 5.6 Freshness Gate

在以下阶段前验证：

```text
Roleplay
Branch
Composition
Generation
Review
Promotion
```

任何输入摘要变化：

- 标记下游 Artifact stale；
- 不删除旧产物；
- 重新签发最早受影响任务。

## 5.7 Memory Trust Tiers

建议：

| Tier | 内容 | Generation 默认 |
|---|---|---|
| formal | Canon、正式角色、已晋升正文、已应用状态 | 允许 |
| approved | 已批准规划、Branch Selection、Handoff | 允许 |
| candidate | 未晋升草稿、候选资产 | 默认不允许 |
| diagnostic | Review、日志、工作流报告 | 不允许 |
| rejected | 被拒分支、被拒稿件 | 不允许 |

检索结果必须记录 path、tier、score 和被采用原因。

第一版使用确定性词面检索、字段过滤和 BM25 即可。Embedding 为可选 Adapter，不得成为运行硬依赖。

## 5.8 测试

新增：

```text
tests/test_context_trace_v2.py
tests/test_context_freshness.py
tests/test_scene_handoff.py
tests/test_memory_trust_tiers.py
```

聚焦：

```powershell
python -m unittest tests.test_context_trace_v2 tests.test_context_freshness tests.test_scene_handoff tests.test_memory_trust_tiers tests.test_context_packet_compaction -v
```

必须覆盖：

- Canon 修改后 Context 失效。
- 文风更换后 Candidate 失效。
- 被拒分支不进入 Generation。
- 下一场缺 Handoff 时阻塞。
- 第一场不要求 Previous Handoff。

## 5.9 退出门禁

- Context 能证明读了什么版本。
- 下一场能证明接住了上一场。
- 非正式记忆不会污染生成。

## 5.10 建议提交

```text
feat: add fresh context traces and scene handoffs
```

---

# Batch 6：Story Architecture、Longform 独立审查与宏观 Rhythm

## 6.1 目标

让长篇不是只有字数库存，还拥有主题、人物变化和终局脊柱。

## 6.2 必读

```text
word_budget.py
longform_materializer.py
longform_audit.py
rhythm_plan.py
narrative_rhythm.py
workflow_state.py 中 _longform_state
task_registry.py 中 longform 任务
```

## 6.3 Story Architecture Contract

新增 Schema：

```text
_engine/schemas/story_architecture.v1.json
```

至少包含：

- premise；
- central_dramatic_question；
- protagonist_initial_misbelief；
- protagonist_desire；
- protagonist_need；
- counterforce；
- thematic_contradiction；
- change_vector；
- midpoint_irreversibility；
- endgame_choice；
- ending_state；
- volume_obligations；
- non_negotiable_payoffs。

## 6.4 正式顺序

Longform Route 调整为：

```text
story architecture candidate
→ independent architecture review
→ word budget candidate
→ independent budget review
→ global rhythm candidate
→ independent rhythm review
→ scene inventory candidate
→ independent inventory review
→ chapter obligations candidate
→ independent obligation review
→ materialize
```

## 6.5 Review 独立性

Planner Agent 写 Candidate。

Reviewer Agent：

- 使用不同 session_id；
- 只读 Candidate 与必要 Canon；
- 输出 Review v2；
- 不同时修改 Candidate。

Revision 由 Planner 或新的 Planner Session 执行，再由 Reviewer 复审。

## 6.6 Global Rhythm Plan

进入正式 CLI，不再由 API 直接写正式配置。

至少包含：

- 全书压力曲线；
- 各卷结构职责；
- 各章节奏位置；
- Scene Role 分布；
- 快慢场比例；
- 高压连续上限；
- Breathing Scene；
- Narrative Distance；
- 对话/动作/心理/环境材质分布；
- Chapter Ending 类型；
- Set Piece；
- Climax 与 Aftermath；
- 目标字数与详略等级。

前端编辑产生 Candidate，由 CLI 审查和晋升。

## 6.7 Materializer

物化时将：

- word_count_target；
- rhythm_role；
- pace；
- density；
- narrative_distance；
- scene_function；
- reader_effect；
- chapter_ending_role；

写入正式 Scene/Chapter 计划。

不得维护两套互不一致的字数或节奏数字。

## 6.8 测试

新增：

```text
tests/test_story_architecture_contract.py
tests/test_longform_review_independence.py
tests/test_global_rhythm_route.py
tests/test_longform_materialization_v2.py
```

聚焦：

```powershell
python -m unittest tests.test_story_architecture_contract tests.test_longform_review_independence tests.test_global_rhythm_route tests.test_longform_materialization_v2 tests.test_longform_materializer tests.test_longform_revision_loop -v
```

文学 Fixture：

- 目标 50 万字但只有短篇库存，必须 Block。
- 字数足够但无终局选择，Architecture Review 必须 Revise。
- 连续十章高压无余波，Rhythm Review 必须 Revise。

## 6.9 退出门禁

- Story Architecture 是 Word Budget 上游。
- Rhythm Plan 是正式 CLI 产物。
- Candidate 与 Review 不由同一 Session 自审。
- 物化 Scene 带正式字数和节奏目标。

## 6.10 建议提交

```text
feat: formalize longform architecture and rhythm planning
```

---

# Batch 7：Bridge、Reader Question 与 Promise/Payoff 持久账本

## 7.1 目标

消除场景孤岛，管理长篇读者期待。

## 7.2 必读

```text
reader_experience.py
narrative_rhythm.py
longform_audit.py
scene_composer.py
prompt_pack.py
narrative_projection.py
```

## 7.3 Bridge Contract v2

新增：

```text
_engine/schemas/scene_bridge.v2.json
```

每个 Hook：

- hook_id；
- type；
- content；
- source_scene；
- target_window；
- status；
- handling；
- evidence；
- character_refs；
- object_refs；
- canon_refs。

下一场 Incoming 必须引用前场 Hook ID，并说明：

```text
payoff
delay
intensify
reverse
transfer
close
```

## 7.4 Reader Question Ledger

新增正式项目资产：

```text
plot/reader_questions/ledger.json
```

字段：

- question_id；
- opened_at；
- visible_question；
- reader_current_knowledge；
- planned_answer_window；
- last_advanced_at；
- status；
- answer_evidence；
- urgency；
- related_promises。

## 7.5 Promise/Payoff Ledger

新增：

```text
plot/promises/ledger.json
```

字段：

- promise_id；
- promise_type；
- setup_scene；
- promised_effect；
- due_window；
- reinforcement_count；
- status；
- payoff_scene；
- payoff_type；
- payoff_evidence；
- contradiction_risk。

## 7.6 Ledger 写入

场景正文不得直接改 Ledger。

流程：

```text
promoted scene
→ ledger delta candidate
→ semantic review
→ apply
→ next context
```

## 7.7 Longform Audit

新增检查：

- Incoming 未接住；
- Hook 孤立；
- Reader Question 超期；
- Promise 无兑现；
- Payoff 无铺垫；
- 同一问题重复提出；
- 连续场景只延迟不推进；
- 关系债务无后果；
- 物件消失；
- Chapter Ending 类型重复。

Audit 失败必须生成 Repair Tasks。

## 7.8 测试

新增：

```text
tests/test_scene_bridge_handshake.py
tests/test_reader_question_ledger.py
tests/test_promise_payoff_ledger.py
tests/test_longform_repair_tasks.py
```

聚焦：

```powershell
python -m unittest tests.test_scene_bridge_handshake tests.test_reader_question_ledger tests.test_promise_payoff_ledger tests.test_longform_repair_tasks tests.test_reader_experience_contract -v
```

## 7.9 前端

Read Model 展示：

- 当前开放问题；
- 即将到期承诺；
- 最近兑现；
- 超期风险；
- 场景承接。

前端只读正式投影，不自行推断 Ledger。

## 7.10 退出门禁

- 场景桥可跨场追踪。
- 问题和承诺有完整生命周期。
- Audit 能生成正式返工任务。

## 7.11 建议提交

```text
feat: track scene bridges and reader promises
```

---

# Batch 8：Review 独立性、Revision Map 与 Prompt Compiler

## 8.1 目标

减少 Agent 自我合理化，避免提示词规则堆叠造成僵硬文本。

## 8.2 必读

```text
agent_scene_review.py
agent_canon_review.py
agent_committee.py
scene_revision.py
prompt_pack.py
prompt_registry.py
anti_ai_style.py
punctuation_standard.py
creative_quality.py
style_prompt.py
style_compiler.py
Studio runtime session modules
```

## 8.3 Runtime Roles

正式角色：

```text
planner
writer
reviewer
canon_reviewer
steward
advisor
```

要求：

- Writer 与 Reviewer 不共享会话。
- Advisor 不拥有写权限。
- Steward 只能执行策略允许的代理用户决策。
- Canon Reviewer 不直接 Apply。
- Subagent 不写正文。

## 8.4 Blind Review

Reviewer 默认读取：

- Candidate；
- Canon；
- Character；
- Selected Branch；
- Word Budget；
- Reader/Rhythm/Bridge；
- Style；
- Review Rubric；
- Deterministic Lint。

Reviewer 默认不读取：

- Writer 自我说明；
- 隐藏推理；
- 无关任务日志；
- 被拒版本。

## 8.5 Revision Map

新增 Schema：

```text
_engine/schemas/revision_map.v1.json
```

每条：

- finding_id；
- original_location；
- problem_type；
- required_change；
- applied_change；
- new_location；
- semantic_preservation；
- style_preservation；
- exception_reason；
- status。

Re-review 检查：

- 原问题解决；
- 没有换一种同类问题；
- 没有语义反转；
- 没有破坏 Canon；
- 没有破坏文风；
- 字数仍合规；
- Bridge 与 Rhythm 仍合规。

## 8.6 Prompt Compiler

新增推荐模块：

```text
src/literary_engineering_studio_engine/prompt_compiler.py
src/literary_engineering_studio_engine/prompt_conflicts.py
tests/test_prompt_compiler.py
```

优先级固定：

1. 用户硬约束、Canon、事实；
2. Branch、Scene Function、人物行为；
3. Mounted Style；
4. Reader、Rhythm、Bridge、Budget；
5. 标点、Style Lint 预防、反模板；
6. Revision 局部要求。

输出：

- `active_constraints`；
- source refs；
- suppressed constraints；
- conflict report；
- justified exceptions。

## 8.7 文风与反 AI 规则

规则不能简单全局“一刀切”。

文风可声明：

- 核心修辞；
- 允许频率；
- 合理例外；
- 禁止变体；
- 与通用规则冲突时的裁决。

确定性 Lint 只负责发现，不自动语义改写正文。

禁止用正则直接把“不是 A，是 B”改成可能反转含义的句子。

## 8.8 测试

新增：

```text
tests/test_review_session_independence.py
tests/test_revision_map.py
tests/test_prompt_compiler.py
tests/test_prompt_conflicts.py
```

聚焦：

```powershell
python -m unittest tests.test_review_session_independence tests.test_revision_map tests.test_prompt_compiler tests.test_prompt_conflicts tests.test_prompt_evaluation tests.test_scene_review_revision_loop -v
```

## 8.9 退出门禁

- Writer 与 Reviewer Session 可证明不同。
- Review 绑定精确 Candidate SHA。
- Revision 有逐项证据。
- Prompt 冲突可见，不静默覆盖。
- Lint 不自动破坏语义。

## 8.10 建议提交

```text
feat: isolate literary review and compile active constraints
```

---

# Batch 9：State / Canon Decision-Apply 完整闭环

## 9.1 目标

State 和 Canon 都形成：

```text
Candidate
→ Review
→ Decision
→ Apply
→ Context Invalidation
```

## 9.2 必读

```text
character_state_evolver.py
character_state_apply.py
canon_evolver.py
canon_lint.py
agent_canon_review.py
project_interaction.py
autopilot.py
choice_effect_materialization 相关代码
client/src/stores/humanChoices.ts
```

## 9.3 State Decisions

补齐 `state_patch_confirmation` 的实际 Choice Producer。

前端卡片显示：

- 哪个角色；
- 哪项状态变化；
- 正文证据；
- 对后续行为影响；
- 接受、拒绝、要求修订。

提交后必须：

- 生成幂等 Receipt；
- Materialize Decision；
- Apply 或 Rejection；
- 消费 Choice；
- 卡片消失；
- 刷新后不复现。

## 9.4 Canon Decisions

保留现有 Canon Approval，但升级为统一 Contract。

显示：

- 目标 Canon；
- 变化前后；
- 证据；
- 冲突；
- 影响范围；
- 是否不可逆。

## 9.5 下一场一致性

默认强一致策略：

- 上一场 State Candidate 必须 Accept+Apply 或 Reject。
- 上一场 Canon Candidate 必须 Accept+Apply、Reject 或明确标记“不形成 Canon”。
- 未决时下一场 Context 阻塞。

如果将来支持宽松模式，必须把 approved pending delta 注入 Context；本轮不优先实现。

## 9.6 Apply

- 使用 Batch 3 原子事务。
- 目标摘要冲突时不覆盖。
- Apply 后更新 revision。
- 失效下游 Context。
- 写入 Audit Log。

## 9.7 测试

新增或扩展：

```text
tests/test_state_patch_route.py
tests/test_state_patch_choices.py
tests/test_canon_patch_route.py
tests/test_choice_effect_materialization.py
tests/test_context_freshness.py
```

聚焦：

```powershell
python -m unittest tests.test_state_patch_route tests.test_state_patch_choices tests.test_canon_patch_route tests.test_choice_effect_materialization tests.test_context_freshness -v
```

## 9.8 退出门禁

- State 不再形成无出口 Backlog。
- Canon 与 State 使用同类审计语义。
- 选择卡与后端真实状态一致。
- 下一场不会忽略上一场状态变化。

## 9.9 建议提交

```text
feat: complete state and canon decision-apply loops
```

---

# Batch 10：Runtime 性能、安全、SSE 与启动可靠性

## 10.1 目标

长时间自动创作不会因扫描、连接、竞态、二进制信任或启动判断而失效。

## 10.2 Read Model Cache

### 必读

```text
read_model_cache.py
core_read_models.py
api_server.py
live_events.py
client/src/services/api.ts
client/src/stores/app.ts
```

### 实施

- 建立 project revision。
- 文件 watcher 增量更新 revision。
- watcher 不可用时低频扫描。
- Cache Key 使用 project+revision+view。
- TTL 必须实际执行。
- Styles、Exports、Release、Decision、Ledger 纳入 revision。
- SSE 推送事件和 revision，不每次全量扫描。

## 10.3 SSE

- 指数退避。
- 随机抖动。
- Last-Event-ID。
- 网络恢复。
- Event ID 幂等。
- 项目切换取消旧连接。
- UI 显示连接状态但不打扰创作。

## 10.4 项目切换竞态

- AbortController 取消旧请求。
- 响应携带 project_id 与 revision。
- Store 提交前核对当前项目。
- 旧响应不得覆盖新项目。

## 10.5 API 安全

- 默认 `127.0.0.1`。
- 绑定非 loopback 时没有 Token 必须拒绝启动。
- 桌面启动生成短期 Token。
- 读写 API 默认鉴权。
- CORS 只允许明确来源。
- 日志过滤 Token、模型认证和完整敏感路径。

## 10.6 OpenCode 验证

Manifest 按版本、平台、架构记录：

- archive SHA256；
- binary SHA256；
- source URL；
- license；
- version。

已存在二进制也必须比对 binary SHA。失败则隔离。

## 10.7 桌面启动

- Sidecar 绑定端口 0。
- 通过受控 IPC 返回实际端口。
- `/health` 返回 app id、version、nonce、protocol version。
- Tauri 只接受匹配 nonce。
- 加载界面等到真实 ready。
- Windows 后台进程不闪终端窗口。

## 10.8 Autopilot 无进展

进度指纹至少含：

- current route；
- task_id；
- route audit digest；
- formal artifact digests；
- pending choices；
- workflow revision。

规则：

- Worker Complete 但指纹不变，不记进度。
- 连续两轮提示 slow。
- 连续三轮尝试一次恢复。
- 恢复后仍不变，暂停 `no-progress`。
- 不无限重启 Runtime。

## 10.9 测试

新增或扩展：

```text
tests/test_read_model_revision.py
tests/test_sse_reconnect.py
tests/test_project_switch_race.py
tests/test_api_auth_binding.py
tests/test_opencode_binary_trust.py
tests/test_bootstrap_readiness.py
tests/test_autopilot.py
```

前端：

```text
client/src/services/api.spec.ts
client/src/stores/app.spec.ts
```

聚焦：

```powershell
python -m unittest tests.test_read_model_cache tests.test_read_model_revision tests.test_api_server tests.test_api_auth_binding tests.test_opencode_binary_trust tests.test_bootstrap_readiness tests.test_autopilot -v
npm run client:test
```

## 10.10 性能验收

准备 100、1,000、10,000 文件项目：

- Dashboard 请求不应每次全量扫描。
- SSE 空闲时 CPU 与磁盘占用稳定。
- 50 万字 Reader 不加载全部正文到初始响应。
- 连续 100 场景任务无持续内存增长。

## 10.11 退出门禁

- 非本地服务无 Token 无法启动。
- 被替换 OpenCode 无法运行。
- 项目切换无旧响应污染。
- 自动创作能识别空转。
- 桌面 readiness 验证的是正确服务。

## 10.12 建议提交

该 Batch 可以拆成三个提交：

```text
perf: make project read models revision-driven
security: verify local API and agent binaries
fix: harden desktop readiness and autopilot recovery
```

---

# Batch 11：渐进模块化、前端投影与仓库治理

## 11.1 目标

降低后续扩展成本，不改变外部正式契约。

## 11.2 渐进拆分

当前大模块不能一次性重写。先写 characterization tests，再移动。

### API

从 `api_server.py` 渐进提取：

```text
api/projects.py
api/workflow.py
api/runtime.py
api/decisions.py
api/library.py
api/settings.py
api/release.py
```

### Jobs

从 `jobs.py` 提取：

```text
jobs/lifecycle.py
jobs/execution.py
jobs/autopilot.py
jobs/recovery.py
jobs/telemetry.py
```

### Task Registry

按 Route 提取：

```text
routes/scene_development.py
routes/longform_planning.py
routes/source_ingest.py
routes/style_engineering.py
routes/character_world.py
routes/review_audit.py
routes/export_release.py
```

共用 `task_contracts.py`。

### CLI

拆为：

- Formal Surface；
- Internal Route Commands；
- Maintainer Diagnostics。

普通 `--help` 只显示正式面和 Studio 用户命令。

## 11.3 前端 Read Models

前端新增或升级：

- Task Contract 人类可读投影；
- Agent Session 与 Writer/Reviewer Role；
- Story Architecture；
- Global Rhythm；
- Reader Questions；
- Promise/Payoff；
- State/Canon Decisions；
- Stale Context；
- Repair Tasks。

前端不得解析内部 Sidecar Markdown 来判断状态。

## 11.4 用户交互

用户可以管理：

- 创作方向；
- 文风挂载；
- 节奏偏好；
- Branch Selection；
- State/Canon Decision；
- Revision 方向；
- 扩纲方向。

用户修改先产生 Candidate/Decision，不直接写正式文件。

## 11.5 CSS 治理

- 建立 token 层。
- 清除重复组件选择器。
- 限制全局 `!important`。
- 定义 z-index 层级表。
- 窗口拖动前后尺寸一致。
- 面板内容使用独立滚动区。
- Markdown 使用 `SafeMarkdown`。
- 不引入白色裸露控件破坏主题。

本轮前端以功能投影为主，不重新设计整个星仪视觉。

## 11.6 Git 与 CI

新增 PR/Push CI：

```text
Python tests
compileall
Prompt Registry
Task Contract Audit
Frontend tests
Frontend build
Rust check
Packaging smoke
```

治理：

- `.gitignore` 忽略日志与临时产物。
- `.gitattributes` 统一换行。
- Python 依赖锁。
- 保留 `package-lock.json` 和 `Cargo.lock`。
- 单一版本源同步 Python、Node、Tauri 和 Release。
- 发布生成 SBOM 与 SHA256。

## 11.7 测试

- API 拆分前后契约快照一致。
- Route 拆分前后 Task 顺序一致。
- 前端不依赖内部路径。
- CSS 做桌面和小窗口截图。
- CI 在无模型密钥环境可运行确定性测试。

## 11.8 退出门禁

- 大模块已按安全边界开始拆分。
- 外部 API/CLI 不破坏。
- 前端能展示新增文学机制。
- 工作树不再被日志污染。
- PR/Push 有完整 CI。

## 11.9 建议提交

允许按模块拆分，但每个提交必须可运行：

```text
refactor: split formal route registries without contract changes
refactor: split Studio APIs behind stable read models
feat: project literary reliability into the client
chore: harden CI and repository hygiene
```

---

# Batch 12：Golden Projects、全量验收、安装与发布准备

## 12.1 目标

证明系统不仅通过单元测试，也能完整创作、审查、演化和交付。

## 12.2 Golden Projects

在 `tests/fixtures/` 或专用生成器中建立不含版权内容的小型项目：

1. 单主角线性悬疑。
2. 多角色利益冲突。
3. 强文风历史叙事。
4. 多卷成长小说。
5. 高 Canon 密度架空世界。
6. 已有文本续写/改写。

Fixture 不要提交真实模型大段生成正文。可使用短小人工测试段落和可选 Live Test。

## 12.3 每个项目必须验证

```text
project create
→ story architecture
→ word budget
→ global rhythm
→ scene inventory
→ character/world assets
→ context
→ roleplay
→ branch
→ composition
→ prose candidate
→ independent review
→ revision if needed
→ promotion
→ state/canon decision-apply
→ handoff
→ next scene
→ longform audit
→ repair task if needed
→ Markdown/DOCX export
```

## 12.4 故意植入错误

Golden Tests 必须植入并拦截：

- 角色违反 moral_line；
- Branch 无代价；
- Context 使用旧 Canon；
- 前后场景空间不连续；
- 未兑现 Promise；
- 预算不足；
- 连续高压；
- 文风冲突；
- “不是——是”变体；
- Review 审 A 晋升 B；
- State Patch 无正文证据；
- Canon Patch 改禁止项；
- Completion-only 输出；
- Submit 中途失败。

## 12.5 全量自动验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src
python -m literary_engineering_studio doctor
python -m literary_engineering_studio --help
python -m literary_engineering_studio_engine prompt-registry-validate --json
python -m literary_engineering_studio prompt-eval --output dist/prompt-evaluation.json
npm run client:test
npm run client:build
Push-Location desktop/src-tauri
cargo check --locked
Pop-Location
git diff --check
```

## 12.6 API 验收

使用新建项目验证：

- `/health`
- `/projects`
- `/runtime/adapters`
- Workflow Read Model
- Reader Read Model
- Human Choices
- State/Canon Decisions
- Rhythm/Architecture
- Agent Sessions
- SSE

验证：

- Token；
- Project ID；
- Revision；
- Event ID；
- Markdown 安全渲染；
- 切项目；
- 断线重连。

## 12.7 前端验收

至少验证：

- 1440×900；
- 1920×1080；
- 1280×720；
- 小窗口；
- Windows 缩放 125% 与 150%。

检查：

- 无遮挡；
- 无横向溢出；
- 面板可滚动；
- 决策卡能消失；
- Reader 能边创作边阅读；
- Rhythm 与 Ledger 可读；
- Agent Session 角色明确；
- 错误信息不暴露敏感绝对路径；
- 所有 Markdown 安全渲染。

## 12.8 桌面候选

构建：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/build_desktop.ps1 -SkipPythonInstall -SkipNodeInstall
```

必须在干净 Windows 环境验证：

- 首次安装；
- 默认作品库；
- 新建项目；
- OpenCode 安装与摘要；
- 模型连接；
- 首个任务；
- 重启恢复；
- 覆盖升级；
- 卸载；
- 无终端窗口闪烁；
- 安装器不因已运行进程无法覆盖二进制；
- 更新清单与签名。

## 12.9 交付报告

创建：

```text
docs/verification/cli-literary-reliability-final-verification.md
```

包含：

- 实施范围；
- 每个 Batch 提交；
- 数据迁移；
- 新增 Schema；
- 新增 Route/Task；
- 测试结果；
- Golden Project 结果；
- 性能结果；
- 安全结果；
- 安装结果；
- 未完成项；
- 已知限制；
- 回滚方法。

## 12.10 发布门槛

全部满足才能发布：

1. Contract Audit 通过。
2. Prompt Registry 通过。
3. Python 全量通过。
4. Frontend Test/Build 通过。
5. Rust Check 通过。
6. Golden Projects 通过。
7. P0/P1 文学门禁通过。
8. API 非本地鉴权通过。
9. OpenCode 摘要验证通过。
10. Windows 安装与升级通过。
11. 无真实密钥。
12. 无未跟踪构建垃圾被提交。
13. Release Notes、版本、Tag 一致。

## 12.11 建议提交

```text
test: verify end-to-end literary reliability
docs: record CLI literary reliability delivery
```

---

## 10. 数据迁移总则

### 10.1 不破坏旧项目

旧项目打开时：

- 自动备份元数据。
- 识别旧 Schema。
- 只迁移能确定转换的字段。
- 不覆盖正文。
- 不删除旧 Candidate/Review。
- 不能迁移时生成正式 Repair Task。

### 10.2 旧 Completion

旧 Completion 不能自动升级为语义完成。

状态：

```text
legacy_verified
legacy_migratable
legacy_unverified
```

- 能从旧产物验证内容：`legacy_verified`。
- 能转换：迁移后重新验收。
- 只有 Marker：`legacy_unverified`，重新执行任务。

### 10.3 Schema 版本

- Reader 必须支持当前版本与上一个正式版本。
- Writer 只写最新版本。
- 每个迁移函数必须幂等。
- 每个迁移必须有 Fixture。

### 10.4 Context 失效

迁移后：

- 旧 Context 默认 stale。
- 已晋升正文保留。
- 重新生成 Context/Handoff。
- Review 只有候选摘要仍匹配时保留。

---

## 11. 测试编写标准

### 11.1 单元测试

测试具体不变量，不只测试“返回非空”。

错误：

```python
self.assertTrue(result)
```

正确方向：

```python
self.assertEqual(result["verdict"], "block")
self.assertIn("candidate_sha256", result)
self.assertEqual(result["source_digests"]["roleplay"], expected_sha)
```

### 11.2 契约测试

Task、Schema、Prompt、Worker、Route Gate 应形成一组契约测试。

### 11.3 文学逻辑测试

不能只靠字符串断言。使用小型结构化 Fixture：

- 角色信念；
- 欲望；
- 恐惧；
- 道德底线；
- Scene 目标；
- 故意冲突 Branch；
- 预期 Review 结论。

### 11.4 快照

快照适合：

- Task Package；
- API Read Model；
- Prompt Asset 编译结果；
- CLI Help。

快照不适合掩盖语义变化。更新快照前必须阅读差异。

### 11.5 Live Model Tests

Live Tests：

- 默认不进入无凭证 CI。
- 使用显式开关。
- 记录 Runtime 与模型。
- 不因模型随机波动成为唯一发布门禁。
- 与确定性 Schema、Lint 和 Contract Gate 配合。

---

## 12. 文学质量验收 Rubric

每个 Golden Project 至少按以下维度人工或独立 Agent 审查：

| 维度 | 合格标准 |
|---|---|
| 人物因果 | 行动来自 belief/desire/fear/moral_line，而非剧情便利 |
| 场景功能 | 每场改变关系、信息、选择、压力或代价 |
| 分支质量 | 分支有真实差异、代价与不可逆点 |
| 连续性 | 时间、地点、物件、状态、关系与信息分布连续 |
| 长篇脊柱 | 主题矛盾、变化向量和终局选择可追踪 |
| 节奏 | 过场、蓄压、高潮、余波有区别 |
| 详略 | 字数服务场景功能，不靠形容词堆积 |
| Reader Question | 问题被推进、延迟、反转或兑现 |
| Promise/Payoff | 承诺有铺垫、有到期、有证据 |
| 文风 | 文风进入生成且不被通用规则误杀 |
| 降低 AI 味 | 避免机械对照、器官轮岗、万能意象和模板转折 |
| 审查独立性 | Reviewer 不给自己无条件放行 |
| 最终作品 | 不含工作流、Canon、Patch、Scene ID 等痕迹 |

任一核心维度 Block 时，不得以总平均分掩盖。

---

## 13. 失败处理

### 13.1 测试失败

1. 先判断是基线失败还是本轮回归。
2. 只修当前 Batch 范围内问题。
3. 不删除失败测试。
4. 不降低断言以换取通过。
5. 记录根因。

### 13.2 Runtime 不可用

- 不改用隐藏 HTTP Provider。
- 不伪造 Live Test 通过。
- 完成确定性开发与测试。
- 在验证报告标明 Live Test 待外部环境。

### 13.3 迁移不确定

- 不猜。
- 保留原文件。
- 标记项目需要 Repair。
- 提供人类可读原因。

### 13.4 文学规则冲突

按 Prompt 优先级裁决。无法自动裁决时生成 Decision，不静默选择。

### 13.5 当前 Batch 过大

可拆分提交，但不能跨越退出门禁。每个子提交必须保持测试可运行。

---

## 14. 禁止事项总表

负责开发的 Agent MUST NOT：

1. 推倒重写状态机。
2. 新建第二套项目格式。
3. 用更多 Agent 角色掩盖 Contract 缺陷。
4. 让 Completion 替代语义产物。
5. 让前端直接写正式文件。
6. 让 Subagent 写正文。
7. 让同一 Session 写稿并正式审稿。
8. 用正则自动改写可能改变语义的文学句子。
9. 把被拒分支放入默认生成记忆。
10. 让未决 State/Canon 被下一场忽略。
11. 在非本地 API 无鉴权时启动。
12. 只检查 OpenCode 文件存在。
13. 用全量递归扫描支撑高频 SSE。
14. 为解决模块过大一次性重写 API/Jobs/Task Registry。
15. 修改用户系统 PowerShell 策略。
16. 提交真实密钥、作品正文样本或用户绝对路径。
17. 使用 Debug Waiver、`unreview` 或 `LEW_MAINTAINER_MODE` 绕过正式门禁。
18. 未做 Windows 安装验收就发布。

---

## 15. Definition of Done

开发 Agent 只有在以下条件全部满足时，才能回复“全部完成”：

### Contract

- [ ] Task Contract v2 已生效。
- [ ] Contract Audit 在 CI 中通过。
- [ ] 无正式语义任务仅靠 Completion。

### Literary Chain

- [ ] RP 被 Branch 消费。
- [ ] Branch 被 Composition 消费。
- [ ] Composition Review 可返修。
- [ ] Context 有摘要和新鲜度。
- [ ] Scene Handoff 生效。
- [ ] Story Architecture 生效。
- [ ] Global Rhythm 进入 CLI。
- [ ] Reader/Promise Ledger 生效。
- [ ] Writer/Reviewer 隔离。
- [ ] State/Canon 完整 Apply。

### Engineering

- [ ] Task Finalize 原子。
- [ ] 失败恢复通过。
- [ ] Cache 增量化。
- [ ] SSE 可恢复。
- [ ] API 鉴权安全。
- [ ] OpenCode 摘要可信。
- [ ] Desktop Readiness 正确。
- [ ] Autopilot 无进展可识别。

### Quality

- [ ] Python 全量测试通过。
- [ ] Prompt Registry 通过。
- [ ] Contract Audit 通过。
- [ ] Frontend 测试和构建通过。
- [ ] Rust Check 通过。
- [ ] Golden Projects 通过。
- [ ] Windows 安装/升级通过。
- [ ] Final Verification 文档完成。

### Git

- [ ] 每个 Batch 有清楚提交。
- [ ] 无日志和临时文件。
- [ ] 无真实密钥。
- [ ] 版本与 Release Notes 一致。

---

## 16. 最终交付回复模板

完成后向用户汇报：

```markdown
已按《ArcVellum CLI 文学可靠性完整优化执行指令》完成全部 Batch。

## 核心交付

- Task Contract：
- 原子写回：
- RP/Branch/Composition：
- Context/Handoff：
- Longform/Rhythm：
- Reader/Promise Ledger：
- Review/Revision：
- State/Canon：
- Runtime/Security：
- Frontend：

## 验证

- Python：
- Prompt Registry：
- Contract Audit：
- Frontend Tests：
- Frontend Build：
- Rust：
- Golden Projects：
- Windows Installer：

## Git

- Branch：
- Final commit：
- Release：

## 已知限制

- ...
```

如果任一 Final Gate 未通过，必须写“尚未完成”，明确剩余工作和阻塞，不得用“基本完成”代替。

---

## 17. 最后原则

本轮优化的判断标准不是文件更多、Prompt 更长或 Agent 角色更多。

判断标准只有三个：

1. **每个正式任务是否真的产出了它声称产出的文学信息。**
2. **这些信息是否被下一环节实际读取并影响结果。**
3. **失败、旧上下文、自我审查、未应用变化和前端旁路是否还能伪装成完成。**

只要其中任何一项答案仍然是“可能”，本轮优化就没有完成。
