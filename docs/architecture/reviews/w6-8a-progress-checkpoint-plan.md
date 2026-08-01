# W6-8A Progress Fingerprint 与 ChapterCheckpoint 契约（计划）

## 目标

按自适应编排方案 §11 与 W6-8（AO-7）要求建立无人值守的确定性基础：

1. `ProgressFingerprint`：只接受正式项目事实（产物 hash、task lifecycle、
   gate、正文字数、义务/账本、review 绑定），不接受 Agent 自报。
2. `no_progress_detected`：同 scope 连续两轮指纹不变 → no-progress，
   触发暂停重规划与回退。
3. `ChapterCheckpoint`：最近一次正式验证的安全状态；恢复前必须验证项目
   指纹与进度指纹仍匹配。

## 边界

- 本批不读文件系统、不创建任务、不调用 Worker、不持久化、不激活计划。
- 指纹只作为诊断与恢复身份；不改变正式 Gate 顺序。

## 交付物

- `orchestration/progress.py` 与 `orchestration/checkpoint.py`。
- `tests/orchestration/test_progress_checkpoint.py`。

## 验收

- 指纹稳定且对产物/义务/review 绑定敏感；no-progress 仅在同 scope 下成立。
- checkpoint 恢复要求项目指纹与进度指纹同时匹配；ISO 时间可确定性排序。
- 非法输入（空 scope、负字数、重复产物路径、空 checkpoint 字段）有
  violation。
- Architecture Audit 不新增债务；全量测试通过。
