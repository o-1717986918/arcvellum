# W6-4G4 紧凑审查证据与 bounded A/B 实施计划

> 日期：2026-07-28
> 状态：确定性实施完成；真实模型 A/B 待显式授权
> 范围：`scene-development/candidate-review` 首轮上下文的语义去重、摘要校验、
> 无模型真实项目验证，以及满足前置条件后的同模型 A/B。

## 1. 问题与基线

W6-4G3 已让 Engine 声明高成本场景任务的首轮资料合同，但真实项目 `1+1=2` 的
`scene_0004 candidate-review` 仍有 75247 个首轮可见字符，只比 off 模式的
131175 个字符下降 42.6%，未达到 W6-4G 的 50% 目标。

现有约 1.9 万字符的 `scene_review.agent_tasks.md` 同时承担三类职责：

1. 人类可读的完整恢复说明；
2. 候选特定的确定性审查证据；
3. 已由 Prompt Asset 和输出 schema 表达的通用审查纪律。

它们被整体内联，导致 Prompt Asset、task package 和 sidecar 在语义上重复。不能通过
删除候选、场景、Composition、分支、文风、字数、读者体验或节奏证据解决该问题，也
不能继续单纯上调预算。

## 2. 目标

1. Engine 在执行 `agent-review-scene` 时同时生成完整 sidecar 和紧凑机器证据。
2. 完整 sidecar 保持原有语义、文件路径和 standalone Skill 兼容性。
3. Studio 首轮内联紧凑证据；完整 sidecar 保留在授权 workspace，归入
   `exact_on_demand`。
4. 紧凑证据绑定 exact candidate、完整 sidecar 和输出 schema 的 SHA-256。
5. Studio 在模型调用前独立校验紧凑证据；缺失、过期、路径错配、摘要不一致时
   fail closed。
6. 生产配置继续保持 `shadow`，本批不默认启用 bounded。
7. 先证明无模型资料完整性和正式项目零写回，再考虑真实 provider A/B。

## 3. 非目标

- 不改变 fixed route、任务顺序、Agent 角色或正式 Gate。
- 不改变 review JSON、Markdown 报告和 completion receipt 的所有权。
- 不增加 Agent 文件权限或正式写回权限。
- 不实现 Context Cache、session reuse、Execution Bundle、并发或增量 repair。
- 不把字符下降直接宣称为 Token、成本或质量提升。
- 不删除 standalone Skill 依赖的完整 `.agent_tasks.md`。

## 4. 设计

### 4.1 Engine-owned 紧凑证据

新增 `literary-engineering-workbench/scene-review-context/v1`，由独立高内聚模块生成。
建议路径：

```text
reviews/agent/<scene_id>_scene_review.context.json
```

内容只保存候选特定且可机器验证的信息：

- scene ID；
- exact candidate 相对路径与 SHA-256；
- 完整 sidecar 相对路径与 SHA-256；
- review JSON/Markdown 输出路径；
- `scene_review.v1` schema 身份、规范化内容与 SHA-256；
- Style Mount Snapshot；
- Creative Quality Profile 身份；
- 结构化 Style Lint gate；
- 结构化字数预算 adherence；
- 结构化 Reader Experience adherence；
- 结构化 Narrative Rhythm / Scene Bridge contract；
- 新角色、Canon、anti-evasion 和 clean-pass 的最小枚举政策；
- 产生上述证据的精确来源摘要。

不得复制长篇通用说明、Markdown 输出模板或完整任务运行纪律。

### 4.2 文件所有权

紧凑证据是 CLI/Engine deterministic output：

- 进入 `expected_outputs`；
- 进入 `core_managed_outputs`；
- Agent 只读；
- Worker 在 Agent 运行后恢复并校验；
- Agent 不能创建、修改或删除。

完整 sidecar 仍是 core-managed output，但不再是 candidate-review 的 mandatory inline
证据。它必须继续存在于 workspace，供 Agent 在证据冲突或恢复场景下精确读取。

### 4.3 双重校验

Engine 生成时校验：

- 所有路径均为项目内规范化文件路径；
- candidate 和 sidecar 均存在；
- candidate digest 与 task candidate 一致；
- schema payload 符合预期 schema ID/value；
- evidence payload 可规范 JSON 序列化。

Studio 消费时独立校验：

- 紧凑证据 schema/revision；
- scene ID 与 task；
- candidate path 与 task；
- candidate/sidecar 的当前文件摘要；
- 输出路径与 expected outputs；
- embedded output schema 的规范摘要；
- 必需 evidence section 和状态字段；
- 紧凑证据本身必须为 core-managed output。

Studio 不导入 Engine 实现，不从 Markdown 猜测字段，也不在失败时静默回退。

### 4.4 兼容策略

- 新发出的 candidate-review task 必须携带紧凑证据，缺失时 fail closed。
- 已签发旧 task 在 `off` / `shadow` 下保持可重开；重新签发后获得新 task
  fingerprint 和紧凑证据。
