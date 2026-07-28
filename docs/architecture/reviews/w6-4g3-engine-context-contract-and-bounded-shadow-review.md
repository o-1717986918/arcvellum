# W6-4G3 Engine 资料合同与 bounded 影子验证评审

> 日期：2026-07-28  
> 范围：高成本场景任务的 Engine-owned 首轮资料合同、任务指纹、Studio 消费端校验、
> 用户方向身份绑定和无模型 bounded 沙箱验证。

## 结论

W6-4G3 已完成，但 W6-4G 尚未完成。本子批让正文生成、精确候选审查和语义修订任务由
Engine 明确声明不可省略的首轮资料，不再由 Studio 根据目录顺序、文件大小或扩展名猜测
文学重要性。

生产配置仍保持 `shadow`。本批没有调用模型、没有修改用户配置、没有写回真实作品，也
没有把单个样本的字符下降冒充真实 Token 或质量目标已经达成。

## Engine 任务合同

`routes/scene/context_contract.py` 为以下正式状态生成
`literary-engineering-workbench/task-context-contract/v1`：

- `candidate-generation-provenance`；
- `candidate-review`；
- `candidate-revision`；
- `static-revision`。

合同声明 `context_must_inline_paths`，并对任务 sidecar、精确候选、精确修订源和审查证据
执行 fail-closed 校验。场景 YAML、当前 Context Packet、分支/Composition 证据、文风、
创作质量和标点标准按任务族进入首轮；完整 Context Trace 和全书字数预算等已授权资料
可以保持 `exact_on_demand`，但不会从 Agent workspace 消失。

任务合同 revision 已更新。资料合同字段进入 executable task fingerprint，因此合同
内容变化后旧 completion receipt 不能证明新合同已经执行。

## 协议与模块边界

本批在架构门禁发现问题后没有扩大债务 baseline，而是完成了职责拆分：

- `routes/scene/context_contract.py`：只拥有场景任务族的文学资料声明；
- `tasking/context_contract.py`：只拥有 Engine 侧跨路线 schema、路径和来源规范化；
- `tasking/package_contract.py`：消费规范化结果并把字段纳入任务指纹；
- `protocols/task_context.py`：Studio 独立验证收到的任务合同；
- `runtime/context_materialization.py`：只消费合同并装配实际执行上下文；
- `runtime/execution_context.py`：把用户方向的 SHA-256 纳入上下文身份，不在安全投影中
  泄露原文或其 digest。

Engine 与 Studio 均拒绝部分合同、重复路径、目录路径、越界路径和错误 schema/status。
Studio 不信任任务包仅因为它来自本地 Engine。

依赖方向保持：

```text
Engine scene route
  -> Engine task context contract
  -> executable task fingerprint
  -> Studio consumer validation
  -> bounded materialization
  -> Prompt / TASK_CONTEXT / Run Manifest / Context Ledger
```

资料合同不能扩大 Sandbox capability、expected outputs 或正式写回权限。

## 真实项目只读验证

对项目 `1+1=2` 的
`scene-development-scene-0004-candidate-review` 创建系统临时克隆和三份独立沙箱，
不运行模型：

| 指标 | off | shadow | bounded |
| --- | ---: | ---: | ---: |
| target inline characters | 80500 | 80500 | 80500 |
| enforced inline characters | 180000 | 180000 | 80500 |
| first-turn visible characters | 131175 | 131175 | 75247 |
| must-inline paths | 12 | 12 | 9 |
| exact-on-demand paths | 0 | 0 | 3 |
| excluded paths | 35 | 35 | 35 |
| mandatory missing | 0 | 0 | 0 |
| tier overlap | 0 | 0 | 0 |

bounded 相对 off 的首轮字符下降为 **42.6%**。全部 9 项 Engine mandatory 资料均进入
首轮，3 项非首轮资料仍存在于 Agent workspace，可被精确按需读取。Prompt、
`TASK_CONTEXT.json`、Run Manifest 和 Context Ledger 使用同一 execution-context
digest。

正式项目取样前后均为 859 个文件，内容快照 digest 均为：

```text
7c6856842e27c3ab2cf1b6660eb4e0e64e3186d54680c483f17d7b61ccd150d9
```

没有发生正式项目写回。

## 预算校准与未达目标

旧 Review 高风险目标为 63250 字符，但该真实任务不可省略的精确证据为 75247 字符。
直接执行旧预算会丢失候选、分支、Composition 或审查 sidecar，因此 bounded 正确地
fail closed。

本批把 Review 高风险目标校准为 80500 字符，优先保持文学正确性。42.6% 的单样本下降
仍不足以证明 W6-4G 的“首轮模型可见字符中位数下降 50%”，也没有真实 provider token
证据。G4 在调用模型前，应先把约 1.9 万字符、与 task package 存在重复语义的 Review
sidecar 投影为带 digest 的紧凑结构化证据；不能继续单纯上调预算。

## 验收

- Python：668 passed，1 skipped；
- Client：44 files、135 tests passed；
- Prompt Registry：54 assets、89 task prompt IDs、0 errors/warnings；
- `client:build`、`vue-tsc`、Vite 和桌面前端同步：passed；
- Architecture Audit：34 个既有 file debt、221 个既有 function debt、0 cycle，
  0 新增 violation；
- `compileall`、`git diff --check`：passed；
- 真实项目 off/shadow/bounded 只读比较：passed。

## 明确延期

以下仍属于 W6-4G 后续子批：

1. 同模型、同任务、等价输入的真实 bounded Token/质量 A/B；
2. Review sidecar 重复语义的 digest-bound 紧凑投影；
3. state/canon/continuity/style/archaeology/longform 的任务族资料合同；
4. 只携带 issue、无效输出和相关证据的增量 repair；
5. bounded 生产激活、分阶段开关和回退验收；
6. `ContextCacheKey`、session reuse、Execution Bundle 与并发。

G4 关闭前不得把用户默认配置改为 bounded，也不得宣称 W6-4G 的 Token、repair 或质量
退出门槛已经满足。
