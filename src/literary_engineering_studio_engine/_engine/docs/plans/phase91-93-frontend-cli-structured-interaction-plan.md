# Phase 91-93：前端-CLI 结构化交互规划

## 目标

把当前前端从“状态展示页”推进为“项目总控 + 作品档案 + 人类选择边界”的结构化工作台。用户仍然主要和平台 Agent 自然对话，平台 Agent 仍然负责创作、审查、推演和修订；前端与 CLI 负责把项目状态、作品内容、关键选择和审批动作变成可见、可查、可验证的正式记录。

本阶段不把前端设计成独立创作 Agent，也不让前端直接绕过 CLI 改写正式链路。核心方向是：

1. 前端展示作品内容时，过滤 Markdown、JSON、路径、sidecar、canon 标记和 workflow 痕迹，用读者能理解的界面包装信息。
2. 前端允许编辑少量低风险的展示字段和用户笔记，涉及 canon、正文、剧情推进、角色状态变化的写入必须走候选、review、approval 或正式 CLI route。
3. 前端在分支选择、文风挂载、候选资产审批、发布审批、章节义务确认等关键节点提供结构化选择控件。
4. 所有人类选择都写成 CLI 可验证的 `human_choice` 或 approval 记录，供平台 Agent 观察、解释和继续推进。

## 当前 CLI 流程理解

项目已经有持续状态机，不需要重造一套工作流。正式执行闭环是：

```text
task-next -> task-open -> 平台 Agent 执行任务 -> task-submit -> task-complete -> workflow-advance / workflow-dashboard
```

CLI 的职责是发任务、提供提示词包、列出必读文件、声明硬约束、收提交、做确定性校验、写 completion marker 和 event log。平台 Agent 的职责是阅读任务包，完成需要判断和创作的部分，例如正文、分支选择、角色推演、AgentReview、文风 prompt、候选资产审查和状态演化解释。

现有 route 已覆盖：

1. `scene-development`：逐场景上下文、RP、分支、编剧态、字数契约、读者体验契约、正文、AgentReview、晋升、静态 review、状态演化。
2. `longform-planning`：长篇字数预算、预算化大纲、场景库存、章节义务。
3. `source-ingest`：已有作品导入后的项目文件反推。
4. `style-engineering`：文风 profile 到可挂载 LLM-facing style prompt 的生成与评测。
5. `character-and-world-assets`：角色、背景故事、世界观、大纲等候选资产的创建、审查、审批和晋升。
6. `review-and-audit`：canon lint、canon review、longform audit、committee review。
7. `export-and-release`：章节工作区、导出包、发布审批、正式发布。

因此前端应当以 `workflow-dashboard`、`workflow-state`、`route-audit`、`agent-task-status`、`workflow-events` 和 task registry 为事实来源。不要维护另一份“前端自己的进度”，否则会重新引入漏审查、跳步骤和状态漂移。

## Phase 91：作品档案与流式展示

### 目标

新增前端一级目录“作品档案”。这里的“新目录”不是新的项目文件夹，而是前端左侧或顶部导航中的一级栏目。它和当前项目绑定，只读取当前项目下的正式文件、候选文件和审查证据。

### 展示内容

作品档案应包含：

1. 项目概览：标题、类型、目标长度、当前章节、当前 route 状态、活跃文风、最近阻塞项。
2. 正文草稿：按卷、章、场景展示已晋升正文和候选正文。默认展示清洗后的正文，不显示 scene id、状态变化、canon notes、AGENT_TASK、review notes、writeback candidate。
3. 人物设定：区分主要角色、次要角色、临时角色和候选角色。每个角色展示公开设定、隐藏背景故事摘要、当前状态、关系、未解决风险。
4. 世界观设定：世界规则、地点、组织、时间线、禁改项、事实依据。
5. 场景设定：场景目标、参与者、冲突、读者问题、承诺回报、目标字数、当前状态。
6. 推演分支：把 `branch_manifest.json`、`branch_selection.md` 和分支报告包装成分支卡片，展示分支标题、代价、风险、推荐理由和已选结果。
7. 文风挂载：当前挂载风格、可用 Style Skill、风格 prompt 质量状态、评测摘要。
8. 审查证据：AgentReview、Style Lint、canon review、longform audit、export manifest 的人类可读摘要。

### 后端建议

新增只读模块：

1. `project_library.py`：扫描项目目录，聚合 characters、canon、plot、drafts、branches、style、reviews、exports。
2. `display_cleaner.py`：把 Markdown、JSON、YAML 转换为前端展示模型，清除工程痕迹。正文清洗应复用 `draft_text.final_body_from_workbench_text()` 与现有 final body 规则。
3. API：
   - `GET /project/library`
   - `GET /project/library/stream`
   - `GET /project/library/item?kind=...&id=...`

