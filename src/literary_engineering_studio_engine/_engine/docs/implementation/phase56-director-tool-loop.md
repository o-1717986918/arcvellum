# Phase 56: Creative Director Tool Loop

本阶段把 `director_tools` 从静态隐藏计划升级为创作总监的有限工具调用循环。

创作总监现在不是只做一次路由，然后直接运行一个固定 workflow；它会按 `observe -> decide -> act -> observe` 的方式推进一轮任务：

1. 读取项目状态和最近对话。
2. 生成初始 `director_decision.v1`。
3. 从 `director_tools` 取出下一项安全工具调用。
4. 执行工具并记录观察结果。
5. 再调用创作总监 Agent，根据观察结果决定下一项工具或停止。
6. 写入最终总监决策、报告和对话记忆。

## 工具白名单

当前循环只允许以下工具：

- `init_project`
- `run_workflow`
- `create_asset_candidate`
- `review_candidates`
- `summarize_project_status`
- `ask_user`
- `write_director_report`

循环默认最多执行 4 步，避免一次请求中无限扩张。`auto_execute=false` 时，工具调用只记录为 `planned`，不会产生创作写入。

`run_director_turn(..., agent_tasks=True)`、API `/director/chat` 的 `agent_tasks=true`、以及 CLI `director-chat --agent-tasks` 会把同名开关传给内部 `run_workflow`。这会生成 `.agent_tasks.md` 侧车任务文件，供 Codex/Claude 等平台 Agent 继续执行“判断、填充、审查、是否写回”的非确定性环节；不会把 `[AGENT_TASK: ...]` 写入 JSON、prompt manifest、canon、角色文件、正文草稿或发布包。

## 审计产物

每轮总监对话新增：

- `director/runs/{run_id}/tool_loop.json`
- `director/runs/{run_id}/agent_observe_01/`
- 后续观察决策目录：`agent_observe_02/`、`agent_observe_03/` 等

`tool_loop.json` 会记录：

- 初始决策摘要
- 每步工具调用
- 工具执行前观察
- 工具执行后观察
- 工具状态、产物、错误
- 再决策 Agent 的运行目录与校验结果

## 设计边界

- 工具循环不是无限自治；它是单轮请求内的有限 agent loop。
- 正式 canon、人物文件、剧情源文件仍不被直接覆盖。
- 新设定、人物、世界观和大纲仍先作为候选资产，再审查和晋升。
- 用户可见对话继续保持“创作总监式”表达，不暴露 schema、路径、workflow ID 或 agent 细节。

## 测试

新增回归覆盖：

- `dry-run` 下会执行 `run_workflow -> observe -> write_director_report`。
- `tool_loop.json` 记录每步工具调用、观察和再决策。
- `auto_execute=false` 时只记录 planned 工具，不执行写入。
- `/director/chat` 响应和对话 audit 中包含 `tool_loop` 路径。
