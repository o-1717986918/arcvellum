# ArcVellum v0.98 内置 Pi Worker 与连续创作闭环实施方案

日期：2026-08-11

状态：实施中

## 1. 交付目标

本轮只在以下条件同时成立时完成：

1. ArcVellum 主仓库拥有专用 Pi Worker 源码、测试、锁定依赖和第三方声明。
2. Windows 安装包携带可执行 Worker 及其运行时，用户无需安装 Node 或外部 Agent 平台。
3. 用户可在“连接与模型”中启用 Pi、选择模型、验证连接，并在推进仪表选择 Pi 作为创作执行器。
4. 从前端等价的用户路径创建一个新作品，选择全自动模式并明确授权。
5. 同一作品由 Pi 连续推进到第一场正文晋升、人物状态和连续性写回，并领取下一场正式任务。
6. 后台证据包含任务、会话、模型请求、工具、预检、修复、写回、Gate、费用和停止原因。
7. 不允许用分段 benchmark、手工补文件、调试豁免或仅单元测试代替连续闭环。

## 2. 架构决策

### 2.1 所有权

Studio/Engine 永远拥有：

- 作品和路线状态；
- TaskPackage、上下文编译与资源声明；
- 沙箱、确定性前置命令、preflight 和 canonicalization；
- writeback、task-complete、route-audit、promotion、state/canon apply；
- Autopilot、授权、预算、恢复和用户决策。

Pi Worker 只拥有：

- 执行一个已领取的 Agent-required TaskPackage；
- 读取 TASK_CONTEXT 与白名单资料；
- 写 Agent-owned expected outputs；
- 本地格式验证、显式完成或结构化阻断；
- 发出有界运行事件和真实用量。

Pi 不成为第二套工作流引擎，不直接读取正式项目路径，不领取下一任务，不运行 CLI、Shell、Git 或任意网络工具。

### 2.2 源码与上游

主仓库新增 `workers/pi-worker/`，迁入 ArcVellum 专用 Worker 源码与测试。整个 Pi monorepo 不复制进主仓库。

Worker 依赖锁定版本的 `@earendil-works/pi-agent-core`、`@earendil-works/pi-ai` 与 TypeBox。`third_party/pi/` 记录上游仓库、版本、摘要、许可证和升级流程。现有 `arcvellum-pi-agent` fork 保留为上游评估和补丁来源，不承担 Studio 业务逻辑。

这样可使 TaskContext、Worker 和安装器变更在同一 PR/CI 中原子验收，同时避免把 coding-agent、TUI、server 等无关包带入产品源码。

### 2.3 安装边界

首个正式可选版本使用“固定 Node 运行时 + 编译后的 Worker 资源”方案，优先可靠性和可诊断性，不在同一批引入未经验证的单文件打包器。

安装资源：

```text
desktop/src-tauri/resources/pi-worker/
  node.exe
  dist/
  node_modules/
  package.json
  pi-worker-installation.json
  PI-WORKER-NOTICE.md
  PI-WORKER-LICENSE.txt
```

构建脚本只复制 production dependency closure。安装收据绑定 Studio commit、Worker source digest、Pi 包版本、Node 版本、文件摘要和许可证。运行时先验证收据与关键文件，再启动 Worker。

## 3. 用户配置

### 3.1 Runner 配置

Pi Worker 的产品配置至少包含：

- enabled；
- model，格式为 `provider/model`；
- thinking preset；
- max turns、tools、repair、provider requests；
- credential source；
- bundled executable/entrypoint 自动发现结果；
- readiness、provider support 和预算支持收据。

开发环境可发现 `~/.pi/agent/auth.json`；桌面端不复制或回显密钥。正式 UI 只显示 Provider 已连接/未连接。首版复用 Pi 自有 CredentialStore，不建立第二套 HTTP Provider SDK。

### 3.2 前端

“连接与模型”新增 Pi Runner 卡片：

- 内置状态；
- 模型选择；
- 连接测试；
- 推理预设；
- 实验/正式可选成熟度；
- 成本、隐私和回退说明。

推进仪表新增执行器选择。开始、恢复、顾问“推进下一步”和全自动均读取当前项目选定 Runtime，禁止继续写死 `opencode`。运行中锁定 Runtime；切换只影响下一任务或新 run。

## 4. 连续端到端合同

### 4.1 测试作品

