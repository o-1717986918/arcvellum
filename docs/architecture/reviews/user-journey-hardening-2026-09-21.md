# 用户旅程加固：问题来源与模块变更包

日期：2026-09-21
基线：ArcVellum 0.99.7 Beta，`feat/lean-literary-kernel-v2`

## 结论

本轮体验问题不是单一页面故障，而是四个可独立修复的边界问题：开发入口没有把浏览器、API 与当前 checkout 绑定；长会话列表缺少信息收束；创作现场直接暴露运行时术语；星仪和项目 Agent 的布局没有覆盖中窄窗口。修复应保持既有正式创作状态机、API 协议与投影口径不变。

本轮不会以测试便利为由启用 `LEW_MAINTAINER_MODE`、跳过 TaskPackage、伪造正式产物，或让前端根据文案推断业务状态。

## 已定位的问题来源

### 1. 开发板版本串线

Vite 固定代理到 `127.0.0.1:8791`，而 `npm run client:dev` 不负责验证该端口上的 API 是否来自当前 checkout。实测中，0.99.7 前端连接到了另一份 0.99.6 checkout 启动的 Python 进程，因此“关于”、健康状态、Pi Worker 与路径信息均显示旧版本。

根因位于开发入口的装配层，不在产品 API。仓库已有 `verify_checkout_import.py`，但它只被测试脚本调用，未进入日常启动路径；Vite 的 API 地址也不能按隔离端口配置。

### 2. 项目 Agent 会话与作品选择信息过载

会话栏一次渲染全部历史会话；当可视化夹具或长周期使用积累几十条会话时，主要操作被挤出首屏。新对话对话框只显示作品标题，同名作品无法区分。

根因是项目 Agent 的显示投影缺少“默认窗口”和同名消歧，不是会话存储或作品数据错误。

隔离开发板复测又定位到首次使用断点：浏览器保存的当前作品路径若不属于本次 API 返回的作品目录，Store 不会清空它。界面看起来没有选中作品，但 `projectRoot` 仍为旧路径；用户点击“建立或导入作品”后，项目 Agent 的一致性 watcher 会立即关闭作品库并重开选择弹窗。修复在目录加载时主动清除失效选择及其本地缓存，弹窗继续使用标准组件事件。

### 3. 创作现场把内部运行时直接交给用户

会话标签回退为 `worker`，时间线标题反复使用泛化的“创作现场更新”，失败事件直接显示底层命令错误。用户无法快速回答“谁在做什么、做到哪一步、我该怎么办”。

根因是 Creative Live 的展示适配层没有把已有 typed event、任务与会话字段转换成稳定的人类可读标签。业务事实仍应来自既有投影，前端只做展示映射。

### 4. 星仪与窄窗口缺少安全布局区

约 1050px 宽时，右侧阶段卡与总进度卡占用同一区域；390px 宽时，项目 Agent 固定侧栏挤压主内容且页面不可横向补救。

根因是组件样式只覆盖宽桌面与局部响应式状态，没有为中等宽度定义避让区，也没有把窄窗口导航改为可收起层。

## Module Change Packet A：开发入口一致性

```yaml
module_change_packet:
  objective: "让开发板默认从当前 checkout 的虚拟环境启动，并在浏览器接入前验证源码与版本；允许使用隔离端口避开已有实例。"
  primary_module: "scripts/"
  public_entry: "scripts/start_dev.ps1；npm run dev"
  variation_point: "API 与 Vite 端口通过显式参数和 ARCVELLUM_API_ORIGIN 注入，默认仍为 8791/5173。"
  inputs: "仓库根目录、ApiPort、ClientPort、当前 .venv、package.json 版本。"
  outputs: "当前 checkout 的 API 进程、指向该 API 的 Vite 进程、启动前校验报告。"
  invariants: "不终止占用端口的未知进程；不修改用户配置或凭据；不改变生产 API；失败时不遗留新 API 子进程。"
  allowed_dependencies: "verify_checkout_import.py、verify_version_sync.py、PowerShell、Vite 配置环境变量。"
  forbidden_dependencies: "系统 Python 的隐式包解析、固定指向其他 checkout、自动杀进程。"
  tests: "checkout/version 单元测试；PowerShell 语法检查；隔离端口 health 与版本实测；client build。"
  rollback_unit: "start_dev.ps1、package.json dev script、vite.config.ts 环境端口适配。"
  documentation: "本文件；README 开发启动段。"
```

