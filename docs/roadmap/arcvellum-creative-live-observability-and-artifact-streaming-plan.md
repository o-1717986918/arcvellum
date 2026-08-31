# ArcVellum 创作现场、Agent 会话与产物流实施方案

状态：Implemented in v0.99.4
基线版本：ArcVellum v0.99.3  
日期：2026-08-31  
适用仓库：`literary-engineering-studio-v099-work`

## 1. 决策摘要

ArcVellum 下一阶段应把已经存在的 Runtime 事件、任务状态、候选产物、审查证据和正式晋升结果组织成一个面向文学用户的“创作现场”。用户需要持续看见作品正在被理解、生成、审查、修订和晋升，同时能够按需展开完整的可见 Agent 会话、工具活动、上下文摘要、Token、成本与诊断信息。

本方案采用以下技术路线：

1. 保持 Engine、CLI、TaskPackage、Gate、Promotion、Canon 和事务写回的唯一权威不变。
2. 复用现有 `RuntimeEventSink`、`LiveEventBus`、Worker Job SSE 和 Autopilot SSE，不建立第二套消息系统。
3. Pi Worker 从已经存在的 `toolcall_delta` 中提取 `write_expected_output` 的候选内容增量，形成只读、临时、可恢复的产物预览流。
4. Studio 建立统一的 Creative Live Projection，把 Runtime 原始事件投影为创作活动、会话、产物、审查、修订、用量六类用户可见事件。
5. 前端默认展示文学意义明确的“创作现场”，完整技术会话进入可展开的工作台，原始诊断进入高级模式。
6. 流式候选永远不直接成为正式正文。只有现有预检、AgentReview、Promotion 和写回完成后，Reader 与正式星仪节点才能显示晋升状态。
7. 不要求模型为了界面展示额外解释自己。所有可视化尽量从已有流、工具、产物和 Gate 证据确定性派生，避免增加 Token、延迟与创作干扰。

这项工作属于 Runtime Observability、Read Model 和 Frontend Projection 的扩展，不属于文学状态机重写。

## 2. 实际基线审计

### 2.1 已具备的能力

当前工程已经具备主要基础设施：

- `workers/pi-worker/src/event-adapter.ts` 能接收 `text_delta`、`thinking_delta`、工具开始/结束、会话状态和 Token/成本事件。
- Pi Agent Core 会把 `toolcall_start`、`toolcall_delta`、`toolcall_end` 作为 `message_update` 传给 Worker；Pi AI 的 partial tool call 已包含逐步解析的 arguments。
- `workers/pi-worker/src/tools.ts` 的 `write_expected_output` 是正式 Agent 产物写入的唯一工具边界，路径和所有权已经受 Task Context 限制。
- `runtime/worker_observability.py` 已为 Worker 事件附加 Context Ledger 和 Agent Session 身份。
- `observability/live_events.py` 已提供有界的临时事件总线。
- `/worker/jobs/{job_id}/stream` 已能把持久事件与 `LiveEventBus` 临时事件合并为 SSE，并支持 `Last-Event-ID`。
- Style Atelier 与 Archaeology 已消费 Worker Job Stream，证明客户端流式基础可用。
- `/autopilot/runs/{run_id}/stream`、`/agent-observability/stream` 和 Workspace SSE 已存在。
- `AgentObservability v3` 已投影活动、上下文、会话、服务、吞吐和最近事件。

### 2.2 当前可感知性断点

当前用户只能看到粗粒度状态，原因来自以下连接缺口：

1. `WorkerEventAdapter.handleMessageUpdate()` 只处理 `thinking_delta` 和 `text_delta`，忽略 `toolcall_delta`。主创正文位于 `write_expected_output.content`，因此正文生成过程没有进入事件流。
2. `write_expected_output` 只在原子写入完成后发送 `file.changed {path}`，不发送产物类型、字符数、摘要、验证结果或内容快照。
3. `automation/controller.py::_worker_event()` 对 ephemeral 事件直接返回。全自动创作中的正文增量、推理活动和会话状态没有进入 Autopilot 实时频道。
4. `agent_session_tracking.py` 主动忽略 `agent.message.delta`，会话记录只有阶段摘要，没有最终可见消息、工具序列和产物关系。
5. `agent_observability.py` 只选择最近的少量持久事件，并将消息压缩为用户安全摘要；它不拥有大文本、差异或完整会话。
6. `AgentObservatoryView.vue` 的界面目标是安全状态投影，当前没有正文、修订、批注或会话阅读器。
7. 直接 Worker 任务可以读取 Job Stream，全自动路线却没有等价的临时事件转发，造成同一 Worker 在两条产品路径下可见性不同。

### 2.3 关键技术判断

仅显示 `agent.message.delta` 无法解决问题。ArcVellum 的主创 Profile 要求正文任务第一步调用 `write_expected_output`，聊天文本不是正式产物。用户会继续经历长时间等待，然后看到文件突然出现。

真正的改进点是产物级流：

```text
Provider token stream
  -> Pi toolcall_delta partial arguments
  -> Artifact Preview Extractor
  -> Creative Live Event
  -> LiveEventBus / SSE
  -> Candidate Manuscript Preview
  -> 完整工具参数
  -> 原子 Sandbox 写入
  -> 确定性 Preflight
  -> Review / Revision / Promotion
  -> Formal Reader
```