使用隔离的新作品，不修改用户现有作品。用户输入保持短而真实：中文近未来短篇，目标一章、至少两场，明确人物、冲突、结尾和字数。项目由正式创建 API 初始化，不复制 benchmark fixture。

### 4.2 启动路径

```text
POST /projects
PUT  /autopilot/policy  mode=full_auto
POST /autopilot/start   runtime=pi-worker, authorized=true
```

该路径与前端按钮相同。测试不得直接调用内部 Worker、runtime benchmark 或 Engine 私有函数推进作品。

### 4.3 完成证据

必须同时观察到：

- Pi Runner 探测为 installed/available；
- Autopilot run 的 runtime 为 pi-worker；
- 至少一个真实 Pi session 和 provider request；
- `scene_0001` 正文候选通过 Style Lint 和独立 AgentReview；
- candidate 被 promote 为正式正文；
- state patch 通过语义审查并 apply；
- continuity ledger delta 完成并 apply；
- route-audit 对 scene_0001 完成项通过；
- Autopilot 随后领取 scene_0002 或下一正式场景任务；
- 正式项目无 expected_outputs 之外的写入；
- 无未回收 Worker 进程；
- 前端可看到正文和推进状态。

### 4.4 后台监测

测试期间持续读取：

- `/autopilot/status`；
- `/agent-observability`；
- `/autopilot/runs/{id}/events`；
- workflow dashboard/route audit；
- 最新 run manifest、runtime JSONL、preflight 和 writeback receipt；
- promoted draft、state、continuity 和下一 task identity；
- Worker/Node 进程列表。

以下情况立即判定阻断并停止盲目重试：

- 同一 progress digest 连续出现；
- 只产生 reasoning、没有工具或文件活动；
- 读取未授权资料；
- prompt 与实际可读集合不一致；
- preflight 相同 issue 重复；
- writeback 后状态不前进；
- Runtime 被静默切回 OpenCode；
- 任务已完成但回合预算误判失败；
- 进程退出后仍被报告为运行。

## 5. 实施批次

### B1：源码与供应链

- 迁入 `workers/pi-worker`。
- 建立独立 package/lock、测试和 build 命令。
- 添加 third-party manifest、NOTICE、LICENSE、provenance builder。
- 保持现有 Pi fork 可同步。

门禁：Worker 单测、TypeScript build、Studio architecture audit、Git diff check。

### B2：运行时产品化

- 增加 bundled Worker locator/verification。
- 默认配置从 bundle 自动发现 executable、entrypoint 和 auth source。
- Pi probe API、配置保存和模型选择。
- 取消 experiment-only 构建级阻断，但保留用户显式启用。

门禁：无 Node PATH 也可探测 bundle；错误收据、缺文件、错误模型和缺凭证给出稳定错误码。

### B3：前端与全自动接线

- Runner 选择 store/API/UI。
- AutopilotPanel、AdvisorDock 和手动 Worker 使用选定 Runtime。
- Pi 设置卡、连接测试和运行状态。
- 运行中禁止无提示切换 Runtime。

门禁：Vitest、类型检查、生产构建、前端路径 API 断言。

### B4：连续 E2E 与系统修复

- 创建隔离作品并从用户 API 启动全自动 Pi。
- 持续监测直到下一场。
- 每个阻断先记录 root cause，再做最小系统修复。
- 修复后从干净测试作品重跑，不在损坏项目上手工续接冒充通过。

门禁：保存脱敏 E2E 报告、事件时间线、产物摘要和进程收据。

### B4-P：提示词工程全量审计与持久会话分层

该工作包在连续 E2E 暴露提示词或无进展问题时优先于继续重试。它不是只压缩正文
Prompt，而是审阅从 Engine Prompt Asset、TaskPackage、context contract、sidecar、
Prompt Program、Worker 工具描述到 repair turn 的整个提示词工程。

正式审计基线与逐项整改状态见
[`docs/quality/arcvellum-v098-prompt-engineering-audit-and-remediation.md`](../quality/arcvellum-v098-prompt-engineering-audit-and-remediation.md)。

#### 实际触发证据

- v7 正文任务的实际 `AGENT_TASK.md` 为 189,908 字符、5,043 行，包含 36 次
  “平台 Agent”、32 个 `[AGENT_TASK]` 和重复的 Skill/CLI 运行说明；
