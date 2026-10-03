# 自然创作提示词与独立角色对话

2026-10-03。用户要求保留纯角色卡，其余创作提示词改为正向文学引导、自然文本交付；共享取材权限提示层退出新拼装。运行检查继续由现有程序负责。新链路仍需用户评审及文学场景验收后启用。

## Module Change Packets

### Engine prompting / literary contract

- objective: 四类领域创作者直接用初始化模板作为系统提示词，单一自由文风栏，旧文案可追溯。
- primary_module: Engine prompting（委托字段变化另走 literary public 合同）。
- public_entry: public.prompting / public.literary。
- variation_point: 版本化自然文本拼装，与已冻结旧快照并存。
- inputs: 主创委托、角色卡、文风文字、来源挂载。
- outputs: 版本化提示词、style_direction 委托字段。
- invariants: 角色卡结构、Canon/Gate/正式写回、旧快照。
- allowed_dependencies: Engine 标准库与 literary 合同。
- forbidden_dependencies: Studio/Provider/文件检索。
- tests: 提示词注册、角色卡、文风替换、委托解析。
- rollback_unit: Engine 提示词及合同独立提交。

### Studio runtimes

- objective: 创作自然文本原样留存，后置整理为现有候选、正文、Delta、审读合同。
- primary_module: runtimes。
- public_entry: RoleConversationGateway / SceneCreatorV2Mixin。
- variation_point: response_mode 自然文本版本标记、既有连接 Agent 整理步骤。
- inputs: 冻结提示词/信息包、自然回答。
- outputs: 原文审计文件与校验后的既有 DTO。
- invariants: 必用类别实际调用、每次独立档案冻结、正文逐字提取、旧交易沿用原输出格式。
- allowed_dependencies: Engine public、Studio workspace、既有 gateway。
- forbidden_dependencies: 新模型客户端、整理步骤代写文学正文、修改正式档案。
- tests: 自然响应往返、原文提取、旧交易兼容、文风与系统层拼装。
- rollback_unit: Runtime 独立提交。

### Character chat application

- objective: 用户以独立上下文与带角色卡和已知事实的角色对话。
- primary_module: application。
- public_entry: CharacterChatService / CharacterConversationPort，由 ApplicationContainer 装配。
- variation_point: 文件会话 repository、既有角色 runtime adapter。
- inputs: 作品、人物、完整角色卡、已知档案选取、会话消息。
- outputs: 独立会话、冻结来源、自然回答。
- invariants: 会话目录与主创交易分离、正式档案只读、角色系统模板一致。
- tests: 会话隔离、越界路径、事实冻结、恢复历史、失败不污染已完成消息。
- rollback_unit: 应用及替换 port 独立提交，API/Vue 各自随后迁移。

### Character chat persistence adapter

- primary_module: persistence。
- objective: 独立保存角色对话与读取主创角色卡快照。
- public_entry: CharacterChatRepositoryPort。
- variation_point: FileCharacterChatRepository。
- inputs / outputs: 作品标识、UUID 会话与冻结卡/资料/历史。
- invariants: 主创交易目录和正式作品档案独立。
- allowed_dependencies: 标准库、稳定作品标识。
- forbidden_dependencies: 模型调用、正式作品修改。
- tests: test_character_chat.py 的会话恢复和隔离。
- rollback_unit: 文件 adapter 独立提交。

### Character chat infrastructure composition

- primary_module: infrastructure。
- objective: 将既有角色 runtime、只读档案和独立存储经 ports 装配。
- public_entry: build_default_application_ports / ApplicationContainer。
- variation_point: CharacterChatRuntimeAdapter / CharacterChatArchiveAdapter。
- inputs / outputs: port DTO、自然回答、档案快照。
- invariants: 既有 Agent 连接、独立 data root 目录。
- allowed_dependencies: application ports、现有 runtime / persistence。
- forbidden_dependencies: 第二组合根、新模型客户端。
- tests: application container、character chat API。
- rollback_unit: adapter 和默认装配独立提交。

### Character chat API

- primary_module: API。
- objective: 提供独立对话、填卡和档案选择接口。
- public_entry: CharacterChatService / router factory。
- variation_point: none。
- inputs / outputs: HTTP 请求与 service DTO。
- invariants: 用例由 application service 执行。
- allowed_dependencies: application service、API transport。
- forbidden_dependencies: 直接修改作品、直接访问 Engine internal。
- tests: 新建真实作品后的健康、作品列表、runtime、read-model、SSE 与对话往返。
- rollback_unit: router、OpenAPI 与生成类型独立提交。

### Character chat Vue feature

- primary_module: Vue character-chat。
- objective: 从作品档案室选择人物、挂载已知资料、加载单独场景并交谈。
- public_entry: characterChatClient。
- variation_point: injectable feature transport。
- inputs / outputs: typed feature DTO、页面事件。
- invariants: 作品切换时重新创建页面，来源和回答按文字展示。
- allowed_dependencies: 自有 feature client、共享 app store、router。
- forbidden_dependencies: 组件直接调用 generic transport、跨 feature 组件调用。
- tests: client 合同、组件、全量客户端与构建；视觉验收尚待完成。
- rollback_unit: feature、路由和档案室入口独立提交。

### Offline prompt review

