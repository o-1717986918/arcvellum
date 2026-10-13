# 43. 文学创作链与文风挂载修复执行记录

目标：执行用户确认的完整计划，重组通用文风、按叙述方式的量化预设、交易冻结与实际加载展示；迁移《星光咖啡馆》的未来规划和角色表达；以 v2＋计量指导＋去 AI 味开展真实验收。

## Module Change Packets

各批先合同与测试，再迁移实现和调用方；每批唯一所有者。

| 批次 / primary_module | public_entry | inputs → outputs | variation_point | tests |
| --- | --- | --- | --- | --- |
| A Engine literary/style 与 prompting | public.literary / public.prompting | 通用文风、语料与文学用途 → 正向文风资产和带来源的候选目录 | 叙述声音与技法 | style/reference/prompt contracts |
| B Studio application/style | StylometryService、StylePresetV1、repository port | 画像与版本 → 预设集合、默认预设、版本化激活 | 画像集合 | presets/service/API/legacy single mount |
| C Studio runtimes | PiSceneTransactionRuntime、NaturalOutputProcessor | 主创预设选择 → TransactionStyleBundleV1、冻结加载、自然交付及前后测量 | 文学选择由主创作出 | selection/read evidence/freeze/resume/tone alignment |
| D Engine planning/composition 与 Studio planning adapter（分别提交） | public.literary planning、LeanLongformPlanningService、replan_lean_future | 作者方向、章节任务 → 自由叙述单元和适配表达投影 | 单元文学形式 | world/no-character/replan/natural transport |
| E Studio application/project direction 与 persona | record/read directions、CreatorPersonaStore | 人类方向、Agent 判断、正文证据 → 来源区别与校正记录 | 意图与连续性分别更新 | provenance/persona digest/full ending regression |
| F Studio observability / API / client（分别迁移） | creative-live projector、feature clients | 实际加载/素材/编辑/测量 → 可查看和编辑的文风、提示词及效果 | UI 展示与任务状态 | API/OpenAPI/components/build/desktop/mobile |
| G Studio project migration | 既有项目/资产/规划公共用例 | 《星光咖啡馆》快照 → 已校正资料、新角色表达、新规划、新交易 | 既定事实与新表达 | committed prefix/hash/audit receipts/new plan binding |
| H acceptance harness | ApplicationContainer、生产 coordinator、RoleConversationGateway | 四类案例与挂载配置 → 两轮文学复测、原文/素材/成本证据 | 当前注册模型 | v2/style/tone required flags/full writeback/literary comparisons |

invariants：角色系统提示原文为十六部分角色卡；创作原文由注册 Runtime 生成；整理器不代写正文；正式 Gate 与写回回执沿用；既有交易冻结；项目端口经 ApplicationContainer 装配；前端经所属 feature client；全部已收到素材及缺测均可追踪。

allowed_dependencies：Engine public、Studio-owned ports、现有 Gateway、现有 stylometric_prompt_lab 集成。
forbidden_dependencies：Studio→Engine internal、Engine→Studio、直连模型客户端、第二套文学状态机、人工伪造模型正文或审读结论。
rollback_unit：分批文件差异及执行前快照；当前工作树已有上一轮改动，保存基线后仅处理本计划所属文件，其他工作不纳入。
documentation：本记录、模块目录/生成模块图、接口合同、实际验收台账。

## 确认的实施偏好

- 改造现有通用文风；保留原 25 段，按需补充可使用且出处明确的文学原文。
- 依叙述方式选择画像；参数可拖动。
- 实际作品校正并重规划未来单元；角色保留经历，重塑表达与特色。
- 文学验收实加载 v2、计量指导与去 AI 味；产品去 AI 味保持可选实验。
- 提示词塑造特性、声音与创作欲望，清理谨慎、克制、边界感与反面兜底的通用措辞。

## 进度

### 已落实

- 通用文风与四组叙述预设已建立，原 25 段全文保留，补充八段有来源的文学原文；画像由分析服务计算，训练与留出来源分别记录。
- 主创开场自主选择预设与完整参照，冻结 TransactionStyleBundleV1；创作、修订、审读和去 AI 味共用文风，编辑前后分别测量。角色初始化仍为角色卡原文。
- 初始、滚动和未来规划采用文学任务与自然交付；无人物表达投影、叙述时间策略、未来章节权重和数量重选已接入。旧交易保留快照，新规划绑定新交易。
- 实际加载接口与前端、预设编辑和参数联动已实现。定向前端测试通过，构建通过；桌面与手机实页验收仍在进行。
- 《星光咖啡馆》备份已完成，四条错误的硬币方向留档并被连续性校正替代；作者方向与 Agent 判断分源。七位人物的新十六区块角色卡及主创人格已通过注册 Runtime 生成并保存，既定经历沿用。

