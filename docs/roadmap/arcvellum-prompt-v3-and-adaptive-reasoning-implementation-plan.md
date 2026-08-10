# ArcVellum Prompt v3 与自适应推理预算实施方案

> 状态：待实施
> 编写日期：2026-08-10
> Studio 基线：`release/v0.97.0` / `640cc63`
> Pi fork 基线：`85bf8eff`
> 适用范围：Studio Prompt 编译、上下文投影、执行画像、Pi Agent Core 专用 Worker、Runtime benchmark

## 1. 结论先行

本轮优化应把“减少模型输入”和“减少模型推理”视为一个联合工程，但按可归因顺序实施：

1. 先建立 Prompt 体积、重复率、证据覆盖与推理用量基线；
2. 修正现有上下文分层在 shadow 模式下失效的问题；
3. 建立唯一权威的 Prompt v3 中间表示和任务类型配方；
4. 先在 structured/review 两类任务中启用 Prompt v3；
5. Prompt 稳定后再启用自适应推理预算；
6. 只有同模型 A/B 证明更快、更省且文学质量不降，才扩展到 prose/planning；
7. 本阶段不引入 Subagent，不把多模型并发与 Prompt/推理优化混在同一实验中。

这不是删除文学规则，也不是把复杂任务变成一句提示词。目标是让每条规则只出现一次，让确定性约束由代码负责，让模型只接收完成当前文学判断所需的任务、证据和创作标准。

## 2. 实际工程审计

### 2.1 当前 Prompt 链路

当前正式链路为：

```text
Engine TaskPackage
  -> scene/route context contract
  -> Studio select_agent_context
  -> context materialization
  -> PreparedPromptContext
  -> ExecutionContextEnvelope
  -> render_worker_program
  -> AGENT_TASK.md
  -> Runtime / Agent
  -> expected outputs
  -> deterministic preflight
  -> writeback
```

权威边界总体正确：

- Engine 负责路线、TaskPackage、Prompt Asset、输出与上下文合同；
- Studio 负责沙箱、上下文物化、Prompt 编译、Runtime、preflight 和写回；
- Runtime 只执行当前任务；
- Pi Worker 只消费任务程序和受控工具，不拥有项目状态机。

因此不得新建第二套任务状态、第二套 Prompt Registry 或第二套 preflight。

### 2.2 真实样本

2026-08-10 的 P6 同模型样本中：

| 样本 | AGENT_TASK.md | TASK_CONTEXT.json | 首轮内联 | 内联文件 |
|---|---:|---:|---:|---:|
| structured-world-foundation | 22,266 字符 | 14,191 字符 | 约 12,000 字符 | 14 |
| review-scene-candidate | 74,391 字符 | 19,935 字符 | 45,937 字符 | 10 |

review 首轮内联中包括：

- `scene_review.agent_tasks.md`：17,521 字符；
- `memory/context_packets/scene_0001.md`：11,835 字符；
- compact review context：6,206 字符；
- 场景、候选、文风、composition、branch、标点规范等精确证据。

同一个场景文件还以软记忆检索结果的形式多次出现在 context packet 中。文风、输出 Schema、门禁和执行纪律分别由 Prompt Asset 元数据、Prompt Asset 正文、CLI sidecar、compact review context、Task Program 和工具描述重复表达。

### 2.3 已定位的结构性问题

#### A. exact-on-demand 在 shadow 模式中没有真正生效

Engine 的 `scene_context_contract()` 已明确把完整 review sidecar 和 context packet 声明为 exact-on-demand。但是 Studio 的 `_exact_on_demand_context_paths()` 只在 `ContextBudgetMode.BOUNDED` 下返回这些路径。

默认配置仍是 `context_budget.mode=shadow`，因此这些文件虽在合同上是 on-demand，实际仍会被 prepared snapshot 整份内联。它不是文学任务需要，而是 rollout 语义与可见性语义被错误耦合。

正确原则：

> visibility tier 始终生效；rollout mode 只决定预算是否阻断，不能改变文件属于 must-inline、exact-on-demand、summary 或 excluded 的事实。

#### B. Prompt Asset 不是主要膨胀源

当前 exact Prompt Assets 已有结构化 frontmatter，正文通常很短。不得为了“重构 Prompt”重写全部文学资产。主要问题在 Task Program 组装时把 sidecar、context packet、重复合同和操作说明同时塞进首轮。

#### C. PreparedPromptContext 只做路径去重

`prompt_context.py` 能去除完全相同的路径，但不能处理：

