# Phase 54: Codex-Style Creative Director

本阶段把创作总监从“固定 workflow 路由器”推进为第一版 Codex 式文学工程总控 Agent。

## 用户体验

- 用户可以继续用自然语言和创作总监对话。
- 前端不再强制要求 `Project Root`；留空时，创作总监可以从一句创作方向自动建立新文学工程项目。
- 如果用户明确提出“新建项目 / 一句话生成完整文学项目”，即使当前已有项目，也会创建一个新的相邻项目，避免覆盖旧项目。
- 前端只展示自然对话、用户需要判断的创作取舍和折叠的处理记录。

## 后台能力

- 新增 `bootstrap_project_from_direction()`：
  - 从一句创作方向生成工程项目目录。
  - 写入 `project.yaml`、`AGENTS.md`、`agentread.yaml`、canon、characters、plot、drafts、memory、workflow 等完整骨架。
  - 写入 `director/bootstrap.json` 记录本次建项来源和文件列表。
- `director_decision.v1` 兼容新增字段：
  - `conversation_headline`
  - `conversation_reply`
  - `director_tools`
- `director_tools` 是隐藏工具计划，用于记录创作总监准备调用的内部能力，例如：
  - `init_project`
  - `run_workflow`
  - `create_asset_candidate`
  - `review_candidates`
  - `summarize_project_status`
  - `ask_user`
  - `write_director_report`

## 安全边界

- 新建项目只会发生在允许根目录内。
- 已有项目不会被隐式覆盖。
- canon、人物、主线等正式资产仍不被直接重写；新增内容优先进入候选、审查和记录链路。
- 前端对话层继续过滤 schema、workflow、文件路径、候选 ID 等内部词。

## 回归

- 新增 API 测试覆盖一句话建项。
- 新增工具计划断言，确保创作总监输出隐藏 `director_tools`。
- 全量测试：`117 tests OK`。
