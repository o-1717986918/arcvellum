# Denova 与 ArcVellum 架构对比审阅

> 审阅对象：`alfredxw/denova`  
> 审阅基线：`024a463b8f333885821dae9643e392c13e8d617b`（2026-07-25 获取）  
> Denova 当前版本：v0.3.2 beta  
> 许可证：Apache-2.0  
> 审阅方式：GitHub 仓库树、README、设计文档、核心 Go/React 源码、测试目录与 CI 配置的静态审阅；未在本机执行 Denova  
> 目的：研究可参考的工程思想，不把“功能存在”误判为“适合直接移植”

落地任务已编入[自适应创作编排系统实施方案](../roadmap/arcvellum-adaptive-creative-orchestration-implementation-plan.md)的“Denova 借鉴成果落地任务组”，其跨模块归属、版本顺序和架构质量门禁由[v0.96 - v1.0 统一工程实施方案](../roadmap/arcvellum-v0.96-v1.0-integrated-engineering-implementation-plan.md)统一约束。

### 研究与实现硬约束

Denova 在本项目中只作为外部研究样本。ArcVellum 对所有相关能力均执行独立设计、独立编码和独立测试：

- 不复制或改写 Denova 源代码。
- 不复制 Prompt、Schema、配置、测试、文档段落、视觉资源或 UI 组件。
- 不把 Denova 包、模块或内部 API 加入 ArcVellum 依赖。
- 不按 Denova 文件逐行翻译或做语言间移植。
- 只提取问题定义、失败风险、职责分层和工程目标，再依据 ArcVellum 自身状态机重新设计。
- 任何实现均以 ArcVellum 现有契约、命名、数据模型、测试和视觉语言为唯一代码基线。

## 1. 结论先行

Denova 和 ArcVellum 都在解决 AI 长篇创作中的上下文、人物/世界资料、Agent 工作流、版本与用户控制问题，但两者的核心哲学不同：

- Denova 更像一个 **AI 原生写作 IDE + 互动故事/RPG 平台**。Agent 在应用内部长期工作，工具能力较广，Lore、编辑器、版本和对话体验成熟。
- ArcVellum 更像一个 **文学工程状态机 + 受控 Agent Runtime + 正式作品生产线**。任务包、双工作区沙箱、expected outputs、确定性预检、审查、晋升和写回 Gate 更强。

最合理的关系不是合并、Fork 或让 ArcVellum 变成 Denova，而是：

> 借 Denova 的 Agent 工程可观测性、上下文账本、工具能力注册、Mutation Receipt、版本差异和资料编辑体验；保留 ArcVellum 更严格的正式状态机、任务沙箱和文学 Gate。

Denova 最值得借鉴的五项：

1. Context Ledger 和持久会话压缩。
2. Tool Manifest、按读写性质分类的并发执行门禁。
3. Mutation Tracker、Change Group 和工具动作回执。
4. Git 版本时间线、差异、恢复与编辑冲突处理。
5. Lore/正文 IDE 的编辑器、可调整布局、国际化和长时使用纪律。

最不应直接借鉴的四项：

1. 通用 Agent 默认拥有文件写入、Shell 和 Web 的宽权限。
2. 以 post-run warning 代替 ArcVellum 的确定性正式 Gate。
3. 让 Git commit 本身等同于语义正确或正式晋升。
4. 把互动 RPG、图像生成和通用自动化同时塞进下一阶段核心路线。

## 2. 审阅证据

### 2.1 仓库规模与工程状态

在审阅基线中：

- 仓库树约 1375 个条目；
- 约 555 个 Go 文件；
- 约 609 个 TypeScript/TSX 文件；
- 约 190 个 Go 测试文件；
- 约 152 个前端 test/spec 文件；
- CI 同时运行 Go tests、`govulncheck`、前端测试、前端构建、发行构建和 Windows workspace change 回归；
- 后端基于 Go、CloudWeGo Eino、Hertz、go-git；
- 前端基于 React、TipTap、Monaco、TanStack Query、Motion、Radix/shadcn、i18next。