## 3. 产品信息架构

### 3.1 三层可见性

| 层级 | 受众 | 默认展示 | 内容 |
| --- | --- | --- | --- |
| 创作现场 | 普通用户 | 是 | 当前任务、场景目标、正文生长、审查、修订、晋升、等待原因 |
| Agent 工作台 | 深度用户 | 按需展开 | 可见会话、工具、资料摘要、上下文、模型、Token、成本、耗时 |
| 技术追踪 | 维护者 | 高级设置开启 | 原始事件名、Task/Run ID、Prompt digest、预检代码、恢复记录 |

默认界面不得直接倾倒 JSON、系统 Prompt、绝对路径或工具协议。结构化任务要转换为人物卡、分支卡、审查批注、节奏曲线和资产变化；只有高级模式允许查看经过脱敏的机器表示。

### 3.2 创作现场的核心对象

创作现场以“当前作品产物”为中心，而非以进程为中心：

- 当前文学任务：这一步要解决的场景、人物、结构或审查目标。
- 工作中产物：流式候选正文、候选资产、分支、Review 或状态补丁。
- 证据关系：本轮读取了哪些人物、Canon、场景合同与文风版本。
- 修订关系：哪条审查意见触发了哪一段修改。
- 正式身份：预览、候选、预检通过、审查通过、已晋升、已写回。
- 运行状态：角色、模型、会话、首段等待、工具活动、成本和阻塞。

### 3.3 正式身份阶梯

前端和事件合同必须使用同一组身份，不得把预览称为正式正文：

```text
streaming_preview
  -> candidate_written
  -> deterministic_preflight_passed
  -> semantic_review_passed
  -> promoted
  -> state_and_canon_applied
```

失败、修订和替代使用：

```text
validation_failed
revision_streaming
revision_written
superseded
rejected
```

Reader 继续只读取已晋升正文。创作现场单独显示临时候选，并在晋升时将其视觉上汇入正式长卷。

## 4. 目标架构

```text
┌──────────────── Literary Engineering Engine ────────────────┐
│ TaskPackage / Gate / Review / Promotion / State / Canon     │
└──────────────────────────┬───────────────────────────────────┘
                           │ formal contracts and receipts
┌──────────────── Studio Runtime ──────────────────────────────┐
│ AgentWorker                                                 │
│   ├─ PiWorkerRuntime                                        │
│   ├─ WorkerObserver                                         │
│   └─ WritebackCoordinator                                   │
│                                                             │
│ CreativeLiveProjector                                       │
│   ├─ Activity Projection                                    │
│   ├─ Session Transcript Projection                          │
│   ├─ Artifact Preview Projection                            │
│   ├─ Review / Revision Projection                           │
│   └─ Usage Projection                                       │
│                                                             │
│ LiveEventBus (ephemeral, bounded)                           │
│ Persistence (final messages, checkpoints, diffs, receipts) │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST snapshot + resumable SSE
┌──────────────── Vue Client ──────────────────────────────────┐
│ CreativeLiveStore                                           │
│   ├─ LiveManuscript                                         │
│   ├─ ReviewRail / RevisionDiff                              │
│   ├─ SessionTranscript                                      │
│   ├─ ExecutionTimeline                                      │
│   └─ OrreryLiveBinding                                      │
└──────────────────────────────────────────────────────────────┘
```

### 4.1 依赖方向

- Engine 不导入 Studio Observability，也不感知 SSE 或界面。
- Pi Worker 只产生 Runtime 事件，不判断 Promotion 或正式项目状态。
- Studio Projection 只消费事件和正式收据，不修改任务流程。
- API Router 只装配 Snapshot 与 Stream，不解释文学状态。
- 前端不通过动画推断 Gate；所有正式状态来自 Engine/Studio Read Model。
- Artifact Preview 是 display-only，不能作为 Task completion、恢复或写回证据。

## 5. 统一事件合同

### 5.1 Creative Live Event v1

新增共享 Schema：

`protocol/observability/creative-live-event.schema.json`

建议合同：

```json
{
  "schema": "arcvellum/creative-live-event/v1",
  "event": "artifact.preview.delta",
  "sequence": 128,
  "at": "2026-08-31T12:00:00Z",
  "project_id": "project-digest",
  "controller_id": "autopilot-or-job-id",
  "run_id": "worker-run-id",
  "session_id": "agent-session-id",
  "task_id": "scene-0001-candidate-generation",
  "route": "scene-development",
  "role": "main-creative-agent",
  "channel": "artifact",
  "visibility": "user",
  "durability": "ephemeral",
  "data": {}
}
```

`project_id` 使用不可逆摘要，不在事件中传绝对项目路径。`controller_id` 连接 Autopilot 或手动 Job，`run_id` 连接 Sandbox run，`session_id` 连接 Provider 会话。

### 5.2 事件频道