- 同一任务同时内联 Prompt Asset、生成 sidecar、三份角色资产 sidecar、context packet、
  composition、outline、budget 和重复检索片段；
- v8 世界观资产审查的 v2 正式 Prompt 为 27,869 字符，仍携带 Skill/平台 Agent 话术；
  同任务 Prompt v3 影子版本已降至 20,565 字符且移除 Skill 文件，但仍包含与当前审查
  关系较弱的整份大纲、预算和冲突矩阵；
- v8 在该审查任务已写出并通过本地验证两个产物后，仍被 no-progress guard 判为失败，
  说明提示词、工具停止合同和 Runtime 终止判定需要联合审计。

#### 三层信息模型

1. **Worker Bootstrap Profile：初始化一次**
   - 只包含沙箱边界、工具语义、输出所有权、主创正文权和停止协议；
   - 不包含项目路径、当前任务、Skill 文档、CLI 教程或文学资料；
   - 用版本和 SHA-256 标识，可由 Provider prompt cache 或同角色会话复用；
   - 对内部 Pi 使用 Worker Profile，不把宿主平台的 `SKILL.md` 当成 Pi 的 system prompt。
2. **Durable Project Session Context：同项目、同角色有界复用**
   - 只保存经过编译的作品身份、稳定 Canon 摘要、挂载文风身份和已确认资产摘要；
   - 每个条目必须绑定来源 digest、事实版本和失效条件；Canon、人物状态、文风挂载、
     creative plan 或模型变化时必须更新或新建会话；
   - 主创、审查、规划、资产维护使用隔离会话，禁止审查者继承主创的自我解释；
   - 会话历史只是缓存和交互连续性，不是正式事实源，不能覆盖当前任务证据。
3. **Ephemeral Task Contract：每个任务重新签发**
   - 只包含 objective、当前决策、Allowed Outputs、精确 schema、当前候选和任务所需证据；
   - 输出路径、候选 digest、当前人物状态、当前 Gate 和 writeback 条件不得依赖旧会话记忆；
   - repair turn 只发送失败项、对应产物片段和仍有效的合同摘要，不重放完整初始 Prompt。

#### 兼容与隔离原则

- Engine 的 `.agent_tasks.md`、`SKILL.md`、`AGENTS.md`、`agentread.yaml` 继续服务外置
  Codex/Claude Skill 宿主，不直接删除；
- Studio 根据 execution audience 编译提示词：`host-skill-agent`、`internal-pi-worker` 和
  `external-coding-agent` 不共享同一渲染结果；
- Pi Prompt 不得出现“装载本 Skill”“等待平台 Agent”“不要调用外部 LLM”“运行
  task-submit/task-complete”等宿主话术；
- sidecar 对 Pi 默认为 recovery/on-demand 证据。其结构化任务、schema 和输出合同由
  TaskPackage/PromptProgram 投影，不整份内联；
- 不以持久会话掩盖上下文选择缺陷，不把完整项目历史永久留在模型上下文中。

#### 代码实施点

1. `runtime/prompt_program.py`
   - 增加 execution audience / bootstrap profile identity；
   - Prompt digest 区分 bootstrap、project session 与 task contract digest。
2. `runtime/prompt_compiler.py` 与 `runtime/prompt_renderer.py`
   - 为 Pi 生成 Worker 原生 Prompt；每条边界、规则和输出合同只出现一次；
   - Prompt Asset 正文只提取当前任务决策，不重复 frontmatter、sidecar 和 validation gate。
3. `runtime/evidence_compiler.py` 与 `runtime/evidence_projection.py`
   - host 文档和 sidecar 对 Pi 降为 recovery/on-demand；
   - 按任务类型、资产类型和内容 digest 去重；
   - asset review 不默认内联整份全书预算和与候选无关的角色模板；
   - 保留 exact candidate、相关 Canon 和必要引用，不因压缩丢失审查依据。
4. `runtime/prompt_materialization.py`
   - Pi 的 structured/creative/planning/style/review/prose 全任务使用通过门禁的 v3
     tool-worker renderer；v2 只作为显式回滚，不再作为未匹配任务的静默默认值；
   - 保存 content-free prompt audit：各层字符数、重复率、剔除原因和 digest。
