# ArcVellum CLI 文学可靠性与工程优化计划

> 文档状态：正式开发指导稿
> 审阅基线：`9cab45e`
> 审阅日期：2026-07-23
> 适用范围：ArcVellum Studio、内嵌 Literary Engineering Engine、Agent Worker、正式 CLI 状态机、创作与审查任务包
> 核心目标：消除“形式完成、语义空心”的流程风险，使 CLI 不仅能阻止 Agent 绕过步骤，还能证明每一步确实产生了下一步所需要的文学信息。
>
> 实施入口：`docs/roadmap/arcvellum-cli-literary-reliability-implementation-directive.md`。本文件负责问题分析与路线设计，实施入口负责唯一执行顺序、模块改动、迁移、测试和交付门禁。

---

## 1. 执行摘要

### 1.1 总体评价

ArcVellum 当前不是一个缺少流程的原型。相反，它已经具备相当成熟的文学工程内核：

- 正式路线、任务领取、任务打开、任务提交、任务完成、路线审计形成了状态机闭环。
- 场景开发已经覆盖上下文、角色推演、分支、字数预算、读者体验、叙事节奏、正文生成、精确候选审查、晋升、状态演化和 Canon 写回。
- 正文候选、审查和晋升之间已有文件摘要绑定，能够防止“审 A、晋升 B”。
- Style Lint、字数、读者体验、节奏、文风挂载、新角色登记和静态审查已经进入正式门禁。
- 同一项目的正式执行被串行化，降低了多个 Agent 同时写坏项目状态的风险。
- 测试、提示词注册表、前端构建和桌面端检查在当前基线下均可通过。

但是，当前最值得警惕的问题不是“流程不够多”，而是少数关键步骤存在双重契约：

1. 任务说明要求 Agent 修改某个语义产物。
2. Studio Worker 的正式写入白名单只允许提交一个完成标记。
3. 完成门禁只检查标记，不验证被要求产生的文学内容。

这会导致 RP、Composition Review、State Patch Review、Canon Patch Review 等步骤在界面上显示完成，但其语义成果可能没有进入下一阶段。此类问题属于 **P0 级假完成风险**，必须优先于新增功能、视觉扩展和更多 Agent 角色。

### 1.2 对 CLI 创作流程的可靠性结论

从工程逻辑上看，当前 CLI 的“顺序可靠性”较强，“语义传递可靠性”不足。

从文学创作上看，当前系统已经能控制字数、文风、格式、审查和项目资产，但对以下问题仍缺少可证明的正式闭环：

- 角色推演是否真实影响分支；
- 前一场的后果是否完整进入下一场；
- 分支是否来自角色欲望、恐惧、道德底线和不可逆代价，而非模板变体；
- 场景之间的承接是否是因果承接，而非字段齐全；
- 全书是否具有统一的主题矛盾、人物变化向量和终局方向；
- 读者问题、承诺、伏笔是否在长篇尺度上持续登记、到期和兑现；
- 生成 Agent 与审查 Agent 是否具有足够独立性；
- 全局节奏曲线是否真正属于正式 CLI 状态，而非前端直接编辑的旁路配置。

因此，当前内核适合继续演进，不需要推倒重写。下一阶段的核心不是继续增加步骤，而是建立：

> **可验证语义产物 + 因果传递 + 来源摘要 + 独立审查 + 原子写回**

---

## 2. 审阅范围与证据

### 2.1 实际审阅模块

本轮审阅基于仓库实际代码和命令面，不基于历史对话印象。重点覆盖：

- `src/literary_engineering_studio/worker.py`
- `src/literary_engineering_studio/api_server.py`
- `src/literary_engineering_studio/jobs.py`
- `src/literary_engineering_studio/contracts.py`
- `src/literary_engineering_studio/core_bridge.py`
- `src/literary_engineering_studio/read_model_cache.py`
- `src/literary_engineering_studio/opencode_binary.py`
- `src/literary_engineering_studio/project_interaction.py`
- `src/literary_engineering_studio_engine/task_registry.py`
- `src/literary_engineering_studio_engine/workflow_state.py`
- `src/literary_engineering_studio_engine/context_broker.py`
- `src/literary_engineering_studio_engine/context_packet.py`
- `src/literary_engineering_studio_engine/roleplay_lab.py`
- `src/literary_engineering_studio_engine/branch_lab.py`
- `src/literary_engineering_studio_engine/scene_composer.py`
- `src/literary_engineering_studio_engine/scene_readiness.py`
- `src/literary_engineering_studio_engine/candidate_promotion.py`
- `src/literary_engineering_studio_engine/character_state_evolver.py`
- `src/literary_engineering_studio_engine/canon_evolver.py`
- `src/literary_engineering_studio_engine/narrative_rhythm.py`
- `src/literary_engineering_studio_engine/longform_audit.py`
- `src/literary_engineering_studio_engine/memory_index.py`
- `client/src/services/api.ts`
- `client/src/stores/app.ts`
- `client/src/styles/components.css`
- `desktop/src-tauri/src/main.rs`
- `.github/workflows/release.yml`
- `pyproject.toml`

### 2.2 当前验证基线

在本轮审阅前的最近完整验证中：

- Python 测试：253 项通过。
- 前端测试：54 项通过。
- 前端类型检查与生产构建：通过。
- Rust `cargo check`：通过。
- Prompt Registry：36 个提示词资产、73 个任务提示词标识，校验通过。
- npm production audit：未发现生产依赖漏洞。

这些结果证明当前系统具有良好的实现基础，但测试主要证明“现有契约按现有定义运行”，不能证明契约本身完整。下一阶段应增加语义产物流测试、失败注入测试和长篇文学金样工程。

---

## 3. 当前正式创作链

### 3.1 正式路线

当前内嵌引擎提供以下主要正式路线：

1. `scene-development`
2. `longform-planning`
3. `source-ingest`
4. `style-engineering`
5. `character-and-world-assets`
6. `review-and-audit`
7. `export-and-release`

宿主和内置 Agent 的推荐入口是：

