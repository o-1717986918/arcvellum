# CLI 中介 Agent 工作流

本模块是 Phase 84 的核心目标：让平台 Agent 保持自由创作能力，但让正式项目产物统一经过 CLI 持续状态机中介。

一句话原则：

> 用户自然对话不受限制；正式产物必须 CLI-mediated。

## 1. 为什么需要它

过去的正式场景链路依赖平台 Agent 自觉读取文档、运行命令、处理 sidecar、写 completion marker。实践中容易出现以下问题：

1. Agent 认为 CLI 是可选步骤，直接手写同名文件。
2. `.agent_tasks.md` 被当成“过程文件”跳过。
3. RP、branch、compose、review、promote、state-evolve 在批量场景中被省略。
4. `word_budget`、Style Lint、AgentReview notes 等约束生成了但没有进入下游链路。
5. review 或 export gate 阻塞时，Agent 倾向于用临时脚本或 debug flag 绕过。

CLI 中介工作流的目标不是让 CLI 写小说，而是让 CLI 负责发任务、管状态、收提交、做确定性校验和留下审计。

## 2. 职责边界

平台 Agent 负责：

1. 与用户自然沟通创作方向、审美判断和重大取舍。
2. 阅读 CLI 输出的任务包。
3. 写正文、修订、review、分支选择、状态判断和创意 JSON 草案。
4. 对创作判断负责。

CLI 负责：

1. 根据 `workflow-state` 派发下一项正式任务。
2. 输出给平台 Agent 的提示词包、必读文件、硬约束、预期产物和禁止捷径。
3. 接收平台 Agent 产物提交记录。
4. 检查 expected outputs、schema、provenance、Style Lint、word target、review gate 等确定性条件。
5. 写 completion marker、event log 和状态账本。

CLI 不负责：

1. 不替平台 Agent 写正文。
2. 不替平台 Agent 判断人物、剧情、文风和审稿结论。
3. 不把本地模型、dry-run 或 HTTP provider 输出作为正式创作权威。
4. 不允许手动推进状态绕过真实产物。

## 3. 最小命令闭环

当前支持 `scene-development`、`longform-planning`、`source-ingest`、`style-engineering`、`character-and-world-assets`、`review-and-audit` 与 `export-and-release` 七条正式路线。`scene-development` 是逐场景样板；`longform-planning` 用来确保长篇字数预算、预算化大纲和分场景库存不会被生成环节跳过；`source-ingest` 用来确保已有作品导入后的反推设定、候选资产和 review 不会被跳过；`style-engineering` 用来确保文风 profile 真正转化为可挂载、可评测的 LLM-facing prompt；`character-and-world-assets` 用来确保角色/世界/大纲等候选资产必须经过 sidecar、review、approval 和 promotion gate；`review-and-audit` 用来确保项目级审查不是旁路报告；`export-and-release` 用来确保最终交付不绕开 chapter/export/publish gate。

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench task-next <project> --route scene-development
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
# 平台 Agent 按 task 中的 Command / Hard Constraints 完成产物
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
python -m literary_engineering_workbench workflow-advance <project> --route scene-development
python -m literary_engineering_workbench workflow-events <project>
python -m literary_engineering_workbench workflow-dashboard <project>
```

长篇规划路线使用同一套控制面：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench task-next <project> --route longform-planning
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
# 平台 Agent 按 task 执行 word-budget、预算化大纲、预算 review、场景库存候选、库存 review、章节义务规划和章节义务 review
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
python -m literary_engineering_workbench workflow-advance <project> --route longform-planning
```

已有作品导入后的反推路线也使用同一套控制面：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench source-ingest <project> --source <source> --title <title> --work-id <work-id>
python -m literary_engineering_workbench task-next <project> --route source-ingest
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
# 平台 Agent 读取 source chunks 和 extract_project_files.agent_tasks.md，写候选项目文件与 review
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
```

项目内文风 profile 的正式 readiness 也使用同一套控制面：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench task-next <project> --route style-engineering
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
# 平台 Agent 写 style_prompt.md / style_prompt.agent.json，并完成 style eval
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
```

