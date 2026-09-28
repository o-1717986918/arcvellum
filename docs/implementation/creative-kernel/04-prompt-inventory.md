# 模型可见提示词分层清单

2026-09-28。统一工作台只枚举当前创作路径的 `PromptLayerSpec` 与可进入模型输入的正式 `PromptAsset`。当前共 **111 个静态层**，其中 22 个文学层可编辑、89 个固定结构模板只读；另有 **48 个正式 Agent 提示资产正文**可编辑。工作台全局目录共 159 条，按创作流程的 7 个主枝、22 个步骤组成可展开的树。Engine 原正式资产注册表保留 59 项，其中 11 项属于确定性命令或人工关口，不作为模型提示展示或覆盖。

| 职责与代表 ID | 运行入口及用途 | 来源和编辑边界 |
| --- | --- | --- |
| `scene.creator.identity/create/revise` | 场景主创成稿、修订及按意图取材 | 文学层可按作品／全局编辑；`*.protocol` 固定事实、输出及权限 |
| `scene.review` | 独立审读、留白与阅读损害判断 | 文学层可编辑；证据、冲突、输出合同及返修收敛片段固定 |
| `scene.performance.plan`、`scene.material.selection` | 主创按需取角色或描写素材 | 文学层可编辑；请求与候选合同固定 |
| `scene.actor.identity/turn` | 作品人设支持的人格初始化和续演 | 人格文学指引可编辑；作品人物档案仍由档案模块维护，私念与言行权限固定 |
| `scene.environment.*`、`scene.describer.character/event/scene`、`scene.description.turn` | 环境、人物、场外事件与设定、场面候选 | 各 agent 的身份和逐轮文学层可编辑；初始化作为 system prompt，候选无正式写权，结构协议固定；事件候选标注来源状态 |
| `advisor.identity`、五个 `advisor.persona.*`、`project_agent.creative_direction`、`steward.identity` | 顾问、内置人格、项目总编、自动决策顾问 | 文学职责和内置人格可按作品／全局编辑；自定义人格仍由 Advisor 资产保存；工具、事实与 JSON 权限固定 |
| `formal.asset.*` | 48 个可进入模型的正式任务提示资产正文 | 可按作品／全局编辑 body；原 PromptAsset ID、route、输出合同与硬约束不可编辑；v2/v3 编译消费有效正文 |
| `formal.prompt_program.v3`、`formal.semantic.*`、`formal.prepared-context.*`、`formal.context-access.*`、`formal.prose.*`、`formal.repair.*`、`formal.completion.*` | 正式任务组装、语义合同、上下文、正文预算、返修和完成条件 | 固定只读协议资源；动态任务事实由 Studio 投影填入 |
| `pi.worker.*`、`pi.conversation.system` | Pi Worker 工具权限及无工具会话边界 | 固定只读；注册镜像和 Worker 实际 profile 内容一致 |
| `scene.actor.interaction.protocol` | 当前按需角色取材的逐轮结构 | 固定只读；角色人格化初始化继续由作品人设、身份文学层及沉浸协议组成 |
| `scene.fallbacks.protocol`、作品文风／人物档案 | 无资料占位、已确认事实和作品表达 | 固定占位登记；场景资料由运行时投影注入，文风及档案在原有编辑器维护 |

解析次序是**作品版本→全局版本→随包默认**。协议资源不参与覆盖。场景交易开始时保存层 ID、有效版本、来源和摘要，重启沿用原快照；正式任务在物化时将实际 PromptAsset 正文及版本摘要记录在运行 manifest。工作台显示随包默认与有效正文、用途、状态、历史、预览、激活和撤销覆盖。预览用占位符表示场景和任务资料，只有实际运行才能得到带真实来源的最终 prompt。

`legacy.template.*`、旧自动导演、旧补长、无消费的 JSON 修复层和动态资料说明已从活动注册剥离。旧项目模板编辑入口关闭；旧 Engine 直连 Provider 路径的完整模块删除计划见 [提示词流程树与退役核查](09-prompt-flow-tree-and-retirement.md)。当前活动固定结构在流程树中可逐项展开查看全文；根据数据生成的路径、数值、schema、文件清单仍由对应模块计算。