```text
workflow-dashboard
→ task-next
→ task-open
→ Agent 执行 task package
→ task-submit
→ task-complete
→ workflow-advance / route-audit
→ 重复
```

该结构是正确的，应继续作为唯一正式创作入口。

### 3.2 场景开发实际顺序

当前 `scene-development` 大致执行：

```text
Context Packet
→ Context Trace
→ Roleplay Prepare
→ Roleplay Agent Task
→ Branch Manifest
→ Branch Agent Task / Branch Selection
→ Scene Word Budget
→ Reader Experience Contract
→ Narrative Rhythm Contract
→ Composition
→ Composition Agent Task
→ Prose Candidate
→ Generation Agent Task
→ Exact Candidate AgentReview
→ Review Agent Task
→ Promotion
→ Promoted Draft
→ Static Review
→ State Patch
→ State Agent Task
→ Canon Writeback
```

这条链条在“步骤存在性”上已经足够完整。接下来需要把每个节点由“文件存在门禁”升级为“语义产物契约”。

---

## 4. 已实现优势

### 4.1 CLI 与状态机优势

- 正式命令面已经收敛，普通 Agent 不必从巨型命令箱自行挑选内部命令。
- `task-next` 和 `task-open` 能将当前任务、允许读取资料和预期输出动态下发。
- Studio Worker 以 `expected_outputs` 限制正式写入范围，方向正确。
- 正式项目按项目维度串行执行，避免同一项目多个任务并行争写。
- 路线审计不只看单个文件，而是检查上下文、任务完成、候选来源、审查、晋升和写回链。

### 4.2 长篇规划优势

- 字数预算不再只是总字数除以章节数，而是要求剧情库存、场景功能和展开程度与目标体量相匹配。
- 已明确禁止通过单纯拉长单场景来填补长篇字数缺口。
- 中文字数采用适合中文正文的统计口径，机器字符数只作为诊断。
- 章节义务、场景库存、预算和物化之间已有正式步骤。

### 4.3 正文与审查优势

- 文风提示词已经进入生成层，而非只在审查时补救。
- 文风文件长度、内容维度和挂载都有质量约束。
- 生成提示词包含 Canon、角色背景、读者效果、叙事节奏、场景衔接、字数、标点和降低 AI 味要求。
- Style Lint 会以确定性检测补充 AgentReview，避免模型用标点变体绕过规则。
- 审查与正文候选通过路径和摘要绑定。
- `pass_with_notes` 不允许直接晋升，必须修订并重新审查。
- 最终导出会过滤工作流痕迹、状态记录和其他非正文材料。

### 4.4 项目资产优势

- 角色、世界观、场景、状态、Canon、文风和来源提取均有标准化资产形式。
- 新角色需要登记，不允许正文中出现无法追踪的重要角色。
- State 与 Canon 使用候选补丁，不应由 Agent 任意直接覆盖正式资产。
- 路线审计能识别未应用补丁和未完成任务。

---

## 5. 关键问题清单

| 优先级 | 问题 | 主要后果 | 结论 |
|---|---|---|---|
| P0 | Agent Task 说明与 `expected_outputs` 不一致 | Agent 被要求修改的文件被 Worker 拒绝，最后只能提交空完成标记 | 必须先修 |
| P0 | RP 结果未被 Branch 生成读取 | 角色扮演成为仪式性步骤，分支与人物逻辑脱节 | 必须先修 |
| P0 | State Patch、Canon Patch 缺少一致的语义写回契约 | 状态或 Canon 可能以启发式空壳通过，或形成无法消解的待办 | 必须先修 |
| P0 | 提交、完成和文件写回非原子 | 失败时可能留下半提交任务状态 | 必须先修 |
| P0 | 非本地绑定时 API 鉴权不是强制 | 配置不当可能暴露完整项目 API | 发布前修复 |
| P0 | OpenCode 已存在文件未做可信摘要比对 | “verified” 可能只代表文件存在 | 发布前修复 |
| P1 | Composition Review 只提交完成标记 | 没有结构化 verdict，也无法正式退回修改 | 高优先级 |
| P1 | Longform 规划由同一 Agent 产出并自审 | 评审缺乏来源摘要和角色独立性 | 高优先级 |
| P1 | Context Trace 无来源文件摘要与新鲜度 | Canon、角色或大纲更新后仍可能使用旧上下文 | 高优先级 |
| P1 | 下一场没有可靠承接上一场后果 | 场景顺序正确但人物状态、关系和余波可能断裂 | 高优先级 |
| P1 | 宏观节奏不属于正式 CLI 状态 | 前端可编辑，但不能证明进入长篇规划和场景生成 | 高优先级 |
| P1 | Scene Bridge 只查字段，不查前后语义匹配 | “有钩子”不等于下一场真的接住 | 高优先级 |
| P1 | 缺少持久 Reader Question / Promise-Payoff Ledger | 长篇悬念可能遗忘、拖欠或重复 | 高优先级 |
| P1 | Memory Retrieval 混入草稿、审查和被拒分支 | 生成可能被非正式信息污染 | 高优先级 |
| P1 | Review Agent 与 Writer Agent 独立性未保证 | 同一会话容易合理化自己的错误 | 高优先级 |
| P1 | 提示词约束过多但无优先级编译 | 可能造成僵硬、冲突和文学表达收缩 | 高优先级 |
| P1 | 缺少正式的主题、人物变化与终局脊柱 | 作品可满足篇幅但仍可能松散 | 高优先级 |
| P2 | Read Model 缓存每次递归扫描项目 | SSE 与页面刷新会放大 IO 成本 | 应优化 |
| P2 | SSE 固定重连、项目切换竞态 | 弱网络和切项目时体验不稳定 | 应优化 |
| P2 | 桌面启动端口存在 TOCTOU，readiness 只测 TCP | 可能连到错误服务或过早展示正式页面 | 应优化 |
| P2 | API、Jobs、Task Registry、CLI 文件过大 | 修改风险、测试难度和认知成本持续增加 | 渐进拆分 |
| P2 | CSS 重复和全局覆盖较多 | 视觉回归和窗口状态差异风险高 | 渐进治理 |
| P2 | CI、依赖锁定、日志忽略和发布标签管理不足 | 可复现性和仓库整洁度不足 | 应治理 |

