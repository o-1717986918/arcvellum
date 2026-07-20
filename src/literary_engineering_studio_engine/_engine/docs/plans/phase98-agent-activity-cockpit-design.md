# Phase 98：Agent 任务推进驾驶舱设计

## 目标

把现有前端从“项目状态可视化”继续推进为“平台 Agent 正在如何完善项目”的活动驾驶舱。用户打开页面时，不应只看到一组静态指标，而应能立刻理解：

1. 当前最需要处理的是哪条正式路线；
2. 平台 Agent 正在处理或应该处理哪一个任务；
3. 任务处在领取、打开、执行、提交、验收、阻塞、等待用户选择中的哪一段；
4. 这个任务为什么重要，完成后会把项目推到哪里；
5. 哪些信息只是展示，哪些动作会进入 CLI 状态机证据链。

本阶段不把前端升级成独立创作 Agent，不让前端绕过 `task-next -> task-open -> task-submit -> task-complete`。前端的职责是显示、解释、提醒、记录用户选择；正式推进仍由 CLI 状态机和平台 Agent 完成。

## 当前基础

现有前端已经具备以下能力：

1. `/workflow/dashboard`：聚合 `workflow-state`、`agent-task-status`、七条 `route-audit` 和最近 task events。
2. `/project/library`：把正文、人物、世界观、场景、分支、文风、审查、字数预算、节奏衔接和 canon patch 包装成作品档案。
3. `/project/library/stream`：持续推送作品档案快照。
4. `/workflow/current-choice` 和 `/workflow/human-choice`：把分支选择、资产审批、发布审批、长篇规划方向等用户决策节点结构化。
5. `workflow/events/task_events.jsonl`：已有任务事件流，能作为“推进感”的事实来源。

主要缺口是：前端还没有一个一等模块专门解释“当前活跃任务”。`next_actions` 和 `recent_events` 已经展示，但它们更像报告清单，不像一个正在运行的项目现场。

## 设计原则

### 1. 真实推进，不做假动画

推进感必须来自真实事件和真实门禁：

- 有 `task_issued` 才显示“已领取任务”；
- 有 `task_opened` 才显示“任务包已打开”；
- 有 `task_submitted` 才显示“产物已提交”；
- 有 `task_completed` 才显示“验收通过”；
- 有 `task_blocked` 或 route gate blocking 才显示“卡住”。

不要显示虚构的百分比。正式进度用离散阶段表达，例如：

```text
领取任务 -> 打开任务包 -> Agent 执行 -> 提交产物 -> CLI 验收 -> 路线审计
```

场景开发可显示更细阶段：

```text
Context -> RP -> Branch -> Composition -> Prose -> AgentReview -> Promote -> State/Canon
```

### 2. 高亮标准必须可计算

“当前任务”不能靠前端猜，也不能靠用户手动点亮。建议由后端生成 `workflow_activity` 读模型，基于以下优先级选择活跃项：

1. 最近出现 `task_blocked` 且未修复的任务；
2. 最近 `task_opened` 但还没有 `task_submitted` 或 `task_completed` 的任务；
3. 最近 `task_submitted` 但还没有 `task_completed` 的任务；
4. 最近 `task_issued` 但还没有 `task_opened` 的任务；
5. `workflow-dashboard.next_actions[0]`；
6. 如果全部 ready，则显示“等待下一轮创作方向”。

同一个任务的状态由事件和文件共同决定：

- `issued`：task JSON/Markdown 存在；
- `opened`：事件流出现 opened；
- `submitted`：`workflow/submissions/{task_id}.submission.json` 存在；
- `completed`：相邻 completion marker 或 task-complete 事件存在；
- `blocked`：task-complete 写入 blocked event，或 route-audit 对同一对象有 blocking gate；
- `waiting_user`：`current-choice` 对同一 route/target 产出选择卡；
- `stale`：opened/submitted 后超过建议时间仍无下一事件。

### 3. 前端只展示任务包，不替 Agent 执行任务

任务包可以在前端中被包装展示：

- 当前任务要解决什么；
- 必须读取哪些资料；
- 预期产物是什么；
- 禁止捷径是什么；
- prompt asset 的摘要；
- task-submit / task-complete 命令。

但前端默认不应替平台 Agent 自动点击完成，也不应直接生成任务产物。若未来增加操作按钮，也必须是 CLI wrapper，并写入正式事件和 provenance。

### 4. 用户看到作品语言，Agent 看到任务语言

同一份任务在前端要分成两层：

- 用户层：这一步是在“选剧情分支”“补人物背景”“审查文风”“确认发布”。
- Agent 层：任务 ID、route、source paths、expected outputs、hard constraints。

默认展示用户层；Agent 层放在可展开的“执行包证据”里。

## 视觉方向

采用“编辑部值班台”而不是传统后台仪表盘：

1. 顶部是大号“当前任务灯塔”，只放一个最重要任务。
2. 中部是路线泳道，每条正式 route 一条横向轨道。
3. 右侧或下方是事件时间线，像项目推进日志。
4. 作品正文和设定仍留在“作品档案”，不要把任务页变成文件浏览器。

