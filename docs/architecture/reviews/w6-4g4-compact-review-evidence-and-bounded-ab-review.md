# W6-4G4 紧凑审查证据与 bounded A/B 前置验收

> 日期：2026-07-28
> 范围：`scene-development/candidate-review` 紧凑审查证据、显式资料层级合同、
> 真实项目无模型比较和真实模型 A/B 前置条件。
> 结论：确定性实施完成；生产继续使用 `shadow`，真实模型 A/B 尚未执行。

## 1. 结论

本子批把候选审查首轮上下文从“完整恢复 sidecar 整体内联”改为：

```text
精确候选 + 场景/分支/Composition/文风/节奏证据
  + digest-bound 紧凑审查证据（首轮）
  + 完整审查 sidecar（授权 workspace 内精确按需读取）
```

真实项目 `1+1=2` 的同一候选审查任务在 bounded 模式下，首轮可见字符从当前 off
基线的 139894 降至 64085，下降 **54.19%**。以 W6-4G3 记录的历史基线 131175
计算，下降 **51.15%**。全部 mandatory 资料保留，完整 sidecar 没有被删除或排除，
四处 execution-context digest 一致，正式项目没有写回。

该结果证明真实模型 A/B 的确定性前置条件已经满足，但不证明真实 Token、时延、
repair 次数或文学质量已改善。本批没有调用付费模型，也没有把生产模式从 `shadow`
切换为 `bounded`。

## 2. 实现

### 2.1 Engine-owned 紧凑证据

新增 `literary-engineering-workbench/scene-review-context/v1`：

```text
reviews/agent/<scene_id>_scene_review.context.json
```

证据由 Engine 文学审查领域生成，包含：

- exact candidate、完整 sidecar、review JSON 和 review report 的规范路径；
- candidate 与 sidecar 的 SHA-256；
- `scene_review.v1` schema 的规范内容、资源摘要和合同摘要；
- Style Mount Snapshot、Creative Quality Profile、Style Lint；
- 字数预算、读者体验、叙事节奏与场景衔接证据；
- Canon、新角色、反规避和 clean-pass 的最小机器政策；
- 所有确定性来源的路径与摘要。

它不复制完整 Markdown 操作说明、输出模板或通用 Agent 纪律。完整 sidecar 仍由 CLI
生成并保持 standalone Skill 兼容。

### 2.2 显式资料层级

正式任务合同新增可选字段：

```text
context_exact_on_demand_paths
```

该字段与 `context_must_inline_paths` 一并进入 executable task fingerprint。Engine 和
Studio 分别校验：

- 路径已被任务授权；
- 两个层级互斥；
- 路径规范化且位于项目内；
- candidate-review 的紧凑证据必须首轮内联；
- 完整 `.agent_tasks.md` sidecar 必须精确按需可读。

bounded 模式即使尚有预算，也不会重新内联显式 exact-on-demand 文件。`off` 和
`shadow` 继续保持旧可见行为，以便进行等价比较和安全回退。

### 2.3 双重校验和所有权

- `literary/review/context_evidence.py` 只生成 Engine-owned 紧凑证据；
- `protocols/review_context.py` 在 Studio 侧独立校验，不导入 Engine 实现；
- 紧凑证据进入 `expected_outputs` 与 `core_managed_outputs`，Agent 只读；
- Worker 在 Agent 执行后恢复并重新验证 core-managed 内容；
- 候选、sidecar、schema、scene 或输出路径发生变化时 fail closed；
- Runtime 只消费已验证合同，不从 Markdown 猜测文学资料。

## 3. 真实项目无模型验收

正式项目：

```text
C:\Users\26532\Documents\ArcVellum\Works\1+1=2
```

在系统临时目录创建副本并重新签发
`scene-development-scene-0004-candidate-review`。三种模式使用同一任务身份，不调用
模型。

| 指标 | off | shadow | bounded |
| --- | ---: | ---: | ---: |
| target inline characters | 65550 | 65550 | 65550 |
| enforced inline characters | 180000 | 180000 | 65550 |
| first-turn visible characters | 139894 | 139894 | 64085 |
| exact-on-demand characters | 0 | 0 | 74797 |
| mandatory characters | 64069 | 64069 | 64069 |
| must-inline paths | 13 | 13 | 9 |
| exact-on-demand paths | 0 | 0 | 4 |
| excluded paths | 34 | 34 | 34 |
| mandatory missing | 0 | 0 | 0 |
| tier overlap | 0 | 0 | 0 |

bounded 中：

- 紧凑证据层级为 `must_inline`；
- 完整 sidecar 层级为 `exact_on_demand`；
- 紧凑证据为 10796 bytes，完整 sidecar 为 31737 bytes；
- candidate SHA、sidecar SHA、schema contract SHA 和 schema resource SHA 均匹配；
- Prompt、`TASK_CONTEXT.json`、Run Manifest、Context Ledger digest 一致。

正式项目验证前后均为 859 个文件、9388972 bytes，内容快照均为：

```text
a929a57b2a9901bb6e4a1bd7298c95f790d619ff7bcc85500f11318dc12be9f4
```

没有发生正式项目写回。

## 4. 预算校准

Review 基础预算由 70000 调整为 57000，高风险倍率后的目标为 65550。真实 mandatory
证据为 64069 字符，因此仍保留 1481 字符余量。该预算来自正式任务测量，不通过截断
文件、删除文学证据或降低 Gate 获得。

若未来 mandatory 合同增长并超过预算，bounded 必须继续 fail closed，而不是静默丢弃
候选、场景、分支、Composition、文风、节奏或审查证据。

## 5. 工程验收

- Python：674 tests passed，1 skipped；
- Client：44 files、135 tests passed；
- Prompt Registry：54 assets、89 task prompt IDs、0 errors/warnings；
- Client production build、Vue typecheck、Vite、桌面前端同步和 v0.9 build verifier：
  passed；
- Architecture Audit：34 个既有 file debt、221 个既有 function debt、0 cycle，
  无新增 violation；
- `python -m compileall -q src tests`：passed；
- 正式项目 off/shadow/bounded 无模型比较：passed。

## 6. 尚未完成与生产边界

以下内容没有在本子批中完成，也不得由字符数结果代替：

1. 同模型、同任务、等价输入的真实 provider A/B；
2. 真实 input/output Token、时延和 repair 次数比较；
3. 同一正式文学审查标准下的质量比较；
4. 全任务族首轮可见字符中位数和 P95；
5. bounded 生产激活、分阶段开关和回退演练；
6. state/canon/continuity/style/archaeology/longform 的资料合同；
7. 增量 repair、Context Cache、session reuse、Execution Bundle 与并发。

因此，W6-4G4 的确定性前置工作可以关闭，但 W6-4G 的真实模型与生产退出门槛仍保持
未完成。后续真实 A/B 必须显式使用用户选定 provider，记录费用相关用量，并继续在临时
项目副本中运行。