---

## 6. CLI 文学与逻辑可靠性审计

## 6.1 长篇立项与故事脊柱

### 当前能力

当前长篇规划已经重视字数、卷章场景库存和章节义务，能够避免“50 万字目标只有短篇事件量”的明显错误。

### 主要缺口

字数库存充足不等于文学结构成立。正式路线目前没有强制建立并审查以下全书脊柱：

- 核心戏剧问题；
- 主角初始错误认知；
- 主角欲望与深层需要；
- 对抗力量及其合理性；
- 主题矛盾的两端；
- 主角变化向量；
- 不可逆中点；
- 终局选择；
- 结局状态与开篇状态的照应；
- 各卷不可替代的结构职责。

没有这些约束时，系统可能生成“事件很多、字数足够、每章也有任务”，但整体仍像持续加码的支线集合。

### 优化原则

在 `word-budget` 之前新增或整合 `story-architecture-contract`，但不创建第二套大纲系统。它只负责定义全书因果脊柱，并成为预算、场景库存、宏观节奏和结局审计的共同上游。

## 6.2 字数预算与素材库存

### 当前能力

该环节逻辑方向正确，已经能识别大纲体量不足，不鼓励用冗长描写填字。

### 主要缺口

- 预算候选和预算 Review 可由同一 Agent 一次性写出。
- Markdown 中的 `pass` 结论缺少候选摘要绑定。
- 评审未必能证明卷、章、场景库存足以承载主题变化和人物弧，而不只是满足数量。
- 宏观节奏、叙事距离、场景材质多样性尚未成为预算的硬输出。

### 优化原则

将“规划候选”和“规划审查”拆成两个正式任务，Review 必须绑定候选 SHA256，并输出结构化结论。预算不只分配字数，还要分配：

- 场景功能；
- 压力等级；
- 详略等级；
- 叙事距离；
- 信息增量；
- 人物变化；
- 读者问题和承诺；
- 章节收束方式；
- 节奏位置。

## 6.3 上下文构建与记忆

### 当前能力

Context Packet、Context Trace、角色/Canon/大纲/文风检索已经建立。检索过程可记录来源，优于把整个项目一次性塞入提示词。

### 主要缺口

1. Context Trace 记录路径，但没有记录每个来源文件的摘要。
2. Canon、角色、章节规划或文风更新后，旧 Context 仍可能被认为有效。
3. `previous_scene_tail` 当前没有可靠填充。
4. 上一场已批准但尚未应用的 State/Canon 变化不能稳定进入下一场。
5. Memory Index 可能包含被拒分支、审查记录、工作流痕迹和非正式草稿。
6. 词面检索对同义改写、隐性伏笔和长期人物关系召回有限。
7. Canon、角色、Plot、Style、Word Budget 在 Context Policy 中过多使用非必需配置。

### 文学风险

- 人物已经改变立场，下一场仍按旧状态行动。
- 上一场形成的关系债务没有进入下一场。
- 被拒绝的分支被检索后重新混入正文。
- 伏笔改写了说法后无法召回。
- 文风已更换，旧 Context 仍然有效。

### 优化原则

升级为 `context_trace.v2`：

- 每个输入路径记录 SHA256。
- 记录项目 revision、正式 Canon revision、角色状态 revision、文风挂载 revision。
- 记录上一场 promoted draft、approved state delta、approved canon delta 的摘要。
- 记录检索命中项的信任等级和来源类型。
- 在 RP、Composition、Generation 和 Review 前执行 freshness gate。
- 按项目策略动态声明必需上下文，而非固定全部可选。

## 6.4 角色推演

### 当前能力

RP 模板要求读取角色 BDI、恐惧、秘密、道德底线和背景故事，并从角色视角提出行动。这一文学理论基础是可靠的。

### 发现的 P0 问题

`roleplay-agent-task` 的正式 `expected_outputs` 只允许写入完成标记；但 RP Sidecar 要求 Agent 回填：

- 读取回执；
- 各角色行动提案；
- 世界后果；
- 分支候选；
- Director 评分；
- Canon 审查；
- 合并建议和写回候选。

Studio Worker 按正式白名单验收输出，因此 Agent 若真的修改 RP 文档，可能被判定越权；若只写完成标记，又可在没有实质推演内容时通过。

更关键的是，`branch_lab.py` 当前只检查 RP Sidecar 是否完成，并未读取 RP 的结构化行动和后果来生成 Branch。由此产生：

> RP 在流程上是前置门禁，在因果上却不是 Branch 的上游。

### 优化原则

将 RP 改为结构化正式产物：

```json
{
  "schema": "roleplay_result.v2",
  "scene_id": "scene_0001",
  "source_digest": "...",
  "characters": [
    {
      "character_id": "char_001",
      "belief": "...",
      "avoidance": "...",
      "intended_action": "...",
      "rejected_convenient_action": "...",
      "moral_reason": "...",
      "background_story_influence": "...",
      "next_scene_cost": "..."
    }
  ],
  "world_consequences": [],
  "canon_conflicts": [],
  "candidate_pressures": []
}
```

正式任务允许输出：

- `roleplay_result.v2.json`
- 人类可读的 `roleplay_report.md`
- `agent_completion.json`

Branch 必须读取并引用 RP 条目 ID。没有被引用的 RP 不得被视为已进入创作链。

## 6.5 分支生成与选择

### 当前能力

系统已经要求正式分支选择，支持用户决策，并能防止正文生成绕过选支。

### 主要缺口

当前 Branch 候选更多是确定性模板变体，如“角色逻辑优先”“冲突升级”“伏笔优先”。它们适合作为启发式种子，但不能替代真正的文学推演。

Agent 当前可以选、融合、否决，却缺少正式输出新的结构化分支集合的权限和 Schema。结果可能是：

