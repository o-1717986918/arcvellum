# 轻量资产初始化与事件预算修正

## 现场证据

《青春之旅》的长期目标连续三次停在 `character-and-world-assets`。人物与世界占位文件均已存在，最初失败点是深化模型把 `world.rules` 返回为结构化规则对象，而应用层只接受字符串数组；模型的有效内容因此在原子写入前被整体拒绝。修正校验后，真实重跑还证明六份人物档案与世界规则合并为一次响应会撞到模型单次输出上限并留下残缺 JSON，旧流程没有结构返修。现有人物深化合同还只生成背景故事，没有外形与衣着、信念与意图、公开面具、关系张力和可区分的说话方式，不能支撑后续人物化对白。

《他与她》已经提交 70 场、约 21.9 万字。计划先按总字数推导 96 个场景槽位，随后滚动规划只看到最近三场后果，未持有全书已用事件摘要；缺少新事件时，模型反复生成“听见名字、排期逼契书、媒人递话、看信不拆”等可逆拍子。用户已选择把未来压缩为第 71—86 场，并让信、差额和存主成为不可逆兑现锚，但该方向只进入方向记录，当前计划与预算尚未改变。第 71 场旧候选又因计划来源在生成后发生变化而被乐观并发校验拦下。

此前顶层 Agent 所称“工具预算耗尽”混合了两个概念：旧版固定调用次数已经移除；当前只保留单次工具结果的 64 KiB 传输边界，而读模型把“大结果已截断”误写成“工具预算截断”，容易诱导错误诊断。

## 批次 A：资产深化合同

```yaml
module_change_packet:
  objective: "让规划占位资产一次深化为可用于人物行动、对白和世界后果的正式资料"
  primary_module: "Studio application/lean_asset_enrichment"
  public_entry: "enrich_lean_planning_assets()"
  variation_point: "现实题材与幻想题材仍由已有世界事实决定具体规则内容"
  inputs: ["lean_project_plan characters/world_facts", "用户方向", "project/forbidden constraints"]
  outputs: ["完整人物档案", "可执行世界规则"]
  invariants: ["只改仍与机器占位完全一致的资产", "用户编辑永不覆盖", "人物与世界分批生成后整批原子写入", "每批最多一次结构返修", "背景故事默认隐性呈现"]
  allowed_dependencies: ["Engine public character slug and atomic write API", "RoleConversationGateway"]
  forbidden_dependencies: ["直接数据库写入", "新增审查 Gate", "第二套人物资产格式"]
  tests: ["tests/test_lean_assets.py"]
  rollback_unit: "资产深化实现与测试独立提交"
  documentation: ["本记录"]
```

## 批次 B：事件优先的未来重排

```yaml
module_change_packet:
  objective: "允许顶层 Agent 在不改已提交正文的前提下，按不可逆事件重做未来场景并缩减虚假容量"
  primary_module: "Studio application/lean_future_replan + project_agent"
  public_entry: "project_future_replan"
  variation_point: "调用方提供各章最终场数与创作方向，模型只设计尚未提交的连续后缀"
  inputs: ["已提交场景前缀", "章节职责", "章级字数预算", "用户认可的兑现锚"]
  outputs: ["替换后的未写场景后缀", "同步后的 project.yaml 与章/卷/全书场数预算", "可审计回执"]
  invariants: ["已提交场景、正文、事实和总字数目标不变", "project.yaml、计划摘要与正式预算的场数一致", "只覆盖无正文无提交回执的未来 YAML", "场景 ID 连续", "不自动恢复长期目标"]
  allowed_dependencies: ["Engine public lean-plan/materialization API", "RoleConversationGateway", "Project Agent allowlist"]
  forbidden_dependencies: ["倒插已成稿历史", "直接修改已提交正文", "用节奏配置伪造场景库存", "自动追加场景补字数"]
  tests: ["tests/test_lean_future_replan.py", "tests/project_agent/*"]
  rollback_unit: "未来重排服务与 Project Agent 适配独立提交"
  documentation: ["本记录"]
```