- `bounded` 只接受显式合同，不因旧 task 缺失紧凑证据而把长 sidecar 伪装成成功。
- Prompt Asset 改为首先读取紧凑证据，完整 sidecar 仅作为精确恢复资料。

## 5. 实施顺序

1. Characterization tests：锁定当前 sidecar、task blueprint、context contract 和
   Engine/Studio 边界。
2. 新增 Engine 紧凑证据领域模块和 schema 常量。
3. `write_platform_scene_review_task` 只调用该模块，不继续扩大其既有职责。
4. 更新 candidate-review blueprint 的 expected/core-managed outputs。
5. 更新场景 context contract：紧凑证据 mandatory，完整 sidecar on-demand。
6. 新增 Studio 独立 consumer validator，并在 materialization 前调用。
7. 更新 exact Prompt Asset 和 task contract revision。
8. 补齐 tamper/stale/missing/legacy tests。
9. 全量门禁。
10. 对真实项目临时副本运行 off/shadow/bounded 无模型比较。
11. 只有无模型结果达到目标且零证据缺失时，才评估同模型 A/B。

## 6. 测试矩阵

### 6.1 Engine

- 紧凑证据包含 exact candidate、sidecar、schema digest。
- Style Lint、字数、读者体验、节奏、文风快照与完整 sidecar 同源。
- 相同输入产生稳定规范内容。
- candidate、schema 或 sidecar 缺失时拒绝。
- task fingerprint 随紧凑证据合同变化。

### 6.2 Studio

- 新 task 在 Agent 启动前通过独立验证。
- candidate 被替换后拒绝。
- sidecar 被替换后拒绝。
- embedded schema 被篡改后拒绝。
- scene、candidate 或输出路径错配时拒绝。
- 完整 sidecar 在 bounded 中为 `exact_on_demand`，不是 excluded。
- 紧凑证据始终 `must_inline`。

### 6.3 回归

- standalone `agent-review-scene` 仍输出完整 sidecar。
- review JSON/Markdown、promotion 和 revision gate 行为不变。
- Agent 不能修改 core-managed compact evidence。
- 旧项目在 shadow 模式可重新签发任务。
- Architecture Audit 不增加 file/function/cycle debt。

## 7. 真实项目验收

在系统临时目录创建 `1+1=2` 的只读验证副本，不修改正式项目：

1. 用同一 task identity 创建 off、shadow、bounded 三份独立沙箱。
2. 不调用模型。
3. 比较：
   - first-turn visible characters；
   - must-inline / exact-on-demand / excluded；
   - mandatory missing；
   - tier overlap；
   - Prompt、Task Context、Run Manifest、Context Ledger digest；
   - candidate、sidecar、schema digest；
   - 正式项目文件数和内容快照。
4. 以 off 基线 131175 字符计算下降比例；目标至少 50%。
5. 若未达到，不调用真实模型，继续消除可证明的重复信息。

## 8. 真实模型 A/B 前置条件

只有全部满足后才可运行：

- 无模型首轮字符下降达到至少 50%；
- mandatory evidence 零遗漏；
- 完整 sidecar 可按需读取；
- 四处 execution-context digest 一致；
- 全量测试和 Architecture Audit 通过；
- 正式项目零写回；
- 用户配置仍为 shadow；
- A/B 使用同模型、同任务、等价输入和临时项目副本；
- 记录真实 provider input/output token、时延、repair 次数、schema/gate 结果；
- 文学质量由同一正式审查标准比较，不以“模型成功返回”代替质量通过。

若真实调用需要产生费用或当前 provider 不稳定，本批可以诚实停在“满足 A/B 前置条件”，
不得伪造 Token 结论。

## 9. 架构质量门禁

- 新模块不依赖 Studio。
- Studio validator 不依赖 Engine。
- `platform_tasks.py` 只增加一处组合调用；如超出职责预算则同步抽取，而不是扩大
  baseline。
- Router、Runtime 和 Context Ledger 不承担文学证据生成。
- 不新增第二套 review lifecycle。
- 所有新增正式字段进入 task fingerprint 或由摘要绑定。
- 不接受新的循环依赖、文件债务或函数债务。
- `.tmp/` 不纳入 Git。

## 10. 退出标准

本批只有在以下证据齐全时关闭：

- 紧凑证据契约和独立校验已实现；
- candidate-review 首轮不再整体内联完整 sidecar；
- 真实项目副本无模型下降目标达成；
- 全量 Python、Client、Prompt Registry、build、Architecture Audit、
  `compileall`、`git diff --check` 全部通过；
- 实施评审文档记录达成项、未达项和真实数字；
- 建立单一目的、可回滚 Git 提交并推送；
- 生产 bounded 是否启用由真实 A/B 证据决定，不在本批提前承诺。
