# ArcVellum v1 实施进度

> 权威路线：`docs/roadmap/arcvellum-v0.96-v1.0-integrated-engineering-implementation-plan.md`
>
> 长期产品路线：`docs/roadmap/arcvellum-post-v0.95.3-long-horizon-product-and-runtime-roadmap.md`
>
> 自适应编排规格：`docs/roadmap/arcvellum-adaptive-creative-orchestration-implementation-plan.md`
>
> 约束基线：`docs/architecture/module-boundaries.md`
>
> 规划基线提交：`f3cc855`；当前实施分支：`feat/v097-archive-foundation`
>
> 本文件只记录已经通过退出门禁的事实。完成一段代码、通过定向测试或生成构建产物，均不能单独视为工作流交付。

## 实施顺序决策（2026-07-26）

- W4 Project Archaeology 完成全部 Exit Gate 后，只实施 W5 中作为 W6 安全前置的 Capability Broker、能力策略/审计和必要 `ResourceClaim` 契约。
- Pi RPC、Ollama 与新增模型供应商接入暂缓，不作为进入 W6 的前置；现有 `AgentRuntime`、Worker、任务包、Gate、JobStore 和当前 Provider 通道保持不变。
- W6 不复制 W5 的 Runtime、Provider 或 Capability Broker。未获 Broker 授权的能力必须确定性拒绝；尚未具备资源声明的工作保持串行，不得伪报并发完成。
- W5 的新增 Runtime 与 Provider 子项状态记为 `deferred_by_owner`；后续只有用户显式恢复时再实施。该顺序调整不降低 W4 退出标准，也不允许 W6 绕过 mandatory gates。

## 当前结论

- F0 契约与架构基线已完成三个可回滚批次：吞吐测量、架构质量审计、叙事焦点契约。
- W1 Living Narrative Field 已完成关系可见性、人物引用、正文窗口三态、工作区语义 revision、100/300/1000 规模基准、v3 增量传输、真实磁盘完整证据与浏览器大规模视觉验收。
- W1 已满足当前路线定义的性能、导航、焦点、空间语法、主题、多窗口与 canvas 非空退出门禁。
- W2 Narrative Archive IDE 已完成受控资产身份、校验、影响预览、Owner Override、修订历史、正式 stale 传播、可逆归档/恢复、候选晋升、Registry 驱动的结构化编辑、状态化引导和隔离真实项目作者闭环。
- W2 已满足统一实施方案当前定义的产品、Gate、Stable Knowledge 与架构出口；后续 W3-W8/AO 工作流仍未实施完毕，不得据此声称 v1 已交付。
- W4 Project Archaeology 已完成不可变源证据、分块提取、全书聚合、实体解析、候选重建、领域审查、Archive 晋升边界、四模式工作台和真实纵向 Exit Audit。
- 最近一次 Python 全量证据：618 tests passed、1 skipped，耗时约 137 秒；Client 最近一次基线为 101 tests passed；Python compileall、Prompt Registry、Architecture Audit 与 `git diff --check` 全部通过。

## F0-1：Measure-only 创作吞吐投影

- Status: complete
- Commit: `7109fce`
- Added: `observability/throughput_metrics.py`，统计任务、模型轮次、修复次数、阶段耗时与首次通过率。
- Boundary: 只观测，不改变任务选择、模型分配或 Gate。

## F0-2：架构质量基线

- Status: complete
- Commit: `484c523`
- Added: `scripts/architecture_audit.py`、`scripts/architecture_audit_core.py`、`architecture/quality-baseline.json`。
- Gate: 冻结现有大文件/大函数债务，拒绝新增超预算函数、依赖环、非法 facade 依赖和重复路由。

## F0-3：NarrativeFocusScope

- Status: complete
- Commit: `2eb951f`
- Added: book/chapter/scene/character 的稳定焦点契约与 Python/TypeScript 共享夹具。
- Evidence: 整章包含全部场景；场景焦点保留相邻场景；人物焦点不删除全书上下文。

## W1-1：关系可见性契约

- Status: complete
- Commit: `d9d0d8e`
- Added: 关系族、LOD、焦点态、关系可见性档案与跨语言契约测试。
- Evidence: 旧 edge type 保持兼容；章节/场景人物关系不再因 endpoint 推断错误而消失。

## W1-2：人物引用与人物轨道

- Status: complete
- Commit: `b340cc9`
- Added:
  - `CharacterReference`、`resolved/unresolved/ambiguous` 枚举和共享夹具；
  - 正式人物 ID、别名、旧式参与者名称和显式 `participant_refs` 的确定性解析；
  - 未解析与多义提及的显式节点，不再静默丢弃；
  - v3 投影中的全书人物节点、场景/章节参与关系和 revision 绑定；
  - 前端人物轨道按“本章人物 / 全书人物 / 待解析”分组；
  - 新项目模板增加兼容的 `aliases` 与 `participant_refs` 空字段。
- Boundary:
  - 该能力只构建只读投影；
  - 不创建、晋升或修改正式人物资产；
  - 不把未解析提及伪装成正式角色。
- Exit evidence:
  - Python full suite: 411 passed；
  - Client full suite: 62 passed；
  - Client production build: passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: 37 existing file debts, 230 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W1-3：正文长卷三态

- Status: complete
- Commits: `09c02c1`, `d226883`
- Added:
  - `peek / reading / immersive` 三态窗口契约；
  - 作品级窗口状态持久化与旧布局升级；
  - 进入沉浸态前保存返回位置、尺寸和非沉浸状态；
  - 正文首段预览、完整阅览和沉浸阅读之间的显式转换；
  - 窗口几何从 Pinia store 提取为纯模块，避免状态仓库继续膨胀；
  - 受控阅读器组件测试和窗口状态/返回几何测试。
- Boundary:
  - 不改变正式正文、阅读清单或后端投影；
  - 不把阅读器全屏状态保存在组件私有变量中；
  - 不允许旧持久化数据注入未知阅读器状态。
- Exit evidence:
  - Python full suite: 414 passed；
  - Client full suite: 69 passed；
  - Client production build: passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: 37 existing file debts, 230 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed；
  - 实际浏览器：`reading 388×640 -> immersive 1248×688 -> reading 388×640` 精确恢复；
  - 实际浏览器：拖动后保持 `388×640`，与推进仪表双窗口共存；
  - 实际浏览器：连续 5.2 秒工作区 SSE 后，窗口位置、尺寸、模式和窗口数量均保持稳定；
  - 实际截图：窄窗标题不再逐字竖排，沉浸态隐藏无关全局观测控件。

## W1-S1：工作区语义 revision 与稳定流更新

- Status: complete
- Commit: `d226883`
- Added:
  - 工作区总 revision 与 dashboard/library/delivery/progress/prose/agent-observability 分区 revision；
  - narrative v3 `projection_revision` 兼容字段；
  - SSE 优先使用服务端显式语义 revision，不再对含墙钟计数的整包数据反复发事件；
  - Agent 会话 `elapsed_seconds` 保留可见更新，但不再污染语义 revision；
  - Pinia 按分区 revision 更新，未变化的读模型保持对象身份；
  - 星仪投影 store 忽略相同 `projection_revision`，避免无意义重排；
  - 阅读器窗口在观测状态变化时保持同一挂载实例的组件回归测试。
- Boundary:
  - 不降低 Agent 会话可观察性；
  - 不以客户端节流掩盖服务端语义不稳定；
  - 不把窗口几何或正文阅读状态写回作品项目。

## W1-4A：100/300/1000 规模基准

- Status: complete
- Commit: `727fa24`
- Added:
  - 稳定的 100/300/1000 场景文学证据 fixture；
  - book 聚合投影与 scene 全书细粒度投影的可重复后端基准；
  - 六种空间语法的 1000 节点有限坐标、可寻址和布局耗时回归；
  - 已建立节点在全书扩张时保持 X/Z 不漂移、Y 仅随宏观节奏受限呼吸的契约。
- Baseline:
  - 1000 场景 scene 投影：1049 nodes、3024 edges、约 1.985 MB；
  - 当前机器基线中位构建耗时约 110 ms；
  - 六种语法均可完成 1000 节点布局，无非有限坐标或节点丢失。

## W1-4B：Narrative v3 增量 SSE

- Status: complete
- Commit: `191eb1e`
- Added:
  - digest-bound `arcvellum/narrative-projection-patch/v1` 协议；
  - 首帧完整 snapshot、后续语义变化 patch 的 FastAPI SSE 路由；
  - nodes / edges / metadata 的增删改与顺序契约；
  - 前端 exact-base 原子应用、旧序列忽略、base mismatch 自动回源；
  - SSE 路由集成测试，证明同一连接依次收到 snapshot 和 patch；
  - 1000 场景单节点转换基准。
- Baseline:
  - 全量约 1.985 MB；
  - 单节点 patch 约 120 KB，占全量 6.05%；
  - 只 upsert 1 个节点、0 条边，应用后 revision、nodes 和 edges 精确等于目标图。
- Exit evidence:
  - Python full suite: 423 passed；
  - Client full suite: 76 passed；
  - Client production build: passed；
  - `python -m compileall -q src benchmarks scripts`: passed；
  - Architecture Audit: 37 existing file debts, 229 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W1-4C1：真实磁盘项目完整叙事证据

- Status: complete
- Commit: `737fd51`
- Added:
  - 独立的 `arcvellum/narrative-evidence/v1` 只读证据投影；
  - Narrative v2/v3 与节点详情不再复用面向人的截断 Library 摘要；
  - Library 继续保持人物 200、场景 250、分支 250、审查 80、Canon patch 250 的展示上限；
  - Narrative Read Model 使用独立缓存键，不污染档案视图；
  - 可直接物化为真实工作项目的 100/300/1000 场景视觉 fixture；
  - API 集成测试证明 300 场景项目即使 Library 只展示 250 场，Narrative 仍保留全部 300 场。
- Materialized evidence:
  - 100 场景：100 个叙事场景，475 nodes，1641 edges；
  - 300 场景：Library 250 场、Narrative 300 场，1285 nodes，4841 edges；
  - 1000 场景：Library 250 场、Narrative 1000 场，4095 nodes，16042 edges；
  - 三组 fixture 均含章节、人物、分支、审查、Canon patch、节奏计划和部分晋升正文。
- Exit evidence:
  - Python full suite: 427 passed；
  - Client full suite: 76 passed；
  - Client production build: passed；
  - `python -m compileall -q src benchmarks scripts`: passed；
  - Architecture Audit: no new violation；
  - `git diff --check`: passed。
- Performance gate at C1 completion, closed by W1-4C2:
  - 当前真实 1000 场景项目首次完整证据读取约 11.8 秒；
  - v3 scene 投影约 8.4 秒，JSON 首包约 12.6 MB；
  - 正确性和可重复验收基础已完成，但浏览器交互性尚未达到 W1 退出标准；
  - 下一批必须先压缩首次读取、投影和传输成本，再做四 focus、六语法、四主题浏览器视觉验收。

## W1-4C2：大规模叙事性能与真实浏览器验收

- Status: complete
- Commits: `50834cf`, `8e77e17`
- Added:
  - 修复 YAML 列表解析跨区块吞并，1000 场景不再膨胀为 16042 条伪关系；
  - 提取并复用节奏源读模型，避免每个场景重复解析同一章节节奏；
  - 100/300/1000 真实项目物化基准与趋势门禁；
  - Narrative 投影身份由单一 revision 扩展为 revision、焦点、层级和空间语法的组合身份；
  - 扩大叙事工作平面，并以场景簇包围盒计算章节聚焦相机；
  - 章节节点携带确定性入口场景，消除快速切换时使用旧投影的竞态；
  - 项目切换菜单避开全局观测工具的独立堆叠上下文，不再出现首项可见但无法点击；
  - 几何计算提取为纯函数，没有提高架构债务基线。
- Materialized performance evidence:
  - 100 场景：147 nodes、341 edges、约 270 KB，稳定证据读取约 33 ms，投影约 77 ms；
  - 300 场景：357 nodes、941 edges、约 721 KB，稳定证据读取约 83 ms，投影约 245 ms；
  - 1000 场景：1067 nodes、3042 edges、24 个人物节点、0 个未解析引用、约 2.26 MB；
  - 1000 场景稳定证据读取约 367 ms，投影约 744 ms；
  - 1000 场景冷启动证据读取约 8.36 s，冷投影约 1.70 s；
  - 三个规模样本均满足当前趋势预算，未检测到性能违规。
- Browser evidence:
  - 100、300、1000 场景项目均可从项目菜单切换并显示完整规模摘要；
  - 全书、章节、场景和人物焦点可切换，人物焦点保留全书图而只强调相关关系；
  - 第 50 章聚焦一次显示 `scene_0491` 至 `scene_0500` 全部 10 个场景；
  - braid、constellation、loop、spine、stage、strata 六种空间语法均完成实际画布验收；
  - moss、iris、obsidian、bookcase、modern 五套主题均完成实际画布验收；
  - 推进仪表与正文长卷可同时打开，叙事画布保持可见；
  - 所有验收截图均为 804×898，抽样唯一色数为 983-2280，亮度标准差为 18.84-25.68，未出现空白 canvas；
  - 验收截图保存在本地忽略目录 `.tmp-dev/w1-4c2-browser/screens/`，不作为运行时依赖。
- Exit evidence:
  - Python full suite: 431 passed；
  - Client full suite: 79 passed；
  - Client production build: passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: no new violation；
  - `git diff --check`: passed。

## W2-1：受控 Archive 资产与作者事务基础

- Status: complete
- Commits: `4923988`, `b64beea`, `1627fc0`
- Added:
  - `application/assets/` 领域包，集中管理资产契约、注册表、安全加载、revision、确定性校验、影响预览和作者事务；
  - `projections/archive/` 只读树与详情投影，不复用面向人的截断 Library，也不把 Library 改造成巨型编辑器；
  - character、scene、world-rule、location-catalog、organization-catalog、promise-ledger 和 reader-question-ledger 的第一批稳定资产定义；
  - API 只接收 `<asset-type>:<stable-id>`，不接受客户端提供的任意项目内路径；
  - UTF-8 文本、NUL、空内容、4 MB 上限、JSON 根、角色/场景 ID 一致性和场景人物引用校验；
  - `sha256:` revision 与乐观锁，旧标签页提交返回稳定 `version_conflict`；
  - Owner Override 只支持显式 `replace /content`，语义豁免不能豁免结构、路径、引用或版本检查；
  - 原子目标替换、失败回滚、before/after snapshot、transaction 和 Mutation Receipt；
  - 有界影响扫描，输出相对路径和 stale 类别，不暴露项目绝对路径；
  - `/archive/tree`、详情、validate、impact 和 commit API；
  - API 路由表测试改为临时数据目录，消除本机配置和受限环境对测试结果的影响。
- Boundary:
  - 本批不实现任意文件编辑、移动、删除、候选晋升或 Engine Gate 复制；
  - `stale_propagation=recorded-for-follow-up` 只记录影响，尚未改变现有任务 Gate；
  - 事务快照当前保存在项目 `workflow/archive/transactions/`，SQLite 索引、保留政策和历史投影留待 W2-2；
  - 需要语义审查的事务不能直接提交；本批只开放作者明确给出理由的 owner waiver；
  - 软链接越界测试在无 Windows 软链接权限时跳过，路径/ID 越级和运行时边界检查仍执行。
