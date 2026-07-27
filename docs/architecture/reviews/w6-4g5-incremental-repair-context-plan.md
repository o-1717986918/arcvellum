# W6-4G5 增量 Repair Context 实施计划

> 日期：2026-07-28
> 状态：确定性实施完成；真实模型同任务 A/B 待授权
> 范围：OpenCode 正式 Worker 的同 session 确定性预检修复回合。

## 1. 现状证据

当前 `OpenCodeRuntime` 已经在原任务 session 中执行最多两次 repair，不会创建第二套
正式 task、Review 或 writeback lifecycle。每次失败后调用
`PreflightResult.repair_prompt()`，只发送：

- issue code；
- issue path；
- message；
- 自然语言 repair 要求。

该机制比重新启动完整任务更节省，但仍有四个缺口：

1. issue 没有跨回合稳定身份，事件只能按数量统计；
2. Agent 必须再次自行读取整个无效产物，repair prompt 没有受限相关片段；
3. 未命中 issue 的已通过输出仍可被模型改坏；
4. 没有持久化 repair context digest、片段字符量和实际允许修改范围，无法进行可信 A/B。

## 2. 目标

1. 保持同一 OpenCode session 和现有 deterministic preflight loop。
2. 为每个 issue 生成稳定 `issue_id`。
3. repair 只携带 issue、对应无效输出的有界片段和已通过输出的只读身份。
4. 已通过输出在 repair 回合后由 Worker 确定性恢复，不能被顺手重写。
5. 每个 repair 回合保存不含完整 Prompt/正文的机器上下文与 digest。
6. 事件记录 repair prompt 字符量、片段字符量、目标数、保护数和 context digest。
7. 任何映射不确定时优先兼容现有修复能力，不把合法跨文件修复锁死。

## 3. 非目标

- 不改变正式 task、preflight、promotion 或 writeback Gate。
- 不让模型修复 deterministic core-managed outputs。
- 不增加 shell、外部目录、网络或正式项目权限。
- 不使用第二个模型审查 repair。
- 不实现 ContextCacheKey、跨任务 session lease、Execution Bundle 或并发。
- 不把 deterministic canonicalization 伪装成 Agent repair。
- 不在本批启用生产 bounded context。

## 4. 模块设计

### 4.1 `runtime/repair_context.py`

新增高内聚协调器，消费 `TaskPackage`、`SandboxManifest` 和 `PreflightResult`，输出：

```text
arcvellum/repair-context/v1
```

字段至少包括：

- task/run/attempt 身份；
- stable issue IDs；
- issue code/path/message/repair；
- 精确 repair target；
- invalid output path/SHA/size/selector/bounded excerpt；
- protected output path/SHA/size；
- excerpt 与总 prompt 字符预算；
- canonical context digest；
- `targeted` 或 `all_declared_outputs_fallback` 写范围模式。

上下文保存在：

```text
<run_root>/repairs/attempt-<n>/repair-context.json
```

它是运行证据，不进入作品项目，不进入 Agent workspace，也不包含完整任务 Prompt。

### 4.2 目标推导

1. 从 issue path 的 `#selector` 前缀匹配 Agent 可写 expected output。
2. 同一输出的多个 issue 合并为一个 invalid output。
3. 精确匹配成功时，其余 Agent 可写输出成为 protected outputs。
4. 没有任何 issue 能映射到 expected output 时，显式使用
   `all_declared_outputs_fallback`，避免旧 preflight 的抽象路径导致修复死锁。
5. core-managed outputs 永远不成为 Agent repair target。

### 4.3 有界片段

- 单输出片段上限 1200 字符；
- 总片段上限 6000 字符；
- JSON 有 selector 时优先提取对应字段；
- 普通文本保留首尾和截断标记；
- 缺失输出只声明 `missing`，不伪造内容；
- protected output 只发送路径、SHA 和大小，不发送正文。

### 4.4 已通过输出保护

协调器在 repair 开始前把 protected outputs 快照到 run root。repair turn 结束后，
Worker 从快照恢复被改动的 protected outputs，并发出恢复事件。repair target 不恢复，
继续由下一轮 preflight 判断。

恢复只影响沙箱，不修改正式项目。若 repair 超时或取消，也执行相同恢复；后续恢复运行
不能把被模型误改的已通过产物当成新鲜有效输出。

### 4.5 Runtime 接线

`OpenCodeRuntime` 只增加两个可选回调：

- `repair_prompt_builder(preflight, attempt, maximum)`；
- `repair_turn_finalizer()`。

Runtime 不导入 TaskPackage、Sandbox 或文学模块。未提供回调时继续使用
`PreflightResult.repair_prompt()`，保持兼容。

`AgentWorker` 拥有协调器并把回调注入 OpenCode。其他 runtime 行为不变。

## 5. 安全与架构约束

- Preflight 继续是唯一通过判定者。
- Repair Context 不能扩大 expected outputs。
- Studio Runtime 不解释文学结论，只投影确定性 issue 和文件片段。
- Prompt 不包含 source/reference 全文、用户凭证、绝对正式项目路径或隐藏推理。
- OpenCode transport 不取得任务语义所有权。
- 新模块不能形成 Engine -> Studio 反向依赖。
- Architecture Audit 不接受新 file/function/cycle debt。

## 6. 测试矩阵

### 单元

- issue ID 对相同 issue 稳定、不同 issue 不碰撞；
- JSON selector 提取正确；
- 文本和总片段严格受预算限制；
- protected output 不泄露正文；
- context digest 对等价输入稳定，对无效输出变化敏感；
- target 命中与 fallback 模式正确；
- protected output 被改后恢复，target 保留修改；
- 缺失输出和 Unicode 路径可处理。

### 集成

- Worker 首次 preflight 失败后使用新 repair prompt；
- 同一 session ID 保持不变；
- repair 事件包含 context digest 与字符统计；
- finalizer 在 complete/timeout/cancelled 均执行；
- legacy/fallback builder 行为仍可用；
- 下一轮 preflight 看到 target 修订和 restored protected outputs。

### 回归门禁

- 全量 Python 与 Client；
- Prompt Registry；
- Client production build；
- Architecture Audit；
- `compileall` 与 `git diff --check`。

## 7. 退出标准

- OpenCode 正式 Worker 使用持久化、有界、digest-bound Repair Context；
- repair prompt 不重新展开完整 task package；
- 可映射问题只允许目标输出保留修改，其余已通过输出确定性恢复；
- repair 统计足以支持后续同模型 A/B；
- fixed route、正式 Gate 和 writeback 语义不变；
- 全量工程门禁通过；
- 评审文档记录真实数字、兼容降级和未完成项；
- 建立单一目的 Git 提交并推送。
