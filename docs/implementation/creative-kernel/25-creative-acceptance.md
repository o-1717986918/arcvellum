# 创作链路集中验收

2026-10-07。执行用户确认的四类强风格、连续场景与局部编辑对照计划。以文学特色为首要判断，分批记录成本。

## Module Change Packet：主创与编辑文风一致性

- objective: 主创和实验去 AI 味编辑使用同一交易冻结的文风。
- primary_module: Studio runtimes。
- public_entry: PiSceneTransactionRuntime.create_scene / revise_scene。
- variation_point: 既有 creator style snapshot 与实验编辑 mount。
- inputs: 作者指示、正式文风、计量挂载快照、旧交易 mount。
- outputs: 编辑的冻结文风文本及来源版本。
- invariants: append/replace/observe 语义、旧交易冻结、实验默认关闭、独立审读、SceneDelta 原文证据。
- allowed_dependencies: 既有 runtime mixins、Engine public、style snapshot port。
- forbidden_dependencies: 新模型客户端、直接正式写回、改 Gate、覆盖旧冻结内容。
- tests: 三种挂载语义、作者指示、编辑与主创一致、恢复与切换版本、旧 mount 兼容。
- rollback_unit: 本项 runtime 与测试的独立提交。
- documentation: 本文件。

## 本批交付与复跑

细读结论见 [验收结果](26-creative-acceptance-results.md)。本地 `build/creative-acceptance-20261007/report.html` 包含正文、编辑对照与可导出的用户阅读意见；`evidence-index.json` 汇总素材委托、挂载摘要、取舍、失败和成本。原始模型产物位于隔离实例的数据目录，未写入用户作品。

```powershell
$env:PYTHONPATH='src'
# 只重建报告，不调用模型
& .venv/Scripts/python.exe scripts/creative_acceptance.py daily --config work/dev-runtime/less-ai-tone-experiment.config.json --output build/creative-acceptance-20261007 --action report
# 连接恢复后，使用原案例与变体继续；这是显式的真实模型调用
& .venv/Scripts/python.exe scripts/creative_acceptance.py conflict --config work/dev-runtime/less-ai-tone-experiment.config.json --output build/creative-acceptance-20261007 --variant invitations --max-calls 80 --max-minutes 45 --max-revisions 3 --confirm-live-model
```

批次限额在调用前检查。一个进行中的主创调用可能包含多个 Provider 请求，费用和时间以实际回执记录；正式 Gate 继续决定稿件状态。进程锁阻止同一案例变体并发写入。已有 frozen snapshot 在恢复时保持；测试新模板须创建新的变体与交易。

验收前端测试读取 `ARCVELLUM_CHARACTER_ACCEPTANCE_ROOT` 指定的隔离作品；角色恢复和提示词评审测试不调用模型。`ARCVELLUM_CREATIVE_REPORT` 指向本地报告，可检查交换版本、揭示来源及导出。未设置这两个环境变量时相应 opt-in 测试跳过，常规测试不会产生模型消费。

```yaml
delivery:
  module: Studio runtimes, Pi Worker, character-chat/settings clients, acceptance tools
  public_contract: 既有场景协调器、角色 Gateway、feature clients；附加不透明用量身份和档案读取回执
  behavior: 冻结文风一致、自然原文可恢复、完整审读可复核、独立对话作用域稳定、新旧提示词可查看与评审
  adapters_changed: [natural-output, literary-role-gateway, pi-worker-event, pi-worker-conversation, character-chat-panel, prompt-workbench]
  gates_preserved: [正式审读, SceneDelta 验证, Canon 和状态晋升, 旧交易冻结]
  tests_passed: [runtime 63, application-role-acceptance 18, client 272, worker 124, architecture-and-module-direction 10, prompt-registry, frontend-build]
  architecture:
    forbidden_dependencies: 0
    import_cycles: 0
    debt_delta: 0
  e2e_evidence: build/creative-acceptance-20261007; build/orrery-visual/results; work/dev-runtime/creative-*.log
  rollback_commit: 分层独立提交，见版本历史及提示词差异
  remaining_risk: [四类连续两场未完成, 素材物件连贯性, 角色代写对话者, 计量收益未建立, 实验编辑完整链路未完成, 网络阻断, 两条费用缺测]
```

## Module Change Packet：调用费用的执行身份

