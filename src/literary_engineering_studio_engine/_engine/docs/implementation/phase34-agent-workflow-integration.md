# Phase 34：Agent Workflow / LangGraph / Dify / API 联动

## 目标

把 Agent 审查能力接入现有 workflow、LangGraph、Dify 和 API 链路，保持 CLI、本地状态机、外部编排工具共用同一底层能力。

## 新增能力

> Current project-type skill override: formal creative/review workflow nodes now write platform-agent task sidecars and expected artifacts. They do not invoke local dry-run, `http-chat`, or external agent services. Legacy local provider paths remain only for explicit regression/debug use.

- `run-workflow --agent-review`
- `run-langgraph --agent-review`
- FastAPI `RunWorkflowRequest.agent_review`
- FastAPI `RunWorkflowRequest.agent_tasks`
- FastAPI `/agent/run`
- FastAPI `/agent/runs/{run_id}`
- Dify DSL 增加 `agent_tasks` 输入，并通过 `/director/chat` 交给创作总监透传到内部 workflow。

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench run-workflow work/demo --mode scene-loop --agent-review
python -m literary_engineering_workbench run-workflow work/demo --mode scene-loop --agent-tasks --generate-candidate
```

## 工作流节点

Scene loop 在规则审查后追加：

- `agent_scene_review`
- `agent_committee`

Chapter publish 在 longform audit 后可追加：

- `agent_canon_review`

## 边界

Dify 仍是审稿台和人工审批界面，不是 canon 源。真实模型 key 继续留在本地后端环境变量中。`agent_tasks` 只写 `.agent_tasks.md` sidecar，不写入 prompt manifest、canon、角色文件、正文草稿或发布包。