`task-next` 会写出：

1. `workflow/tasks/{task_id}.task.json`
2. `workflow/tasks/{task_id}.agent_tasks.md`
3. `workflow/events/task_events.jsonl`

`task-submit` 会写出：

1. `workflow/tasks/{task_id}.submission.json`
2. 对应 event log

`task-complete` 会先按 `current_state` 运行真实门禁，再写出：

1. `workflow/tasks/{task_id}.agent_completion.json`
2. 更新后的 `{task_id}.task.json`
3. 刷新的 `workflow/route_state.md` 和 `workflow/route_state.json`
4. 对应 event log

从 `v0.84.1` 起，`task-complete` 不只检查文件是否存在。它会按当前状态验证 CLI provenance、sidecar completion、branch selection、composition readiness、word-budget sidecar/review、candidate generation manifest、Style Lint、exact-candidate AgentReview、promotion waiver、static review 和 state patch JSON。失败时任务会进入 `blocked`，失败信息就是下一步修复任务。

从 `v0.84.2` 起，`task_registry.py` 使用 route registry 分发表、选择器、任务构建器和门禁函数。`longform-planning` 已接入同一生命周期：`word-budget-file`、`budget-agent-task`、`budget-review`、`scene-inventory-agent-task`、`scene-inventory-review`。预算 sidecar 的 completion marker 不能单独放行；预算化大纲候选、分场景库存候选和对应 clean `pass` review 也必须存在。

从 `v0.88.0` 起，`longform-planning` 在 scene inventory 后新增 `chapter-obligation-agent-task` 和 `chapter-obligation-review`。`word-budget` 会生成 `plot/chapter_obligations/chapter_obligations.agent_tasks.md`，平台 Agent 必须完成章节义务规划、写 clean review 和 completion marker。单章正式生成前还要通过 `chapter-obligation --chapter-id <chapter_id>` 建立 per-chapter reader contract；缺失时 scene-development 会停在 `reader-experience-contract`，不会进入正文候选生成。

从 `v0.89.0` 起，`workflow-dashboard` 提供跨路线只读 cockpit。它会把 `workflow-state --route overall`、`agent-task-status`、七条正式 route audit 和最近 event log 汇总到 `workflow/dashboard/workflow_dashboard.json`、`.md`、`.html`。这个 dashboard 只展示状态，不完成任务、不创建创作产物、不允许跳过 `task-next/task-open/task-submit/task-complete`。

从 `v0.84.3` 起，`source-ingest` 已接入同一生命周期：`source-manifest`、`extraction-agent-task`、`extraction-review`。已有作品导入只负责源文本、chunk 和 extraction sidecar；反推出的项目简报、人物/背景、世界观、大纲、时间线、伏笔、文风 notes 和 extraction review 必须由平台 Agent 写入候选区。completion marker、候选文件和 clean `pass` review 缺一项都不能 ready。

从 `v0.84.4` 起，`style-engineering` 已接入同一生命周期：`style-profile`、`style-prompt-task-file`、`style-prompt-agent-task`、`style-prompt-quality`、`style-eval-readiness`。项目根 `style/style-profile.md` 占位文件不会被误当成 profile；真正的 profile 目录必须完成 sidecar、prompt、agent JSON、质量检查和 accepted style eval 后才 ready。

从 `v0.84.5` 起，`character-and-world-assets` 已接入同一生命周期：`asset-intake`、`asset-creation-agent-task`、`asset-review-task-file`、`asset-review-agent-task`、`asset-review-pass`、`asset-approval`、`asset-promotion`。`asset-create` / `agent-create-*` 只准备平台 Agent 创建任务；review 只证明候选可请求审批，不等于用户 approval；`promote-candidate-asset` 必须使用 approve record，不能用 `--allow-unapproved`。

