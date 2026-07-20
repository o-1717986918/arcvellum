# Phase 84：CLI 中介 Agent 工作流内核

版本：`v0.84.6`

## 目标

把正式 `scene-development` 从“平台 Agent 自己按文档记忆串命令”，推进为“CLI 根据持续状态机派发下一项正式任务”。用户仍和平台 Agent 自然对话；但正式产物由 CLI 发任务、平台 Agent 执行、CLI 收提交、校验 expected outputs 并写 completion marker。

## 新增模块

- `src/literary_engineering_workbench/task_registry.py`

核心函数：

- `issue_next_task()`：基于 `workflow_state.py` 派发下一项任务。
- `open_task()`：标记任务已打开，并重写可读任务包。
- `submit_task()`：记录平台 Agent 输出的产物路径。
- `complete_task()`：检查 expected outputs，写 `.agent_completion.json`，刷新 workflow state。
- `advance_workflow()`：刷新 artifact-derived 状态，不允许手动跳状态。
- `build_workflow_events()`：渲染 task event log。

## 新增 CLI

```powershell
python -m literary_engineering_workbench task-next <project> --route scene-development
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
python -m literary_engineering_workbench workflow-advance <project> --route scene-development
python -m literary_engineering_workbench workflow-events <project>
```

## 新增文件契约

- `schemas/agent_task.v1.json`
- `schemas/agent_submission.v1.json`
- `schemas/agent_completion.v1.json`

任务文件写入：

- `workflow/tasks/{task_id}.task.json`
- `workflow/tasks/{task_id}.agent_tasks.md`
- `workflow/tasks/{task_id}.submission.json`
- `workflow/tasks/{task_id}.agent_completion.json`

事件文件写入：

- `workflow/events/task_events.jsonl`
- `workflow/events.md`

## 当前接入范围

第一版以 `scene-development` 为样板，并将已有 `workflow_state.py` 的当前步骤映射为 task package。覆盖步骤包括：

1. context packet
2. roleplay simulation
3. roleplay sidecar completion
4. branch manifest
5. branch sidecar completion
6. branch selection
7. scene composition
8. composition sidecar completion
9. word-budget contract
10. prose candidate generation provenance
11. generation sidecar completion
12. exact-candidate AgentReview
13. AgentReview sidecar completion
14. candidate promotion
15. promoted draft
16. static review
17. state patch
18. state sidecar completion

## 关键设计选择

### 1. 状态派生，不手动写死

`workflow-advance` 不接受 “advance-to ready” 之类参数。它只重新运行 `workflow_state.py`，根据真实项目文件和 gate 推导状态。这避免 Agent 用状态命令绕过产物。

### 2. 新 task registry 不删除旧 sidecar

当前版本采用双层兼容：

- `workflow/tasks/*.agent_tasks.md` 是统一控制任务包。
- 原命令生成的 sidecar 仍保留在原位置。
- 上层 task 可以要求平台 Agent 处理原 sidecar，并把原 sidecar 的 completion marker 作为 expected output。

后续 Phase 85-87 可以逐步把 Prompt Registry、Context Broker 和完整状态机接入，减少双层感。

### 3. CLI 不是创作权威

CLI 只负责：

- 发任务
- 输出约束
- 记录提交
- 检查文件存在和部分确定性 gate
- 写 completion marker
- 刷新状态

正文、审查、分支判断、角色推演、状态解释仍由主平台 Agent 完成。

## 已修复的相关问题

初始化模板允许 `scene_id: ""`。`workflow_state.py` 过去会把空 scene id 当成有效 id，导致状态路径变成 `branches/`、`_composition.json`、`reviews/agent/_scene_review.json`。本阶段已修正：空 scene id 自动回退到文件名 stem，例如 `scene_0001.yaml` -> `scene_0001`。

## v0.84.1 深度门禁硬化

`task-complete` 已从“expected outputs 存在性检查”升级为“按 `current_state` 调用真实 route gate”。这一步专门修复平台 Agent 手写同名文件、漏读 sidecar、跳过 word budget、跳过 AgentReview 或用 debug-waiver promotion 伪装完成的问题。

当前接入：

