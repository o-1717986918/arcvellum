# 模型可见提示词分层清单

2026-09-27。统一工作台枚举 Engine 的 `PromptLayerSpec` 和原有 `PromptAsset`，按职责与使用状态区分。当前共 **129 个静态层**，其中 24 个允许按作用域编辑；另有 **59 个正式 PromptAsset 正文**允许编辑。工作台全局目录共 188 条：114 条活动静态层、59 条正式任务正文、12 条旧只读路径、2 条旧作品模板及 1 条动态来源说明。旧作品模板仅在选中有效作品时可编辑。

| 职责与代表 ID | 运行入口及用途 | 来源和编辑边界 |
| --- | --- | --- |
| `scene.creator.identity/create/revise` | 场景主创成稿、修订及按意图取材 | 文学层可按作品／全局编辑；`*.protocol` 固定事实、输出及权限 |
| `scene.review` | 独立审读、留白与阅读损害判断 | 文学层可编辑；证据、冲突、输出合同及返修收敛片段固定 |
| `scene.performance.plan`、`scene.material.selection` | 主创按需取角色或描写素材 | 文学层可编辑；请求与候选合同固定 |
| `scene.actor.identity/turn` | 作品人设支持的人格初始化和续演 | 人格文学指引可编辑；作品人物档案仍由档案模块维护，私念与言行权限固定 |
| `scene.environment.*`、`scene.describer.*`、`scene.description.turn` | 环境、人物、事物与场面候选 | 身份与逐轮文学层可编辑；候选无正式写权，结构协议固定 |
| `advisor.identity`、五个 `advisor.persona.*`、`project_agent.creative_direction`、`steward.identity` | 顾问、内置人格、项目总编、自动决策顾问 | 文学职责和内置人格可按作品／全局编辑；自定义人格仍由 Advisor 资产保存；工具、事实与 JSON 权限固定 |
| `formal.asset.*` | 59 个正式任务提示资产正文 | 可按作品／全局编辑 body；原 PromptAsset ID、route、输出合同与硬约束不可编辑；v2/v3 编译消费有效正文 |
| `formal.prompt_program.v3`、`formal.semantic.*`、`formal.prepared-context.*`、`formal.context-access.*`、`formal.prose.*`、`formal.repair.*`、`formal.completion.*` | 正式任务组装、语义合同、上下文、正文预算、返修和完成条件 | 固定只读协议资源；动态任务事实由 Studio 投影填入 |
| `pi.worker.*`、`pi.conversation.system` | Pi Worker 工具权限及无工具会话边界 | 固定只读；注册镜像和 Worker 实际 profile 内容一致 |
| `legacy.template.scene_generation_{system,user}` | 旧项目场景生成 | 作品范围版本化编辑写回作品原模板文件；Engine 旧 PromptPack 读取该文件；无全局覆盖 |
| 其余 `legacy.template.*`、`scene.interaction.direction`、`scene.length.legacy` | 旧直连模板、旧逐轮导演或自动补长 | 目录标记旧路径、只读；不得宣称其版本会影响当前主创交易 |
| `scene.sources`、`scene.fallbacks.protocol`、作品文风／人物档案 | 场景证据、无资料占位、已确认事实和作品表达 | 运行时数据标明来源；固定占位统一登记；文风及档案在原有编辑器维护，工作台提供入口 |

解析次序是**作品版本→全局版本→随包默认**。协议资源不参与覆盖。场景交易开始时保存层 ID、有效版本、来源和摘要，重启沿用原快照；正式任务在物化时将实际 PromptAsset 正文及版本摘要记录在运行 manifest。工作台显示随包默认与有效正文、用途、状态、历史、预览、激活和撤销覆盖。预览用占位符表示场景和任务资料，只有实际运行才能得到带真实来源的最终 prompt。

旧 Engine 直连 Provider 路径不属于 Studio 正式模型执行入口。其 10 个随包模板已在统一目录列出；其中其他旧模块还含拼接式旧提示句段，作为旧模块退役候选记入 `docs/architecture/reviews/full-repository-cleanup-inventory-2026-09-27.md`，不通过当前工作台冒充可编辑活动提示。活动 Studio 场景、项目 Agent、顾问、Steward、正式任务与 Worker 的可复用固定句式按上述层级登记；根据数据生成的路径、数值、schema、文件清单仍由对应模块计算。
