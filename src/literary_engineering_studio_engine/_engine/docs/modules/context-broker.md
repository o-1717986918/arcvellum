# Context Broker / Context Trace

Context Broker 是 `v0.86.0` 引入的上下文证明层。它不替平台 Agent 做创作判断，也不替代 Prompt Registry；它只负责把正式场景创作需要的上下文打包，并留下机器可审计的来源 trace。

一句话原则：

> 没有 context trace 的 context packet，不是正式上下文。

## 1. 解决的问题

过去 `memory/context_packets/{scene_id}.md` 只有一份 Markdown。它对人类可读，但很难自动回答这些问题：

1. 这次写作是否真的读了当前 scene 文件？
2. 是否加载了主要角色与本场景涉及的次要角色？
3. 是否加载了 canon、forbidden changes、outline、foreshadowing、mounted style 和 word budget？
4. 是否有关键文件缺失？
5. 是否为了上下文长度故意排除了某些角色或素材？
6. 后续 RP、branch、composition、generation、review 是否引用了同一份上下文？

Context Trace 把这些问题变成可检查的 JSON，而不是依赖平台 Agent 的自觉。

## 2. 产物

正式 `context` 命令必须生成两份文件：

```text
memory/context_packets/{scene_id}.md
memory/context_packets/{scene_id}.trace.json
```

Markdown packet 是平台 Agent 写作时阅读的紧凑上下文。Trace JSON 是 provenance artifact，用来证明本次 packet 的来源、范围和缺失项。

CLI 输出中也会打印：

```text
context_packet: memory/context_packets/scene_0001.md
context_trace: memory/context_packets/scene_0001.trace.json
```

看到第一行不代表 context 完成；必须同时检查第二行。

## 3. Trace 字段

`context_trace.v1` 至少包含：

1. `schema`
2. `route`
3. `scene_id`
4. `context_packet`
5. `scene_file`
6. `required_context_groups`
7. `loaded_files`
8. `summarized_files`
9. `excluded_files`
10. `style_mounts`
11. `word_budget_source`
12. `character_files`
13. `canon_files`
14. `previous_scene_tail`
15. `token_or_length_budget`
16. `missing_required_context`

`missing_required_context` 非空时，正式路线不得继续。平台 Agent 应先补项目文件或重跑 `context`，再进入 RP、branch、composition、generation、review、revision、promotion、chapter workspace 或 export。

## 4. 正式链路接入点

下列模块必须保留或检查 trace：

1. `context`：生成 Markdown packet 与 trace。
2. `workflow-state` / `task-next`：如果 packet 存在但 trace 缺失，派发 `context-trace` 修复任务。
3. `agent-task-status` / `route-audit`：把无效 trace 作为 blocking gate。
4. `simulate-scene --agent`：RP sidecar 要求平台 Agent 先读 trace。
5. `branch-simulate --agent`：branch sidecar 要求平台 Agent 读 trace 后再做分支判断。
6. `compose-scene --agent-tasks`：composition manifest 写入 `context_trace`。
7. `generate-scene`：缺 trace 时重建 context；prompt pack 和 `.agent_tasks.md` 都引用 trace。
8. `agent-review-scene`：review prompt 和 sidecar 都引用 trace；缺 trace 时不能 clean pass。
9. `revise-scene`：修订 prompt manifest 与任务包引用 trace；trace 缺失时先修复 context。
10. `chapter-workspace` / `export-package`：从 scene readiness 继承 trace gate。

## 5. 平台 Agent 执行纪律

正式场景开发时，平台 Agent 必须：

1. 先通过 `task-next` / `task-open` 获取当前任务。
2. 对 context 类任务运行 `context`，确认 CLI 输出同时包含 packet 与 trace。
3. 打开 trace，检查 `scene_id`、`context_packet`、`loaded_files`、`character_files`、`canon_files`、`style_mounts`、`word_budget_source` 和 `missing_required_context`。
4. 在 RP、branch、composition、generation、review 或 revision 的 reading receipt 中记录已读 trace。
5. 不手写 `*.trace.json` 冒充正式产物；若 CLI 失败，只能记录 attempted command failure 和 CLI-equivalent workaround，且不得绕过后续 gate。

## 6. 与 Prompt Registry 的关系

Prompt Registry 决定“这个任务该怎么要求平台 Agent 输出”。Context Broker 决定“这个任务依赖的上下文是否真实、可追踪、可复盘”。

二者必须同时存在：

1. `task-open` 注入 Prompt Asset，告诉 Agent 做什么。
2. source paths 和 prompt manifest 引用 Context Trace，告诉 Agent 必须依据什么做。

## 7. 常见失败模式

1. **只有 packet 没有 trace**：视为未完成 context；重跑 `context`。
2. **trace 指向旧 scene**：视为错误来源；重跑当前 scene 的 `context`。
3. **trace 报告 missing required context**：补文件或确认缺失原因，不能直接生成正文。
4. **prompt manifest 没有 trace**：重新运行 `generate-scene` 或相关 CLI，不手写 manifest。
5. **review 想 clean pass 但 trace 缺失**：review 必须阻塞，并要求先修复上下文来源证明。
