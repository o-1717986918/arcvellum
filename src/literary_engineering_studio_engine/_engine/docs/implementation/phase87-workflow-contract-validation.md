# Phase 87: Workflow Contract Validation

版本：`v0.87.0`

本阶段把 CLI-mediated route loop 继续硬化为可审计的 workflow contract。目标是减少平台 Agent 在长篇批量创作中“看起来已经完成，其实跳过 sidecar / review / promotion / state patch”的漏洞。

## 新增能力

- 新增 `workflow-validate` CLI 命令。
- 新增 `workflow_contract.py`，只读校验 route state、task records、submissions、completion markers 和 event log。
- 新增 `schemas/workflow_state.v1.json` 与 `schemas/workflow_event.v1.json`。
- 新增 `workflow/workflow_contract.md` 与 `workflow/workflow_contract.json` 输出。
- 新增 `docs/modules/workflow-state-machine.md` 作为 Agent 可读的状态机规范。

## 校验范围

`workflow-validate` 检查：

1. `workflow/route_state.json` 是否符合 formal route state schema。
2. route item 是否存在“下游 pass、上游 blocking”的顺序异常。
3. `status=ready` 是否与 steps 全部 `pass` 一致。
4. `workflow/tasks/*.task.json` 是否有合法 schema、task id、route、state、expected outputs。
5. submitted task 是否有 submission JSON，且 submission artifacts 存在。
6. completed task 是否有 completion marker，且 `expected_artifacts_checked=true`。
7. `workflow/events/task_events.jsonl` 是否为合法事件流，事件是否引用存在的 task id。

## 计数口径修正

本阶段同时把两个重要计数门禁从“机器非空白字符”改为“中文内容字符”：

- Mountable Style Skill 的 `style_prompt.md` 质量门禁仍为 500-2500，但计数单位改为中文内容字符，计入汉字和中文标点，不计入 Markdown 标记、代码围栏、英文路径或空白。
- 长篇 `word_budget`、场景 `word_count_target/min/max`、AgentReview 字数门禁和候选 manifest 现在把用户目标字数解释为清洗后中文正文字符，计入汉字和中文标点。机器非空白字符保留为诊断映射，不作为正式 pass/fail 基准。

这解决了两个旧问题：

- 文风提示词因为英文字段、路径、Markdown 标记被误判为过长或足够长。
- 正文预算因为 workflow 痕迹、scene id、文件路径、英文 key 或内部说明被计入“字数达标”。

## 使用方式

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench workflow-validate "<work-project>" --route scene-development
```

输出：

- `workflow/workflow_contract.md`
- `workflow/workflow_contract.json`

若 `status=fail`，平台 Agent 必须先修复错误，再继续 generation、review、promotion、export 或 release。

## 测试

新增测试覆盖：

- 完成任务后的 workflow contract pass。
- 下游 pass 但上游 blocking 时 fail。
- event log 引用不存在 task 时 fail。
- CLI 暴露并运行 `workflow-validate`。
- Style prompt 按中文内容字符计数。
- Word budget adherence 按中文内容字符过门，并输出机器字符诊断映射。
