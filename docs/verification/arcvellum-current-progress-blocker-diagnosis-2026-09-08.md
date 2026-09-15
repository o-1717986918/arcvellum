# ArcVellum 当前推进阻断诊断

日期：2026-09-08  
项目：`C:\Users\26532\Documents\ArcVellum\Works\兄弟`  
自动创作运行：`autopilot-38263b7978dc42b4`  
路线：`scene-development`  
当前任务：`scene-development-scene-0001-candidate-revision`

## 结论

当前流程停在第一场正文的第二轮修订。现场先后出现了两个彼此独立的问题：

1. Pi Worker 的局部字数修订协议把合理的小幅删改拒绝掉，随后模型引用了未落盘版本中的片段，触发重复失败和防空转暂停。该代码缺陷已经修复并通过 Worker 全量测试。
2. 修复后的真实重试尚未进入创作，模型供应商直接返回 HTTP 402 `Insufficient Balance`。这是此刻仍然阻止项目继续推进的直接原因。

正式项目文件没有被失败运行污染。沙箱写回机制和防空转保护均按预期工作。

## 现场时间线

### 审查元数据异常

第一轮成功修订之后，AgentReview 的 `style_mount_snapshot` 为空。原因是评审沙箱有意隐藏候选 manifest，并改由 CLI 管理的精简审查证据携带文风快照，但元数据规范化函数仍只读取旧 manifest。

修复内容：

- `scene_review_metadata.py` 优先读取精简审查证据，校验候选路径和 SHA 后提取文风快照。
- `state_scene.py` 将 `style_mount_snapshot_stale` 归类为应重跑审查的基础设施状态，避免误导路线回到正文修订。

验证结果：真实 AgentReview 已写入有效文风快照，并从第 45 项正式任务推进到第 46 项。

### 合理的文学修订

新的语义审查给出 `revise_required`，依据成立：

- 场景约定要求主角压住追问，正文仍出现公开逼问倾向。
- 母亲过早说出死因相关线索，破坏信息延迟。
- 下一场需要更明确地接住怀表、账本等物证。

因此回到 `candidate-revision` 属于质量闭环，不是状态机空转。

### 局部修订协议空转

失败运行：

`20260907T160020001843Z-26e93afb-scene-development-scene-0001-candidate-revision`

模型先把正文从明显超长压缩到 1410 个中文内容字符；合同上限为 1333，还需减少 77。模型随后提交一项减少 13 字的精确片段替换，旧算法固定要求至少减少 20 字，于是拒绝了这项有效进展。

下一轮模型尝试重写全文，但新稿更长且未被落盘。此后模型根据未落盘稿选择 `find` 片段，连续收到 `find string is absent`。防空转守卫检测到无状态进展后主动停止，避免继续耗费额度。

修复内容：

- 大幅超标阶段仍要求整稿修订产生显著进展。
- 接近字数边界后，局部精确修订改用 `max(8, 剩余差额的 15%)`，并受剩余差额封顶。
- 该阈值允许连贯句段的收尾删改，同时仍拒绝逐字蚕食。

验证结果：

- Pi Worker 定向测试：36 项通过。
- Pi Worker 全量测试：93 项通过。
- Pi Worker TypeScript 生产构建通过。

### 当前供应商阻断

修复后重试运行：

`20260907T161334667997Z-e5580c06-scene-development-scene-0001-candidate-revision`

运行在首次模型请求即结束：

```text
provider: deepseek
model: deepseek-v4-pro
HTTP status: 402
message: Insufficient Balance
tool calls: 0
written outputs: 0
```

Autopilot 已暂停并标记 `provider-billing-required`。补充当前 DeepSeek 连接的可用余额，或由用户明确切换到已经完成鉴权且有额度的 Pi Worker 模型后，即可从同一任务恢复；无需重建项目或清理正式文件。

## 性能与成本旁路发现

当前修订任务的准备上下文为 157810 字符，配置目标为 89700 字符，超出 68110 字符。Context Budget 仍处于 shadow，bounded rollout 关闭，prepared-context cache 也关闭。

这不会直接造成当前 402，但会带来三项影响：

- 每次修订首次请求延迟偏高。
- 输入费用和缓存读取量偏大。
- 修订任务更容易让模型在大量证据中丢失“当前落盘稿”这一局部状态。

后续应按既有上下文优化路线启用受控预算和候选稿按需读取，并以真实任务回放比较通过率、费用和延迟。该项不应与当前额度恢复混做一次热修。

## 恢复条件

恢复全自动创作前应满足：

1. 当前 Pi Worker 绑定模型的供应商请求不再返回 402。
2. 使用已构建的最新 Worker 产物。
3. 恢复后观察同一 `candidate-revision` 是否先完成正文局部修订，再依次生成修订报告与 JSON 清单。
4. 只有三个 Agent 产物全部通过 deterministic preflight 后才允许写回项目。
5. 下一轮 AgentReview 必须绑定修订后的精确候选 SHA；通过后才能晋升正文并进入状态演化。

## 相关文档

星仪与桌面渲染性能的独立分析见：

`docs/roadmap/arcvellum-orrery-performance-and-desktop-rendering-optimization-plan.md`
