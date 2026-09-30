# 场景主创 v2：接口变更包与待设计提示词

本轮只实现可验证的结构和隔离能力。具体文学提示词保留占位；新链路默认不激活，旧场景交易及其提示词快照继续可用。

## Packet A：取材委托合同

```yaml
module_change_packet:
  objective: "主创可逐次编写五类委托，并选择档案条目或片段挂载"
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "public.literary 的 SceneMaterialRequestV3 解析合同"
  variation_point: "委托内容、角色知识分区和档案挂载随场景变化"
  inputs: ["SceneBrief", "主创委托", "档案条目引用"]
  outputs: ["验证后的委托与挂载引用"]
  invariants: ["主创独有正文写权", "候选不得自动晋升", "角色知识分区保留"]
  allowed_dependencies: ["Engine literary", "Engine prompting"]
  forbidden_dependencies: ["Studio 文件系统", "Provider SDK", "正式 Gate 副本"]
  tests: ["五类委托合同", "附件与知识边界", "公开 API"]
  rollback_unit: "取材委托 v3 合同"
  documentation: ["本记录"]
```

## Packet B：档案、必达信息和持久工作区

```yaml
module_change_packet:
  objective: "主创自由只读作品档案，并获得可跨场景使用的隔离工作区"
  primary_module: "Studio runtimes/scene creator v2"
  public_entry: "SceneCreatorWorkspace 与 SceneCreatorBriefing"
  variation_point: "作品档案内容和主创笔记按作品变化"
  inputs: ["作品根目录", "Studio 数据根目录", "SceneBrief", "人格版本"]
  outputs: ["只读档案工具结果", "挂载快照", "必达信息包", "沙盒文件"]
  invariants: ["档案无写权", "沙盒不进入正式写回", "无越界路径或符号链接逃逸", "超预算不静默裁剪"]
  allowed_dependencies: ["Engine public literary/projections", "Studio Runtime DTO"]
  forbidden_dependencies: ["Engine internal import", "Provider SDK", "Canon 写回"]
  tests: ["档案整条和片段挂载", "来源冻结", "必达信息缺失状态", "跨场景沙盒隔离"]
  rollback_unit: "Studio 主创 v2 工作区"
  documentation: ["本记录"]
```

## Packet C：Pi 会话工具与未激活的新提示词链

```yaml
module_change_packet:
  objective: "只为场景主创挂载档案读取及沙盒工具，并保留 v1 会话兼容"
  primary_module: "workers/pi-worker"
  public_entry: "arcvellum/scene-creator/v2 会话 envelope"
  variation_point: "不同场景主创工作区根路径"
  inputs: ["主创身份提示", "档案根", "沙盒根", "场景提示"]
  outputs: ["工具结果与主创回答"]
  invariants: ["五类取材 Agent 无档案工具", "正式项目无写权", "v1 会话不变"]
  allowed_dependencies: ["Node 文件系统", "Pi SDK 工具类型"]
  forbidden_dependencies: ["Studio 数据库", "正式任务写回", "通用 Shell"]
  tests: ["v2 envelope", "目录/搜索/读取", "沙盒操作", "角色无工具"]
  rollback_unit: "Pi 主创 v2 工具"
  documentation: ["本记录"]
```

## 提示词待设计清单

初次重组的具体文案均为占位；后续角色系统卡及主创填写任务已提供草稿，见 16-actor-character-card.md。其他文案仍待设计，不得把占位文字作为正式创作指令激活。

激活入口为 `application.scene_creator_v2.enabled`。顶层人格模板和所有 `scene.v2.*` 层完成前，顶层或场景入口会明确拒绝 v2 运行；旧交易继续使用原提示词快照。档案初始化、场景审查、提交与 SceneDelta 写回仍由原有正式流程负责。

- 顶层：人格生成与更新；审查 `project_agent.creative_direction`、`project_agent.system.{read,write}.protocol`、`project_agent.turn.protocol`、`project_agent.scene_checkpoint.protocol`、`project_agent.goal_followup.protocol`。
- 主创：人格承接、必达信息、档案读取、委托编写、附件选择、候选取舍、修订、沙盒；审查 `scene.creator.*` 与 `scene.material.selection`。
- 五类：角色、环境、人物描写、事件叙述、场面描写各自的身份、当轮任务和输出；审查 `scene.actor.*`、`scene.environment.*`、`scene.describer.*`、`scene.description.turn`。
- 共同边界：档案状态、角色可知与仅供参考、候选事实边界；审查 `scene.protocol`、`scene.fallbacks.protocol`、`scene.quantitative_detail.protocol`、`scene.ownership.action-audit.protocol`、`scene.review*` 及渲染器内置短句。
- `scene.performance.plan*` 退出独立创作规划；其仍需在旧交易中保留兼容。

## Packet D：作品级主创人格的顶层初始化

~~~yaml
module_change_packet:
  objective: "顶层 Agent 按用户意图生成并维护版本化主创人格"
  primary_module: "Studio project_agent"
  public_entry: "creator_persona_read/update 与 CreatorPersonaStore"
  variation_point: "用户明确改变作品创作意图"
  inputs: ["作品作用域", "用户方向", "人格生成模板"]
  outputs: ["人格版本", "方向摘要", "主创初始化输入"]
  invariants: ["无新用户方向不重写人格", "未完成文案时不启用 v2", "不直接写正文或 Canon"]
  allowed_dependencies: ["application CreatorPersonaStore", "Engine public prompting", "Pi Project Agent 工具 adapter"]
  forbidden_dependencies: ["Engine internal", "正式写回 Gate 副本"]
  tests: ["人格版本及用户方向门禁", "Project Agent 工具与只读权限", "Pi 工具合同"]
  rollback_unit: "顶层主创人格初始化"
  documentation: ["本记录", "16-actor-character-card.md"]
~~~

当前验证：Project Agent 的 73 项 Python 测试通过。人格写入沿用现有顶层写权限，具体生成模板仍占位。
