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
