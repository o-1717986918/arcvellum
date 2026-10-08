# 实验编辑按场景作用判断动作路径 Change Packet

```yaml
module_change_packet:
  objective: "依据既有验收记录对‘绕到桌子南面’缩为‘在桌子南面’的正向评价，修正 v2 对动作路径的泛化保留要求，让编辑依据全场判断路径信息的文学作用。"
  primary_module: "Engine prompt asset experiment.less_ai_tone.editor"
  public_entry: "prompt_layer_spec('experiment.less_ai_tone.editor') frozen into each scene transaction"
  variation_point: "局部表达编辑对路线、站位、动作结果的上下文判断"
  inputs:
    - "docs/implementation/creative-kernel/26-creative-acceptance-results.md 中对路线缩写‘减少不必要的移动，表达更准确’的验收记录"
    - "v2 提示词将已写明的移动路径统一要求为逐项保留的表述"
    - "已有 scene.v2.review 对行动线、空间位置和正文证据的审读职责"
  outputs:
    - "按路径是否承担抵达、阻碍、迟疑、关系距离或视角信息来编辑的正向提示"
    - "上下文已建立站位且路线仅重复方位时，允许更直接地落在动作结果"
    - "完整行动线与物件衔接问题继续进入主创札记并由整场审读判断"
  invariants:
    - "去 AI 味实验保持可选且默认关闭"
    - "旧交易继续使用已冻结的 v1/v2 提示快照"
    - "文风槽仍唯一；作者文风继续与主创共用交易冻结版本"
    - "局部改稿仍由主创审读，正式正文和 SceneDelta 的既有审读与写回保持"
    - "提示保持正向文学判断，不加入通用否定权限话术"
  allowed_dependencies:
    - "prompt layer registry"
    - "已有场景审读和实验编辑合同测试"
  forbidden_dependencies:
    - "新增 Provider 调用或语义评分模型"
    - "词表驱动的动作分类器"
    - "将单一案例包装成真实模型复测或盲评"
  tests:
    - "提示版本升至 v3 并仅含一个文风插槽"
    - "动作路径按叙事功能保留、简化或提交全场判断的条件均可见"
    - "实验编辑后的正文仍进入正式场景审读"
    - "不引入用户明确反对的否定边界套话"
  rollback_unit: "less-AI editor prompt asset v3"
  documentation:
    - "docs/implementation/creative-kernel/37-less-ai-tone-contextual-action-change-packet.md"
```

## 证据校正

第 26 号验收报告记录了编辑把“她绕到桌子南面站住”改成“她在桌子南面站住”，并明确评价为减少不必要的移动、表达更准确。第 36 号变更包把它重新归类为删去有效移动路径的失败，证据并不支持这种定性；缺少该句完整上下文，也不足以把此改动确认为普遍正确的文学规则。

本包因此撤回“每条已写动作路径都应逐项保留”的概括。提示改为考察路线在当前段落与全场中的作用：它若使抵达方式、阻碍、迟疑、关系距离或视点经验可感，就保留相应经验；上下文已建立站位且路线只重复方位时，可以直接落在动作结果。完整行动线仍由主创结合场景审读。

## 验证范围

此次只修正规则的证据解释与提示表达，并以合同测试确认版本、文风槽和全场审读接线。真实模型重跑与独立文学评审仍待连接恢复后完成；不从离线测试推断文学收益。
