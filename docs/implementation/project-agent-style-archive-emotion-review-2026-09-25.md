# 顶层 Agent 档案与文风权限、情绪表达、短句审查

## Module Change Packet A：顶层 Agent 资产权限

```yaml
module_change_packet:
  objective: 顶层 Agent 能读取并以作者身份创建、修改、归档或恢复前端档案编辑器支持的资产
  primary_module: project_agent/
  public_entry: ProjectAgentDependencies 与 ProjectAgentActionDependencies 的工具适配
  variation_point: none
  inputs: [work_id, asset_id, base_revision, content, reason]
  outputs: [archive detail, owner mutation receipt]
  invariants: [只允许注册作品与注册资产, 保留版本冲突检测及审计回执, 不代写正式正文或绕过晋升]
  allowed_dependencies: [application.assets 的现有服务, archive projection]
  forbidden_dependencies: [直接写项目文件, 复制资产校验, 绕过任务生命周期]
  tests: [project_agent 定向工具测试, archive owner transaction 测试]
  rollback_unit: 顶层 Agent 工具合同与组合根改动
  documentation: [本文件]
```

## Module Change Packet B：作者自写文风层

```yaml
module_change_packet:
  objective: 顶层 Agent 可在正式不可变文风版本之外写入带版本和回执的项目文风指令，并影响后续场景
  primary_module: application/style/
  public_entry: owner style directive service
  variation_point: none
  inputs: [work root, current revision, prompt text, reason]
  outputs: [new revision, audit receipt, active directive]
  invariants: [不伪造正式文风审查结果, 不修改不可变版本包, 不覆盖 canon 和用户明示事实]
  allowed_dependencies: [project_agent adapter, Pi scene prompt adapter]
  forbidden_dependencies: [绕过正式 style mount 校验, 覆写正式版本文件]
  tests: [style directive 版本冲突与生效测试]
  rollback_unit: 作者文风指令层
  documentation: [本文件]
```

## Module Change Packet C：角色与环境情绪初始化

```yaml
module_change_packet:
  objective: 角色和环境初始化挂载鲜明情绪标签
  primary_module: literary/scene/roleplay/
  public_entry: performance plan prompt 与初始化渲染器
  variation_point: none
  inputs: [SceneBrief, 人物档案, 主创的标签方案]
  outputs: [带个性情绪指向的角色标签, 带情绪空间感的环境标签]
  invariants: [导演仍可自由定制标签, 初始化不承载具体场景任务]
  allowed_dependencies: [既有 performance prompt 与初始化渲染器]
  forbidden_dependencies: [新增硬门禁, 改变正式素材所有权]
  tests: [角色与环境初始化合同测试]
  rollback_unit: 情绪初始化提示改动
  documentation: [本文件]
```

## Module Change Packet D：主创情绪与审查短句

```yaml
module_change_packet:
  objective: 主创承担可感的情绪弧线，审查阶段识别真正损害阅读的短句堆叠
  primary_module: runtimes/pi_scene_*_prompt.py
  public_entry: render_scene_create_prompt, render_scene_revision_prompt, render_scene_review_prompt
  variation_point: none
  inputs: [SceneBrief, Candidate, VerificationReport, 一级素材]
  outputs: [主创情绪引导, 有原文证据的短句与情绪审查建议]
  invariants: [短句审查为软文学判断, 有叙事落点的短句保留, 不按情绪词或段落数量打分]
  allowed_dependencies: [既有 Pi Scene prompt recipe]
  forbidden_dependencies: [新增硬门禁, 复制作文审查状态机]
  tests: [scene prompt 合同测试]
  rollback_unit: 主创与审查提示改动
  documentation: [本文件]
```

实施顺序：档案读写合同及组合、自写文风层、情绪初始化、主创与审查提示。当前工作树有大量既有改动，保留它们，不把无关文件纳入本轮改动。

## 已落实与验证

- 顶层 Agent 可分页查看档案树、详情、历史和回收站；创建、替换、归档与恢复均走前端使用的 owner 服务。替换须提供精确 base revision，服务返回审计回执和影响信息。
- 新增正式文风版本目录读取，挂载时仍使用不可变版本的预览、完整性和影响检查。顶层 Agent 自写的文风指令是另一个有版本与审计回执的项目层，显示在挂载状态中；它不会被伪称为已通过正式盲评的版本。
- 自写指令进入 lean 场景的主创、角色/环境素材和审查来源。角色、环境初始化与主创提示获得明确情绪标签；审查者按原文相邻短句及阅读损害判断，不把现有短句 lint 提醒升级为确定性硬门禁。
- 定向 Python 测试、Pi Worker 构建和测试、架构审计、prompt registry 校验、`git diff --check` 均已通过。尚未进行真实模型端到端创作试跑，因此文风实际收益仍需用下一场正文验证。