### 流式输出

内容展示不需要平台 Agent。所谓流式，应优先理解为项目文件与 workflow event 的增量展示：

1. 轮询或 SSE 推送 `workflow/events/task_events.jsonl` 的新增行。
2. 当前端发现文件更新时间变化，刷新对应作品档案卡片。
3. 大文本正文可以按章节或场景分块加载，避免一次性塞满页面。

这能满足“看到平台 Agent 正在完善项目”的需求，但不会假装前端自己理解或创作作品。

## Phase 92：低风险编辑与用户笔记

### 可行范围

前端可以增加编辑能力，但必须分级。

低风险可直接编辑：

1. UI 展示名、标签、备注、收藏、阅读进度。
2. 场景标题、场景摘要、用户备注。
3. 角色显示名、别名、重要性标签、用户备注。
4. 章节目标字数、场景目标字数、最小/最大容忍区间，但必须触发 route audit 或 word-budget 复核提示。
5. 文风挂载偏好、候选风格备注。

中风险必须生成候选：

1. 角色背景故事、动机、秘密、关系变化。
2. 世界规则、历史事实、组织设定。
3. 场景目标、冲突设计、伏笔、下一场 hook。
4. 大纲、章节库存、情节顺序。

高风险禁止前端直接写正式文件：

1. 正文晋升。
2. canon 正式规则。
3. 角色状态演化正式写回。
4. 发布包与 release latest 指针。
5. workflow task、completion marker、approval record 的手工伪造。

### 后端建议

新增写入模块：

1. `project_editing.py`：白名单字段编辑、原子写入、备份、编辑日志。
2. `human_notes.py`：把用户批注写入 `workflow/user_notes/*.jsonl`，不污染 canon 和正文。
3. API：
   - `GET /project/editable-schema`
   - `PATCH /project/display-field`
   - `POST /project/ui-note`

所有写入必须满足：

1. 只接受项目相对路径或稳定 ID，不接受任意绝对路径。
2. 只允许白名单字段。
3. 写入前验证当前 route 状态，避免改动已经发布的对象。
4. 写入后记录 `actor=user-ui`、时间、原值摘要、新值摘要、影响范围。
5. 对会影响剧情或字数的编辑，自动把对应 route 标记为需要重新 audit，而不是静默生效。

## Phase 93：关键节点人类选择控制

### 基本原则

前端不替平台 Agent 判断文学质量，但可以把必须由用户决定的节点做成清晰的选择卡片。选择卡片的输出必须成为 CLI 可验证证据。

建议新增统一 schema：

```json
{
  "schema": "human_choice.v1",
  "choice_id": "scene_0007.branch-selection.20260719-210000",
  "route": "scene-development",
  "task_id": "scene-development.scene_0007.branch-selection",
  "decision_type": "branch_selection",
  "target": {
    "scene_id": "scene_0007",
    "chapter_id": "chapter_01"
  },
  "options": [
    {
      "id": "branch_a",
      "label": "保守推进",
      "summary": "维持当前人物关系，代价较低。"
    }
  ],
  "selected": "branch_a",
  "rationale": "用户选择优先保证人物行为可信。",
  "actor": "user-ui",
  "status": "submitted",
  "source_paths": [
    "branches/scene_0007/branch_manifest.json"
  ]
}
```

### 分支选择

当前 CLI 已经有 `branch-selection` 状态和 `branch_selection.md` 门禁。前端可以读取分支 manifest，包装为“路线卡”：

1. 分支名称。
2. 主要行动。
3. 人物代价。
4. 世界后果。
5. canon 风险。
6. 对下一场景的 hook。
7. 推荐理由与反对理由。

用户选择后，后端写 `workflow/human_choices/*.json`，再由 CLI 或 helper 物化为正式 `branches/{scene_id}/branch_selection.md`。随后平台 Agent 或前端按钮可以触发 `task-submit` 与 `task-complete`。这样可以保留“用户决定大方向”，又不破坏 branch gate。

### 文风选择

当前 `style-engineering` 已经要求 `style_prompt.md` 达到 500-2500 中文内容 detail chars，并通过评测。前端可以提供：

1. 可挂载风格列表。
2. 每个风格的适用题材、叙述距离、句法节奏、AI 腔限制、评测分数。
3. 当前项目已挂载风格与优先级。
4. 用户选择“挂载、替换、暂不使用、请求平台 Agent 解释差异”。

注意：前端只能选择 ready 风格。未通过 style prompt quality 或 style eval 的风格，应显示为“可查看，不可挂载”。

