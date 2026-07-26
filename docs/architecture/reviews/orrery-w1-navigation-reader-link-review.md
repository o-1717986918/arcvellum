# 星仪 W1-Fix C 空间导航与正文联动评审

> 日期：2026-07-27  
> 范围：W1-Fix C  
> 结论：通过；W1-Fix D 与 W1-Exit 不在本次通过范围内。

## 1. 交付范围

本子批只补齐星仪的只读探索和正文定位能力：

- 搜索叙事节点并让结果强制显标；
- 临时显示全部标签；
- 小地图、视野外 beacon 和方向键空间导航；
- 星仪正式节点与正文阅读单元双向定位。

没有增加 Canon、资产、正文或编排计划的写入入口，也没有提前伪造 AO-8 数据。

## 2. 架构判断

### 2.1 状态所有权

- `spatialProjection` Store 继续拥有唯一语义焦点；
- `readerNavigation` Store 只拥有当前阅读单元和定位请求；
- `spatialWindows` Store 继续拥有阅读器窗口；
- 镜头位置、搜索词和标签临时显隐均为会话级 UI 状态，不伪装成作品事实。

### 2.2 模块边界

- `model/spatialNavigation.ts`：搜索、方向邻居、小地图归一化和 beacon 几何；
- `model/readerLink.ts`：投影节点与 reader manifest 单元的身份转换；
- `OrreryNavigationLayer.vue`：紧凑导航交互，不实现布局和项目写入；
- `OrreryNodeOverlay.vue`：只负责标签可见性，不复制搜索索引；
- `OrreryWorkbench.vue`：只协调 Store、窗口、镜头和投影焦点。

`OrreryWorkbench.vue` 没有吸收搜索算法、几何算法或阅读单元解析，符合既定大文件边界。

## 3. 可靠性与风险

### 3.1 已控制风险

- 路径型 `source_id` 不再通过脆弱字符串包含关系匹配；
- 重复定位同一正文单元仍会增加 request sequence，避免请求被响应式去重；
- 阅读器打开时优先使用显式星仪请求，持久化旧阅读位置只作为恢复后备；
- 阅读器反向定位只在阅读器窗口存在时触发，避免后台 manifest 刷新擅自移动星仪；
- 搜索和小地图只改变视图，不写入正式资产。

### 3.2 剩余风险

- 当前小地图是投影导航，不是完整语义缩略图；高级关系热力层留到 W1-Fix D；
- 自动化组件测试覆盖数据和事件合同，但四主题截图及 canvas pixel check 尚未建立；
- 1000 节点布局已有性能测试，1000 节点 DOM 标签、搜索和小地图的端到端帧率仍需
  W1-Exit 记录。

## 4. 退出证据

- Client：37 files、118 tests passed；
- Python：628 tests passed、1 skipped；
- 生产前端构建和桌面资源同步：passed；
- Prompt Registry：54 assets、89 task prompt IDs、0 warning；
- Architecture Audit：35 file debts、224 function debts、0 cycle，无新增债务；
- 真实项目浏览器验收：搜索、精确正文打开、正文反向焦点和 1440x900 无遮挡通过。

## 5. 后续归属

W1-Fix D 继续负责套索比较、路径回放、高级热力层、视图书签和受约束
`LayoutHintProvider`。W1-Exit 负责主题、焦点、大规模节点、SSE 稳定性、reduced-motion
和像素回归。AO-8 只负责计划、Gate、Patch 与 Agent Observatory 投影。