- 从几个抽象策略标签中挑一个；
- 没有完整行动链；
- 没有不可逆代价；
- 没有明确谁因为什么采取下一步；
- 与 RP 推演的角色行动没有可追踪引用。

### 优化原则

引入 `branch_candidates.v2`：

- 每个分支必须引用 RP 行动和后果 ID。
- 包含触发、人物行动、世界反应、关系变化、信息变化、代价、不可逆点、下一场压力。
- 允许确定性 Branch Lab 生成种子，但标记为 `seed_only`。
- Agent 负责扩写、重组或新增候选。
- Branch Review 与 Branch Selection 分开。
- 用户或代理用户只选择“创作方向”，不直接编辑底层文件。

## 6.6 场景构成与正文生成

### 当前能力

Composition 已汇总场景目标、分支、字数、Reader Experience、Rhythm、文风、背景故事和 Canon。Prose Generation 的约束覆盖面很强。

### 主要缺口

1. Composition Agent Task 只有完成标记，没有结构化 Review。
2. Agent 发现 Composition 不足时，没有正式修订目标。
3. Prompt 中硬约束数量过多，缺乏优先级与冲突检测。
4. “避免 AI 味”如果不区分作品文风，可能误伤合法修辞。
5. 字数、节奏、文风、标点和读者效果同时以同等强度出现，可能造成文本僵硬。

### 优化原则

建立两层产物：

1. `composition_candidate.v2.json`
2. `composition_review.v2.json`

Review 必须给出 `pass / revise / block`。非 `pass` 自动进入 `composition-revision`。

增加 Prompt Compiler：

| 优先级 | 约束层 |
|---|---|
| 1 | 用户硬约束、游戏规则、Canon、事实 |
| 2 | 已选分支、场景功能、人物行为逻辑 |
| 3 | 挂载文风及其允许的修辞例外 |
| 4 | Reader Experience、Rhythm、Bridge、字数 |
| 5 | 标点、反模板表达、Style Lint 预防规则 |
| 6 | 上轮 Review 的局部修订要求 |

Compiler 输出短小的 `active_constraints`，完整规范以引用形式保留。冲突时不得静默叠加，必须生成冲突报告。

## 6.7 叙事节奏与场景衔接

### 当前能力

场景已具备功能、节奏、张力、读者效果、incoming/outgoing hooks 等字段；章节和长篇审计也能检测部分节奏问题。

### 主要缺口

- 当前更多检查字段存在和数值曲线，不充分比较相邻场景的语义承接。
- 宏观节奏计划主要由 Studio API 直接保存，不是正式 CLI 路线的一部分。
- 场景钩子缺少稳定 ID，下一场无法明确“接住了上一场的哪个钩子”。
- 章节结尾、叙事距离、场景材质多样性没有形成强审计。

### 优化原则

引入 `bridge_contract.v2`：

```yaml
incoming:
  - hook_id: hook_scene_0012_02
    type: emotional_debt
    handling: intensify
outgoing:
  - hook_id: hook_scene_0013_01
    type: reader_question
    due_window: chapter_06..chapter_09
```

正式审查比较：

- 前场 outgoing 是否被后场 incoming 引用；
- 引用后是兑现、延迟、反转、升级还是转移；
- 人物情绪、关系、物件、信息和空间位置是否连续；
- 连续多个场景是否同速、同密度、同叙事距离；
- 高潮前是否有蓄压，高潮后是否有余波；
- 章节结尾是否过度依赖同一种悬念句。

宏观 Rhythm Plan 必须进入正式 `longform-planning`，前端修改只能生成候选，不得直接改正式状态。

## 6.8 Reader Question 与 Promise/Payoff

### 当前能力

现有提示词和场景字段已经关注读者问题、承诺、暂扣信息、兑现和延迟。

### 主要缺口

这些信息还没有形成全书级持久账本，因此 Agent 很难稳定回答：

- 哪个问题拖欠最久；
- 哪个承诺即将到期；
- 哪个伏笔已被多个场景重复暗示；
- 哪个问题已经失去读者兴趣；
- 哪个兑现没有足够前置铺垫；
- 哪个反转违反了已建立事实。

### 优化原则

新增两个可由同一底层实现支持的正式 Ledger：

- `reader_question_ledger`
- `promise_payoff_ledger`

每项记录：

- 稳定 ID；
- 首次出现位置；
- 类型；
- 读者当前可知信息；
- 计划兑现窗口；
- 当前状态；
- 最近推进位置；
- 兑现证据；
- 超期程度；
- 与人物、物件、Canon 和分支的关系。

Longform Audit 必须报告超期、孤立、重复、无铺垫兑现和无兑现承诺。

## 6.9 AgentReview 与修订

### 当前能力

精确候选摘要、Style Lint 注入、文风和字数审查、`pass_with_notes` 阻断、重新审查等机制已经较强。

### 主要缺口

- Writer 与 Reviewer 可能是同一持久会话。
- Committee Review 可能只是一个 Agent 在同一上下文中模拟多个角色。
- Composition、Longform Planning、State、Canon 的 Review 没有达到正文 Review 的同等严谨程度。
- Review 可能列出问题，却没有验证修订是否逐项解决且未引入新问题。
- 反 AI 规则可能被机械执行，误伤特定文风中合理的节奏修辞。

### 优化原则

- Writer 和 Reviewer 使用不同会话 ID；条件允许时使用不同 Runtime。
- Reviewer 默认不读取 Writer 的自我解释，只读正式上下文、候选和审查标准。
- 所有 Review 绑定精确候选摘要。
- Revision 生成 `revision_map`，逐项记录问题、修改位置、处理方式和保留理由。
- Revision Review 同时检查：
  - 原问题是否解决；
  - 是否只是换一种同类生硬转折；
  - 是否产生语义反转；
  - 是否破坏文风；
  - 是否破坏 Canon、节奏和字数。
- 文风文件可以声明合法修辞例外，但例外必须具体、有限且可被审查。

## 6.10 人物状态与 Canon 演化

### 当前能力