- context packet 内嵌同一源文件的多个检索片段；
- compact context 已包含的确定性证据又被 sidecar 解释一遍；
- 同一 style/scene 事实同时以原文件、摘要和检索命中出现；
- output schema 同时以 JSON 合同和自然语言清单出现。

#### D. 推理控制是“名义等级”，不是总预算

`TaskExecutionProfile` 当前设置：

- structured：minimal；
- creative/planning/style/archaeology/prose：medium；
- review：high。

Pi Worker 把等级传给 Agent Core，并设置每级 `thinkingBudgets`，但没有：

- 单任务 reasoning token 总上限；
- Provider 请求次数上限；
- 最大可升级等级；
- 升级触发条件；
- Provider 是否真正支持该控制的运行时收据；
- 超预算后的稳定停止与重试策略。

真实 review 样本累计报告 23,505 reasoning tokens，证明单纯配置 `high/low` 不能作为可执行成本合同。

#### E. enforcement 默认不覆盖 Pi Worker

默认配置的 execution profile 为 shadow，enforcement Runtime 列表只有 OpenCode。若只修改 `_PROFILE_TARGETS`，Pi Worker 可能继续使用自身 legacy 设置，造成“代码看起来降级、真实运行没有变化”。

## 3. 目标与非目标

### 3.1 工程目标

1. 建立 Prompt Program v3 单一中间表示；
2. 同一规则、证据和输出字段在首轮 Prompt 中只出现一次；
3. exact-on-demand tier 在 off/shadow/bounded 三种预算模式下语义一致；
4. Prompt 编译结果可度量、可复现、可摘要比较、可回退；
5. 推理策略具备初始等级、上限、总预算、升级和停止语义；
6. 不支持推理控制的 Provider 必须报告 unsupported，不能伪装为已生效；
7. repair 只接收失败增量，不重放完整初始 Prompt；
8. 保持 Engine、Studio、Runtime 和 Worker 的现有所有权边界。

### 3.2 文学目标

1. 不压缩或摘要 exact candidate、正式正文和挂载文风中影响语气的原文；
2. 不因减少 Prompt 而丢失 Canon、人物状态、节奏、场景桥、字数和读者体验约束；
3. review 仍必须独立、挑刺、不能用 pass_with_notes 逃避修订；
4. 正文生成仍由主创 Agent 完成；
5. 降低推理强度不能退化为机械套模板、浅层审查或短篇摘要化。

### 3.3 明确不做

- 不重写全部 Prompt Assets；
- 不删除现有 TaskPackage 或 context contract；
- 不让 Runtime 自己决定读取任意文件；
- 不通过扩大 context window 掩盖重复；
- 不让 Subagent 代替普通文件读取；
- 不在本轮同时改变默认模型；
- 不把推理文字持久化为新的项目事实；
- 不因节省 token 放宽 Canon、review、promote 或 writeback Gate；
- 不在 benchmark 前把 Prompt v3 或推理预算设为全局默认。

## 4. 目标架构

```text
Engine TaskPackage + Prompt Asset + Context Contract
                    |
                    v
          PromptProgramCompiler
        /          |            \
Task Contract   Evidence Pack   Task Recipe
        \          |            /
                    v
          PromptProgram v3 IR
             |             |
             v             v
   File-Agent Renderer   Tool-Worker Renderer
             |             |
             +------ Runtime ------+
                        |
                Reasoning Budget
                        |
                 formal preflight
```

PromptProgram v3 是投影，不是新权威。任何字段都必须能追溯到 TaskPackage、Prompt Asset、ExecutionContextEnvelope 或正式证据文件。

## 5. Prompt Program v3

### 5.1 中间表示

新增 `runtime/prompt_program.py`，只定义少量不可变 dataclass：

```python
@dataclass(frozen=True)
class PromptEvidence:
    evidence_id: str
    source_ref: str
    source_sha256: str
    role: str
    tier: str
    fidelity: str
    body: str

@dataclass(frozen=True)
class PromptProgram:
    schema: str
    recipe_id: str
    task_identity: dict[str, str]
    objective: str
    decisions: tuple[str, ...]
    constraints: tuple[str, ...]
    output_contract: dict[str, object]
    evidence: tuple[PromptEvidence, ...]
    exact_on_demand: tuple[dict[str, str], ...]
    stop_contract: tuple[str, ...]
    metrics: dict[str, object]
    digest: str
```

限制：