这说明 Denova 不是概念 Demo，但它仍明确标记为 beta，且提交和接口变化活跃。ArcVellum 仅研究其问题拆分和工程取舍，不依赖其内部 API，也不移植其实现。

### 2.2 主要模块

| Denova 模块 | 作用 | 对 ArcVellum 的意义 |
| --- | --- | --- |
| `internal/agent/` | Agent loop、工具、subagent、context、compaction、run ledger | 参考其职责拆分，ArcVellum 独立实现 Runtime 工程部件 |
| `internal/interactive/` | Director、Actor State、事件、规则和回合 | 参考“未来计划/当前状态/历史回合”的问题分区，重新定义 ArcVellum 真相模型 |
| `internal/book/versions/` | go-git 版本、diff、restore | 参考版本体验目标，独立设计档案 IDE |
| `internal/workspacechange/` | 工作区变更与审查 | 参考用户可见变更集的产品需求，独立定义 Change Group |
| `web/src/features/` | Lore、正文、Agent、自动化、版本和互动 UI | 参考编辑器产品能力，不复制组件和信息架构实现 |
| `DESIGN.md` | 设计 token、响应式、无障碍、长时使用规则 | 参考设计纪律，不复制视觉体系或文档规范 |

## 3. 总体架构对比

| 维度 | Denova | ArcVellum | 判断 |
| --- | --- | --- | --- |
| 产品定位 | 写作 IDE + AI Agent + 互动故事/RPG | 长篇文学工程工作室 + 正式状态机 | ArcVellum 更专注于“可靠交付长篇作品” |
| 后端 | Go 单体服务，Eino Agent | Python Studio + Literary Engineering Engine | ArcVellum 分层更明确，但跨层契约更多 |
| 前端 | React，TipTap/Monaco，IDE 密度高 | Vue/Tauri，叙事星仪与阅读/档案 | 两者可互补 |
| Agent 执行 | 应用内长期 Agent loop | 任务级受控 Runtime + OpenCode 等适配器 | Denova 更自由，ArcVellum 更可审计 |
| 项目写入 | 工具直接写工作区，再跟踪/检查 | 沙箱只写 expected outputs，预检后事务写回 | ArcVellum 更适合正式生产 |
| 版本 | 本地 Git 版本/恢复 | 正式候选、晋升、任务事件、发布 | Denova 版本 UX 更成熟，Arc 语义 Gate 更强 |
| 上下文 | 长期对话压缩 + Context Ledger | 每任务 Context Broker + trace/digest | 应形成混合方案 |
| 编排 | Agent loop、Plan UI、互动 Director | 固定 route + task-next 状态机 | Arc 的新自适应 Plan Compiler 更适合正式长篇 |
| 并发 | 工具按只读/有状态分流，workspace RWMutex | 项目级单正式执行 owner | Denova 模式可借，但 Arc 需更细资源图 |
| 自动化 | 通用 Agent/Automation | 文学路线 Autopilot + 授权策略 | Arc 领域约束更强 |

## 4. 真相分区：最重要的架构启发

Denova 在互动故事设计中明确区分：

- Turn：已经发生的历史；
- Actor State：当前事实；
- Lore：稳定资料；
- Director Plan：未来意图。

这对 ArcVellum 非常有价值。ArcVellum 应正式定义：

| ArcVellum 分区 | 对应内容 |
| --- | --- |
| Historical Truth | 已晋升正文、任务事件、发布版本 |
| Current State | 人物状态、关系、时间线、承诺债务 |
| Stable Knowledge | Canon、角色背景、世界规则、正式文风 |
| Future Intent | CreativeExecutionPlan、场景库存、节奏策略 |
| Evidence/Opinion | Review、Lint、模拟、研究与推断 |

这样能避免新编排系统把“准备写什么”污染成“作品里已经发生什么”。

