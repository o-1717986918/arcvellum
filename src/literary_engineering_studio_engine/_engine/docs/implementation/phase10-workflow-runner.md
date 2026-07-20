# Phase 10：Agent 工作流编排 Runner

命令：`run-workflow`

> Current project-type skill override: formal workflow generation/review/asset nodes write platform-agent task sidecars and expected output paths. They do not invoke local `dry-run`, `http-chat`, or external agent services. Provider flags are compatibility fields for legacy/debug paths.

模式：

- `scene-loop`
- `chapter-publish`
- `full-cycle`

输出：

- `workflow/runs/{run_id}/workflow_state.json`
- `workflow/runs/{run_id}/workflow_log.md`

Runner 保留已有草稿，默认不覆盖人工写作成果。

`scene-loop` 当前节点顺序：

1. `retrieve_memory`
2. `build_context_packet`
3. `character_simulation`
4. `branch_simulation`
5. `scene_composition`
6. `generate_candidate`（可选）
7. `promote_candidate`（可选）
8. `draft_workspace`
9. `review_ci`
10. `state_evolution_patch`

其中 `branch_simulation` 产出 `branch_manifest.json` / `branch_selection.md`，`scene_composition` 产出 `drafts/compositions/{scene_id}_composition.md` / `.json`，用于把剧情分支和人物隐性动因整理为正文生成前的创作编排包。

当前版本通过 `--generate-candidate` 在 `scene_composition` 后追加平台 Agent 正文生成任务，记录 `candidate_task`、`expected_candidate`、`expected_candidate_manifest` 和 `prompt_manifest`。候选正文必须由平台 Agent 回填，不能由 workflow 本地调用 provider。

`v0.24.0` 起，若草稿存在，`review_ci` 后会追加 `state_evolution_patch` 节点，输出 `characters/state_patches/{scene_id}_state_patch.md` / `.json`。该节点只生成候选 patch，不写回人物档案。

`v0.25.0` 起，可通过 `--promote-candidate` 在生成候选后追加 `promote_candidate` 节点，把最新或刚生成的候选稿转成 `drafts/scenes/{scene_id}.md`，然后继续进入审查和人物状态 patch。`v0.72.0` 起，该节点默认要求候选稿已经通过 candidate-specific 平台 Agent 场景审查；未写入候选、缺审查或审查未引用 exact candidate 时会延迟或阻塞。人物状态写回仍由 `state-apply` 在审批后单独执行。

`--agent-tasks` 会在 scene-loop 中生成平台 agent 任务说明，并把路径登记进 workflow state：

- `simulation_agent_tasks`
- `branch_agent_tasks`
- `scene_composition_agent_tasks`
- `candidate_task`（存在候选生成时）
- `state_patch_agent_tasks`

这些任务说明可包含 `[AGENT_TASK: ...]`，但 JSON、prompt manifest、正稿和发布产物不得包含该标记。