系统坚持候选补丁、审查、批准、应用的方向，避免正文 Agent 直接修改正式资产。

### 发现的问题

State Agent Task 和 Canon Agent Task 与 RP 存在相同的输出契约冲突：

- Sidecar 要求 Agent 修改或覆盖 Patch JSON/Markdown。
- 正式 `expected_outputs` 只允许完成标记。
- Worker 若严格执行白名单，就无法提交真正修订后的 Patch。

此外：

- Canon 已有较明确的审批与应用路线。
- State Patch 缺少同等完整的正式审批、应用和前端决策生产器。
- Export/Audit 会发现未应用 State Patch，但用户可能没有明确的正式解决入口。

### 文学风险

- 人物状态停留在旧值，后续行为反复重置。
- 启发式状态变化被当作 Agent 审核结果。
- Canon 变化只存在于草稿或报告中，没有正式写回。
- 大量未应用 State Patch 最终阻塞交付。

### 优化原则

统一 `candidate → semantic review → human/proxy approval → atomic apply`：

```text
state-patch-candidate
→ state-patch-agent-review
→ state-patch-decision
→ state-patch-apply
→ context invalidation

canon-patch-candidate
→ canon-patch-agent-review
→ canon-patch-decision
→ canon-patch-apply
→ context invalidation
```

任何 Apply 都必须：

- 校验来源正文摘要；
- 校验目标文件当前摘要；
- 检测并发修改；
- 原子写回；
- 记录变更日志；
- 使受影响 Context Packet 失效。

## 6.11 全书审计与交付

### 当前能力

导出前已有路线审计、长篇审计、静态审查、补丁状态和正文过滤。DOCX/作品汇编不会故意携带工作流痕迹。

### 主要缺口

- 长篇审计对主题脊柱、人物变化、Promise/Payoff、叙事距离和章节结尾多样性覆盖不足。
- 审计可能发现问题，但缺少统一的“返工路由生成器”。
- 正文完成度、文学完成度和工程完成度没有明确分开。

### 优化原则

交付仪表应分别报告：

1. **正文完成度**：已晋升字数 / 目标字数。
2. **结构完成度**：计划场景、章节、卷的完成比例。
3. **文学闭环度**：人物弧、读者问题、Promise/Payoff、主题和结局义务完成比例。
4. **工程可信度**：任务、Review、Patch、Audit、Export Gate 的通过比例。

任何长篇审计失败都应生成正式 Repair Tasks，而不是只输出一份报告。

---

## 7. 工程可靠性审计

## 7.1 正式写回非原子

当前 Worker 大致按以下顺序执行：

```text
应用 expected outputs
→ task-submit
→ task-complete
```

若 `task-complete` 失败，文件可以回滚，但 `task-submit` 已写入的状态和提交记录不一定同步回滚。任务可能停留在半提交状态。

### 目标设计

新增 `task-finalize` 事务：

1. 在临时目录验证全部产物。
2. 计算摘要并生成 write set。
3. 锁定项目任务状态。
4. 原子替换正式文件。
5. 同一事务更新 submission、completion、route revision。
6. 失败时恢复文件与任务状态。
7. 记录可重放的 transaction journal。

## 7.2 Read Model 与 SSE

当前项目快照指纹可能递归扫描大量文件；SSE 和页面刷新会重复触发。缓存虽然记录过期时间，但没有形成强制失效策略，且部分影响展示的根目录未纳入 revision。

### 目标设计

- 使用变更日志或文件系统 watcher 更新项目 revision。
- Read Model 以 revision 为键，不在每次请求时全量 `rglob`。
- 把 Styles、Exports、Release、Decision 等正式影响面纳入 revision。
- SSE 只推送 revision 和局部事件，客户端按需拉取变化部分。
- 提供 watcher 不可用时的低频兜底扫描。

## 7.3 API 边界

本地桌面默认使用 localhost 与 token，方向安全；但 CLI 允许自定义 Host，只有设置环境变量时才强制 Token。

### 目标设计

- 绑定非 loopback 地址时，没有 Token 则拒绝启动。
- 桌面端每次启动生成短期 Token。
- 所有写 API 要求 Token；只读 API 也默认鉴权。
- 明确 CORS 白名单，不允许通配。
- 日志不得记录 Token、Agent 凭据或完整敏感提示词。

## 7.4 OpenCode 供应链验证

当前已存在的可执行文件可能只因“存在”而被标记 verified，计算出的摘要没有与可信清单比对。

### 目标设计

- Manifest 为每个版本、平台、架构记录 archive SHA256 和 binary SHA256。
- 已存在文件必须比对 binary SHA256。
- 不匹配时隔离，不允许静默继续。
- 安装器、更新器和运行时共用同一验证模块。
- UI 展示来源、版本、摘要状态和最后验证时间。

## 7.5 桌面启动与健康检查

当前端口选择存在“先探测、后启动”的时间窗口，readiness 主要依赖 TCP 可连接，不能证明连接的是正确版本的 ArcVellum。

### 目标设计

- 让 Sidecar 绑定端口 `0`，由操作系统分配，再通过父进程管道返回端口。
- 健康检查返回应用标识、版本、启动 nonce、协议版本和项目根状态。
- 桌面端只有收到匹配 nonce 的 ready 响应才结束加载界面。
- 启动失败只保留一个可读错误面板，不闪烁终端窗口。

## 7.6 前端流和竞态

当前 SSE 使用固定间隔重连；切换项目后多个异步请求可能交错，旧项目响应有机会覆盖新项目状态。

### 目标设计

- SSE 使用指数退避、抖动、Last-Event-ID 和连接状态提示。
- 项目切换使用 AbortController 取消旧请求。
- Store 响应带 project ID 与 revision，提交前再次比对当前项目。
- 所有决策、任务和进度事件具有稳定事件 ID，保证幂等。

## 7.7 模块规模

`api_server.py`、`jobs.py`、`task_registry.py` 和内嵌 CLI 已经过大。此时直接“大重构”风险高，但继续堆功能也会恶化。

