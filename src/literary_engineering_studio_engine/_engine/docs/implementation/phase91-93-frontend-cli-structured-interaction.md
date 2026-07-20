# Phase 91-93：前端-CLI 结构化交互

版本：`v0.91.0`

## 目标

把 Phase 91-93 规划落地为本地前端和 API 能力：前端展示作品内容、包装工程证据、收集关键用户选择；CLI 状态机仍是正式流程权威，平台 Agent 仍是创作与审查主体。

## 新增后端模块

### `display_cleaner.py`

提供前端展示清洗工具：

1. `prose_body_for_display()` 复用最终交付正文清洗规则，过滤 `AGENT_TASK`、状态变化、canon notes、scene id、workflow 痕迹。
2. `markdown_to_display_text()` 把 Markdown 转为普通可读文本。
3. `display_counts()` 同时展示中文内容字数与机器非空白字符，避免把工程信息计入正文。
4. `scalar_from_yaml_text()` / `list_from_yaml_text()` 用于无第三方依赖地读取轻量 YAML 字段。

### `project_library.py`

新增作品档案聚合器：

1. 项目概览：标题、类型、目标长度、简介。
2. 正文草稿：正式草稿、候选正文、修订候选、章节合稿。
3. 人物设定：主要/次要角色、BDI、隐藏背景故事摘要。
4. 世界观设定：canon 和 plot 中适合展示的正式资料。
5. 场景设定：章节、目标字数、参与者、读者问题、承诺回报。
6. 推演分支：branch manifest 包装为分支卡片，显示候选、推荐与已选状态。
7. 文风挂载：活跃 Style Skill 与项目内 style prompt。
8. 审查证据：AgentReview、Style Lint、canon review、longform audit 等摘要。
9. 字数预算：word budget 与章节义务/读者体验契约。

该模块只读，不推进 workflow，不把候选自动视为 canon。

### `project_interaction.py`

新增前端安全交互层：

1. `build_editable_schema()` 返回前端可直接编辑字段和禁止越界边界。
2. `save_display_field()` 只写 `workflow/ui_overrides.json`，用于展示标题、摘要、标签、备注、目标字数提示。
3. `record_ui_note()` 写 `workflow/user_notes/`，作为用户意图备注，不污染 canon、characters 或 drafts。
4. `build_current_human_choices()` 从 workflow dashboard 与 branch manifest 中提取当前等待用户选择的节点。
5. `record_human_choice()` 写 `workflow/human_choices/`。
6. 当 `decision_type=branch_selection` 时，可把用户选择物化为正式 `branches/{scene_id}/branch_selection.md`，但不创建 completion marker，不绕过 `task-submit/task-complete`。

## 新增 API

只读展示：

```text
GET /project/library
GET /project/library/item
GET /project/library/stream
```

安全编辑：

```text
GET /project/editable-schema
PATCH /project/display-field
POST /project/ui-note
```

人类选择：

```text
GET /workflow/current-choice
POST /workflow/human-choice
```

## 前端改动

前端新增一级栏目“作品档案”，与当前项目绑定。

页面结构：

1. 顶部作品封面摘要：项目标题、简介、类型、目标长度。
2. 分类档案目录：正文草稿、人物设定、世界观设定、场景设定、推演分支、文风挂载、审查证据、字数预算。
3. 档案详情：事实卡、指标条、正文/设定正文、分支卡片。
4. 需要你决定的节点：分支选择、审批、扩纲方向等结构化选择。
5. 安全标注：写入 UI 覆盖层和用户备注，不直接改正式项目文件。
6. 可挂载文风：读取文风库中的 Style Skill，用户选择后先写 `human_choice` 证据，再调用正式挂载接口。

页面继续保留“项目总控”“文风挂载”“连接设置”，不恢复旧的 director-chat 主界面。

## 边界

前端可以做：

1. 展示清洗后的正文和项目资料。
2. 包装 JSON/YAML/Markdown 为普通人能读懂的卡片。
3. 保存用户备注、展示摘要、标签和目标字数提示。
4. 记录用户在关键节点的选择。
5. 为分支选择写正式 `branch_selection.md`。
6. 对 ready Style Skill 发起挂载，并保留用户选择证据。

前端不能做：

1. 不写 canon 正式事实。
2. 不覆盖角色背景故事或角色状态。
3. 不晋升正文候选。
4. 不创建 `.agent_completion.json`。
5. 不发布 release。
6. 不替平台 Agent 写正文、审查结论或创意 JSON。

## 测试

新增/扩展 `tests/test_api_server.py`：

1. 验证 `/project/library` 返回作品档案 schema。
2. 验证正文展示体过滤 `scene_id` 和状态变化候选。
3. 验证 `/project/library/item` 可按分类读取档案条目。
4. 验证 `/project/editable-schema` 声明只写 UI 覆盖层。
5. 验证 `/project/display-field` 写入 `workflow/ui_overrides.json`。
6. 验证 `/project/ui-note` 写入 `workflow/user_notes/`。
7. 验证 `/workflow/current-choice` 能发现待分支选择。
8. 验证 `/workflow/human-choice` 能记录选择并物化 `branch_selection.md`。
9. 验证前端包含“作品档案”“需要你决定的节点”“安全标注”，并仍不暴露旧 director-chat 主入口。

## 后续方向

下一步可以继续增强：

1. 让 `workflow-dashboard` 原生汇总 `human_choices` 和 `ui_overrides`。
2. 为 `/project/library/stream` 增加持续 SSE event，而不是当前单次快照流。
3. 增加 stale choice 校验：选择提交时验证 branch manifest hash 未变化。
4. 增加候选化编辑：角色背景、世界观、大纲修改先写 candidate，再进入 asset route。
5. 把 asset/release approval 的前端选择与现有 `/workflow/approve` 进一步合并，减少用户重复确认。
