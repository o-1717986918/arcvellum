# Orrery v0.99 Narrative Signal Hierarchy

## Module Change Packet

```yaml
module_change_packet:
  objective: "默认星仪减少无用工程节点，以更大节点和清晰章节主脉呈现作品；用户仍可主动查看全部项目事实。"
  primary_module: "client/src/features/orrery"
  public_entry: "OrreryWorkbench -> OrreryNodeOverlay / NarrativeSpineLayer"
  variation_point: "用户可切换 narrative 与 all 两种视觉信息密度；项目投影合同不变"
  inputs:
    - "SpatialNarrativeProjection v3/v4"
    - "相机投影后的 node anchors"
    - "选中、导航、强制显示和当前任务状态"
  outputs:
    - "语义分层后的可见节点集合"
    - "主干/全部视野状态与用户可读计数"
    - "更强的章节主脉和更大的可操作节点"
  invariants:
    - "不删除、不改写任何后端资产或投影事实"
    - "不改变 CLI、任务状态机、Gate 和正式项目文件"
    - "选中、搜索、当前、阻断节点永远可见"
    - "章节节点与章节时间顺序永远保留"
    - "全部细节模式可恢复原始投影的所有节点"
  allowed_dependencies:
    - "@/types/spatial"
    - "orrery model/layout/components"
  forbidden_dependencies:
    - "generic API transport"
    - "Engine/Runtime 内部实现"
    - "新的后端节点过滤真相"
  tests:
    - "narrative signal hierarchy unit tests"
    - "OrreryNodeOverlay component tests"
    - "frontend Vitest suite"
    - "frontend production build"
    - "desktop and mobile visual screenshot / overlap review"
  rollback_unit: "one frontend-only Git commit"
  documentation:
    - "this review and implementation record"
```

## Actual Problem

现有节点层把“工程事实完整性”和“用户视觉完整性”视为同一件事。代码只压掉碰撞文字，却保留每一个星点；大型项目因而同时展示世界观、地点、组织、文风、预算、候选正文、审查证据等大量维护资产。其结果不是信息更完整，而是章节与场景的阅读顺序被噪声淹没，节点还被全局缩放压到难以点击。

## Visual Contract

默认 `narrative` 视野：

- 永远显示项目原点和全部章节，保留作品的时间与结构骨架。
- 全书远景只展开当前、阻断或被用户定位的场景；章节与场景视野展开当前章节的全部场景。全部场景仍保留在同一投影、章节目录、检索和 `all` 视野中。
- 显示主要人物，以及当前章节相关人物；低重要度且与当前焦点无关的次要人物降级。
- 当前、阻断、选中、搜索定位、人工决策及其一跳关联证据永远显示。
- 世界观、地点、组织、架构、字数预算、文风文件、候选正文、正式正文镜像、普通 Canon 和已完成审查默认不进入星空；它们继续存在于档案、检索、节点详情和 `all` 视野。
- `all` 视野保持原行为，用于调试关系、检查完整项目事实或定位低频资产。

节点层级：

- 章节是最大、最稳定的顺序锚点。
- 场景是第二层可操作节点，概览状态也保持足够点击面积。
- 当前和阻断信号高于普通人物与证据。
- 被隐藏的资产不参与常态视觉计数，界面同时标明“主干节点 / 全部事实”，避免误解为数据丢失。

主脉层级：

- 章节 Catmull-Rom 主脉拥有稳定底光、实体轨道和流动信号三层。
- 关系线继续表达人物、证据与桥接，但在高密度时不得压过章节主脉。
- 聚焦章节时保留全书脉络，仅降低非当前区段；不能让用户失去当前位置。

## Non-goals

- 本批不修改后端投影生成、资产模型或档案结构。
- 本批不通过随机采样删除章节或场景；场景显隐只由当前叙事粒度和章节焦点决定。
- 本批不重做空间构型算法；若语义降噪后仍有局部拥挤，再在独立 layout 批次处理。

## Implementation Record

- 新增纯模型 `model/narrativeSignalHierarchy.ts`，不改变后端 Projection DTO。
- 新增“主脉 / 全部”分段控制；搜索、选中、当前、阻断节点可穿透默认筛选。
- 全书使用章节级语义缩放；章节/场景视野展开当前章节的场景。
- NarrativeSpineLayer 只绘制当前可见证据与人物线，但继续使用完整场景集合计算章节重心和全书主脉。
- 节点增加按类型区分的最小可读尺度；章节、场景和 symbolic signal 的点击面积同步放大。
- 主脉底线、实体轨道与辉光增强，关系线在视觉上退居第二层。

真实 1000 场景压力项目观测结果：

| 状态 | 常态节点 | 工程事实 |
|---|---:|---:|
| 全书 / 主脉 | 69 | 1148 |
| 章节 / 主脉 | 78 | 1148 |
| 章节 / 全部 | 1148 | 1148 |

验证：

- `npm run client:test`：65 files / 200 tests passed。
- `npm run client:test:visual`：8 Playwright scenarios passed，覆盖 100/300/1000 场景、主题、焦点、SSE、reduced motion、顾问悬浮、千场平移缩放和左键旋转。
- `npm run client:build`：Vue typecheck、Vite production build、desktop frontend sync、v0.9 build verification passed。
- `python scripts/generate_module_map.py --check` 与 `git diff --check`：passed。
- `python scripts/architecture_audit.py`：仍报告本批前已经存在的 compatibility facade、超预算文件/函数和跨 feature 组件依赖；本批未新增这些依赖，也没有修改 architecture baseline。
