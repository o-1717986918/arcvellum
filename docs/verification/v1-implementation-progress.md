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
- W1 Living Narrative Field 已完成关系可见性、人物引用、正文窗口三态、工作区语义 revision、100/300/1000 规模基准和 v3 增量传输六个可回滚批次。
- 当前尚未完成 W1 的真实浏览器大规模视觉与像素验收，以及后续 W2-W8/AO 工作流；不得据此声称 v1 已交付。
- 最近一次全量证据：Python 423 tests、Client 76 tests、Client production build、Python compileall、Architecture Audit 全部通过。

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

## 下一批

下一批开始前必须重新读取统一实施方案 W1、模块边界和本文件。优先建立可由浏览器直接加载的 100/300/1000 视觉验收项目，完成六种语法、四个 focus、窗口共存、主题切换、远中近 LOD 和 canvas 像素非空验证；在 W1 大规模视觉正确性未闭环前，不开始 Archive 写模型。