### 色彩语义

在现有 0.98 前端基础上继续使用克制的编辑色：

- 墨黑：普通文字和结构线；
- 纸白：正文阅读与任务卡底色；
- 深蓝：当前活跃任务和主行动；
- 朱红：阻塞、审查失败、不可发布；
- 琥珀：等待用户选择、需要留意；
- 青绿：验收通过、已完成。

红色只表达风险，不作为主要品牌色大面积使用。当前任务的“活跃感”优先用蓝色边框、轨道光标、状态标签和轻微动效表达。

### 动效策略

动效必须服务状态，不做装饰：

- `opened` 且等待 Agent 输出：任务灯塔边缘缓慢扫描；
- `submitted` 且等待验收：进度轨道显示短暂流动线；
- `blocked`：红色静态角标，不做持续闪烁；
- `completed`：短暂完成动画后归入时间线；
- 支持 `prefers-reduced-motion`，减少或关闭循环动画。

## 信息架构

### 新增一级模块：任务推进

左侧导航建议变为：

```text
项目总控
任务推进
作品档案
文风挂载
```

其中“项目总控”仍是项目健康概览；“任务推进”专门解释当前 Agent 工作现场。

### 任务推进页面布局

```text
┌────────────────────────────────────────────────────────────┐
│ 当前任务灯塔                                                │
│ route / target / stage / waiting_for / suggested_action      │
│ [打开任务包] [查看阻塞] [记录用户选择]                       │
└────────────────────────────────────────────────────────────┘

┌──────────────────────────────┬─────────────────────────────┐
│ 正式路线泳道                  │ 事件时间线                  │
│ scene-development  ━━━●━━      │ task issued                 │
│ longform-planning  ━━━━━━      │ task opened                 │
│ style-engineering  ━━!━━━      │ task submitted              │
│ ...                            │ task blocked                │
└──────────────────────────────┴─────────────────────────────┘

┌──────────────────────────────┬─────────────────────────────┐
│ 任务包摘要                    │ 等待用户决定                │
│ Required reading              │ branch / approval / budget   │
│ Expected outputs              │ structured choices           │
│ Hard constraints              │ rationale textarea           │
└──────────────────────────────┴─────────────────────────────┘
```

### 当前任务灯塔

字段建议：

```json
{
  "active_task": {
    "task_id": "scene-development-scene-0007-branch-selection",
    "route": "scene-development",
    "target": "scene_0007",
    "stage": "waiting_agent",
    "stage_label": "等待平台 Agent 执行任务包",
    "current_step": "branch-selection",
    "waiting_for": "agent",
    "elapsed_seconds": 620,
    "suggested_action": "打开任务包，完成分支选择后提交产物。",
    "task_markdown": "workflow/tasks/...",
    "task_json": "workflow/tasks/...",
    "expected_outputs": [
      "branches/scene_0007/branch_selection.md"
    ],
    "source_paths": [
      "branches/scene_0007/branch_manifest.json"
    ],
    "risk": "normal"
  }
}
```

前端展示为：

- 主标题：`scene_0007 正在等待分支选择`
- 副标题：`这一步会决定下一场正文的剧情路线。`
- 状态：`等待 Agent` / `等待你决定` / `等待验收` / `被门禁阻塞` / `已完成`
- 建议：只用一句普通话解释下一步。

### 路线泳道

每条 route 显示：

- 中文名；
- 当前阶段；
- 阻塞数；
- 待处理 sidecar 数；
- 最近任务目标；
- 是否 waiting_user；
- 是否 stale。

泳道不应只显示数字，而要显示“路线状态句”：

- `场景开发：scene_0007 卡在 AgentReview，不能晋升正文。`
- `文风工程：当前文风已挂载，可以进入正式生成。`
- `导出发布：等待发布审批，尚未写 latest。`

### 事件时间线

事件要按人能懂的方式包装：

- `task_issued` -> `状态机发出了一个新任务`
- `task_opened` -> `平台 Agent 打开了任务包`
- `task_submitted` -> `平台 Agent 提交了产物`
- `task_completed` -> `CLI 验收通过`
- `task_blocked` -> `CLI 拦下了这一步`

每条事件展示：

- 时间；
- route；
- task id 的短名；
- 对象；
- 一句话说明；
- 相关文件折叠显示。

### 任务包摘要

前端不直接暴露完整 JSON。建议分为四块：

1. 这一步要做什么；
2. 需要看的资料；
3. 要交付的东西；
4. 不允许走的捷径。

完整 task JSON / Markdown 可以作为“查看原始证据”折叠项，仅给维护者或 Agent 使用。

## 后端设计

### 新模块：workflow_activity.py

职责：把 dashboard、events、task files、current choices 合并成前端活动读模型。

建议公开函数：

```python
def build_workflow_activity(project_root: Path, *, limit: int = 30) -> dict[str, object]:
    ...
```

输出 schema：

```json
{
  "schema": "literary-engineering-workbench/workflow-activity/v0.1",
  "generated_at": "...",
  "project_root": "...",
  "active_task": {},
  "route_lanes": [],
  "timeline": [],
  "waiting_choices": [],
  "rules": []
}
```

