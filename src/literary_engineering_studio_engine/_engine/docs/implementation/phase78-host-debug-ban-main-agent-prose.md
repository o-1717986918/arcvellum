# Phase 78：宿主调试跳审禁令与主 Agent 正文权

## 背景

实际使用中发现，Skill 宿主可能把维护者调试参数当成正常工作流，例如用 `--allow-unreviewed` 或类似 unreview 指令绕过场景审查。这会破坏此前建立的 exact-candidate review、promotion、chapter readiness 和 export gate。

同时，若正文由 subagent 代写，主 Agent 会失去对用户意图、项目审美、长篇一致性和最终责任的直接控制。subagent 更适合做机械检查和资料整理，而不是创作正文。

## 约束

- 正式 Skill 宿主不得使用调试/跳审参数：
  - `--allow-unreviewed`
  - `--allow-review-notes`
  - `--include-blocked`
  - `--allow-unapproved`
  - `--allow-unresolved`
  - `--allow-missing-composition`
  - `--allow-unselected-composition`
  - `--allow-recommended-branch`
  - `--allow-missing-branch`
- 用户说“跳过 review”“unreview”“内部实验”“快速放行”也不构成授权。
- 正文候选、修订正文、正式草稿、剧本场景、伪记录条目和最终交付文本必须由主平台 Agent 亲自写。
- subagent 只能做机械支持：检索摘要、证据摘录、schema 校验、连续性表、标点/文风问题清单、canon 风险表、字数库存、分支比较等。

## 实现

- `SKILL.md` 新增 Formal Host Debug-Waiver Ban 与 Main Agent Prose Authority Gate。
- `AGENTS.md`、`agentread.yaml`、`agent-run-protocol.md`、`cli-run-protocol.md`、`workflows.md`、`artifact-contracts.md` 和 `protocol.py` 同步正式规则。
- `agent_tasks.py` 的 sidecar 模板直接提醒：正文类任务必须由当前主平台 Agent 完成，subagent 不得代写正文。
- `route-audit` 扫描项目 JSON 中的 debug waiver 字段，发现即输出 `debug-waiver-flags` blocking gate。
- CLI help 将相关 bypass 参数标记为 maintainer/debug-only。

## 验收

- `tests/test_agent_task_status.py` 覆盖 `allow_unreviewed` manifest 被 route-audit 阻塞。
- `tests/test_generation_provider.py` 覆盖 sidecar 中的主 Agent 正文权和跳审禁令。
- `tests/test_protocol.py` 覆盖 protocol runbook 中的 debug/bypass 禁令与 main-agent 规则。