## Module Change Packet B：项目 Agent 信息收束

```yaml
module_change_packet:
  objective: "让高会话量与同名作品场景仍能快速开始创作。"
  primary_module: "client/src/features/project-agent/"
  public_entry: "AgentThreadRail.vue；NewConversationDialog.vue。"
  variation_point: "默认显示最近会话窗口，用户可展开；作品选项使用已有元数据生成消歧副标题。"
  inputs: "既有 session 列表、works 列表、搜索词与选中状态。"
  outputs: "有界会话列表、可展开入口、可区分的作品选择项。"
  invariants: "不删除或隐藏搜索结果；当前会话始终可达；不修改会话排序、持久化与作品身份。"
  allowed_dependencies: "projectAgentClient DTO、Vue 本地展示状态。"
  forbidden_dependencies: "按夹具名称特判、修改后端会话数据、从标题推断业务状态。"
  tests: "AgentThreadRail 与 NewConversationDialog Vitest；窄窗口组件截图。"
  rollback_unit: "项目 Agent 两个组件及其定向测试。"
  documentation: "本文件与测试记录。"
```

## Module Change Packet C：创作现场展示适配

```yaml
module_change_packet:
  objective: "将已有运行时投影表达为可理解的任务、阶段、结果和恢复建议。"
  primary_module: "client/src/features/creative-live/"
  public_entry: "会话标签与执行时间线展示组件。"
  variation_point: "集中式 presentation helper；未知事件保留稳定兜底。"
  inputs: "Creative Live typed events、session/task metadata、错误文本。"
  outputs: "人类可读标签、去重复阶段标题、对用户安全的失败摘要。"
  invariants: "不改变 typed event schema；不以显示字符串驱动控制流；原始细节仅在明确的详情区域保留。"
  allowed_dependencies: "creativeLiveClient 类型、纯函数展示映射。"
  forbidden_dependencies: "改写状态机、吞掉失败状态、把完整命令或凭据暴露到摘要。"
  tests: "presentation helper 与相关组件 Vitest；真实创作现场观察。"
  rollback_unit: "Creative Live presentation helper、组件及测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet D：星仪与窄窗口布局

```yaml
module_change_packet:
  objective: "消除星仪中宽视口遮挡，并让项目 Agent 在 390px 窗口仍可完成主要操作。"
  primary_module: "client/src/features/orrery/"
  public_entry: "OrreryWorkbench/NarrativeParallaxStage 样式；项目 Agent 外壳的窄屏导航适配作为单独消费端改动。"
  variation_point: "CSS 安全区与分段断点，不改变 Pixi 相机、节点布局或业务交互。"
  inputs: "视口宽高、现有导航展开状态。"
  outputs: "无卡片重叠的中宽星仪；可收起、可恢复的窄屏导航。"
  invariants: "桌面主布局与键盘焦点顺序不回退；不允许主内容横向溢出；不把关键操作永久隐藏。"
  allowed_dependencies: "现有 CSS tokens、组件本地响应式状态。"
  forbidden_dependencies: "用固定坐标掩盖所有分辨率、修改 narrative projection、删除无障碍标签。"
  tests: "相关 Vitest；1050x898 与 390x844 截图；overflow 与 overlap 检查；client build。"
  rollback_unit: "Orrery 样式批次；项目 Agent 窄屏样式批次分别回退。"
  documentation: "本文件与创作测试报告。"
```

## 验收顺序

1. 先用隔离端口启动并证明 UI、API、Worker 均为 0.99.7。
2. 运行定向单元测试与构建，确认投影协议未变。
3. 在桌面、中宽、手机宽度复测基本导航和遮挡。
4. 以一个全新、非敏感的虚构作品执行真实创作请求；按正式工作流观察提问、规划、执行、创作现场与产物回写。
5. 最终记录运行 ID、可见结果、失败恢复路径与仍未解决的风险，不以“页面能打开”代替创作成功。

## Module Change Packet E：交付入口门禁表达

```yaml
module_change_packet:
  objective: "在没有正式正文或投影已报告阻断时，不把交付任务呈现为可立即执行的主操作。"
  primary_module: "client/src/features/delivery/"
  public_entry: "DeliveryView.vue。"
  variation_point: "只消费 delivery.blockers、project progress 与 reader manifest 的既有投影。"
  inputs: "正式正文字符数、可读单元数、交付阻断项、准备中状态。"
  outputs: "可解释的禁用按钮与首要阻断提示。"
  invariants: "后端导出门禁仍是最终权威；前端不伪造 ready；刷新始终可用。"
  allowed_dependencies: "App store 已加载的交付与进度投影。"
  forbidden_dependencies: "根据标题或文件名猜测可交付状态、绕过 export-and-release。"
  tests: "DeliveryView 定向 Vitest；空项目与有阻断项目用户视角复测。"
  rollback_unit: "DeliveryView 及定向样式/测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet F：新建作品规模输入