- Exit evidence:
  - Python full suite: 437 passed, 1 skipped；
  - Client full suite: 79 passed；
  - Client production build and desktop frontend sync: passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: 37 existing file debts, 229 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W2-2：修订历史、可重建索引与正式失效证据

- Status: complete
- Commits: `d955e30`, `d41dba9`, `e2ef298`
- Added:
  - Studio SQLite schema 升级到 v9，并在现有 `JobStore` 连接、写锁、备份和迁移协议下增加 `archive_asset_transactions` 与 `archive_asset_revisions`；
  - transaction 与 before/after revision 在同一数据库事务写入，重复 receipt 幂等；revision 写入失败会回滚 transaction 行；
  - 项目 `workflow/archive/transactions/*/receipt.json` 与快照继续作为正式真相源，SQLite 只保存可重建索引；
  - 历史读取可从项目 receipt 自动同步丢失的索引；索引暂时不可用时，已成功的项目写入不会被伪装成失败，Mutation Receipt 会记录 `history_index=rebuild-required`；
  - `/archive/assets/{asset_id}/history` 返回不含绝对路径的 revision、transaction、影响和失效摘要；
  - `/archive/assets/{asset_id}/restore/preview` 从受控 revision 索引定位快照，重新校验项目边界、软链接、UTF-8 和内容 digest，只生成基于当前 revision 的 OwnerOverride 预览，不修改资产；
  - 作者事务提交后，使用 Engine 既有 Context Trace SHA-256 freshness 机制验证受影响场景；receipt 记录具体 scene、trace、原因和下游阶段，正式 workflow 会回到 `context-trace`；
  - 已晋升正文只作为历史事实保留，不被 Archive 提交或恢复预览静默改写；
  - Archive router 的新增逻辑继续委托 application/projection service，没有抬高 API 或架构债务基线。
- Boundary:
  - 没有增加第二套 task/stale 状态机；Context、RP、Branch、Composition、Candidate、Review 和 Promotion 的失效仍由 Engine 派生状态与 Gate 判断；
  - SQLite 不保存大段正文 diff，也不取代项目 receipt/snapshot；
  - 本批不执行实际 restore、archive、永久删除、候选晋升或前端编辑；
  - `not-required` 表示当前没有 Context Trace 消费该资产，不表示所有文本引用都已自动修订；
  - 软链接越界测试在当前 Windows 权限不足时仍跳过，运行时代码继续做 resolved parent boundary 检查。
- Exit evidence:
  - Python full suite: 444 passed, 1 skipped；
  - Client full suite: 79 passed；
  - Client production build and desktop frontend sync: passed；
  - `python -m compileall -q src benchmarks scripts`: passed；
  - Architecture Audit: 37 existing file debts, 229 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W2-3：可逆归档、实际恢复与回收站

- Status: complete
- Commits: `5b87009`, `7250b82`, `40e2e81`
- Added:
  - Studio SQLite schema 升级到 v10，在既有 `JobStore` 连接、写锁、迁移备份和事务协议下增加 `archive_recycle_entries`；
  - 项目 `workflow/archive/recycle-bin/<entry_id>/` 中的 entry、不可变 snapshot 与 receipt 继续作为真相源，SQLite 只保存可重建索引；
  - `character` 与 `scene` 第一批可归档资产继续使用 `<asset-type>:<stable-id>`，归档和恢复 API 不接收任意项目路径；
  - 归档前检查 `supports_archive`、base revision 和正式引用；`scenes/`、`canon/`、`plot/` 中的引用形成硬阻断，作者权威不能制造断裂正式事实；
  - 归档先把正式文件移动到同项目 staging snapshot，再激活回收条目；激活、目录提交或失效证据写入失败会恢复原正式路径；
  - 恢复重新验证 entry identity、snapshot 边界、UTF-8 内容 digest、asset schema 和目标占位冲突；
  - 恢复失败不会留下新的正式文件；恢复成功后 snapshot 保持不可变，entry 转为 `restored` 并写入独立恢复回执；
  - 索引暂时不可用不会伪装项目事务失败，receipt 标记 `rebuild-required`，后续回收站读取可从项目 entry 重建；
  - `/archive/recycle-bin`、`/archive/assets/{asset_id}/archive`、`/archive/assets/{asset_id}/restore`；
  - 回收站投影只公开稳定身份、标题、状态、原相对位置、原因和时间，不公开绝对路径、snapshot 或内部事务目录；
  - `version_conflict`、`archive_reference_conflict`、`restore_conflict` 分别使用稳定 `409` 语义。
- Boundary:
  - 本批不实现永久删除；已归档和已恢复的 snapshot 都作为历史证据保留；
  - 本批不把移动文件当成候选晋升，不复制或旁路 Engine promotion Gate；
  - 本批不开放任意文件归档，只允许 Registry 明确声明 `supports_archive=True` 的资产；
  - 本批不自动修改正式引用、已晋升正文或发布物；Context Trace 仍是下游 stale 的唯一正式机制；
  - 本批只提供后端事务和安全投影，尚未实现 Archive IDE 的编辑器、时间线和回收站界面。
- Failure evidence:
  - 正式引用仍存在时，归档拒绝且原文件不变；
  - entry 激活失败时，已移动 snapshot 回滚到正式路径；
  - restore receipt/entry 状态写入失败时，新正式文件被移除，entry 保持可重试；
  - 同一稳定 ID 已存在新正式文件时，恢复拒绝覆盖；
  - 新 `JobStore` 可从项目 entry 重建 active/restored 索引；
  - 恢复后不可变 snapshot 继续存在，支持审计和后续历史能力。
- Exit evidence:
  - Python full suite: 450 passed, 1 skipped；
  - Client full suite: 79 passed；
  - Client production build and desktop frontend sync: passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: 37 existing file debts, 229 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W2-4：候选资产投影与单一晋升门禁

- Status: complete
- Commits: `6e8a4ff`, `42189f9`
- Added:
  - 候选资产拥有独立稳定 ID、Registry 投影和来源定位，不与正式资产或回收条目混淆；
  - 候选详情集中呈现 source、review、completion、impact 和 output contract，不要求前端理解 Engine 内部目录；
  - 晋升预览由 Engine 原有 Gate 计算 exact review、completion、digest、结构校验和阻断原因；
  - Studio 只创建受控 Worker 任务，实际晋升继续委托 Engine 单一 promotion 实现；
  - 人工批准绑定候选 revision、preview digest、目标路径和 task command，旧预览或候选变化后必须重新批准；
  - 晋升成功后保留既有 promotion manifest、Mutation Receipt 和 stale 传播语义；
  - `/archive/candidates`、候选详情、晋升预览和晋升执行 API；
  - 错误响应使用稳定 code/details，前端不再依赖解析任意错误文本。
- Boundary:
  - 不允许 Archive 直接复制候选文件到正式目录；
  - Owner Override、restore 和普通资产 commit 均不能伪造候选晋升；
  - 候选审查、完成标记和 digest 任一失效时，必须回到 Engine 重新生成正式证据；
  - 前端只批准既有预览，不拥有删除 Gate 或改写 task command 的能力。
- Exit evidence:
  - focused Archive/API suite: 38 passed, 1 skipped；
  - candidate promotion success、stale preview、review mismatch、digest mismatch 和 approval mismatch 均有回归测试；
  - Architecture Audit: no new violation；
  - `git diff --check`: passed。

## W2-5：Narrative Archive 前端工作台与真实项目兼容

- Status: complete
- Commit: `9dcd373`
- Added:
  - 新增独立 `/archive` Narrative Archive 工作台，保持旧 `/library` 只读入口可访问；
  - 三栏紧凑深色布局：正式资产树、多标签校勘区、影响/历史/候选/回收证据区；
  - 正式详情、多标签切换、字段导航、完整源文本编辑、预校验和影响预览；
  - 作者权威提交必须显式填写理由，并绑定 owner waiver 与 exact base revision；
  - Revision Timeline、受控恢复预览、归档、回收站恢复和 stale 证据展示；
  - 候选 Gate、阻断原因、输出影响和人工批准卡片，晋升仍经既有 Worker 与 Engine Gate；
  - Archive 核心资料先加载，人工选择异步补充；选择服务缓慢或不可用不再阻塞首个正式资产打开；
  - API client 增加结构化 `ApiError`，保留 code、message、status 和 details；
  - 前端测试命令固定使用 Vitest runner config loader，消除受限 Windows 环境下的 esbuild 配置加载失败；
  - Registry 稳定 ID 支持安全的 Unicode 字母和数字，继续拒绝路径分隔符、冒号、空格、`..`、非法起始字符和超长 ID；
  - 真实项目 `1+1=2` 可完整投影 79 个正式资产和 3 个候选资产，不再因中文角色文件名使整棵资产树失败。
- Browser evidence:
  - 1440×900 桌面视口完成真实 API 验收，三栏保持同高、无横向溢出；
  - 首个正式资产可在人工选择请求尚未返回时自动打开；
  - 窄视口降级为可滚动纵向布局，资产树、编辑区和证据区仍可使用；
  - 修复浅色原生滚动条和过小辅助文本，Archive 保持暗色校勘台视觉，不出现突兀白色面板。
- Boundary:
  - 当前字段导航用于理解结构，正式修改仍采用 Registry 校验过的完整源文本，尚未为七种资产分别建立深度结构化表单；
  - 本批没有开放任意文件浏览、路径输入、Shell 或绕过语义审查的保存方式；
  - 本批没有实现“新建正式资产”，因此 W2 整体仍未达到退出标准；
  - 候选浏览器截图未作为门禁证据，候选交互由 store/component/API 测试覆盖。
- Exit evidence:
  - Python full suite: 461 passed, 1 skipped；
  - Client full suite: 84 passed；
  - Client production build、typecheck、desktop frontend sync 和 v0.9 build verification: passed；
  - `python -m compileall -q src benchmarks scripts`: passed；
  - Architecture Audit: 37 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W2-6：Registry 驱动的受控资产创建

- Status: complete
- Commit: `7a6a083`
- Added:
  - 七种已注册资产通过 `supports_create` 显式声明创建能力；客户端不能提交任意目录或文件路径；
  - 创建选项由 Registry 投影类型、稳定 ID 规则、编辑器种类、受控模板和占用状态；
  - 新建请求绑定资产类型、稳定 ID、内容、作者理由、语义审查策略、预期影响和 preview digest；
  - 创建前执行路径边界、目标占用、UTF-8/结构/引用与类型必填字段校验，并生成影响预览；
  - 创建使用独占文件创建、临时事务目录、before/after snapshot、Mutation Receipt 和失败回滚；正式目标或事务提交任一失败都不会留下半成品；
  - SQLite schema 升级到 v11，历史索引显式记录 `create/replace` operation；旧数据库通过独立 additive migration 升级；
  - 创建完成后进入既有历史索引和 Context Trace stale propagation，不建立第二套资产状态机；
  - `/archive/creation/options`、`/archive/creation/preview`、`/archive/creation/commit` 使用稳定错误码区分校验、目标冲突和旧预览；
  - Archive IDE 增加紧凑深色创建面板，包含类型选择、稳定身份、受控模板、完整源文本、作者理由、结构/影响检查和提交；
  - 创建成功后刷新工作区并打开新资产，后续编辑、历史、归档和恢复继续复用既有单一事务链。
- Adaptive orchestration boundary:
  - 正式资产创建仍属于作者事务，不是 `CreativeExecutionPlan` 的事实写入捷径；
  - 将来编排 Agent 只能提出资产候选或创建意图，不能直接调用本 Owner 创建事务绕过 Candidate/Promotion Gate；
  - Archive 写模型没有导入 task lifecycle、Plan Compiler、Runtime 或 Engine route 实现；
  - 本批没有赋予 Agent 任意路径、Shell、正式 Canon、人物状态或正式正文写入权。
- Failure evidence:
  - 旧 preview digest、目标已存在、非法稳定 ID、缺失必填字段和不满足结构契约均被拒绝；
  - 事务目录最终化失败会删除刚创建的正式文件；
  - Registry 固定单例资产已存在时，创建选项明确不可用；
  - 历史索引暂时不可用时，项目 receipt 仍是可重建真相源。
- Real project evidence:
  - 原项目 `C:\Users\26532\Documents\ArcVellum\Works\1+1=2` 未被修改；
  - 626 文件的隔离克隆投影出 79 个正式资产、7 个创建选项和 3 个候选；
  - 克隆中完成 `character:archive_qa_character` 的创建、编辑、`create/replace` 历史核验、归档和恢复；
  - 候选 `world-foundation` 的既有 Engine Gate 正确报告不可晋升和 1 个阻断，没有被 Archive 创建能力旁路。
- Visual evidence:
  - 当前开发客户端在 812×898 窄视口打开创建面板，dialog 完整位于视窗内，无横向溢出；
  - 面板保持 Archive 暗色校勘台视觉，类型、编辑、审查三层在窄视口按响应式规则重排；
  - 独立 API/真实项目链由 TestClient 验收；浏览器安全策略阻止打开独立 `127.0.0.1:8794` 页面，因此不把该次视觉检查伪装成完整浏览器 API 链验收。
- Exit evidence:
  - Python full suite: 467 passed, 1 skipped；
  - Client full suite: 86 passed；
  - Client production build、typecheck、desktop frontend sync 和 v0.9 build verification: passed；
  - `python -m compileall -q src benchmarks scripts`: passed；
  - Architecture Audit: 37 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W2-7A：字段契约与保格式结构化文档边界

- Status: complete
- Commit: `3c7d07e`
- Added:
  - `AssetViewRegistry` 的七种资产从字段名列表升级为统一 `AssetFieldDefinition` 契约，声明字段类型、分区、必填性、帮助信息与有限选项；字段契约必须与 `writable_fields` 完全一致；
  - 人物、场景和世界规则使用共享表单契约，地点、组织、承诺与读者问题使用共享表格契约，不为每种资产复制独立编辑器协议；
  - 新增 `ruamel.yaml` round-trip 文档编解码层，拒绝重复键、递归别名、非对象根、异常深度和异常节点数量，同时保留未修改 YAML 的注释、引号与字段顺序；
  - JSON ledger 与 YAML 资产通过同一个受控结构化编辑服务投影和回写；
  - 结构化回写只接受 Registry 注册的顶层可写字段，稳定 ID 和其他机器所有字段不能通过表单提交；
  - 结构化投影绑定源文本 digest；用户切换模式或草稿变化后，旧投影会以稳定 `structured_draft_stale` 冲突拒绝覆盖；
  - `/archive/assets/{asset_id}/structure` 和 `/archive/assets/{asset_id}/render-structured` 只返回投影或新的 draft，不直接修改正式项目；
  - 结构化回写后重新执行既有确定性资产校验，真正 commit 仍走 Owner Override、revision、impact、history、stale propagation 与原有事务链；
  - YAML 正式校验从正则抽取升级为完整结构解析，重复键、错误根类型、错误引用类型和损坏嵌套不能再借语义审查豁免进入正式资产；
  - 结构化编辑路由被拆入独立 HTTP 边界模块，未抬高 `archive.py` 文件债务或架构基线。
- Unified implementation boundary:
  - 只建立 `application/assets` 写模型与 API 投影，不改变 `projections/archive` 的只读职责；
  - Engine 继续唯一拥有候选审查、正式晋升、Canon/人物状态 Gate 和任务生命周期；
  - 本批没有让前端直接解析或重写 YAML，也没有把完整项目结构暴露为任意文件编辑器。
