# W6-4G3 Engine 资料合同与 bounded 影子验证计划

> 日期：2026-07-28

## 目标

让 Engine 正式任务包，而不是 Studio 的目录启发式或运行时文件顺序，声明高成本场景
任务中不可省略的精确资料；随后在临时沙箱中验证 bounded context 可以在不遗漏文学
事实、不改变 fixed route 和不写回项目的前提下运行。

本批不修改用户默认配置，不开放全局 bounded，不调用模型生成新正文，也不宣称真实
Token 目标已经达成。

## 问题证据

W6-4G2 真实项目审查任务的结果是：

- shadow target：63250 字符；
- actual first turn：131175 字符；
- 10 个 Agent source 全部可追溯，但任务包没有声明其中哪些必须首轮出现；
- 直接启用 bounded 时，Studio 只能按文件顺序选择非 mandatory 资料，文学正确性依据
  不足。

因此必须先建立 Engine-owned context contract。

实现中的首次 bounded 取样进一步发现，`scene_0004 candidate-review` 的不可省略资料
实际为约 75231 字符，高于早期 63250 shadow 目标。该目标不是文学事实：本批把高风险
Review 预算校准为 80500 字符，保留全部 mandatory 证据并继续 fail closed。校准后该
样本相对 131175 字符旧首轮下降约 42.7%，仍不足以证明全路线“首轮中位数下降 50%”；
真实模型 A/B 前必须继续把 review sidecar 中与 task package 重复的内容投影为结构化、
带 digest 的紧凑证据，不能把本次预算上调冒充最终 Token 优化。

## 本批范围

首批只覆盖 scene-development 中最昂贵且会直接影响正文质量的三个任务族：

1. `candidate-generation-provenance`：正文候选生成；
2. `candidate-review`：精确候选独立审查；
3. `candidate-revision` / `static-revision`：正文语义修订。

后续 composition、state/canon/continuity、style、archaeology 和 longform planning 必须
分别建立自己的任务族合同，不能把本批规则泛化为“所有 Markdown 都必需”。

## Engine 合同

新增高内聚模块：

```text
literary_engineering_studio_engine/routes/scene/context_contract.py
```

它只根据已经确定的 scene state、正式路径和 Agent source list 生成：

```json
{
  "context_contract_schema": "literary-engineering-workbench/task-context-contract/v1",
  "context_contract_revision": "scene-v1",
  "context_must_inline_paths": [],
  "context_contract_status": "shadow-ready"
}
```

约束：

- mandatory 路径必须来自 `agent_source_paths`、Studio command 产生的
  `core_managed_outputs`，或明确的 domain reference；
- 路径必须是规范化相对路径；
- 不允许目录作为 mandatory；
- 同一 task 的 mandatory 顺序稳定且去重；
- 精确候选、scene contract、当前任务 sidecar 和任务族关键文学合同不得被省略；
- Canon、人物状态、文风、字数、节奏和精确候选是否 mandatory 由任务族显式决定，
  不能依据文件大小决定；
- 其余已授权 Agent source 在 bounded 中按确定性顺序进入
  `must_inline` 或 `exact_on_demand`，不会变成 excluded；
- Engine 不生成摘要，不拥有 Studio budget，也不读取 Runtime 配置。

## 首批资料原则

### 正文生成

首轮必须包含：

- scene YAML；
-当前 context packet；
- composition Markdown/JSON；
- selected branch；
- mounted style profile 与 creative quality profile；
- scene YAML 与 task package 中的 `word_count_target/min/max` 精确字数合同；
- punctuation standard；
- CLI 生成的 prose task sidecar。

context trace、完整 branch/roleplay machine JSON、provenance manifest 和全书
`plot/word_budget/word_budget.json` 可保持 exact-on-demand，但必须仍在 Agent
workspace；这不会豁免场景字数 Gate，因为精确的场景目标已经由 scene YAML 和 task
package 双重承载。

### 精确审查

首轮必须包含：

- exact candidate Markdown；
- scene YAML；
- review task sidecar；
- composition semantic review；
- selected branch；
- current context packet；
- mounted style/quality rules；
- punctuation standard。

candidate manifest、context trace 和完整全书 word-budget JSON 可按需精确读取。Review
仍必须检查 task package 中的字数目标与确定性 lint 证据，不能因 word-budget 文件按需
而豁免字数 Gate。

### 语义修订

首轮必须包含：

- exact revision source；
- exact review JSON；
- scene YAML；
- revision task sidecar；
- current context packet；
- mounted style/quality rules；
- punctuation standard；
-用户已确认的修订方向（存在时）。

完整 review Markdown、trace、branch/composition 支撑和全书预算可按需读取。任何
blocking issue 未映射到正文变化时，正式复审仍阻止晋升。

## 任务合同与指纹

修改 `tasking/package_contract.py`：

- 把 context contract 字段纳入 executable task fingerprint；
- 校验 schema/revision/status；
- 校验 mandatory 是字符串列表、规范化、去重、非目录；
- 校验 mandatory 来源合法；
- Agent-required 的本批 scene state 缺少合同则 fail closed；
- deterministic 和未纳入本批的 task 行为保持不变。

刷新旧 task package 时，合同变化必须产生新 fingerprint；旧完成回执不能证明新合同
已经执行。

## Studio bounded 影子验证

不改变默认 `shadow` 配置。测试和真实项目临时沙箱显式传入 bounded budget：

1. mandatory 总量超过预算时 `ContextBudgetExceeded`；
2. mandatory 全部进入 `must_inline`；
3. 非 mandatory 授权资料仍存在于 Agent workspace，并进入
   `exact_on_demand`；
4. Prompt、TASK_CONTEXT、Run Manifest 和 Context Ledger 保持同一 digest；
5. expected outputs、preflight、writeback policy 和 task completion 不变；
6. 取样前后正式项目文件快照一致。

## 验收

- Engine 合同与 fingerprint 单元测试；
- scene task transport 覆盖 prose/review/revision；
- Studio bounded sandbox 集成测试；
- 真实项目 `1+1=2` 的 `scene_0004 candidate-review` 只读 fixed/shadow/bounded 字符
  对比；
- bounded 首轮不超过证据校准后的任务目标，mandatory 0 missing，tier 0 overlap；
- 不运行模型、不写回正式项目；
- 全量 Python、Client、Prompt Registry、Architecture Audit、compileall、生产前端
  构建和 `git diff --check` 通过。

## 明确延期

- 默认或用户可见 bounded 开关；
- 同模型真实生成与质量 A/B；
- state/canon/continuity/style/archaeology/longform 的资料合同；
- 摘要生产线；
- 增量 repair；
- ContextCacheKey、session reuse、Bundle 与并发。

完成本批后，W6-4G4 才能在有限任务族上进行真实模型 bounded A/B，并根据首次
preflight、AgentReview、Canon/状态/文风/字数/节奏 Gate 结果决定是否逐步开放生产
配置。