```yaml
module_change_packet:
  objective: "让界面展示的整万字目标同时满足浏览器原生数值校验。"
  primary_module: "client/src/features/projects/"
  public_entry: "ProjectsView.vue 的 target_length 输入。"
  variation_point: "目标规模的最小值与步进基准。"
  inputs: "用户填写的正整数目标字数。"
  outputs: "可提交的整万字目标与一致的中文标签。"
  invariants: "后端仍负责最终参数校验；不改变默认 30 万字；不替用户自动改写已输入的数字。"
  allowed_dependencies: "HTML number input 原生约束。"
  forbidden_dependencies: "提交前静默取整、绕过表单校验。"
  tests: "ProjectsView 组件断言；真实浏览器以 30000 字提交。"
  rollback_unit: "ProjectsView 目标规模输入属性与定向测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet G：长篇规划结构化返修

```yaml
module_change_packet:
  objective: "在创作决策完整但结构化响应不满足精确数量契约时，允许一次有界、可观测的格式返修。"
  primary_module: "src/literary_engineering_studio/application/lean_longform_planning.py"
  public_entry: "LeanLongformPlanningService.ensure_initial / expand_next_window。"
  variation_point: "应用服务在 Engine 正式校验失败后构造一次定向 repair prompt。"
  inputs: "原始结构化回答、Engine 校验错误、章节与场景精确预算。"
  outputs: "重新校验通过的完整规划，或第二次失败后原样安全停机。"
  invariants: "Engine 的精确数量与字段校验不放宽；不截断、不补写、不静默改动模型的创作选择；最多返修一次；只有通过校验的规划可以落盘。"
  allowed_dependencies: "RoleConversationGateway、normalize_initial_plan、normalize_scene_window、现有事件出口。"
  forbidden_dependencies: "维护者模式、绕过校验、把多余场景直接丢弃、在失败后写入半成品。"
  tests: "初始规划与后续章窗各覆盖一次失败后成功；覆盖返修仍失败且无落盘；既有可恢复性测试。"
  rollback_unit: "规划服务的 bounded repair helper、提示词与定向测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet H：长期目标回执的正式作品证据

```yaml
module_change_packet:
  objective: "阻止 Project Agent 把运行任务数误报为正式正文单元数，并让暂停/恢复回执直接携带权威阅读投影。"
  primary_module: "src/literary_engineering_studio/project_agent/"
  public_entry: "project_goal_manage 工具结果与 Project Agent system prompt。"
  variation_point: "由 composition root 注入只读 reader evidence；动作适配器不自行扫描文件。"
  inputs: "Autopilot run、reader manifest 的 unit_count 与 total_chinese_content_chars。"
  outputs: "goal tool result 中独立的 formal_work 证据，以及禁止混淆 tasks_completed 的提示规则。"
  invariants: "运行计数与正式正文计数保持不同语义；不让 Agent 根据目录或文件名猜测；不改变暂停、恢复和晋升行为。"
  allowed_dependencies: "composition root、现有 read_models.reader 投影、Project Agent 数据型 action adapter。"
  forbidden_dependencies: "在 project_agent 包导入 API router、把 tasks_completed 重命名为正式单元、读取候选稿冒充正式稿。"
  tests: "Project Agent action 定向测试；真实暂停后的 reader manifest 与 Agent 回答对照。"
  rollback_unit: "goal_evidence 注入、formal_work 工具字段与 prompt 约束。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet I：部分正文的交付完整度门禁

```yaml
module_change_packet:
  objective: "已有少量正式正文但全书路线尚未闭环时，不把正式交付主操作显示为可执行。"
  primary_module: "client/src/features/delivery/"
  public_entry: "DeliveryView.vue 与 deliveryReadiness。"
  variation_point: "消费 project-progress 的 integrity checks，而不是用目标字数比例猜测完稿。"
  inputs: "正式正文、reader units、delivery blockers、交付完整度未完成检查数。"
  outputs: "等待作品完成、等待正文、处理 blocker 或允许交付四种明确状态。"
  invariants: "后端 export-and-release 仍是最终权威；不要求正文精确达到目标字数；部分正式正文仍可阅读。"
  allowed_dependencies: "App store 已有 projectProgress.parts 与 delivery projection。"
  forbidden_dependencies: "把目标字数当硬等式、前端伪造 route pass、自动启动导出。"
  tests: "deliveryReadiness 四态定向测试；3/18 场景真实项目页面复测。"
  rollback_unit: "deliveryReadiness helper 与 DeliveryView 参数装配。"
  documentation: "本文件与创作测试报告。"