- Adaptive orchestration boundary:
  - `CreativeExecutionPlan` 不能通过结构化编辑服务直接修改 Stable Knowledge；
  - 将来 Agent 只能产出候选或受 task package 约束的提议，结构化 Owner 编辑是显式作者事务，不是 Agent 编排自由度；
  - Plan Compiler、Runtime 和 Archive 写模型之间没有新增反向依赖或第二套正式写入路径。
- Failure evidence:
  - 未注册字段、错误字段值形状、旧 source revision 和重复 YAML key 均有确定性反例；
  - JSON ledger 与带注释、引号和扩展机器字段的 YAML 均完成无项目写入的 round-trip；
  - 结构化 API 不接收目标路径，且错误使用稳定 code 区分文档、字段与版本冲突。
- Exit evidence:
  - Python full suite: 472 passed, 1 skipped；
  - `python -m compileall -q src tests`: passed；
  - Architecture Audit: 37 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W2-7B：共享结构化编辑器与逐资产草稿会话

- Status: complete
- Commit: `63fbb68`
- Added:
  - 前端通过后端 `AssetFieldDefinition` 契约生成共享结构化表单，不在 Vue 中复制资产 schema、可写字段或正式 Gate；
  - 统一支持短文本、数值、有限选项、字符串列表、Markdown、对象与表格字段，对象/表格沿用同一递归值编辑器，复杂字段在宽屏跨列、窄屏自动单列；
  - Markdown 字段提供安全编辑/预览，原始 YAML/JSON 保留为明确的专家模式；无效源文本仍可进入专家模式修复，不会被结构化投影失败锁死；
  - 结构化编辑只把实际变更字段提交给 `render-structured`，得到的新内容仍只是当前 draft，不直接 commit 或晋升；
  - 每个已打开正式资产拥有独立 draft、structure、validation、impact 和 history 会话；切换标签不会覆盖其他草稿；
  - 脏标签不能静默关闭，用户必须先保存或显式“放弃草稿”；放弃后恢复 exact 正式内容并重新加载结构化投影；
  - 项目切换清空所有资产会话，标签关闭后的回退选择具有确定顺序；
  - Archive transport、消息、编辑器状态和标签会话被拆到独立 service/composable，Pinia store 保持应用编排职责，没有形成新的巨型组件或反向依赖；
  - 生产构建同步到桌面前端资源。
- Unified implementation boundary:
  - `features/archive/` 是独立作者工作面，旧 `LibraryView` 继续保持亲用户只读入口；
  - UI 只消费 Studio API 的 Registry 与投影，不读取 sidecar Markdown，不实现 Engine promotion 或 Gate 判断；
  - 所有编辑模式共享同一 draft、revision、validate、impact 和 Owner Override commit 链。
- Adaptive orchestration boundary:
  - Archive 编辑器只表达作者事务；`CreativeExecutionPlan`、Planner 和 Runtime 没有获得直接修改正式资产的能力；
  - Stable Knowledge 仍只能通过资产候选/Engine 晋升或显式 Owner Override 进入正式项目；
  - 将来计划节点失效只消费 Archive mutation receipt，不复制本批的版本或写回生命周期。
- Failure and interaction evidence:
  - 组件测试证明只发送实际变化字段，Markdown 预览使用安全渲染，表格支持增删和重排；
  - store 测试证明两个资产草稿相互隔离、脏标签关闭被拒绝、放弃后可关闭且回退标签稳定；
  - 使用真实项目 `1+1=2` 进行只读视觉验收，确认人物、场景、世界规则和 ledger 均可由 Registry 打开；没有修改该项目；
  - 1440px 宽屏和 900px 窄屏均完成截图验收，页面无浏览器 error/warning。
- Exit evidence:
  - Client full suite: 90 passed；
  - Client production build、typecheck、desktop frontend sync 和 v0.9 build verification: passed；
  - Architecture Audit: 37 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W2-7C：状态化引导与隔离真实项目作者闭环

- Status: complete
- Commits: `d43e9e2`, `742a818`
- Added:
  - 新增可复用 `GuidedTour` 与独立 tour state service，模块引导不再依赖一次性的全局说明层；
  - Archive 引导根据正式资产数、候选数、当前选中资产和草稿状态动态生成五步任务，不展示与当前项目无关的空步骤；
  - 所有定位目标使用稳定 `data-tour-id`，引导状态按版本持久化，并提供显式重播入口；切换项目不会重复骚扰用户；
  - Archive 首批引导覆盖工作模式、资产树、编辑器、作者事务和候选 Gate，具体写入规则仍由 Studio API 与 Engine 下发；
  - 新增真实 Studio API 端到端测试，在完整临时工作项目中走通创建、结构化编辑、专家源文本往返、历史、影响失效、归档、恢复、候选审查、人工批准与 Worker 晋升；
  - 候选晋升使用真实 `character-and-world-assets` Engine route，完成标记、审查 digest、人工批准和正式投影均来自既有单一 Gate。
- Unified implementation boundary:
  - 引导只解释当前可执行动作，不复制 Engine schema、候选 Gate、稳定知识写入规则或 CLI 内部项目地图；
  - Archive 作者事务与 Agent 候选晋升在同一界面相邻呈现，但使用不同写入路径和不同审计证据；
  - 真实项目闭环通过公开 Studio API 完成，没有在测试里直接拼接正式资产或伪造 promotion receipt。
- Adaptive orchestration boundary:
  - Agent 只能生成候选、审查产物和 task completion；正式晋升仍由 Worker 调用 Engine；
  - Owner Override 不能伪装成 Agent 计划节点，也不能使未来 `CreativeExecutionPlan` 绕过 Stable Knowledge Gate；
  - 引导状态属于客户端体验状态，不参与 task lifecycle、计划完成度或正式作品事实。
- Verification evidence:
  - Archive authoring lifecycle E2E: passed；
  - Archive focused suite: 35 passed, 1 skipped；
  - Client full suite: 90 passed；
  - 真实项目 `1+1=2` 只读视觉验收通过，宽/窄视口的引导高亮、卡片定位和滚动均正常，浏览器无 error/warning；
  - Architecture Audit: 37 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W2 Exit Audit：Narrative Archive 与 Stable Knowledge 写入边界

- Status: complete
- Product exit:
  - 用户可以从 Archive 创建、结构化编辑或专家编辑主要资产，预览影响后以显式 Owner Override 提交；
  - 用户可以查看修订历史、归档、恢复，并对 Agent 候选执行独立审查、批准和正式晋升；
  - 多资产草稿、脏标签保护、冲突拒绝、窄屏布局和状态化引导均已进入生产前端资源。
- Engineering exit:
  - Registry、结构解析、引用检查和路径边界属于不可豁免的确定性约束；语义 waiver 不能跳过这些约束；
  - 关键人物变更会准确使依赖该人物的 Context Trace 失效，端到端测试已验证 `scene_0001` 的具体传播；
  - 候选晋升只经 Engine route；Archive UI、Studio API 和 Owner transaction 均未复制或弱化 promotion Gate；
  - 前端不解析 sidecar、不直接写 Stable Knowledge，也不拥有任意项目路径、Shell 或 task command；
  - Vue -> Studio API -> CoreBridge/Engine 的边界保持，Architecture Audit 未增加文件债务、函数债务或循环依赖。
- Full exit evidence:
  - Python full suite: 473 passed, 1 skipped；
  - Client full suite: 90 passed；
  - `python -m compileall -q src benchmarks scripts`: passed；
  - Client production build、typecheck、desktop frontend sync 和 v0.9 build verification: passed；
  - Architecture Audit: 37 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。
- Residual risks and deferred work:
  - Windows 当前环境不能创建测试用符号链接，因此相关安全用例跳过；确定性路径越界、稳定 ID 和真实路径边界用例仍通过；
  - 并发编辑当前采用 revision/digest 冲突阻断，不提供自动语义合并；自动合并在没有可靠三方合并和用户确认前不应进入正式写链；
  - rename/move/clone 和批量文件管理属于长期 Archive 扩展，不是统一实施方案定义的 W2 退出 Gate；
  - 状态化引导当前只在 Archive 首批落地，其他模块由 W7 的全产品引导批次处理。

## W3-1：Style Application 契约与安全版本投影

- Status: complete
- Commit: `5983462`
- Added:
  - 新增 `application/style/`，把 Style Atelier 的作者、作品、来源摘要、评测与版本读模型从 API router 和 legacy read model 中分离；
  - `RightsProjection` 明确区分已声明与缺失权利，不能仅凭作者名称推断授权；
  - 来源投影只公开稳定 ID、文件名、内容 SHA-256、字符数、分块数和导入时间，不公开语料正文、内部路径或训练上下文；
  - 评测投影把风格质量与原文泄漏风险拆成独立信号，高风格得分不能覆盖 `high_copy_risk`；
  - 当前 profile、Prompt 候选、确定性评测、built skill 和 active mount 被归一成只读版本状态与内容 hash；
  - 新增 `GET /style-lab/authors` 和 `GET /style-lab/versions`，旧 library/mount API 保持兼容；
  - Style 路由依赖装配移出 `create_app` 主体，未增加 app factory 或 service 复杂度债务。
- Unified implementation boundary:
  - Engine `literary/style` 继续拥有 Prompt 质量计量、评测算法、skill readiness 和正式 route；
  - Studio 只投影 Engine 已有事实，没有复制评测阈值为新的写入 Gate，也没有增加同步模型调用；
  - 新 API 不返回原文或评测候选全文，符合保留集隔离和必要短片段原则。
- Adaptive orchestration boundary:
  - 当前版本目录是只读证据，不是 `CreativeExecutionPlan` 的 Stable Knowledge 写入口；
  - Planner 将来只能引用 version/content hash，不能由计划候选伪造 review、mount 或 rights；
  - 本批未改变固定 `style-engineering` route、Worker、Runtime 或 task lifecycle。
- Exit evidence:
  - Python full suite: 476 passed, 1 skipped；
  - `python -m compileall -q src tests`: passed；
  - Architecture Audit: 37 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W3-2：受控作者、作品与来源事务

- Status: complete
- Commit: `8b1379b`
- Added:
  - 新增集中枚举的 `RightsMode` 与 `SourceMediaType`，Router、事务和测试不再各写一套权利/媒体字符串；
  - `POST /style-lab/authors`、`/works`、`/sources` 只接受稳定身份和受控字段，不接收目标目录或任意源文件路径；
  - 作者与作品采用不可覆盖创建；已占用身份返回稳定 `style_identity_conflict`；
  - 每份来源必须声明 public-domain、authorized、user-owned 或 craft-only 及具体权利依据，缺失声明被确定性拒绝；
  - TXT/Markdown 内容统一换行并拒绝 NUL、替换字符、异常尺寸和路径化文件名；
  - 来源使用规范内容 SHA-256 全库去重；重复语料返回已有稳定身份，不重复保存；
  - source manifest 升级记录 media type、content hash、原始显示文件名和逐来源 rights，不把正文写入收据；
  - 作者事务在 Engine 公共写入前先写 `prepared` 收据，成功转为 `committed`，异常转为 `failed` 并保留错误类型；
  - API 错误使用稳定 code/status，前端不需要解析任意异常文本。
- Unified implementation boundary:
  - Studio 复用 Engine 现有作者/作品/来源格式与公开函数，没有复制文风编译、Prompt、评测或挂载算法；
  - 本批不接受 DOCX 二进制；DOCX 需要正式读取器和结构证据，不能用临时文本猜测冒充支持；
  - 来源正文不进入 SQLite、列表投影、事务收据或模型日志。
- Adaptive orchestration boundary:
  - 这些接口是显式用户作者事务，不是 Planner 可自由调用的 Stable Knowledge 写入能力；
  - 将来 Agent 只能通过受控候选或 task package 提议来源处理，不能伪造 rights；
  - 本批没有改变 `style-engineering` route、Runtime、task lifecycle 或自动推进顺序。
- Exit evidence:
  - Python full suite: 480 passed, 1 skipped；
  - `python -m compileall -q src tests`: passed；
  - Architecture Audit: 37 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W3-3A：项目内正式文风工程会话

- Status: complete
- Commit: `daa0fd0`
- Added:
  - 新增 Engine 所有的 `style-engineering-session/v1`，把可复用文风资料库中的明确来源选择物化为作品项目内的受控正式会话；Worker 不再尝试把非工作项目的资料库根目录当成 route 根；
  - 训练来源与保留来源必须分别显式选择且集合不相交；每一项都绑定 author/work/source 稳定身份、规范内容 SHA-256 和逐来源权利声明；
  - 会话采用临时目录后原子重命名，重复相同请求按 request digest 幂等复用，已占用 profile 使用不同证据时稳定阻断；
  - `workflow_state_style` 同时识别尚未产生 profile 的 `style_session.json`，不再要求先手写 `style-profile.md` 才能进入正式 route；
  - 新会话的 `style-profile` 任务使用具体训练语料和输出目录，不再含 `<corpus>/<profile-dir>/<name>` 未决模板；保留集不会进入编译命令；
  - 保留集优先成为正式评测 reference；旧项目内 profile 继续保留 corpus reference 兼容行为；
  - `POST /style-lab/compile` 只准备会话并启动既有 Worker，返回 queued job，不在 HTTP 请求线程调用模型，也不返回 `pending_platform_agent`；
  - 真实 Worker 测试在隔离 sandbox 完成 session -> deterministic profile compile -> Engine Gate -> writeback，并进入下一 `style-prompt-task-file` 状态。
- Unified implementation boundary:
  - Engine `literary/style/session.py` 拥有会话、来源证据、训练/保留集隔离和摘要验证；Studio `task_service.py` 只准备受控意图并启动既有 Worker；
  - 仍只有一条 `style-engineering` route 和一套 task lifecycle；未新增 Studio 状态机、同步 LLM 路径或任意 Shell；
  - route 会话投影与通用 helper 被拆出主 definition，现有 route 文件从架构债务预算中退出，没有以 W3 功能扩展换取新的大文件债务。
- Adaptive orchestration boundary:
  - Style session 是用户明确选择来源后产生的受控执行会话，不是 Planner 可伪造的来源或 rights；
  - 将来 `CreativeExecutionPlan` 只能引用 session/request digest 并调度现有 style route，不能把训练文本、保留文本或权利判断写入计划事实；
  - 保留集不进入 Prompt Agent 的训练证据，后续独立 review 也必须使用不同 reviewer 会话。
- Exit evidence:
  - Python full suite: 483 passed, 1 skipped；
  - 真实 deterministic Worker style compile: passed；
  - `python -m compileall -q src tests`: passed；
  - Architecture Audit: 36 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W3-3B：独立文风语义审查与完整摘要门禁

