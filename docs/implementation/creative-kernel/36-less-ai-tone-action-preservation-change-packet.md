# 实验编辑保留动作路径 Change Packet

```yaml
module_change_packet:
  objective: "依据真实局部编辑中删去人物移动路径的失败，更新去 AI 味编辑提示，使措辞调整延续原文的动作经历。"
  primary_module: "Engine/Studio prompt asset experiment.less_ai_tone.editor"
  public_entry: "prompt_layer_spec('experiment.less_ai_tone.editor') frozen into each scene transaction"
  variation_point: "11 种局部观察中的整体编辑原则与第 8 条操作表达观察"
  inputs:
    - "真实同稿编辑对照中将‘绕到桌子南面站住’收成‘在桌子南面站住’的例子"
    - "已冻结的作者风格与本场正文"
  outputs:
    - "把动作、移动、方向、物件位置及先后视为同一段经历的正向局部编辑原则"
    - "涉及完整行动线的疑问交由主创札记处理"
  invariants:
    - "提示仍保持实验可选，普通配置默认关闭"
    - "旧交易继续使用冻结提示词快照"
    - "保留正向提示文风和唯一文风插槽，不增加通用否定规则"
    - "补丁程序、正式正文、SceneDelta、审读及 Gate 语义不变"
  allowed_dependencies:
    - "prompt layer registry"
    - "existing less-AI-tone prompt/runtime tests"
  forbidden_dependencies:
    - "语义分类模型或新的 Provider 请求"
    - "整段自动重写"
    - "通过计量分数判断动作语义"
  tests:
    - "动作路径与原有提示版本变化可验证"
    - "唯一文风槽与 11 条观察保留"
    - "编辑模板不引入用户明确排斥的否定边界口吻"
  rollback_unit: "less-AI editor prompt asset v2"
  documentation:
    - "docs/implementation/creative-kernel/36-less-ai-tone-action-preservation-change-packet.md"
```

## 修订文字

编辑可以改变语序和句法，替换后的段落仍应让读者读出原句已写明的人物动作、移动方向、物件位置和发生顺序。若疑问在动作是否完整、物件是否连贯或人物如何经过空间，就把原文证据交给主创，在完整场景中判断。此项修订对应既有实际样本；真实模型复测仍待连接恢复后进行。

## 后续证据复核

第 26 号验收报告对“她绕到桌子南面站住”改为“她在桌子南面站住”给出的评价是“减少不必要的移动，表达更准确”。因此，该报告本身不能支持本包最初的“删去有效移动路径的失败”定性。v2 的逐项保留措辞也可能把修订方向推向过度保留。后续按上下文判断路线在本场是否承担抵达、阻碍、迟疑、关系距离或视点信息，见第 37 号变更包；原始报告中的文学判断保留为本 Agent 阅读记录，不声称已完成独立盲评。
