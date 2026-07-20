# Phase 11：FastAPI / LangGraph / Dify 实接入

## 目标

把本地 `run-workflow` 接入两个真实外部面：

- FastAPI 后端：给 Dify、前端页面或其他 HTTP 客户端调用。
- LangGraph adapter：把工作流包装成真实 `StateGraph`。

## 安装

```powershell
python -m pip install -e '.[orchestration]'
```

## FastAPI 后端

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench serve-api --host 127.0.0.1 --port 8765 --allowed-root "C:\path\to\workspaces"
```

Endpoints：

- `GET /health`
- `POST /director/chat`
- `POST /workflow/run`
- `GET /workflow/runs/{run_id}?project_root=...`
- `GET /workflow/artifact?project_root=...&path=...`
- `POST /workflow/approve`

`/workflow/approve` 只记录审批，不直接写 canon。

## Dify Workflow 接法

1. Start / User Input：收集 `project_root`、`creative_direction`、`provider`、`auto_execute`，可选收集 `agent_tasks`。
2. HTTP Request：POST `/director/chat`，让创作总监自行路由到内部工作流。
3. If/Else：如果 `blocked=true` 或 `status` 不是 `completed`，进入 Human Input。
4. HTTP Request：GET `/workflow/artifact` 读取日志。
5. Human Input：收集 `approve / revise / reject` 和 notes。
6. HTTP Request：POST `/workflow/approve`。

专业/调试场景仍可直接 POST `/workflow/run`。该请求体支持 `agent_review=true` 和 `agent_tasks=true`；后者会让 scene-loop 产出 `.agent_tasks.md` 侧车任务文件。

`generate_candidate=true` 时，后端会在 scene-loop 的 `scene_composition` 后追加候选生成节点。使用 `provider=http-chat` 前，应在 `serve-api` 所在环境设置 `LEW_MODEL_API_BASE`、`LEW_MODEL_NAME` 和必要时的 `LEW_MODEL_API_KEY`。

`promote_candidate=true` 时，后端只会在候选稿已经通过 candidate-specific 平台 Agent 场景审查后把它转入草稿审查通道，再继续执行 `review_ci` 和 `state_evolution_patch`。未写入候选、缺审查、审查未引用 exact candidate 或存在未解决 notes 时，promotion 会延迟或阻塞。人物状态写回仍需人工 approve 后单独运行 `state-apply`。

Dify 不直接写 `canon/`，也不绕过 `review-scene`。

## LangGraph Adapter

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench run-langgraph work/demo-work --scene scenes/scene_0001.yaml --chapter-id chapter_0001
```

当前图：

```text
START -> scene_loop -> chapter_publish -> END
```

状态合并优先级：`failed > blocked > completed_with_skips > completed`。

## 下一步

- API token 或本地网关鉴权。
- LangGraph checkpointer / SQLite 持久化。