- objective: 同一提示词的真实重试被记录为新消费；事件重播保持去重。
- primary_module: workers/pi-worker。
- public_entry: usage.updated 的不透明 usage_id。
- variation_point: 一次 WorkerEventAdapter 执行的身份。
- inputs: 同提示同 session 的不同实际进程、消息索引。
- outputs: 带本次执行 UUID 的 usage_id；session_id 与字段合同保持原样。
- invariants: 一次执行内同事件身份稳定、不同执行身份唯一、原 token/cost 数值保留。
- allowed_dependencies: node:crypto、现有 event adapter。
- forbidden_dependencies: 新价格客户端、推测账单、修改 Provider 调用行为。
- tests: 同 session 两次执行的 usage_id 不同、既有 worker suite、验收台账重复事件与付费重试对照。
- rollback_unit: Worker 事件身份独立提交。
- documentation: 本文件。

## 实测中的新增修复面

网络中断留下部分回答时，Worker 原消息仍称“conversation completed”且 validationPassed 为真。本项归 Worker conversation 结果装配与 Studio runtime Gateway：完成状态以全文返回且无 Provider 错误为依据；保留部分原文、失败类型、可重试属性及原运行目录。前端沿用原错误合同，展示明确的中文原因、下一步及原始诊断。验收台账读取既有失败元数据，不重试模型、不猜测未知失败。通过部分回答中断回归及角色 Gateway 回归验证。

真实工具日志显示 32 次成功工具调用就触发 64 次限额：事件适配与场景工具钩子各加一次计数。此项归 workers/pi-worker 的 conversation adapter：计数由工具开始事件唯一拥有，工具钩子读取配置限额，保留原权限和路径校验；验证每次只计一次，既有工具合同继续通过。

自然委托已出现引号、例句列表及知识区别名等表示差异。仅恢复来源明确、文字相同的原文；改写词语、缺失内容与歧义继续拒绝。完整且有界的四类非事件回应可直接入素材库；演员需有可定位的第一人称动作片段，事件仍整理并核验来源状态。技术错误优先用保存的同源提取重验。

SceneDelta 交接被误填为变更目标时，先调用 Engine 的原验证器核对后置记录，再重提取同一正文。原始审读信按被审正文摘要保存并进入修订上下文，避免完整阅读问题被缩为几个标签。

三次文学返修预算按独立审读触发的修订计数；确定性技术校验返修另记，并有六次停止限额。此前简单按总 revision_attempts 停止的验收记录保持可见，重新计算其文学与技术轮次。正式 Gate 和原始失败证据保持。

## Module Change Packet：独立角色对话上下文

- objective: 用户看清所选资料的来源状态与自己在对话中的身份；换作品后旧回复保持在原作品。
- primary_module: client/character-chat。
- public_entry: characterChatClient、CharacterChatPanel。
- variation_point: 作品作用域与异步回复。
- inputs: 切换作品、延迟请求、角色卡、档案状态、用户上下文。
- outputs: 当前作品的角色与对话、来源标签、身份与时点填写引导。
- invariants: 角色卡结构与系统提示词保留；通过 feature client；在途模型仍记录于原会话；新作品不采用旧返回。
- allowed_dependencies: Vue、既有 feature client 与合同。
- forbidden_dependencies: 新提示词边界层、改角色系统结构、修改主创历史。
- tests: 跨作品迟到回复、已有对话合同、桌面/手机截图与溢出检查。
- rollback_unit: 前端状态修正与相关测试独立提交。
- documentation: 本文件及验收报告。

## Module Change Packet：提示词目录加载中的搜索

- objective: 目录尚在加载时输入的搜索，在资料返回后展开匹配叶子。
- primary_module: client/settings 的 PromptWorkbench。
- public_entry: settingsClient.promptCatalog 与既有筛选控件。
- variation_point: 过滤树更新时的展开行为。
- inputs: 延迟目录、切换作品范围、已输入的提示词 ID。
- outputs: 匹配项可见、仍按原范围保存及恢复版本。
- invariants: 固定层只读；旧提示词可查；冻结交易语义与编辑范围保持。
- allowed_dependencies: Vue 与 settings feature client。
- forbidden_dependencies: 修改交易、引入通用 transport 调用、改目录 API。
- tests: 延迟目录与先输入搜索的回归；实际新旧提示词查看、修改、组装与恢复；桌面及手机检查。
- rollback_unit: 搜索展开与测试独立提交。
- documentation: 本文件及验收报告。

