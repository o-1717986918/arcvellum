# 轻量创作链路：人物背景、世界规则与首轮场景篇幅

## 批次 A：轻量资产生成

```yaml
module_change_packet:
  objective: "在初始人物档案和世界事实之后，独立创作可用的隐性背景故事及可执行的细化世界规则"
  primary_module: "application/"
  public_entry: "LeanRouteAutopilotHost character-and-world-assets"
  variation_point: "lean asset enrichment service"
  inputs: ["lean_project_plan.json", "已建立的人物档案", "用户方向", "现存世界规则"]
  outputs: ["人物 background_story", "细化 canon/world_rules.yaml"]
  invariants: ["用户已有资产不被覆盖", "不凭空升级未确认事实", "背景故事作为隐性行为因果", "不扩展通用顶层 Agent 文件系统权限"]
  allowed_dependencies: ["tool-free Pi role conversation", "atomic project writes"]
  forbidden_dependencies: ["直接执行任意命令", "修改任务状态机或审批 Gate"]
  tests: ["lean assets 单元测试", "lean route 集成回归"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本执行记录"]
```

## 批次 B：轻量场景生成篇幅

```yaml
module_change_packet:
  objective: "在首轮创作阶段按场景预算完成有情节承载的正文，减少短稿直接进入审查的情况"
  primary_module: "runtimes/"
  public_entry: "PiSceneTransactionRuntime.create_scene"
  variation_point: "scene create prompt and same-stage prose completion"
  inputs: ["SceneBrief.length", "规划节拍", "已生成正文"]
  outputs: ["接近场景预算的完整 CreativeResult"]
  invariants: ["不灌水", "不提前完成后续场景职责", "保留结构化 scene_delta", "字数偏差仍非单独审查门禁"]
  allowed_dependencies: ["tool-free Pi role conversation", "正式中文内容字符计数"]
  forbidden_dependencies: ["修改字数目标", "绕过人物/canon/语言硬约束"]
  tests: ["Pi scene runtime tests", "lean scene transaction tests"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本执行记录"]
```

现状证据：桌面自动创作的 `longform-planning` 先创建含 `background` 和 `world_facts` 的简表；`character-and-world-assets` 仅将其直接写成简短 YAML，没有独立背景故事创作，也没有细化世界规则创作。旧版资产候选链路虽然有对应 schema 与 sidecar，但不在当前轻量自动创作路径中。场景预算已进入 `SceneBrief.length` 与首轮提示词；轻量事务验证把低于 `soft_min` 记为 warning，审查者被要求不因软字数偏差单独退回，故首轮短稿可以提交。

顶层 Agent 权限审计：当前为显式工具白名单，提供项目概览、检索、观察、诊断、记录方向、目标管理和经应用服务的有限写操作。它没有任意文件读写或命令执行权，也不应以扩大权限替代缺失的轻量创作能力。若未来开放更多权能，应增加具体、可审计的领域工具，而非泛用 shell/文件系统。

## 批次 C：顶层 Agent 受控重排权限

```yaml
module_change_packet:
  objective: "使顶层 Agent 能在用户授权的作品内补足当前章场景库存并重排未来场次预算，解除已证实的章末阻断"
  primary_module: "project_agent/"
  public_entry: "project_chapter_extend domain tool"
  variation_point: "application lean chapter expansion service"
  inputs: ["注册作品作用域", "章 ID", "追加场数", "未来单场目标", "用户方向"]
  outputs: ["追加的场景计划与 YAML", "一致的章节/卷/全书场次预算"]
  invariants: ["总字数与章数不变", "已晋升场景及正文不覆写", "新场景只能接在现有成稿之后", "审批与审查边界不变"]
  allowed_dependencies: ["Project Agent 受控动作", "轻量规划服务", "正式场景物化入口"]
  forbidden_dependencies: ["任意 shell/文件系统写入", "直接修改正文", "降低章级目标规避阻断"]
  tests: ["顶层 Agent 工具注册/作用域", "场景追加与预算一致性", "已完成场景保护", "轻量路线回归"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本执行记录"]
```

现场证据：《他与她》第二章检查点为 `revision-required`，目标 17,100 中文内容字符，实交 8,678（51%）；六场正文已晋升。现有工具只有节奏、质量、文风、资产晋升、目标管理等可写能力，缺少场景库存和预算调整。重复恢复已实证无效。原会话建议在已晋升的《盘货》《改口》《独客》之间插场，不可执行；后续补场必须按时间顺序追加，保护既有正文和状态写回。

实场验证：顶层 Agent 经新工具将《代存》《排期》《回话》追加为 `scene_0007` 至 `scene_0009`，预算总目标仍为 300,000，规划场数由 35 调整为 96，旧正文未动。因本轮按用户要求未恢复，Autopilot 的 `lean-scene-checkpoint` 是扩场前的停机记录。顶层 Agent 曾误将六场的场景目标相加为新的章级目标 27,000；实际上 `load_chapter_planning_facts` 从 `chapter_budgets` 读取章级目标，仍为 17,100，而循环在本章有未提交场景时先推进 `scene_0007`，不会先复用旧的章末检查点。已在工具回执与顶层提示词中明确这两点；真正过章仍需新三场成稿并重算检查点。

补场后发现 `rhythm_plan.json` 的书级 directive 仍说倒插场景、以《独客》收束；旧用户方向日志也保留该说法。这些是未来创作的输入，不能只修正场景库存。顶层 Agent 现可用既有 `project_rhythm_update` 仅提交 `book_profile`，应用服务保留已保存的逐场人工覆盖，新场景继续使用场景 YAML 中的默认节奏，避免让 Agent 手抄九条记录；另通过方向记录说明旧插场口径已被追加式修复取代。

第一次实场重试表明，节奏读取模型还包括从新场景 YAML 派生的默认角色（`escalation`、`bridge`、`payoff`），而旧节奏编辑器只接受其人工覆盖枚举，重新保存这三条会被拒绝。profile-only 适配因此只保留 `source=rhythm-plan` 的既存人工覆盖；新场景默认继续留在 scene YAML，既不被重写也不丢失。失败尝试未改变正式记录。
