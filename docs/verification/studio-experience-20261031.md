# 工作室体验重构 · 2026-10-31

基线：已发布 v0.99.15（1173d8fd）。开发分支 `feat/studio-experience-20261031`，独立工作树；原开发目录与发布标签保持可回退。完整 Git bundle 已校验。

## 审查与设计

创作的中心是一段持续的对话。作品、资料、人物、正文和审查围绕它展开，使用者不应为寻找功能、恢复输入或辨认状态中断思考。

初步实证缺口：输入法确认键触发发送；发送清空后失败不能恢复；忙碌时 Enter 仍清空输入；草稿不按会话保存；流式输出强制滚动；较早消息只提示收起、无法展开；工作区兼容路由丢失查询上下文；读者搜索/切换章节存在异步覆盖；阅读按键干扰输入；导出链接绕过授权 transport；对话选择器没有焦点约束；工作区切换销毁缓存；现有界面叠加高不透明度使星仪背景被遮蔽。

视觉方向：矿绿玻璃书房。松墨 #203b33、玉绿 #28715d、雾纸 #f7faf7、冷银 #d1dfd5、墨蓝 #53658a、淡金 #977232。标题用宋体系列，正文用系统中文无衬线，数字等宽化。保留既有星仪与美术；记忆点是穿过透明界面可见的叙事星轨，以及对话纵向书脊。装饰服务定位，文案服务行动。

结构：左侧作品与工具 / 中央持续对话 / 右侧当前作品。工具展开占用中央与右侧；回到对话原位。统一快速切换可搜索所有工作区和会话，键盘与触屏同样可达。三层透明度：环境、导航、阅读；输入框保持文字对比。

## Module Change Packets

### 1. 连续对话
- objective: 输入、发送、阅读、恢复都保持用户上下文。
- primary_module: Vue project-agent
- public_entry: projectAgentClient / useProjectAgentSession / AgentComposer / AgentConversation
- variation_point: 消息提交受理与流式任务完成两个阶段。
- inputs: 既有会话、消息、job 和事件 DTO；会话作用域草稿。
- outputs: 既有提交与停止操作；可恢复草稿；可展开消息历史。
- invariants: 不自动重发任务；不改变顶层创作工具、任务或 Gate；中断不显示为完成。
- allowed_dependencies: Vue、既有 feature client、共享 UI、workspace registry。
- forbidden_dependencies: generic transport、Engine、第二模型调用。
- tests: 输入法、重复发送、失败恢复、草稿隔离、历史展开、流式滚动、浏览器交互。
- rollback_unit: 独立会话体验提交。
- documentation: 本文验收记录。

### 2. 统一导航与视觉
- objective: 所有功能可发现、可返回，透明界面支持长期阅读。
- primary_module: Vue workspace composition
- public_entry: projectAgentWorkspaces / router / StudioWorkspaceShell
- variation_point: viewport 与用户主题、动效偏好。
- inputs: workspace descriptors、现有会话摘要。
- outputs: 工作区导航、命令选择、焦点恢复与一致视觉。
- invariants: 保留所有 feature 入口、人物对话来源及对话实例；不引入新业务真相。
- allowed_dependencies: registry、共享 UI、Vue Router、已有设计资产。
- forbidden_dependencies: 跨 feature concrete imports、新服务端调用。
- tests: 全工作区桌面/移动截图、溢出/重叠、命令键盘导航、主题与减少动效。
- rollback_unit: 独立工作台体验提交。
- documentation: 本文验收记录。

### 3. 正文阅读与交付
- objective: 正文检索、章节切换和下载具有正确作用域与结果反馈。
- primary_module: Vue delivery / shared ManuscriptReader（分批提交）
- public_entry: deliveryClient / ManuscriptReader
- variation_point: 异步读取与下载完成顺序。
- inputs: 既有 reader / delivery DTO。
- outputs: 正确章节、搜索结果与下载文件。
- invariants: 仅展示正式正文；不改变导出审查、文件及版本合同。
- allowed_dependencies: deliveryClient、已有 stores、共享 UI。
- forbidden_dependencies: 直接 HTTP、项目文件修改、正式任务生命周期。
- tests: 反序响应、输入焦点、网络失败重试、授权下载及浏览器阅读路径。
- rollback_unit: 独立阅读与导出体验提交。
- documentation: 本文验收记录。

### 5. 作品库与首次建立
- objective: 回访用户先找到已有作品；新用户能以最少输入建立作品且不丢失构思。
- primary_module: Vue projects
- public_entry: projectsClient / ProjectsView / 既有 createProject 用例。
- variation_point: 首次建立与已有作品继续。
- inputs: 项目目录摘要、建立表单。
- outputs: 作品检索、保存于本机的创建草稿、原有项目建立操作。
- invariants: 不修改建立合同和目标规模约束；不改写既有作品；不隐藏可用高级选项。
- allowed_dependencies: 既有 store、projectsClient、desktopBridge。
- forbidden_dependencies: 新创作业务逻辑、generic transport。
- tests: 原项目选择流程、创建表单草稿、规模预设与全尺寸页面。
- rollback_unit: 独立作品库体验提交。
- documentation: 本文。

