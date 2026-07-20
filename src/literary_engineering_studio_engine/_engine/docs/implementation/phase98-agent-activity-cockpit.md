# Phase 98 - Agent Activity Cockpit

本阶段把 Phase 98 设计落成第一版实现：前端新增“任务推进”一级模块，后端新增只读活动读模型，用真实 CLI 任务事件和 route gate 证据呈现平台 Agent 正在推进什么。

## 已实现

1. 后端活动读模型
   - 新增 `workflow_activity.py`。
   - `build_workflow_activity()` 聚合 `workflow-dashboard`、`workflow/tasks/*.task.json`、`*.submission.json`、`task_events.jsonl` 和 `current-human-choices`。
   - 输出 `active_task`、`route_lanes`、`timeline`、`waiting_choices` 和只读规则。
   - 活跃任务优先级：`blocked > waiting_user > waiting_agent > waiting_gate > issued > next_action > completed > ready`。

2. 只读 API
   - `GET /workflow/activity`：返回当前任务推进驾驶舱快照。
   - `GET /workflow/activity/stream`：以 SSE 持续推送 `activity` 事件；设置访问口令时前端自动降级轮询。
   - `GET /workflow/task-package`：把 task JSON / Markdown 包装成任务包摘要，默认展示目的、必读资料、来源文件、预期产物、禁止捷径和执行命令证据。

3. 前端任务推进页
   - 左侧导航新增“任务推进”。
   - 页面包含当前任务灯塔、正式路线泳道、推进时间线、任务包摘要和等待用户决定节点。
   - 总控页也嵌入小版当前任务灯塔，刷新总控即可看到最重要的活跃任务。

4. 视觉和动效
   - 蓝色表示进行中，朱砂表示阻塞，琥珀表示等待用户决定，绿色表示完成/就绪。
   - `opened` 等等待执行状态有轻量扫描动效；`prefers-reduced-motion` 环境中关闭动效。
   - 任务 ID、路径和命令只作为证据辅助显示，主文案用“场景开发、分支选择、等待验收”等普通中文说明。

## 边界

- 任务推进页是只读 cockpit，不调用 task-complete，不写 completion marker，不晋升候选，不写 canon / characters / drafts / releases。
- 用户在任务推进页做出的选择继续写入 `/workflow/human-choice`，与作品档案页共享同一证据层。
- 前端显示“任务已打开”不等于完成；只有 `task-complete` 或 `route-audit` pass 才是正式完成证明。

## 验证要求

- `python -m unittest discover -s tests -q`
- `python -m literary_engineering_workbench prompt-registry-validate`
- `git diff --check`
- 浏览器检查：
  - `/health` 版本与 `UI_VERSION` 均为 `0.99.0`；
  - 任务推进页能显示当前任务灯塔、路线泳道、推进时间线；
  - `/workflow/activity/stream?max_events=1` 返回 `event: activity`；
  - 移动端导航四项不横向溢出。