```

## 第二轮修正方案：编辑型回执与连续性约束

本轮不新增剧情数据库、人物状态机或新的正式写作路线。修正只利用已经存在的
library、reader、plan 与 scene source refs：先让顶层 Agent 能把“故事写到哪里、人物
处境如何、下一步写什么”说清楚，再把用户已经确认的人物、章序和时间事实带进规划与
场景审读。既有正式稿不由补丁静默改写；发现的内容矛盾作为修订输入保留，等待正式
修订路线处理或在新的隔离验收项目中验证。

实施顺序如下：

1. 从现有投影合成一个小型 `story_brief`，不建立第二套事实源。
2. 要求 Project Agent 在里程碑回执中先报告故事、人物、悬念和下一步，再报告运行状态。
3. 收紧长篇规划提示，禁止擅自追加尾声，并要求复用人物表与用户指定章序。
4. 把上一场正式正文加入下一场 source refs，并在生成/审读提示中明确核对姓名、日期和时间差。
5. 以定向测试、全量相关测试和新的用户视角创作轮次验收；旧测试稿只作为缺陷证据，不手改冒充修复结果。

## Module Change Packet J：Project Agent 编辑型故事简报

```yaml
module_change_packet:
  objective: "让顶层 Agent 在创作里程碑中说明故事进展、人物处境、未决线索和下一步，而不只汇报任务计数。"
  primary_module: "src/literary_engineering_studio/project_agent/"
  public_entry: "project_overview 只读工具与 Project Agent system/follow-up prompt。"
  variation_point: "从现有 library 与 reader 投影合成紧凑 story_brief；不持久化新状态。"
  inputs: "library sections、reader manifest、既有 progress 与 route audits。"
  outputs: "formal_units、completed_beats、main_characters、open_threads、next_planned_scene、continuity_status。"
  invariants: "正式正文只以 reader manifest 为准；空 continuity 表示尚未记录而非无问题；默认不泄露超出下一计划场景的未来情节。"
  allowed_dependencies: "project_agent read models、现有 API projection provider、纯函数 helper。"
  forbidden_dependencies: "新增剧情数据库、扫描候选稿冒充正式稿、在 Agent 层修改作品文件、用 tasks_completed 推断故事完成度。"
  tests: "project_agent read-model 与 service prompt 定向测试；真实项目问答复测。"
  rollback_unit: "story_brief helper、overview 字段、prompt 规则及定向测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet K：规划语义护栏

```yaml
module_change_packet:
  objective: "在不增加规划 schema 和校验器复杂度的前提下，减少章序、结局位置、人物名单和时间基准漂移。"
  primary_module: "src/literary_engineering_studio/application/lean_longform_planning.py"
  public_entry: "LeanLongformPlanningService 的初始、窗口扩展与有界返修 prompt。"
  variation_point: "提示上下文补入人物表、世界事实和全书章脊，并声明语义不变量。"
  inputs: "用户 premise/central question/ending choice、registered characters、world facts、chapter spine。"
  outputs: "复用正式人物、遵守用户章序和结局位置、采用一致时间参照的结构化规划。"
  invariants: "Engine 结构校验不放宽；仍最多返修一次；不增加新的持久化字段；模型不得自行追加续集钩子或尾声。"
  allowed_dependencies: "现有 plan JSON、planning state 与 RoleConversationGateway。"
  forbidden_dependencies: "新增规划状态机、自动改名、静默重排用户指定章节、以截断方式修复超额场景。"
  tests: "planning service prompt/context 定向断言及既有规划回归。"
  rollback_unit: "planning prompts 与对应测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet L：上一场正式正文进入证据链

```yaml
module_change_packet:
  objective: "让后一场生成和审读能直接核对上一场正文中的姓名、日期、数字与措辞承诺。"
  primary_module: "src/literary_engineering_studio/infrastructure/project_scene_transactions.py"
  public_entry: "ProjectSceneBriefProvider.prepare 生成的 SceneBrief.source_refs。"
  variation_point: "若存在上一场正式正文，将其项目相对路径加入既有 source refs。"
  inputs: "当前 scene facts、上一场 scene id、drafts/scenes 中的正式文件。"
  outputs: "包含上一场正式正文的可追踪 SceneBrief。"
  invariants: "只引用已存在的项目内相对路径；不改变提交顺序、锁或 revision 计算；首场行为不变。"
  allowed_dependencies: "既有 project structure 与 source-ref normalizer。"
  forbidden_dependencies: "读取候选稿、跨项目绝对路径、复制正文到新存储、绕过 formal commit。"
  tests: "project adapter 首场/后续场 source refs 定向测试。"
  rollback_unit: "previous-scene source ref 与测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet M：场景连续性显式审读

