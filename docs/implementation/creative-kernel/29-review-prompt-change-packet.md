# Review Prompt Change Packet

```yaml
module_change_packet:
  objective: "让审读先辨认正文成立的文学力量，再用原文证据区分主要修订问题与可选审美探索。"
  primary_module: "Engine prompting / scene.v2 review and revision assets"
  public_entry: "scene.v2.review, scene.v2.review.protocol, scene.v2.creator.revise prompt layers"
  variation_point: "作品意图、当前正文和前轮已接受的审读随场景交易变化"
  inputs:
    - "冻结作品人格、场景意图、SceneBrief 与当前正文"
    - "上一轮完整审读信及对应正文"
  outputs:
    - "自然语言审读信：成立之处、主要问题、可选探索、清楚的判断"
    - "主创修订提示：优先解决实际阅读损害并保留已成立的表达"
  invariants:
    - "文学效果由正文证据支持，不把计量距离替代审美判断"
    - "可选探索与影响场景成立的问题明确区分"
    - "保留主创独写正文与正式 ReviewResult / Gate 语义"
    - "正向引导，不添加模型身份、无权限或机械反面约束"
  allowed_dependencies:
    - "Engine prompt layer registry"
    - "提示层文本与 prompt registry tests"
  forbidden_dependencies:
    - "Studio Runtime、Provider 或项目文件写入"
    - "复制正式 Gate / ReviewResult 判断"
  tests:
    - "提示层注册与占位符检查"
    - "自然审读维度和修订问题进度的提示意图检查"
  rollback_unit: "Review prompt layer revision"
  documentation:
    - "docs/implementation/creative-kernel/29-review-prompt-change-packet.md"
```

## 实施与验证

- 审读身份、自然信件协议、修订提示层及主创委托层升级到各自 v5 文案版本。
- 审读先写正文中已成立的声音、动作和读者经验；主要问题引用原文说明阅读损害；可选探索说明它会带来怎样的另一种经验。
- 新稿审读回应前轮各问题在正文中的进展，给出已经改正、仍影响阅读、变化为新问题或证据不足的判断。修订提示保留前稿的声音和结构力量。
- 文案保留作品风格槽位，未加入统一角色边界层或输出 JSON 的创作指令。
- 已通过自然提示合同、取材链与自然创作共 19 项定向测试；Prompt Registry 59 个素材、73 个任务 ID 全部有效。