| Channel | 典型事件 | 持久化策略 |
| --- | --- | --- |
| `activity` | `task.opened`、`runner.reasoning.started`、`tool.started` | 阶段持久，高频活动临时 |
| `transcript` | `agent.message.delta/completed`、`tool.summary` | delta 临时，完成消息有界持久 |
| `artifact` | `artifact.preview.*`、`artifact.checkpoint` | delta 临时，checkpoint 持久 |
| `review` | `review.finding`、`revision.diff`、`validation.*` | 持久 |
| `usage` | `usage.updated`、首 Token 和阶段耗时 | 汇总持久 |
| `control` | `waiting_human`、`blocked`、`cancelled`、`promoted` | 持久 |

### 5.3 可见性等级

```text
user        普通用户可直接理解的文学活动和产物
advanced    会话、工具、上下文与用量
diagnostic  原始事件 ID、错误码、Prompt digest 和恢复细节
restricted  凭证、原始系统秘密、未授权资料；永不发送到前端
```

可见性由 Studio/Pi 的机器规则决定，模型不能在输出中自行声明等级。

### 5.4 临时事件与持久事件

继续复用 `EventDurability`。扩展 ephemeral 集合：

- `agent.message.delta`
- `runner.reasoning.activity`
- `runner.session.status`
- `artifact.preview.delta`
- `artifact.preview.progress`

以下事件持久化：

- `agent.message.completed` 的脱敏最终文本或摘要；
- `artifact.preview.completed` 元数据；
- `artifact.checkpoint` 的 path、digest、characters、format 和 validation；
- `validation.failed/passed`；
- `revision.diff.completed`；
- `artifact.promoted` 与正式 receipt；
- 会话结束、失败、取消和用量汇总。

不得把每个 Token 增量写入 SQLite 或项目目录。

## 6. Pi Worker 模块方案

### 6.1 `workers/pi-worker/src/event-adapter.ts`

职责扩展：

- 处理 `toolcall_start`、`toolcall_delta`、`toolcall_end`。
- 只追踪 `write_expected_output` 的 partial arguments；其他工具只发送已有的开始/完成事件。
- 为每个 `contentIndex` 维护工具名、上次可见参数、输出路径和已发送字符偏移。
- 从 Pi 已解析的 `partial.content[contentIndex].arguments` 读取字符串，避免自行解析不完整 JSON。
- 新内容是旧内容前缀扩展时只发送追加部分；前缀关系失效时发送完整 `artifact.preview.snapshot`，避免重复或错序。
- 对 Provider 不支持工具参数流的情况，在单次完整 delta 或 `toolcall_end` 发送 snapshot。
- 推理内容与产物内容分离，不能把 tool arguments 当作聊天文本。

建议把产物提取职责拆到新模块：

```text
workers/pi-worker/src/artifact-preview.ts
  ArtifactPreviewExtractor
  previewOutputContracts()
  extractPartialWrites()
  appendOrSnapshot()
  resetAttempt()
```

`event-adapter.ts` 只负责 AgentEvent 到 Runtime Event 的路由，避免继续膨胀。

### 6.2 Task Context 预览政策

Studio 编译 Pi Task Context 时，为 Agent-owned output 增加机器拥有字段：

```json
{
  "path": "drafts/scenes/scene_0001_candidate.md",
  "format": "markdown",
  "preview_mode": "prose_stream",
  "artifact_kind": "scene_candidate",
  "display_label": "第一场候选正文"
}
```

`preview_mode` 只允许：

- `prose_stream`：正文或长篇文学文本，逐段显示。
- `markdown_stream`：可读报告，Markdown 流式显示。
- `semantic_on_commit`：JSON/YAML 在完整后转为语义卡，不流式显示原始标记。
- `metadata_only`：只显示进度、字符数和完成状态。
- `hidden`：敏感或纯机器产物不进入创作现场。

该字段由 Studio 根据 TaskPackage output contract 投影，不能由模型选择，也不改变 Engine 正式合同。

### 6.3 `workers/pi-worker/src/tools.ts`

`write_expected_output` 写入完成后补发：

```text
artifact.checkpoint
  path
  artifact_kind
  format
  characters
  sha256
  validation_passed
  issue_count
```

不得在 checkpoint 中重复发送全文。正文全文已经通过 preview snapshot 或正式文件读取获得。

### 6.4 修订尝试

每次 Worker 执行和 repair 必须有 `attempt_id`。新尝试开始时发送：

```text
artifact.revision.started
artifact.preview.started
```

完成后由 Studio 比较上一 checkpoint 与新 checkpoint，形成正式 diff。旧预览标记为 `superseded`，不能在界面中静默覆盖。

### 6.5 Pi 单元测试

新增：

- `workers/pi-worker/test/artifact-preview.test.ts`
- `workers/pi-worker/test/event-adapter-artifact-stream.test.ts`

覆盖：

- 单文件正文参数逐步增长；
- path 晚于 content 出现；
- path 省略但可由唯一输出合同推断；
- batch outputs；
- Unicode、引号、换行和部分转义；
- partial prefix 失效后的 snapshot；
- Google 类一次性完整 tool delta；
- JSON `semantic_on_commit` 不泄露半截 JSON；
- repair attempt 隔离；
- 非授权输出和 restricted output 不产生正文事件；
- 2,000,000 字符上限下不出现无界副本累积。

## 7. Studio Runtime 与 Observability 模块方案

### 7.1 新模块布局

