# ArcVellum v1 实施进度

> 权威路线：`docs/roadmap/arcvellum-v0.96-v1.0-integrated-engineering-implementation-plan.md`
>
> 约束基线：`docs/architecture/module-boundaries.md`
>
> 规划基线提交：`f3cc855`；实施分支：`feat/v096-f0-throughput-baseline`
>
> 本文件只记录已经通过退出门禁的事实。完成一段代码、通过定向测试或生成构建产物，均不能单独视为工作流交付。

## 当前结论

- F0 契约与架构基线已完成三个可回滚批次：吞吐测量、架构质量审计、叙事焦点契约。
- W1 Living Narrative Field 已完成关系可见性、人物引用、正文窗口三态、工作区语义 revision、100/300/1000 规模基准、v3 增量传输、真实磁盘完整证据与浏览器大规模视觉验收。
- W1 已满足当前路线定义的性能、导航、焦点、空间语法、主题、多窗口与 canvas 非空退出门禁。
- 当前尚未完成后续 W2-W8/AO 工作流；不得据此声称 v1 已交付。
- 最近一次全量证据：Python 431 tests、Client 79 tests、Client production build、Python compileall、Architecture Audit 全部通过。

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

## 下一批

下一批开始前必须重新读取统一实施方案 W2、模块边界和本文件。W2 先建立 Archive 写模型、作者权威与乐观并发的最小闭环；不得直接把任意文件编辑器接到正式项目文件，也不得让 Archive 绕过现有状态机、审查、晋升或审计协议。
