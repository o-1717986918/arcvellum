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

### API / Vue / offline review

- primary_module: API（router）、Vue character-chat（feature client）、tools/prompt-design-desk（分批提交）。
- objective: 提供角色对话入口，并让用户观察、修改、评审新旧文案。
- public_entry: application service / characterChatClient / prompt-design-submission/v2。
- invariants: 来源文字仅作为文字展示，评审页面不自动激活运行链路，用户现有草稿保留。
- tests: API 会话往返与公共健康/SSE；feature client、组件；离线 DOM 与导出。
- rollback_unit: 三模块各自提交。

## 参考资料

两仓库已拉取至当前聊天输出 reference-repositories，作为设计资料阅读，未安装为运行时技能。

- lieflat-less-ai-tone: 27d29232f10124db904ca9c0536d0b67cb3b2833，https://github.com/larashero3-dotcom/lieflat-less-ai-tone
- writing-dna-skill: ee3d97ee27268004b5187d97711161f44fc4aae4，https://github.com/larashero3-dotcom/writing-dna-skill

借鉴 Writing-DNA 的语言、结构、素材选择与认知视角分层；文学作品的文风档案与作者指示提供具体语感。去 AI 味项目用于成稿编辑判断，作者样本决定修辞与句法的使用。本次模板由项目自身编写，采用正向创作引导。

文学依据与项目设计的关系是启发性转化，以下理论并未规定软件中五类分工：

- Woolf《Modern Fiction》对连续感知与日常印象的关注，用于环境的感官选择、注意力流动和余韵。https://www.gutenberg.org/files/64457/64457-h/64457-h.htm#chap16
- James《The Art of Fiction》对人物与事件联系、具体印象的讨论，用于人物可见细节及主创组织。https://public.archive.wsu.edu/campbelld/public_html/amlit/artfiction.html
- Aristotle《Poetics》VIII–XI 对行动整体、因果和认知变化的讨论，用于事件叙述的时间组织与揭示节奏。https://classics.mit.edu/Aristotle/poetics.1.1.html
- Frank《Spatial Form: Some Further Reflections》用于同时存在的空间关系、重复细节与回看效果。https://www.journals.uchicago.edu/doi/10.1086/447989

实施与验证结果在各批提交后补充。
