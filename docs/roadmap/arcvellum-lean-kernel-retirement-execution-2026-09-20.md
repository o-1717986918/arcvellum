# ArcVellum 轻内核收敛与旧内核退役执行计划

日期：2026-09-20；更新：2026-09-21
状态：新作品生产创作、审计、交付和工作台读模型已完全解除对 `strict-v1` 执行器的依赖；旧内核已从用户选择面隐藏，仅作为未迁移历史作品的数据恢复实现保留。旧代码物理删除仍受历史数据迁移门槛约束。

## 1. 目标和已核对的现实

目标是让用户完成一本书所需的语义调用、往返时间、任务文件与失败重试显著下降，同时保住作品事实和正式正文的可恢复写回。**轻量快捷是首要验收指标**；不能把旧流程换名后继续执行全部旧状态。

本次按源码核对的事实：

- `automation/run_loop.py` 只在 `scene-development + lean-v2` 时调用 `automation/lean_scene_host.py`；`longform-planning` 等路线即使 policy 为 `lean-v2`，仍经 `Worker.run_once`、Engine 旧 task package 与 sidecar 流程。
- `project_agent/actions.py` 的长期目标明确选择 `lean-v2`，故 Agent 的口头路线与实际规划路线目前不一致。
- `workflow/state_longform.py`、`routes/longform/blueprints.py` 和 `routes/longform/gates.py` 分别表达规划状态、派发任务与验收条件。故事架构 review 为 `block` 时，状态停止规划，但 blueprint 仍派发 writer revision；gate 只接受 `revise`。这是确定性死路。
- 故事架构执行 prompt 要求“最小可信因果骨架”，review prompt 又可能按全书场景库存不足判 `block`；后续预算、库存、章节义务恰好负责展开这一层。审查范围发生前置。
- `compatibility/lean-kernel-v2.json` 已规定 `lean-v2=production`、`strict-v1=historical-compatibility` 且不可由用户选择；`deletion_allowed=false` 只约束旧数据读者的物理删除。

相关既有决策：`docs/architecture/arcvellum-lean-literary-kernel-v2-design.md`、`docs/architecture/arcvellum-legacy-surface-retirement-audit-2026-09-14.md`。本文收敛实施，不推翻兼容规则。

## 2. 不变量与反过度设计标准

1. 新创作路径只保留候选创作、必要的语义判断、确定性校验、正式写回与发布完整性；中间思考不自动等于一个任务、一个模型调用和一份 sidecar。
2. 用户锁定事实、Canon、人物状态、正式正文和交付不可被 Agent 直接覆盖；机器负责 ID、路径、摘要、字数与恢复证据。
3. `block` 表示当前目标或边界需重新决定；`revise` 表示同一目标下候选可修。二者不得落到同一个自动修订循环。
4. 新路径减少概念和代码。不得为迁移另造一套通用 DAG、任务协议或第二状态机；优先复用 Pi Worker、事务提交、项目数据格式和 Studio 观测流。
5. 旧项目的读取、恢复和显式回退独立于新项目的写入。没有消费者证据，不删除旧读者。
6. 故障恢复用本事务的可验证结果，不因界面、文档或无关资产变化重复调用模型。

## 3. 目标依赖方向

```text
Project Agent / 用户动作
  -> Studio application 的作品用例
  -> lean planning 或 scene transaction
  -> Engine 领域合同、确定性预算/校验、只读兼容适配
  -> Studio Pi runtime、原子写回、事件流

strict-v1: 只由显式兼容/回退分支进入；不再成为 lean-v2 的隐式规划实现。
```

Engine 不依赖 Studio 的 Agent/数据库；Pi Worker 不决定文学路线；前端只呈现用例和事件，不拼接旧 CLI 任务。Engine `public.*` 仍是跨包边界；迁移期间旧任务读取器保留在兼容侧。

## 4. 分批实施及模块/代码落点

