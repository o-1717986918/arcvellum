# ArcVellum 顶层 Agent 与 Lean v2 真实端到端验收

日期：2026-09-15  
结论：通过

## 验收范围

本轮使用真实用户入口和真实模型，验证以下连续链路：

1. 用户向顶层 Project Agent 提交长任务。
2. Project Agent 创建作品并启动全自动长期目标。
3. Autopilot 使用 `lean-v2` 文学内核和内置 Pi Worker 推进项目。
4. Lean Scene Transaction 生成正文、语义审查、提交场景增量。
5. 项目级 Canon、长篇质量和委员会审查完成。
6. 章节工作区、章节正式发布和整书交付完成。
7. 同一 Project Agent 持久会话读取最终证据并向用户报告结果。

## 真实运行

- Project Agent session：`project-agent-9f120e9329784b7c`
- Work ID：`work-a1cf9d0ef68ae01d`
- Autopilot run：`autopilot-1454776303504f1b`
- 项目：`C:/Users/26532/Documents/ArcVellum/Works/ArcVellum目标模式验收-20260914-2104`
- Runtime：`pi-worker`
- Provider/model：`deepseek/deepseek-v4-flash`
- Policy：`full_auto`、`lean-v2`、委派发布
- 最终状态：`complete`
- 正式任务：91 项
- 最终失败数：0
- 待用户决策：0

## 场景事务证据

`scene_0001` 已生成并通过正式事务提交：

- Transaction：`scene-tx-0c41213620c849549cd9c2192da2dfa7`
- Receipt schema：`arcvellum/scene-commit/v2`
- Review decision：`pass`
- Steward approved：`true`
- Prose SHA-256：`7b6f3ceb5999af5aea20cd8f5a9efc0a3c26249cc54d5c06917c66b6da7919a8`
- 正文：`drafts/scenes/scene_0001.md`
- 场景增量：`workflow/scene_deltas/scene_0001.json`
- 提交回执：`workflow/scene_commits/scene_0001.json`
- 中文内容字符：1314，目标 1000，通过字数契约

这证明 Lean v2 的核心事务没有停留在原型层：正文、审查结论、结构化增量和不可混淆的提交回执均已落盘。

## 最终交付证据

整书发布目录：`releases/whole-book/`

- `ArcVellum目标模式验收-20260914-2104-complete.md`
- `ArcVellum目标模式验收-20260914-2104-complete.docx`
- `ArcVellum目标模式验收-20260914-2104-complete.layout.json`
- `ArcVellum目标模式验收-20260914-2104-complete.inspection.json`
- `release_manifest.json`

发布清单记录：

- `status: released`
- `approved_by: delegated-agent:creative-steward`
- `scene-development` 使用 Lean v2 审计，1/1 场景 ready
- `review-and-audit` 阻断 0
- `export-and-release` 阻断 0
- 工作流痕迹过滤通过
- 场景编号标题过滤通过
- DOCX 检查警告 0、缺失项 0

同一 Project Agent 会话最终又执行 8 次工具调用，读取运行和发布证据，正确报告作品已完成且无需恢复。这验证了持久会话可以从长期任务中断后的真实项目状态继续工作。

兼容投影收口后，该会话又执行 4 次只读工具调用进行最终复核，确认项目总进度 100%、scene-development 阻断 0，旧 strict-v1 的 context/RP/branch 步骤不再误报 Lean v2 已提交场景。

## 本轮发现与修复

### Lean v2 本体

Lean v2 场景事务已成功完成真实正文闭环，没有发现会阻断场景提交的内核缺陷。

### 新旧内核兼容层

1. 长篇审计原先只理解 strict-v1 的历史流程产物，无法把 Lean v2 的精确场景提交回执识别为 ready。
2. Autopilot 场景依赖判断仍可能要求 strict-v1 上下文、RP、分支、composition 等旧产物。
3. 导出沙箱没有携带 `workflow/scene_commits`，章节工作区无法确认 Lean v2 正文已经封存。
4. 整书发布仍调用 strict-v1 scene route audit，导致 Lean v2 已提交场景被旧义务否决。

修复后，Lean v2 通过精确正文哈希、场景 ID、事务 ID 和提交回执参与长篇、章节与整书验收；strict-v1 项目保持原行为。

### 旧流程遗留

1. route audit 重复实现了 `conclusion == pass` 和 `final_recommendation == approve`，与共享审查语义不一致。现在统一接受没有任何正式问题的 `pass_with_notes` / `approve_with_notes`。
2. `plot/chapters/*.json` 是导出阶段生成的派生章节工作区，却被计入长篇审计新鲜度。它曾形成“审查通过 -> 导出生成工作区 -> 审查立即过期”的循环。现在审计仍可读取该目录，但派生产物不会反向使文学证据过期。
3. 最终发布在章节工作区尚未生成时直接阻断。现在会回到已有 `export-and-release` 路线补齐导出，再重试发布，不新建任务路线。
4. scene-development 的只读审计和状态投影曾继续展开 strict-v1 步骤，导致已交付作品仍显示 context/RP 等旧义务。现在合法 Lean v2 回执直接投影为单一 `lean-scene-commit` 证据；摘要与正式发布统一为 100%。

以上修复删除了重复义务和循环依赖，没有新增 Gate，也没有降低 Canon、正文哈希、语义审查或发布证据的真实性要求。

## 回归验证

聚焦测试：

```text
Ran 83 tests in 8.446s
OK
```

覆盖：

- 项目审查共享语义
- route audit 的 `pass_with_notes` / `approve_with_notes`
- 章节派生工作区不会使长篇审计过期
- Lean v2 提交回执进入长篇审计与任务沙箱
- Lean 场景依赖恢复
- 缺失章节导出的自动回退
- 整书发布使用 Lean 场景审计
- 历史 strict-v1 场景晋升兼容

`git diff --check` 通过。

## 结论

当前遇到的问题并非都来自新内核。真实缺陷主要集中在 Lean v2 与旧审计、导出、发布编排之间的兼容边界，以及旧流程内部重复且互相冲突的判定。修复后，顶层 Agent 驱动的真实全自动作品已从用户目标连续推进到整书正式交付，Lean v2 具备进入后续产品验收的基础。
