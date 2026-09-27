# 《月光下的约定》轻内核准备阶段阻断

## 事实与边界

作品于 2026-09-26 新建，持久策略为 `lean-v2`。目前只有 `scenes/scene_0001.yaml` 规划档案，没有 `drafts/scenes/*.md` 正式正文、`workflow/scene_commits/*.json` 轻事务回执或自动创作运行。顶层 Agent 数次调用启动，报“历史正式正文尚未转换为轻事务回执”。实际判定函数把任何非空 `scene_*.yaml` 且尚无 lean 全书规划的作品都视为历史正式正文；报错不是数据库标记，迁移也不能解决。失败的 `project_goal_manage(start)` 还在校验之前写入了多条重复“长期创作目标”方向。

用户原要求是完成规划与资产准备，停在角色推演之前；全自动创作启动即使通过迁移检查，也不能保证这个停止位置。已有手写场景档案在 lean 全书规划物化时又会因缺少自动物化的标题/卷 ID 被视为冲突，因此需要安全保留而不是覆盖。

## Module Change Packet A：识别历史正式产物

```yaml
module_change_packet:
  objective: "仅正式正文或语义增量缺少轻事务回执时阻止 lean-v2；场景规划档案本身不触发迁移门禁"
  primary_module: "project_agent/"
  public_entry: "project_goal_manage、creation_control 的启动适配器"
  variation_point: "已编排场景与已晋升正式正文是不同产物"
  inputs: ["drafts/scenes", "workflow/scene_deltas", "workflow/scene_commits", "scenes"]
  outputs: ["安全内核选择或真实历史正文错误"]
  invariants: ["旧正式正文保留 strict-v1", "未通过校验不追加创作方向", "不写生产作品"]
  allowed_dependencies: ["现有项目产物目录", "Autopilot policy facade"]
  forbidden_dependencies: ["数据库假标记", "空迁移回执", "绕过正式提交"]
  tests: ["仅场景档案允许 lean", "无回执的正文和语义增量仍阻断", "启动失败不污染方向"]
  rollback_unit: "顶层启动适配修复"
  documentation: ["本文"]
```

## Module Change Packet B：已有场景与规划物化

```yaml
module_change_packet:
  objective: "轻规划可采用用户预先填写的同一场景档案，绝不覆盖它；关键身份或容量冲突仍拒绝"
  primary_module: "Engine literary/planning 与 Studio LeanLongformPlanningService"
  public_entry: "materialize_lean_window、ensure_initial"
  variation_point: "空场景模板由规划写入；已填写且无正式产物的场景由规划采用"
  inputs: ["现有 scene YAML", "标准预算", "主创规划"]
  outputs: ["正式全书规划与物化清单", "保留原场景字节"]
  invariants: ["不覆盖已有场景", "scene_id、chapter_id、目标字数和人物范围一致", "已有正式产物不走采用路径"]
  allowed_dependencies: ["Engine materializer", "标准场景事实读取", "LeanLongformPlanningService"]
  forbidden_dependencies: ["自动重写用户档案", "放宽正式正文来源校验"]
  tests: ["已有单场完整 YAML 被采用且原字节不变", "真实身份/容量冲突拒绝", "正式正文冲突拒绝"]
  rollback_unit: "轻规划采用路径修复"
  documentation: ["本文"]
```

## Module Change Packet C：顶层 Agent 的有界规划权限

```yaml
module_change_packet:
  objective: "顶层 Agent 可只执行标准 lean 全书规划并停在推演前，无需启动全自动正文路线"
  primary_module: "project_agent/"
  public_entry: "project_planning_prepare"
  variation_point: "只准备规划与开始正式创作是两种不同用户授权"
  inputs: ["注册 work_id", "现有作品档案与方向"]
  outputs: ["规划、预算、物化状态的回执；无场景推演或正文"]
  invariants: ["复用 LeanLongformPlanningService", "不启动 Autopilot", "真实历史正文仍需先处理", "重入不重复规划"]
  allowed_dependencies: ["RoleConversationGateway", "标准 lean 规划服务", "Project Agent 受控工具桥"]
  forbidden_dependencies: ["新规划器", "直接写项目正文", "隐式进入角色推演"]
  tests: ["只规划不创作", "历史正文拒绝", "工具注册、长调用回执"]
  rollback_unit: "顶层有界规划工具"
  documentation: ["本文", "Project Agent 工具提示"]
```

## 实施与验证

- 启动与诊断现在共用正式产物判定：只有缺少相应轻事务回执的正式场景正文或场景语义增量，才要求迁移。单独的场景规划 YAML 不触发阻断。失败的长期目标启动在校验前不再追加重复方向；此前留下的同文方向在规划提示中去重，不改写用户项目记录。
- 轻规划初轮读取既有场景档案；规划结果须与已填场景的身份、章节、容量和参与人物一致。无正式产物的匹配场景被原样采用，卷号、标题等尚未填写的生成字段不再造成误冲突；已填写且冲突的字段继续拒绝覆盖。
- 顶层 Agent 新增 `project_planning_prepare`，复用标准轻内核规划服务，返回准备回执且不启动 Autopilot。后续档案补全仍走现有 `project_assets_reconcile` 或正式档案事务，不由规划工具暗中创作正文。
- 对实际作品只做了只读核验：`月光下的约定` 的正式产物判定为 `false`，容量为一卷、一章、一场、目标 10000 字；现有场景的章节、容量和三名参与人物与可采用条件相符。未修改该作品，也未代用户启动创作。
- Python 全量回归：1654 项通过、1 项跳过；Pi Worker 检查：113 项通过。另有针对实际场景文件的只读采用条件检查通过。