- primary_module: tools/prompt-design-desk。
- objective: 观察、修改、评审新旧文案并导出装载资料。
- public_entry: build_snapshot.py / prompt-design-submission/v2。
- variation_point: 内置及历史来源快照。
- inputs / outputs: 注册文案、用户填写 / 自包含 HTML、JSON、ZIP。
- invariants: 来源仅作文字展示，已有草稿保留，运行开关由项目配置控制。
- allowed_dependencies: Engine public.prompting、标准库。
- forbidden_dependencies: 正式作品写入、自动启用运行链路。
- tests: DOM、来源保真、采用/组合/通过/撤销、导入导出。
- rollback_unit: 离线工具及来源快照独立提交。

### Application prompt workbench migration packet

- primary_module: application prompt_workbench / prompt_flow。
- objective: 注册后置整理的流程位置，区分新版候选和退出拼装的历史位。
- public_entry: PromptWorkbenchService.catalog。
- variation_point: 单一流程映射及 usage_status。
- invariants: 全部来源可查看，旧编辑和预览行为继续可用。
- tests: PromptWorkbenchTests 与 public API 快照。
- rollback_unit: 工作台目录修正独立提交。

### Project Agent prompt migration packet

- primary_module: project_agent。
- objective: 新版作品总管使用正向交流文案，现有总管默认继续其原版本。
- public_entry: prompt_policy / ProjectAgentService 的 turn request。
- variation_point: scene_creator_v2 opt-in 选择独立 project_agent.v2.* 位。
- invariants: 现有工具、长期目标检查点、回执与暂停语义；未启用配置保持不变。
- tests: prompt policy、检查点/终态目标测试、默认旧文案与新位选择。
- rollback_unit: 独立顶层提示词与调用方提交。

## 参考资料

两仓库已拉取至当前聊天输出 reference-repositories，作为设计资料阅读，未安装为运行时技能。

- lieflat-less-ai-tone: 27d29232f10124db904ca9c0536d0b67cb3b2833，https://github.com/larashero3-dotcom/lieflat-less-ai-tone
- writing-dna-skill: ee3d97ee27268004b5187d97711161f44fc4aae4，https://github.com/larashero3-dotcom/writing-dna-skill

借鉴 Writing-DNA 的语言、结构、素材选择与认知视角分层；文学作品的文风档案与作者指示提供具体语感。去 AI 味项目用于成稿编辑判断，作者样本决定修辞与句法的使用。本次模板由项目自身编写，采用正向创作引导。

文学依据与项目设计的关系是启发性转化，以下理论并未规定软件中五类分工：

- Woolf《Modern Fiction》对连续感知与日常印象的关注，用于环境的感官选择、注意力流动和余韵。[原文](https://www.gutenberg.org/files/64457/64457-h/64457-h.htm)
- James《The Art of Fiction》对人物与事件联系、具体印象的讨论，用于人物可见细节及主创组织。[原文](https://people.bu.edu/rcarney/newsevents/hj2.shtml)
- Aristotle《Poetics》VIII–XI 对行动整体、因果和认知变化的讨论，用于事件叙述的时间组织与揭示节奏。[原文](https://classics.mit.edu/Aristotle/poetics.1.1.html)
- Lessing《Laocoon》XVI 对语言展开连续行动的讨论，用于移动视线、物件变化与场面空间的经验。[原文](https://www.gutenberg.org/files/73078/73078-h/73078-h.htm)

## 实施状态

- 角色系统卡保持十六区块的纯结构版本。四类领域身份直接加载为系统提示词，共同事实/权限和 JSON 候选提示层退出新快照。
- 创作、取材、填卡与审读先返回自然文字，再经已安装的角色 runtime 整理为既有合同。原文在整理前保存；正文、候选和新角色卡区块检查逐字提取，已冻结角色卡可原样复用。
- 主创接收完整挂载文风与自由作者指示，审读接收当场创作记忆。四类委托的 style_direction 填入各自唯一文风栏。
- 新顶层六位使用独立 project_agent.v2.* ID，随新版 opt-in 选择。旧位、旧覆盖、未完成交易和旧请求摘要保持兼容。
- CharacterChatService 经 container/ports 装配独立存储和现有角色 runtime。角色卡、已知档案快照、场景与历史按独立 session 保存。前端由 characterChatClient 调用，从档案室进入。
- 离线评审台展示 33 位、97 份来源；25 位当前设计，8 位历史稿。已有浏览器草稿保留，来源全文可查看、编辑、采用、通过与导出。此次重写前的版本号、来源提交及内容摘要均留档。
- 档案初始化、Canon/Gate、场景正文与 SceneDelta 正式写回沿用现有工程。新功能存放于 Studio data root。

默认运行开关保持关闭。真实模型文学场景对照尚待执行。浏览器工具拒绝本地页面访问；桌面/手机截图及实际渲染验收尚未完成。

## 验证记录

- 完整 Python 回归：1692 项，OK，1 项既有跳过。提示词重构与独立对话的定向测试同时通过；顶层模板修改装载另复验 75 项。
- Client：78 文件 / 250 项通过；生产构建及桌面资源同步通过。
- Pi Worker：13 文件 / 121 项通过；check 通过。
- 离线评审：2 项来源快照测试及完整 DOM 行为测试通过，产物已重新构建。
- 架构审计：16 个原有文件债务、76 个原有函数债务，0 循环，0 Studio 内部 Engine import；模块图、OpenAPI、注册表、compileall 与 diff 检查通过。
- 新建作品验证健康、作品列表、runtime adapters、project workspace 和 SSE；独立角色事实冻结、对话恢复、失败消息处理及主创历史隔离通过。模型回答使用注入的测试端口，真实模型文学效果留待场景验收。
- load_config 的实际新版开关判定为 false；两参考仓库的 commit 已核对。
