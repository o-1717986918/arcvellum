# Phase 76：Supervisor Agent 执行纪律与 sidecar 闭环

本阶段修正实际使用中暴露出的 supervisor agent 执行问题：Agent 看到 skill 文档中的 `agent-review-scene`、`promote-candidate`、`export-package` 等步骤时，可能没有先试命令，就主观判断“需要模型环境”“我做不了”，随后跳过正式 review/promotion gate，甚至用自写脚本绕过官方导出门禁。

## 根因

- 文档已经说明 sidecar 需要平台 Agent 处理，但没有把“命令写出 sidecar 不等于完成任务”写成足够醒目的执行纪律。
- `agent-review-scene` 这类命令名容易被误解为外部 agent/model 调用，实际它主要生成任务说明和 expected output paths，审查本身由当前平台 Agent 完成。
- 缺少“先试再判断”的硬规则。Agent 有 shell/文件工具，却可能在没运行 `--help` 或最小命令前先声明不可用。
- 导出 gate 失败时，Agent 可能把“官方 gate 阻塞”误解成“工具不好用”，转而自写脚本输出，导致正式交付绕过 review/readiness。

## 已实现

- `SKILL.md` 新增 Execution Discipline Gate：文档命令先试再判断，sidecar 是当前平台 Agent 的待执行任务，`agent-review-scene` 不是外部模型依赖，官方 gate 失败不能用自写脚本冒充最终交付。
- `AGENTS.md`、`references/agent-run-protocol.md`、`references/cli-run-protocol.md` 增加 Command Attempt Rule：运行 `--help`、`protocol <route>` 或最小安全命令；失败后记录真实命令和错误。
- `src/literary_engineering_workbench/protocol.py` 的 route runbook 输出加入能力探测、sidecar 执行、`agent-review-scene` review JSON/Markdown 填写和导出 gate 不绕过要求。
- `src/literary_engineering_workbench/agent_tasks.py` 统一 sidecar 头部：命令写出任务文件只表示任务准备好，不表示任务完成；当前平台 Agent 必须读取、执行、写入目标产物。
- `references/workflows.md`、`references/artifact-contracts.md` 明确 `agent-review-scene --draft <candidate>` 后要读取 `reviews/agent/{scene_id}_scene_review.agent_tasks.md`，再写入引用 exact candidate 的 `scene_review.v1` JSON/Markdown。
- README 和 roadmap 更新到 `v0.76.0`。

## 后续原则

当用户说“按标准流程走”时，supervisor agent 的默认动作应是尝试文档中的命令并处理 sidecar，而不是解释为什么可能做不了。只有真实命令失败、路径缺失或项目状态阻塞时，才进入替代方案；替代方案必须标明是内部预览、临时补救或待正式 gate 修复。