从 `v0.84.6` 起，`review-and-audit` 已接入同一生命周期：`canon-lint-file`、`canon-review-task-file`、`canon-review-agent-task`、`canon-review-pass`、`longform-audit-file`、`committee-task-file`、`committee-agent-task`、`committee-pass`。确定性 canon lint 和 longform audit 只是证据；平台 Agent 必须写 canon review 与 committee review。带 warnings、unresolved facts、timeline risks、committee action items 或 disagreements 的项目不能 ready。

从 `v0.84.6` 起，`export-and-release` 已接入同一生命周期：`chapter-workspace`、`export-package`、`release-approval`、`publish-release`。正式交付必须先得到 ready chapter workspace 和 clean export manifest，再取得人类 approve 记录，最后由 `publish-chapter` 写 release manifest、notes、rollback 和 latest 指针。`--include-blocked`、`--allow-unapproved`、自写导出脚本和读者正文泄漏工程痕迹都会阻塞路线。

从 `v0.85.0` 起，`task-open` 会解析 `prompt_asset_id` 并把 Prompt Registry 中的资产正文写进任务包。`templates/prompt_assets/*.md` 现在覆盖七条正式路线，`prompt-registry-validate` 会检查所有 task registry prompt id 是否有 exact 或 wildcard asset 可用。这样 prompt id 不再只是占位符，而是 CLI 输出给平台 Agent 的实际提示词资产。

从 `v0.86.0` 起，`context` 会同时写出 Markdown context packet 和相邻的 `*.trace.json`。`task-next`、`workflow-state`、`route-audit`、`compose-scene`、`generate-scene`、`agent-review-scene`、`revise-scene`、chapter readiness 和 export readiness 都把缺失或无效 context trace 视为 blocking。平台 Agent 不能只凭一份看似完整的 context packet 继续写作；必须先确认 trace 证明本场景实际加载了 scene、canon、character、style、word-budget 和检索来源。

从 `v0.86.1` 起，场景生成和审查任务会携带 New Character Register。平台 Agent 写候选正文或修订候选时，必须在 candidate manifest 中声明是否引入新角色；AgentReview 必须审查该 register。一次性路人可通过 waiver 保持本场景局部存在；持久新角色必须走 `characters/candidates/`、asset review、用户 approval 或 promotion。`route-audit` 会输出单独的新角色登记 gate。

## 4. Scene-development 样板状态

第一版按 `workflow_state.py` 已有推导状态发任务。典型顺序：

1. `context-packet`
2. `context-trace`
3. `roleplay-simulation`
4. `roleplay-agent-task`
5. `branch-manifest`
6. `branch-agent-task`
7. `branch-selection`
8. `composition-json`
9. `composition-agent-task`
10. `scene-word-budget-contract`
11. `reader-experience-contract`
12. `candidate-generation-provenance`
13. `generation-agent-task`
14. `candidate-review`
15. `agent-review-task`
16. `promotion-manifest`
17. `promoted-draft`
18. `static-review`
19. `state-patch-json`
20. `state-agent-task`

状态不是靠 CLI 手写推进，而是由真实项目文件、sidecar completion marker 和现有 gate 推导。`workflow-advance` 只是刷新账本，不允许把未完成状态强行改成完成。

## 4.1 Longform-planning 状态

长篇规划路线顺序：

1. `word-budget-file`
2. `budget-agent-task`
3. `budget-review`
4. `scene-inventory-agent-task`
5. `scene-inventory-review`
6. `chapter-obligation-agent-task`
7. `chapter-obligation-review`

对应硬产物：

1. `plot/word_budget/word_budget.md`
2. `plot/word_budget/word_budget.json`
3. `plot/word_budget/word_budget.agent_tasks.md`
4. `plot/word_budget/word_budget.agent_completion.json`
5. `plot/candidates/outlines/word_budget_expansion.md`
6. `reviews/word_budget/word_budget_review.md`，结论必须为 `pass`
7. `plot/word_budget/scene_inventory_expansion.agent_tasks.md`
8. `plot/word_budget/scene_inventory_expansion.agent_completion.json`
9. `plot/candidates/scenes/word_budget_scene_inventory.md`
10. `reviews/word_budget/scene_inventory_review.md`，结论必须为 `pass`
11. `plot/chapter_obligations/chapter_obligations.agent_tasks.md`
12. `plot/chapter_obligations/chapter_obligations.agent_completion.json`
13. `reviews/word_budget/chapter_obligation_review.md`，结论必须为 `pass`