### 渐进拆分边界

- API：Projects、Workflow、Agent Runtime、Decisions、Library、Settings、Release。
- Jobs：Lifecycle、Execution、Autopilot、Recovery、Telemetry。
- Task Registry：按 Route 分注册器，共用统一 Task Contract。
- CLI：Formal Surface、Internal Commands、Developer Diagnostics。
- 前端 CSS：Tokens、Shell、Orrery、Panels、Reader、Advisor、Settings。

拆分必须保持现有外部命令和 API 契约，先增加 characterization tests，再移动实现。

## 7.8 Git、CI 与发布

### 当前问题

- Release Workflow 主要由标签或手动触发，缺少完整 PR/Push CI。
- Python 依赖以最低版本范围为主，没有统一锁文件。
- 工作目录存在大量未跟踪日志，`.gitignore` 没有完整覆盖。
- 历史提交中存在大型快照式提交，回溯成本高。
- Release 标签与文档版本不完全一致。
- 缺少统一 `.gitattributes` 管理换行和二进制文件。

### 目标设计

- PR/Push CI：Python、Frontend、Rust、Prompt Registry、Task Contract Consistency、Packaging Smoke。
- 维护可复现的 Python、Node、Rust 依赖锁。
- 忽略运行日志、临时项目、构建缓存和本地安装器产物。
- 增加 `.gitattributes`，统一文本换行并标记二进制。
- 发布由单一版本源生成 Python、前端、Tauri、安装器和 Git Tag 版本。
- 每个 Release 生成 SBOM、校验和、变更日志和升级说明。

---

## 8. 目标架构原则

### 8.1 不推倒重写

保留：

- 正式路线；
- `task-next / task-open / task-submit / task-complete` 操作模型；
- Project Worker；
- Sandbox；
- Route Audit；
- Prompt Registry；
- Candidate/Review/Promotion 思路；
- Studio 前端与内嵌 Engine 的独立部署。

重构集中在“契约层”和“语义产物流”，不重做全部文学工具。

### 8.2 单一正式任务契约

每个任务只允许存在一份权威契约：

```json
{
  "task_id": "...",
  "task_type": "...",
  "source_paths": [],
  "source_digests": {},
  "expected_outputs": [],
  "output_schemas": {},
  "allowed_write_roots": [],
  "semantic_acceptance": [],
  "next_states": [],
  "review_policy": {},
  "approval_policy": {}
}
```

Sidecar、前端、Worker 和 Route Gate 必须由此生成，不再分别维护隐含要求。

### 8.3 完成标记不能代表语义完成

`agent_completion.json` 只证明 Agent 已结束执行，不能证明任务合格。正式完成必须同时满足：

- 预期产物存在；
- Schema 通过；
- 来源摘要匹配；
- 语义字段完整；
- 确定性检查通过；
- 需要 Review 时 Review 通过；
- 需要用户审批时审批已记录。

### 8.4 所有语义产物必须被下游消费

对每个正式产物建立消费者声明：

```text
roleplay_result
  consumed_by: branch_candidates

branch_selection
  consumed_by: composition

composition
  consumed_by: prose_generation

reader/rhythm/bridge
  consumed_by: composition + generation + review

state/canon_patch
  consumed_by: next_context + audits
```

没有消费者的“正式步骤”应删除、降为诊断，或真正接入下游。

### 8.5 UI 不能成为正式状态旁路

前端允许用户编辑：

- 创作方向；
- 节奏偏好；
- 分支选择；
- 文风挂载；
- Canon/State 审批；
- 修订方向；
- 扩纲方向。

但所有编辑都先生成 Candidate/Decision，再由 CLI 写入正式状态。前端不直接修改正式项目资产。

---

## 9. 分阶段实施计划

## Phase A：建立可靠性基线

### 目标

冻结当前行为，建立可证明的任务契约地图，防止修复过程中制造新旁路。

### 工作项

1. 生成全部正式 Task Type 的契约清单。
2. 对比 Sidecar 指令、`expected_outputs`、Worker 允许写入、Route Gate 和下游消费者。
3. 增加 `task-contract-audit` 命令。
4. 输出以下错误：
   - Sidecar 要求写入但未列入 expected outputs；
   - expected output 无 Schema；
   - completion 是唯一输出；
   - 正式产物无下游消费者；
   - `next_allowed_states` 与状态机顺序不一致；
   - Review 没有候选摘要。
5. 为当前项目制作最小长篇 Golden Project。

### 验收

- 全部正式任务契约可机器扫描。
- 当前已知 RP、Composition、State、Canon 冲突能被自动检出。
- CI 中 Contract Audit 失败会阻止合并。

## Phase B：修复 P0 假完成与原子写回

### 目标

任何显示“完成”的任务都必须具有可验证语义产物。

### 工作项

1. RP 改为 `roleplay_result.v2`。
2. Composition Agent Task 改为 `composition_review.v2`。
3. State Agent Task 允许写入正式 State Patch Candidate 与 Review。
4. Canon Agent Task 允许写入正式 Canon Patch Candidate 与 Review。
5. Completion Marker 与语义验收分离。
6. 新增 `task-finalize` 原子事务。
7. 增加中途失败注入：
   - 文件写入后失败；
   - submit 后失败；
   - complete 前失败；
   - route revision 冲突；
   - 目标文件被并发修改。
8. 修正所有重复维护的 `next_allowed_states`。

### 迁移

- 旧 Completion Marker 不自动视为 v2 语义产物。
- 已完成旧任务在打开项目时进入 `legacy_completion_needs_validation`。
- 能从旧 Markdown 提取的内容自动迁移；无法提取的重新发任务。

### 验收

- 空 completion 不再推进路线。
- Agent 对 RP/State/Canon 的实际修改不会被 Worker 误判越权。
- 任一写回失败后，文件状态和任务状态完全一致。

## Phase C：接通 RP、Branch、Composition 的因果链

### 目标

让角色推演真实决定剧情候选，而不是只在 Branch 前打勾。

### 工作项

