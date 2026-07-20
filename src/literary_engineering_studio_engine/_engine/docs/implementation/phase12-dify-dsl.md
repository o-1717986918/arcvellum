# Phase 12：Dify Workflow DSL 示例

## 目标

Phase 12 在 Phase 11 的 `serve-api` 基础上，补一份可进入 Dify 的 Workflow DSL starter，并提供 CLI 生成器，避免手工维护 YAML。

`v0.12.1` 起，默认 DSL 改为网页端导入优先的 import-safe 版本：保留 Start、HTTP Request 和 End 的基础链路，暂不在 YAML 中预置 Human Input / 分类器等更依赖 Dify 版本的节点。

## 新增命令

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench dify-dsl
```

输出：

```text
docs/integrations/dify/literary-workbench-reviewer.workflow.yml
```

可选参数：

- `--out`
- `--app-name`
- `--api-base`
- `--dsl-version`
- `--default-mode`
- `--default-scene`
- `--default-chapter-id`

## Workflow 结构

当前 DSL 包含：

```text
Start
  -> Run creative director
  -> Read director report
  -> End
```

对应后端 endpoints：

- `POST /director/chat`
- `GET /workflow/artifact`

Start 变量包含 `project_root`、`creative_direction`、`provider`、`auto_execute` 和 `agent_tasks`。`agent_tasks=true` 时，创作总监触发的内部工作流会产出 `.agent_tasks.md` 侧车任务文件，供平台 Agent 审查与继续执行。

## 设计边界

- Dify 是审稿台和人工确认层。
- Workbench API 是文件状态和审查状态的唯一后端。
- Dify 不直接写 canon。
- `/workflow/approve` 仍由后端保留，但建议在成功导入基础 DSL 后，再在 Dify UI 中添加 Human Input 和审批记录 HTTP 节点。

## 注意

Dify 的导出 DSL 会随版本演化。当前文件优先保证基础导入成功、变量名、节点意图和 HTTP endpoint 契约稳定；如果导入后某个节点 UI 字段不兼容，按 `docs/integrations/dify/README.md` 中的映射在 Dify UI 里重新校准节点即可。