### A. 立即止损：旧规划路径不再空转（本批）

| 位置 | 改动 | 验收 |
| --- | --- | --- |
| `routes/longform/blueprints.py` | 故事架构 `block` 走现成 `route-diagnostic-boundary`，不再生成永远无法通过 gate 的 revision；`revise` 保持原任务 | `block` 不调用 writer，`revise` 可完成并重审 |
| `routes/longform/gates.py` / `workflow/state_longform.py` | 保持 review verdict 的唯一解释与现有 pass/revise/block 状态合同；若测试揭示分歧才做最小修改 | 状态、task type、gate 三者一致 |
| `.../prompt_assets/route.longform-planning.story-architecture.review.v1.md`、`literary/assets/continuity/architecture.py` | 正式 Prompt 与旧 sidecar 同步审查因果骨架和卷级义务；详细场景量转交预算/库存审查；明确 block/revise 决策边界 | 不因尚未生成 100 场景而误判架构无效；真实 premise 冲突仍可 block |
| `tests/test_story_architecture_contract.py` | 增加 exact-digest block 回归，保持 revise 回归 | 阻塞可解释、无重复调用 |

本批**不**将用户项目中的 `block` 改写为 `pass`，不篡改已有 review，也不删除旧内核。
旧路线中的项目级 `block` 暂时只能停下并交由作品方向调整；现有任务协议缺少“方向改变后重启候选”的简洁恢复入口。B 批必须把恢复作为验收用例，不能把 A 批的明确暂停误称为全自动恢复。

### B. 轻量长篇规划：解除 lean-v2 对旧规划 route 的隐式依赖

先实现一个直接的轻量规划用例，不引入新的总编排框架。按 `arcvellum-lean-literary-kernel-v2-design.md` 的滚动规划执行：全书有因果骨架和章级库存，近端细化 2-4 场，章节写完后再补下一个窗口。不得一次要求模型输出百场详表。

- `src/literary_engineering_studio_engine/literary/planning/service.py`：先把预算计算与旧 sidecar 写入分离；新用例只复用预算计算，旧 `build_word_budget` 保持历史输出。
- `src/literary_engineering_studio_engine/literary/planning/materializer.py`：把“已审查旧候选的准入”与“安全物化正式场景”分开；lean 用例提供经自身校验的输入，复用正式文件冲突检查，不能伪造旧 review JSON 来骗过 materializer。
- `src/literary_engineering_studio_engine/literary/planning/`：复用既有目标字数、章节/场景库存、因果合理性等纯函数；新增最小 `PlanningCandidate` 校验。候选只需作品因果骨架、卷级义务、目标预算、可展开的事件/章节库存，不要求前置写出整书正文或每场完整推演。
- `src/literary_engineering_studio/application/`：一个规划用例负责读取现有方向、准备精简上下文、调用一次主创规划、执行确定性预算；若风险高或一致性失败，按需独立审查/修订。默认无“候选准备 -> completion marker -> review 准备”等空调用。
- `src/literary_engineering_studio/automation/run_loop.py`：对 `longform-planning + lean-v2` 显式进入新用例，旧 `Worker.run_once` 只服务 `strict-v1`。路由进度仍交给现有 run store；不建立第二份运行状态。
- 复用 `runtime/` 的 Pi Adapter、沙箱、取消、超时和 `automation` 的事件/恢复；输出继续物化现有 `project.yaml`、`plot/`、章节/场景合同，保持阅读器与星仪消费者不变。
- 要求可中断续跑：规划候选已存在且 digest 未变时，确定性物化不重复请求模型；失败只重跑未提交的语义阶段。

具体交付次序：