Denova 的 Director Plan 还包含：

- revision；
- baseline hashes；
- run status；
- optimistic concurrency；
- 运行期间发生手工更新时拒绝覆盖；
- staging docs 全部完成后一次发布。

这些机制揭示了 revision、baseline hash 和冲突保护的重要性。ArcVellum 应依据自身任务沙箱和正式状态机，独立设计 plan revision、base project fingerprint、Plan Patch 和原子激活。

但需要澄清：Denova 的 Director Plan 主要服务互动回合和导演资料，并不是一个通用、可编译、带强制 Gate 的文学任务 DAG。ArcVellum 仍需自己的 Plan Compiler。

## 5. Agent Loop 与工具权限

### 5.1 Denova 的优点

Denova 的工具注册中心具有：

- 稳定的工具注册顺序；
- 能力族；
- 针对不同 Agent kind 的权限覆盖；
- skills、lore、todo、file、shell、web、image 等能力；
- Tool Manifest 驱动的只读/有状态分类；
- 并行工具调用时，只读共享锁、有状态独占锁；
- Mutation Tracker 记录工具调用目标和变更状态。

这比仅靠 Prompt 说“不要乱写”可靠。

### 5.2 对 ArcVellum 的正确借法

ArcVellum 已有：

- `runtime_capabilities_required`；
- OpenCode deny-by-default profile；
- 双工作区沙箱；
- expected outputs；
- deterministic preflight；
- 项目单执行 owner。

应新增 `CapabilityManifest + ResourceClaim`：

```text
TaskPackage
  -> machine-owned capability manifest
  -> declared read set
  -> declared candidate write set
  -> formal write set
  -> ResourceLockManager
```

Denova 的 workspace RWMutex 可以作为第一参考，但 ArcVellum 不能只做“整个工作区一把锁”。需要按资源区分：

- scene prose；
- scene review；
- character state；
- canon；
- promise ledger；
- timeline；
- release。

### 5.3 不应照搬

Denova 通用 Agent 的文件写入、Shell 和 Web 能力适合通用 IDE，但不适合 ArcVellum 的正式创作 worker。ArcVellum 应继续：

- 默认拒绝；
- 任务级授权；
- 主创正文单写者；
- formal write 只能走写回事务；
- 任意 Shell 永不进入正式文学路线。

## 6. Context Ledger 与上下文压缩

### 6.1 Denova 的成熟点

Denova 的 Context Ledger 记录模型实际看见的每个片段：

- source；
- title；
- purpose；
- bytes/chars；
- hash；
- preview；
- included/truncated；
- limit 与 unit。

它的 compaction 还考虑：

- 模型上下文窗口；
- completion/tool reserve；
- pre-run 和 mid-run 压缩；
- 保留最近回合；
- 压缩重试；
- 持久 checkpoint/epoch；
- 因果、未解决问题和用户意图的保留。

### 6.2 ArcVellum 的现状

ArcVellum 的正式任务上下文更安全：

- task package 指定 source paths；
- Agent-visible workspace 与 control workspace 分离；
- Context Broker 和 trace/digest；
- 任务不依赖无限历史对话。

但 ArcVellum 在以下场景较弱：

- 顾问长对话；
- 编排总监长期理解作品；
- 用户看不见“模型究竟读了什么、哪些被截断”；
- 计划 provenance 不够直观。

### 6.3 建议

采用混合结构：

- 正式任务继续使用 bounded snapshot，不改成长期聊天记忆；
- 顾问和编排总监使用持久会话压缩；
- 每次规划和任务运行生成 Context Ledger；
- 压缩摘要必须绑定源 hash 和不可省略事实表；
- LLM 摘要只能用于导航，不能取代 Canon/State 原文；
- 前端展示来源、用途、大小、截断和更新时间，不展示隐藏思维链。

## 7. Mutation Tracker 与变更审查

Denova 的 Mutation Tracker 会记录：