1. `branch_candidates.v2` 强制引用 RP 条目。
2. Branch Seed 与 Agent-authored Branch 分开标记。
3. 每个 Branch 包含：
   - 触发；
   - 行动主体；
   - 动机；
   - 世界反应；
   - 关系变化；
   - 信息变化；
   - 代价；
   - 不可逆点；
   - 后续压力。
4. Branch Review 检查：
   - 是否为了剧情便利违背人物；
   - 是否存在伪选择；
   - 分支差异是否只是表述差异；
   - 是否新增未授权 Canon；
   - 是否提供足够后续剧情库存。
5. Composition 必须引用 Selected Branch、RP 和 Bridge IDs。
6. Composition Review 不通过时进入正式 Revision。

### 验收

- 删除 RP 内容会导致 Branch Gate 失败。
- 修改 RP 摘要会使 Branch、Composition 和后续 Context 失效。
- 分支报告能追溯到角色信念、欲望、恐惧和道德底线。

## Phase D：上下文新鲜度与场景连续性

### 目标

确保下一场知道上一场真正改变了什么。

### 工作项

1. 实现 `context_trace.v2` 来源摘要。
2. 新增 Rolling Scene Handoff：
   - 上一场结尾事实；
   - 人物状态差量；
   - 关系债务；
   - 未处理行动；
   - 空间与时间位置；
   - Incoming/Outgoing Hook；
   - 已批准待应用补丁。
3. Context Freshness Gate 进入 RP、Composition、Generation、Review。
4. 建立 Context Invalidation：
   - Canon Apply；
   - State Apply；
   - 文风重新挂载；
   - Branch 重选；
   - Scene Plan 修改；
   - Word Budget 修改。
5. 重构 Memory Index 信任层：
   - Formal Canon/Character/Promoted Prose：高；
   - Approved Planning：中；
   - Candidate：低且默认不进入 Generation；
   - Rejected/Review/Workflow：排除。
6. 先实现 BM25/字段过滤；Embedding 作为可选增强，不成为离线运行硬依赖。

### 验收

- 修改任一已读取正式文件后，旧 Context 自动失效。
- 被拒分支不会进入默认生成检索。
- 下一场必须显式处理上一场的状态和桥接条目。

## Phase E：长篇文学架构与节奏

### 目标

从“流程完整”提升为“作品具有长篇结构、呼吸和兑现能力”。

### 工作项

1. 新增 Story Architecture Contract。
2. 将 Global Rhythm Plan 纳入 `longform-planning`。
3. 建立 Volume、Chapter、Scene 三级节奏曲线。
4. 建立 Reader Question 与 Promise/Payoff Ledger。
5. 实现 Bridge Handshake。
6. 增加以下审计：
   - 场景功能重复；
   - 连续同速；
   - 连续高压；
   - 叙事距离单一；
   - 对话/心理/动作材质单一；
   - 章节结尾模板化；
   - 问题超期；
   - 伏笔无兑现；
   - 兑现无铺垫；
   - 终局与主题脊柱偏离。
7. Longform Audit 自动生成 Repair Tasks。

### 验收

- 50 万字计划可追踪到卷、章、场景和事件库存。
- 每个场景在宏观节奏中有位置，而非独立设置快慢。
- 相邻场景 Bridge 可以机器追踪并由 Agent 语义复核。
- 全书问题和承诺有明确生命周期。

## Phase F：审查独立性与 Prompt Compiler

### 目标

降低同一 Agent 自我合理化，以及约束过载造成的僵硬文本。

### 工作项

1. Runtime 增加 Role Session：
   - Writer；
   - Reviewer；
   - Canon Reviewer；
   - Planner；
   - Advisor。
2. Writer 与 Reviewer 默认不同会话。
3. Review 输入隐藏 Writer 自我解释。
4. 所有 Review 使用精确摘要。
5. 实现 Prompt Compiler 和冲突诊断。
6. 文风规则声明：
   - 核心特征；
   - 禁止特征；
   - 可用修辞；
   - 例外条件；
   - 频率上限；
   - 冲突时优先级。
7. Revision Map 与 Re-review 正式化。

### 验收

- 同一 Runtime 也能通过不同 Session 实现盲审。
- Prompt Compiler 可解释每条活跃约束来自哪里。
- 冲突约束不会静默叠加。
- 修订不是“换一种同类问题”，而有逐项验证。

## Phase G：运行时性能、安全与恢复

### 目标

使长时间自动创作不因缓存、连接、进程或状态不一致而空转。

### 工作项

1. Revision-driven Read Model Cache。
2. 增量 SSE 与指数退避。
3. 项目切换请求取消和 revision guard。
4. 非本地 API 强制 Token。
5. OpenCode 二进制摘要验证。
6. 端口由 Sidecar 原子分配。
7. Readiness 验证应用 nonce 和协议版本。
8. Agent Job 加入：
   - 心跳；
   - 阶段进度；
   - 无进展检测；
   - 可重试分类；
   - 幂等恢复；
   - 最大连续失败熔断。
9. 自动创作空转检测：
   - 同一 task 重复领取；
   - 连续没有新正式产物；
   - Agent 输出重复；
   - Decision 长期未处理；
   - Patch 长期未应用；
   - Context 反复失效。

### 验收

- 长时间运行时项目扫描成本与项目总文件数近似解耦。
- 网络短断不会丢任务或重复应用产物。
- 可执行文件被篡改时无法启动。
- Autopilot 能明确区分等待、阻塞、失败和空转。

## Phase H：模块化、前端契约与仓库治理

### 目标

降低后续修改前端、后端、Agent Runtime 和打包流程的成本。

### 工作项

1. 按既定边界渐进拆分大模块。
2. 前端只消费稳定 Read Model，不解析内部任务文件。
3. 所有用户决策卡使用统一 Decision Schema。
4. 前端对任务、Agent 会话、审查、节奏和 Ledger 采用结构化视图。
5. 清理重复 CSS、全局 `!important` 和无约束 z-index。
6. 增加 PR/Push CI。
7. 增加依赖锁、`.gitattributes`、日志忽略和版本单一来源。
8. 发布产物附带校验和、SBOM 和升级测试。

