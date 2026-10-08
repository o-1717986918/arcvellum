# Review Issue Ledger Change Packet

```yaml
module_change_packet:
  objective: "按正文版本和显式顺序记录审读问题，给下一轮审读与主创修订提供可追踪的解决进度。"
  primary_module: "Studio runtimes/scene creator review continuity"
  public_entry: "review_continuity(root, prose) / record_review(root, prose, extracted_review, formal_review, source)"
  variation_point: "每个新正文、审读判断和问题状态"
  inputs:
    - "完整正文 SHA-256"
    - "自然审读原文和可追溯的证据摘录"
    - "前轮主要问题与本轮解决状态"
  outputs:
    - "按单调序号保存的审读记录和稳定 issue_id"
    - "对当前正文的前轮审读、当前问题及仍开放事项"
    - "供 SceneCreator 修订使用的问题进度上下文"
  invariants:
    - "审读与正文用完整 SHA-256 绑定，记录按显式序号排序，不按文件时间推断"
    - "每项重要判断引用精确正文证据；未提及的旧问题保持 uncertain"
    - "解决状态来自本轮审读；形式 ReviewResult、Gate 和提交状态不变"
    - "旧缓存可以读取；多个无顺序旧审读同时存在时明确报告歧义"
  allowed_dependencies:
    - "Studio Runtime natural output / Pi ReviewResult facade"
    - "已有审读与自然输出合同测试"
  forbidden_dependencies:
    - "Engine internal imports、Provider-specific transport"
    - "mtime 排序或从正式 Gate 推导审美状态"
    - "绕过正式审读、成稿或写回"
  tests:
    - "issue ID 复用、状态更新、证据来源和按序恢复"
    - "旧缓存歧义处理"
    - "ReviewResult 摘要保持 strength / major issue / optional exploration 区别"
  rollback_unit: "Scene review continuity ledger v1"
  documentation:
    - "docs/implementation/creative-kernel/30-review-issue-ledger-change-packet.md"
```

## 实施与验证

- 每条审读以完整正文 SHA-256 绑定，并获得单调递增序号；重试不重复登记同一正文。
- 自然审读整理为“正文已经成立、主要修订问题、可选审美探索、前轮进展”四类。Strength、major issue 与 optional exploration 保持各自语义，主要问题证据必须是当前正文中的连续原句。
- 问题以稳定 ID 延续；未提及的旧问题保留为 uncertain。审读原文、正式 ReviewResult、状态与正文散列进入作品交易本地的 ledger。
- 下一版审读读取前轮开放问题；主创修订同时收到当前正文对应的问题进度。旧缓存单条可作为前轮阅读，多条缺少序号的记录明确返回歧义。
- 已通过 38 项审读、自然输出、取材链与恢复回归，含 issue ID 复用、解决/未决、重复登记、证据引用和旧缓存歧义用例。
- 架构审计通过；证据校验和问题台账拆分后，新增代码均符合单文件/函数复杂度阈值。
