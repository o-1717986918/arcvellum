# 星仪 W1 规划与实际实现差距审计

> 审计日期：2026-07-26
> 依据：
> `arcvellum-v0.96-v1.0-integrated-engineering-implementation-plan.md` W1、
> `arcvellum-post-v0.95.3-long-horizon-product-and-runtime-roadmap.md` 第 5 节。
> 本文件只记录实际代码证据和后续归属，不修改 Narrative Projection、前端状态或作品事实。

## 1. 总体结论

星仪已经具备可用的 Living Narrative Field 基础，不是一个未完成原型：

- 后端 v3 投影、focus scope、11 类 relation profile、人物别名/未解析引用、增量 SSE 和
  revision 已建立；
- book/chapter/scene 都保留全书投影，章节目录由独立 book projection 装配；
- 六种稳定空间语法、节奏/时间间距、簇间避碰、伪 3D 平移缩放和中键视角已建立；
- 人物轨道、章节主脊、场景关系、完成/未完成状态、时间游标和无障碍列表已存在；
- 正文长卷拥有 peek/reading/immersive 三态、分段连续阅读、搜索、书签、阅读位置、字体、
  行距、主题和跟随新正文；
- 100/300/1000 节点布局与后端投影性能已有确定性夹具。

但 W1 仍不能按文档判定为“产品面完全闭环”。主要问题不是数据缺失，而是已有合同没有
全部进入用户可操作的前端控制面。

## 2. 已完整或基本完整

### 2.1 后端只读边界

`projections/narrative/` 已按 contracts、focus、relations、characters、grammar、revision
拆分；API router 没有获得 Canon、正文或资产写入权。旧投影文件继续作为 facade。

结论：符合 W1 单一只读投影边界。

### 2.2 全书投影与章节簇

前端维护独立 `bookChapterNodes`，底部目录始终来自 book projection；布局按章节和场景
稳定 ID、阅读顺序、故事时间、节奏和簇关系生成坐标。章节定位镜头使用场景簇重心，而
不是把镜头机械放在第一场。

结论：全书目录、章节簇和镜头重心已实现；焦点语义仍有一项 P1 缺口，见 3.1。

### 2.3 人物引用基础

后端读取 `participant_refs`，兼容旧名称和 aliases；无法唯一解析时生成 unresolved 或
ambiguous reference，不静默丢弃。前端人物轨道分为本章、全书和待解析三组。

结论：人物身份合同已完成，人物焦点产品面仍不完整，见 3.3。

### 2.4 正文长卷

`ManuscriptReader.vue` 已建立统一三态和持久阅读状态，连续阅读采用增量展开而不是一次
创建百万字 DOM；新晋升正文可在用户选择跟随时进入阅读位置。

结论：正文阅读器达到基本产品标准；星仪节点与阅读单元的双向定位仍需补齐，见 3.5。

## 3. 真实缺口

### 3.1 P1：场景粒度下点击章节仍用首场景冒充章节作用域

`OrreryWorkbench.openChapterFromRail()` 在 scene level 下仍调用：

```text
setView({ level: "scene", focus: entryScene })
```

随后镜头虽然移动到整章场景簇重心，但后端 `scene` focus scope 只声明当前场景、相邻场景
和所属章节锚点。视觉镜头和语义作用域因此不是同一件事。该实现可能再次出现“同章其他
场景存在，但其分支、问题、承诺、审查被按远景降级”的历史故障。

修复归属：W1 修复批，不应等待 W6-9。

验收：

- 章节目录在 scene 粒度下提交 chapter scope，而不是首场景 ID；
- 同章每个场景及其直接关系节点进入作用域成员；
- 再点单场景只提高权重，不替换整章作用域；
- API、Store、布局、Overlay 使用同一 focus scope。

### 3.2 P1：RelationVisibilityProfile 未进入前端控制与渲染决策

后端已经返回 `relation_profiles`，但前端没有 `SemanticLensBar` 或 `RelationLegend`，
也没有关系族开关、独显、恢复全部、计数与远景聚合边解束。

当前渲染仍存在固定裁剪和透明度经验值：

- local flow 只取前 6 条；
- 未聚焦人物线只取前 5 条；
- secondary relation 在远景可降到 `alpha=0.01`；
- book level 不在 SVG 证据层绘制场景证据关系。

这会再次把“降低线团噪声”误做成“关系几乎不可确认”，与文档要求的 semantic presence
相冲突。

修复归属：W1 前端补全；W6-9 只增加 plan relation family，不替代本修复。

### 3.3 P2：人物焦点合同存在，但没有完整用户入口

后端支持 `level=character`，合同和测试也存在；前端控制栏只有全书、章节、场景。
`CharacterThreadRail` 的选择当前只设置 `activeCharacterId`，用于高亮关系，不形成正式
character focus scope，也没有焦点历史。

修复归属：W1 交互补全。

验收：

- 点击人物可进入可回退的 character focus；
- 不删除全书节点，只改变关系和布局权重；
- 人物参与的全部章节和场景均可追溯；
- 提供返回上一焦点和全书的明确操作。

### 3.4 P2：文档要求的语义探索工具尚未实现