### API

新增：

```text
GET /workflow/activity?project_root=...
GET /workflow/activity/stream?project_root=...&interval_seconds=4&max_events=0
GET /workflow/task-package?project_root=...&task_id=...
```

第一阶段可以只做只读接口；第二阶段再考虑 CLI wrapper：

```text
POST /workflow/task-next
POST /workflow/task-open
POST /workflow/task-submit
POST /workflow/task-complete
```

如果实现 wrapper，必须满足：

1. 调用现有 `task_registry.py` 函数，不重写状态逻辑；
2. 写入与 CLI 一致的 task event；
3. 拒绝 debug waiver；
4. 前端只允许完成当前 task package 中的 expected outputs；
5. 所有错误以 blocking gate 的口径返回。

### 活跃任务推导

建议实现为确定性读模型：

1. 读取 `workflow/events/task_events.jsonl` 最近 200 条；
2. 按 `task_id` 聚合最后状态；
3. 结合 `workflow/tasks/*.task.json` 和 submission 文件；
4. 结合 dashboard 的 `next_actions` 和 route audit；
5. 选择最需要用户注意的 active task。

优先级：

```text
blocked > waiting_user > opened_without_submission > submitted_without_completion > issued_without_opened > first_next_action > ready
```

如果同级多项，选择最近事件时间最新且 route priority 最高的项。route priority 可设为：

```text
scene-development
longform-planning
style-engineering
character-and-world-assets
review-and-audit
export-and-release
source-ingest
```

## 前端实现计划

### Phase 98A：只读活动模型

1. 新增 `workflow_activity.py`。
2. 新增 `/workflow/activity` 和 `/workflow/activity/stream`。
3. 增加 API 测试：
   - 空项目返回 ready/empty；
   - 有 issued event 时 active task 为 issued；
   - 有 opened event 但无 submission 时 active task 为 waiting_agent；
   - 有 blocked event 时优先显示 blocked；
   - current-choice 可把 active task 标成 waiting_user。

### Phase 98B：前端任务推进页

1. `index.html` 增加一级导航“任务推进”。
2. `app.js` 增加 `loadActivity()`、`renderActivity()`、`startActivityObservation()`。
3. `styles.css` 增加：
   - task beacon；
   - route lane；
   - timeline rail；
   - task package summary；
   - waiting choice callout。
4. 总控页也嵌入一个小版当前任务灯塔，让用户不切页也能看到当前活跃任务。

### Phase 98C：任务包查看器

1. 从 active task 的 `task_markdown` / `task_json` 读取任务包。
2. 把 required reading、expected outputs、hard constraints 包装为中文分区。
3. 提供“复制 CLI 命令”按钮。
4. 原始 JSON 只放折叠证据抽屉。

### Phase 98D：安全操作增强

仅在只读体验稳定后考虑：

1. 前端按钮触发 `task-next` / `task-open`，用于生成或打开任务包；
2. `task-submit` 仍要求选择实际产物；
3. `task-complete` 只调用 CLI 原生校验；
4. 任何失败都显示为“门禁拦截”，而不是前端报错。

## 风险与防护

### 风险 1：前端变成第二套状态机

防护：所有 active task、lane、timeline 都来自后端读模型；后端读模型又来自 CLI 产物和 event log。前端不保存自己的进度。

### 风险 2：Agent 把前端状态当成完成证明

防护：界面上明确区分：

- “显示已更新”不是完成；
- “用户已选择”不是完成；
- “任务包已打开”不是完成；
- 只有 `task-complete` 或 route-audit pass 是正式完成。

### 风险 3：推进感诱导批量跳步

防护：不要提供“一键完成全部”。最多提供“打开下一项任务”或“刷新门禁”。批量生成只能由 CLI route 自己决定，并继续逐任务验收。

### 风险 4：用户看不懂 task id

防护：task id 只作为小号证据展示。主文案使用作品语言，例如：

- `选择 scene_0007 的剧情分支`
- `审查本场正文是否可晋升`
- `确认角色候选是否进入人物库`
- `检查导出包是否干净`

## 验收标准

1. 前端能显示当前活跃任务，并说明它为什么重要。
2. 至少能区分 `waiting_agent`、`waiting_user`、`waiting_gate`、`blocked`、`completed`、`ready`。
3. 事件时间线由真实 task events 驱动。
4. 路线泳道覆盖七条正式 route。
5. 任务包摘要不暴露难读 JSON，原始证据可折叠查看。
6. 前端无任何直接写正式正文、canon、角色状态、发布指针的入口。
7. 流式观察可用；设置 token 时自动降级轮询。
8. 移动端仍可读，任务灯塔不挤压正文阅读区。

## 推荐实施顺序

先实现 Phase 98A + 98B。这两步收益最大，风险最低：它们只读，不会改变正式项目文件，却能显著增强“平台 Agent 正在推进项目”的可见性。

Phase 98C 适合紧随其后，因为它会降低 Agent 忘读 task package 的概率。Phase 98D 必须更谨慎，等只读活动模型稳定后再做。