```text
src/literary_engineering_studio/observability/creative_live/
  __init__.py
  contracts.py
  projector.py
  artifact_projection.py
  transcript_projection.py
  review_projection.py
  snapshot.py
  redaction.py
  coalescing.py
```

边界：

- `contracts.py`：事件 DTO、频道、可见性、正式身份枚举。
- `projector.py`：原始 Runtime/Event Store 事件到 Creative Live Event 的单向投影。
- `artifact_projection.py`：预览增量、checkpoint、attempt 与正式 identity ladder。
- `transcript_projection.py`：最终消息、工具摘要和会话条目。
- `review_projection.py`：预检、AgentReview、修订、Promotion 和 Apply receipt 的关联。
- `snapshot.py`：断线后恢复当前预览、会话、阶段和最近 diff。
- `redaction.py`：在现有 `observability/redaction.py` 基础上增加字段级政策，不复制密钥正则。
- `coalescing.py`：按 session/artifact 合并高频 delta，实施背压。

现有 `agent_observability.py` 继续提供轻量摘要，不直接承载完整正文或会话。Creative Live 是它的可展开细节层。

### 7.2 `LiveEventBus` 复用

不新增第二个 EventBus。扩展现有 Channel 约定：

```text
worker:{job_id}
autopilot:{run_id}
project:{project_digest}
session:{session_id}
```

同一个事件只构造一次，再路由到需要的有界频道。每个频道必须有：

- 最大事件数；
- 最大总字节数；
- 过期时间；
- sequence；
- 丢失后 snapshot 恢复合同。

建议初始预算：单事件正文增量 1–4 KiB，100–250 ms 合并一次；单个 active artifact 内存预览不超过 2 MiB；单个 run 的总临时数据不超过 8 MiB。实际值通过长场景压力测试校准。

### 7.3 `automation/controller.py`

修改 `_worker_event()`：

1. 继续把所有事件交给 Session/Context/Mutation projector。
2. durable 事件继续进入 Autopilot Event Store。
3. ephemeral 事件不写数据库，但要发布到 `autopilot:{run_id}` 和当前 session/artifact 频道。
4. `agent.message.delta`、`artifact.preview.delta` 不更新正式 progress fingerprint。
5. activity liveness 与 productive progress 继续分离；正文 delta 计入 productive progress，纯 reasoning 只计入 liveness。

这样手动 Worker 和全自动 Worker 获得一致的可见性，而不增加 SQLite 写放大。

### 7.4 `runtime/worker_observability.py`

为每次事件附加：

- `task_id`
- `route`
- `run_id`
- `session_id`
- `attempt_id`
- `agent_role`
- `artifact_kind`（存在时）

仍不得附加绝对项目路径、Prompt 全文或凭证。

### 7.5 会话持久化

扩展 Persistence Port，新增有界的 `agent_session_entries`：

```text
session_id
sequence
entry_type: message | tool | checkpoint | validation | control
visibility
summary
payload_digest
created_at
```

普通模式持久化：

- 完整的最终可见 Agent 文本；
- 工具名、目标产物、状态、耗时和安全摘要；
- 产物 checkpoint；
- 验证与修订摘要；
- 用量汇总。

默认不持久化 raw reasoning delta。高级设置可以选择“仅本次会话实时显示 Provider 返回的 reasoning”，退出会话后丢弃。若未来允许持久保存，必须单独引入 retention、尺寸、用户确认和 Provider 能力声明。

“完整会话”定义为 ArcVellum 实际收到且允许展示的消息和工具记录，不能宣称包含 Provider 未返回的内部推理。

### 7.6 Artifact Revision 与 Diff

Studio 不在每个 token 上计算 diff。只在以下节点形成差异：

- 第一次候选 checkpoint；
- repair checkpoint；
- AgentReview 后修订 checkpoint；
- Promotion 前最终 checkpoint。

新模块建议：

```text
src/literary_engineering_studio/observability/artifact_revisions.py
```

职责：

- 读取 Sandbox 中受授权的前后版本；
- 对 Markdown/正文按段落和行生成 bounded diff；
- 关联触发修订的 review finding 或 preflight issue；
- 保存 digest、hunk、原因和 attempt；
- 不写正式正文，不替代 Revision Gate。

长正文 diff 只返回当前修改附近的 hunk，前端按需读取完整版本。

## 8. API 与 SSE 模块方案

### 8.1 API 边界

新增 Router：

```text
src/literary_engineering_studio/api/routers/creative_live.py
```

API Server 只注入 Projector、Snapshot Store、Session Repository 和 EventBus，不在 Router 内拼文学状态。

### 8.2 端点

```text
GET /creative-live?project_root=...
GET /creative-live/stream?project_root=...&channels=activity,artifact,review
GET /creative-live/runs/{controller_id}/snapshot
GET /creative-live/sessions/{session_id}
GET /creative-live/artifacts/{artifact_id}/revisions
GET /creative-live/artifacts/{artifact_id}/revisions/{revision_id}
```

`/worker/jobs/{job_id}/stream` 和 `/autopilot/runs/{run_id}/stream` 保持兼容。它们内部调用共享的 stream merger，而不是各自复制临时事件逻辑。新 `/creative-live/stream` 为项目级聚合入口，适合星仪和创作现场长期订阅。

