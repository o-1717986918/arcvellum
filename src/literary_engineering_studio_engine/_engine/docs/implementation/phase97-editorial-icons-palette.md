# Phase 97 - Editorial Icons And Ink-Blue Palette

本阶段继续优化前端视觉：在 Phase 96 的 Swiss 编辑部结构上，把高冲击红蓝黑配色调整为更适合长期写作工作台使用的“墨蓝 / 纸白 / 朱砂”系统，并用 imagegen 生成一套统一的编辑部物件图标。

## 设计判断

Phase 96 的红蓝黑方案足够醒目，但长时间使用会略硬，容易接近竞赛海报或后台看板。本阶段保留 Swiss 网格、hairline、硬边和大号状态数字，把色彩降噪：

- 墨蓝 `#111827`：替代纯黑，用于侧栏、正文封面和主结构线。
- 纸白 `#F7F7F8`：保持干净，不走廉价暖米色。
- 网格线 `#DDE2EA`：让界面继续有稿纸和排版感。
- 行动蓝 `#1F3A8A`：替代高饱和 Yves Klein Blue，用于主按钮和状态通过。
- 朱砂 `#D7263D`：只用于阻塞、审查提醒和正文主线，不大面积铺开。
- 橙色 `#FF4F00`：保留为极少数方向性提示。

这套配色更接近“现代文学编辑室 + 工程控制台”，比红蓝黑更耐看，同时不削弱流程门禁的可见性。

## 图标资产

使用内置 imagegen 生成一张 2x3 编辑部物件图集，再本地裁切为 6 个项目资源：

- `frontend/assets/editorial-icons/dashboard-board.png`
- `frontend/assets/editorial-icons/manuscript-page.png`
- `frontend/assets/editorial-icons/archive-folder.png`
- `frontend/assets/editorial-icons/character-dossier.png`
- `frontend/assets/editorial-icons/branch-cards.png`
- `frontend/assets/editorial-icons/style-card.png`

图标约束：

- 不含文字、数字、汉字、英文、logo 或水印。
- 不作为普通按钮图标使用，避免小尺寸下失真。
- 只放在能增强理解的位置：品牌章、已完成正文、作品档案封面、档案统计、档案详情、文风空状态。
- 仍以真实项目数据和 CLI/API 证据为界面内容，不用图像伪造项目状态。

## 已实现

1. 静态资源服务
   - `/ui/*` 增加 PNG/JPEG/WebP/SVG content type。
   - PNG 等二进制资源改为 `read_bytes()` 返回，避免图片被文本读取损坏。

2. 前端资源接入
   - 侧边栏品牌章使用 `dashboard-board.png`。
   - 项目总控的“已完成正文”使用 `manuscript-page.png`，包括空状态和正文封面。
   - 作品档案总览使用 `archive-folder.png`，统计卡分别使用正文、人物、场景和分支图标。
   - 档案详情根据分类挂载对应图标。
   - 文风挂载空状态使用 `style-card.png`。

3. 版本同步
   - 前端 `UI_VERSION`、包版本和 `/health` 版本同步为 `0.98.0`。

## 边界

- 图标只增强识别和亲和感，不替代 route gate、task sidecar、review、promotion 或 export readiness。
- 不生成带文字的图片，避免 AI 图像模型生成错字污染界面。
- 不把 AI 生成图像当作正式作品封面输出；这里只是控制台 UI 资产。

## 验证要求

- `python -m unittest discover -s tests -q`
- `python -m literary_engineering_workbench prompt-registry-validate`
- `git diff --check`
- 浏览器检查：
  - `/ui/assets/editorial-icons/dashboard-board.png` 返回 `image/png`；
  - 桌面和移动端无横向溢出；
  - 图标不会遮挡正文、状态、按钮或项目路径。