这条路线专门堵住“预算文件生成了但没人读”的漏洞。正式批量场景生成前，平台 Agent 必须完成预算化大纲、场景库存和章节义务三类判断，不能只靠拉长每个场景满足目标字数，也不能把章节写成缺乏读者承诺的事件摘要。

## 4.2 Source-ingest 状态

已有作品导入路线顺序：

1. `source-manifest`
2. `extraction-agent-task`
3. `extraction-review`

对应硬产物：

1. `sources/imports/{work_id}/source_manifest.json`
2. `sources/imports/{work_id}/source_ingest.md`
3. `sources/imports/{work_id}/extract_project_files.agent_tasks.md`
4. `sources/imports/{work_id}/extract_project_files.agent_completion.json`
5. `sources/imports/{work_id}/extracted/project_brief.md`
6. `characters/candidates/extracted/{work_id}_characters.md`
7. `canon/candidates/extracted/{work_id}_world.md`
8. `plot/candidates/extracted/{work_id}_outline.md`
9. `plot/candidates/extracted/{work_id}_timeline.md`
10. `plot/candidates/extracted/{work_id}_foreshadowing.md`
11. `style/candidates/{work_id}_style_generation_notes.md`
12. `reviews/source_ingest/{work_id}_extraction_review.md`，结论必须为 `pass`

这条路线专门堵住“导入了已有文本但没有真正反推项目文件”的漏洞。所有 source-derived 内容仍是 candidate，必须带 evidence_refs、confidence、unknowns 和 contradiction notes，不得直接覆盖正式 canon / characters / plot / drafts。

## 4.3 Style-engineering 状态

项目内文风路线顺序：

1. `style-profile`
2. `style-prompt-task-file`
3. `style-prompt-agent-task`
4. `style-prompt-quality`
5. `style-eval-readiness`

对应硬产物：

1. `style/{profile}/style-profile.md`
2. `style/{profile}/style_metrics.json`
3. `style/{profile}/style_prompt.agent_tasks.md`
4. `style/{profile}/style_prompt.agent_completion.json`
5. `style/{profile}/style_prompt.md`
6. `style/{profile}/style_prompt.agent.json`
7. `style/{profile}/evaluation_results/*/style_eval_*.json` 至少一个 accepted

质量门禁：

1. `style_prompt.md` 必须是供 LLM 写作时直接使用的文风约束提示词，不是风格评论。
2. 正文中文内容 detail chars 必须在 500-2500 之间，计入汉字和中文标点，不计入 Markdown 标记、英文路径、代码围栏或空白。
3. 必须包含身份/边界、核心机制、叙述距离、句法节奏、标点、意象感官、心理/行为、对白、AI 腔控制、禁止倾向和输出自检。
4. accepted eval 要求 `overall_score >= 45`，且 `risk_level` 不能是 `high_copy_risk` 或 `low_similarity`。

## 4.4 Character-and-world-assets 状态

角色/世界资产路线顺序：

1. `asset-intake`
2. `asset-creation-agent-task`
3. `asset-review-task-file`
4. `asset-review-agent-task`
5. `asset-review-pass`
6. `asset-approval`
7. `asset-promotion`

对应硬产物：