5. `runtime/session_lease.py` 与 `workers/pi-worker/`
   - 先实现同项目同角色的 bootstrap/session contract，再决定是否真正复用 Provider 会话；
   - 会话必须有最大任务数、最大时间、最大 token、模型/角色/项目/digest 一致性门禁；
   - 任一失效条件触发新会话，不在旧聊天历史上做事实增量补丁。
6. Worker 终止语义
   - 所有 required outputs 已写入且 `validate_output` 全部通过时，立即返回 success；
   - no-progress guard 不能把“重复验证已通过产物”覆盖为失败；
   - 工具失败、模型无活动、缺输出和语义预检失败使用不同错误码。

#### 全量审计范围

- 55+ Prompt Assets 的 frontmatter、正文、优先级和重复合同；
- 所有 route blueprint 的 source/reference/sidecar 列表；
- Prompt v2/v3 renderer、Task Context、Prepared Context、Context Packet、Evidence Pack；
- Pi system/bootstrap prompt、工具说明、模型消息、repair prompt 和 stop prompt；
- Style、标点、反 AI、字数、节奏、桥接、读者体验、Canon、状态、连续性和审查规则；
- 用户方向、Advisor 指令和 Creative Plan 是否被重复注入或错误提升优先级；
- 各任务类型的必要证据覆盖、冲突规则、无效历史说明和已经由代码强制的机械规则。

#### 量化门禁

- Pi 正式 Prompt 中 Skill/宿主残留命中数必须为 0；
- 同一规范化规则在同一 Prompt 中只出现一次；重复率 warning < 10%，error < 15%；
- structured/review 目标不超过 18k/30k 字符，planning/creative/style 不超过 32k/42k，
  prose 默认不超过 65k；超过时必须给出保真证据说明，不能静默退回 180k v2；
- 每种高风险任务至少有一个 fixture 覆盖“必要信息不丢失”和“无关资料未内联”；
- 同模型 A/B 比较首响应时间、总输入 token、Provider 请求数、工具调用、修复次数、
  文学盲评和正式 Gate 结果；只省 token 但质量或闭环率下降不通过；
- 真实连续 E2E 必须在提示词修复后从干净作品重跑到下一场，不复用失败项目伪装通过。

#### 明确非目标

- 不把所有文学规范做成永不更新的 system prompt；
- 不复用主创会话给独立审查 Agent；
- 不让会话记忆替代 Canon、人物状态、候选 digest 或正式 TaskPackage；
- 不删除外置 Skill 兼容能力；
- 不用简单截断、摘要正文候选或降低 Gate 强度换取速度。

### B5：安装与发布

- 全量 Python/Vitest/visual/architecture/prompt tests。
- 本地生产构建。
- 干净安装后从 UI 验证 Pi installed/available。
- 自动更新、卸载和进程残留检查。
- 版本、README、CHANGELOG、Release notes、Git 提交与 GitHub Release。

## 6. 质量与回滚

- 每批独立 Git commit；不把 B1-B5 压成单次不可回滚提交。
- 任何问题都不得通过关闭 Gate、扩大文件权限、增加无限重试或自动切回 OpenCode解决。
- 机械字段继续由 Studio canonicalization 生成；Pi 只提交语义产物。
- 正文只能由 Pi 主创 Worker 生成，任何未来子 Agent 仍禁止写正文。
- 若 Pi 连续闭环质量低于现有 Runtime，允许作为正式可选能力发布，不宣布为默认能力。

## 7. 当前进度

- [x] 已完成 Pi 真实规划、RP、正文和审查任务矩阵。
- [x] 已完成 Worker 终轮验证与 Studio 有界修复。
- [x] 已迁入专用 Pi Worker 源码并建立可打包的便携运行时。
- [x] 已接入普通用户前端配置、探测和 Runtime 选择。
- [ ] 旧的同一作品连续全自动闭环已暂停；提示词整改后必须从干净作品重新启动，禁止在旧失败项目上续接冒充通过。
- [x] B4-P 已完成全量 Prompt 审计、Pi 全任务原生 Prompt、稳定 Worker Profile、任务型证据策略、场景 Context Packet 投影、增量 repair、55 资产 audience lint 与真实正文 Prompt 导出。
- [~] 受控项目会话仅完成租约/身份基础；Provider 级复用明确延后到连续 E2E 通过之后，避免会话缓存掩盖证据缺口。
- [ ] 未完成同一作品连续全自动闭环。
- [ ] 未完成安装版连续闭环与发布验收。