- tool name/call id；
- workspace；
- target/source；
- post-check；
- idempotency；
- lore IDs；
- change group/review thread/change set；
- base revision/revision；
- review status/apply state。

ArcVellum 当前对正式写回更安全，但用户看到的“Agent 到底做了什么”仍可以更好。

建议新增统一 `MutationReceipt`：

```json
{
  "task_id": "...",
  "session_id": "...",
  "action": "write_candidate",
  "target": "reviews/scenes/scene_0001_review.json",
  "base_sha256": "...",
  "result_sha256": "...",
  "preflight": "pass",
  "writeback": "applied",
  "formal_effect": "none",
  "at": "..."
}
```

前端 Agent 观察面板应以 receipt 展示：

- 读取了哪些资料；
- 使用了哪些允许工具；
- 写了哪些候选；
- 哪些通过预检；
- 哪些正式写回；
- 哪些被拒绝以及原因。

不要记录或展示隐藏思维链。

## 8. Git 版本与 Archive IDE

### 8.1 Denova 的优点

Denova 使用 go-git：

- 初始化本地版本仓库；
- 提交工作区快照；
- 读取 commit 文件；
- diff；
- 恢复整个版本；
- 排除运行时目录；
- 编辑端支持 change/rebase/recovery。

配合 TipTap、Monaco、resizable panels 和版本组件，用户能像使用写作 IDE 一样管理正文和 Lore。

### 8.2 ArcVellum 应借什么

- 项目版本时间线；
- 资产/正文逐文件 diff；
- 编辑前 base revision；
- stale edit 冲突提示；
- 保存、候选、晋升和正式版本的视觉区分；
- 恢复前预览影响；
- 用户编辑和 Agent 修改的 change group。

### 8.3 不应如何借

Git commit 只说明“文件有一个版本”，不说明：

- Canon 合法；
- 引用完整；
- Review 通过；
- 正文已晋升；
- State patch 已审查；
- 作品可发布。

因此 ArcVellum 的关系应是：

```text
Owner/Agent candidate change
  -> diff/change set
  -> schema/reference/semantic gates
  -> formal promotion/apply
  -> optional Git snapshot
```

不是：

```text
git commit -> automatically formal
```

## 9. 计划与编排

Denova 的 Agent Plan Protocol 能从流式输出中解析 plan questions 和 proposed plan，并转成 UI 事件。这对 ArcVellum 的“计划生成过程可见”很有价值：

- 规划问题；
- 候选计划；
- 更新中的计划；
- 计划完成；
- 冲突与重试。

但该协议本身主要是流式 UI 协议，不具备 ArcVellum 需要的：

- mandatory Gate 注入；
- task kind allowlist；
- resource read/write graph；
- Freedom Budget；
- Plan Simulation；
- formal task binding；
- Progress Contract；
- bounded replan。

建议借“流式 plan event protocol”，不借“计划文本即执行”。

## 10. 互动 Director 的有限借鉴

Denova 的互动模块包含：

- Director Plan；
- Actor State；
- 事件机会与频率；
- 规则检查；
- 分支与回合；
- 基于 revision 的冲突保护。

可用于 ArcVellum：

- RP 与分支推演的当前/未来分区；
- 事件机会作为场景库存候选；
- 状态变化必须有显式 binding；
- Planner 运行期间用户修改导致 conflict，而不是覆盖；
- 重规划基于 trigger，不随意发生。

不应引入：

- 骰子和 RPG 规则作为普通小说默认机制；
- 回合制结构主导长篇叙事；
- 把互动 Actor State 直接映射成 Canon；
- 把所有小说场景处理成游戏事件。

## 11. 前端设计对比

Denova 的设计目标是“安静、可靠、适合长时间使用”，强调：

- 内容优先；
- 语义 token；
- 稳定布局；
- 响应式；
- i18n；
- 无障碍；
- 完整 loading/empty/error 状态；
- 不滥用渐变、霓虹、玻璃和装饰。