1. `characters/candidates/*.agent_tasks.md`、`canon/candidates/**/*.agent_tasks.md` 或 `plot/candidates/**/*.agent_tasks.md`
2. 对应候选 JSON 与候选 Markdown 报告
3. 创建 sidecar 的 `.agent_completion.json`
4. `reviews/assets/{candidate_id}_review.agent_tasks.md`
5. `reviews/assets/{candidate_id}_review.json`
6. `reviews/assets/{candidate_id}_review.md`
7. 审查 sidecar 的 `.agent_completion.json`
8. `workflow/approvals/index.jsonl` 中匹配 candidate_id 的 approve 记录
9. `workflow/asset_promotions/{candidate_id}_promotion.json`
10. promotion manifest 列出的正式输出文件

质量门禁：

1. 候选 JSON 必须通过资产类型对应 schema，并保留 `candidate_id`、`risks`、`source_paths`、`promotion_notes`。
2. 角色与背景故事候选必须把 `background_story` 作为隐性行为因果，不得默认写成正文 exposition。
3. 平台 Agent 资产审查必须 `status=pass`，且没有 blocking issues 或 unresolved revision actions。
4. Review 不是 approval。用户 approve 记录缺失时不能晋升。
5. `allow_unapproved=true` 的 promotion manifest 在正式路线中 blocking。

## 4.5 Review-and-audit 状态

项目级审查路线顺序：

1. `canon-lint-file`
2. `canon-review-task-file`
3. `canon-review-agent-task`
4. `canon-review-pass`
5. `longform-audit-file`
6. `committee-task-file`
7. `committee-agent-task`
8. `committee-pass`

对应硬产物：

1. `reviews/canon_lint.md`
2. `reviews/canon_lint.json`
3. `reviews/agent/canon_review.agent_tasks.md`
4. `reviews/agent/canon_review.agent_completion.json`
5. `reviews/agent/canon_review.json`
6. `reviews/agent/canon_review.md`
7. `reviews/longform/longform_audit.md`
8. `reviews/longform/longform_audit.json`
9. `plot/longform_graph.json`
10. `reviews/agent/committee_project-final-audit.agent_tasks.md`
11. `reviews/agent/committee_project-final-audit.agent_completion.json`
12. `reviews/agent/committee_project-final-audit.json`
13. `reviews/agent/committee_project-final-audit.md`

质量门禁：

1. `canon_lint.json` 可以有 warning，但 blocking_count 必须为 0。
2. 平台 Agent canon review 必须是 clean `conclusion=pass`，不能带 blocking issues、warnings、unresolved facts 或 timeline risks。
3. `longform-audit` 必须存在并通过 schema。
4. committee review 必须 `final_recommendation=approve`，且没有 action_items 或 disagreements。
5. Review route 不能直接写 canon/character/plot/draft/export；只能输出修复任务、候选修改和审批边界。

## 4.6 Export-and-release 状态

章节导出路线顺序：

1. `chapter-workspace`
2. `export-package`
3. `release-approval`
4. `publish-release`

对应硬产物：

1. `drafts/chapters/{chapter_id}.md`
2. `plot/chapters/{chapter_id}.json`
3. `exports/{chapter_id}/export_manifest.json`
4. `exports/{chapter_id}/{chapter_id}_novel.md`
5. `exports/{chapter_id}/{chapter_id}_screenplay.md`
6. `exports/{chapter_id}/{chapter_id}_video_prompt_pack.md`
7. `workflow/approvals/index.jsonl` 中 `release-{chapter_id}` 的 approve 记录
8. `releases/{chapter_id}/formal-release/publish_manifest.json`
9. `releases/{chapter_id}/formal-release/release_notes.md`
10. `releases/{chapter_id}/formal-release/rollback.md`
11. `releases/{chapter_id}/latest.json`

质量门禁：

1. Chapter workspace 必须 ready_count > 0 且 blocked_count = 0。
2. Export manifest 必须 schema-valid，`include_blocked=false`，`skipped_scenes=[]`，所有请求输出真实存在。
3. 读者正文必须清除 `scene_0001`、`chapter_0001`、内部路径、canon/review/workflow/state/writeback 标记和 `[AGENT_TASK: ...]`。
4. publish manifest 必须 `status=published`，approval decision 必须是 `approve`。
5. `latest.json` 必须指向 formal-release 的 publish manifest。