```yaml
module_change_packet:
  objective: "把姓名、日期、时间间隔等硬冲突明确列为必须返修的问题，而不是笼统的文风建议。"
  primary_module: "src/literary_engineering_studio/runtimes/pi_scene_transaction.py"
  public_entry: "render_scene_create_prompt / render_scene_review_prompt。"
  variation_point: "在现有提示行内补充精确事实复用与硬冲突判定，不新增审读阶段。"
  inputs: "SceneBrief source excerpts、candidate prose、现有 critic JSON contract。"
  outputs: "生成时保持事实一致；审读遇到姓名、日期、时间差矛盾时返回 revise。"
  invariants: "JSON contract、重试次数、质量门禁与正式提交协议不变；模块行数不增加。"
  allowed_dependencies: "现有 prompt renderer 与 source evidence。"
  forbidden_dependencies: "新增语言解析器、正则事实数据库、修改 pass 阈值、自动重写正式正文。"
  tests: "Pi runtime prompt 定向断言与既有 runtime 回归。"
  rollback_unit: "两处 prompt 文案与测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet N：文风去流程化护栏

```yaml
module_change_packet:
  objective: "减少连续场景反复采用核对、追问、停顿、留悬念的同构程序感，并补足主角的具体感受与选择代价。"
  primary_module: "src/literary_engineering_studio/runtimes/pi_scene_transaction.py"
  public_entry: "render_scene_create_prompt / render_scene_review_prompt。"
  variation_point: "在既有文学生成与独立审读提示中声明文风差异化要求，不新增算法评分。"
  inputs: "SceneBrief、上一场正式正文 source evidence、candidate prose。"
  outputs: "场景动作组织更有差异；人物情绪通过身体反应、记忆触点、避让与选择显影；审读能指出损害人物辨识度的流程化重复。"
  invariants: "不把偏好升级为机械硬门禁；不要求心理独白；不牺牲清楚、克制与现实主义；runtime 模块行数不增加。"
  allowed_dependencies: "现有 prompt renderer、Relevant Sources 与 reviewer contract。"
  forbidden_dependencies: "新增 AI 味分数、关键词黑名单、自动替换套话、扩展状态机。"
  tests: "Pi runtime prompt 定向断言及既有 runtime 回归。"
  rollback_unit: "生成与审读提示的文风句及测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet O：精确数值复核与软字数降权

```yaml
module_change_packet:
  objective: "修复审读只保留差值却漏掉绝对测量值漂移，并避免软字数提示喧宾夺主。"
  primary_module: "src/literary_engineering_studio/runtimes/pi_scene_transaction.py"
  public_entry: "render_scene_create_prompt / render_scene_review_prompt。"
  variation_point: "提示模型先核对同一对象的绝对值与差值；软字数偏差本身不得成为退回理由。"
  inputs: "上一场正式正文、candidate prose、Length Contract 与 deterministic report。"
  outputs: "同一测量对象的绝对值漂移触发 revise；字数只在造成可举证的人物、情节或阅读损害时随该问题处理。"
  invariants: "不新增数值解析器或硬编码题材知识；不把软字数范围改成机械硬门禁；JSON 审读协议不变。"
  allowed_dependencies: "现有 Relevant Sources、SceneBrief.length 与 reviewer prompt。"
  forbidden_dependencies: "正则事实数据库、自动篡改候选正文、仅凭长度比例无条件退回。"
  tests: "Pi runtime prompt 定向断言及既有 runtime 回归。"
  rollback_unit: "精确数值与软字数降权提示语及测试。"
  documentation: "本文件与第二轮创作测试记录。"
```

