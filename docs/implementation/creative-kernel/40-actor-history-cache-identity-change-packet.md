# 角色逐轮上下文缓存身份 Change Packet

```yaml
module_change_packet:
  objective: "将角色调用实际接收的已采用经历绑定到调用记录；同一份委托遇到不同角色历史时清楚呈现上下文冲突，并保留已有缓存以避免自动重复消费。"
  primary_module: "Studio runtimes/scene_creator_v2_materials.py"
  public_entry: "SceneCreatorV2MaterialCoordinator.execute"
  variation_point: "相同材料委托在不同 actor history / initialization answer 下的缓存复用"
  inputs:
    - "角色委托及冻结附件"
    - "主创标记为 use 的前序角色候选"
    - "同角色初始化回答与逐轮历史"
  outputs:
    - "记录中可复核的角色历史与其上下文摘要"
    - "相同委托、相同上下文的稳定缓存命中"
    - "相同委托但历史变化时的明确主创处理提示"
  invariants:
    - "历史冲突只返回确定性问题，不自动重调模型"
    - "没有新上下文摘要的旧交易缓存继续可恢复，不制造重复 Provider 消费"
    - "原始回答与 prompt_sha256 的既有字段语义保持"
    - "候选采用状态仍由主创写入，未知状态不推测"
    - "角色卡、档案挂载、材料计划和正式写回合同不变"
  allowed_dependencies:
    - "Studio scene material transaction records"
    - "SceneCreatorMemoryV1 adopted-candidate decisions"
  forbidden_dependencies:
    - "新模型调用、Provider 客户端或自动 prompt 重写"
    - "修改已有 raw answer、候选或冻结档案"
  tests:
    - "同一委托与同一角色历史命中原缓存"
    - "同一委托但历史摘要变化时提示主创提供新的当轮语境"
    - "上下文冲突路径不再次调用 invoke"
    - "旧记录缺少摘要时仍可恢复"
  rollback_unit: "actor role-context digest and cached-context comparison"
  documentation:
    - "docs/implementation/creative-kernel/40-actor-history-cache-identity-change-packet.md"
```

## 验收边界

候选 ID 和主创 `use` 选择组成历史输入。角色的调用记录保存收到的结构化历史及摘要。重复请求仍先读取已有调用记录；记录带有上下文摘要且与当前角色历史不同，返回可操作提示，让主创在委托或工作语境中表达新的来话。运行时沿用历史记录中的原始回答，不自动产生第二次 Provider 调用。未带摘要的旧记录按原恢复行为读取。

合同测试可验证缓存身份、旧记录恢复和调用次数。它们不代表风格变化的文学效果已通过真人物创作验证。