- `roleplay-simulation`：检查 `simulate-scene` CLI 来源标记。
- `branch-manifest` / `branch-agent-task`：检查 `branch_manifest.json` 的 `formal_cli_provenance.created_by=branch-simulate` 和 `agent_tasks_requested=true`。
- `branch-selection`：复用 `branch_selection_status()`，必须有 `decision: selected` 与 `selected_branch`。
- `composition-json` / `composition-agent-task`：复用 `ensure_composition_ready_for_generation()`，必须由 `compose-scene` 生成、基于正式 branch selection 且请求 sidecar。
- `scene-word-budget-contract`：复用 `ensure_scene_word_budget_ready()`，并额外检查 scene inventory sidecar/review。
- `candidate-generation-provenance` / `generation-agent-task`：复用 `candidate_generation_gate()`，并对 cleaned body 运行 Style Lint Gate 与场景字数预算 adherence。
- `candidate-review` / `agent-review-task`：复用 `candidate_generation_gate()` 与 `candidate_review_gate()`，要求 exact-candidate clean pass。
- `promotion-manifest` / `promoted-draft`：回查 promotion manifest，拒绝 `allow_unreviewed` / `allow_review_notes`，并重新验证 candidate generation 与 review gate。
- `static-review`：要求 `reviews/{scene_id}-review.md` 结论为 `pass`。
- `state-patch-json` / `state-agent-task`：检查 state patch JSON 可解析、schema 正确、scene_id 匹配且仍处于候选/审查/审批边界。

## v0.84.2 Route Registry 与 Longform 接入

`task_registry.py` 已从单一路线实现改为 route registry 分发表。每条路线定义：

1. `select_work_item`：从 `workflow-state` 中选择当前待处理工作项。
2. `build_task`：生成 CLI 中介平台 Agent 任务包。
3. `validate_task`：在 expected outputs 存在后执行路线专属真实门禁。
4. `ready_message`：路线完成时返回的说明。

当前已注册：

1. `scene-development`
2. `longform-planning`
3. `source-ingest`
4. `style-engineering`
5. `character-and-world-assets`
6. `review-and-audit`
7. `export-and-release`

`workflow-state --route longform-planning` 现在会输出 Longform State，包含：

1. `word-budget-file`
2. `budget-agent-task`
3. `budget-review`
4. `scene-inventory-agent-task`
5. `scene-inventory-review`

`task-next --route longform-planning` 使用同一套 `task-open` / `task-submit` / `task-complete` 生命周期。该路线的关键门禁：

1. `word_budget.json` 必须存在、schema 正确、目标中文内容字符为正、包含 `chapter_budgets` 与 `scene_inventory_binding`。
2. `word_budget.agent_tasks.md` 与 `scene_inventory_expansion.agent_tasks.md` 必须存在。
3. `word_budget.agent_completion.json` 不能单独放行，`plot/candidates/outlines/word_budget_expansion.md` 也必须存在。
4. `scene_inventory_expansion.agent_completion.json` 不能单独放行，`plot/candidates/scenes/word_budget_scene_inventory.md` 也必须存在。
5. `reviews/word_budget/word_budget_review.md` 和 `reviews/word_budget/scene_inventory_review.md` 结论必须为 clean `pass`；`pass_with_notes` 阻塞。

这一步修复了历史问题：预算工具生成了文件，但平台 Agent 后续写场景时没有读取预算任务、没有把目标字数/场景库存变成硬约束。现在长篇规划可以作为正式 route 被状态机持续追踪。

## v0.84.3 Source-ingest 接入

`source-ingest` 已成为第三条 registered route。它不替代导入命令本身：起点仍是 `source-ingest` / `extract-existing-work` 写入 raw source、chunks、manifest、report 和 `extract_project_files.agent_tasks.md`。一旦导入存在，正式反推流程由 task registry 接管。

`workflow-state --route source-ingest` 会扫描 `sources/imports/*/source_manifest.json`，为每个导入生成状态：

1. `source-manifest`
2. `extraction-agent-task`
3. `extraction-review`

`task-next --route source-ingest` 会派发当前第一个 blocked import。关键门禁：

1. `source_manifest.json` 必须存在、schema 正确、包含 `work_id`、chunks 和 `candidate_outputs`。
2. `source_ingest.md` 与 `extract_project_files.agent_tasks.md` 必须存在。
3. `extract_project_files.agent_completion.json` 不能单独放行，manifest 中列出的 candidate outputs 也必须存在。
4. 候选输出包括 project brief、characters/background stories、world、outline、timeline、foreshadowing、style notes 和 extraction review。
5. `reviews/source_ingest/{work_id}_extraction_review.md` 结论必须为 clean `pass`；`pass_with_notes` 阻塞。

这一步修复“已有作品导入了，但平台 Agent 没有真正反推标准项目文件”的漏洞。source-derived 内容仍保持候选性质，不能直接覆盖正式 canon、characters、plot、drafts、exports 或 releases。

## v0.84.4 Style-engineering 接入