### 验收与剩余

- 架构检查通过。完整回归先前有 9 项失败；对应问题修正后的定向 28 项通过，仍需重跑完整回归。
- 世界开场真实验收的几次运行在人格生成、角色卡整理及网络传输处暴露问题，均保留原文和费用记录。已修正工具标记人格、空角色卡、中文区块标题映射、自由人物肖像主题等问题，并恢复同一交易。尚无可宣称完成的正式文学验收。
- 当前继续实际未来重规划、桌面与手机页面验证、四组连续单元和两轮文学修正复测。实际作品尚未切换新链路，待验收完成。

证据目录：`work/literary-style-rebuild-20261009`；隔离真实交易：用户数据目录下 `acceptance/literary-style-rebuild-20261009`。工程测试通过与文学表现成立分别记录。


## 2026-10-10 离线收束与真实运行阻断

### 本轮追加修复

- 未来重规划支持主创选择单元数量和章节权重，按剩余容量分配，保留已提交前缀与全书字数。未来规划分为全书纲要、逐章展开，成功回复原文可恢复复用。规划输入包含当前作者方向、新角色表达与主创人格，已提交正文、SceneDelta 和回执完整交接。
- 文学叙述策略采用自由的时间、声音与详略组织，消除该模式被旧“摘要低、对白中、人物压力”默认值覆盖的问题；篇幅修复文案发展世界、风俗、时间、群体、情感和人物经验。
- 整理器正确处理可选空工作语境、中文角色卡区块、区块列表和机器拥有的 schema；原文严格复核。技术上下文变化后复用同一原文的有效整理结果，同时重新核对当前角色作用域，避免再次生成整份主创交付。
- 实际素材邀请仍暴露两个主创信息交接问题：私人沙盒笔记被写成档案路径；角色挂载缺少可知／参考标记。提示词及恢复反馈已增加正向填写指引，语义选择留给主创。相关真实失败原文保留，修正后的真实调用尚待复测。
- 主创人格增加实际正文编辑、作者意图来源记录、历史版本对照及带证据的待修订状态。人格的实现偏差修复单独记审查证据，连续性校正仍不触发人格变更。
- 原稿／编辑稿计量记录可识别阶段并展示实际分布、目标和距离。预设选择直接打开滑杆；手动卸载关闭预设集合，重新挂载及参数应用激活所选预设。

### 实际作品状态

《星光咖啡馆》七份新角色卡已保存。主创人格初稿仍有明确的细节与对话偏好，包含“在任何场景里，让人进来、坐下、开始说话”等指令，已按正文证据标记为待修订，原文保留可对照。生成任务已修正，等待模型恢复后完成新人格生成与文学复核。

已提交 `scene_0001` 的正文、正式回执和 SceneDelta 与执行前快照校验值一致。通用文风已刷新至修复后的资产。未来重规划的回复与中断记录已保存，当前尚未落盘新未来规划，尚未创建迁移后的正式新交易，作品级 v2 与去 AI 味覆盖开关保持未启用。

### 验证事实

- 先前完整回归：1848 项通过，1 项跳过。
- 后续完整回归：1850 项中一项旧缓存语义测试失败。该测试原先要求任意上下文变化都重新整理；现已改为验证“非语义变化可复用、角色作用域变化必须重验并拒绝越域”。新增定向 18 项通过；最终完整重跑 1851 项通过，1 项跳过，见 `full-regression-final2.log`。
- 人格／API／节奏／规划／篇幅修复定向 43 项通过；前端相关 22 文件、66 项通过。构建与架构检查通过。
- 预设、参照全文、参数联动、挂载／卸载和人格编辑／历史对照通过实际 API 的桌面、390px 手机页面测试，保留截图与溢出检查。
- 真实隔离运行在准备阶段发现工程问题，随后当前 `deepseek-v4-flash` 明确返回 402 余额不足。已停止真实模型调用；费用以运行器估计注明来源，失败零值标为未报告，按真实 usage_id 去重。