- Status: complete
- Commit: `7c1b357`
- Added:
  - accepted deterministic evaluation 不再直接令文风路线 ready；Engine 新增 `style-review-task-file -> style-review-agent-task -> style-review-readiness/revision` 正式闭环；
  - 独立审查 JSON、Markdown、sidecar 与 completion 绑定当前 style session、source set、profile、metrics、prompt、prompt manifest、candidate、evaluation manifest、deterministic score 和 score report 摘要；
  - Reviewer session 必须与 Prompt Writer、Evaluation Writer 均不同；Agent 提供的伪身份、错误 schema、报告路径和摘要由 Studio Worker 预检绑定为当前任务与沙箱真实值；
  - 正式会话的 evaluation manifest 必须持有 prompt、reference、input、candidate 摘要和 Writer 身份；上游文件变化会使评测或语义审查失效；
  - `pass_with_notes` 不在合法 verdict 中；存在 required changes 时只能 `revise` 或 `block`，修订必须改变声明的上游目标并重新完成确定性评测和独立审查；
  - Reviewer task 使用精简安全资料集，不包含原始 holdout 正文；任务约束明确禁止输出隐藏思维链，只保留结论、发现、必要修改和证据限制；
  - 新增三个 exact Prompt Assets，并令 Prompt Registry 递归检查拆分后的 route 模块；
  - Style CLI parser、handler、review contract 和 Studio preflight metadata 分别拆到专属模块，新增门禁未扩张已有巨型 parser、project handler、route definition 或 canonicalization 文件。
- Unified implementation boundary:
  - Engine `literary/style/review.py` 拥有正式审查契约、证据摘要和 readiness 判定；route 只声明状态蓝图与活动 Gate；
  - Studio Worker 只规范化机器拥有的 schema、摘要、路径和会话身份，不改变 Reviewer 的文学判断、findings 或 required changes；
  - 未新增同步 HTTP LLM、任意 Shell、第二套状态机或 Studio 自有文风 Gate；所有执行仍通过既有 task lifecycle。
- Adaptive orchestration boundary:
  - 将来 Planner 只能调度此独立审查节点，不能删除 Gate、指定与 Writer 相同的 Reviewer 或将自己的计划摘要当作正式审查证据；
  - 文风审查结论属于 Derived Knowledge；只有通过后续 W3-3C 确定性 build 才能形成可引用版本；
  - holdout 正文、隐藏审查推理和未绑定模型输出均不能进入 Creative Execution Plan 或 Stable Knowledge。
- Failure and verification evidence:
  - 专项 64 tests 覆盖正式评测、任务服务、预检、任务运输与 Prompt 质量；
  - 回归测试证明上游 Prompt 变化会把 ready 路线退回过期审查准备态；
  - 回归测试证明 Worker 会覆盖伪造 Writer/Reviewer 身份、报告摘要和 evidence，并保持三会话独立；
  - 回归测试证明 Reviewer task 不包含 holdout 正文，且只暴露声明的安全资料；
  - Python full suite: 484 passed, 1 skipped；
  - Prompt Registry: 46 assets, 81 task prompt ids, passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: 36 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W3-3C：不可变 StyleProfileVersion 构建与物化

- Status: complete
- Commit: `93dd64e`
- Added:
  - Engine 新增内容寻址的 `StyleProfileVersion`；版本身份由 builder、style/session 身份、来源权利与摘要、Prompt 质量、确定性评测证据、独立语义审查及 completion 摘要共同计算，Agent 不能自报版本号或正式路径；
  - 只有当前 formal session、500-2500 汉字内容 Prompt、完整 Prompt/Evaluation sidecar、exact accepted score 与 exact passing independent review 同时有效时，版本才可构建；
  - `build-style-version` 是受 Route Blueprint 管理的确定性 CLI/Worker 任务，不调用 Runtime、LLM 或任意 Shell；输入和全部输出均由机器声明；
  - 版本目录使用临时目录完整物化后原子重命名；相同内容幂等复用，非空或摘要不匹配的既有版本进入显式 `style-version-conflict` 人工边界，不能静默覆盖；
  - `style_version.json` 保存稳定身份、来源权利、Prompt 质量、评测/审查证据和逐产物 SHA-256；完整性检查会重算每个包内文件；
  - 版本包不复制训练语料或 holdout 正文，只保存来源身份、摘要、权利、Prompt、指标、评测和审查结论；
  - 同时物化旧 `style_skill.json`、`STYLE.md` 与既有目录形状，已通过旧 `mount_style_skill()` 兼容测试；
  - 正式 style route 在独立审查后进入 `style-version-build`，构建完成才 ready；旧式无 formal session 的 profile 保持原兼容状态。
- Unified implementation boundary:
  - Engine `literary/style/version*.py` 独占版本身份、构建格式、完整性与冲突规则；route 只声明状态、读写集与验证；
  - Studio Worker 只执行 Engine 下发的确定性任务，没有第二套版本服务、同步模型调用或 HTTP 内构建；
  - package renderer 与 version contract 被拆分，Architecture Audit 未新增文件债务、函数债务或依赖环。
- Adaptive orchestration boundary:
  - `StyleProfileVersion` 是通过正式 Gate 后形成的可引用 Derived Knowledge；Planner 将来只能引用 `style_id/version_id/content_hash`；
  - Planner 不能 build、修改、覆盖或 mount 版本，也不能把计划文本、未经独立审查的 Prompt 或 holdout 正文当作正式版本；
  - 本批未实现 mount、项目激活或前端管理，避免把版本构建与 Stable Knowledge 写入混为一个可绕过动作。
- Failure and verification evidence:
  - Reviewer JSON/报告/completion 内容参与版本身份；Reviewer 摘要变化会产生不同 content hash 和 version ID；
  - Prompt 在语义审查后变化会使构建 Gate 失效，不能包装过期审查；
  - 已存在版本被篡改时，重建稳定抛出 immutable conflict 并使 route 进入人工边界；
  - 真实 deterministic Worker 构建、重复幂等构建、包摘要完整性和旧挂载兼容均通过；
  - Python full suite: 488 passed, 1 skipped；
  - Prompt Registry: 48 assets, 83 task prompt ids, passed；
  - `python -m compileall -q src tests`: passed；
  - Architecture Audit: 36 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W3-3D：正式版本应用边界与受控构建

- Status: complete
- Commits: `57065a9`, `5ccc62a`
- Added:
  - Engine 新增对任意历史版本目录的自包含完整性检查；检查不依赖当前 profile 状态，会重算内容寻址身份、逐产物摘要、未声明文件、兼容清单、Prompt 质量、来源权利和正式审查证据；
  - Studio 新增安全版本目录与详情投影；即使文风外部资料库不存在，项目内已构建版本仍可作为历史证据展示，新一轮 profile 计划也不会覆盖旧版本；
  - 版本投影只公开稳定 ID、内容 hash、来源 hash/rights 状态、质量指标、评测摘要、审查状态、优先级和产物摘要，不公开训练/保留集正文、权利声明原文或内部绝对路径；
  - `GET /style-lab/versions/{style_id}/{version_id}` 提供受稳定身份约束的详情查询；包内出现未声明文件时投影为 integrity conflict，不把受污染版本标记为可挂载；
  - `POST /style-lab/build` 只接受项目、作者和 profile 稳定 ID，通过 Engine 解析正式会话并计算 exact current version；调用方不能提交目标路径、版本号或自报 Gate 结果；
  - exact version 已存在时幂等返回 ready；尚未通过全部 Gate 或存在不可变冲突时返回稳定错误且不启动 Worker；
  - 可构建版本只通过既有 `style-engineering` Worker 运行确定性 Engine 任务；HTTP 请求不直接 build，构建任务不启动 Agent Runtime 或模型。
- Unified implementation boundary:
  - Engine `literary/style/version*.py` 继续唯一拥有版本身份、完整性和构建 Gate；Studio 只拥有受控意图、Job 启动和安全投影；
  - Engine 不导入 Studio，Studio 未复制版本算法、评测阈值或挂载规则；API route 拆分后没有突破文件/函数债务基线；
  - W3-3D 没有修改项目挂载、激活状态或正文生成链，避免把 Derived Knowledge 构建与 Stable Knowledge 写入合并为一个动作。
- Adaptive orchestration boundary:
  - 未来 Planner 只能引用安全投影中的 `style_id/version_id/content_hash`，不能制造版本、声明 ready、修复 integrity conflict 或调用任意路径；
  - build 是确定性正式任务，不是 Planner 的创意输出；未通过独立审查的 profile 不能因计划要求而被构建；
  - 历史版本保持不可变和可审计，当前 profile 的新计划不会让旧版本从项目事实中消失。
- Failure and verification evidence:
  - 回归测试覆盖历史版本保留、未声明包文件冲突、安全投影无正文/路径泄漏、缺失 profile 稳定错误、not-ready 不启动 Worker和重复构建不重复排队；
  - 真实 API -> Job Supervisor -> AgentWorker -> deterministic Engine -> version catalog E2E 通过，并断言确定性 build 不会创建模型 Runtime；
  - 从来源事务、正式会话、Prompt/评测、独立审查到版本构建由跨阶段测试矩阵覆盖；当前没有把这些 Agent 阶段伪装成一个单体模型 E2E；
  - Python full suite: 496 passed, 1 skipped；
  - Prompt Registry: 48 assets, 83 task prompt ids, passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: 36 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W3-3 Exit Audit：不可变文风版本

- Status: complete
- Rights and corpus isolation:
  - 每份来源必须有明确 rights mode、basis 和内容 hash；版本只保留身份、摘要与权利证据，不复制训练文本或 holdout 正文；
  - 训练集与保留集在会话创建时强制不相交，Prompt Writer 不读取 holdout，Reviewer 也只读取精简证据摘要。
- Independent judgment:
  - Prompt Writer、Evaluation Writer 与 Reviewer 使用不同会话身份；
  - `pass_with_notes` 不可冒充通过，required changes 必须进入 revise/block，Prompt 或证据变化会使旧 review 失效。
- Immutability and compatibility:
  - 版本身份由正式证据内容寻址，原子物化、幂等复用、冲突拒绝和包内文件重算均已验证；
  - 旧 `style_skill.json`、`STYLE.md` 和既有 mount 读取形状仍兼容；历史版本可在新 profile 计划出现后继续独立检查和展示。
- Architecture and operation:
  - 只有一条 `style-engineering` route、一套 task lifecycle 和一个确定性版本实现；Studio 没有第二套文风状态机；
  - 长任务经 Job/Worker/Observability，HTTP 不同步调用模型或执行构建；
  - W3-3 正式退出不包含 mount、activation、正文消费和 Style Atelier 前端，这些属于 W3-4 至 W3-6。
- Exit gate:
  - W3-3A 至 W3-3D 的功能、失败反例、全量测试、Prompt Registry、架构审计和差异检查全部通过；
  - 当前残余风险是尚未证明 compose/generate/revise/review 消费同一 mounted hash，也没有对版本升级导致的 stale propagation 做正式验收。

## W3-4A：不可变文风版本项目挂载

- Status: complete
- Commit: `37aa828`
- Added:
  - Engine 新增 `mount_style_profile_version()`；正式挂载只接受 `style_id/version_id/content_hash`、项目作用域和固定最高优先级，不接受调用方源路径、目标路径或 `allow_unreviewed`；
  - 挂载前从项目内正式 profile 版本目录解析唯一版本，并重算包内完整性、内容 hash 和稳定身份；版本缺失、被篡改、hash 不匹配或身份重复时拒绝激活；
  - 版本先复制到同目录临时 staging，完整性复验后再原子重命名到 `style/mounted/{style_id}/{version_id}`；
  - `active_style_skill.json`、挂载审计回执和 `project.yaml` style block 通过同一原子写入批次提交；元数据提交失败时清除本次新复制的 mount，不留下半完成激活；
  - active manifest 和 receipt 保存 exact `style_id/version_id/content_hash`、scope、priority、mount path、review/readiness 摘要和前后版本身份，不保存语料、holdout 正文或外部绝对路径；
  - 同一有效版本重复挂载幂等返回，不重复写回执；已挂载副本被篡改时 active projection 进入 integrity conflict 并禁用 prompt；
  - 旧式无 version/hash 的 active manifest 保持可读，但明确标记为 `legacy-unverified`，不会被误判为不可变版本挂载。
- Unified implementation boundary:
  - `literary/style/mount*.py` 分离意图契约、历史版本解析、项目物化和用例编排；Engine 不导入 Studio，也不调用 Agent、模型或 HTTP；
  - 挂载复用 W3-3 的唯一版本完整性检查与既有原子 IO，没有复制版本算法、评测阈值或项目状态机；
  - 本批没有提前修改 Studio 决策面、正文 Prompt 或前端，避免一次提交同时跨越激活、消费和产品交互边界。
- Adaptive orchestration boundary:
  - Planner 只能提出稳定版本身份；Engine 重新验证后才可执行挂载，Planner 不能提供文件路径、降低优先级、开放未审查版本或伪造成功状态；
  - 挂载属于确定性 Stable Knowledge 写入事务，不由创作 Agent 自由生成；
  - 版本升级留下 previous/current 审计身份，为后续 plan stale 与下游任务失效提供机器证据。
- Failure and verification evidence:
  - 回归覆盖 exact mount、幂等复用、错误 hash、源版本篡改、已挂载副本篡改、元数据写入失败回滚和旧读取兼容；
  - Python full suite: 500 passed, 1 skipped；
  - Prompt Registry: 48 assets, 83 task prompt ids, passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: 36 existing file debts, 228 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。
- Not yet complete:
  - Studio 尚未提供只接受稳定版本身份的受控挂载 API，旧决策/自动推进仍需迁移；
  - compose/generate/revise/review 尚未绑定同一 machine-owned mount snapshot；
  - 版本切换后的上下文与正式下游任务 stale propagation 尚未完成端到端验收。

## W3-4B：Studio 受控挂载入口与决策链迁移

- Status: complete
- Commit: `beb9fda`
- Added:
  - Studio 新增 `StyleMountApplicationService`，只把项目根和 exact `style_id/version_id/content_hash`、scope、priority 交给 Engine W3-4A 唯一挂载事务；没有复制版本发现、完整性、评测或原子写入算法；
  - `POST /style-lab/mount` 不再接受 `style_library_root`、调用方路径或 `allow_unreviewed`；Pydantic DTO 禁止额外字段，scope/priority 最终仍由 Engine 枚举验证；
  - API 将版本缺失映射为 404、不可变版本/hash/完整性冲突映射为 409、非法挂载意图映射为 422，并返回稳定 code 与用户可见 message；
  - `GET /style-lab/mounts` 改用安全挂载投影，只公开状态、稳定身份、审查/完整性和执行优先级，不泄露项目绝对路径；
  - Engine 文风决策卡只扫描项目内已构建且完整性通过的不可变版本；每个选项携带 exact 三元身份，未构建的 Prompt、旧散装 skill 和损坏版本不再作为正式选项；
  - human choice 安全记录保留文风选项的稳定身份字段；调用者选中未声明 option 时，application service 在进入 Engine 前拒绝；
  - 前端结构化选择和 Creative Steward 现在都通过同一 `record_choice -> StyleMountApplicationService -> Engine mount transaction` 物化；Steward 不再执行第二次旧式挂载；
  - 成功物化会 finalize 并消费决策卡，审计证据同时记录 active manifest 与 mount receipt；失败的选择保持未消费，可在问题修复后按相同身份重试。
- Unified implementation boundary:
  - Studio 写入副作用从旧 read-model 主函数拆到 `application/choice_effects.py`；文风选项扫描从通用 choices 拆到 Engine `projections/interaction/style_choices.py`；
  - `api_server.py` 只装配无状态 mount application service，handler 不直接写文件；Engine 仍不导入 Studio；
  - 旧 `core_read_models.mount_style()` 与 legacy Engine mount API 暂时保留兼容，但 Studio 正式 API、人类决策和 Autopilot 已不再调用。