## 第三轮收口：约束可见性与审读收敛

第二轮新建作品证明，单靠在通用提示中提醒“保持连续性”仍不够可靠：世界规则虽然
作为来源文件存在，却没有以规则正文进入 `SceneBrief.canon_constraints`；最新用户方向
也没有直接进入场景证据链。多轮返修时，后一次改写因而可能重新引入前一次已经修掉的
数字冲突或新专名。修正仍沿用现有 SceneBrief、source refs 和一次创作/一次审读循环，
不增加事实数据库、解析器、模型调用或新的事务状态。

## Module Change Packet P：正式约束进入 SceneBrief

```yaml
module_change_packet:
  objective: "让世界规则、禁止变更与最新用户方向在每次生成、审读和返修时保持直接可见。"
  primary_module: "src/literary_engineering_studio/infrastructure/project_scene_transactions.py"
  public_entry: "ProjectSceneBriefProvider.prepare 与 known_scene_refs。"
  variation_point: "把既有 YAML 中的规则正文装入 canon_constraints，并把用户方向摘要加入 source_refs。"
  inputs: "canon/world_rules.yaml、canon/forbidden_changes.yaml、workflow/studio/user_directions.md、当前场景与上一场正式正文。"
  outputs: "语义约束正文与可追踪来源分离的 SceneBrief。"
  invariants: "不新增持久化格式；不解析小说正文；base revision 覆盖新增来源；约束文本不得冒充 SceneDelta target_ref。"
  allowed_dependencies: "ruamel.yaml、安全的项目内相对路径、现有 SceneBrief。"
  forbidden_dependencies: "正则事实数据库、跨项目路径、把用户方向复制成第二份状态、手改正式正文。"
  tests: "project adapter 断言规则正文、禁止变更和用户方向来源均进入 brief，且规则文本不进入 known refs。"
  rollback_unit: "constraint loader、direction source ref、known refs 修正及定向测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet Q：返修保持硬约束并收敛

```yaml
module_change_packet:
  objective: "防止后续返修重新引入已修复的事实冲突，并减少审读器不断提出新审美偏好造成的长循环。"
  primary_module: "src/literary_engineering_studio/runtimes/pi_scene_transaction.py"
  public_entry: "render_scene_create_prompt / render_scene_review_prompt / render_scene_revision_prompt。"
  variation_point: "在现有提示中明确 canon_constraints 优先级、新资产登记不等于获准新增、以及审读只处理可证实的实质损害。"
  inputs: "SceneBrief.canon_constraints、Relevant Sources、当前候选、确定性报告和上一轮 revision instructions。"
  outputs: "保留绝对数值与人物限制的修订；通过后不重开无关审美议题。"
  invariants: "不增加模型调用、返修状态、次数上限或 JSON 字段；硬冲突仍必须 revise；轻微风格建议仍可 pass。"
  allowed_dependencies: "现有 prompt renderer 与 reviewer contract。"
  forbidden_dependencies: "新增事实抽取器、按关键词自动改写正文、无限扩张审读维度、用计数上限掩盖未解决问题。"
  tests: "三类 prompt 定向断言与既有 runtime 回归。"
  rollback_unit: "约束优先级与审读收敛提示语及测试。"
  documentation: "本文件与第三轮创作测试记录。"
```

## Module Change Packet R：跨场景禁止项随规划固化

```yaml
module_change_packet:
  objective: "让用户明确的人物白名单、禁用新专名和现实解释等跨场景限制进入既有 world_facts，而非只停留在首轮对话。"
  primary_module: "src/literary_engineering_studio/application/lean_longform_planning.py"
  public_entry: "初始规划与结构返修 prompt。"
  variation_point: "要求规划回答把跨场景硬限制逐条保存在既有 world_facts 数组。"
  inputs: "用户方向、characters 与初始规划回答。"
  outputs: "由既有 materializer 写入 canon/world_rules.yaml 的稳定限制。"
  invariants: "不新增 schema 字段；不把临时文风建议当世界事实；不改变规划数量校验。"
  allowed_dependencies: "现有 world_facts 字段与 materializer。"
  forbidden_dependencies: "新增约束表、重复写入用户方向、静默推断用户未声明的禁令。"
  tests: "initial/repair prompt 定向断言。"
  rollback_unit: "规划提示中的跨场景限制持久化说明与测试。"
  documentation: "本文件与第三轮创作测试记录。"