- 不为每种任务建立子类；
- `recipe_id` 使用表驱动映射；
- IR 不保存 Runtime 命令、凭证、绝对路径或聊天历史；
- `body` 只出现在 must-inline 的 lossless/structured 证据；
- on-demand 只保存路径、角色、digest 与读取理由，不提前内联正文。

### 5.2 单一权威映射

| 信息 | 唯一权威 | Prompt 投影 |
|---|---|---|
| task/route/state/role | TaskPackage | identity，一次 |
| 用户方向 | `user_directions.md` | objective 前置，一次 |
| 文学任务说明 | exact Prompt Asset | objective/decisions |
| 输出路径 | ExecutionContract | output contract |
| Schema | semantic output contract | digest + required semantic fields |
| 文件权限 | ExecutionContextEnvelope | evidence tiers |
| Canon/人物/文风事实 | 正式项目文件 | Evidence Pack |
| lint/budget/rhythm | compact deterministic evidence | Evidence Pack |
| 完成条件 | completion contract | stop contract |
| 格式/存在性 | preflight/tool schema | 不重复写成长篇说明 |

### 5.3 Evidence fidelity

每份证据必须标记保真等级：

- `lossless`：candidate、正文、挂载文风、关键角色原始状态；禁止摘要；
- `structured`：scene YAML、compact review evidence、Canon JSON/YAML；可做字段投影但不得改值；
- `summary`：已带 digest 的正式摘要；只能辅助，不能覆盖 lossless/structured；
- `retrieval`：软记忆片段；必须携带 source_ref、score 和 trust tier；
- `recovery`：完整 sidecar、实现说明；默认 exact-on-demand。

### 5.4 Evidence 去重与优先级

新增 `runtime/evidence_compiler.py`，按以下顺序执行：

1. 规范化相对路径；
2. 相同路径只保留一个正式表示；
3. 相同内容 SHA-256 只保留最高保真表示；
4. compact evidence 已投影的 deterministic contract 不再从 sidecar 内联；
5. exact scene/style/candidate 已存在时，context packet 中同源 retrieval 命中不再内联；
6. 同一 retrieval source 最多保留两个互不重复片段；
7. 丢弃项写入 content-free dedupe receipt，包括 source_ref、原因和字符数，不记录作品正文；
8. 任何 must-inline lossless 证据不得因去重被摘要替代。

表示优先级：

```text
exact candidate/body
  > exact formal structured source
  > compact deterministic evidence
  > digest-bound summary
  > soft retrieval
  > recovery sidecar / implementation manual
```

### 5.5 修正 visibility tier 语义

修改 `runtime/context_materialization.py`：

- `_exact_on_demand_context_paths()` 不再依赖 `budget.mode == bounded`；
- 只要 Engine 声明 exact-on-demand，off/shadow/bounded 都不得首轮内联；
- budget mode 只控制字符上限是否阻断；
- ExecutionContextEnvelope 必须继续记录 tier 与 digest；
- shadow 模式同时生成“若采用旧逻辑会多内联多少字符”的观测字段。

该改动优先于 Prompt v3，因为它可以在不改变文学 Prompt 的情况下直接移除 review sidecar/context packet 的首轮膨胀。

### 5.6 任务类型配方

新增 `runtime/prompt_recipes.py`，使用一个映射表，不创建类树：

| Task kind | 首轮核心证据 | 默认 on-demand | 不应出现 |
|---|---|---|---|
| structured | 用户方向、目标、Schema 语义、相关正式事实 | sidecar、模板、实现文档 | 全项目说明 |
| creative | 场景目标、角色状态、Canon、分支、节奏 | 历史恢复材料 | review 教程 |
| planning | 总体目标、现有结构、字数与义务、Canon | 低相关场景全文 | 正文生成规则全集 |
| style | 语料、现有 style profile、评测合同 | 历史实验报告 | 无关项目资产 |
| archaeology | 输入文本、提取 Schema、已有身份映射 | 完整历史索引 | 正文风格清单 |
| prose | composition、branch、scene、相关角色/Canon、挂载文风、字数/节奏 | sidecar、审查实现细节 | 审查报告模板 |
| review | exact candidate、scene、compact review evidence、挂载文风 | full sidecar、context packet | 重复 Schema 与软记忆同源片段 |

每个配方定义：

- evidence roles；
- fidelity 要求；
- section 顺序；
- 首轮软/硬字符目标；
- on-demand 最大调用数；
- 允许出现的 constraint categories；
- 输出合同渲染方式。

### 5.7 双 Renderer

新增 `runtime/prompt_renderer.py`：

