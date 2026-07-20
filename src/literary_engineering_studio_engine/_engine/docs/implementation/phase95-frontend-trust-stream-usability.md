# Phase 95 - Frontend Trust, Streaming, And Usability

本阶段把本地前端从“能看状态”继续推进为更可信、更亲用户的文学工程驾驶舱。重点不是增加绕过 CLI 的操作能力，而是把已有 CLI/API 产物包装成用户能放心理解和选择的界面。

## 已实现

1. 正文可信度修复
   - `project_library.py` 不再把 `README.md`、`placeholder.md` 等目录说明文件收进正文草稿与已完成正文列表。
   - `completed_prose` 继续只展示已晋升、章节合稿、正式导出和正式发布正文，但排除目录占位说明，避免用户误以为占位文本是作品成果。

2. 真实流式观察
   - `/project/library/stream` 从单次 SSE 快照升级为持续推送。
   - 新增 `interval_seconds` 与 `max_events` 参数；正式前端可持续观察，测试可用 `max_events=1` 安全退出。
   - 前端使用 `EventSource` 连接流式档案；当设置访问口令或 SSE 失败时，自动降级为安全轮询。

3. 版本一致性提示
   - 前端定义 `UI_VERSION`，读取 `/health` 后显示服务版本。
   - 若本地服务进程版本与页面版本不一致，左侧连接状态和流程证据柜会提示用户重启服务，降低“代码已改但页面还是旧服务”的误判。

4. 下一步建议亲用户化
   - Dashboard 不再只平铺前 12 条 `next_actions`。
   - 前端增加“现在先看这里”主行动卡，并按任务、审查、canon、文风、字数预算和流程产物归类展示。
   - 这些归类只解释 dashboard 证据，不替代 `task-next/task-open/task-submit/task-complete/route-audit` 正式链路。

5. 人类选择记录去重
   - 作品档案页的最近决定会按 `decision_type + target + selected` 去重，只展示最近一次有效记录。
   - `style_mount` 等重复选择不再刷屏。

6. 视觉和响应式优化
   - 总控文案改为“下一步该做什么，打开就知道”，作品档案改为“像翻资料夹一样查看作品”。
   - “项目证据柜”更名为“流程证据柜”，“安全标注”更名为“我的备注”。
   - 增加优先行动卡、行动分类卡、版本证据卡样式。
   - 移动端侧栏收紧为紧凑头部，导航横排，避免首屏被导航占满。
   - 增加 `min-width: 0` 与横向溢出兜底，降低长路径撑破布局的风险。

## 仍遵守的边界

- 前端不直接写正式正文、canon、角色状态、发布指针或审查结论。
- 前端安全标注仍只写入 `workflow/ui_overrides.json` 或用户备注层。
- 文风挂载仍记录人类选择证据，并调用正式 readiness gate；不允许 `allow_unreviewed`。
- 所有正式推进仍以 CLI 状态机为准。

## 验证

- `python -m unittest discover -s tests -q`：282 tests passed。
- `python -m literary_engineering_workbench prompt-registry-validate`：pass。
- `git diff --check`：pass。
- 浏览器验证：
  - 新源码服务 `/health` 返回 `0.96.0`。
  - Dashboard 不再把 `drafts/chapters/README.md` 展示为已完成正文。
  - 优先行动分组正常出现。
  - `/project/library/stream?max_events=1` 返回 `event: library`。
  - 桌面和移动端无横向溢出。
