# 角色候选逐轮历史投影 Change Packet

```yaml
module_change_packet:
  objective: "后续角色轮次仅接收主创明确采用的本角色候选，避免原始回答中的其他人物台词或未选候选继续充当角色经历。"
  primary_module: "Studio runtimes/scene_creator_v2_materials.py"
  public_entry: "SceneCreatorV2MaterialCoordinator.execute"
  variation_point: "原始角色回答、整理候选、主创取舍和逐轮历史之间的投影"
  inputs:
    - "第 26 号验收报告记录的角色候选夹带其他人物台词"
    - "material-call/v2 中并存的原始回答、目标角色字段和候选 ID"
    - "SceneCreatorMemoryV1 中主创明确写下的 use/adapt/discard 取舍"
  outputs:
    - "角色候选正文由台词与第一人称动作构成"
    - "下一轮同角色历史只包含主创选为 use 的候选字段"
    - "其他原始话语仍可从调用审计记录复核"
  invariants:
    - "原始回答、初始化回答、提示摘要、附件摘要继续完整留档"
    - "adapt 与 discard 候选不作为角色已发生的经历"
    - "主创仍以 working_context 或选入素材交代改写后的经历"
    - "角色卡、挂载、材料事实状态、候选 ID 和正文写回合同保持"
    - "不增加 Provider 请求，不更改既有 scene.v2/material-call schema"
  allowed_dependencies:
    - "SceneCreatorMemoryV1 的主创材料取舍记录"
    - "Engine public scene material contracts"
    - "现有角色卡与场景 runtime 回归测试"
  forbidden_dependencies:
    - "直接把角色候选写入 Canon、正式正文或人物档案"
    - "将主创选用状态推断为作者未标记的 use"
    - "丢弃调用原文或修改角色卡十六区结构"
  tests:
    - "原文含两个人声音时审计记录保留原文、候选正文仅保留目标角色字段"
    - "未被选用的候选不进入角色历史"
    - "主创标为 use 的候选能从 transaction memory 进入下一轮角色历史"
    - "调用恢复、角色卡冻结、材料计划门禁和 scene v2 回归通过"
  rollback_unit: "adopted actor history projection"
  documentation:
    - "docs/implementation/creative-kernel/39-actor-turn-history-projection-change-packet.md"
```

## 证据范围

第 26 号验收报告记录的角色候选曾包含另一人物的台词。当前 coordinator 把调用原文存入审计文件，却又把该原文整段传入同角色下一轮；另一处把未选候选视为逐轮经历的风险来自同一投影点。

本包将后续历史改为从主创标记为 `use` 的候选字段构成。`adapt` 的最终版本由主创在下一轮工作语境或附件中提供。修复可以验证信息路径与候选选择，但真人物声线是否变得更鲜明，仍须在连接恢复后以新交易复测。

## 实施与离线验证

- coordinator 从 creator memory 接收已采用候选 ID；角色历史保留台词、第一人称动作及私念，未采用候选不进入历史。
- 原始回答仍保留于 material-call/v2；候选正文从规范化角色字段投影，原有角色卡与 SceneDelta 流程未改。
- 定向角色、场景和提示词测试：22 项通过；完整 runtime suite：76 项通过、13 个子测试通过。
- 仓库标准 unittest：1807 项通过，1 项因当前 Windows 无法创建符号链接而跳过。架构审计、模块图检查、compileall 及提示注册表验证通过。
- 未发起真实模型调用。以上验证覆盖代码投影与合同，不构成声线或文学质量复测。
