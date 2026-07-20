# Dify Workflow 接入

本目录保存 Literary Engineering Workbench 的 Dify Workflow 导入示例。

> Project-type Skill note: 当前主路线不是把 Dify 作为项目总监，而是让 Codex、Claude 等工具层 agent 直接担任项目总监、创作总监、模型 provider 和子 agent 编排层。Dify DSL 仅保留为可选本地集成、审批界面或回归示例；如果它与根目录 `SKILL.md`、`AGENTS.md`、`CLAUDE.md`、`agentread.yaml` 或 `references/project-director-playbook.md` 冲突，以项目型 Skill 入口为准。

## 文件

- `literary-workbench-reviewer.workflow.yml`：Dify Workflow DSL import-safe starter。

## 生成命令

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench dify-dsl
```

自定义 API 地址：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench dify-dsl `
  --api-base "http://127.0.0.1:8765" `
  --out docs/integrations/dify/literary-workbench-reviewer.workflow.yml
```

默认声明 Dify DSL `0.6.0`，以兼容 Dify 0.6+ 的导入链路。如你的 Dify 明确要求更高版本，可加：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench dify-dsl --dsl-version "0.7.0"
```

## 后端启动

先启动 workbench API：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench serve-api `
  --host 127.0.0.1 `
  --port 8765 `
  --allowed-root "C:\path\to\workspaces" `
  --api-token "your-token"
```

如果 Dify 运行在 Docker 中，`127.0.0.1` 可能指向容器自身。此时通常需要把 `WORKBENCH_API_BASE` 改成宿主机可访问地址，例如：

- `http://host.docker.internal:8765`
- 局域网 IP，例如 `http://192.168.x.x:8765`

## 导入后检查

导入 Dify 后检查：

1. Environment variable `WORKBENCH_API_BASE` 指向可访问的 `serve-api`。
2. Start 节点包含 `project_root`、`creative_direction`、`provider`、`auto_execute`、`agent_tasks`。
3. `Run creative director` 节点调用 `POST /director/chat`，仅表示启用本地 workbench director 桥接。
4. `Read director report` 节点调用 `GET /workflow/artifact` 读取总监报告。

Start 节点的 `provider` 默认 `auto`，会由本地 workbench 全局配置解析到真实 `http-chat` 模型。`agent_tasks=true` 时，内部工作流会额外写 `.agent_tasks.md` 侧车任务文件，供平台 Agent 审查、填充和继续决策。启动 `serve-api` 的同一环境中需要配置全局模型配置，或设置 `LEW_MODEL_API_BASE`、`LEW_MODEL_NAME` 和 API Key；若只是导入验证，可在 Dify 中显式选择 `dry-run`。

历史工作台在 `v0.46.0` 起曾把 Dify 默认入口收束到 `/director/chat`。在项目型 Skill 发布形态中，这条链路只作为可选本地演示：平台 agent 可以直接执行 `project-seeding`、`character-lab`、`worldbuilding-lab`、`outline-lab`、`scene-loop` 等文件工作流，并把 Dify 当作外部审批面板或 HTTP 调用器。Dify 不保存模型 key，也不成为 canon 来源。

人物状态写回、候选资产晋升和章节发布不要放进默认 Dify 自动链路，应在人工 `approve` 后由受控命令执行。

如果 `serve-api` 启用了 `--api-token`，在 Dify HTTP Request 节点加入：

```text
Authorization: Bearer your-token
```

或：

```text
X-LEW-API-Token: your-token
```

## 人工审批节点

默认 DSL 为网页端导入优先版，暂不预置 Human Input / 分类器节点。导入成功后，建议在 Dify UI 中追加：

1. Human Input 节点：读取 `Read director report` 的返回内容，由人工选择 `approve`、`revise` 或 `reject`。
2. HTTP Request 节点：调用 `POST /workflow/approve`，写入 `project_root`、`run_id`、`decision`、`actor`、`notes`。
3. End 节点：输出 workflow run 响应、日志响应和审批记录响应。

`/workflow/approve` 会返回：

- `approval_path`
- `index_path`
- `task_path`

其中 `revise` / `reject` 会自动生成 `workflow/tasks/` 下的后续任务。需要汇总时运行：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench approval-summary "C:\path\to\work"
```

这样做的原因是 Dify 的 Human Input / 分类器节点 DSL 字段随版本变化较大，先导入基础 HTTP 链路更稳。

## 导入失败排查

- 确认导入的是 `.yml` 文件，而不是 skill zip。
- 确认 YAML 顶层包含 `kind: app`、`version: "0.6.0"`、`dependencies: []`、`workflow:`。
- 若 Dify 提示版本不兼容，重新生成并指定 `--dsl-version "0.7.0"`。
- 若 Dify 提示节点字段不兼容，先删除导入文件中的第二个 HTTP 节点，只保留 Start -> Run creative director -> End 验证基础导入。
- 若导入成功但运行失败，再检查 `WORKBENCH_API_BASE` 与本地 `serve-api` 是否可被 Dify 访问。

## 边界

- Dify 不直接修改 `canon/`、`characters/`、`plot/`。
- `/workflow/approve` 只记录人工决策，不自动写 canon。
- blocked 或 failed 的 run 不应被当作正式交付。
- 若 Dify 版本调整了节点内部 DSL 字段，可保留变量名和 HTTP endpoint 契约，在 UI 中重新选择 HTTP Request / Human Input 等节点。

## 参考

- Dify HTTP Request node：https://docs.dify.ai/en/cloud/use-dify/nodes/http-request
- Dify Human Input node：https://docs.dify.ai/en/cloud/use-dify/nodes/human-input