1. `render_file_agent_program()`
   - 用于 OpenCode 等文件型 Agent；
   - 保留简短沙箱纪律；
   - 明确 Allowed Outputs；
   - 不重复工具型 Worker 已知的七工具说明。

2. `render_tool_worker_program()`
   - 用于 Pi Worker；
   - 系统 Prompt 已声明工具边界，用户 Prompt 只提供 objective、evidence、output semantics 和 stop contract；
   - 输出路径和写入权限由工具 Schema 强制；
   - 不重复“不要 Shell/不要改 source”等已经无法违反的限制，保留一条证据注入防线即可。

`runtime/task_program.py` 保持公开 facade：

```python
render_worker_program(..., prompt_version="v2", renderer="file-agent")
```

v2 在迁移期继续存在；调用方不得直接导入 v3 内部模块。

### 5.8 Prompt Metrics 与 Prompt Lint

新增 `runtime/prompt_metrics.py`，生成 content-free 指标：

- `total_characters`
- `estimated_input_tokens`
- `instruction_characters`
- `evidence_characters`
- `lossless_evidence_characters`
- `recovery_characters`
- `unique_source_count`
- `duplicate_path_count`
- `duplicate_digest_count`
- `nested_duplicate_characters`
- `constraint_count`
- `constraint_repetition_ratio`
- `on_demand_count`
- `prompt_program_digest`

Prompt Lint 规则：

- 同一路径重复为 error；
- exact-on-demand 内容出现在首轮为 error；
- output path 不完整为 error；
- must-inline lossless 缺失为 error；
- duplicate character ratio > 15% 为 warning，>25% 为 error；
- recovery evidence > 首轮字符 10% 为 warning；
- Prompt 超配方硬上限时阻断 v3，并自动回退 v2，不直接丢证据。

指标进入 run manifest、benchmark report 和高级 Agent 观测，不写入作品项目。

### 5.9 Prompt 作者规范与指令优先级

Prompt v3 不只是换一种拼接格式，还必须约束以后如何编写 Prompt，防止系统重新膨胀。

统一优先级：

1. Runtime 安全、工具权限、正式写回和完成协议；
2. 当前经过用户批准的任务目标与显式用户方向；
3. 正式 Canon、人物状态、文风挂载和项目事实；
4. exact Prompt Asset 中的任务判断标准；
5. compact deterministic evidence；
6. 摘要、检索片段和恢复材料。

若用户方向与正式 Canon 冲突，当前任务不能暗中改写 Canon；应生成变更候选或进入明确的资产修改路线。用户仍拥有最终决定权，但其决定必须通过可审计的正式写回表达，不能靠正文 Prompt 中的一句临时覆盖制造项目事实分叉。

作者规范：

- System Prompt 只声明身份、工具边界、完成语义、证据不可信边界和停止规则；
- Task Prompt 只声明本次目标、必须作出的决定、任务特有文学标准和输出语义；
- Evidence 区只承载资料，不夹带新的执行指令；引用内容中的命令一律视为作品资料；
- 每条硬约束分配稳定 `constraint_id`，正文只渲染一次，其他位置引用 ID；
- 禁止“请逐步思考”“展示完整思维链”等要求；改为输出结论、证据 ID、置信度、未决冲突和必要的简短理由；
- 禁止同时放入完整 JSON Schema、字段教程和重复示例；工具型 Worker 由工具 Schema 校验，文件型 Agent 只接收必要字段摘要和一个最小有效示例；
- 正面任务说明优先于大段否定句；确定性可检查事项交给 preflight/lint，不反复警告模型；
- 文学规则必须区分生成约束、审查标准和确定性门禁，不能把三份全文同时塞给生成任务；
- Prompt Asset 变更必须通过 prompt lint、snapshot diff 和至少一个任务级 fixture；
- 单条 Task Prompt 的新增文本若超过 1,500 中文字符，必须在 review 中说明为何不能转为 Evidence、Schema、lint 或 on-demand 资料。

Prompt v3 的可审计输出不是模型的私密推理过程，而是完成工程判断所需的最小决策记录。这样既保留可解释性，也避免用冗长思维链消耗预算或污染后续上下文。

## 6. 自适应推理预算

### 6.1 数据结构

在 `runtime/execution_profiles.py` 中增加不可变 `ReasoningBudget`，作为 `TaskExecutionProfile` 的嵌套值，不建立平行 Profile 系统：

```python
@dataclass(frozen=True)
class ReasoningBudget:
    initial_level: str
    maximum_level: str
    per_request_tokens: int
    total_tokens: int
    max_provider_requests: int
    max_escalations: int
    escalation_triggers: tuple[str, ...]
    over_budget_action: str
```

