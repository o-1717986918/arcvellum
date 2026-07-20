# Phase 46：顶层创作总监 Agent

本阶段把用户对话入口收束到一个顶层 `Creative Director Agent`。

目标是让用户只给出创作大方向；角色、世界观、大纲、场景审查、候选资产生成、二级路由和风险提示由总监 Agent 统一管理，并写入可审计记录。

## 新增模块

- `src/literary_engineering_workbench/director_agent.py`
  - `run_director_turn()`：接收用户大方向，调用顶层 Agent 生成 `director_decision.v1` 决策，再按需要执行内部工作流。
  - `build_director_status()`：汇总项目状态、候选资产、最近工作流和最近总监运行。
- `schemas/agent_outputs/director_decision.v1.schema.json`
  - 约束总监输出的意图、工作流选择、二级决策、委派对象、风险和用户可见决策。
- `templates/prompts/director_system.md`
- `templates/prompts/director_user.md`

## 用户入口

CLI：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench director-chat "<work-dir>" --message "把项目推进成双主角悬疑长篇，先补足角色压力"
python -m literary_engineering_workbench director-status "<work-dir>"
```

FastAPI：

- `POST /director/chat`
- `GET /director/status`

Dify：

- `dify-dsl` 生成的 starter 已改为调用 `POST /director/chat`。
- Dify Start 节点只收 `project_root`、`creative_direction`、`provider` 和 `auto_execute`，不再要求用户选择底层 workflow mode。`provider` 默认 `auto`，由本地全局配置解析到真实模型。
- 第二个 HTTP 节点读取 `director_report.md`，作为后续 Human Input / 审批节点的阅读对象。

前端：

- 原“对话控制”页改为“创作总监”页。
- 默认调用 `/director/chat`。
- 用户只输入项目路径和创作大方向；`provider` 默认 `auto` 连接真实 LLM，`dry-run` 仅保留为显式离线调试参数。

## 内部路由

总监 Agent 会把方向路由到以下最小可执行工作流：

- `project-seeding`：世界观、角色、大纲候选及审查。
- `character-lab`：角色档案、隐藏背景故事、关系网候选及审查。
- `worldbuilding-lab`：世界规则、地点、组织候选及审查。
- `outline-lab`：主线大纲、章节计划、场景列表候选及审查。
- `scene-loop`：上下文、角色推演、分支推演、场景编排、候选生成和 Agent 审查。
- `none`：仅读取状态，不触发创作写入。

## 审计产物

每轮总监对话会写入：

- `director/runs/{run_id}/agent_decision/input.prompt.json`
- `director/runs/{run_id}/agent_decision/parsed_output.json`
- `director/runs/{run_id}/agent_decision/schema_validation.json`
- `director/runs/{run_id}/director_decision.json`
- `director/runs/{run_id}/director_report.md`
- `director/runs/index.jsonl`

若自动执行内部工作流，还会关联：

- `workflow/runs/{run_id}-wf/workflow_state.json`
- `workflow/runs/{run_id}-wf/workflow_log.md`

## 安全边界

- 总监只负责二级决策和委派，不直接覆盖正式 canon。
- 新角色、背景故事、世界观和大纲仍先进入候选资产目录。
- 角色背景故事仍按隐性行为因果处理，不默认显式写入正文。
- 默认 `auto` 需要全局模型配置具备 API Base、Model 和 API Key。
- 如果真实模型输出没有通过 `director_decision.v1`，系统会回退到确定性安全路由，并在总监报告中记录。

## 测试

新增 `tests/test_director_agent.py`，覆盖：

- 大方向自动路由到 `project-seeding`。
- `--no-execute` 只规划不运行。
- 总监状态视图。
- CLI `director-chat`。
- `scene-loop` 委派链路。

`tests/test_api_server.py` 覆盖 `/director/chat`、`/director/status` 和前端 `/director/chat` 调用。