### 8.3 SSE 恢复

- 所有事件带单调 sequence 和 event id。
- 客户端重连携带 `Last-Event-ID`。
- Ring Buffer 仍有对应事件时继续增量。
- Cursor 已过期时先发送 `creative.snapshot`，再继续新事件。
- snapshot 含当前 artifact 完整预览、attempt、阶段、会话和最后 checkpoint，不含 raw reasoning 历史。
- stream 继续发送 heartbeat；heartbeat 不进入 UI 时间线。

### 8.4 背压与性能

- Server 每 100–250 ms 合并同一 artifact 的相邻 delta。
- 只发送新增文本，不重复发送整个累计字符串。
- 前端每 animation frame 或 50–100 ms 批量落入响应式状态，避免每 Token 触发 Vue 重排。
- 后台标签页降低渲染频率，但保持 SSE 连接和内存缓冲。
- 超过内存预算时丢弃旧 delta，保留最新 snapshot、checkpoint 和持久事件。
- 流式展示不得增加新的模型请求、工具回合或 Prompt 文本。

## 9. 前端模块方案

### 9.1 新 Feature 目录

```text
client/src/features/creative-live/
  components/
    CreativeLiveDock.vue
    CreativeLiveHeader.vue
    LiveManuscript.vue
    ArtifactStatusRail.vue
    ReviewRail.vue
    RevisionDiff.vue
    SessionTranscript.vue
    ToolActivityList.vue
    ExecutionTimeline.vue
    UsageSummary.vue
  composables/
    useCreativeLiveStream.ts
    useArtifactPreview.ts
    useSessionTranscript.ts
  services/
    creativeLiveClient.ts
  stores/
    creativeLiveStore.ts
  types.ts
  presentation.ts
```

模块职责：

- Store 只合并事件、管理 cursor、attempt 和 snapshot，不生成正式文学判断。
- `presentation.ts` 把 route、task kind、event 和 artifact kind 转为中文用户文案。
- `LiveManuscript` 只显示候选预览与身份，不读取正式 Reader 文件冒充实时流。
- `ReviewRail` 只消费后端已关联的 finding，不在浏览器自行做 Lint。
- `RevisionDiff` 渲染后端 bounded diff，不在主线程比较整篇长文。
- `SessionTranscript` 支持 Markdown，但工具参数使用语义卡而非代码块倾倒。

### 9.2 创作现场布局

创作现场采用“正文为主、过程为轨”的信息结构：

```text
┌ 当前场景 / 任务 / 正式身份 / 停止控制 ┐
├──────────────────────┬────────────────┤
│                      │ 审查与修订轨   │
│   流式候选正文       │ finding        │
│   新增文字柔和显影   │ validation     │
│                      │ diff / gate     │
├──────────────────────┴────────────────┤
│ 阶段时间线  会话  工具  上下文  用量 │
└───────────────────────────────────────┘
```

默认不显示技术 ID。任务、角色和阶段使用文学含义明确的文案，如“正在形成第一场候选正文”“审读 Agent 正在核对人物选择”“修订稿已通过标点与文风预检”。

### 9.3 Agent 工作台

工作台提供：

- 会话列表和并发状态；
- 当前模型、角色、任务、开始时间和耗时；
- Agent 可见文本的 Markdown 流；
- 工具调用时间线；
- Context Ledger 的资料类别、数量、digest 和按需读取情况；
- Token、cache、成本和首 Token 延迟；
- blocker、repair、validation 和 retry；
- 高级模式下的原始事件名和技术详情。

工具卡只展示用户有意义的内容：

- `read_authorized_source`：读取了哪类资料、字符量和是否截断。
- `write_expected_output`：正在写什么产物、字符数、验证情况。
- `validate_output`：通过项目和问题数量。
- `complete_task`：正在交给 Studio 正式预检。
- `report_blocker`：阻塞原因和建议动作。

### 9.4 星仪接入

新增：

```text
client/src/features/orrery/live/
  liveNodeState.ts
  liveEdgeState.ts
  liveCameraHints.ts
  liveWindowBinding.ts
```

星仪只消费 `CreativeLiveStore` 的语义状态：

- 当前任务节点产生缓慢呼吸与真实字符增长刻度。
- 读取人物、Canon、文风或场景合同时，对应既有关系线短暂增强。
- 分支候选完整产生后再长出分支，不根据模型半截 JSON 创建节点。
- Review finding 以节点边缘刻度和 Review Rail 表现。
- 修订期间节点保持候选色；晋升 receipt 到达后才切换正式亮度。
- Promotion 时触发一次内容汇入正文长卷的动画。
- Agent 会话以节点附近的小型活动灯呈现，点击打开会话工作台。

动画必须由真实事件驱动。无事件时保持安静，不使用循环跑马灯模拟活动。

### 9.5 Reader 边界

- `ManuscriptReader` 继续只显示已晋升正文。
- Reader 可显示“某场正在创作”的非侵入提示，并允许打开创作现场。
- 用户可选择并排查看正式上一场和当前候选场。
- 当前候选晋升后，Reader 通过现有 Library/Workspace SSE 增量刷新。
- Reader 不直接订阅 token delta，避免正式阅读位置被临时稿扰动。