现有 `reasoning_policy` control 在兼容期投影为 `initial_level`。Profile schema 升级时保留 v1 safe projection，避免旧 run manifest 无法读取。

### 6.2 建议初始矩阵

以下是 canary 目标，不直接全局启用：

| Task kind | 初始 | 最高 | 每请求目标 | 单任务总目标 | Provider 请求 | 升级次数 |
|---|---|---|---:|---:|---:|---:|
| structured | minimal | low | 256 | 768 | 3 | 1 |
| creative | low | medium | 512 | 2,048 | 4 | 1 |
| planning | low | medium | 768 | 4,096 | 4 | 1 |
| style | low | medium | 768 | 3,072 | 4 | 1 |
| archaeology | low | medium | 512 | 2,048 | 4 | 1 |
| prose | minimal | low | 512 | 2,048 | 3 | 1 |
| review | low | medium | 768 | 3,072 | 4 | 1 |

这些数字是成本合同目标，不假设所有 Provider 都会精确遵守。实际支持状态必须来自 Runtime capability receipt。

`reasoning` 预算与可见输出预算必须彻底分离。正文任务的目标汉字数、最大 completion token、流式输出和工具结果不计入 `total_tokens`；不得因为隐藏推理达到上限而截断一篇仍在正常生成且尚未达到正文长度合同的作品。对 prose 的 `minimal -> low` 只是实验起点，若同模型盲评显示人物行为、节奏或语言质量下降，应保持 Prompt v3 而回退 prose 推理限制，不得为了统一矩阵牺牲文本质量。

### 6.3 升级规则

新增纯函数模块 `runtime/reasoning_policy.py`，输入 task kind、attempt、preflight issue categories、evidence conflict 和已用预算，返回：

```text
keep | escalate | retry_same | stop
```

允许升级：

- Canon 与场景事实存在真实冲突；
- 两条高可信证据互相矛盾；
- 复杂规划存在未满足的全局义务；
- review 的人物行为、节奏或承诺兑现判断无法由确定性证据裁定；
- 第一次语义 preflight 失败且失败不属于格式、路径或缺文件。

禁止升级：

- JSON 无效；
- 字段缺失；
- 路径错误；
- 没有调用 complete；
- 重复 validate；
- 字数可由确定性计数发现；
- Style Lint 已给出精确位置；
- Agent 原地空转；
- Provider/网络错误。

机械失败应通过定向 repair、工具提示或编译器修复，不能用更多 reasoning 掩盖。

### 6.4 Pi Worker 执行

Pi fork 修改：

- `contracts.ts`：增加 reasoning budget 投影和使用收据；
- `main.ts`：解析 `--max-thinking-level`、`--reasoning-total`、`--reasoning-per-request`、`--max-provider-requests`；
- `worker.ts`：初始使用 `initial_level`，仅在策略允许时修改 `agent.state.thinkingLevel`；
- 包装 `streamFn`，通过 Pi AI 的 provider-neutral `maxTokens/thinkingBudgets` 传递每请求上限；
- `event-adapter.ts`：累计实际 reasoning token、请求次数和是否由 Provider 报告；
- `shouldStopAfterTurn`：在回合边界执行总预算和请求预算；
- 超预算但已有完整产物时先 validate；没有完整产物则 `blocked=reasoning_budget_exhausted`；
- 不默认在 reasoning delta 中硬中断当前响应，以免丢失同一响应末尾的正式工具调用；硬中断只作为后续独立实验。

Worker 结果增加：

```json
{
  "reasoning_budget": {
    "requested": {},
    "provider_support": "supported|partial|unsupported|unknown",
    "actual_tokens": 0,
    "actual_characters": 0,
    "provider_requests": 0,
    "escalations": [],
    "stop_reason": ""
  }
}
```

不得把 unsupported 记成 actual_tokens=0；未知就是 unknown。

### 6.5 Studio Runtime 投影

修改：

- `runtime/worker_execution_profile.py`
  - 把 ReasoningBudget 作为一个完整合同传入支持的 Runtime；
  - 保留 legacy `reasoning_policy` 给不支持 v2 的 Runtime。
- `runtimes/pi_worker.py`
  - 声明 `reasoning-budget-control`、`provider-request-limit-control`；
  - 构造 CLI 参数；
  - 验证 Worker receipt；
  - receipt 缺失时标记 partial/unknown，不宣称预算已执行。