- Adaptive orchestration boundary:
  - Steward 只能从 CLI/read-model 声明的 exact version options 中选择，不能提交路径、任意 hash 或未审查版本；
  - 文风挂载仍是受控 Stable Knowledge 事务；自动授权只替代用户选择，不替代 Engine 完整性与审查 Gate；
  - 挂载收据成为未来 plan provenance 和 stale propagation 的正式输入。
- Failure and verification evidence:
  - 回归覆盖调用方路径字段拒绝、hash 冲突稳定错误、未声明选项拒绝、API exact mount、挂载状态无绝对路径、决策卡消费及 Steward 单次受控物化；
  - Python full suite: 504 passed, 1 skipped；
  - Client: 90 tests passed；TypeScript check 与 production build passed；
  - Prompt Registry: 48 assets, 83 task prompt ids, passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: 36 existing file debts, 227 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。
- Not yet complete:
  - compose/generate/revise/review 仍需显式保存并验证同一个 machine-owned mount snapshot；
  - 版本切换尚未对依赖旧 mount hash 的 Context、Composition、Generation、Revision 和 Review 形成统一 stale 原因与重发链；
  - Style Atelier 的版本选择/切换界面属于 W3-5/W3-6，本批未提前建设。

## W3-4C：统一文风快照、失效传播与 Historical Truth

本批开始前重新读取了统一实施方案 W3、长期文风路线、自适应创作编排方案、模块边界和本文件。W3-4C 只实现统一 mount snapshot 与版本切换失效传播：

1. 先审阅 Context Broker、Prompt Pack、Composition、Generation、Revision、AgentReview 当前文风读取点和各自正式 manifest，禁止给四阶段各造一套版本字段。
2. 新增 Engine-owned `StyleMountSnapshot`，至少包含 `style_id/version_id/content_hash/prompt_sha256` 和 snapshot digest；只从通过完整性检查的 active mount 生成。
3. Context trace、composition manifest、generation prompt/candidate manifest、revision manifest 和 review 证据必须保存同一 snapshot digest；任何阶段不得只保存路径或 display style ID。
4. 新挂载版本后，依赖旧 digest 的未晋升 Context/Composition/Generation/Revision/Review 统一进入 machine-owned stale；已晋升正文保持 Historical Truth，不自动重写。
5. Prompt reader 遇到 versioned active mount integrity conflict 时必须 fail closed，不能退回旧 prompt 或项目散装 style 文件。
6. 用真实 scene chain 覆盖同一 hash 消费、挂载切换、stale 重发和已晋升正文不变；本批仍不建设前端。

### 完成证据

- Engine 新增唯一的 `StyleMountSnapshot` 契约，Context trace、Composition、Generation prompt/candidate、Revision prompt 和 AgentReview 均保存同一 exact version/hash/digest，不再只传 display ID 或路径。
- Context、Composition、Generation、Revision 与 Review 的正式 Gate 统一比较 machine-owned snapshot；挂载切换后，未晋升产物进入可解释的 stale，损坏的 versioned mount fail closed。
- Promotion 现在封存 `historical_evidence`：候选正文、晋升正文、生成 Gate、独立 Review Gate 和 exact style snapshot 均有内容摘要；验证不与未来 active style 比较，但会拒绝路径逃逸、正文/候选篡改、Gate 证据篡改、debug bypass 和错误 scene identity。
- Workflow state 与 route audit 只对通过防篡改验证且尚未被新候选替代的晋升记录投影 Historical Truth；RP、分支、状态、Canon、Continuity 等无关门禁不会被顺带豁免。
- 新候选晚于 promotion manifest 时，旧 Historical Truth 不再充当当前候选，正式路线重新进入该候选的生成、Review 与晋升闭环。
- 新增真实场景链与晋升证据回归，覆盖同一 snapshot 传播、挂载切换 stale、历史证据保留、候选/正文篡改阻断、新候选重开路线以及 legacy promotion 安全回退。
- Verification:
  - Python full suite: 511 passed, 1 skipped；
  - focused style/promotion/workflow suite: 51 passed；
  - Prompt Registry: 48 assets, 83 task prompt ids, passed；
  - `python -m compileall -q src`: passed；
  - Architecture Audit: passed, no new violation；
  - `git diff --check`: passed。

### 边界

- Historical Truth 只证明“该正文在当时通过正式生成与独立审查后被晋升”，不允许修改当前 Canon、人物状态或未来文风，也不替代晋升后的 static review/state/canon/continuity 链。
- 旧版 promotion manifest 缺少 `historical_evidence` 时继续走原有当前 Gate 校验，不自动追认历史有效性。
- 本批没有建设 Style Atelier 前端，也没有提前实现 W4 Project Archaeology 或自适应任务 DAG。

## W3-5A/W3-5B：Style Atelier 工作台投影与客户端骨架

- Status: complete
- Commits: `22f454b`, `5d976e3`
- Added:
  - Studio `StyleApplicationService.workbench()` 和 `GET /style-lab/workbench` 把作者、作品、来源权利、文风抽象、隔离评测、独立审查、不可变版本和当前挂载组合为单一用户工作台投影；
  - 投影不公开绝对路径、来源原文或内部运行参数；公共文风资料库缺失时保持安全空状态，并继续显示作品内正式版本；
  - Vue 新增独立 `style-atelier` feature，包含 typed contract、API client、Pinia store、来源谱系、六阶段证据链、版本架和版本证据区；
  - 一级导航新增“文风工坊”，项目路由保护同步覆盖该页面；初始焦点优先选择证据最完整的作者，并保持作者、作品与版本上下文一致；
  - 唯一视觉签名为“文风证据织机”，用真实来源、评测、审查、版本和挂载状态构成进度链；没有把内部 JSON、文件路径或超长 hash 暴露为主要界面内容；
  - 页面采用现有多主题 instrument tokens，在 720px 窄屏下按来源、证据、版本顺序重排，并保持整页与版本区无横向溢出。
- Unified implementation boundary:
  - Vue 只消费 read model 和版本详情，不复制评测、完整性、可挂载性或版本选择算法；
  - Engine 继续拥有不可变版本与挂载真相，Studio application service 只做安全投影，API router 只装配依赖；
  - 本批为只读客户端骨架，没有把创建、编译、构建、挂载或 Agent 调用直接塞进页面。
- Adaptive orchestration boundary:
  - 工作台显示真实阶段状态，不根据文件存在性伪造“完成”；
  - 未来长任务必须继续通过 Worker/job/observability 执行，页面不能同步等待模型或自行写正式资产；
  - 未来挂载仍只提交 exact stable identity，并由 Engine 重新验证。
- Failure and verification evidence:
  - Store 回归覆盖 workbench 加载、已挂载版本优先、版本证据详情和未构建版本不误取详情；
  - Client: 92 tests passed；
  - TypeScript check、Vite production build、desktop frontend sync 和 v0.9 build verification passed；
  - Architecture Audit: 36 existing file debts, 227 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed；
  - 真实开发服务和“1+1=2”项目完成宽屏、720px 窄屏截图验收；版本长标识不再产生横向滚动，页面 `body/shell/version rack` 的 `scrollWidth == clientWidth`。

## W3-5C/W3-6：受控文风工程、精确挂载与 W3 Exit Audit

- Status: complete
- Commits: `b5066fd`, `ac1eb4d`, `a359400`, `2d6e114`, `6c93403`
- Added:
  - Style Atelier 现在可受控建立作者和作品、声明来源权利并导入文本；来源正文只进入 Engine 管理的不可变证据，不在工作台、任务状态或挂载预览中回显；
  - 编译、评测、独立审查和构建继续通过正式 `style-engineering` task、Worker/job 与 Agent Runtime 执行；客户端只启动任务并通过 SSE 观察真实 queue/running/writeback/complete/failed 状态；
  - Worker 控制台支持写回批准或拒绝、停止、失败后重试和按正式 route 状态继续推进；任务到达真实终态后才按 revision 刷新工作台，不用固定轮询伪造进度；
  - Engine/Studio 新增 exact version 挂载预览：比较当前与目标不可变版本的安全证据，并投影依赖旧 mount snapshot 的未晋升场景、阶段和产物数量；
  - 已晋升正文通过 Historical Truth 验证从 stale 影响中排除；界面明确说明历史正文保留，不把版本切换解释为自动重写；
  - 挂载确认必须重新提交 exact `style_id/version_id/content_hash` 与最新 `preview_revision`；预览缺失、过期或目标发生变化时事务 fail closed；
  - Style Atelier 增加紧凑的版本挂载面和确认窗口，显示版本证据差异、未晋升场景刷新范围及历史正文边界；未构建、冲突或缺失稳定身份的版本不会出现可用挂载动作。
- Unified implementation boundary:
  - Vue 只消费 typed read model、Worker SSE 与挂载应用服务，不复制可挂载性、历史晋升验证或 stale 计算；
  - Studio `application/style/` 只组合安全比较、影响投影和 Engine 唯一挂载事务；API router 只校验 DTO、映射稳定错误并装配服务；
  - Engine 继续拥有不可变版本、完整性、评测、审查、mount snapshot 和 scene stale 真相；没有引入第二套文风状态机或同步模型调用。
- Adaptive orchestration boundary:
  - 文风创意判断仍由正式主 Agent 在 CLI task package 内完成；客户端和 Worker 不以启发式文本替代评测或审查；
  - 自动授权或人工确认都不能删除 review、integrity、exact identity 和 preview revision Gate；
  - 来源导入、Agent 长任务、写回和挂载分别保留稳定 transaction/job/task/mount receipt，可作为后续计划 provenance 和 stale 重发证据。
- Browser evidence:
  - 最新 Studio API 在 `127.0.0.1:8791` 启动并通过 health；开发客户端在真实项目“1+1=2”上读取最新 Style Atelier 投影；
  - 文风工程控制台、来源证据、版本证据和挂载区均显示为用户可读状态，没有原始来源、绝对路径或内部 JSON 泄漏；
  - 1280×720 实际页面滚动到挂载区后，挂载控件保持 516×48 的稳定尺寸，版本证据区完整可见，页面无横向溢出；
  - 当前真实项目尚无已审构建版本，因此没有为视觉演示而运行模型或篡改项目；确认窗口由组件测试和 exact transaction Store 测试验收。
- Exit evidence:
  - Python full suite: 513 passed, 1 skipped；
  - Client full suite: 97 passed；
  - TypeScript check、Vite production build、desktop frontend sync 和 v0.9 build verification passed；
  - Prompt Registry: 48 assets, 83 task prompt ids, passed；
  - `python -m compileall -q src benchmarks scripts tests`: passed；
  - Architecture Audit: 36 existing file debts, 227 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。

## W4-1：Project Archaeology 确定性源证据纵向切片

- Status: complete
- Commit: `71826fa`
- Added:
  - Engine 新增不可变 `SourceDocument`、`SourceRange`、`SourceSegment`、`SourceEvidenceRef` 和 `SourceChunk` 契约；source-ingest 新导入升级为 v2，同时保留 v1 route/state 读取兼容；
  - TXT 与 Markdown 使用严格 UTF-8 读取和稳定段落/标题边界；DOCX 使用标准库 OpenXML 读取正文、标题层级、段落样式、表格文本和被引用脚注，不引入额外二进制或第三方解析依赖；
  - 原始输入字节和标准化提取文本分别不可变保存并记录 SHA-256；manifest 只保存项目相对路径，不泄露用户绝对路径；
  - 确定性分段保留卷、章、节、段落、场景分隔和脚注，chunk 以 source/结构/目标大小为边界并携带 exact segment/evidence 引用；
  - `evidence_index.json` 保存 source、range、segment、字符/段落范围、hash、extractor version 和确定性 confidence；正式 Gate 校验原文、提取文本、range/segment/evidence、chunk 引用、计数与 import revision；
  - 覆盖导入通过 `.importing` staging 和 `.backup` 事务提交；解析或写入失败时旧导入保持不变，启动新导入前可恢复中断备份；
  - sidecar writer 增加可选逻辑身份路径，使 staging 中生成的任务仍绑定最终正式 task/completion 路径；
  - CLI 新增 `--rights-declaration`，并明确支持 TXT/Markdown/DOCX 与语义 chunk；source-ingest task package 只指示 Agent 读取实际获准的 `project.yaml`、manifest、报告、evidence index 和 chunks。
- Unified implementation boundary:
  - `projects/source_ingest.py` 保持兼容 facade；reader、分段、证据和事务实现全部位于 `literary/ingest/`；
  - reader 不做文学事实推断，evidence 不做实体合并，route 不直接晋升 Canon；Agent 生成的人物、世界、情节和文风仍只进入候选输出；
  - 本批没有建设第二套 Archive、任务系统、模型调用或前端流程。
- Adaptive orchestration boundary:
  - task package 的可见 source paths 与 Worker 沙箱读取集一致，不再要求 Agent 读取未暂存的整个项目；
  - evidence ID 和范围由机器拥有，Agent 只能引用，不能自造或改写；
  - v2 manifest/evidence 破损时 workflow state 与 route gate fail closed，不让反推任务在伪证据上继续。
- Failure and verification evidence:
  - 新回归覆盖多文件稳定顺序、Markdown 标题、DOCX 正文/表格/脚注顺序、权利声明、相对路径、原始与提取 hash、range/evidence 篡改、chunk 引用、sidecar 正式身份和失败覆盖回滚；
  - Python full suite: 517 passed, 1 skipped；
  - Client full suite: 97 passed；
  - TypeScript check、Vite production build、desktop frontend sync 和 v0.9 build verification passed；
  - Prompt Registry: 48 assets, 83 task prompt ids, passed；
  - `python -m compileall -q src benchmarks scripts tests`: passed；
  - Architecture Audit: 36 existing file debts, 226 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。
- Not yet complete:
  - Agent 候选实体尚未使用统一机器 schema，别名/共指、同名消歧和跨 chunk fan-in 尚未实现；
  - 事件时间约束、因果冲突、多解释保留和领域级候选复核尚未进入正式 route；
  - 候选项目重建、Archive 批量晋升、四种产品模式和 Archaeology 前端仍属于后续 W4 批次。

## W4-2A：实体、事件、别名与冲突机器合同

- Status: complete
- Commit: `de86887`
- Added:
  - `arcvellum/project-archaeology-chunk-extraction/v1` 统一块级实体、事件、关系和主张合同；候选、属性与时间约束都必须绑定当前 chunk 的 evidence refs、confidence、unknowns 和 contradiction notes；
  - 同名只形成 unresolved alias hypothesis，不自动合并身份；跨 chunk occurrence 使用 namespaced reference，避免局部 candidate ID 相撞；
  - 确定性冲突发现覆盖同名身份歧义、同一主张的多值替代、Agent 声明矛盾和 before/after 时间环；所有替代保留，不按多数表述选真值；
  - fan-in aggregate 明确区分 expected、received、missing、invalid chunk，并在不丢失有效局部工作的前提下 fail closed。
- Boundary:
  - schema、别名归一、时间约束和冲突检测归 `literary/ingest/`；不创建第二套 Archive 资产身份，不写 Canon；
  - 本批只建立可验证聚合合同，不把确定性词法相似误称为共指决议。

## W4-2B：Chunk Agent Task、Worker Preflight 与正式 Fan-In

