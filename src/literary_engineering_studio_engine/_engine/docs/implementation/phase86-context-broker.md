# Phase 86：Context Broker / Context Trace

版本：`v0.86.0`

本阶段把场景上下文从“只有一份可读 Markdown”升级为“Markdown packet + machine-readable trace”的双产物机制。目标是让正式创作链路能自动证明：平台 Agent 写作、推演、审查时依据了哪些项目文件，漏掉了什么，哪些文件被摘要或排除。

## 1. 新增文件

1. `src/literary_engineering_workbench/context_broker.py`
2. `schemas/context_trace.v1.json`
3. `docs/modules/context-broker.md`

## 2. 核心行为

`context` 命令现在会同时写出：

```text
memory/context_packets/{scene_id}.md
memory/context_packets/{scene_id}.trace.json
```

Trace JSON 记录：

1. 当前 route 与 scene_id。
2. context packet 与 scene 文件路径。
3. 必需上下文组。
4. 已加载文件、摘要文件、排除文件。
5. mounted style、word budget、角色文件、canon 文件。
6. 上一场尾部信息和上下文长度预算。
7. `missing_required_context`。

## 3. 接入模块

本阶段改动覆盖以下链路：

1. `context_packet.py`：写 trace。
2. `cli.py`：`context` 增加 `--trace-out`，stdout 打印 `context_trace`。
3. `workflow_state.py`：新增 `context-trace` 状态。
4. `task_registry.py`：新增 `context-trace` 任务，后续正式任务 source paths 携带 trace。
5. `agent_task_status.py` / `scene_readiness.py`：无效 trace 阻塞 route gate、chapter readiness 和 export readiness。
6. `scene_composer.py`：composition payload 和 sidecar 引用 trace。
7. `prompt_pack.py`：prompt manifest 引用 trace；外部传入 context packet 但缺 trace 时 hard fail。
8. `generation_provider.py` / `platform_agent_tasks.py`：generation sidecar 要求读取 trace。
9. `agent_scene_review.py`：review prompt 注入 trace JSON，缺 trace 时禁止 clean pass。
10. `scene_revision.py`：revision task 与 prompt manifest 引用 trace。
11. `roleplay_lab.py` / `branch_lab.py`：RP 与 branch sidecar 显式要求读取 trace。
12. `chapter_pipeline.py` / `workflow_runner.py` / `orchestration_blueprint.py`：保留 trace provenance。
13. `init_project.py`：work-project 模板说明 trace 文件。

## 4. 新增门禁

下列情况被视为 blocking：

1. `memory/context_packets/{scene_id}.md` 存在但 `.trace.json` 缺失。
2. trace JSON 不是 `literary-engineering-workbench/context-trace/v1`。
3. trace 的 `scene_id` 与当前 scene 不一致。
4. trace 的 `context_packet` 不指向当前 packet。
5. trace 的 `missing_required_context` 非空。
6. trace 没有任何 `loaded_files`。

`task-next` 在发现 packet 存在但 trace 缺失时，会派发 `context-trace` 修复任务；`route-audit`、`agent-task-status`、chapter readiness 和 export readiness 也会报告同一问题。

## 5. 测试

新增或更新的测试覆盖：

1. context packet 生成时写出 trace。
2. trace 包含 scene、character、canon、style、word-budget 等来源信息。
3. 主要角色与场景相关次要角色进入 `character_files`，无关角色进入 `excluded_files`。
4. task registry 将 trace 纳入 expected outputs 和 task Markdown。
5. packet 存在但 trace 缺失时，`task-next` 派发修复任务。
6. `route-audit` 阻塞缺 trace 的 scene-development 链路。

## 6. 后续方向

Context Broker 已完成最小可用闭环，但后续仍可增强：

1. 为高风险任务提供更细的 context budget 策略。
2. 对 `loaded_files` 做 hash 记录，支持判断 trace 是否过期。
3. 将 Reader Experience Contract、章节义务和读者问题也纳入 trace。
4. 在 dashboard 中把缺失上下文、被排除角色和 style/word-budget 来源展示给用户。