1. `literary/planning/service.py` 将预算的纯计算与旧任务文件写入拆开；`materializer.py` 将正式文件冲突检查和渲染与旧 review 准入拆开，原函数保持向后兼容。
2. Engine 提供最小 `ProjectPlanBundle` 合同：全书因果骨架、各章戏剧义务/目标字数、当前滚动窗口的场景。项目事实 ID、字数分配、路径和摘要由程序生成。先做纯校验与夹具，不接模型。
3. Studio 通过现有 `RoleConversationGateway` 调用 Pi 主创，一次生成/更新一个规划窗口；确定性校验后原子写入，并发冲突或失败不产生半套正式场景。
4. `automation/run_loop.py` 对 lean-v2 的 `longform-planning` 显式路由新用例；`automation/lean_scene_loop.py` 写完窗口后先扩下一章，再判断全书完成。更新 `route_dependencies.py` 与 release 进度索引，避免固定旧路线序号。
5. 使用同一作品方向跑新建、断点续跑、章节扩展、目标长度变化、项目级 block、旧作品回退以及两章正文闭环；比较 Pi 调用次数、上下文量和产物数。

完成条件：一个 lean-v2 全自动目标从规划到两章正文不触及 Engine `task-next` / Studio `AgentWorker.run_once` 的长篇规划 route；旧项目仍能显式选择 strict-v1。

**先做垂直切片**：新作品方向 -> 规划 -> 预算与库存 -> materialization -> 第一场 `lean-v2` transaction。固定小夹具至少覆盖新建、resume、revise、block、旧项目只读。切片通过前，不切新项目默认。

### C. 其余旧路线按消费者迁移，不能一刀切

| 旧路线/模块 | 迁移动作 | 保留条件 |
| --- | --- | --- |
| `style-engineering` / `routes/style/` | 文风作为可挂载资产；导入/编写/校验一次完成，场景 brief 只读取精简约束 | 保留旧文风文件 reader |
| `character-and-world-assets`、`source-ingest` | 资产候选和来源解析改为按需用例；用户编辑优先级不变 | 保留格式解析与追溯 |
| `review-and-audit`、`export-and-release` | 章节检查点与最终交付聚合；不逐场重演过程 gate | 保留发布前完整性与确定性防护 |
| `routes/scene/`、`workflow/state_scene.py` | 新项目入口迁至 scene transaction；旧 route 明确标识 strict-v1 | 旧项目恢复/迁移期间保留 |
| `tasking/`、sidecar、completion marker、legacy prompt assets | 只在零新写入且迁移/回退独立可用后分批移除 | 持久历史读取器保留到版本承诺兑现 |

每条路线都按“真实消费者 -> 新用例 -> 验证 -> 禁止新写旧格式 -> 版本化退役”顺序，不为凑清单重写仍好用的确定性模块。

生产迁移的优先顺序：先 B（规划），再 review/release（两章闭环所必需），最后按需资产与文风、来源导入。后面三类可用现有独立应用服务，不应为了形式统一都变成新的大任务。lean-v2 的 `ROUTE_ORDER` 只保留确有业务工作的阶段；空路线不调用模型、不生成 sidecar。

### D. 旧内核物理删除门槛

1. 新作品默认路径完成至少两章连续创作、恢复、角色/Canon 更新和交付；同模型对照显示文学质量不劣，任务数/调用数/耗时确实下降。
2. 新旧项目迁移命令及回退文档存在；兼容 manifest 中的零消费者发布周期真实记录达到要求。
3. `scripts/verify_compatibility_surface.py`、受影响 Python/前端测试和安装版 smoke 通过；公开 Engine API 的移除遵守版本下限。
4. 逐批删除旧写入、旧执行、旧 UI 暴露，最后才处理旧读者。删除包必须附消费者搜索结果及数据恢复样例。

## 5. 性能和文学验收

选固定模型与固定目标，分别记录：首次可读正文时间、每千字模型调用数、传入上下文字符数、任务/sidecar 数、无进度重试数、完成一章的人工干预数。用相同作品 brief 做盲评，检查人物行动因果、叙事节奏、文风与衔接；不能只用 gate 通过率证明质量。目标方向是这些流程成本较 strict-v1 显著降低，且无不可恢复的错误写回。若质量下降，调整 brief/审查风险，不恢复逐步 sidecar 仪式。