`style-engineering` 已成为第四条 registered route。它面向项目内 `style/{profile}/` profile 目录；项目根 `style/style-profile.md` 占位文件会被跳过，避免误报。

`workflow-state --route style-engineering` 会扫描 `style/**/style-profile.md`，并为每个 profile 生成状态：

1. `style-profile`
2. `style-prompt-task-file`
3. `style-prompt-agent-task`
4. `style-prompt-quality`
5. `style-eval-readiness`

关键门禁：

1. `style-profile.md` 与 `style_metrics.json` 必须存在。
2. `style_prompt.agent_tasks.md` 必须由 `style-prompt` 或等价正式任务生成。
3. 平台 Agent 必须写出 `style_prompt.md` 与 `style_prompt.agent.json`，并创建 `style_prompt.agent_completion.json`。
4. `style_prompt.md` 必须通过 `style_prompt_quality_report()`：500-2500 中文内容 detail chars，计入汉字和中文标点，不计入 Markdown 标记、英文路径、代码围栏或空白，且包含身份/边界、核心风格机制、叙述距离、句法/节奏、标点、意象/感官、心理/行为、对白、AI 腔控制、禁止倾向和输出自检。
5. 至少一个 `evaluation_results/*/style_eval_*.json` 被接受：`overall_score >= 45`，且 `risk_level` 不是 `high_copy_risk` 或 `low_similarity`。

这一步修复“文风 profile 已生成，但实际挂载的 prompt 过短、过泛或未评测”的漏洞。统计 profile、style_metrics 和 dry-run 文档都不能代替可执行的 LLM-facing style prompt。

## v0.84.5 Character-and-world-assets 接入

`character-and-world-assets` 已成为第五条 registered route。它面向候选人物、隐藏背景故事、关系图、世界规则、地点、组织、大纲、章节计划和场景列表，覆盖从创建 sidecar 到正式晋升的完整资产链路。

`workflow-state --route character-and-world-assets` 会扫描候选资产目录与资产创建 sidecar，并为每个候选生成状态：

1. `asset-intake`
2. `asset-creation-agent-task`
3. `asset-review-task-file`
4. `asset-review-agent-task`
5. `asset-review-pass`
6. `asset-approval`
7. `asset-promotion`

关键门禁：

1. `asset-create` / `agent-create-*` 只生成平台 Agent 创建任务，不代表候选已完成。
2. 候选 JSON 和候选 Markdown 报告必须存在，候选 JSON 必须通过资产 schema，并包含 `candidate_id`、`risks`、`source_paths`、`promotion_notes`。
3. `review-candidate-asset` 只生成审查 sidecar；平台 Agent 必须写入 `reviews/assets/{candidate_id}_review.json` 与 `.md`，并创建 completion marker。
4. 资产审查必须 clean `pass`，不能带 blocking issues 或 unresolved revision actions。
5. Review 不是 approval。晋升前必须有匹配 candidate_id 的用户 approve 记录。
6. `promote-candidate-asset` 不能使用 `--allow-unapproved`，promotion manifest 的输出必须真实存在。
7. `route-audit --route character-and-world-assets` 会逐候选检查 creation sidecar、review sidecar、clean review、approval、promotion 和输出文件。

这一步修复“角色/世界资产虽然是候选机制，但仍可被平台 Agent 手写候选、跳过审查或用 approval bypass 晋升”的漏洞。角色背景故事、世界规则和大纲等上游资产现在也进入 CLI 中介状态机。

## v0.84.6 Review / Export 接入

`review-and-audit` 与 `export-and-release` 已成为第六、七条 registered route。两者把项目后段最容易被跳过的“总审查”和“最终交付”纳入统一 `task-next -> task-open -> task-submit -> task-complete` 控制面。

`workflow-state --route review-and-audit` 会生成项目级状态：

1. `canon-lint-file`
2. `canon-review-task-file`
3. `canon-review-agent-task`
4. `canon-review-pass`
5. `longform-audit-file`
6. `committee-task-file`
7. `committee-agent-task`
8. `committee-pass`

关键门禁：

1. `canon-lint` 必须写出 Markdown/JSON，schema valid，blocking_count 为 0。
2. `agent-canon-review` 只生成平台 Agent sidecar；平台 Agent 必须写 canon review JSON/Markdown 和 completion marker。
3. canon review 必须 clean `conclusion=pass`，不能带 blocking issues、warnings、unresolved facts 或 timeline risks。
4. `longform-audit` 必须写出 Markdown/JSON 与 `plot/longform_graph.json`。
5. `agent-committee` 只生成 sidecar；平台 Agent 必须写 committee JSON/Markdown 和 completion marker。
6. committee review 必须 `final_recommendation=approve`，且没有 action_items 或 disagreements。

