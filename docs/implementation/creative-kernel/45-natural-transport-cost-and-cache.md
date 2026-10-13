# 自然交付整理与缓存优化 · 2026-10-10

用户授权：实施非思考整理、本地解析、原文引用、局部修复和缓存优化。按用户要求，本批不新增费用、token、调用次数预算机制或新的输出上限。

2026-10-10 实测补包：用户恢复余额并授权实测。Runtime 合同按实际素材角色分化，程序保持完整角色原文与源版本；技术封套先归一，再逐字段校验；引用索引仅投影必要定位信息。修复编辑展示引用标记进入正文替换的问题。涉及入口仍为 NaturalOutputProcessor、MaterialInvocationV2、LessAiToneExperiment；验证原文完整、实际候选准入、角色私人标注、事件来源状态、准备/完成阶段、编辑正文定位及非思考用量。Engine 提示升至版本 3，旧版本保留；旧交易冻结文字保持。

## A：Engine 原文引用与提示资产

primary_module：Engine literary/scene 与 prompting，分开迁移。
public_entry：版本化原文索引/引用解析函数，经 public/literary 导出；scene.v2.transport.extractor。
inputs：完整自然原文、技术引用记录；outputs：逐字重建的既有交付合同。
invariants：原文完整、字符索引明确、来源摘要核对；文学判断来自创作者；旧冻结提示保留。
allowed_dependencies：Engine public/标准库；forbidden_dependencies：Studio、Provider、正式写回。
tests：重复原句、跨段落、Unicode、引用缺失/歧义、历史合同兼容；rollback_unit：引用合同与提示版本。

## B：Studio Runtime 整理流水线

primary_module：Studio runtimes；public_entry：NaturalOutputProcessor、PlanningNaturalDelivery、SceneCreatorV2MaterialCoordinator。
inputs：自然原文、冻结提示及解释上下文；outputs：本地解析/复用/语义整理记录及原文素材。
invariants：先存原文；本地处理明确结构；模型只整理剩余语义；正文和成功字段保持；角色完整回应为主体；私人冲动的接力分区保持。
variation_point：原文定位策略与旧完整复制模式；allowed_dependencies：Engine public 与既有 Gateway；forbidden_dependencies：新模型客户端、正式作品写回、创造文学判断。
tests：十一块卡、素材原文、局部补交、缓存失效/恢复、并发复用、保存证据回放；rollback_unit：Runtime 适配。

## C：角色 Gateway 技术执行身份

primary_module：Studio runtime；public_entry：RoleConversationGateway.run(role=transport)。
inputs：技术整理原文封套；outputs：既有 Pi Worker 的非思考交付与用量事件。
invariants：模型沿用已配置 Runtime，技术角色明确关闭思考；创作和文学审读沿用各自设置；不增加预算机制。
tests：实际 execute 参数、技术角色归类、旧创作设置保持；rollback_unit：Gateway 技术角色。

## D：记录与前端

primary_module：Studio observability / 对应 Vue feature，分批迁移。
public_entry：现有 Scene material/process read models 与 feature client。
outputs：本地处理、结果复用、模型整理与局部修复状态；输入/输出/缓存用量及原文证据。
invariants：只读展示；费用仍标明来源和缺测；旧交易按原快照可查看；不引入预算开关。
tests：记录投影、组件、桌面与移动；rollback_unit：记录与展示。

## C2：既有模型选择入口

primary_module：Studio integrations/pi_worker/control；public_entry：pi_worker_catalog/select_pi_worker_model。
objective：设置页可单独选择技术整理模型；默认继承原审读模型，创作思考设置保持。
inputs：现有角色模型选择；outputs：transport 模型配置；tests：目录与单角色保存、Gateway 继承、设置页构建；rollback_unit：技术角色模型选择。

## 实施与核验

先合同与提示，再 Gateway/Runtime，再前端。当前不新增付费模型请求；使用保存原文回放及真实浏览器完成离线核验。供应商真实命中变化与非思考整理质量须另行付费验证，离线结果不冒充实际节省。

已落实：独立 transport 模型角色及非思考策略；十一块/历史十六块卡、文风选择、简单言行、明确编辑条目的本地解析；带摘要和 Unicode 索引的原文引用；成功字段保留与局部修复；同源并发复用、原始字节和 CRLF 保存；技术失败保留创作原文；全书纲要及成功章节检查点；设置页模型选择及取材页整理记录；技术提示版本 2 与旧稿对照。

核验：完整回归1867项（1项跳过）通过；其后补充字段引用修复的33项定向回归通过。前端8项定向回归、构建通过，桌面1440与手机390真实浏览器均通过，架构及提示资产检查通过。Windows 并发原文文件替换问题已复现并改为同源锁内写入。

106份历史请求离线回放：88份可验证恢复，18份保留待处理；本轮新增付费请求为0。待处理包含旧委托知识分区缺失、人物范围不一致、正文/邀请混合及完整整理结果缺失。回放报告：`work/literary-style-rebuild-20261009/transport-replay-report.json`。非思考整理的真实质量、实际费用变化和供应商缓存命中变化待实测。