### 验收

- 修改一条 Route 不需要同时手改多个不一致的前端判断。
- 新增 Runtime Adapter 不需要修改文学内核。
- 新版本能从上一正式版本完成项目迁移和安装升级。
- 工作树默认不被运行日志污染。

---

## 10. 测试与验收矩阵

## 10.1 契约测试

- Sidecar 指令与 expected outputs 一致。
- 每个 output 有 Schema。
- 每个正式产物有消费者。
- 每个 Review 绑定候选摘要。
- 每个 Apply 绑定来源和目标摘要。
- 每个 task type 只有一个权威 transition 定义。

## 10.2 失败注入测试

- Agent 超时。
- Agent 输出非法 JSON。
- Agent 写出白名单外文件。
- Submit 成功、Complete 失败。
- Apply 前目标文件被修改。
- SSE 断线重连。
- 项目切换过程中旧请求返回。
- OpenCode 可执行文件被替换。
- 桌面启动端口被抢占。

## 10.3 文学金样测试

至少建立以下小型项目：

1. 单主角线性悬疑。
2. 多角色利益冲突。
3. 强文风历史叙事。
4. 多卷成长小说。
5. 高 Canon 密度架空世界。
6. 来源作品续写/改写。

每个项目验证：

- RP 是否影响 Branch；
- Branch 是否影响 Composition；
- 前场后果是否进入后场；
- 人物是否按状态演化；
- Reader Question 是否登记和兑现；
- 全局节奏是否能被场景执行；
- Review 是否能拦截故意植入的错误；
- Export 是否只包含正式作品。

## 10.4 性能测试

- 100、1,000、10,000 个项目文件时 Dashboard 与 SSE 延迟。
- 50 万字正文的 Read Model、全文审计和导出耗时。
- 100 个连续场景任务的内存增长。
- Agent 断线恢复和重复提交幂等性。

## 10.5 用户验收

- 用户可以只给创作方向，由 CLI 状态机逐步推进。
- 用户能清楚看到当前等待什么，而非只看到“等待处理”。
- 需要选择时一定出现决策卡。
- 选择后卡片消失，并能追踪已记录的正式 Decision。
- 用户能查看节奏、分支、状态和 Canon 变化，但不直接接触 JSON。
- 自动模式遇到高风险节点能按策略由代理用户或真人处理。

---

## 11. 发布门槛

下一个标记为“文学可靠性完成”的版本必须同时满足：

1. RP、Composition、State、Canon 不再存在完成标记空转。
2. RP 结果被 Branch 结构化引用。
3. Context 具备来源摘要与新鲜度检查。
4. 下一场显式接收上一场 Handoff。
5. State 与 Canon 都有完整 Candidate/Review/Decision/Apply。
6. 全局 Rhythm Plan 进入正式 CLI 路线。
7. Longform Review 与 Candidate 摘要绑定。
8. Writer 与 Reviewer 至少会话隔离。
9. Task Finalize 原子化并通过失败注入测试。
10. 非本地 API 强制鉴权。
11. OpenCode 二进制执行前完成可信摘要验证。
12. Golden Projects 全部通过正式路线与导出。
13. Python、Frontend、Rust、Prompt Registry、Contract Audit 全部进入 CI。
14. 安装、升级、首次启动和恢复路径完成桌面端验收。

---

## 12. 优先级与建议排期

### 第一批：必须先完成

- Phase A：Task Contract Audit。
- Phase B：假完成修复与原子写回。
- Phase C：RP → Branch → Composition 因果链。
- API 鉴权和 OpenCode 摘要验证。

这些问题不解决，继续增强自动创作只会更快地产生无法证明可靠的内容。

### 第二批：决定长篇质量

- Phase D：Context Freshness 与 Scene Handoff。
- Phase E：Story Spine、Global Rhythm、Bridge、Reader/Promise Ledger。
- Phase F：Review 独立性与 Prompt Compiler。

这些工作决定作品能否从“单场景合格”提升到“百万字尺度仍然连贯”。

### 第三批：决定产品耐久性

- Phase G：性能、恢复、进程、SSE。
- Phase H：模块化、CI、依赖与发布治理。

这些工作决定 ArcVellum 能否成为普通用户可以长期运行和升级的应用。

---

## 13. 明确不做

下一阶段不应：

- 推倒现有 CLI 状态机。
- 新建第二套文学项目格式。
- 用更多 Agent 角色掩盖任务契约问题。
- 让前端直接写正式 Canon、State、Rhythm 或 Branch 文件。
- 把 Embedding/向量数据库设为离线运行硬依赖。
- 用一个“总分”取代具体文学审计。
- 让 Subagent 编写正式正文。
- 用自动正则直接改写可能改变语义的文学句子。
- 为追求全自动而取消高风险 Apply 的可审计决策记录。
- 在修复 P0 前继续扩充大量可选 CLI 命令。

---

## 14. 最终判断

ArcVellum 当前架构适合这个项目，不需要整体重构。它最有价值的部分正是：

- CLI 是文学工程操作系统；
- Agent 是受控的创意执行者；
- Studio 是普通用户的项目客户端；
- 正式文件、任务、审查和审批形成可追踪证据。

真正需要重构的是任务语义契约，而不是项目方向。

下一阶段应把系统从：

> “Agent 按顺序走完了很多步骤”

升级为：

> “每一步都产生了结构化、可验证、被下一步实际消费的文学信息；任何旧信息、空结果、自我审查、未应用后果和旁路写入都无法伪装成完成。”

当这条原则落实后，ArcVellum 才能同时具备两种可靠性：

1. **工程可靠性**：不会空转、乱写、跳步、半提交或带着旧上下文继续。
2. **文学可靠性**：人物行动有原因，分支有代价，场景有承接，长篇有脊柱，伏笔有兑现，节奏有呼吸，审查有独立证据。

这应当成为后续所有功能、前端和自动化开发的共同验收标准。