- Status: complete
- Commit: `2f88888`
- Added:
  - 每个稳定 source chunk 获得独立 `.agent_tasks.md`、语义 JSON 和 completion receipt；workflow state 一次暴露一个未完成 chunk，为后续安全 fan-out 保留独立工作单元；
  - Studio 任务包只向 Agent 暴露 `project.yaml`、manifest、evidence index 和当前 chunk；sidecar、完整控制读集与 completion receipt 留在 Worker 控制面；
  - schema、work/chunk identity、source path/hash、evidence revision 和 status 收归 Worker canonicalization；Agent 只提交实体、事件、关系、主张与证据判断；
  - 新增 `archaeology-aggregate` 确定性命令和精确 Prompt Asset；所有 chunk 与 receipt 通过后才进入 fan-in，aggregate 必须与当前 chunk 输出逐字可重建；
  - source-ingest route 拆为 `blueprints.py`、`gates.py`、`support.py`，事务位置准备归 ingest importer，未增加大文件、复杂函数、依赖环或第二套状态机；
  - 真实 deterministic Worker 测试证明控制沙箱会携带 source chunks、提取结果和 receipts，命令无需 Agent Runtime 即可生成并写回 ready aggregate。
- Verification:
  - Python full suite: 524 passed, 1 skipped；
  - focused archaeology/route/preflight/Worker suite: passed；
  - Prompt Registry: 50 assets, 85 task prompt ids, passed；
  - `python -m compileall -q src tests`: passed；
  - Architecture Audit: 36 existing file debts, 226 existing function debts, 0 cycles, no new violation；
  - `git diff --check`: passed。
- Not yet complete:
  - aggregate 仍是证据 occurrence 与冲突集合，不是可晋升的候选项目；
  - 全书 alias/coreference 的语义复核、分领域重建 review、四种产品模式和 Archive 候选晋升尚未完成；
  - Project Archaeology 前端、恢复/中断矩阵和 W4 Exit Audit 尚未完成。

## 下一批

W4-2B 已通过。下一批进入 W4-3“候选项目重建与 Archive 晋升边界”：

1. 审阅现有 Archive candidate registry、promotion route、stable asset identity 和 revision receipt，只复用正式写入路径。
2. 以 ready aggregate 为唯一全书证据输入，新增 reconstruction candidate schema；人物、世界、时间线、情节、承诺和文风观察按领域分离。
3. 把 alias/coreference resolution 与 conflict review 设计为显式 Agent task，任何未决集合继续保留，不能为了生成项目文件而强行闭合。
4. 将已通过分领域 review 的 reconstruction materialize 为现有 Archive 候选，不直接写正式资产；用户或正式审批仍通过原 promotion Gate。

## W4-3：候选项目重建、领域审查与 Archive 候选边界

**状态：完成。**

- `source-ingest/v2` 在 deterministic fan-in 之后新增三项正式平台 Agent 任务：
  - 全书 alias/coreference 与冲突逐项解析；
  - 面向 `continuation`、`rewrite`、`adaptation`、`analysis` 模式的候选项目重建；
  - character、world、plot、style、promise 五领域独立审查和逐资产决策。
- 三类任务都拥有独立 Prompt Asset、显式 `agent_source_paths`、系统拥有的 schema/revision 字段、Worker canonicalization 和 deterministic preflight；Agent 不负责猜测来源 revision 或物化路径。
- identity resolution 必须覆盖每个 entity occurrence 与 aggregate conflict 恰好一次；`unresolved`、`partial` 和 `keep_distinct` 是正式结果，不会被多数表述静默合并。
- reconstruction 中的每个候选资产必须：
  - 使用现有 Archive 注册类型与 schema；
  - 提供稳定 `candidate_id`、evidence refs、confidence 和 unresolved refs；
  - 与当前 aggregate 和 identity revision 精确绑定；
  - 在 `analysis` 模式保持 `analysis_only`。
- domain review 必须完整覆盖五个领域与每个候选资产；`pass` 不能保留 blocker，带 blocker 的资产不能获得 `promote`。
- `archaeology-materialize` 是 deterministic CLI 步骤：
  - 只物化 reconstruction recommendation 与 domain decision 均为 `promote` 的资产；
  - 只写既有 Archive candidate registry 声明的目录；
  - 不直接写 Canon、人物正式档案、大纲、场景、正文或发布产物；
  - 重复执行在输入不变时保持字节级幂等；
  - 既有同 ID 候选内容不同时拒绝覆盖，要求新 candidate ID。
- materialized candidate 继续进入既有 Archive 生命周期：exact-content independent review → 当前内容批准 → shared promotion transaction。共享 Gate 会重验 archaeology provenance；源证据、aggregate、identity、reconstruction 或 domain review revision 改变后，旧候选自动 stale。
- `analysis` 模式通过完整的 analysis-only domain review 后直接 route-ready，不创建 promotable Archive candidate。
- 工程边界：
  - 资产注册常量独立于 `workshop` 与 promotion 副作用；
  - 候选记录构造、来源新鲜度、磁盘事务和 route orchestration 分层；
  - source-ingest reconstruction blueprints 从主蓝图表拆出；
  - 未引入第二套 Archive、Provider、Runtime、写回协议或正式资产身份。

验证：

- `python -m unittest discover -s tests`：`528` tests passed，`1` skipped；
- Project Archaeology / Worker preflight / Archive promotion / task transport focused suite：通过；
- `python scripts/architecture_audit.py`：通过，`0` 新增 file/function debt，`0` import cycle；
- `python -m literary_engineering_studio_engine prompt-registry-validate --json`：通过，`54` assets、`89` task prompt IDs；
- `python -m literary_engineering_studio_engine archaeology-materialize --help`：通过；
- `python -m compileall -q src tests`：通过。

尚未越界宣称：

- W4 的四模式差异化恢复策略、Studio Archaeology 前端、长任务中断/恢复矩阵与 W4 Exit Audit 仍未完成；
- 候选项目进入 longform planning 的真实用户路径将在 W4 Exit Audit 中做隔离项目验收；
- 本批没有提前实现 W5 Capability Broker、Pi/Ollama/新增 Provider 或 W6 自适应 DAG。

## W4-4：Project Archaeology 应用服务与安全读模型

**状态：后端完成，等待 W4-5 前端与 Exit Audit。**

- 新增独立的 Archaeology 应用层：
  - 支持 TXT、Markdown、DOCX 上传，要求显式权利声明、单一内容载体、受控扩展名、1,000-20,000 chunk size 和 25 MB 单源上限；
  - 上传内容只进入临时文件，再委托 Engine `ingest_existing_work()` 原子事务；Studio 不复制分块、证据或 route 逻辑；
  - continuation、rewrite、adaptation、analysis 四种模式拥有面向普通用户的中文意图说明。
- 新增路径安全的工作台读模型：
  - 显示源文本保全、结构分割、分块理解、身份解析、项目重建、领域审查和候选入档旅程；
  - 投影来源、分段、实体别名、冲突、重建资产、晋升队列、证据数量和中断恢复信号；
  - 不返回项目绝对路径、原始 sidecar Markdown 或裸 workflow JSON；
  - `.importing` / `.backup` 事务残留只作为可恢复状态展示，稳定源资料保持不可变。
- 新增 `/archaeology/options`、`/archaeology/imports` 与
  `/archaeology/workbench/{work_id}` API；导入后立即由正式 `source-ingest`
  状态机报告 `chunk-extraction-agent-task`，没有建立第二套任务状态。
- API 组装通过 `api/dependencies.py` 注入，`api_server.create_app()` 保持既有架构预算。
- 新增应用/API 回归覆盖：
  - 四种模式；
  - 权利声明、扩展名、DOCX 二进制载体、Base64 和输入互斥；
  - 中断事务恢复投影；
  - v2 `source_documents` schema 映射与绝对路径脱敏；
  - API 导入到 Engine 正式任务状态的连续性。

本批 focused verification：

- `tests.test_archaeology_application`：5 passed；
- Project Archaeology ingest/extraction/reconstruction + Archive API：18 passed；
- `python -m unittest discover -s tests`：533 passed，1 skipped；
- `python scripts/architecture_audit.py`：通过，未增加 file/function debt 或 import cycle；
- `python -m compileall -q src/literary_engineering_studio src/literary_engineering_studio_engine`：通过；
- `git diff --check`：通过。

下一步：

1. W4-5 建立 Project Archaeology 用户工作台，不展示路径、JSON 或 sidecar；
2. 复用现有 Worker/Autopilot 领取 source-ingest 任务，不在前端另造“解析”状态；
3. 完成四模式 UX、冲突与证据视图、候选进入 Archive 的用户路径；
4. 做中断恢复与真实隔离项目 W4 Exit Audit。

## W4-5：Project Archaeology 用户工作台

**状态：完成。**

- Commit: `33be1fc`
- 新增独立 `features/archaeology/` 前端边界，包含 typed contract、API client、Pinia store、来源导入、七阶段证据旅程、分段时间线、人物与别名、冲突工作台、重建预览和候选入档队列。
- continuation、rewrite、adaptation、analysis 四种模式在导入面板中以用户意图而非内部 route 名称呈现；权利声明、文件类型、chunk size 和覆盖行为在提交前显式确认。
- 长任务只调用正式 `/worker/run` 的 `source-ingest` route，并通过现有 Worker SSE、批准、拒绝、停止、重试和继续机制观察；前端不生成第二套提取状态，也不直接调用模型。
- 工作台不展示绝对路径、原始 JSON、sidecar Markdown 或来源正文；证据、冲突、置信度、未决项和候选晋升状态都使用紧凑用户界面呈现。
- “前往档案管理”把可晋升候选交回既有 Narrative Archive 生命周期；analysis 模式保持只分析、不产生可晋升资产。
- 一级导航、项目切换和无项目 route guard 已覆盖作品考古；首次使用继续复用全局引导，不另造 onboarding 状态。
- 响应式验收：
  - 1536×960 桌面端为来源、证据工作区、入档/完整性三栏结构，无纵向或横向页面溢出；
  - 390×844 窄屏按来源、证据、入档顺序重排，无横向溢出；
  - 移动端取消桌面证据舞台固定高度后，页面高度从 1478px 收敛到 1220px，未保留突兀空白。

## W4 Exit Audit：Project Archaeology 纵向闭环

**状态：完成。**

- Commit: `13dd33c`
- 新增真实初始化项目纵向测试：
  1. 导入授权源文本并记录不可变原文 hash；
  2. 完成 chunk extraction、deterministic fan-in、identity resolution、candidate reconstruction 和五领域 review；
  3. `archaeology-materialize` 只生成现有 Archive world candidate；
  4. 候选经过 exact-content independent review 与当前内容 approval；
  5. 共享 `promote_candidate_asset()` 事务写入正式 `canon/world_rules.yaml`；
  6. source-ingest route 达到 ready，原始 source digest 保持不变；
  7. 正式 Task Registry 成功领取 longform-planning 的 `story-architecture-prepare` 任务。
- W4 验收矩阵：
  - DOCX 标题、正文、表格与脚注稳定顺序：既有 ingest 回归通过；
  - 同名不同人、一人多名与 unresolved identity：实体/冲突合同回归通过；
  - 候选事实 evidence range 与 hash：evidence/fan-in 回归通过；
  - 冲突不静默覆盖：alias、claim 和 timeline cycle 回归通过；
  - 中断与恢复：覆盖导入回滚、`.importing`/`.backup` 恢复投影、Worker fresh-output recovery 回归通过；
  - 候选进入 Archive 和 longform planning：新增纵向 Exit Audit 通过。
- 最终退出证据：
  - `python -m unittest discover -s tests -v`：534 passed，1 skipped；
  - `npm run client:test`：32 files、101 tests passed；
  - `npm run client:build`：TypeScript、Vite production build、desktop sync 和 v0.9 build verification passed；
  - Prompt Registry：54 assets、89 task prompt IDs，passed；
  - Architecture Audit：36 existing file debts、226 existing function debts、0 cycles、无新增债务；
  - `python -m compileall -q src tests` 与 `git diff --check`：passed。

## 下一批

W4 已完成全部退出门禁，并已按“实施顺序决策（2026-07-26）”完成受限 W5。

## 受限 W5：Capability Broker、能力契约与 ResourceClaim

**状态：完成。**

- Commits:
  - `1a6b0bb`：版本化 Runtime 能力投影、Capability Broker、七项能力 Handler、
    policy/audit 和 `ResourceClaim`；
  - `1e5c384`：把能力清单与资源声明接入现有 Worker 沙箱和任务上下文。
- `AgentRunnerCapabilities` 保持旧设置页/observability 字段兼容，并增加
  `protocol_version`、`context_window`、`tool_calls`、`cancellation`、
  `local_execution` 和 `capability_ids`。
- 首批稳定能力 ID：
  - `project.query`；
  - `schema.inspect`；
  - `text.statistics`；
  - `citation.lookup`；
  - `reference.search`；
  - `research.web`；
  - `asset.diff`。
- Capability Broker 已实际实现：
  - task、route、role 与显式 policy 联合 allow-list；
  - project-relative 路径规范化与声明读写集边界；
  - HTTPS 域名白名单、禁止自动重定向、`research.web` 默认关闭；
  - UTF-8 文本、搜索数量和 Web 响应上限；
  - 超限结果写入 run-scoped artifact，只返回摘要和 hash；
  - completed、denied、failed 全状态 append-only 审计；
  - 审计与事件只含参数摘要、结果 digest、耗时、artifact 和错误码，不保存密钥或正文；
  - event sink 为 W6 Context Ledger 留出稳定接点。
- 内置 Handler 都是窄能力：
  - 项目查询只投影允许字段和当前任务状态；
  - schema 检查只读取 Embedded Engine 注册 schema；
  - 统计、引用与搜索只访问 manifest 声明的资料；
  - asset diff 只比较声明 source/output；
  - Web 结果永远标记为未核验 research candidate，不能直接成为 Canon。
- 每次 `stage_task()` 都生成：
  - `capabilities/manifest.json`；
  - `capabilities/resource-claim.json`；
  - run manifest 摘要；
  - Agent `_task/` 只读副本；
  - `TASK_CONTEXT.json` 控制面投影。
- 这些合同都位于 Worker run，不写入正式作品目录，也不改变现有
  command → Agent → preflight → preview/writeback → task-submit/task-complete 顺序。
- `ResourceClaim` 已覆盖 reads、writes、runtime/model slot、network 与独占 barrier；
  冲突判断区分 read/read、write/read、write/write、目录前缀和跨项目隔离。
  不同场景的不同正文路径允许进入 W6 并发候选集，最终仍由 DAG 与文学 barrier 判断。

### 受限 W5 Exit Audit

- `python -m unittest discover -s tests -v`：549 passed，1 skipped；
- `npm.cmd run client:test`：32 files、101 tests passed；
- `npm.cmd run client:build`：2,551 modules、desktop sync 和 v0.9 build verification passed；
- Prompt Registry：54 assets、89 task prompt IDs，passed；
- Architecture Audit：36 existing file debts、226 existing function debts、0 cycles、无新增债务；
- `python -m compileall -q src tests` 与 `git diff --check`：passed。

### 明确延期

以下项目按业主决定保持 `deferred_by_owner`，不计入本次受限 W5 完成范围：

- Pi RPC Runtime；
- Ollama；
- 新增模型供应商；
- 外部 CLI Runner 的 Capability Broker tool-call transport。

