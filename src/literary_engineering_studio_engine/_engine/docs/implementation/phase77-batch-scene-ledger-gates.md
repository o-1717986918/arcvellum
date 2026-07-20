# Phase 77：批量场景逐场景账本门禁

## 背景

实际使用中出现过这样的失败模式：Agent 对一个场景运行了 context / RP / branch / selection，却对后续大批场景直接写 prose，跳过 compose-scene、agent-review-scene、promote-candidate、state-evolve、longform-audit 和 route-audit。结果是字数目标失真、审查缺失、promotion 链路断裂，最终导出看似完整，工程账本却没有闭合。

这不是单个命令缺失，而是批量执行纪律缺失：一条 scene-development 链路只证明一个 scene 通过，不证明整章或整卷通过。

## 实现

- `route-audit --route scene-development` 对每个 `scenes/*.yaml` 独立检查：
  - context packet
  - roleplay simulation / reading receipt / AGENT_TASK resolved
  - branch manifest
  - formal `branch_selection.md`
  - ready composition
  - prose candidate
  - exact-candidate `scene_review.v1`
  - promotion manifest
  - promoted draft
  - `state-evolve` patch JSON/Markdown
- 对 100000+ 字或多卷项目，`scene-development` 与 `export-and-release` audit 增加 word-budget gate。
- 当 word budget status 为 `needs_expansion` 时，预算化大纲、场景库存扩展、budget review 和 scene inventory review 均为阻塞项。
- `export-and-release` audit 对未生成 `state-apply` 报告的 state patch 给出 warning，提醒最终发布前审批写回；正式 Skill 宿主不得用 internal-preview / unreview 指令跳过。

## 文档同步

- `SKILL.md` 新增 Batch Scene Loop Coverage Gate。
- `AGENTS.md` 新增逐场景 ledger 纪律。
- `references/agent-run-protocol.md` 与 `references/cli-run-protocol.md` 明确 scene loop 需要逐场景重复。
- `references/workflows.md` 与 `references/artifact-contracts.md` 将 `route-audit` 描述为正式路线账本。
- `protocol scene-development` 输出中加入 batch preflight、completion gates 和 forbidden shortcut。

## 验收

- `tests/test_agent_task_status.py` 增加缺候选、缺 AgentReview、缺 promotion、缺 state patch 和长篇缺 word-budget 的断言。
- 正式通过用例必须真实创建候选、写 exact-candidate review、执行 `promote_scene_candidate` 并生成 `state-evolve` patch。