当前已有时间游标、构型切换、镜头 fit/reset 和无障碍列表；以下仍缺失：

- 语义透镜与关系图例；
- 搜索与搜索结果强制显标；
- 框选/套索比较；
- 小地图、视野外 beacon 和方位提示；
- 星仪视图书签；
- 叙事路径回放；
- 节奏、张力、承诺债务和审查风险热力层；
- “显示全部标签”临时检查模式；
- 完整键盘空间导航。

修复归属：拆成 W1-UX 两批。先做关系图例、搜索、小地图和焦点历史，再做套索、回放、
热力层和视图书签；不得一次塞入 `OrreryWorkbench.vue`。

### 3.5 P2：节点与正文阅读位置尚未双向同步

正式节点可打开正文长卷，阅读器也有目录和持久位置，但星仪节点没有把精确
chapter/scene unit 传给阅读器；阅读器当前位置也不会反向高亮星仪节点。

修复归属：W1 Reader/Orrery integration。

### 3.6 P2：持续 glyph 与离屏可达性只完成一半

Canvas 层保留节点图形，DOM Overlay 也保证章节、场景、当前、阻断和选中节点不因标签
碰撞消失，这是正确方向。但离开视野后的节点没有 beacon 或小地图，普通次级节点的
DOM 标签仍受 far/detail 和 56 项上限约束，用户无法主动验证被省略的标签。

修复归属：W1 搜索/小地图/显示全部标签批。

### 3.7 P2：自动化视觉验收不完整

现有 Python 性能夹具和 Vue 单元测试覆盖投影、布局、焦点、关系、窗口稳定性与增量
patch；仓库中没有可重复执行的 Playwright 四主题/四焦点视觉回归，也没有正式 canvas
pixel check 套件。

人工浏览器验收不能替代长期回归。后续星仪修改若没有截图和像素门禁，容易重新出现节点
空白、窗口遮挡、主题漏色和焦点丢关系。

修复归属：W1 验收基础设施。

## 4. 明确属于后续阶段，不算当前 W1 漏做

以下条目应保留到 W6-9/AO-8：

- CreativeExecutionPlan、Gate 注入和 Plan Patch 的星仪投影；
- Planner/Reviewer typed SSE；
- 计划差异、模拟、预算和审批窗口；
- Agent Observatory 的 plan/node/context/mutation receipt 时间线；
- 重规划时旧路径淡出、新路径生长和 fallback 回溯。

这些功能依赖 AO-3 至 AO-7 的后端合同。提前在前端伪造数据会形成第二套编排事实。

## 5. 实施建议

1. **W1-Fix A：焦点一致性**
   - 修正 scene 粒度章节选择；
   - 增加 character focus 和焦点历史；
   - 补 API/Store/组件/浏览器验收。
2. **W1-Fix B：关系可见性**
   - 让 renderer 消费 `relation_profiles`；
   - 增加图例、开关、独显、计数和远景聚合解束；
   - 删除固定 `slice()` 作为语义丢弃手段，改为确定性 LOD/bundle。
3. **W1-Fix C：空间导航**
   - 搜索、显示全部标签、小地图、beacon、键盘导航；
   - 节点与阅读器双向定位。
4. **W1-Fix D：高级叙事透镜**
   - 套索比较、路径回放、热力层、视图书签；
   - `LayoutHintProvider` 只输出受约束的视图提示，不写 Canon。
5. **W1-Exit：自动化验收**
   - 四主题、book/chapter/scene/character、100/300/1000 节点；
   - Playwright 截图、canvas pixel check、SSE 后焦点与窗口稳定性；
   - 低性能模式和 reduced-motion 功能等价。

## 5.1 2026-07-26 实施回执

W1-Fix A 与 W1-Fix B 已完成：

- `chapterRailFocusTarget()` 把底部目录锁为 chapter scope；
- `spatialProjection` Store 已支持 character focus、history 和 back；
- `RelationLensBar` 已提供 11 类真实关系的计数、显隐、独看与复位；
- `relationModeForLevel()` 和 `applyRelationLens()` 成为 Vue、SVG、Pixi 共用的纯模型边界；
- 固定关系裁剪已移除，人物列表不再隐藏后续条目；
- v3 焦点摘要已从旧全书文案改为实际焦点可读描述。

3.1、3.2 已关闭，3.3 的正式人物焦点与返回历史已关闭。3.4、3.5、3.6、3.7
仍保持开放，不因本次界面已有“关系镜头”而提前宣告 W1 完成。

## 6. 架构约束

- 不在 `OrreryWorkbench.vue` 中实现布局、关系裁剪、搜索索引或窗口正文；
- `relation_profiles` 是后端语义合同，前端只能选择显示策略，不能改写正式边；
- Focus Store 是唯一焦点真相；镜头状态不能替代语义 focus scope；
- 搜索、小地图、透镜和回放只读，不写项目资产；
- W6-9 复用现有 narrative v3 revision/SSE，不新建 v4，除非合同无法向前兼容；
- 任何 Agent Layout Hint 都必须由确定性布局引擎做边界、碰撞、稳定性和性能校验。
