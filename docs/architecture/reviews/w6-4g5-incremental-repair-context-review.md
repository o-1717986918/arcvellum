# W6-4G5 增量 Repair Context 与越权改动恢复评审

> 日期：2026-07-28
> 结论：确定性实现与全量工程门禁通过；未启用生产 bounded context，未进行真实模型 A/B。

## 1. 问题与根因

历史正式运行
`20260727T160407Z-scene-development-scene-0004-candidate-revision`
在两次模型修复后仍报：

```text
sandbox output still fails deterministic preflight
Agent runtime changed files outside expected_outputs:
characters/candidates/scene-0004-母亲.json
```

本次任务只允许 Agent 写修订候选及报告。Agent 为了“清理”角色候选，把未声明为
`expected_outputs` 的角色文件改成了空对象。旧实现把该确定性越权错误再次发给模型；
模型仍可能继续修改同一文件，最终耗尽 repair 次数。安全 Gate 拒绝写回是正确的，
但修复路径不应依赖模型理解文件权限。

## 2. 实现结果

### 2.1 确定性沙箱清理

`runtime/sandbox_hygiene.py` 在语义预检前比较 Agent workspace、staged baseline 与
未受 Agent 影响的 control workspace：

- 新增且不在 declared outputs 中的文件直接从 Agent workspace 移除；
- 被修改或删除的非输出文件，只有 control copy 的 digest 与 staged baseline 一致时
  才恢复；
- 无法证明可恢复的改动继续 fail closed，不会被静默接受；
- 该过程只修改运行沙箱，不接触正式作品项目，也不消耗模型 repair turn。

`worker_writeback.py` 在清理后仍独立运行 `sandbox_change_issues()`。因此自动恢复不是
绕过 Gate，而是把可确定处理的权限错误移出模型回合；任何残余越权改动仍会阻断。

### 2.2 增量 Repair Context

`runtime/repair_context.py` 为同一 OpenCode session 的每次修复生成
`arcvellum/repair-context/v1`：

- issue 拥有由 code/path/message 形成的稳定 ID；
- 可映射问题只开放对应 invalid outputs；
- 单输出 excerpt 最多 1200 字符，总 excerpt 最多 6000 字符；
- JSON issue 带 selector 时优先只提取对应字段；
- 已通过输出只向模型暴露路径、SHA 与大小，不重复附带正文；
- 已通过输出在修复前形成 run-local snapshot，修复后若被顺手改动则确定性恢复；
- 无法精确映射的旧式抽象 issue 显式降级为
  `all_declared_outputs_fallback`，保持兼容而不伪装成精确目标；
- Repair Context、digest 与统计只保存在 run root，不进入作品项目。

`runtimes/opencode_repair.py` 保持原 session、原 task、原 deterministic preflight 和原
writeback lifecycle。Runtime 只接受 prompt builder/finalizer 回调，不取得
TaskPackage、Sandbox 或文学 Gate 的所有权。

### 2.3 安全可观测性

throughput projection 新增：

- repair prompt/excerpt 字符数；
- targeted/fallback 回合数；
- protected/restored output 数量；
- task-scoped repair context digest。

投影不包含 excerpt、正文、Prompt、绝对路径或被恢复文件名。

## 3. 真实历史运行验证

在历史失败 run 的只读临时副本上复现相同 Agent workspace：

- 修复前唯一问题：
  `characters/candidates/scene-0004-母亲.json` 越权修改；
- 确定性恢复后：0 个 sandbox change issue；
- 原历史运行目录保持 208 个文件的内容快照不变；
- 原始快照 digest：
  `38fc914830716ea64a24d64b8fb00e21943cda458a1226726b345ce9d600e36b`。

对同一历史任务中的 provenance 语义问题构造增量上下文：

- 目标：`drafts/revisions/scene_0004_revision.md`；
- write scope：`targeted`；
- protected outputs：2；
- bounded excerpt：1200 字符；
- repair prompt：2553 字符；
- full task replay：false；
- context digest：
  `db357400647b6807c7a5b23009a3123490fdbbd0e2d5ac0ec7235796dcb6edf1`。

旧 issue-only prompt 只有 519 字符，新 prompt 因携带受限证据而更长。因此本批不能声称
“repair prompt 字符数下降”。可确认的收益是：模型不必盲目重读完整任务、已通过输出
不会被连带改坏、越权改动不再浪费模型回合，并且每次修复有稳定审计身份。

## 4. 验收

- Python：682 tests passed，1 skipped；
- Client：44 files、135 tests passed；
- Prompt Registry：54 assets、89 task prompt IDs，0 errors/warnings；
- Client production build：passed；
- `compileall`：passed；
- Architecture Audit：34 个既有 file debt、221 个既有 function debt、0 cycle，
  无新增 violation；
- 正式项目与历史 run 均未被写回或修改。

## 5. 批判性结论与剩余工作

本实现解决的是 repair 的确定性边界和上下文质量，不等于 W6-4G 已全部退出：

1. 尚未在同一模型、同一任务、等价输入下测量 repair/重试次数、非缓存输入 Token、
   时延和文学质量；
2. 生产 context mode 仍保持 `shadow`，本提交不暗中启用 bounded；
3. `all_declared_outputs_fallback` 是兼容降级，不是理想常态；后续应逐步让 Engine
   preflight issue path 精确指向输出与 selector；
4. ContextCacheKey、跨任务 session lease、Execution Bundle 与并发仍属于后续批次；
5. 任一自动恢复失败时必须继续 fail closed，不能为了吞吐把未知改动带入正式项目。

达到上述真实 A/B 退出门槛前，应把 W6-4G5 标记为“确定性实施完成”，而不是“生产
Token 优化完成”。