### 4. 作品切换的读取归属
- objective: 快速切换作品时，晚到的旧响应不能覆盖当前作品的正文、进度和交付状态。
- primary_module: Vue stores/app
- public_entry: useAppStore 现有 load 方法。
- variation_point: 并发读取完成顺序。
- inputs: feature client DTO、请求时作品根目录。
- outputs: 仅当前作品的展示快照。
- invariants: 不修改服务端事实；错误可见；原有接口签名兼容。
- allowed_dependencies: 既有 feature clients。
- forbidden_dependencies: generic transport、新业务 API。
- tests: A/B 项目反序响应、正文缓存归属。
- rollback_unit: 独立作品读取修复提交。
- documentation: 本文。

## 实现与验收

### 已修正的体验断点

| 使用过程 | 原问题 | 当前行为 |
| --- | --- | --- |
| 写消息 | 输入法误发、失败丢字、会话间没有草稿 | 按会话保存草稿，只在任务受理后消耗对应输入 |
| 看回答 | 流式输出抢走滚动位置；旧消息无法展开 | 尊重阅读位置，显式回到最新，逐批展开历史 |
| 找功能 | 工具散落，兼容路由丢上下文 | 统一检索所有工具与会话，保留参数、焦点和工作区现场 |
| 建立作品 | 表单靠前挡住已有作品；刷新丢构思 | 作品库先呈现作品，保存创建草稿，提供篇幅预设 |
| 刷新作品库 | 启动时误关作品库、弹出新对话 | 保持当前工作区；新对话由显式操作打开 |
| 读正文 | 旧响应覆盖、正文修订不刷新、方向键抢输入 | 请求与作品、章节及修订绑定；搜索命中高亮 |
| 下载与诊断 | 绕过开发代理与授权；诊断按钮不保存文件 | 统一消费授权响应，实际保存，显示操作结果 |
| 判断运行状态 | 停止、失败也可能显示完成 | 区分完成、失败、取消；工具和耗时同步呈现 |
| 视觉与窄屏 | 多层背景叠得不透；长导航挤压页脚 | 分层玻璃、可滚动导航、固定输入、窄屏与主题适配 |

### 本地检查

- Vue：99 个测试文件、324 项测试通过。含输入法、受理前失败、草稿作用域、较晚章节响应、修订更新、恢复位置竞态、项目读取归属、下载和兼容路由。
- Pi Worker：21 个测试文件、160 项测试通过；版本声明更新后重新构建。
- 浏览器：两组工作室验收共 13 项通过。覆盖完整人物对话往返、已有工作区、输入草稿、作品创建草稿、真实文件下载事件、深色、高对比、减少动效，以及 360 / 390 / 820 / 1024 / 1440 宽度的溢出和控件重叠检查。模型写入请求由验收夹具拦截。
- 前端生产构建、TypeScript 检查、桌面静态资源同步通过；166 个构建资产、2 个共用 WebP 美术素材。
- 架构审计通过：15 个既有文件债务、68 个既有函数债务、0 个依赖环、0 个 Studio 到 Engine 内部导入。没有增加债务预算。
- 13 处版本声明同步为 0.99.16；模块目录已生成并检查；Python 编译、CLI 帮助、doctor、59 个提示资产与 73 个任务提示的注册验证通过。
- Python 首轮执行 2,107 项：2,104 通过、1 项跳过、2 项档案流程超过测试固定的 15 秒等待期限。两项随后独立复测均通过（共 4 个档案用例）；保留原超时阈值，串行重跑全量并使用独立云端环境复核。最终结果随交付验证记录提供。
- 另一次专门的图集验收等待每个工作区的实际内容出现后截图，11 个工作区的桌面及手机画面均通过；不把异步加载中的空壳作为完成画面。

### 证据与范围

桌面、手机、夜间、快速切换及全部工具的截图汇总在随交付附带的 `ArcVellum-Experience/index.html`。截图使用确定性作品夹具；正文与对话里的验收内容不是对实际用户作品的改写。

浏览器验收改用独立配置、作品登记、数据和运行目录。审查时发现早期夹具会沿用默认配置；本轮仅移除了本工作树生成的三条夹具登记，先保存登记表备份，其余作品和文件保留。

本轮没有增加模型调用、替换模型连接或改变正式文学任务、晋升与交付合同；没有为每部作品生成背景。未重新执行付费模型长篇创作，也不将浏览器截图等同于原生 WebView 手工验收。macOS 仍为未签名预览。

### 回退

v0.99.15 发布标签、安装资源与经过验证的完整 Git bundle 保留。当前改动在独立工作树和分支中；原开发目录的未提交修改未被覆盖。前端变更不要求作品数据迁移。