## 5. Task 包必须包含什么

每个 `agent-task.v1` 至少包含：

1. `task_id`
2. `route`
3. `scene_id`
4. `current_state`
5. `task_type`
6. `prompt_asset_id`
7. `command`
8. `required_reading`
9. `source_paths`
10. `hard_constraints`
11. `style_constraints`
12. `expected_outputs`
13. `submission_command`
14. `completion_command`
15. `validation_gates`
16. `forbidden_shortcuts`
17. `next_allowed_states`

这些字段是给平台 Agent 的执行边界，不是外部 LLM prompt，也不是 canon。

## 6. 使用纪律

1. 看到 `task-next` 输出后，先 `task-open`。
2. 读取 `workflow/tasks/{task_id}.agent_tasks.md`，不要只看终端摘要。
3. 如果任务要求运行原有命令，例如 `context`、`simulate-scene`、`generate-scene`，先运行该命令并检查输出路径。
4. 如果原有命令又生成 sidecar，先处理原 sidecar，再提交当前 task。
5. 产物写完后必须 `task-submit`。
6. `task-complete` 失败时，失败原因就是下一步工作，不得用 debug flag 绕过。
7. `route-audit` 和 `agent-task-status` 仍然是正式审计工具。

## 7. 与旧 sidecar 的关系

新 task registry 不删除旧 `.agent_tasks.md`。第一版做法是：

1. `workflow/tasks/*.agent_tasks.md` 是上层“统一任务包”。
2. 原命令生成的 sidecar 仍在原位置，例如 `branches/{scene_id}/roleplay_simulation.agent_tasks.md`。
3. 上层 task 会要求平台 Agent 处理原 sidecar，并把原 sidecar 的 `.agent_completion.json` 作为 expected output。
4. 后续阶段可以逐步把旧 sidecar 注册进 task registry，减少双层任务感。

## 8. 验收口径

第一版完成后，至少应满足：

1. `task-next` 能对 demo scene 发出下一项 formal task。
2. `task-open` 能输出完整 Agent 可执行任务包。
3. `task-submit` 拒绝不存在的提交产物。
4. `task-complete` 拒绝 expected outputs 缺失的任务。
5. `task-complete` 拒绝 current_state 对应真实 gate 未通过的任务，例如手写 composition、未完成 word-budget sidecar、Style Lint blocking、`pass_with_notes` review、debug-waiver promotion、非 clean pass static review。
6. `workflow-advance` 只能刷新 artifact-derived 状态，不能手动跳状态。
7. `workflow-events` 能回放 task issued / opened / submitted / completed / blocked。

## 9. 后续扩展

下一阶段应将本模块继续接入：

1. Prompt Registry：让 `prompt_asset_id` 不再只是标识，而是真正可验证的提示词资产。
   - `v0.85.0` 已完成文件型 registry、CLI list/validate/preview、task-open 注入；后续可以为高风险任务补 exact prompt asset。
2. Context Broker：让 `task-open` 输出稳定的 context trace。
   - `v0.86.0` 已完成 context packet / context trace 双产物、下游读取、route gate、workflow state 和生成/审查/revision 链路接入。
3. New Character Register：阻止持久新角色从正文旁路进入角色库。
   - `v0.86.1` 已完成生成 manifest、AgentReview、promotion、readiness、route-audit 和 state-evolve 接入。
4. Reader Experience Contract：让字数和章节义务进入 `task-open` 与 `task-complete`。
   - `v0.88.0` 已完成 chapter-obligation sidecar、reader-experience scene gate、prompt/generation/review/promotion/readiness 接入。
5. route-audit：逐步从“文件存在检查”升级为“task registry provenance 检查”。
6. 扩展跨路线 dashboard：把七条正式路线的缺口压缩成用户可读的下一步队列。
   - `v0.89.0` 已完成 `workflow-dashboard` JSON/Markdown/HTML 只读 cockpit；后续可以让本地前端通过 HTTP 轮询该 JSON。