- OpenCode
  - 第一批只记录 shadow 预算；
  - 在它不能提供实际 reasoning token 或动态等级时保持 unsupported；
  - 不为了表面统一伪造控制能力。

### 6.6 Repair 的推理策略

repair 不重新发送完整初始 Prompt。Repair Context 只包括：

- 原输出路径与 digest；
- preflight issue code、字段和简短说明；
- 与失败直接相关的 evidence IDs；
- 原任务 objective digest；
- 允许修改的 output paths；
- 当前 reasoning budget 与是否允许升级。

第一次格式失败：same/minimal。

第一次语义失败：若匹配允许升级条件，可升一级。

第二次同指纹失败：停止并报告 no progress，不能继续增加 reasoning。

## 7. 配置设计

继续使用现有 worker 配置，不建立新的全局配置文件：

```yaml
worker:
  prompt_program:
    mode: shadow
    version: v3
    enforcement:
      enabled: false
      runtimes: [pi-worker]
      task_kinds: [structured, review]
    fallback: v2
    lint:
      duplicate_warning_ratio: 0.15
      duplicate_error_ratio: 0.25

  execution_profile:
    mode: shadow
    enforcement:
      enabled: false
      runtimes: [pi-worker]
      task_kinds: [structured, review]
    reasoning_budget:
      enabled: true
      max_escalations: 1
```

配置约束：

- Prompt rollout 与 reasoning rollout 分开开关；
- Prompt v3 先启用，推理策略后启用；
- fallback 只能回 v2，不能跳过任务；
- 用户界面暂不暴露详细阈值；实验成熟后只暴露“经济/均衡/深度”预设，高级设置显示实际字段；
- 默认安装版保持 v2/OpenCode，直到通过门禁。

## 8. 模块级修改清单

### 8.1 Studio 新增

| 文件 | 职责 |
|---|---|
| `runtime/prompt_program.py` | Prompt v3 IR 与 digest |
| `runtime/prompt_recipes.py` | ContextTaskKind 表驱动配方 |
| `runtime/evidence_compiler.py` | 证据分级、去重、优先级与 receipt |
| `runtime/prompt_renderer.py` | file-agent/tool-worker 双 renderer |
| `runtime/prompt_metrics.py` | Prompt 指标与 lint |
| `runtime/reasoning_policy.py` | 推理预算、升级与停止纯函数 |

每个文件应保持单一职责和架构预算。不得为每个 route 新建 renderer、policy 或 class。

### 8.2 Studio 修改

| 文件 | 修改 |
|---|---|
| `runtime/task_program.py` | 保持 facade，增加 v2/v3 dispatch |
| `runtime/prompt_context.py` | 输出结构化 ContextRecord；保留 v2 render |
| `runtime/context_materialization.py` | 始终执行 visibility tier，生成 v3 与 shadow 指标 |
| `runtime/execution_context.py` | 记录 evidence identity 与 tier receipt |
| `runtime/context_budget.py` | 新增 v3 目标，不立即缩小旧硬上限 |
| `runtime/execution_profiles.py` | 嵌入 ReasoningBudget |
| `runtime/worker_execution_profile.py` | 投影 reasoning contract |
| `runtime/repair_context.py` | 生成 delta-only repair context |
| `runtimes/pi_worker.py` | 预算 CLI 与 receipt 验证 |
| `observability/runtime_benchmark.py` | Prompt/reasoning 指标报表 |
| `application/config.py` | shadow 默认配置 |

### 8.3 Engine 修改

| 文件 | 修改 |
|---|---|
| `routes/scene/context_contract.py` | 保持现有 exact sidecar/context packet 合同并补回归测试 |
| `literary/scene/context/packet.py` | 软记忆按 source/text digest 去重，限制同源片段，trace 记录丢弃原因 |
| `tasking/context_contract.py` | 验证 tier 互斥与 digest 绑定，不改变任务权威 |
| exact Prompt Assets | 仅修复确证重复；不批量重写文学规则 |

### 8.4 Pi fork 修改

| 文件 | 修改 |
|---|---|
| `packages/arcvellum-worker/src/contracts.ts` | reasoning contract/receipt |
| `main.ts` | 新参数 |
| `worker.ts` | 预算、升级、请求上限 |
| `event-adapter.ts` | 实际用量和支持状态 |
| `tools.ts` | 工具结果继续保持紧凑；不引入 Subagent |

## 9. 测试设计

### 9.1 Prompt 单元测试

