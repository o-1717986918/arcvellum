# 主创角色委托聚焦当轮回应 Change Packet

```yaml
module_change_packet:
  objective: "让主创编写角色委托时，把来话、目标人物和这一轮的关系选择写清，使角色候选长在目标人物自己的声线、动作与处境中。"
  primary_module: "Engine prompting"
  public_entry: "prompt_layer_spec('scene.v2.creator.delegation')"
  variation_point: "五类委托中角色扮演邀请的刺激点与当轮回应焦点"
  inputs:
    - "第 26 号验收报告记录的角色候选夹带对方回应、角色卡例句复用现象"
    - "本场目标人物、实际来话或动作刺激、关系压力与选择"
    - "本场冻结的角色卡和作品意图"
  outputs:
    - "目标人物、具体来话与关系压力清楚的自然语言邀请"
    - "以目标人物当轮台词、第一人称动作和内心冲动为中心的候选焦点"
    - "声音范例随处境改变节奏、措辞、停顿和动作重心的创作引导"
  invariants:
    - "角色 system prompt 继续严格使用十六区角色卡结构"
    - "不增加角色卡前言、角色权限说明或共用边界提示"
    - "角色候选与正式正文、Canon、角色档案继续分开"
    - "旧交易继续使用冻结提示快照；v2 仍按现有启用配置运行"
  allowed_dependencies:
    - "Engine prompt layer registry"
    - "scene.v2.creator.delegation prompt contract tests"
  forbidden_dependencies:
    - "Studio runtime、材料 schema、Gateway 或正式写回语义"
    - "固定角色人设之外新增共享角色 system preamble"
    - "否定权限套话或逐字复述禁令"
  tests:
    - "提示版本递增并保留正向语气"
    - "模板可见目标人物、具体来话、本轮回应和声线变化方向"
    - "角色卡仍为十六区且不引入文风槽"
  rollback_unit: "scene.v2.creator.delegation prompt v6"
  documentation:
    - "docs/implementation/creative-kernel/38-actor-invitation-focus-change-packet.md"
```

## 实施与验证

- `scene.v2.creator.delegation` 升至 v6，提示主创把角色邀请写成从具体来话进入的当轮回应，让不同角色的声音各自从其轮次生长，并依据处境变化熟悉声线。
- 角色 system prompt 的十六区卡片模板保持原样，没有增加静态前言或共享权限说明。
- 提示合同测试与完整仓库 unittest 在本批通过；提示注册表 59 项资产、73 项任务绑定通过。
- 本包验证主创如何编写邀请；调用记录如何生成后续角色历史，另见第 39 号 Studio runtime 变更包。提示测试不能代替角色文学效果复测。