## Module Change Packet：验收入口与证据

- objective: 四类两场案例可分批运行、恢复，成本与文学产物可追溯。
- primary_module: tests/acceptance（验收支持，CLI 位于 scripts）。
- public_entry: 显式 opt-in 的 creative acceptance CLI。
- variation_point: 案例、计量挂载、局部编辑和提示词快照。
- inputs: 现有配置、隔离作品、案例、阶段与预算。
- outputs: arcvellum/creative-acceptance/v1 报告、调用台账、原始产物与可读对照。
- invariants: 复用 ApplicationContainer、正式场景协调器及角色 Gateway；正文由实际主创产生；人工 Gate 保留；缓存不冒充新消费；费用缺失明示。
- allowed_dependencies: Studio 应用入口、既有 runtime composition、Engine public、标准库。
- forbidden_dependencies: 新 Provider 客户端、合成通过、隐含模型切换、测试产物写入用户作品。
- tests: 四类案例合同、usage_id 去重、缺失费用、预算停止、恢复、报告转义与路径、真实 opt-in 流程。
- rollback_unit: 验收入口、报告与定向测试的独立提交。
- documentation: 本文件与验收报告。

## 执行约定

实测的 work_archive 工具事件只记录工具名，缺少实际读取的条目与版本，无法复核“主创看过哪些资料”。修复面为 Worker 场景档案工具与事件适配：成功读取附条目、行段、分页范围、完整性、文件和返回片段摘要，列出／搜索保留动作；正文内容保持在原工具返回中。只投影该工具的明确字段，不扩展权限或产品 API。通过真实文件分段工具回归与事件投影回归验证。旧记录的条目级阅读证据仍标缺失。

每批最多推进两个场景交易，单场最多三次文学返修。预算停留是测试状态，不改变正式 Gate。先跑日常、冲突，再覆盖空间调度和设定揭示。记录五类委托、档案挂载、原始素材、取舍、正文、审读与统计。提示词修改依据实际失败，单次聚焦一个问题，以原案例和另一案例复测。

首批使用当前模型；余额、鉴权或网络阻断后保留证据，停止反复付费请求，继续离线验证。旧验收中的重复短句画像仅作为合成技术证据。实验效果按原文细读、版本对照和统计分别报告。

## Module Change Packet：可执行的自然委托

- objective: 主创以自然文字给每位取材者完整邀请，整理后能够逐次调用。
- primary_module: Engine prompting。
- public_entry: scene.v2.creator.delegation / scene.v2.creator.create。
- variation_point: 固定模板的正向创作引导；已有交易保持旧快照。
- inputs: 日常真实原稿及两次提取失败；角色合并邀请、其他类别缺失委托正文。
- outputs: 每位角色独立邀请、连续的委托正文和明确文风、来源选择。
- invariants: 自然交付、角色卡原结构、主创决定取材目的、固定技术合同由系统校验。
- allowed_dependencies: Engine prompt assets 与版本快照。
- forbidden_dependencies: 提取器补写创作内容、把表格摘要伪装为主创正文、增加否定边界层。
- tests: 模板正向性、真实原稿整理回放、日常复测及冲突案例验证。
- rollback_unit: 提示词独立提交。
- documentation: 本文件及对照报告。

## Module Change Packet：档案知识分区整理

- objective: 后置整理把主创明确写出的知识分区转为既有枚举值。
- primary_module: Studio runtimes 的 NaturalOutputProcessor。
- public_entry: process(operation=creator)。
- variation_point: 整理任务的机器字段说明。
- inputs: 主创的角色可知／主创参考区与技术合同。
- outputs: knowledge 为 known/reference 的挂载记录；未说明的选择保留空值并进入原校验。
- invariants: 保留原文、角色卡与知识选择；没有新增角色知识；全部正式校验继续执行。
- allowed_dependencies: 现有 source transport；Engine public 验证。
- forbidden_dependencies: 整理器编写邀请、猜测主创未选的分区、放宽角色知识合同。
- tests: 原始交付提取回放、分区输入合同、角色隔离回归。
- rollback_unit: 技术整理提示独立提交。
- documentation: 本文件。