### 尚未完成的原范围

1. 完成主创人格的修订及真实角色声音验证。
2. 完成实际未来重规划并创建绑定新规划的新交易。
3. 四组各两单元的完整创作、五类素材及采用／改写／舍弃追踪。
4. 同原稿去 AI 味对照、不同计量配置独立生成对照及隐藏来源的文学评审。
5. 至少两轮文学问题修正与复测，完成效果与成本证据后切换实际作品到 v2。

工程通过与文学效果成立分别记录，当前计划仍在执行。

### 当前入口与证据

- 当前评审前端：`http://127.0.0.1:5175/ui/`；API：8793。自动审批拒绝终止旧服务（blocked by policy），因此旧 5173／8791 服务保留。
- 真实验收报告：`C:/Users/26532/.literary-engineering-studio/acceptance/literary-style-rebuild-20261009/report.html`。
- 实际前缀与文风刷新：`work/literary-style-rebuild-20261009/style-refresh-final.json`。
- 人格缺陷证据：`work/literary-style-rebuild-20261009/migration/persona-literary-review.json`。
- 保存原文的离线校验：`work/literary-style-rebuild-20261009/offline-real-source-validation.json`。


## 文风参照重算补充合同

primary_module：Studio application/style；public_entry：StylometryService 与预设重算用例。
inputs：作品、预设标识、期望预设修订、该预设当前选定的完整参照。
outputs：真实计算的新画像与参数版本、保持标题／意图／参照／挂载方式的预设新修订。
invariants：旧画像和已开始交易保持冻结；并发修订冲突明示；来源不足显示计算错误；计算过程使用现有 Lab 算法；不发起模型调用。
adapter：stylometry router 与所属 feature client；tests：参照选择、训练／留出声明、版本保留、冲突、前端重算入口。


### 实际画像与参照重算补齐

再次核对实际作品数据，发现四组计量预设此前只在隔离实例创建。现已通过 ApplicationContainer 的文风服务为《星光咖啡馆》实际生成四组初始画像，预设集合修订为 1，各组均保存真实训练／留出声明与参数版本。作品级 v2 和去 AI 味仍未切换，新人格仍待修订。

新增按预设当前选定完整参照重新计算的用例与接口。保留预设名称、文学意图、参照选择、组合和观测方式，只生成新的画像、参数版本与集合修订；旧版本可继续读取。并发修订冲突在计算前拒绝。用户短样段按完整原文合并统计，成员标识和摘要明示；不足的留出来源报错。核验原文的排版重排仅用于测量，引用原文保持不变。

- 应用／API／冻结文风新增定向 11 项通过，覆盖参照选择、旧版本保留、冲突及仅观测／替换的编辑一致性。
- 文风前端 38 项通过，包含计算完成后参数联动及切换作品时拒收旧作品回复。
- 独立临时 API／前端的桌面和手机重算、挂载／卸载页面验收通过；构建、架构和模块图检查通过。
- 为旧开发服务增加能力识别：重新统计按钮只在支持该接口的服务中显示。旧服务保持既有功能；新版服务冷启动后提供重算入口。
- 实际画像证据：`work/literary-style-rebuild-20261009/actual-work-style-presets.json`；重算验收：`reference-recalculation-regression2.log`、`recalculation-ui-e2e2.log`。

本阶段没有发起新的模型调用。完整文学验收和实际未来规划的未完成范围保持原样，继续等待余额恢复或作者指定其他可用模型。


### 阻断审计

模型余额不足已连续三个目标轮次阻断所需的真实生成，当前没有创作／迁移模型进程在运行，也未收到余额恢复或更换模型的消息。可离线的画像、接口、页面和回归补齐已完成；剩余人格修订、实际未来规划、八个文学单元及对照、两轮文学修正与正式切换均需模型可用。目标保留完整原范围，标记为 blocked，等待外部可用性变化。

## 恢复后人格表达复核合同

objective：人格生成直接发展作者指定的文学性情，使宏观讲述与语言展开进入长期初始化。
primary_module：Engine prompting；public_entry：prompt_layer_spec。
variation_point：版本化人格生成资产；inputs：作者方向、作品文风；outputs：自然文字人格。
invariants：角色卡结构与已冻结交易保持原版本，人格历史保留，文学效果由实际原文复核。
allowed_dependencies：prompt_layers 与 layer registry；forbidden_dependencies：模型供应商和正式写回规则。
tests：提示词注册验证与既有人格合同回归；rollback_unit：人格生成资产版本；documentation：本执行记录。

