# W6-4G2 唯一执行上下文信封评审

> 日期：2026-07-28
> 范围：fixed route 下的 `ExecutionContextEnvelope`、四级资料契约、Prompt/TASK_CONTEXT/
> Run Manifest/Context Ledger 身份绑定和 SQLite 可观测索引。

## 结论

W6-4G2 已完成，但 W6-4G 尚未完成。本子批把模型实际可见资料收敛为一个版本化、
可校验、可追溯的执行信封；没有改变 Engine 正式任务顺序、文学 Gate、Agent 角色、
沙箱写权限、候选晋升或写回事务。

生产默认仍是 `shadow`。真实审查样本的首轮资料仍使用旧 180000 字符上限，因此本批
证明的是上下文合同一致、分层明确和遗漏可审计，不能声称真实 Token 已下降。

## 已实施合同

`runtime/execution_context.py` 现在拥有不可变
`arcvellum/execution-context-envelope/v1`：

- `must_inline`：首轮必须完整出现，缺失或未实际内联时 fail closed；
- `exact_on_demand`：模型可在 Agent workspace 精确读取，路径不存在时 fail closed；
- `summary_reference`：只暴露摘要和来源 digest，正式来源变化后旧摘要失效；
- `excluded`：不进入 Agent 资料视图，也不在 Prompt 中提示模型读取。

四组路径必须互斥。信封 digest 绑定 task、route、scene、Agent role、Prompt Asset、
预算、实际内容 hash、expected outputs 与 hard constraints；相同任务身份但资料内容
变化会产生新 digest。

## 单一装配边界

`runtime/context_materialization.py` 在 Prepared Context 完成后编译一次信封，并把同一
实例投影到：

1. 模型首轮 `AGENT_TASK.md`；
2. 恢复与审计用 `TASK_CONTEXT.json`；
3. run manifest；
4. Context Ledger；
5. `sandbox.context_ready` 安全事件。

模型首轮不再重复列出已经由 Prepared Context 和四级资料区表达的完整 source/reference
清单。`TASK_CONTEXT.json` 保留兼容字段，但它是恢复/审计投影，不是让模型再次阅读一遍
相同资料的指令。

## Context Ledger 与持久化

- 每个 ledger entry 记录真实 `visibility_tier`；
- ledger 绑定精确 `execution_context_digest`；
- summary reference 只保存 source digest、summary digest 和有界安全预览；
- SQLite schema 15 增加 execution context digest 与 visibility tier 索引；
- 旧 v1 ledger 的可选字段缺失时继续按原 digest 解析，迁移不重写历史正式作品；
- Run Manifest 和 API 安全投影只公开 schema、digest、层级计数和预算，不公开正文、
  Prompt、绝对路径、凭证或隐藏推理。

## 真实项目只读证据

对项目 `1+1=2` 的
`scene-development-scene-0004-candidate-review` 建立系统临时目录中的只读沙箱：

| 指标 | 值 |
| --- | ---: |
| task kind | review |
| Agent role | main-review-agent |
| mode | shadow |
| target inline characters | 63250 |
| enforced inline characters | 180000 |
| first-turn visible characters | 131175 |
| must-inline paths | 12 |
| exact-on-demand paths | 0 |
| summary-reference paths | 0 |
| excluded paths | 35 |
| declared Agent source paths | 10 |
| unclassified Agent source paths | 0 |
| tier overlaps | 0 |
| visible-but-missing paths | 0 |

Prompt、`TASK_CONTEXT.json`、Run Manifest 和 Context Ledger 的 digest 均为：

```text
aea856ac7acffdde0fc16790118ab0f21b3b2891ae24fd6a0f752e1fc01e0b5a
```

取样前后正式项目均为 910 个文件，mtime/size 快照完全一致，未执行 writeback。

该样本同时证明下一子批不能只调低上限：131175 个首轮字符仍明显超过 63250 的影子
目标。正式 bounded A/B 前，Engine task package 必须明确拥有 machine-authored
`context_must_inline_paths`，并为可按需读取和摘要资料建立任务族级合同。

## 架构审计

本批没有新增架构债，也没有修改 debt baseline：

- `context_selection.py` 拥有操作手册排除与 compact reference policy，避免
  `task_program -> execution_context -> context_selection` 循环；
- `execution_context.py` 只拥有信封、层级、摘要引用、digest 和安全投影；
- `task_program.py` 只渲染程序，不重新拥有资料选择；
- `runtime/context_ledger.py` 只把同一装配事实转成 ledger；
- Persistence 只保存索引与脱敏预览，不复制完整上下文；
- Architecture Audit：34 个既有 file debt、221 个既有 function debt、0 cycle，
  0 新增 violation。

依赖方向保持：

```text
Engine TaskPackage
  -> Studio context selection + budget
  -> Prepared Context
  -> ExecutionContextEnvelope
  -> Prompt / TASK_CONTEXT / Run Manifest / Context Ledger
  -> Agent Runtime
  -> existing deterministic preflight + transactional writeback
```

信封只能缩小模型可见资料，不能扩大 Sandbox 能力、expected outputs 或写回权限。

## 验收

- Python：657 passed，1 skipped；
- Client：44 files、135 tests passed；
- Prompt Registry：54 assets、89 task prompt IDs、0 errors/warnings；
- `client:build`、`vue-tsc`、Vite、桌面前端同步：passed；
- Architecture Audit：passed，无新增 violation；
- `compileall` 与 `git diff --check`：passed；
- 真实项目只读信封一致性：passed。

## 明确延期

以下仍属于 W6-4G 后续子批，不能在 G2 中冒充完成：

1. Engine 正式任务族的 machine-authored mandatory/tier contract；
2. bounded context 生产激活与可回退配置；
3. 同模型、同任务、等价输入的真实 Token/质量 A/B；
4. 只携带 issue、无效输出和相关片段的增量 repair；
5. 可追溯语义摘要生产线；
6. `ContextCacheKey`、跨任务 session lease、Execution Bundle 与并发。

W6-4G3 应先建立 Engine task package 的资料层级声明和 shadow completeness 审计，再在
有限任务族上进行 bounded A/B。不得让 Studio 根据目录名或字符大小自行猜测 Canon、
人物、文风、字数和精确候选中哪些资料可以省略。