```

## Module Change Packet S：场景约束层级与审读收敛

```yaml
module_change_packet:
  objective: "阻止审读器在场景转向与章级概括之间来回摇摆，并在已有多轮有效返修后停止追逐孤立文风偏好。"
  primary_module: "src/literary_engineering_studio/runtimes/pi_scene_transaction.py"
  public_entry: "PiSceneTransactionRuntime.review_scene 与 render_scene_review_prompt。"
  variation_point: "从既有 revision cache 推导本场返修轮数，并在提示中声明字段优先级和后期收敛标准。"
  inputs: "SceneBrief、当前场景来源、上一场正文、当前候选、已有 revision_result 文件数。"
  outputs: "场景级 scene_turn/outgoing hook 优先于章级概括；两轮后只有硬冲突、明确义务缺失或可举证阅读损害才能继续 revise。"
  invariants: "不新增数据库字段、事务状态、模型调用或硬次数上限；真正硬冲突在任何轮次都必须 revise。"
  allowed_dependencies: "现有 scene transaction cache 目录与 prompt renderer。"
  forbidden_dependencies: "自动把 revise 改成 pass、按关键词裁决文学质量、隐藏未解决的硬冲突。"
  tests: "review prompt 字段优先级、通用地名与返修轮次收敛断言；既有 runtime 回归。"
  rollback_unit: "revision count 提示与优先级文案。"
  documentation: "本文件与第三轮创作测试记录。"
```

## Module Change Packet T：长期目标启动回执降噪

```yaml
module_change_packet:
  objective: "让顶层 Agent 在启动后台目标后给出短而诚实的交接，不暗示当前回答会持续守候，也不夹带无关的作品库治理建议。"
  primary_module: "src/literary_engineering_studio/project_agent/prompt_policy.py"
  public_entry: "Project Agent system prompt。"
  variation_point: "补充后台目标启动阶段的答复边界。"
  inputs: "project_goal_manage 的 running 状态、当前 project_overview 与用户原始要求。"
  outputs: "当前正式成果、当前路线与自动终态回执说明；无成果时不编造故事情况。"
  invariants: "不改变后台恢复机制与终态 follow-up；不抑制真实阻断和用户请求的比较分析。"
  allowed_dependencies: "现有工具结果与 prompt policy。"
  forbidden_dependencies: "声称继续实时监看、承诺未注册的通知、主动建议归档或淘汰无关作品。"
  tests: "system prompt 定向断言。"
  rollback_unit: "启动回执规则与测试。"
  documentation: "本文件与创作测试报告。"
```

## Module Change Packet U：正式单元检查点

```yaml
module_change_packet:
  objective: "让‘写到第 N 个正式场景后暂停’成为运行策略中的确定性检查点，而不是依赖提示词或外部轮询抢停。"
  primary_module: "src/literary_engineering_studio/automation/ 与 src/literary_engineering_studio/project_agent/"
  public_entry: "project_goal_manage.stop_after_formal_units、DelegationPolicy 与 ClaimedRunLoop。"
  variation_point: "在现有 policy.limits 中保存可选总正式单元上限，并在每个自动步骤开始前检查原子 scene commit 数。"
  inputs: "用户明确的正式单元检查点、workflow/scene_commits 中的正式提交回执。"
  outputs: "达到检查点后 status=paused、stop_reason=goal-scope-complete，后续场景不会开始。"
  invariants: "默认 0 表示不设检查点；不把 tasks_completed 当正式单元；不改变场景提交事务；现有全书目标行为不变。"
  allowed_dependencies: "现有 delegation policy、正式 scene commit 目录与 pause 出口。"
  forbidden_dependencies: "读取候选稿计数、外部轮询抢停、按模型自报场景数、删除超出的正式正文。"
  tests: "policy 规范化、Project Agent goal 参数透传、run loop 达标即停和 Pi 工具 schema。"
  rollback_unit: "stop_after_formal_units 参数、策略字段与 run-loop 检查。"
  documentation: "本文件与第三轮创作测试记录。"
```
