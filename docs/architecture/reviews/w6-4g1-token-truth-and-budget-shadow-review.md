# W6-4G1 Token 真相与预算影子模式评审

> 日期：2026-07-28  
> 范围：fixed route 下的 usage truth、task context budget shadow、可观测投影和前端分栏。

## 结论

W6-4G1 已完成，但 W6-4G 尚未完成。本子批建立可信测量和安全的预算策略，不改变任何
正式文学任务、Gate、候选/晋升顺序或写回语义。

生产默认模式为 `shadow`。它计算任务目标并记录超额，但仍使用旧的 180000 字符上限。
因此本批可以证明哪里浪费，不能声称已经降低真实 Token 消耗。

## 已实施边界

### Task Context Budget

`runtime/context_budget.py` 根据任务族、Agent role 和风险等级生成不可变预算：

- 结构化任务从约 24000 字符开始；
- RP/branch/composition 等创意任务约 55000 字符；
- Review 任务高风险目标为 63250 字符；
- 正文任务高风险目标为 89700 字符；
- 自定义正整数配置可以覆盖 task-kind 基准，但不能突破旧 180000 字符安全上限。

无效模式回退 `shadow`。`off` 与 `shadow` 均不缩减旧行为；`bounded` 会使用目标上限，
但任务没有显式 `context_must_inline_paths` 时必须 fail closed。四级资料契约完成前，
不得用 protected sidecar、输出清单或目录启发式猜测文学 mandatory context。

### Prompt Context

`prompt_context.py` 已拆分为加载、mandatory 校验、完整文件选择和 report 四个职责：

- 文件只能完整内联或完整进入 on-demand；
- 非 UTF-8、二进制或缺失文件不进入 Prompt；
- bounded 模式 mandatory 缺失或总体超额时直接失败；
- report 只有计数、枚举和 digest，不包含文本、绝对路径或密钥。

### Usage Truth

吞吐投影现分别记录：

- provider-reported non-cache input；
- cache read；
- cache write；
- output；
- reasoning；
- provider cost；
- model turns、repair、retry；
- 首轮可见、按需、排除、授权和超额字符。

归因维度包含 task、scene、Agent role、Runtime role、provider/model 和 context digest。
累计 message usage 继续按稳定 `usage_id` 计算增量，不重复累加快照。

前端 Agent Runtime 仪表分别显示非缓存输入、缓存读取、模型输出和首轮上下文中位数，
不把 total token 解释为等价账单。

## 真实任务证据

对项目 `1+1=2` 的
`scene-development-scene-0004-candidate-review` 建立临时只读沙箱：

| 指标 | 值 |
| --- | ---: |
| task kind | review |
| Agent role | main-review-agent |
| risk | high |
| mode | shadow |
| target inline characters | 63250 |
| enforced inline characters | 180000 |
| first-turn visible characters | 131127 |
| exact on-demand characters | 0 |
| overage characters | 67877 |

该样本表明下一子批有明确压缩空间，也证明 G1 尚未改变实际输入。只有
ExecutionContextEnvelope 和四级资料分层完成后，才能用等价任务做 bounded A/B。

## 架构审计

本批没有接受新的架构债：

- Prompt 选择拆为短函数，未扩大既有函数复杂度基线；
- throughput 事件状态、数值事实和公开投影分成三个高内聚模块；
- 前端 throughput DTO 从 `types/api.ts` 移到独立类型文件；
- Sandbox 的 `WritebackPreview` 移入独立不可变合同模块；
- Architecture Audit 为 pass，未修改债务 baseline。

依赖方向保持：

```text
Engine TaskPackage
  -> Studio context budget / selection / materialization
  -> Agent sandbox + Context Ledger
  -> runtime events
  -> safe throughput projection
  -> API / Client presentation
```

Observability 不反向影响任务选择、Gate 或写回。

## 验收

- Python：652 passed，1 skipped；
- Client：135 passed；
- Prompt Registry：54 assets、89 task prompt IDs；
- `client:build`、`vue-tsc`、Vite、桌面前端同步：passed；
- Architecture Audit：passed；
- `compileall` 与 `git diff --check`：passed。

## 明确延期

以下不属于 G1，不能在本评审中冒充完成：

1. `ExecutionContextEnvelope`；
2. `must_inline / exact_on_demand / summary_reference / excluded` 四级资料契约；
3. bounded 生产激活；
4. 去除 Task JSON、sidecar、TASK_CONTEXT 和 Worker Program 的重复语义；
5. 只携带 issue 与相关片段的增量 repair；
6. 同模型同任务样本的真实 Token A/B；
7. ContextCacheKey、跨任务 session lease、Execution Bundle 与并发。

下一子批应先完成 ExecutionContextEnvelope 与四级资料选择，再开启 bounded A/B；不能
跳过这一层直接调低 180000 字符上限。