- exact-on-demand 在 off/shadow/bounded 均不首轮内联；
- must-inline 在三种模式均保持；
- 相同 path 和 digest 去重；
- exact source 覆盖同源 retrieval；
- lossless candidate 不被摘要；
- compact review evidence 存在时 full sidecar 留在 on-demand；
- output paths 与 semantic contract 不丢失；
- tool-worker renderer 不包含文件型 Agent 冗余纪律；
- v2 fallback 可用；
- Prompt digest 对同输入稳定。

### 9.2 推理策略单元测试

- structured 初始 minimal，不能超过 low；
- review 初始 low，仅语义冲突升 medium；
- JSON/path/missing-output 不触发升级；
- 同一进度指纹第二次失败停止；
- Provider unsupported 不标记 applied；
- 总预算/请求预算在回合边界停止；
- receipt 缺字段 fail closed；
- deterministic task 始终 off/0。

### 9.3 集成测试

- TaskPackage -> v3 prompt -> Pi Worker -> expected output -> preflight；
- repair 只包含 issue delta；
- 取消后进程回收；
- Prompt v3 失败可回退 v2，状态机不跳步；
- writeback preview/digest 保持；
- OpenCode 不支持 reasoning budget 时仍可运行；
- run manifest 同时记录 requested/effective/actual。

### 9.4 文学质量测试

至少包含：

- structured world foundation；
- scene candidate review；
- roleplay/branch creative task；
- longform planning；
- prose generation；
- revision。

质量维度：

- Canon 准确性；
- 人物逻辑；
- 文风遵守；
- 节奏和场景桥；
- 字数与剧情库存；
- review 的挑刺能力；
- revision 是否真实落实；
- 是否出现流程痕迹或模板化语言。

## 10. Benchmark 矩阵

禁止一次同时打开 Prompt v3、推理降级和 Subagent。按以下顺序：

| 组 | Prompt | Reasoning | 目的 |
|---|---|---|---|
| A | v2 | current | 冻结基线 |
| B | v3 | current | 隔离 Prompt 收益 |
| C | v3 | adaptive-shadow | 验证策略预测 |
| D | v3 | adaptive-enforced | 验证真实推理收益 |

每类至少 3 次交错执行，保持：

- 同 Provider、同模型；
- 同 TaskPackage fingerprint；
- 同正式项目 fixture；
- 同 writeback/preflight；
- 样本顺序随机或交错，降低缓存和服务波动影响。

记录：

- Prompt 字符与估算 token；
- actual noncached/cache read input；
- reasoning/output/total token；
- 首 reasoning、首工具、首文件、总耗时；
- Provider 请求数；
- 修复次数；
- preflight 结论；
- 盲评质量；
- Prompt/Execution/Reasoning digest。

## 11. 晋升门禁

### 11.1 Prompt v3 structured/review canary

同时满足才可保留 enforced：

1. structured 首轮字符相对 v2 下降至少 30%；
2. review 首轮字符下降至少 40%；
3. duplicate character ratio 低于 10%；
4. noncached input 中位数下降至少 25%；
5. preflight 首次通过率不下降超过 3 个百分点；
6. repair 次数不增加；
7. exact candidate、Canon、style、rhythm、word-budget 证据覆盖率 100%；
8. 匿名质量不劣于 v2。

### 11.2 自适应推理 canary

同时满足才可扩大：

1. review reasoning token 中位数下降至少 50%；
2. structured reasoning token 下降至少 40%；
3. 总费用下降至少 20%；
4. 总耗时下降至少 15%；
5. preflight 和文学盲评不劣于 Prompt v3/current reasoning；
6. 预算超限、unsupported 和升级事件均可解释；
7. 不出现因低推理导致的浅审、漏 Canon 或虚假 pass。

未达到时：

- Prompt v3 可以独立保留；
- reasoning enforcement 回退 shadow；
- 不因推理策略失败回退已经证明有效的证据去重；
- 不得通过提高默认等级掩盖 Prompt 缺陷。

## 12. 实施批次与 Git 闭环

### P0：冻结基线与 Prompt Audit

修改：benchmark/metrics/tests/docs。

交付：

- 5 类任务 v2 Prompt 报告；
- section size、duplicate、evidence coverage；
- reasoning/provider request 基线；
- 独立提交。

### P1：修正 tier 语义

修改：`context_materialization.py`、context tests。

交付：

- shadow 下 exact-on-demand 不再内联；
- 旧 v2 Prompt 仍可执行；
- candidate-review 定向回归；
- 独立提交，可单独回滚。

### P2：Prompt v3 IR 与 shadow compiler

修改：新增 Prompt Program、recipe、evidence、renderer、metrics；`task_program.py` facade。