Broker Python API、policy、Handler、artifact、audit、event sink 和 Worker manifest 已可用；
W6 只接入已有合同，不得重写 Broker、再造 Runtime 或第二套任务状态机。

## W6 下一批

1. 复读自适应编排方案与统一实施方案，建立 W6 批次计划和退出门禁；
2. 以现有固定 route 编译为默认 `CreativeExecutionPlan`，保证行为不变；
3. 引入 Plan Lint、Plan Compiler、任务 DAG、Context Ledger 与 Mutation Receipt；
4. 用本批 `ResourceClaim` 做并发 admission，不让并发越过文学依赖或正式写回边界；
5. 再逐步开放推演深度、修订策略、场景库存与无人值守 campaign。

## W6-1：AO-0 编排边界与正式能力目录

**状态：完成。**

- 新增 ADR-001，固定五类事实分区和“计划属于 Future Intent”的所有权原则；
- 旧 `tasking/orchestration.py` 的外部平台静态蓝图实现已迁移至
  `platforms/orchestration_blueprint.py`，根模块和旧 tasking 路径保留兼容 facade；
- 新增 Engine `orchestration/` 只读协议：
  - `PlanNodeKind` 枚举覆盖 15 类首版正式计划节点；
  - `FormalTaskCapability` 绑定 route、允许 task type、scope、角色、资源模板和可验证贡献；
  - `GateId` 提供稳定机器 Gate ID，高风险场景可确定性注入 `full-roleplay`；
  - `DEFAULT_ROUTE_ORDER` 与当前 Autopilot `ROUTE_ORDER` 由测试锁定等价；
- 新增 Studio `orchestration/settings.py`，定义 fixed、shadow、assisted、
  supervised_adaptive 和 full_adaptive 模式；feature 默认关闭，关闭时 effective mode
  无条件为 fixed；
- 尚未接入 Autopilot、Worker 或 API，当前运行行为没有变化；Engine catalog 不包含命令，
  Planner 未来只能通过 Compiler 解析正式 task package。

本批 focused verification：

- 编排基础、配置、Autopilot 与架构审计测试：38 passed；
- `python -m unittest discover -s tests -v`：556 passed，1 skipped；
- Architecture Audit：无新增 file/function debt、dependency violation 或 import cycle；
- `python -m compileall -q src tests` 与 `git diff --check`：passed。

下一批进入 W6-2 / AO-1：

1. 建立 `CreativeExecutionPlanCandidate`、机器字段隔离、Freedom Budget 和 Progress Contract；
2. 建立不可被候选覆盖的编排宪法；
3. 用 `DefaultPlanFactory` 把固定 route 表达为正式计划；
4. 以 route 顺序、节点角色、Gate 集和 task-next 投影证明默认计划等价。

## W6-2：AO-1 计划契约、编排宪法与默认计划

**状态：完成。**

- `CreativeExecutionPlanCandidate` 与正式 `CreativeExecutionPlan` 已分离：
  - Candidate 只包含 scope、目标、作品理解、策略、节点、重规划规则和 Freedom Budget；
  - plan ID、revision、项目指纹、宪法版本、创建时间、Gate 绑定、route macro、编译 digest、
    审批者和生命周期状态全部由机器拥有；
  - Candidate 伪造机器字段时字段被删除并留下 warning，不能进入正式 DTO；
  - task node 出现 `command`、任意 path 或其他未声明字段时直接拒绝。
- 首版枚举与不可变合同覆盖：
  - book/volume/chapter/scene scope；
  - light/targeted/full RP 深度；
  - 三种修订策略；
  - 十种结构化重规划触发器；
  - scene inventory、Promise policy、Progress Contract、Freedom Budget 和任务贡献。
- `constitution_v1()` 固定 11 条 error 级规则，包括单一正文 Writer、正文前置契约、禁止删
  Gate、修订后 fresh review、正式变化必须 patch、禁止任意命令、Context Broker、资源冲突、
  长篇库存、subagent 禁写正文和 planning 不算正式进度。
- `DefaultPlanFactory` 用 `fixed-formal-route.v1` 包装当前七条 route：
  - 不创建第二套 task 节点；
  - Freedom Budget 为零扩展、零重规划、单执行槽；
  - plan ID 绑定项目 fingerprint；
  - Engine 等价检查拒绝 route 重排、未知 route 或 macro 篡改。
- 新增 candidate/formal plan JSON schema 与 constitution YAML；测试锁定运行枚举、schema ID
  和规则 ID 一致。
- 修正新枚举实现为 `str, Enum`，继续满足项目声明的 Python 3.10+，不依赖 3.11
  `StrEnum`。

本批退出证据：

- `python -m unittest discover -s tests -v`：561 passed，1 skipped；
- Architecture Audit：36 个既有 file debt、226 个既有 function debt、0 cycle，无新增债务；
- `python -m compileall -q src tests` 与 `git diff --check`：passed。

下一批进入 W6-3 / AO-2：

1. Candidate Normalizer 绑定机器 ID、revision、项目 fingerprint、宪法和 Gate；
2. Plan Lint 阻止 DAG 环、孤点、漏前置契约、双 Writer、超 Freedom Budget 和任意能力；
3. Plan Compiler 只生成对现有正式任务的 binding，不签发或完成 task；
4. Plan Simulator 以当前正式状态预演可执行性、资源冲突和空转风险；
5. measure-only 记录编译/模拟开销，但不改变 fixed route。

## W6-3A：AO-2 Candidate Normalizer 与 Plan Lint

**状态：完成。**

- `normalize_plan_candidate()` 已实现纯确定性候选归一：
  - 机器生成 plan ID、revision、项目 fingerprint、宪法版本和创建时间；
  - 归一 node ID、依赖、scope 和 capability ID，并保留可审计 warning；
  - Freedom Budget 与分支数只能向授权上限收缩；
  - Gate 只从 Engine catalog 重新注入，候选无法自报或删除；
  - 高风险节点会获得机器 `full-roleplay` Gate；
  - 显式节点使用 `explicit-task-graph.v1`，不会伪装成默认 fixed macro。
- `lint_plan()` 已实现纯确定性文学工程宪法检查：
  - 重复节点、缺依赖、自依赖、DAG 环和孤点；
  - stale fingerprint、未知 scope、越权 capability 和 Gate 缺失；
  - Freedom Budget 数值域、授权上限、计划深度、附加任务、重规划、分支数和分析比例；
  - 正文前必须具备 context、RP、分支推演、正式选支和 composition 祖先；
  - 正文/修订必须有 fresh semantic review，export 必须有 longform audit；
  - 正文必须声明正汉字目标和正式产物变化，state evolution 必须声明 patch；
  - 同 scope 双正文 Writer 与未串行 revision 会被阻断。
- `budget_policy.py` 独立拥有预算数值域，避免后续设置、Compiler 和 Lint 复制边界。
- state/canon evolution 的机器 Gate 已补入 promotion 前置，避免把未晋升正文作为正式变化来源。
- 所有实现仍为无 I/O、无模型、无 task lifecycle 的纯域逻辑；当前 fixed route 行为不变。

本子批验证：

- Normalizer、Plan Lint、AO0/AO1 聚焦测试：19 passed；
- `python -m unittest discover -s tests`：568 passed，1 skipped；
- Architecture Audit：36 个既有 file debt、226 个既有 function debt、0 cycle，无新增债务；
- `python -m compileall -q src tests` 与 `git diff --check`：passed。

下一子批进入 W6-3B：

1. 建立只消费 Engine catalog 的 Compiler Registry；
2. 编译稳定 task binding、DAG、资源意图和 graph digest，不签发任务；
3. 建立无模型、无写回的 Plan Simulator，预演 blocker、冲突、Gate 和 no-progress；
4. 用默认 macro 等价测试证明 fixed route 仍由现有 Task Registry 动态领取。

## W6-3B：AO-2 Plan Compiler 与 Plan Simulator

**状态：完成。**

- 新增 command-free `TaskBinding`、`CompiledTaskNode` 与 `CompiledTaskGraph`：
  - binding 只包含 capability、route、允许 task type、scope、角色、parameter schema、
    Gate、资源模板和 progress kind；
  - graph 绑定 plan ID/revision、项目 fingerprint、macro、依赖和 SHA-256 digest；
  - 新增 `compiled-task-graph.v1.schema.json` 作为跨语言协议。
- `CompilerRegistry` 只消费 Engine `FormalTaskCapability`：
  - 不保存或生成命令；
  - 每种 parameter schema 使用明确 allow-list；
  - command/path 类参数在 Candidate 入口已拒绝，未知业务参数在 binding 时再次拒绝。
- `compile_plan()` 的确定性编译纪律：
  - 只接受 passing 且 `plan_digest` 精确匹配当前 plan 的 Lint receipt；
  - stable topological order；
  - 保留 Normalizer 注入的高风险 `full-roleplay` 等动态 Gate；
  - 对无依赖关系的 state/canon/release mutation 增加机器串行边；
  - fixed macro 仍输出空 nodes 与原 route sequence，不复制 task lifecycle；
  - sealed graph 被修改后 digest 校验失败。
- `simulate_plan()` 只接受调用方显式提供的正式状态观察和 Runtime `ResourceClaim`：
  - 校验 route、task type、scope、项目 revision 与 resource project；
  - 区分 ready、waiting、completed 和 blocked；
  - 只在 DAG 上可并发的节点间计算 read/write/barrier 冲突；
  - 汇总 expected artifacts、stale invalidation 和 machine-injected dependency；
  - 检查未消费输出和只分析不形成正式产物的 no-progress 路径；
  - 给出模型调用、费用和运行时间的 measure-only 区间，不运行模型。
- AO-2B 仍未接入 Autopilot、Worker、API 或 persistence，当前 fixed 执行行为保持不变。

本子批聚焦验证：

- Compiler/Simulator、AO0-AO2 合同测试：29 passed；
- `python -m unittest discover -s tests`：578 passed，1 skipped；
- Architecture Audit：36 个既有 file debt、226 个既有 function debt、0 cycle，无新增债务；
- `python -m compileall -q src tests` 与 `git diff --check`：passed。

下一子批进入 W6-3C：

1. 建立计划/编译图/模拟报告的 SQLite 元数据与项目审计文件持久化；
2. 使用 optimistic revision 与 fingerprint 阻止 stale activation；
3. 增加 shadow pipeline 量测，不影响正式 Autopilot 任务顺序；
4. 完成 AO-2 架构复核和退出审计后，再进入 Planner/Reviewer。

## W6-3C：AO-2 持久化、Shadow 量测与恢复基础

**状态：完成。独立 reviewer 已确认 AO-2 close = Yes。**

- SQLite schema 从 11 升至 12，沿用迁移前自动备份：
  - `creative_plans` 保存 plan 身份、scope、状态、active revision、fingerprint 和 policy；
  - `creative_plan_revisions` 保存各审计文件的 path/hash/status 摘要、revision digest 和
    `reserved/ready` 产物状态；
  - `creative_plan_events` 保存 append-only revision/activation 事件；
  - 明确删除 `creative_plan_nodes` 设计，避免形成第二套可写 task lifecycle。
- 持久化按职责拆分：
  - `creative_plans.py`：不可变 revision、查询、列表和 optimistic activation；
  - `creative_plan_events.py`：append-only 事件；
  - `creative_plan_activation.py`：SQLite 与 `active_plan.json` 的补偿式一致写入；
  - `creative_plan_primitives.py`：无循环依赖的共享身份校验；
  - `orchestration/persistence.py`：项目审计文件与 SQLite 索引协调；
  - `orchestration/audit_integrity.py`：跨审计产物语义链；
  - `shadow.py`：无执行能力的 measure-only 流水线。
- 项目审计文件已实现：
  - candidate、normalized plan、compiled graph、lint、simulation、shadow review；
  - provenance 保存各文件 hash、plan digest、graph digest、fingerprint 和 revision digest；
  - 先在 SQLite 预留 revision digest，再原子 batch 写入
    `workflow/orchestration/plans/{plan_id}/`，成功后标记 ready；
  - SQLite 不保存完整大 JSON，只保存文件引用和摘要；
  - 相同 plan/revision/digest 重复写入幂等，写入失败可从 reserved 状态重试；
  - 不同 digest 在文件写入前冲突，不会覆盖已存在的审计链；
  - 文件 hash 之外，还校验 candidate -> normalized plan -> lint -> compiled graph ->
    simulation -> provenance 的语义归属。
- activation 已建立确定性门禁：
  - expected active revision；
  - current project fingerprint；
  - passing/warn Lint；
  - passing/warn Simulation；
  - passing independent orchestration review；
  - 单项目唯一 active plan；
  - plan 初始状态由 Store 固定为 `shadow`，调用方不能直接写 `active`；
  - revision 进入 ready 前由 Store 核验六类审计文件的存在性与 hash；
  - 显式 SQLite transaction 协调 active projection，SQL/event/commit 失败时恢复原文件。
- Shadow evaluation 记录 Normalize、Lint、Compile、Simulate 和总耗时；Lint 失败不编译，
  不产生 graph 或 simulation；模块尚未接入 Autopilot，因此正式路线与任务顺序不变。
- Plan Lint 额外将 analysis/production ratio 设为硬限制，并禁止同一 scope 的正式正文与
  revision 并行写作；默认 plan ID 同时绑定 candidate digest 和项目 fingerprint。
- 持久化、文学链规则和 activation 已按单职责拆分，架构门禁保持 0 cycle。

本子批验证：

- AO0-AO2 与 persistence 聚焦测试：44 passed；
- `python -m unittest discover -s tests -v`：598 passed，1 skipped；
- Architecture Audit：36 个既有 file debt、226 个既有 function debt、0 cycle，无新增债务；
- `python -m compileall -q src tests` 与 `git diff --check`：passed。

AO-2 退出结论：

1. 两轮独立 reviewer findings 全部关闭，无剩余 P0/P1；
2. Bundle Compiler 按统一实施方案延后至 AO-6/v0.99，不在 AO-2 提前建立第二执行单元；
3. 提交 W6-3C 后进入 AO-3 Planner/Reviewer，仍不直接接入生产 Autopilot。

## W6-4：AO-3 Planner、Reviewer 与可审计运行基础

**状态：进行中。**

本阶段继续保持 `orchestration.enabled=false` 的默认路径，不把 Planner 接入生产
Autopilot，也不建立第二套 task lifecycle。按以下四个可回滚子批执行：

### W6-4A：协议、Profile 与规划上下文合同

**状态：完成。**

1. 建立 Historical / Current State / Stable Knowledge / Future Intent / Evidence 真相分区；
2. 建立独立 Planner 与 Orchestration Reviewer profile，固定能力、网络和写入边界；
3. 建立只读 planning context package 与 Context Ledger 纯合同；
4. Planner 只能产出 plan candidate，Reviewer 只能产出绑定精确 candidate/plan/graph/
   simulation digest 的 review；
5. Planner 与 Reviewer session ID 必须不同，模型字段不能满足机器 Gate。

实现结果：

- `truth_partition.py` 明确 Future Intent 与 Evidence/Opinion 不能满足正式 Gate；
- Planner/Reviewer profile 为 machine-owned、network deny、formal-write deny；Reviewer
  额外禁止 subagent 并要求独立 session；
- Context Builder 优先装配 mandatory source，按字符预算记录 included/truncated，并对
  metadata preview 做凭证脱敏；