2026-10-10 用户恢复指令后，单次注册 Runtime 连接成功。第二版实际人格已扩大世界／时间／风俗兴趣，但仍出现“抒情但不飘浮”“丰盛而不臃肿”等附加收束。保留其原文与版本，按证据请求修订；生成模板补充正向人格句式示范，再生成复核。

第三版仍有“长句……但……剪短”等预设收束。人格生成进一步采用六段具体肯定句式，集中发展各项志趣。隔离验收的人格缓存另按生成模板摘要与案例种子识别：已有交易沿用原人格，新模板的新隔离实例生成新版本，同条件对照复用同一来源。

primary_module（验收缓存补充）：tests/acceptance；public_entry：ensure_persona；inputs：案例种子与人格模板；outputs：带生成来源摘要的人格缓存；invariants：旧交易人格与旧缓存全文保留，同条件对照来源一致；tests：人格缓存版本识别定向回归；rollback_unit：验收缓存适配。

### 实际纲要复核与规划提示修订

恢复后的实际纲要 `future-migration/b8ecd048ead40f6cb4947469fd47faff710f48d553bf7c6df005d9564c523027.md` 仍写出“越小的东西越要细讲”，第一章四个未来单元继续围绕接客、点单、秘密和空椅子。世界／时间仅作为主题标签，没有发展成独立的阅读阶段。原文保留为问题证据。

primary_module：Engine prompting；public_entry：planning.v2.future；inputs：全书作者方向、已提交前缀、人物表达；outputs：自然交付的全书与单元阅读旅程；invariants：已提交经历、篇幅目标与交易冻结保持，人物现场仍是可选叙述资源；tests：既有未来规划及自然整理回归，实际未来规划细读；rollback_unit：未来规划提示资产新版本。
修订从阅读尺度和文学经验组织单元，发展世界、风俗、思想、情感和长过程的完整篇幅。实际迁移任务明确序章后的森林全景与风俗展开作为下一单元的文学任务。迁移脚本的缓存复用交还给生产 planning_run（其摘要包含系统提示与文风），避免只按任务正文复用旧模板回答。

### 计量对照执行合同

primary_module：tests/acceptance；public_entry：creative_acceptance 的 measurement-config 参数。
inputs：新隔离实例、真实预设画像、人工目标范围；outputs：参数新版本、应用来源及独立生成证据。
invariants：画像统计与来源保持原值，调整项明确为人工创作目标；旧交易冻结不变；两组均开启计量指导和编辑；同参数配置恢复复用，变化要求新实例。
allowed_dependencies：生产 StylometryService 与 DTO；forbidden_dependencies：直接修改画像统计、正式 Gate、模型供应商。
tests：新目标版本、原统计保留、相同配置恢复及变化拒绝。

### 规划自然交付修复合同

primary_module：Studio runtimes；public_entry：future_planning_delivery；inputs：已选纲要与先前章节技术记录；outputs：向创作模型发送的自然排版阅读资料与原样保留的技术记录。
invariants：全部阅读内容保留，chapter_id、数量与后置整理合同保持；技术整理继续使用结构化交付。
allowed_dependencies：规划自然交付；forbidden_dependencies：Gate 与规划事实改写；tests：逐章提示中完整保留纲要、前章与数量，同时以自然阅读格式传递。
依据：恢复后的实际逐章回答开始直接输出 JSON。创作任务携带整份 JSON 纲要及技术字段写法，提供了强烈格式示范。改为自然排版阅读资料，保留技术字段值，在后置整理阶段处理记录格式。

primary_module（规划任务适配）：Studio application/lean_future_replan；public_entry：replan_lean_future；inputs：现有规划、注册角色、用户方向；outputs：自然创作任务与准确的结构错误定位；invariants：参与人物注册校验保持，群体与临时客人作为自然叙述内容进入单元；tests：未来重规划合同与错误定位。
真实生成在四章展开后失败于“未注册参与人物”。原任务却写着“无名路人可用角色称谓”，与正式名单校验冲突。删除该错误引导，正向说明名单与叙述内容各自的填写位置；错误附具体章节、单元和姓名，便于修正。

### 自然取舍的技术编号修复合同