交付：

- v2 正式运行；
- v3 只生成 shadow artifact/metrics；
- 不调用第二次模型；
- 架构审计与 digest 稳定测试；
- 独立提交。

### P3：structured canary

修改：structured recipe 和 Pi Worker opt-in。

交付：

- 真实 structured A/B；
- 通过后只对实验 Pi Worker enforced；
- 失败则修编译器，不扩大范围。

### P4：review canary

修改：review recipe、compact evidence 优先、context packet retrieval 去重。

交付：

- 移除首轮 full sidecar/context packet；
- exact-on-demand recovery 验证；
- 3 次交错 A/B 与盲评；
- 独立提交。

### P5：ReasoningBudget shadow

修改：Profile v2、policy、observability、Pi receipt。

交付：

- 只计算推荐等级/预算，不改变运行；
- 比较 recommended 与 actual；
- 确认 Provider 支持；
- 独立提交。

### P6：ReasoningBudget canary

修改：Pi Worker 执行与 Studio projection。

交付：

- structured/review enforced；
- 预算、升级、停止和 repair E2E；
- 同模型基准；
- 未过门禁立即回 shadow。

### P7：扩展决策

只有 P3-P6 通过后才评估 creative/planning/prose。每类单独 A/B，不允许一次全开。

每个 P 批次必须执行：

```text
回读本文对应章节
-> 写批次计划
-> 实现
-> 定向测试
-> architecture audit
-> 必要时全量测试
-> 更新 benchmark 与本文状态
-> git diff --check
-> 独立 Git 提交
```

## 13. 架构质量约束

1. `task_program.py` 继续是唯一公开 Prompt 编译 facade；
2. Prompt v3 不反向依赖 Runtime 实现；renderer 只依赖能力标签；
3. Evidence Compiler 不读取正式项目之外路径；
4. Reasoning Policy 是纯函数，不调用 Provider；
5. Provider 支持检测属于 Runtime，不进入 Engine；
6. Pi Worker 不导入 Python 业务代码；
7. 新模块不得复制 preflight、Schema 或 context tier 逻辑；
8. 不建立 task-kind 子类树，使用 enum + table；
9. 单文件和函数继续受 architecture audit 预算限制；
10. 任何为了测试方便建立的旁路不得进入正式写回；
11. v2/v3 共存期只允许一个 TaskPackage 与一个 ExecutionContext 权威；
12. Prompt Metrics 不保存作品正文或 raw reasoning。

## 14. 风险与防线

### 风险：压缩掉文学细节

防线：lossless fidelity、证据覆盖测试、盲评、candidate/style/character primary evidence 禁止摘要。

### 风险：模型因 Prompt 更短而误解格式

防线：输出工具 Schema、semantic contract、v2 fallback、定向 repair；不靠复制三遍说明增强格式。

### 风险：低推理造成浅审

防线：review 初始 low 而非 off；语义冲突允许一次升 medium；独立审查盲评；不得把 lint pass 当文学 pass。

### 风险：Provider 忽略 reasoning budget

防线：capability receipt、actual usage、请求上限、unsupported 诚实记录、回合边界停止。

### 风险：Prompt v2/v3 双轨长期共存

防线：每个 task kind 通过后迁移；P7 后决定删除 v2 renderer 或保留一个版本周期，禁止无限双轨。

### 风险：只优化 synthetic fixture

防线：synthetic 用于确定性回归，真实项目脱敏样本用于成本与文学质量，二者同时通过。

## 15. 完成定义

本方案完成不是“新增了 Prompt v3 文件”或“把 review 改成 low”。必须同时满足：

1. v3 IR、Evidence Pack、双 renderer 和 lint 可运行；
2. exact-on-demand 在所有 rollout mode 中语义正确；
3. structured/review Prompt 明显缩短且证据不丢；
4. ReasoningBudget requested/effective/actual 可观测；
5. Pi Worker 能限制总推理和请求数，并只按规则升级；
6. repair 不再重放完整 Prompt；
7. 同模型交错 benchmark 达到门禁；
8. 文学盲评不降级；
9. 全量 Python、Pi Worker、架构、凭证与 diff 检查通过；
10. 每批有独立提交和明确回退点；
11. 默认产品链在证据完成前保持不变；
12. 文档准确记录“已证明、未证明、是否晋升”。

本路线的核心不是让模型“少想一点”，而是：

> **先让模型少读重复内容，再让它只在真正需要文学判断的地方思考，并让每一份额外推理都能说明为什么发生、花了多少、是否值得。**