ArcVellum 的视觉签名是“叙事星仪/活叙事场”，更沉浸、更具戏剧性。两者不应互相取代。

ArcVellum 应吸收 Denova 的纪律：

- 星仪之外的工具窗口保持高密度和稳定；
- 资产 IDE 使用成熟编辑器信息架构；
- 所有操作有完整状态；
- 国际化和键盘操作进入基础设施；
- 动效表达真实任务状态；
- 长文编辑和版本 diff 不依赖星仪承担。

ArcVellum 不应照搬 Denova 的中性 IDE 视觉，否则会失去最有辨识度的产品资产。

## 12. 工程成熟度比较

### 12.1 Denova 的强项

- 测试文件和前端测试数量可观；
- CI 覆盖 Go、前端、漏洞检查、发行构建和 Windows 回归；
- 工具、context、compaction、mutation、version 都有独立模块；
- Web 编辑体验技术栈成熟；
- 长期会话和通用 Agent loop 比 ArcVellum 完整。

### 12.2 Denova 的风险

- beta 且变化快；
- 写作与 RPG 双领域增加边界复杂度；
- 通用 Agent 权限面较大；
- post-run verifier 在很多场景以 warning 为主，无法替代正式语义 Gate；
- 内部模块很多，直接依赖会造成升级耦合；
- Director Plan 不是通用任务 DAG；
- Git workspace mutation 与正式文学晋升不是同一个概念。

### 12.3 ArcVellum 的强项

- formal route、task-next/open/submit/complete 和 route audit；
- Agent-visible/control 双工作区；
- expected-output-only writeback；
- deterministic preflight；
- Review、promotion、state/canon patch；
- 字数、节奏、读者问题、文风和长篇 Gate；
- Agent Runtime 与 Literary Engineering Engine 分层。

### 12.4 ArcVellum 的风险

- 固定 route orchestration 缺乏作品级自适应；
- 顾问/Planner 长会话上下文管理不如 Denova；
- 资源并发模型只有项目级 owner；
- mutation/context 的用户可见性不足；
- 档案仍偏浏览器，不是成熟 IDE；
- 自定义视觉复杂度高，容易挤占基础交互和可访问性开发。

## 13. 借鉴矩阵

| Denova 能力 | ArcVellum 落点 | 优先级 | 处理方式 |
| --- | --- | --- | --- |
| Context Ledger | Planner、Advisor、Agent Observatory | P0 | 重新实现数据契约 |
| Compaction | Advisor/Planner persistent session | P1 | 参考压缩目标与风险，基于 ArcVellum 上下文契约独立设计 |
| Tool Manifest | Capability Manifest | P0 | 与 TaskExecutionContract 合并 |
| Tool RW Gate | ResourceLockManager | P1 | 从 workspace 锁升级到资源图 |
| Mutation Tracker | MutationReceipt、Agent 面板 | P0 | 重新实现 |
| Director revision/hash | Plan revision/base fingerprint | P0 | 参考并发冲突问题，独立设计 revision 与 digest 契约 |
| Plan stream events | 创作策略 SSE | P1 | 采用 typed events |
| Git versions/diff | Archive IDE 版本时间线 | P1 | Git 只做版本，不做 Gate |
| Monaco/TipTap | 资产/正文编辑器 | P1 | 评估 Vue 生态等价组件 |
| Change review/rebase | Owner transaction/冲突恢复 | P1 | 与正式写回事务结合 |
| Lore UI | Archive IDE | P1 | 借信息架构 |
| Skills/subagents | 只读分析任务插件 | P2 | 不开放正文 subagent |
| Automations | Campaign 触发器 | P2 | 保留文学授权和预算 |
| Interactive events | 场景库存/重规划触发 | P2 | 去 RPG 化 |
| Image generation | 封面/视觉资产 | P3 | 不进入核心路线 |
| PWA/remote | 远期多端 | P3 | 桌面稳定后再评估 |

## 14. 明确不借

