# 顶层 Agent 长工具阻断与档案字段权限修复

## 后台事实

《文学少女》scene_0006 候选正文已经审查通过，但旧事务在提交时发现场景输入修订变化，未晋升。随后顶层 Agent 的 `project_future_replan` 后台写入成功，Pi 工具桥却先于规划器完成而超时：桥默认等待 30 秒，规划器单次模型调用允许 900 秒。顶层 Agent 将迟到的成功误判为失败并重复重排，最终会话以 Windows 管道错误退出。当前已提交正文仍为五场。

## Module Change Packet A：长工具回执

```yaml
module_change_packet:
  objective: "耗时规划工具完成后，顶层 Agent 收到与后台一致的成功或失败结果，不因短桥超时重复执行"
  primary_module: "project_agent/ runtime bridge"
  public_entry: "ProjectToolBridge.request 与 ProjectAgentRuntime.run_turn"
  variation_point: "普通工具与调用模型的长工具耗时不同"
  inputs: ["versioned tool.call/tool.result", "turn timeout", "用户取消"]
  outputs: ["唯一工具回执", "明确终态", "持久运行事件"]
  invariants: ["工具作用域不变", "正式场景审查与提交 Gate 不变", "用户仍可取消"]
  allowed_dependencies: ["workers/pi-worker/src/project-agent-protocol.ts", "project_agent/runtime.py", "API 与 Vue feature client 的 turn timeout adapter"]
  forbidden_dependencies: ["Engine 内部模块", "任意项目文件写入", "Provider 特判"]
  tests: ["Pi 工具桥长工具/普通工具超时合同", "Project Agent runtime 长工具回执", "feature client/API 超时边界"]
  rollback_unit: "顶层 Agent transport 修复提交"
  documentation: ["本文", "故障回归记录"]
```

## Module Change Packet B：项目档案字段

```yaml
module_change_packet:
  objective: "顶层 Agent 对所有已注册作品档案类型具有与前端结构化编辑器一致的字段读取、修改和审计能力"
  primary_module: "project_agent/"
  public_entry: "project_archive_read 与 project_archive_change"
  variation_point: "文本替换与注册字段修改是两种编辑方式，均汇入同一 owner transaction"
  inputs: ["稳定 work_id", "asset_id", "exact base_revision", "registered field values", "reason"]
  outputs: ["字段定义和当前值", "owner mutation receipt", "项目缓存失效"]
  invariants: ["仅注册作品与资产", "字段类型和内容验证复用结构化编辑服务", "版本冲突拒绝", "正式正文与 Canon Gate 不旁路"]
  allowed_dependencies: ["application/assets/structured_editor.py", "application/assets/owner_transactions.py", "archive projection 与现有 API composition", "Pi Project Agent tool schema"]
  forbidden_dependencies: ["通用 Shell", "直接写资产文件", "第二套档案字段定义"]
  tests: ["各类型字段合同", "过期修订/未知字段拒绝", "Project Agent 工具端到端映射"]
  rollback_unit: "顶层 Agent 档案字段工具提交"
  documentation: ["本文", "工具权限说明"]
```

## 完成标准

1. 慢于旧 30 秒桥限的重排能将同一调用的真实结果交回顶层 Agent；失败也有明确错误，不产生假超时成功。
2. 顶层 Agent 可列出档案字段，并在精确修订版上更新人物、场景、世界规则等当前档案编辑器可改字段；回执与前端同源。
3. 恢复指引优先续接当前目标；场景源改变时重新准备事务，不把历史计划的阻断当成再次重排的理由。
4. 不对用户正式作品直接试写；回归使用临时项目和模拟 Agent。

## Module Change Packet C：缺失档案补齐

```yaml
module_change_packet:
  objective: "顶层 Agent 发现规划内档案缺失或仍为初始化占位时，可以调用当前 lean-v2 标准资产初始化与深化路径"
  primary_module: "project_agent/ 与 application/lean_assets"
  public_entry: "project_assets_reconcile"
  variation_point: "初次自动创作与后续项目管理复用同一补齐路径"
  inputs: ["注册 work_id", "现存 lean_project_plan.json", "已确认人物及世界档案"]
  outputs: ["创建/深化计数", "仍无法由现有计划自动匹配的档案提示"]
  invariants: ["不覆盖已编辑档案", "未在规划中的角色由标准作者资产创建事务处理", "旧内核仍走其正式候选资产路线"]
  allowed_dependencies: ["现有 ensure_lean_planning_assets", "现有 enrich_lean_planning_assets", "RoleConversationGateway", "Project Agent allowlist"]
  forbidden_dependencies: ["直接写正式档案的新旁路", "自动更名或合并既有身份", "绕开旧内核审批门禁"]
  tests: ["缺失规划档案补齐", "现存用户档案不覆盖", "工具分发与长调用回执"]
  rollback_unit: "顶层 Agent 资产补齐工具提交"
  documentation: ["本文", "工具权限说明"]
```

## Module Change Packet D：用户检查点与阻断诊断

