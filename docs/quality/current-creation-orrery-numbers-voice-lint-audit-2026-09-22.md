# 当前创作：星仪、数字、人物语气与 lint 审查（2026-09-22）

## 现场症状与范围

用户在桌面版打开星仪后看到“暂时无法读取叙事场域 / Failed to fetch”。本机当前作品为《他与她》。以下是独立故障/质量议题，不把语言风格问题转成新的数字密度或字数门禁。

## Batch A — 星仪只读投影

```yaml
module_change_packet:
  objective: "带正式连续性投影的作品能读取星仪"
  primary_module: "Engine projections/library/"
  public_entry: "public/projections.py::build_project_library；Studio 既有 narrative projection v4 adapter"
  variation_point: "none"
  inputs: ["workflow/continuity/current.json", "正式作品目录"]
  outputs: ["library.sections.continuity", "星仪 v4 只读图"]
  invariants: ["不修改连续性正式数据", "不隐藏已有冲突", "保持路径相对作品根目录"]
  allowed_dependencies: ["Engine projections/library/common.py", "已有投影测试"]
  forbidden_dependencies: ["Studio UI 对 Engine internal 的导入", "对项目文件的隐式修复"]
  tests: ["包含 entries 与 identity_conflicts 的 library 回归", "真实作品只读星仪投影复现"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本审查记录"]
```

直接用当前源码构建《他与她》的 v4 星仪投影，失败于 `projections/library/continuity.py`：`_projected_continuity_items` 和 `_identity_conflict_items` 在生成相对路径时引用未传入的 `root`，抛出 `NameError`。现有单测只覆盖读者问题与承诺账本，未覆盖 `workflow/continuity/current.json` 中的正式 entries / identity conflicts。桌面版显示的 `Failed to fetch` 是用户侧症状；该只读投影异常是已复现的后端缺陷，仍需在桌面已安装版本上确认是否为同一次请求的唯一原因。

修复后用《他与她》现有资料只读构建 v4 星仪，返回 35 个节点、46 条边；另以带正式连续性条目的临时作品从认证的 `/narrative/projection/v4` HTTP 路由读取，返回 200 和 Tauri 跨域凭据响应头。此前未捕获的 `NameError` 会让浏览器跨域请求表现为网络失败，这是与 `Failed to fetch` 一致的机制推断；并未直接修改或重装用户当前运行的桌面安装包，因此旧安装包尚不能据此宣布已修好。

## Batch B — 当前 lean-v2 场景生成与审读

```yaml
module_change_packet:
  objective: "保留有叙事功能的数字和人物语言差异，同时退回无关精确计数"
  primary_module: "Studio runtimes/pi_scene_transaction.py"
  public_entry: "render_scene_create_prompt/render_scene_review_prompt/render_scene_revision_prompt"
  variation_point: "none；沿用现有 Pi 会话运行时"
  inputs: ["SceneBrief", "人物资产、文风样例与其他 source_refs", "候选正文"]
  outputs: ["场景生成、语义审读和修订提示"]
  invariants: ["既有事实中的数值不得漂移", "不新增数字密度门禁", "不绕开标点与违禁表达审查", "人物特色不能伪造新身世"]
  allowed_dependencies: ["现有 SceneBrief 和 source_evidence", "定向 prompt 合同测试"]
  forbidden_dependencies: ["Engine 正式 Gate 改写", "新模型调用", "数字正则阻断器"]
  tests: ["数词修辞、当场问答、因果数字与装饰数字的 prompt 回归", "人物声音生成/审读提示回归"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本审查记录"]
```

当前 `candidate_language_gate` 对“一个又一个人从门口进来”“还剩几个人？两个”均返回 `pass`。误判来自 lean-v2 最后一轮生成提示与模型审读提示：所有数词都必须同时通过五项测试，任何一处不满足即 `revise`。这把非精确的反复修辞和场景内必要答问也当成“装饰性精确读数”。《他与她》第一场的“两千三百二十块”是被问及的债额，后续又触发账目差异与婚约压力，不能按一般陈设计数删除。

人物资产已进入 `source_refs`，但当前主要人物的 `speech_style` 均未填写；现有生成提示只抽象要求“按欲望、知识边界和说话习惯反应”，没有要求从现有身份、关系与处境推导可辨认的言语策略。因此优先在生成阶段补足人物间的用词、句长、回避方式、主动/被动话语权和情境变化，不用静态对白词表做硬门禁。

实施后，lean-v2 的 create/review/revise 共用同一语义分类：虚指反复不按精确值判；当场问答、谈判、事实辨认、连续性或因果所需的精度可保留；明确无关的件数、次数与读数仍须逐句改写。审读对无关精度要求引用片段和删除精度后的信息损失判断，不能以“未通过五项全满足”直接退稿。生成前从人物现有资料推导可辨认的言语策略，审读仅在持续混同已造成阅读损害时返修。已挂载旧文风中的“五项全满足”若与新分类冲突，以本轮场景语义规则为准，不改动不可变历史文风版本。

## Batch C — 新作品文风规则源头

```yaml
module_change_packet:
  objective: "未来生成的默认文风不再把一切数词当无关精确计数，也明确保留人物声线"
  primary_module: "Engine literary/style/"
  public_entry: "默认文风模板、style.prompt 与 style.prompt_agent 的正式提示词产物"
  variation_point: "none"
  inputs: ["style profile", "授权参考语料", "项目人物与场景事实"]
  outputs: ["默认文风 profile/prompt", "文风编译提示"]
  invariants: ["不修改已有挂载版本", "不将数字审查改成计数 Gate", "保留违禁表达和标点检查"]
  allowed_dependencies: ["现有 style 模板与测试", "anti_ai 生成约束"]
  forbidden_dependencies: ["Studio runtime", "已挂载的不可变文风版本"]
  tests: ["默认预设质量与 R01—R25 完整语料测试", "文风提示词合同"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本审查记录"]
```