### 9.6 可访问性与动效

- 提供暂停自动滚动、暂停新增文字高亮和降低动效。
- 流式正文不强制把用户拉到末尾；只有用户位于底部附近时自动跟随。
- 新增文字使用短暂背景亮度，不逐字跳动排版。
- Screen Reader 以段落 checkpoint 宣告，不逐 Token 播报。
- 键盘可在正文、审查轨、会话和时间线间切换。

## 10. 文学任务的差异化投影

同一套事件不能把所有任务都渲染成聊天：

| 任务类型 | 主显示 | 辅助显示 |
| --- | --- | --- |
| 长篇规划 | 卷章场景库存、字数分配、节奏曲线 | Agent 解释、审查意见、版本差异 |
| 人物/世界资产 | 人物卡、关系、背景故事、Canon 候选 | 资料来源、字段变化、晋升状态 |
| RP 推演 | 角色行动、欲望、恐惧、代价 | 世界后果、冲突、分支形成 |
| 分支模拟 | 分支卡和评分变化 | 选择原因、合并元素、用户决策 |
| 正文生成 | 流式候选正文 | 字数、节奏、文风、当前场景合同 |
| AgentReview | 正文边注和问题列表 | 严重度、证据、pass/pass_with_notes/fail |
| 修订 | 行内 diff 和已解决 finding | 未解决问题、修订尝试、回退点 |
| State/Canon | 变化候选卡 | 审查、批准、写回 receipt |
| 导出 | 交付准备度和文件 | 过滤痕迹、章节完整性、格式结果 |

结构化产物在完成前只显示真实进度，不展示半截 JSON。正文和 Markdown 报告允许流式阅读。

## 11. 安全、隐私与真实性

### 11.1 禁止展示

- API Key、Token、密码和 credential store 内容；
- 原始绝对路径；
- Provider 请求头；
- 未授权上下文文件全文；
- system prompt 中的内部安全控制；
- hidden/restricted output；
- 模型没有返回的所谓“完整思维链”。

### 11.2 推理显示

当前 Pi Worker 只记录 reasoning 活动和字符数。后续可提供设置：

- `off`：只显示“正在推演”和持续时间；默认。
- `live_provider_reasoning`：只在当前会话实时显示 Provider 实际返回的 reasoning，结束后丢弃。
- `diagnostic_summary`：持久化机器生成的阶段摘要和计数，不保存原文。

界面必须标注“模型提供的可见推理记录”，不能标注“完整思维过程”。不支持 reasoning 的模型不显示伪造内容。

### 11.3 真实性原则

- 没有正文 delta 时不播放假打字动画。
- 没有 Gate receipt 时不显示“已通过”。
- 没有 Promotion 时不点亮正式章节。
- Provider 没有返回 Token/成本时显示“未报告”，不估造精确数字。
- 临时事件丢失时恢复 snapshot，不补造历史动画。

## 12. 测试架构

### 12.1 Python

新增：

```text
tests/observability/test_creative_live_contracts.py
tests/observability/test_creative_live_projection.py
tests/observability/test_artifact_preview_projection.py
tests/observability/test_session_transcript_projection.py
tests/observability/test_artifact_revisions.py
tests/api/test_creative_live_api.py
tests/api/test_creative_live_stream.py
tests/automation/test_autopilot_live_events.py
```

必须验证：

- Autopilot ephemeral 事件实时可见但不进入 durable event table；
- 手动 Worker 和 Autopilot 产生等价 Creative Live Event；
- 跨项目、跨 run、跨 session 不串流；
- Last-Event-ID 重连和 snapshot fallback；
- delta 合并、字节上限、过期和背压；
- 候选状态不能提升正式状态；
- review、diff、promotion 与 exact candidate digest 绑定；
- redaction 和 restricted policy；
- stream 断开不影响 Worker、Preflight 或 Writeback。

### 12.2 TypeScript/Vue

新增：

```text
client/src/features/creative-live/**/*.spec.ts
client/src/features/creative-live/**/*.spec.tsx
client/src/features/orrery/live/*.spec.ts
```

必须验证：

- 事件乱序、重复、重连和 attempt 切换；
- delta append 与 snapshot replace；
- 自动滚动只在用户位于末尾时发生；
- Markdown、长段落和 CJK 换行；
- candidate/promoted 视觉身份不能混淆；
- session/tool/review/usage 标签切换不丢数据；
- 结构化产物不泄露原始 JSON；
- reduced motion 和键盘可用性。

### 12.3 端到端

使用真实最小文学项目跑完：

```text
规划/RP
  -> 分支
  -> 正文流
  -> candidate checkpoint
  -> preflight
  -> AgentReview
  -> 至少一次可控修订
  -> promotion
  -> Reader 刷新
  -> 下一场任务
```

验收时同时记录：

- Provider 首事件、首正文 delta、checkpoint、review、promotion 时间；
- SSE 断线一次后的恢复；
- 页面前后台切换；
- 30,000 中文内容字符连续流压力；
- Windows 桌面安装版与开发 Web；
- 无 tool streaming Provider 的 snapshot 降级。

### 12.4 性能门槛