1. 不把 Denova 作为 ArcVellum 运行时依赖。
2. 不 Fork Denova 后混入现仓库。
3. 不把 Eino 或 Go Agent loop 引入 Python Studio 作为第二主控。
4. 不开放通用 Shell 给正式创作 Agent。
5. 不允许 Agent 直接写正式 Lore/Canon。
6. 不以 post-run warning 替代 deterministic preflight。
7. 不以 Git commit 替代 Review/Promotion。
8. 不在自适应编排首版加入 RPG、图像生成和通用自动化。
9. 不复制 Denova 视觉体系覆盖 ArcVellum 星仪。
10. 不复制代码、Prompt、Schema、配置、测试、文档、视觉资源或 UI 组件，无论许可证是否允许。

## 15. 许可证与独立实现策略

Denova 使用 Apache-2.0，但 ArcVellum 对本轮研究采用更严格的项目约束：**不复制、不修改、不翻译移植 Denova 的任何实现材料。**

实施方式固定为：

1. 记录 Denova 解决的工程问题和暴露的风险。
2. 回到 ArcVellum 当前代码与状态机重新做需求建模。
3. 使用 ArcVellum 自己的类型、Schema、命名、算法和测试实现。
4. Code Review 检查新增代码是否出现 Denova 特有命名、文本或结构性逐行对应。
5. 依赖清单和发行包不得包含 Denova 模块或资源。

许可证信息仅用于准确描述审阅对象，不构成本项目复制代码的许可路径。

## 16. 推荐实施顺序

与自适应编排方案合并后，优先顺序为：

1. 定义真相分区和 CreativeExecutionPlan revision。
2. Context Ledger + Plan Provenance。
3. Capability Manifest + Mutation Receipt。
4. Plan Lint/Compiler/Simulator。
5. 场景级自适应编排。
6. Archive IDE 的 change set、diff、base revision 和 owner transaction。
7. ResourceLockManager 与只读并发。
8. Advisor/Planner 长会话压缩。
9. Campaign 自动化和更多可选工具。

不要先做：

- 通用 subagent；
- 全项目并发；
- 远程协作；
- RPG 事件系统；
- 图像生成流水线。

## 17. 最终判断

Denova 证明了三件事：

1. AI 写作产品不能只有生成按钮，必须有编辑、资料、版本、上下文和 Agent 可观测性。
2. 长期 Agent 需要 Context Ledger、compaction、工具能力清单和 mutation tracking。
3. 用户需要看见变更、理解版本并能恢复，而不是被状态机隔绝。

ArcVellum 则已经建立了 Denova 相对较弱的一面：

- 正式文学工程 Gate；
- 受限任务沙箱；
- exact output preflight；
- 审查、晋升和状态写回；
- 全书字数、节奏、文风和交付约束。

两者互补后的最佳方向不是“把 ArcVellum 做得更像 Denova”，而是：

> 让 ArcVellum 继续做最可靠的长篇文学工程内核，同时获得 Denova 式的 Agent 工程透明度、长期上下文管理和 IDE 级作者控制。

## 18. 主要参考

- [Denova 仓库](https://github.com/alfredxw/denova)
- [Denova README](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/README.md)
- [Denova 设计规范](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/DESIGN.md)
- [Agent Plan Protocol](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/internal/agent/plan_protocol.go)
- [Tool Execution Gate](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/internal/agent/tool_execution_gate.go)
- [Context Ledger](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/internal/agent/context_ledger.go)
- [Context Compaction](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/internal/agent/context_compaction.go)
- [Mutation Tracker](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/internal/agent/mutation_tracker.go)
- [Post-run Verifier](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/internal/agent/post_run_verifier.go)
- [Director Plan](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/internal/interactive/director_plan.go)
- [Git Version Store](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/internal/book/versions/git_store.go)
- [Denova CI](https://github.com/alfredxw/denova/blob/024a463b8f333885821dae9643e392c13e8d617b/.github/workflows/ci.yml)
