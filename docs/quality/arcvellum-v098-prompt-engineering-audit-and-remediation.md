# ArcVellum v0.98 提示词工程审计与整改基线

## 1. 审计结论

当前主要问题不是某一份正文 Prompt 写得太长，而是同一任务被多个历史信息层重复包装：

1. Engine Prompt Asset 已经描述任务目标、文学判断和输出要求；
2. TaskPackage 又携带 hard constraints、validation gates、sidecar 和宿主运行说明；
3. Prepared Context 把候选、Canon、规划表、流程文档和 context packet 整份拼接；
4. Worker user prompt 再重复沙箱、工具、停止与完成协议；
5. repair turn 若缺少增量合同，还会重放大部分初始 Prompt。

因此，单独删减正文 Prompt Asset 既不能根治 token 浪费，也可能损伤文学约束。整改必须覆盖 Prompt Asset、TaskPackage、证据编译、Worker Profile、项目会话摘要、repair turn 和终止语义。

## 2. 实际证据

- v7 正文任务实际合并 Prompt：189,908 字符、5,043 行；包含 36 次平台 Agent 话术、32 个 `[AGENT_TASK]`，并重复注入 Skill/CLI 说明、sidecar、角色资料和 context packet；
- 正文精确 Prompt Asset 本身约 3,043 字节，说明膨胀主要发生在合并层；
- v8 世界观审查旧正式 Prompt 约 27,869 字符；第一版 v3 约 20,565 字符；
- 最终整改后，同一真实正文任务快照编译为 26,892 字符、592 行、约 12,939 tokens；相对旧版缩减约 85.8%，并恢复了场景相关 Canon、主要角色完整档案和上一场交接；
- 当前 55 份 Prompt Asset 的正文合计约 21,309 字符，单份最大约 1,553 字符；
- 55 份资产中，20 份包含 sidecar 话术，8 份包含 CLI 话术，5 份包含平台 Agent 话术。它们服务外置 Skill 宿主，不应直接进入 Pi Worker Prompt；
- 真实审查任务曾在两个 required outputs 已写入且本地校验通过后被 no-progress guard 判失败，证明 Prompt、工具合同与停止判定必须联合治理。

## 3. 指令所有权

### 3.1 Worker Bootstrap Profile

只包含长期稳定的 Worker 身份、工具白名单、沙箱边界、输出所有权和停止协议。它必须：

- 按角色版本化并生成 digest；
- 只在 Worker 初始化时绑定；
- 不包含项目路径、当前任务、Canon、文风、候选、Skill 文档或 CLI 教程；
- 主创与审查使用不同 Profile，不共享角色历史。

代码所有者：`workers/pi-worker/src/worker-profile.ts`。

### 3.2 Durable Project Session Context

保存同项目、同角色可复用但会失效的稳定信息：作品身份、确认 Canon 摘要、角色状态摘要、挂载文风身份、Creative Plan 摘要。它必须：

- 每条信息绑定来源 digest、事实版本和失效条件；
- Canon、人物状态、文风、计划、模型或角色变化后重新生成；
- 有最大任务数、时间、token 和失败次数；
- 只作为缓存，不是正式事实源；
- 不让 reviewer 继承 writer 的解释或推理历史。

当前状态：合同已有 `session_lease.py` 基础，Provider 级跨任务复用尚未启用。必须先完成提示词瘦身和连续 E2E，再做受控复用。

### 3.3 Ephemeral Task Contract

每个任务必须重新签发：目标、当前选择、Allowed Outputs、schema、候选 digest、当前状态、必要证据和 Gate。它不能依赖旧会话记忆，也不能被持久 Profile 覆盖。

代码所有者：`prompt_program.py`、`prompt_compiler.py`、`prompt_renderer.py`、`evidence_compiler.py`。

## 4. 证据保真规则

- 正文候选、审查候选和当前修订源必须 lossless；
- 当前场景、参与角色状态、相关 Canon、文风生成标准、节奏/桥接和字数合同必须首轮可用；
- sidecar、Skill/AGENTS/agentread、CLI 协议和实现文档对 Pi 默认为 recovery/on-demand；
- 资产审查不得默认内联整份字数预算、伏笔表、冲突矩阵和无关角色模板；
- 空 Canon 结构和相同结构化投影不占用首轮 Prompt；
- context packet 必须按任务投影并去掉已由 scene/style/outline/budget 精确文件提供的重复章节；
- 不用截断候选、正文或高风险审查证据换取短 Prompt。