primary_module：Studio runtimes；public_entry：NaturalOutputProcessor 与 repair_material_choice。
inputs：原样保存的已完成自然正文、主创取舍札记、真实候选清单；outputs：原正文与 SceneDelta 保持一致的交付，另一次主创确认的编号取舍记录。
invariants：整理器仍不替主创选择素材；未确认的编号保持 pending、无法成稿；委托挂载编号与 selection-only 交付仍逐字校验；正文／SceneDelta 与各次原文留档。
tests：自然取舍未写编号时定向补交，其他文本改写继续拒绝，取舍补交不改变正文／SceneDelta，旧原文可恢复；rollback_unit：自然编号整理与定向取舍适配。
依据：真实世界开场完成正文后出现 `extraction changed selected material candidate ID`，原因是自然取舍描述已存在，而编号由整理器映射。当前处理重新生成整篇。修复将未核对编号单独交给主创补交，保持正文，正式素材取舍合同继续验证真实候选及文学理由。

同一模块补充：尖锐喜剧案例已保存委托，但首轮必用类别计划未被提取。待处理委托恢复时立即执行，而协调器报“material plan is missing”，导致重复恢复无法推进。增加主创的定向计划补交：仅选择必用类别及文学理由，保留原委托；真实调用校验继续执行。回归覆盖缺计划的已保存委托恢复及空／伪造计划拒绝。

恢复包装的实测补充：真实整理答案使用 operation/task_contract 外层，先解包再进入定向编号修复。原先任意恢复反馈都会再次挂入角色卡填写任务，无人物的世界单元因编号错误也被引导重复写卡。改为已有冻结卡／本段所选角色提供按需上下文；已冻结的人格卡可直接用于后续邀请。卡设计任务按当前缺卡状态加载。

世界原稿 8252 字符已从已有整理结果离线恢复，模型调用为零，原文连续一致。恢复到真实校验后发现另一个纯字段错误：整理器把 `next_handoff` 填成连续性变更的 target_ref。针对这个明确的技术字段名，将其原摘要移回 next_handoff，并保存原技术记录与迁移说明；其他未知档案引用继续拒绝。正文保持原样，未来交接仍由主创原文／整理记录提供。

规划技术格式补充（同 runtimes 模块）：真实自然纲要将相对篇幅写成“36%”，后置记录保留为字符串，数值分配随后失败。仅将明确的百分数字符串转换成等值比例，保留转换位置和原值；生产分配仍核对正数、有限值、总容量与已提交前缀。通过已保存原文和记录复测，避免重写完整纲要。

### 返修投入分类补齐

primary_module：tests/acceptance；public_entry：literary_revisions；inputs：各次真实校验与审读记录；outputs：按修订稿次去重的文学返修数量。
invariants：正式校验、审读判断保持；文风类硬校验引发的改稿计入三次文学返修，纯引号排版等技术修复单列；tests：文风返修与审读返修去重、排版错误单独计数。
首份真实喜剧正文及去 AI 味编辑已完成（采纳五处、保留一处），正式校验仍报告生硬对照及排版问题。旧验收脚本只把模型审读 revise 算文学返修，风格 Gate 引发的改稿被误算为技术返修。按本轮三次文学返修投入上限修正分类，避免再次积累无边界的改稿轮次。

### 2026-10-10 已有成果与开销复核

按作者要求停止新增模型调用，展示已保存的两份代表正文、十次五类素材、三次编辑对照、计量、实际作品人格和候选规划。报告位于 `work/literary-style-rebuild-20261009/current-results-and-cost.html`，每份候选与编辑稿摘要一致，原交易不改写。

用量按 usage_id 跨原台账与运行记录去重，共 391 个事件，383 个报告正用量。旧模型目录估算为 $1.3512；依据本次检索的官方 Flash 闲时价表重估为 $2.4906 / ¥16.6037，账单未核验。技术整理约占 56%，其输出中约 71% 是思考；已确认 medium 在当前 DeepSeek 适配中映射为 high。整理策略、交易累计预算、费用目录和全书规划定向修复尚待处理，没有在本次报告中冒称已修复。

工程收尾沿用前述自然交付模块合同：抽出主创运输准备函数以符合复杂度预算；交接字段定向恢复回归改为验证原正文保留、只发生一次整理且原字段记录可追溯。完整回归 1845 项通过（1 项跳过），架构基线保持。