当前默认文风模板与文风编译器仍写“数词五项全满足”，会把旧错误继续传播给新项目。此批只修订未来产物与生成指导，不回写已经挂载的版本。

实施后，默认文风模板、文风编译器及 AI 腔生成指导均先区分虚指反复和精确计数；场景问答、辨认、选择、因果、连续性等任一实际功能足以保留精度。人物对白从现有身份、欲望、关系压力中推导差异，不用统一的“清简”口吻抹平所有人物。R01—R25 语料原文及不可变挂载版本未改动；默认预设、文风相关 18 项测试和提示词注册表校验通过。

## Batch D — 正式场景生成入口

```yaml
module_change_packet:
  objective: "消除旧场景写作入口的五项全满足规则，令人物对白在初稿分化"
  primary_module: "Engine literary/scene/composition/"
  public_entry: "draft scene workspace 与 route.scene-development.prose.generate.v1"
  variation_point: "既有 route prompt asset，不增加新路由"
  inputs: ["场景合同", "人物资产", "已挂载文风", "上下文包"]
  outputs: ["场景草稿模板", "正式正文生成提示"]
  invariants: ["事实数字准确", "无关精确实写仍需改写", "标点与违禁表达继续审查"]
  allowed_dependencies: ["既有场景生成与 prompt asset 测试"]
  forbidden_dependencies: ["新增数词密度 Gate", "改动历史文风挂载", "新增 prompt 路由"]
  tests: ["默认风格场景提示合同", "草稿模板规则回归", "prompt-registry-validate"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本审查记录"]
```

旧场景生成 route asset 和草稿工作台仍要求所有数词同时满足五项条件，且把每个精确值都限定为选择或后文兑现；这一入口虽然不同于当前 lean-v2，但会继续污染其他创作路径。修订限于生成提示，不新增静态门禁。

实施后，正式场景 route asset 与草稿工作台均采用语义分类并在下笔前区分人物言语策略。默认文风路由合同和草稿实写回归通过；prompt-registry 校验与架构审计通过。

## Batch E — 长篇规划中的数字口径

```yaml
module_change_packet:
  objective: "规划阶段不提前删掉问答、债额、身份或时间连续性需要的精确值"
  primary_module: "Studio application/lean_longform_planning.py"
  public_entry: "LeanLongformPlanningService 初始规划与滚动窗口"
  variation_point: "none；沿用现有规划 JSON schema"
  inputs: ["用户方向", "已有故事与人物事实", "章节预算"]
  outputs: ["初始因果骨架", "下一章场景窗口"]
  invariants: ["已有数值事实准确", "不为装饰添加读数", "不改规划输出 schema"]
  allowed_dependencies: ["现有规划服务测试"]
  forbidden_dependencies: ["新增规则引擎", "数字密度门禁"]
  tests: ["初始与滚动规划 prompt 合同", "现有规划服务回归"]
  rollback_unit: "独立 Git 提交"
  documentation: ["本审查记录"]
```

当前初始规划和滚动窗口均要求精确值同时改变眼前选择并在后文兑现。这会在场景尚未生成时删掉当场问答和身份、债务辨认所需的数字；应改为任一实际功能即可保留，仍拒绝装饰性计时、计件。

实施后，两个规划提示先区分虚指反复与精确计数，保留场景内真实有用的精度并延续已确定事实；JSON 输出 schema 未变。规划服务 4 项回归、架构审计和模块映射检查通过。

## Lint 规则审计

| 事项 | 当前实现 | 判断 |
| --- | --- | --- |
| 违禁对照及换皮、用户自定义禁词 | `style/anti_ai.py` 与 creative-quality profile 可阻断 | 已覆盖，继续进入审查；本轮未取消。 |
| 中文标点基础正确性 | `style/punctuation.py` 固定正确性规则阻断；句号密度、逗号链等节奏规则输出提示 | 已覆盖基础规范。节奏不是纯标点合法性，不宜再加硬门禁。 |
| 无意义精确数值 | 没有数字正则或密度规则；此前严格退稿来自模型审读提示 | 不缺静态规则。数词功能依赖问答、债务、因果和前后文；在生成与语义审读修复，避免新增误伤式扫描器。 |
| 人物声音、视角、场景变化、情节因果与跨场重复 | 场景合同、人物来源和独立 AgentReview 承担语义判断；静态 lint 不会可靠辨认谁在说话 | 不应伪装成新正则 Gate；已在生成提示中强化声线，在审读中限定为持续混同且损害阅读时返修。仍需真实创作 A/B 样本验证效果。 |
| 抽象总结、解释性心理、碎句和逗号超量 | 默认 profile 把若干软审美规则设为 `blocking`，现有《他与她》保存的 profile 也如此 | 这是现存的过硬化，不是缺规则；它与“软文风主要在生成阶段落实”存在张力。本轮没有自动改写用户保存的 profile，也没有扩大门禁。建议单独设计 profile 迁移与回归后，将可争议的审美密度降为审读证据，而保留禁词及基础标点硬审查。 |

静态回归已确认“一个又一个人从门口进来。”和“还剩几个人？两个。”通过 `candidate_language_gate`，而机械对照句及错误 ASCII 标点仍被阻断。这里的“文学规则缺口”主要是语义审读质量和人物资料字段空缺，并非再添机器可数的文学指标。