## 5. 全量整改清单

### 已完成

- Pi 全任务默认使用 Prompt Program v3，而不是只对正文启用；
- Pi renderer 删除重复 Runtime Contract；
- 宿主 Skill、平台 Agent、CLI 生命周期话术按 execution audience 过滤；
- sidecar 和实现文档对 Pi 降为 recovery/on-demand；
- 用户方向改为读取结构化消息，只携带最近 5 条、最多 12,000 字符；
- 世界观资产审查保留精确候选、项目身份与必要大纲，降级无关规划表；
- 空结构化证据和相同投影去重；
- 旧 transport task kind 在无 context budget 时也归一为标准 recipe kind；
- Pi Worker Profile 已独立版本化并输出绑定 digest；
- required outputs 已通过本地验证时先成功交回 Studio，不再被 no-progress guard 覆盖。
- 正文 context packet 已投影为 Canon/时间线、Broker 选中的人物档案和上一场交接，不再重放项目配置、场景、全书大纲、风格模板与软检索副本；
- composition 投影不再把自动 `prose_seed`、过期 `revision_targets/guardrails` 或 `target=0/needs_expansion` 预算快照传给主创；
- 世界资产创建、审查和确定性晋升均禁止把 candidate/schema/approval/promotion 生命周期元数据写成虚构 Canon；旧项目中已误写的此类规则不会进入正文 Prompt；
- 55 份 Prompt Asset 已全部通过 Pi audience lint，编译后 `CLI`、`sidecar`、Skill 文件、平台 Agent 和 task lifecycle 残留均为 0；
- 17 个高风险 Prompt Asset 的 exact resolution 和文学语义锚点审计全部通过；
- repair turn 已是增量修复：只携带失败目标、失败产物片段和仍有效合同，不重放完整初始 Prompt；
- 已提供确定性真实任务导出器 `scripts/export_pi_prompt_audit.py`，分别保存 System、User 和合并有效消息及脱敏指标。

### 待完成

- 清理近义但不完全同文的重复 constraints，保留一个权威表述；
- 为 planning、creative、style、review、prose 各保存至少一个真实 Prompt fixture；
- 建立 project-session digest 和 invalidation receipt；
- 连续 E2E 从干净作品重跑到首场晋升、状态/连续性写回与下一场。

`project-session` 的 Provider 级复用继续延后到连续 E2E 通过之后。当前三层信息所有权已经明确，但不能用会话缓存掩盖任务证据选择问题。

## 6. 实际导出

- System message：`build/prompt-audit/pi-worker-main-creative-system-prompt.md`；
- User message：`build/prompt-audit/scene-prose-fixed-full-prompt.md`；
- 实际有效消息合并审计：`build/prompt-audit/scene-prose-fixed-effective-messages.md`；
- 指标：`build/prompt-audit/scene-prose-fixed-prompt-audit.json`。

这些文件由真实 TaskPackage 经过当前 `stage_task -> Prompt Program v3 -> tool-worker renderer` 生成，不是人工整理的示例 Prompt。

## 7. 量化门禁

- Pi 正式 Prompt 中 `SKILL.md`、`AGENTS.md`、`agentread.yaml`、平台 Agent、`[AGENT_TASK]`、`task-submit`、`task-complete` 命中数为 0；
- 同一路径和同一内容 digest 不得重复内联；
- 规范化重复率 warning 小于 10%，error 小于 15%；
- structured/review 建议不超过 18k/30k 字符，planning/creative/style 不超过 32k/42k，prose 默认不超过 65k；
- 超限必须显示证据保真原因，禁止静默回退到 180k v2；
- 每个 Prompt 必须同时通过“必要信息不丢失”和“无关资料未内联”测试；
- 性能验收同时比较首响应、输入 token、Provider 请求、工具调用、repair 次数、文学盲评和正式 Gate，通过率下降即判失败。

## 8. 禁止的伪优化

- 不把当前任务合同永久塞进 system prompt；
- 不把完整项目历史作为持久会话上下文；
- 不让审查 Agent 继承主创 Agent 会话；
- 不删除外置 Codex/Claude Skill 兼容文件来让 Pi 看起来更干净；
- 不因 Prompt 超限自动退回旧版巨型提示词；
- 不用降低审查、Canon、字数、文风或连续性 Gate 换取吞吐；
- 不把“token 更少”单独视为成功，闭环率与文学质量必须同时不下降。
