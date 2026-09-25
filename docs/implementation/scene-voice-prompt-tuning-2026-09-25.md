# 正式场景语感提示词微调

## Module Change Packet

```yaml
module_change_packet:
  objective: "减轻正式场景的手续复述感，同时保留事实与人物自主表达"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "render_actor_interaction_prompt / render_environment_prompt"
  variation_point: none
  inputs: ["SceneBrief", "已发生的公开言行", "角色人格", "场景节拍"]
  outputs: ["角色本轮候选", "环境候选"]
  invariants: ["不改角色初始化标签", "不改候选 JSON 合同", "不增文学门禁"]
  allowed_dependencies: ["Engine 既有角色与环境提示合同"]
  forbidden_dependencies: ["Studio I/O", "正式正文写入"]
  tests: ["test_scene_interaction", "test_scene_performance_agents"]
  rollback_unit: "角色与环境提示词微调"
  documentation: ["本文"]
```

```yaml
module_change_packet:
  objective: "让主创在成稿和修订时区分纸面事实与人物对白，避免重复解释"
  primary_module: "Studio runtimes/pi_scene_transaction"
  public_entry: "render_scene_create_prompt / render_scene_revision_prompt"
  variation_point: none
  inputs: ["SceneBrief", "一级候选素材", "Candidate", "审读意见"]
  outputs: ["主创创作与修订提示"]
  invariants: ["主创独占正式正文", "事实与 SceneDelta 合同不变", "审查与晋升门禁不变"]
  allowed_dependencies: ["既有 SceneBrief 与候选素材合同"]
  forbidden_dependencies: ["新审查规则", "自动改写正文"]
  tests: ["test_lean_kernel_v2_pi_runtime", "test_scene_interaction"]
  rollback_unit: "主创提示词微调"
  documentation: ["本文"]
```

## 根据正式成稿的判断

《停电后的放映室：待核箱》开头有空间质感，但中段多次完整复述未试听、登记栏、签名与钥匙状态。三名角色的立场不同，措辞却趋向同一种完整的程序说明；环境主要集中在首尾，心理多为概括。一次正式审查的 `pass` 只证明路线合规，不证明这些语感问题已经消失。

本次只调整生成提示：角色回应现实中的对话对象，不向读者汇报；环境可在中段回返；主创把手续事实留在纸面、动作或叙述里，保留真正改变关系的发言，并在修订时处理重复。既有硬事实、候选归属、标点和正式审查路线不动。效果需要下一次真实场景试跑与盲读比较，不能由提示词单测宣称已经改善。
