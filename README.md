# ArcVellum

> 让百万字长篇像软件工程一样可维护，也像一本真正的书一样可阅读。

ArcVellum 是面向小说、剧本与伪记录作品的本地 Agent 创作平台。它把人物、世界观、情节、场景、文风、字数预算、审查证据和正式正文放进一条可恢复、可追溯的生产线；Agent 负责创作判断，文学工程内核负责签发任务、验证产物和阻止跳步。

当前版本：**v0.7.0 Reader, Advisor & Narrative Observatory**。

![ArcVellum 叙事观测仪](docs/images/arcvellum-overview-v070.png)

## 为什么需要它

普通 AI 写作工具擅长写一段，却很难维护几十万字：人物会漂移、篇幅会坍缩、分支推演会被省略，审查也容易变成模型给自己放行。ArcVellum 不靠一条更长的 Prompt 解决这些问题，而是把创作拆成可验证的正式任务：

- **长篇规模有预算**：目标字数映射到卷、章、场景和剧情库存，生成与审查共同读取场景目标。
- **正文生成有前置推演**：角色扮演、分支比较、节奏、衔接、读者问题和 Promise/Payoff 进入正式链路。
- **设定演化有证据**：Canon、人物背景、状态变化和新角色候选独立维护，写回必须通过门禁。
- **文风约束进入生成层**：可挂载文风 Prompt 在正文生成前生效，并由确定性 Style Lint 与 AgentReview 复核。
- **Review 不能被跳过**：候选稿、审查、受限修订、晋升和导出使用同一份内容指纹。
- **最终作品保持干净**：Markdown 与 DOCX 过滤任务标记、Scene ID、Canon 注释、状态补丁和审查记录。

## v0.7.0 新体验

### 一本会随创作生长的书

正式正文阅读器按作品顺序自动拼接已晋升内容，支持分章或连续阅读、目录、全文搜索、书签、阅读位置恢复、字号、行距、日夜主题和全屏。正文按需加载，50 万字作品不会被摘要截断；创作继续推进时，新正文会温和提示，不会把读者从当前位置拽走。

![ArcVellum 正文阅读器](docs/images/arcvellum-reader-v070.png)

### 一位有边界的创作顾问

悬浮顾问支持五种内置人格和自定义人格。它可以自然讨论人物、结构、节奏与下一步，也会在任务阻塞、审查失败、需要选择或新正文可读时主动提醒。顾问只读取项目投影，不拥有文件、Shell 或正式写回权限；可执行建议仍必须经过白名单动作和工程门禁。

### 看见故事的结构，而不只看进度条

Narrative Observatory 把场景、分支、人物、Canon、读者问题、承诺与兑现投影成可追溯的故事脉络。节点生长、线路分叉、Canon 点亮和长卷增长都来自真实项目状态；大型作品自动聚合，键盘列表和减少动态模式保留完整信息。

### 安装后即可开始

- Windows 默认作品库为 `Documents/ArcVellum/Works`，也可在设置中更改。
- 桌面启动使用单文档过渡，后台进程在 Windows 下隐藏运行。
- 模型目录只在进入“连接与模型”或主动刷新时加载。
- Provider 列表在固定高度内滚动，不再拉长整个设置页。
- 安装包包含本地服务、文学工程内核和 OpenCode Runner，不要求预装 Python、Node.js、Rust 或浏览器。

## 工作方式

```mermaid
flowchart LR
    UI["ArcVellum 客户端\n作品、正文、选择、顾问"] --> API["本地应用服务\nSSE、项目与应用状态"]
    API --> CORE["文学工程内核\n任务包、状态机、硬门禁"]
    CORE --> BOX["单任务隔离工作区"]
    BOX --> WORKER["Agent Worker\n创作、推演、审查"]
    WORKER --> GATE["Schema、Lint、差异与正式写回"]
    GATE --> CORE
    API --> READER["正式正文阅读器"]
    API --> ADVISOR["只读创作顾问"]
    API --> OBS["叙事观测仪"]
    CORE --> RELEASE["完整 Markdown、DOCX 与发布清单"]
```

ArcVellum 内嵌文学工程内核，不依赖另一个 Skill 仓库。OpenCode 随安装包交付；Claude Code 与宿主 Agent 适配器保留为高级兼容方式。模型推理仍需要网络以及用户选择的有效模型服务。

## 快速开始

### 普通用户

1. 从 [GitHub Releases](https://github.com/o-1717986918/arcvellum/releases) 下载 Windows x64 安装程序。
2. 启动 ArcVellum，在默认作品库新建作品，或打开现有工程目录。
3. 进入“设置 > 连接与模型”，连接模型并选择默认模型。
4. 在项目总控写下创作方向，选择协作、监督自动或全自动模式。
5. 在“正文”边推进边阅读，在“交付”导出完整 Markdown 或 DOCX。

密钥由本地 Agent Runner 的认证机制管理，不进入作品、任务包、普通日志或 Studio 配置。

### 开发者

```powershell
git clone https://github.com/o-1717986918/arcvellum.git
cd arcvellum
python -m pip install -e ".[api,test]"
npm ci
python -m literary_engineering_studio serve --port 8791
```

浏览器开发模式访问 `http://127.0.0.1:8791/`。Vue 热更新开发可运行：

```powershell
npm run client:dev
```

## 开发验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src
python -m literary_engineering_studio_engine prompt-registry-validate --json
npm run client:test
npm run client:build
cd desktop/src-tauri
cargo check --locked
```

Windows 候选构建：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/build_desktop.ps1 -SkipPythonInstall -SkipNodeInstall
```

## 安全边界

- 本地服务默认只监听 `127.0.0.1`，桌面通过启动令牌建立受认证会话。
- Agent 只在任务沙箱中运行，越出 `expected_outputs` 的文件不会写回项目。
- 顾问与 CreativeSteward 使用只读投影，并在调用前后校验项目哈希。
- 用户选择、代理决定、审批、写回、失败、费用和发布身份均持久化审计。
- 正式模式不调用 `unreview`、debug waiver 或 `allow-unapproved` 类绕过开关。
- 数据库迁移前自动备份；诊断报告过滤凭证、正文全文和完整项目路径。

## 项目状态

v0.7.0 已完成默认作品库、桌面稳定性、完整正文阅读器、顾问人格与主动消息、Narrative Observatory v1，以及对应的 Windows 发布链路。它仍属于 Beta：进入 v1.0 前还需持续积累多类型长篇样例、长时间无人值守恢复证据、Windows 10/11 干净虚拟机安装与商业代码签名验证。

进一步阅读：

- [v0.7.0 阅读、顾问与叙事观测计划](docs/roadmap/arcvellum-v0.5.1-v0.7-reader-advisor-observatory-plan.md)
- [v0.7.0 发行说明](docs/releases/v0.7.0.md)
- [当前内核审查](docs/architecture/current-core-review.md)
- [发布与签名说明](docs/releases/RELEASING.md)

License: MIT
