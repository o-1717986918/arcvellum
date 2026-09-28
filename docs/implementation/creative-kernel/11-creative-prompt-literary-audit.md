# 活动创作提示词文学审阅

2026-09-28。本次审阅以 [文学依据](00-literary-basis.md) 为判断框架，核对当前工作台的 22 个可编辑文学层、48 个可编辑正式 Agent 资产及与它们相连的固定结构模板。审阅不把人物、日常、趣味、留白、误导、冲突、节奏做成每场必填清单；每个提示应说明何时使用一种手段、它怎样改变读者的经验，以及事实和视角边界。

## 场景事务文学层

| 层 ID | 本次判断和修改 |
| --- | --- |
| `scene.creator.identity/create/revise` | 重写为工作性作者意图、五类并列工具的精确文学分工、素材文件读取和作者对取舍的责任。首次直接成稿须提供文学理由。修订保留已成立的声音与留白。 |
| `scene.review` | 重写为读者经验审读：人物辨识、日常、信息顺序、可回看的留白、事件说明时机和有效段落的保存。软字数、未用候选和孤立句式不自动退稿。 |
| `scene.performance.plan` | 保留详细人格化初始化。它已经区分稳定性格、内在反差、关系中的口头气质和逐轮压力；这不是文学缺陷。只在主创请求角色时调用。 |
| `scene.actor.identity/turn` | 增强人物的注意方式、误读、改口和可信意外；人格固定身份保留，临场反应留给角色。 |
| `scene.environment.identity/turn` | 明确空间感官与时间气氛的作用，允许平实、丰沛和有意空旷；环境不代人物言行。 |
| `scene.describer.character` | 重写为可见人物特性、习惯与关系距离；不靠外貌清单或性格标签代替呈现。 |
| `scene.describer.event` | 取代物件描写，处理场外事件、设定说明、世界观展开；逐候选标明已确认、转述或待采纳提案及来源边界。 |
| `scene.describer.scene` | 重写为已发生言行的构图、距离、遮挡、视线与观察顺序；不代角色行动。 |
| `scene.description.turn`、`scene.material.selection` | 逐轮按目的、时刻、视角筛选候选；主创只得到候选索引，以文件工具读取并记录采用、改写或舍弃理由。 |
| `advisor.identity`、`advisor.persona.warm-peer/mystery-auditor`、`steward.identity` | 审阅后保留：自然对话、读者线索公平性和选择后果已有明确职责，未发现把情节推进作为唯一价值的指令。 |
| `advisor.persona.chief-editor/dramaturg/cold-reader` | 补入安静场景、日常、可感起因、可回看误导与阅读停留，撤掉“情绪若无决定便有缺陷”的隐含标准。 |
| `project_agent.creative_direction` | 明确作品级审美方向、场间连续性、已确认事实与场景暂定意图的区分；项目 Agent 不代本场主创选镜头。 |

固定协议层逐项查看了权限、占位符、输出形状和事实归属。`scene.describer.event.protocol` 与共用候选 JSON 模板现要求事件候选附 `basis/source_note`；`scene.creator.create.protocol` 显示 `material_skip_reason`；`scene.creator.material-request.protocol` 允许明示为提案的世界观主题。其余固定模板承担结构和事实边界，继续只读。

## 正式任务资产

下表每项列出当前模型可见的正式资产。后缀 `.v1` 为资产身份，不表示本次正文只修订了 v1；各任务硬约束、输出路径和评审合同仍按 Engine 注册元数据执行。

| 路线与资产 | 审阅结论 |
| --- | --- |
| 来源导入（7）：`chunk-extraction`、`extract-project-files`、`extraction-review`、`reconstruct-project`、`resolve-identities`、`review-reconstruction`、`*` | 保留。它们重在证据归属、人物身份歧义和未知项；若把文学解释误写为来源事实反会降低质量。 |
| 人物与世界（5）：`approval-fix`、`create`、`review-fix`、`review.execute`、`*` | 重写 `create`、`review.execute`、`*` 的正文，加入稳定人格、内在反差、关系中的语言幅度、日常生活中世界规则的代价。两个修复任务保留候选局部修改和独立复核职责。 |
| 文风工程（6）：`eval.execute`、`eval.fix`、`prompt.execute`、`review.execute`、`review.fix`、`*` | 保留。生成提示已经要求叙述距离、句法、段落节奏、意象路径、心理和对白机制；盲测、独立审阅与修复都有独立职责。 |
| 长篇规划（10）：`budget-expansion.execute`、`budget-review`、`chapter-obligation-review`、`chapter-obligation.execute`、`reader-experience`、`scene-inventory-review`、`scene-inventory.execute`、`story-architecture.execute`、`story-architecture.review`、`*` | 重写 `budget-expansion.execute`、`budget-review`、`chapter-obligation.execute`、`reader-experience`、`scene-inventory.execute`、`story-architecture.execute`、`*` 的正文。保留其余审阅合同。计划现允许人物辨识、日常时长、细节回声与公平延迟支撑篇幅。 |
| 场景创作（13）：`*`、`branch.execute`、`roleplay.execute`、`branch.selection`、`composition.execute`、`prose.generate`、`agent-review`、`canon-review`、`composition.review.execute`、`revision`、`canon-evolve`、`continuity-ledger`、`state-evolve.execute` | 重写路线正文和角色推演、分支、构图、正文、返修；补强 `agent-review` 与构图审读。Canon、连续性、状态任务保留事实边界。正式分支仍须填写代价及下一场压力，安静场景可用关系或认知后果满足这一合同。 |
| 项目审计（6）：`canon-patch.fix`、`canon-review.execute`、`canon-review.fix`、`committee.execute`、`committee.fix`、`*` | 保留。它们负责精确来源、已提交事实与最终分歧，不替场景主创制造新的文学意图。 |
| 导出交付（1）：`*` | 保留。它过滤工作痕迹，不承担创作或审美扩写。 |

资产短名均以对应 `route.<路线>.` 为前缀；全局工作台显示完整 ID、有效版本和最终组装预览。正式注册共 59 项，其中 11 项为确定性命令或人工关口，不进入模型提示编辑目录。静态层 111 项中 89 项为只读结构。两者在流程树中可展开检查；运行时 SceneBrief、来源、意图和候选由各自数据端口注入，不登记为可编辑静态提示。

## 已知验证边界

程序测试能证明注册、文件权限、输出结构和事实状态的分隔，不能证明某一版提示写出了更好的文学作品。与主创独写、抽象扮演及按需取材方案的同模型盲评仍需真实作品样本；当前不把自动文学评分当作最终证据。