- 启用创作现场不得增加 Provider 请求次数。
- Prompt 字符数和模型输入 Token 不因展示增加。
- Worker P50/P95 任务完成时延相对关闭展示基线不劣化超过 3%。
- SQLite 写入量不随 token 数线性增长。
- 前端 30,000 字候选持续更新时保持可阅读，主线程长任务需要小于 50 ms。
- 关闭创作现场窗口后仍维持有界 Store，不持续执行 Markdown 全量重渲染。

## 13. 实施批次

每批开始前重新阅读本文、`module-boundaries.md` 和相关模块代码；每批结束执行定向测试、Architecture Audit、`git diff --check` 并独立提交。

### CL-0：Characterization 与合同

目标：锁住现有流行为，建立 Creative Live Event v1。

修改：

- `protocol/observability/creative-live-event.schema.json`
- `observability/creative_live/contracts.py`
- Pi/Studio/TypeScript 对应 DTO
- 现有 Worker Job SSE、Autopilot SSE characterization tests

完成条件：合同三端一致；关闭新能力时现有 API 和任务行为逐值兼容。

### CL-1：统一临时事件路由

目标：全自动任务能实时看到现有 Agent 活动。

修改：

- `automation/controller.py`
- `observability/live_events.py`
- `runtime/worker_observability.py`
- Worker/Autopilot 共享 stream merger

完成条件：`agent.message.delta` 和 reasoning activity 在 Autopilot SSE 可见，不落 durable store，不影响 progress fingerprint。

### CL-2：Pi 产物预览流

目标：正文和 Markdown 候选可真实流式显示。

修改：

- `workers/pi-worker/src/artifact-preview.ts`
- `workers/pi-worker/src/event-adapter.ts`
- `workers/pi-worker/src/tools.ts`
- Studio Task Context preview policy

完成条件：支持增量 Provider 逐段显示；不支持的 Provider 自动使用完整 snapshot；正式 Sandbox 文件仍只在完整工具调用后原子写入。

### CL-3：Creative Live Projection 与 API

目标：提供项目级 Snapshot、SSE、会话和产物接口。

修改：

- `observability/creative_live/*`
- `api/routers/creative_live.py`
- `api_server.py` 依赖装配
- Persistence Port 与 session entries

完成条件：断线恢复、跨项目隔离、背压、可见性与 redaction 测试通过。

### CL-4：正文、Review 与修订闭环

目标：用户能看到正文生成、审查、修改和晋升的连续关系。

修改：

- `observability/artifact_revisions.py`
- Review/Preflight/Promotion 事件关联
- bounded diff API
- digest/provenance tests

完成条件：每个 diff 可追溯到 exact candidate、finding/issue 和 attempt；旧预览明确 superseded。

### CL-5：创作现场与 Agent 工作台

目标：交付普通用户可直接理解的前端体验。

修改：

- `client/src/features/creative-live/*`
- 应用 Window Registry
- Agent Observatory 迁为高级工作台入口
- Markdown、diff 和长文本虚拟化

完成条件：普通用户无需理解 task id/JSON 即可知道当前在做什么、写出了什么、为何修改、是否晋升。

### CL-6：星仪与 Reader 联动

目标：让作品空间真实反映创作进行状态。

修改：

- `client/src/features/orrery/live/*`
- `SpatialWindowLayer.vue`
- Narrative Orrery node/edge presentation
- Reader 的“正在创作”入口和晋升刷新

完成条件：动画与节点状态完全由真实事件或正式 receipt 驱动；Reader 不显示未晋升候选。

### CL-7：生产收敛

目标：桌面端、Web、不同 Provider 和长文本下稳定交付。

工作：

- 全量 Python、Pi Worker、Vue、Rust 测试；
- 真实最小文学闭环；
- SSE 断线与进程退出测试；
- Windows 安装包、macOS CI；
- README、架构图、用户帮助和发布说明；
- 指标对比与 Git tag。

## 14. Git 闭环建议

```text
test(observability): characterize worker and autopilot live streams
feat(protocol): define creative live event contract
feat(runtime): forward bounded autopilot live activity
feat(pi-worker): stream authorized artifact previews
feat(observability): project creative sessions and artifacts
feat(review): expose candidate revision evidence
feat(ui): add creative live manuscript and session workspace
feat(orrery): bind live creative activity to narrative nodes
test(e2e): verify live prose review promotion loop
docs(release): record creative live verification
```

每个提交必须可独立回滚。CL-2 失败时应能关闭 artifact preview，仅退回现有状态观测；不得影响 Worker 正式写入。CL-5/CL-6 失败时后端流仍可通过测试客户端验证。

## 15. 禁止的实现方式

- 不让模型额外输出“我正在做什么”来驱动界面。
- 不把正文逐 token 写入正式项目文件。
- 不把半截 JSON 渲染成资产或分支节点。
- 不让前端根据动画、字符数或事件名称自行晋升正文。
- 不把每个 delta 持久化到 SQLite。
- 不在 `AgentObservability` 大摘要中塞入整篇正文。
- 不新建与 `LiveEventBus`、Job Event Store 平行的消息基础设施。
- 不用 WebSocket 重写当前单向 SSE，除非未来出现真实的双向低延迟编辑需求并有量化证据。
- 不暴露凭证、绝对路径、restricted source 或未经授权的上下文。
- 不把 Provider 可见 reasoning 宣称为完整思维链。
- 不通过放宽 Gate、跳过 Review 或提前写回来提升“看起来的进度”。

