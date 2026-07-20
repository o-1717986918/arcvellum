# Phase 82 - Formal CLI Provenance Gate

## 问题

宿主 Agent 容易把“CLI 可选”误读为“正式路线可以手写同名文件”。这会导致正文生成绕过 context、RP、branch、composition、prompt manifest、agent task 和 review provenance，最终约束强度明显下降。

## 决策

- 探索性讨论、临时片段和分析 notes 可以不走 CLI。
- 可能被 promote、计入字数、导出、发布或写回的正式产物必须保留 CLI sidecar / manifest provenance。
- 手写同名文件默认是 exploratory/debug-only，不能满足正式 route gate。
- 只有在先尝试 CLI 并记录失败后，平台 Agent 才能创建 CLI-equivalent workaround，并且仍需进入 route-audit 和人工审查。

## 实现

- `SKILL.md`、`AGENTS.md`、`agentread.yaml`、`references/agent-run-protocol.md` 和 `references/cli-run-protocol.md` 明确区分 exploratory 与 formal。
- `scene_composer.py` 在 composition JSON 写入 `formal_cli_provenance.created_by=compose-scene`。
- `flow_gates.py` 阻塞缺少 `compose-scene` provenance 的正式 generation。
- `roleplay_lab.py` 和 `branch_lab.py` 写入 `simulate-scene` / `branch-simulate` 来源标记。
- `candidate_promotion.py` 新增 candidate generation provenance gate。
- `route-audit` 新增 RP、branch、composition、candidate generation provenance gate。

## 效果

正式正文候选不再只靠文件名进入链路。缺少 prompt manifest、`.agent_tasks.md`、平台 Agent manifest 或约束执行字段时，候选会被降级为 informal/debug material，不能默认晋升或导出。