《文学少女》会话第 13 条用户要求一直推进到第七场。顶层 Agent 在 `resume` 调用中传入 `stop_after_formal_units=7`，但现有动作仅在 `start` 分支读取此参数；当时返回的运行策略仍为 0，Agent 却立即向用户宣称已设置第七场检查点。后来另一条 `autopilot.policy_updated` 事件才把两次运行的检查点改为 7。随后它用与实际 `controller-error` 不符的 `expected_stop_reason` 恢复，得到 `checkpoint_changed`，又因项目规划陈旧状态反复执行耗时重排。计划有效性实际只比较 `project.yaml` 与 `lean_project_plan.json` 的摘要，不能从该错误推断人物标签或文风是变更源。

```yaml
module_change_packet:
  objective: "恢复目标时真正写入用户指定的正式场次检查点，并让诊断呈现计划源摘要的客观对齐状态"
  primary_module: "project_agent/"
  public_entry: "project_goal_manage 与 project_diagnose"
  variation_point: "start 与 resume/recover 均可接收新的检查点；历史 blocked 与当前规划是否对齐是两个状态"
  inputs: ["可选 stop_after_formal_units", "现有暂停或阻断运行", "project.yaml", "lean_project_plan.json"]
  outputs: ["持久化后的运行策略", "规划摘要对齐状态", "恢复或重排建议"]
  invariants: ["未显式传入检查点时保留原策略", "错误的 expected_stop_reason 不修改策略", "不把人格或文风更动冒充 project.yaml 摘要变化", "不改用户现有正文与规划"]
  allowed_dependencies: ["既有 AutopilotPolicyService.save", "Project Agent 只读投影", "现有摘要算法"]
  forbidden_dependencies: ["直接改运行数据库", "新的全书规划器", "未经用户授权回退已写规划"]
  tests: ["resume 与 recover 检查点回归", "检查点不匹配不写入", "规划对齐与陈旧诊断"]
  rollback_unit: "顶层 Agent 检查点及诊断修复提交"
  documentation: ["本文", "文学少女交互复盘"]
```

## 《文学少女》会话交互复盘

以下只读核对用户生产作品与后台 SQLite，没有恢复运行、改动作品或回退规划。

| 会话节点 | 用户真实要求 | 顶层 Agent/后台事实 | 问题 |
| --- | --- | --- | --- |
| 13–14 | 一直写到第七场结束 | 第六场候选正文 4678 汉字、审查通过；提交时场景源修订变化，仍只有 5 场正式正文。首个 `resume` 没写入 7 场检查点，但 Agent 先说已设置；后来策略更新事件才真正写入 7。它又用不符的停止原因做条件恢复。 | 场景事务阻断与检查点参数被忽略叠加；回执核验不足。 |
| 15–16 | 恢复推进；追问怎么回事 | 新运行停在长线规划入口，报 `project direction changed after planning`。顶层 Agent 多次调用耗时 `project_future_replan`；30 秒 Pi 工具桥先于 81–176 秒规划调用超时，后台写入与 Agent 所见不同步，两个会话作业以 `[Errno 22] Invalid argument` 结束。 | 重复重排、迟到写入、对话无终态答复。 |
| 17–18 | 检查是否有权修复 | Agent 把摘要失配归咎于人物人格标签、质量档案、文风挂载，称没有“一键恢复”，并让用户在所谓“平实”与人物文风间选择。 | 摘要校验只读 `project.yaml` 原始字节；这些因果推断没有证据，也没有检查最新规划是否已对齐。挂载的历史 ID 含 `clear-plain-prose`，但正式文风档案 `display_name` 与提示正文均为“弹性叙事”；Agent 把 ID 当作实际文风。 |
| 19 | 收回原文风，澄清原风格为“弹性叙事” | 作者文风指令写入成功；Agent 再次重排。重排在后台完成时，会话作业又以 `[Errno 22]` 结束，没有最终答复，也没有恢复到第六场。 | 把文风纠正误当作必需的全书重排。最近一次重排改写了第 6–56 场共 51 场未写规划，正式正文仍保留 5 场。 |

当前只读核对：`project.yaml` 的 SHA-256 与现行 `lean_project_plan.json.project_digest` 同为 `708220f1489cc23df061e9d3cc0b31b2c6d87fd8394286feaa271d9c4447881b`，即计划已对齐；两个自动创作运行仍记录 `blocked/controller-error`，第七场检查点现已存储为 7。对话失败中的 `[Errno 22]` 有数据库证据；它与工具桥超时及耗时规划调用并存，但尚无足够证据把该 Windows 错误唯一归因于某一个底层句柄。旧桌面包仍须更新才会使用本次代码修复。

工程修复：恢复/恢复阻断可原子地保存检查点并核对回执；`project_diagnose` 给出实际摘要对齐状态；顶层提示要求依据回执与摘要，不根据人物/文风文件推测计划来源；长工具桥及整轮时限已经提升。生产作品未执行自动恢复，因为本次用户消息要求的是查明原因，且最新重排已大幅改写未写规划。

验证：Python 全量 1641 项通过（1 项跳过）；最新增补的文风名称投影测试单独通过。Pi worker 113 项、前端 258 项与前端构建此前已通过；架构审计、模块图校验及 `git diff --check` 通过。代码尚未安装到用户当前桌面版本，生产作品仍保持 5 场正式正文。