## 16. 风险与应对

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Provider 不流式返回工具参数 | 正文无法逐字出现 | 显示真实活动，toolcall 完成后发送 snapshot |
| partial arguments 回退或重写 | 重复、错序正文 | prefix 校验；失配时 snapshot replace |
| 长正文造成内存与 Vue 重排 | 卡顿 | chunk 合并、总量上限、段落缓冲、虚拟化 |
| 临时稿被误认为正式稿 | 用户信任受损 | 明确身份阶梯；Reader 只读 promoted |
| 全量会话泄露内部资料 | 安全问题 | visibility policy、字段脱敏、restricted 永不出后端 |
| 事件量拖慢 Worker | 吞吐下降 | 异步 sink、合并、丢弃旧 delta、性能门槛 |
| Review 与修订关联错误 | 误导用户 | exact candidate digest、attempt_id、receipt 绑定 |
| 重连错过正文 | 显示不完整 | ring cursor + artifact snapshot fallback |
| 界面再次变成工程控制台 | 普通用户难理解 | 默认文学投影；技术信息分层展开 |

## 17. 完成定义

只有同时满足以下条件才算交付：

1. 全自动和手动 Worker 都能在同一前端看到真实活动、会话和产物。
2. 支持工具参数流的 Provider 能逐段展示正文候选；不支持时有诚实的 snapshot 降级。
3. 用户可以看到正文从候选、预检、Review、修订到 Promotion 的完整身份变化。
4. 修订界面能说明哪些段落因哪条 finding 或 issue 发生变化。
5. 完整可见 Agent 会话、工具、上下文和用量可按需读取，默认界面没有 JSON 倾倒。
6. 星仪、创作现场和 Reader 对同一场景状态保持一致。
7. SSE 重连、应用切换、长文本、后台标签页和桌面端均不会丢失最终快照。
8. 未晋升文本绝不进入正式 Reader、导出或 Canon/State 写回。
9. 启用展示不增加模型请求、Prompt 体积或正式任务步骤，任务时延劣化不超过性能门槛。
10. 所有新增模块遵守现有依赖方向、Interface Development Standard 和 Architecture Audit。

## 18. 推荐优先级

最高收益路径是：

```text
CL-0 合同
  -> CL-1 Autopilot 临时事件
  -> CL-2 正文候选流
  -> CL-3 项目级 Stream
  -> CL-4 Review / Diff
  -> CL-5 创作现场
```

CL-6 星仪联动在创作现场稳定后实施。这样可以先证明事件、正文和正式身份正确，再投入高成本视觉动画。第一可用版本应优先让用户看见“正在写什么、为什么修改、何时成为正式正文”，随后再把这些事实转化为 ArcVellum 的空间叙事体验。

## 19. v0.99.4 实施记录

CL-0 至 CL-7 已按本文边界完成，正式文学状态机、Gate、Promotion、State/Canon 写回和 Reader 权威未被改写。

| 批次 | 交付结果 | 主要证据 |
| --- | --- | --- |
| CL-0 | Python、TypeScript、Pi Worker 共用 Creative Live Event v1 与产物身份阶梯 | `protocol/observability/creative-live-event.schema.json`、三端合同测试 |
| CL-1 | Runtime 临时事件进入项目频道和 Autopilot 实时频道，持久进度指纹不消费 delta | `automation/runtime_event_routing.py`、routing tests |
| CL-2 | `write_expected_output` 支持有界候选预览；无工具参数流时发送诚实 snapshot | `workers/pi-worker/src/artifact-preview.ts`、Pi tests |
| CL-3 | 项目 Snapshot、SSE、会话、上下文摘要与修订 API 可用，支持 `Last-Event-ID: live:<sequence>` | `api/routers/creative_live.py`、API reconnect tests |
| CL-4 | candidate、review、revision、mutation receipt 与 promotion 由 exact artifact digest 关联 | 完整身份链 API/投影测试 |
| CL-5 | 创作现场完成三栏工作台、Markdown 正文、审查轨迹、会话、工具、Diff 与用量展示 | Vue tests、Playwright 视觉证据 |
| CL-6 | 星仪高亮当前节点与关系，Reader 只提示流式候选并继续只读已晋升正文 | Orrery/Reader binding tests |
| CL-7 | Python、Pi、Vue、Rust、OpenAPI、视觉与桌面构建进入发布矩阵 | `docs/releases/v0.99.4-verification.md` |

确定性最小闭环已覆盖同一产物的 `streaming_preview -> candidate_written -> semantic review -> revision -> mutation receipt -> promoted`，并验证 30,000 字符候选投影。真实 Pi 请求已经抵达配置的 DeepSeek Provider 与 `deepseek-v4-pro` 模型；外部账户返回 `402 Insufficient Balance`，因此该次环境验证只证明真实连接与错误归类，不作为“真实模型完整文学闭环成功”的证据。完整通过项与这一外部阻断均记录在发布验证文档中。
