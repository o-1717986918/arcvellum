# 星仪 W1 高级探索与 Layout Hint 边界评审

> 日期：2026-07-27  
> 范围：W1-Fix D  
> 结论：通过；W1-Exit 自动化视觉回归仍是独立开放项。

## 1. 交付范围

本批在现有 Narrative Projection v3 上增加只读探索能力，没有创建第二套投影或写入路径：

- 套索框选节点并形成并列观察托盘；
- 按当前语义粒度回放章节或场景路径；
- 节奏、张力、承诺债务和审查风险热力层；
- 按作品隔离的视图书签，保存焦点、构型、时点、时间窗口、热力层和导航节点；
- 前端受约束 Layout Hint 解释器；
- 后端 `projections/narrative/layout_hints.py` 成为唯一 Layout Hint 合同所有者。

## 2. 边界审计

### 2.1 只读边界

- 探索 Store 只写浏览器视图偏好，不写 Canon、人物状态、正文或项目资产；
- 热力层只从正式投影中的 rhythm、metrics、status 和 node type 派生显示强度；
- 路径回放只移动镜头并更新导航节点，不改变语义焦点和作品事实；
- 套索只产生前端比较集合；
- Layout Hint 只允许调整已存在节点的显示偏移。

### 2.2 Layout Hint 防线

只有同时满足以下条件的 hint 才会进入确定性布局：

- schema 为 `arcvellum/layout-hints/v1`；
- intent 明确 `enabled=true` 且 `status=validated`；
- 节点 ID 已存在；
- 章节/场景主节点偏移不超过 `1.2`，其他节点不超过 `3.2`；
- 应用后不触发碰撞阈值。

当前后端默认返回 disabled intent 和空 offset。这是为未来 Agent 创意布局留下的受控接口，
不是提前启用未经验证的 Agent 布局。

## 3. 产品验收

真实项目 `C:\Users\26532\Documents\ArcVellum\Works\1+1=2`、1440x900 下完成：

- 张力热力层作用于 15 个当前可见节点并显示“张力变化”图例；
- 路径回放从“第 1 章”推进到“第 2 章”，暂停后不继续移动；
- 视图书签可从编织恢复到脊柱，并恢复热力层；
- 书签文案为“全书 · 脊柱”，不暴露 `book · spine`；
- 书签面板不与关系镜头、章节目录重叠，小地图不与章节目录重叠；
- 套索几何和组件事件均由确定性测试覆盖；
- 验收创建的临时书签和热力选择已清理。

## 4. 工程证据

- Client：41 files、128 tests passed；
- Python：629 tests passed、1 skipped；
- `npm.cmd run client:build`：2,565 modules，desktop frontend sync 与 build verification passed；
- Prompt Registry：54 assets、89 task prompt IDs，0 error、0 warning；
- Architecture Audit：35 个既有 file debt、224 个既有 function debt、0 cycle；
- `python -m compileall -q src tests` 与 `git diff --check`：passed。

## 5. 剩余风险

本批没有把一次人工浏览器截图误称为长期回归。W1 仍需 W1-Exit：

- 四主题乘以 book/chapter/scene/character 焦点矩阵；
- 100/300/1000 节点截图和 canvas 非空像素检查；
- SSE 增量后焦点、窗口、书签和镜头稳定性；
- reduced-motion 与低性能模式功能等价；
- 可在 CI 或发布前重复运行的浏览器验收命令。

只有 W1-Exit 通过后，Living Narrative Field 才能整体退出。
