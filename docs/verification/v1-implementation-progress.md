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

## 当前结论

- F0 契约与架构基线已完成三个可回滚批次：吞吐测量、架构质量审计、叙事焦点契约。
- W1 Living Narrative Field 已完成关系可见性、人物引用、正文窗口三态、工作区语义 revision、100/300/1000 规模基准、v3 增量传输、真实磁盘完整证据与浏览器大规模视觉验收。
- W1 已满足当前路线定义的性能、导航、焦点、空间语法、主题、多窗口与 canvas 非空退出门禁。
- W2 Narrative Archive IDE 已完成受控资产身份、校验、影响预览、Owner Override、修订历史、正式 stale 传播、可逆归档/恢复、候选晋升、Registry 驱动的结构化编辑、状态化引导和隔离真实项目作者闭环。
- W2 已满足统一实施方案当前定义的产品、Gate、Stable Knowledge 与架构出口；后续 W3-W8/AO 工作流仍未实施完毕，不得据此声称 v1 已交付。
- 最近一次全量证据：Python 473 tests passed、1 skipped；Client 90 tests passed；Client production build、desktop frontend sync、Python compileall、Architecture Audit 与 `git diff --check` 全部通过。

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

## 下一批

下一批开始前必须重新读取统一实施方案 W3、长期文风路线、自适应创作编排方案、模块边界和本文件。W3-3 只把 compile、evaluate、independent review 和 build 接入既有 Worker 与 Engine route：

1. HTTP 写操作只返回 job/task ID，不能在请求线程内等待模型，也不能返回 `pending_platform_agent` 冒充完成。
2. 扩展既有 `style-engineering` route，不新建 Studio 状态机；Prompt、评测候选和独立 review 均是 Agent 候选输出。
3. 确定性 Gate 必须绑定 source、candidate、prompt、review 和 completion digest；review 失败不能 build。
4. build 只能物化通过 Gate 的明确版本，本批仍不直接 mount 到作品；正式挂载与 stale 传播属于 W3-4。