## 批次 C：滚动规划与陈旧事务恢复

```yaml
module_change_packet:
  objective: "让新规划看见已用事件，并在计划来源改变后从新 brief 重建场景事务"
  primary_module: "Studio application/lean_longform_planning + automation/lean_scene_loop"
  public_entry: "下一章窗口提示与 LeanSceneRunCoordinator"
  variation_point: "按当前章职责、全书已用事件与最新用户方向生成不同事件"
  inputs: ["全书已规划场景的功能/后果摘要", "当前章转向", "blocked transaction source revision"]
  outputs: ["避免复演的下一章窗口", "fresh scene transaction"]
  invariants: ["不增加文学审查门禁", "并发校验继续阻止陈旧候选提交", "旧候选保留为历史证据"]
  allowed_dependencies: ["现有 rolling planner", "SceneTransactionService"]
  forbidden_dependencies: ["绕过 source revision", "复用陈旧候选", "修改提交历史"]
  tests: ["tests/test_lean_longform_plan.py", "tests/test_lean_longform_planning_service.py", "tests/test_lean_kernel_v2_autopilot_loop.py"]
  rollback_unit: "滚动提示与事务重建独立提交"
  documentation: ["本记录"]
```

## 批次 D：顶层 Agent 预算表述

```yaml
module_change_packet:
  objective: "把单次大结果截断准确表述为传输边界，避免误报工具额度耗尽"
  primary_module: "Studio project_agent/read_models"
  public_entry: "Project Agent read tools"
  variation_point: "大结果要求按 focus/section/query 缩小读取范围"
  inputs: ["read-model payload"]
  outputs: ["有预览的截断结果和准确提示"]
  invariants: ["固定工具调用次数保持移除", "64 KiB bridge 安全边界保留", "超时和取消保留"]
  allowed_dependencies: ["Project Agent bridge contracts"]
  forbidden_dependencies: ["无限增大单次消息", "重新引入固定调用次数"]
  tests: ["tests/project_agent/test_read_models.py", "workers/pi-worker project-agent protocol tests"]
  rollback_unit: "读模型提示独立提交"
  documentation: ["本记录"]
```

## 验收标准

1. 结构化世界规则可被规范化为下游能读取的规则字符串，空的可选约束不再造成阻断。
2. 人物深化至少包含背景因果、外形/衣着、BDI、心理面具与边界、关系张力、语言词域和句形。
3. 顶层 Agent 能将未提交后缀按用户给定章场数重排；已提交文件逐字节不变，总字数目标不变。
4. 下一章规划携带全书已用事件摘要，并明确要求每场产生不可逆状态变化，不能以维持悬置填槽。
5. 来源变化导致的旧候选继续被拒绝，但下一次恢复会创建新事务，不在旧事务上循环冲突。
6. 《青春之旅》资产深化实际落盘；《他与她》计划改为 86 场、未来 16 场，长期创作仍不擅自恢复。

## 真实项目验收

- 《青春之旅》：6 份机器占位人物档案均已深化，人物文件具备背景因果、外形衣着、BDI、心理边界、关系张力与语言风格；世界资产落盘 6 条规则、5 项约束、3 个待确认问题。整批完成前没有写入半套资产。
- 《他与她》：正式计划、`project.yaml` 与字数预算均为 86 场；未写后缀为 `scene_0071`—`scene_0086`，章分配为 4/6/6。信、差额、代存金镯存主各只兑现一次，第十三章保留“代写拒绝回信”原章纲，第十四章的各自离开固定在最后一场。
- 对《他与她》前 70 场的场景合同、正文与提交凭据逐文件计算 SHA-256，重排前后全部相同；计划数组前 70 项结构相同，总字数目标仍为 300000。
- 两个既有长期运行仍保持 `blocked` 历史终态，没有被修复操作自动恢复；下一次由用户明确恢复时，《青春之旅》会跳过已完成资产，《他与她》的旧第 71 场事务会从当前场景来源重新准备。