### 候选资产审批

`character-and-world-assets` 已经有 `asset-approval` 这个 human approval boundary。前端可以直接包装这一节点：

1. 展示候选人物、背景故事、世界规则或大纲摘要。
2. 展示审查结论和风险。
3. 提供“批准晋升、要求修改、拒绝、暂缓”。
4. 使用现有 `/workflow/approve` 写 approval record。

这比让平台 Agent 在对话里口头问“是否批准”更稳，因为审批记录可以被 `promote-candidate-asset` 验证。

### 发布审批

`export-and-release` 已经有 `release-approval`。前端可以展示：

1. 清洗后的正文预览。
2. 导出 manifest 摘要。
3. 跳过场景数量、阻塞项、格式风险。
4. DOCX、MD、剧本、视频提示词包等输出清单。
5. 用户审批按钮。

审批后仍必须由 `publish-chapter` 发布，不允许前端直接复制 latest 指针。

### 字数预算与章节义务选择

长篇项目常见问题不是“句子写短了”，而是“剧情库存不够”。前端可以在 `longform-planning` 中提供：

1. 目标长度、卷数、章数、场景数的仪表盘。
2. 每章目标中文内容字符、当前正文字符、缺口。
3. 场景库存是否足以支撑目标。
4. 平台 Agent 提出的扩展方案，例如新增副线、增加阶段性目标、增加反复试探、扩展地点和社会关系。
5. 用户选择接受哪个扩展方向。

这类选择会影响大纲和场景库存，不能直接改正式 plot。应写为候选方案，之后进入 review 和 approval。

### Review 后修订选择

AgentReview 的 `pass_with_notes`、Style Lint 或静态 review 可能产生多个修订方向。前端可以展示：

1. 问题类型。
2. 影响范围。
3. 轻修、重写、退回分支选择、退回文风调整四类动作。
4. 用户选择倾向。

实际改稿仍由主平台 Agent 完成，subagent 只能做机械检查、清单整理和证据抽取。

### 状态演化确认

`state-evolve` 可能提出角色状态、关系、世界事实变化。前端可以展示“写回候选”：

1. 角色变化。
2. 关系变化。
3. 世界规则变化。
4. 后续剧情影响。
5. 是否显式出现在正文中。

正式写回仍要走 state patch 和 review gate。前端不直接改 `characters/` 或 `canon/` 正式文件。

## 前端-CLI 作为结构化交流通道

远期形态可以分为两条通道：

1. 自然对话通道：用户和平台 Agent 聊创作方向、审美偏好、剧情大判断。
2. 结构化通道：平台 Agent 运行 CLI，CLI 发现需要用户选择，前端显示选择卡，用户点选，CLI 记录，平台 Agent 观察记录并继续。

推荐闭环：

```text
用户提出方向
-> 平台 Agent 运行 task-next / task-open
-> CLI 输出任务包和可能的人类选择需求
-> 前端显示结构化选择卡
-> 用户选择并写入 human_choice / approval
-> 平台 Agent 通过 workflow-events / workflow-dashboard 观察
-> task-submit / task-complete
-> workflow-advance
```

这样做的好处是，用户不需要读 JSON 和 sidecar，平台 Agent 也不能口头声称“用户已同意”。所有关键选择都有来源、时间、任务 ID、影响对象和审计记录。

## 批判性审视

### 这个想法值得做的地方

1. 它把“平台 Agent 容易跳流程”的问题转成了产品设计问题：关键动作必须通过 CLI 状态机和前端选择卡留下证据。
2. 它保留平台 Agent 的自由创作能力，同时把正式产物关进程序化门禁里。
3. 它让用户从“盯着工程目录查漏”解放出来，只看作品、选择、风险和下一步。
4. 它天然适合长篇项目。百万字工程需要持续状态、审计、预算、分支、角色状态和发布记录，不能只靠聊天上下文。
5. 它可以成为 Codex、Claude 等工具层平台的通用 Skill 面板，而不是绑定某个模型 provider。

### 风险

1. 过度结构化会让创作变得笨重。如果每个小选择都弹窗，用户会疲劳，平台 Agent 也会被流程打断。
2. 前端可能形成第二套 workflow。如果前端自己记录状态而 CLI 不认，最后会出现“界面显示完成，route-audit 仍阻塞”。
3. 结构化选项可能过早收窄创作。分支卡片如果只给三条路，平台 Agent 可能停止探索第四条更好的路。
4. 编辑能力很容易越界。让用户在前端改角色背景故事很方便，但如果绕过候选和 review，会破坏 canon。
5. 长篇高并发下会出现 stale choice。用户选择时，底层 branch manifest 或 task_id 可能已经被更新。
6. 前端展示如果清洗过度，可能隐藏重要风险；如果清洗不足，又会把工作流痕迹暴露给普通用户。