- 模型只提交 judgment candidate；plan/session/digest/independent reviewer 字段由机器
  sealing，未知或伪造机器字段直接拒绝；
- 新增三份跨语言 Schema，保持 Context Ledger、Agent request 和 Review receipt 与
  Python 合同一致。

退出证据：

- `tests/orchestration`：56 passed；
- `python -m unittest discover -s tests -v`：605 passed，1 skipped；
- Architecture Audit：36 个既有 file debt、226 个既有 function debt、0 cycle；
- `python -m compileall -q src tests` 与 `git diff --check`：passed。

### W6-4B：Context Ledger 运行与持久化

**状态：完成。**

1. Agent workspace materialize 后依据实际复制结果生成 `context-ledger.json`；
2. task prompt、Agent 可读路径和 ledger 共享同一 source selection；
3. SQLite 只保存 metadata、hash、截断状态和脱敏短预览；
4. Agent session 关联 ledger ID，重试且上下文变化时产生新 digest；
5. 明确缺失、截断和未包含资料，复现并关闭“prompt 要求读取但 sandbox 拒绝”的历史故障。

实现结果：

- `runtime/context_selection.py` 统一 required reference、Agent source 和 operational path；
  prompt 的 source/reference 只使用实际复制成功的交集；
- `context_materialization.py` 在 Agent workspace 最终装配后一次性生成 prompt、
  `TASK_CONTEXT.json`、Capability/Resource 控制副本和 Context Ledger；
- Ledger 覆盖 source/reference、既有 output baseline、CLI protected output、
  `project.yaml`、用户方向和 `_task` machine controls；缺失输入以 excluded entry
  留证，不再让 prompt 指挥模型读取沙箱拒绝的路径；
- `assembled_sha256` 精确绑定 Agent prompt；ledger identity 额外绑定全部可见元数据，
  同一 run 的核心命令若改变资料内容也会生成新 ID/digest；
- SQLite schema 13 新增 metadata-only ledger/entry 表和 Agent session ledger
  关联；跨项目 replay、digest 冲突和 run-root 外路径均 fail closed；
- API Worker、Autopilot 和直接 prepare 复用同一持久化服务；正式持久化事件为
  `sandbox.context_ready`，不记录模型尚未真正收到的 pre-command 临时上下文；
- 凭证样式内容在 run ledger 和 SQLite preview 写入前统一脱敏，数据库不复制全文。

退出证据：

- AO-3B focused/regression：40 passed；
- `python -m unittest discover -s tests -v`：611 passed，1 skipped；
- Architecture Audit：36 个既有 file debt、225 个既有 function debt、0 cycle；
- `python -m compileall -q src tests` 与 `git diff --check`：passed；
- 架构评审见
  `docs/architecture/reviews/ao-3b-context-ledger-runtime-review.md`。

### W6-4C：Mutation Receipt 与 Typed Plan Events

**状态：完成。**

1. 复用现有 Worker 的 candidate、preflight、preview、apply、rollback、promotion 事件点；
2. receipt 由机器生成并绑定 task/run/session/plan，不允许 Agent 写入；
3. 计划事件采用固定 enum/schema，delta 仅用于显示，completed candidate 才能进入 Lint；
4. rollback 的 formal effect 必须为 `none`，正式写回继续由既有 Engine/Worker Gate 拥有。

实现结果：

- 新增 `arcvellum/worker-mutation-receipt/v1` 合同、JSON Schema、SQLite metadata 索引和
  run-root JSONL 审计；receipt 绑定 task、run、真实 session、plan、context ledger、
  action、change group、artifact digest 和 formal effect；
- fixed route 使用机器保留的 `fixed-route` 计划身份；自适应任务从 machine-owned task
  payload 读取 plan ID/revision，Agent workspace 和 expected outputs 均不能生成 receipt；
- Worker 的 candidate、preflight rejection、preview、human rejection、apply、rollback 和
  promotion 统一经过 `WorkerMutationTracker`；同一事实按确定性 receipt ID 幂等，候选内容
  变化会产生新 receipt；
- rollback receipt 强制 `formal_effect=none`；apply 后 Core Gate 失败时，时间线保留瞬时
  apply 证据并追加 rollback，正式项目仍由既有 Sandbox、Worker 和 Engine Gate 恢复；
- 新增固定 `CreativePlanEventType` 与 `arcvellum/creative-plan-event/v1` Schema；
  `plan.candidate.delta` 只用于实时显示，不能进入 durable event ledger，也不能作为 Lint
  输入；只有机器封装的 `plan.candidate.completed` 能穿越 Planner/Lint 边界；
- SQLite schema 升级到 14，增加 Mutation Receipt 索引和 plan event `session_id`；
  migration 继续使用既有 backup/additive 协议；
- Worker 写回生命周期从 677 行的 `worker.py` 拆分到职责明确的 runtime/observability/
  persistence 模块，`worker.py` 降至 334 行，没有改变正式任务写回所有权。

退出证据：

- `python -m unittest discover -s tests -v`：618 passed，1 skipped，约 137 秒；
- `python -m compileall -q src tests`：passed；
- Prompt Registry：54 assets、89 task prompt IDs，0 error、0 warning；
- Architecture Audit：35 个既有 file debt、224 个既有 function debt、0 cycle；
- `git diff --check`：passed；
- 架构评审见
  `docs/architecture/reviews/ao-3c-mutation-receipt-and-plan-events-review.md`。

下一子批进入 W6-4D。Planner/Reviewer 必须使用独立真实 session，Planner delta 仍仅作为
显示事件，完整候选必须先形成 typed completion event；任何 Planner、Review 或 stale
context 失败只能留下 fallback 证据，不得改变 fixed route。

### W6-4D：Planner/Reviewer Shadow Service 与退出审计

**状态：完成。**

1. Planner 和 Reviewer 通过独立协议会话运行，只在 orchestration audit 目录写候选和证据；
2. Reviewer 不能复用 Planner session，不能修改候选，也不能直接激活计划；
3. 对照 fixed route 记录计划质量、额外开销、Gate 注入和 fallback 原因；
4. 证明 feature-off、Planner 失败、Review 失败和 stale context 均回退固定路线；
5. 完成 AO-3 Architecture Review、独立 reviewer、全量 Python 测试、架构审计和 Git 封口。

实现结果：

- 新增只读 `RuntimeOrchestrationAgentTransport`，当前只允许具有角色隔离能力的
  OpenCode；Planner 和 Reviewer 使用不同真实 session 及独立 audit workspace；
- Planner 的流式 delta 只作为瞬时展示数据，durable ledger 从机器封装的 typed
  completed candidate 开始；
- Reviewer 必须读取未截断的精确候选、normalized plan、Lint、Compiled Graph 和
  Simulation；证据超过边界时 fail closed；
- Review Receipt 绑定 plan/revision、Reviewer context、candidate、plan、graph、
  simulation digest 和独立 session，跨计划或串线 Receipt 在持久化前被拒绝；
- Shadow revision 固定为 `activation_eligible=false`，既有公共 activation API 对其
  fail closed；`pass_with_notes` 不作为 clean pass；
- 普通 Runtime、连接、fingerprint 和审计写盘异常均回退 fixed route；stale context 在
  Planner 后、Reviewer 后和紧贴持久化前重复检查；
- 每次 Shadow run 记录 fixed route 对照、Gate 数、阶段状态、耗时和 fallback 原因，
  但不接入 Autopilot、不改变正式项目状态。

退出证据：

- AO-3D 聚焦及攻击型测试：30 passed；
- `python -m unittest discover -s tests -v`：628 passed，1 skipped；
- Prompt Registry：54 assets、89 task prompt IDs，0 error、0 warning；
- Architecture Audit：35 个既有 file debt、224 个既有 function debt、0 cycle；
- `python -m compileall -q src tests` 与 `git diff --check`：passed；
- 独立审阅首轮 4 P1/3 P2，修复复核后零 P0、零 P1；最后一个 stale P2 已通过
  持久化前二次检查收口；
- 架构评审见
  `docs/architecture/reviews/ao-3d-planner-reviewer-shadow-service-review.md`。

### W6-4E：星仪 W1 文档差距补缺

**状态：完成。W1-Fix A/B/C/D 与自动化视觉退出验收均已关闭。**

实际代码与 W1 文档复核确认星仪基础完整，但存在不能等到 W6-9 的产品缺口：

1. scene 粒度下点击章节仍以首场景提交 focus，镜头簇重心与语义作用域不一致；
2. 后端 `relation_profiles` 尚未进入前端 Semantic Lens、Legend 和渲染 LOD；
3. character focus、焦点历史、节点与正文双向定位、小地图/beacon、搜索和视觉回归仍缺。

其中前两项为 W1 P1，先完成焦点一致性与关系可见性；其余按 W1-UX 分批实现。AO-8 只
增加计划、Gate、Patch 和 Agent Observatory 投影，不得拿未来编排 UI 掩盖现有星仪缺口。
完整审计见 `docs/architecture/reviews/orrery-w1-document-gap-audit.md`。

W1-Fix A/B 实现结果：

- 章节目录统一提交 `chapter` focus；即使当前在 scene level，也不再用首场景冒充整章；
- Focus Store 正式支持 `character` level、焦点历史和返回上一焦点，人物轨道不再只是
  局部 CSS 高亮；
- v3 无障碍摘要由实际 focus scope 生成，人物、章节与场景焦点不再复用 v2 全书摘要；
- 新增紧凑 Relation Lens，使用后端 11 类 `relation_profiles` 提供计数、显隐、独看与复位；
- Pixi 与 SVG 渲染共同消费 far/mid/near relation mode，独看会把选中关系族提升为
  emphasized；固定 `6` 条 local flow、`5` 条人物线和 book 级证据省略已移除；
- 人物栏不再按组截断，关系降噪改为可解释 LOD，而不是静默丢边。

本子批证据：

- Client：106 tests passed；
- v3 Narrative Projection：9 tests passed；
- `python -m unittest discover -s tests -v`：628 passed，1 skipped；
- `vue-tsc`、生产 `client:build`、`git diff --check`：passed；
- Architecture Audit：35 个既有 file debt、224 个既有 function debt、0 cycle，无新增债务；
- 真实项目 `1+1=2` 浏览器验收通过：关系镜头无窗口遮挡，character focus 可回退，
  scene level 点击第 2 章得到 `章节焦点“第 2 章”`。

W1-Fix C 实现结果：

- 新增独立 `OrreryNavigationLayer` 与纯模型 `spatialNavigation`，交付搜索、搜索结果
  强制显标、显示全部标签、小地图、离屏 beacon 和完整方向键导航；
- 新增 `readerNavigation` Store 与 `readerLink` 身份适配，星仪正式节点可打开精确
  chapter/scene 正文单元，阅读器当前位置可反向进入同一 scene focus；
- 路径型 scene source ID、manifest unit ID 与 scene ID 由纯模型统一，不在组件内散落
  路径字符串启发式；
- 1440x900 真实项目验收通过，搜索、小地图、正文入口和章节目录无重叠。

本子批证据：

- Client：37 files、118 tests passed；
- Python：628 tests passed、1 skipped；
- `vue-tsc`、生产 `client:build`、Prompt Registry、`compileall` 与
  `git diff --check`：passed；
- Architecture Audit：35 个既有 file debt、224 个既有 function debt、0 cycle；
- 评审见
  `docs/architecture/reviews/orrery-w1-navigation-reader-link-review.md`。

W1-Fix D 实现结果：

- 新增套索比较、语义路径回放、节奏/张力/承诺/审查热力层和按作品隔离的视图书签；
- 搜索、套索、回放、热力与书签均为只读探索，不写项目资产；
- Layout Hint 建立后端单一合同与前端确定性边界，只接受 validated intent、受限偏移和
  无碰撞结果；当前默认 disabled，不提前放开 Agent 自由布局；
- 真实项目验证热力、回放、书签恢复和中文文案，书签/关系镜头/章节目录/小地图无重叠。

本子批证据：

- Client：41 files、128 tests passed；
- Python：629 tests passed、1 skipped；
- 生产前端构建：2,565 modules；
- Prompt Registry：54 assets、89 task prompt IDs，0 error、0 warning；
- Architecture Audit：35 个既有 file debt、224 个既有 function debt、0 cycle；
- `compileall` 与 `git diff --check`：passed；
- 评审见
  `docs/architecture/reviews/orrery-w1-advanced-exploration-review.md`。

W1-Exit 实现结果：

- Playwright 覆盖 100/300 场景、五主题、四焦点、关系、章节主脊、目录、Canvas 像素和控件避让；
- SSE 增量后保持焦点与多开窗口身份，reduced-motion 保持核心探索功能等价；
- 1000 场景六种空间语法通过有限坐标、可寻址性、Canvas 与交互规模门禁，布局基线约
  32–61 ms；
- 千场详细整页 PNG 只保留为受控 Chromium 的非阻断证据，不把渲染全部 DOM 标签误作
  语义完整性。

退出评审见 `docs/architecture/reviews/orrery-w1-visual-exit-review.md`。

### W6-4F：v0.96.0 创作吞吐收口

**状态：完成首批安全优化；AO-5/AO-6 的 Bundle、缓存与有限并发仍未提前开放。**

- 真实任务分段测量确认模型执行约 189 秒，是 task selection、staging 和 writeback 之外的
  主瓶颈；
- Agent 首轮获得许可 Source、Reference 与 CLI Protected Outputs 的完整带摘要快照，
  省略文件仍留在受限工作区并显式声明；
- 确定性任务采用最小 Agent 沙箱，带 CLI 前置命令的任务延迟到 protected outputs 生成后
  只物化一次；
- 真实 deterministic dependency set 的 staging 从约 0.371 秒降到约 0.092 秒；
- 累计 usage snapshot 改为按稳定消息身份计算增量，修复吞吐面板 token 重复累计。

退出证据：

- Python：632 tests passed，1 skipped；
- Client：41 files、128 tests passed；
- Architecture Audit：35 个既有 file debt、223 个既有 function debt、0 cycle，无新增债务；
- `compileall`、`vue-tsc` 与 `git diff --check`：passed；
- 评审见 `docs/architecture/reviews/v096-throughput-optimization-review.md`。

### W6 后续完整阶段映射

W6 不以一个模糊“长周期验收”跳过剩余路线。AO-3 退出后继续：

| 实施批次 | 自适应阶段 | 统一实施方案覆盖 |
| --- | --- | --- |
| W6-5 | AO-4 场景级自适应 | RP 深度、分支数、修订策略、scene Plan Patch、完整场景闭环 |
| W6-6 | AO-5 章节级编排 | Rolling Horizon、SceneRiskProfile、事件库存、字数/节奏/承诺义务 |
| W6-7 | AO-6 资源锁与有限并发 | Resource Gate、Execution Bundle、上下文缓存、局部修复、session lease、只读并发 |
| W6-8 | AO-7 全书重规划与 Campaign | Progress Fingerprint、checkpoint、恢复阶梯、bounded replan、无人值守 |
| W6-9 | AO-8 前端产品化 | 策略页、typed SSE、计划 diff/模拟/审批、Agent Observatory 与星仪投影 |
| W6-10 | v1 最终验收 | 固定路线回退、真实项目长跑、吞吐基线、桌面生产构建和交付审计 |

各批次必须分别留下 Architecture Review、确定性测试、集成测试和 Git 提交；前一批
退出门槛未满足时不得只为“推进进度”提前开启后一批。