## 6. 本轮执行记录

- A 批完成：故事架构 `block` 与 `revise` 的任务去向不再互相矛盾；审核范围回到因果骨架。
- B 批完成：预算纯计算与旧 sidecar 写入分开；轻规划一次生成全书章级骨架和首章场景，后续按章滚动；正式场景和物化清单安全批量写入。新方向在下一窗口生效，不因追加对话整书停机。
- C 批生产路径完成：新 Studio 作品默认选择 `lean-v2`；七阶段 Autopilot 均由轻用例驱动，不调用 `AgentWorker.run_once`、旧依赖解析或旧 CreativeSteward。默认文风先于规划挂载，消除规划摘要漂移。人物与世界初始事实来自同一次规划回复，不另增模型调用；来源导入可仅保全证据而不产生旧任务，规划按边界读取代表性片段；审查与 DOCX 交付直接核验轻事务/章节检查点。轻项目 dashboard 不调用旧工作流状态构建器。
- 真实验收：临时新作品由已配置 Pi Worker 生成两章两场、完成正文事务和章节检查点、通过 `audit_lean_book`、生成 DOCX。首场 4 次修订、次场 1 次修订；确定性逗号过密与虚构 target_ref 占首场前两轮，审查把孤立 warning 当退稿占一轮。已针对这三类真实浪费修正生成/审查提示，尚未做同模型复测成本比较。
- 受控集成验收：七阶段 Autopilot、两章事务与交付同跑，断言旧 Worker 未创建、无 `workflow/tasks` 和 `reviews` 目录；来源导入、档案投影、资产幂等、默认文风、旧项目回退均有聚焦测试。`scripts/verify_compatibility_surface.py` 与 `git diff --check` 通过。
- 架构收敛：轻规划、轻全书审计、轻交付与 claimed-run 初始化已按 application / automation / projection 职责拆开；架构审计为零新增依赖、体量和复杂度债务。项目 Agent 不再直接依赖星仪与创作现场具体组件，组合关系上移到共享工作区组件。
- 产品收敛：新作品使用正式 `lean-v2`；推进仪表仅暴露创作校对强度，不再向用户展示或切换 `strict-v1`。未标记的历史作品仍保持原内核，避免把旧正文伪装成轻事务提交。
- 写入边界：公开迁移合同只接受 `lean-v2`；`strict-v1` 在兼容清单中为 `historical-compatibility`、`user_selectable=false`。历史项目可继续用原策略读取和恢复，但新请求无法重新启用旧写入链。
- 最终回归：Python 全量 `1465` 项通过、`1` 项按环境跳过；前端 `70` 个测试文件、`230` 项测试通过；Vue 类型检查、架构审计、兼容面验证、OpenAPI 当前性检查和 `git diff --check` 通过。真实 Pi 临时作品完成两章、审计和 DOCX 交付。

## 7. 尚未解除的兼容边界

生产路径和用户入口已完成剥离，**旧内核代码尚未物理删除**。历史作品若有旧正式场景或正文而无轻事务回执，直接改变 policy 会让规划物化或交付审计误判。因此 Project Agent 会维持这类作品现存内核；已错误标记为轻内核的历史作品会明确停下，而不伪造提交回执。旧场景/资产读者、恢复执行器和对应测试继续留在兼容区，不参与新作品运行。

完全删除 `strict-v1` 前还需要：可审计的历史作品迁移工具（原文、promotion、审查、状态变化和章节证据都须准确绑定）；两次零消费者发布周期；同模型文学质量盲评与成本对照。兼容 manifest 继续标记 `deletion_allowed=false`，`ready_for_default=false` 表示文学非劣效证据未足，但记录产品负责人要求新作品先以轻路线默认运行。不能用真实短篇 smoke 冒充全书质量证明。