`workflow-state --route export-and-release` 会按 chapter 生成状态：

1. `chapter-workspace`
2. `export-package`
3. `release-approval`
4. `publish-release`

关键门禁：

1. `chapter-workspace` 必须写出 Markdown/JSON，ready_count > 0 且 blocked_count = 0。
2. `export-package` 必须 schema valid，`include_blocked=false`，`skipped_scenes=[]`，请求输出真实存在。
3. 读者交付文件不得泄漏 scene ID、canon/review/workflow/state/writeback 标记、内部路径或 `[AGENT_TASK: ...]`。
4. 发布前必须有 `release-{chapter_id}` 的人类 approve 记录。
5. `publish-chapter` 必须写 formal-release manifest、release notes、rollback、latest 指针和请求输出；manifest approval 必须为 approve，latest 必须指向 formal-release manifest。

这一步修复“最终审查靠自觉、longform/canon/committee 审查旁路、导出用自写脚本、发布缺审批、最终正文夹带工程痕迹”的漏洞。

## 测试

新增：

- `tests/test_task_registry.py`

覆盖：

- `task-next` 能为首个 blocked scene 发 context task。
- `task-open` 标记任务 opened。
- `task-submit` 记录存在的 artifact。
- `task-submit` 拒绝不存在的 artifact。
- `task-complete` 拒绝缺失 expected outputs。
- `task-complete` 写 completion marker 和 event log。
- `task-complete` 拒绝手写 composition 缺 CLI provenance。
- `task-complete` 拒绝候选正文缺 generation provenance。
- `task-complete` 拒绝候选正文 Style Lint blocking。
- `task-complete` 拒绝 `pass_with_notes` AgentReview。
- `task-complete` 拒绝未处理 word-budget sidecar。
- `task-next --route longform-planning` 能发出 word-budget-file 任务。
- budget scaffold 完成后，`task-next --route longform-planning` 会进入 budget-agent-task。
- longform budget review 为 `pass_with_notes` 时，`task-complete` 阻塞。
- 即使 sidecar completion marker 存在，预算化大纲候选缺失时，`task-complete` 仍阻塞。
- 预算化大纲与分场景库存候选、completion marker、clean review 全部存在后，`task-next --route longform-planning` 返回 ready。
- `task-next --route source-ingest` 能对已有 import 发 extraction-agent-task。
- source-ingest extraction 缺候选输出时，`task-complete` 阻塞。
- source-ingest extraction review 为 `pass_with_notes` 时，`task-complete` 阻塞。
- source-ingest 候选输出、completion marker 和 clean review 全部存在后，`task-next --route source-ingest` 返回 ready。
- `task-next --route style-engineering` 能对项目内 style profile 发 style-prompt-task-file。
- style prompt 过短、缺结构块或缺 completion marker 时，`task-complete` 阻塞。
- style prompt 未产生 accepted style eval 时，`task-complete` 阻塞。
- style prompt、agent JSON、completion marker 和 accepted style eval 全部存在后，`task-next --route style-engineering` 返回 ready。
- `task-next --route character-and-world-assets` 能从空项目派发 asset-intake，并在创建 sidecar 后推进到 asset review。
- 未写资产 review、缺用户 approval 或缺 promotion manifest 时，`task-complete` 阻塞。
- 候选资产完成 creation、clean review、approval 和 promotion 后，`task-next --route character-and-world-assets` 返回 ready。
- `route-audit --route character-and-world-assets` 能阻塞未 review/未 approval/未 promotion 的候选，并放行完整晋升链路。
- `task-next --route review-and-audit` 能派发 canon-lint、canon review、longform audit、committee review，并在 clean approve 后返回 ready。
- `task-complete` 与 `route-audit` 能拒绝带 warnings/unresolved/action_items/disagreements 的 review/audit 链路。
- `task-next --route export-and-release` 能派发 chapter-workspace、export-package、release approval、publish-release，并在正式发布后返回 ready。
- `task-complete` 与 `route-audit` 能拒绝 `include_blocked` 导出、缺 approval 发布、latest 指针不一致和最终正文工程痕迹泄漏。
- `task-complete` 拒绝非 clean pass 的静态 review。
- `task-complete` 拒绝损坏的 state patch JSON。
- context 完成后 `task-next` 推进到 roleplay-simulation。
- CLI help 暴露新命令。

## 后续

Phase 85 应优先实现 Prompt Registry，让 `prompt_asset_id` 从占位标识升级为可验证、可预览、可版本化的提示词资产。
