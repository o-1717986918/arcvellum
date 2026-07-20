# Phase 99：流式总控、作品档案筛选与人类决策面板

## 目标

补齐前端下一层可用性：项目总控不再只靠轮询；作品档案不仅展示文件，还能搜索、筛选、合并相似条目，并突出影响创作的关键点；人类决策面板继续覆盖 canon 写回审批、修订方向和文风挂载候选。

## 实现

- `GET /workflow/dashboard/stream`：总控 SSE 事件源，前端优先使用 SSE，带 API token 或流中断时降级为轮询。
- `project_library.py`：为每个档案卡补 `key_points`，用于提示平台 Agent 后续创作和审查最该注意的事实、风险和取舍。
- `project_interaction.py`：扩展 `current-human-choices`，新增 canon 写回审批、修订方向和项目内文风候选选择。
- `frontend/index.html` / `frontend/app.js`：作品档案增加搜索、状态筛选、相似条目合并开关，选择详情新增“影响创作的关键点”区域。
- `frontend/styles.css`：桌面端右侧 `.workspace` 改为独立滑动框，左侧 sidebar 保持固定满高；移动端恢复自然页面滚动。

## 边界

所有前端选择仍是 human-choice evidence，不直接写入正式 canon、正文或发布指针。正式推进仍必须通过 CLI route gate、review、approval、apply/promote/export 等链路。

## 验证

- `node --check frontend/app.js`
- `python -m py_compile src/literary_engineering_workbench/project_interaction.py src/literary_engineering_workbench/project_library.py src/literary_engineering_workbench/api_server.py`
- `python -m unittest discover -s tests -p test_api_server.py -v`