### 规避策略

1. 只把阻塞级、高价值、不可由 Agent 自行决定的节点展示给用户。低级技术门禁由 dashboard 显示，不打扰。
2. 所有选择必须绑定 `route`、`task_id`、`source_paths`、`source_hash` 或文件更新时间。源文件变动后旧选择自动失效。
3. 前端不推进 workflow，只写选择和审批；推进仍由 CLI `task-submit/task-complete/workflow-advance` 负责。
4. 选项卡必须允许“都不满意，请平台 Agent 重新推演”。
5. canon、角色背景、世界规则、正文、发布结果只允许候选化修改，不能直接覆盖正式文件。
6. 展示层保留“查看原始证据”的折叠入口，但默认展示包装后的摘要。
7. 对用户选择写 event log，使平台 Agent 的下一步能清楚知道“用户为什么这样选”。

## 实施顺序

### Phase 91.1：只读作品档案后端

1. 实现 `project_library.py`，输出统一 display model。
2. 实现正文清洗、JSON/YAML/Markdown 摘要包装。
3. 增加 `/project/library` 与 `/project/library/item`。
4. 添加测试：正文不含 AGENT_TASK、scene id、state patch、canon notes 等工程痕迹。

### Phase 91.2：流式/增量展示

1. 增加 `/project/library/stream`，先用 SSE 或短轮询实现。
2. 监听 workflow event、dashboard 更新时间和关键文件更新时间。
3. 前端显示“正在生成、等待审查、等待选择、已晋升、需修订”等友好状态。

### Phase 91.3：前端视觉改造

1. 导航收束为：项目总控、作品档案、文风挂载、连接设置。
2. 作品档案采用章节书架、人物谱系、世界设定、分支推演、审查证据五类视图。
3. JSON 不隐藏，而是包装成卡片、表格、时间线、风险标签和正文预览。

### Phase 92.1：安全编辑白名单

1. 实现 editable schema。
2. 支持 UI 备注、标签、显示名、场景摘要、目标字数等低风险字段。
3. 写入 `workflow/user_notes` 和 edit manifest。
4. 对影响字数和规划的编辑提示需要重新跑 route audit。

### Phase 92.2：候选化编辑

1. 对角色背景、世界观、章节大纲等编辑，生成 candidate 而非直接写正式文件。
2. candidate 自动进入 `character-and-world-assets` 或相关 route。
3. 前端显示“待平台 Agent 审查”和“待用户审批”。

### Phase 93.1：Human Choice Registry

1. 增加 `human_choice.v1` schema。
2. 增加 `workflow/human_choices/index.jsonl`。
3. 增加 `/workflow/current-choice`、`/workflow/human-choice`、`/workflow/choices/stream`。
4. `workflow-dashboard` 汇总当前待选择事项。

### Phase 93.2：分支选择 UI

1. 读取 branch manifest。
2. 包装分支卡片。
3. 用户选择后写 human_choice。
4. 后端物化 `branch_selection.md`，再由 `task-submit/task-complete` 验证。

### Phase 93.3：文风选择 UI

1. 展示 ready style prompt 和评测结果。
2. 禁止挂载未通过质量门禁的风格。
3. 记录用户选择理由。
4. 挂载后触发 scene-development 的相关 route audit 提示。

### Phase 93.4：资产和发布审批 UI

1. 把 `asset-approval` 包装为候选设定审批卡。
2. 把 `release-approval` 包装为发布审批卡。
3. 复用现有 `/workflow/approve`，必要时补充 approval summary API。

## 成功标准

1. 用户可以不看 raw JSON，也能理解当前项目在做什么、卡在哪里、下一步需要自己决定什么。
2. 平台 Agent 不能把前端选择口头化。所有选择都有正式记录。
3. 前端不会绕过 CLI route gate。
4. 作品展示不会泄露工程痕迹。
5. 分支选择、文风挂载、候选审批、发布审批至少四类人类节点进入前端-CLI闭环。
6. 长篇项目的字数预算、章节义务和 reader contract 可以被前端看懂，并能引导用户做高层取舍。

## 结论

这个方向可行，而且和项目当前架构高度一致。最关键的设计边界是：前端不是第二个 Agent，也不是第二套 workflow；它是 CLI 状态机的人类操作台。平台 Agent 继续负责自由创作，CLI 继续负责状态和门禁，前端负责把复杂工程证据翻译成用户能看懂、能选择、能留下记录的交互界面。
