# Phase 27：Agent Provider 基础层

## 目标

Phase 27 将“审查交给 Agent/LLM 完成”的设想落成统一基础层。此前 `generate-scene`、`style-prompt`、`style-prompt-eval` 各自拥有 provider 调用逻辑；从本阶段开始，剧情审查、canon 审查、JSON 修复、提示词生成、风格提示词评估等通用 Agent 任务可以先通过同一个 `agent-run` 入口运行、留痕和解析。

本阶段不是把所有审查都立即替换为 LLM，而是先建立可测试、可审计、可扩展的执行协议。

## 新增能力

- `agent_provider.py`
  - `AGENT_PROVIDERS = {"auto", "dry-run", "http-chat"}`。
  - `run_agent_task(...)` 执行通用 Agent 任务。
  - 写出 `input.prompt.json`、`raw_output.md`、`parsed_output.json`、`validation_report.md`。
  - `auto` 为当前默认值，配置完整时解析为 `http-chat`。
  - `dry-run` 生成稳定 JSON，用于测试下游流程。
  - `http-chat` 复用 `LEW_MODEL_API_BASE`、`LEW_MODEL_NAME`、`LEW_MODEL_API_KEY`、`LEW_MODEL_TIMEOUT`、`LEW_MODEL_TEMPERATURE`、`LEW_MODEL_MAX_TOKENS` 环境变量。
  - 不把 API key 写入任何产物。

- `lew agent-run`
  - 支持 prompt 文件：`--system`、`--user`。
  - 支持内联 prompt：`--system-text`、`--user-text`。
  - 支持 `--provider auto|dry-run|http-chat`。
  - 默认输出到 `agents/runs/{run_id}/`。

## 命令示例

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-run work/demo-work `
  --agent-id scene-reviewer `
  --task review-scene `
  --system-text "你是文学工程审查 agent。" `
  --user-text "请审查 scene_0001 的人物行为、canon 风险和修订建议。"
```

离线调试时显式追加 `--provider dry-run`。

真实模型调用也可显式指定 `http-chat`：

```powershell
$env:LEW_MODEL_API_BASE="https://your-model-endpoint/v1/chat/completions"
$env:LEW_MODEL_NAME="your-model-name"
$env:LEW_MODEL_API_KEY="your-api-key"
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-run work/demo-work `
  --agent-id canon-reviewer `
  --task review-canon-risk `
  --system prompts/review/canon_system.md `
  --user prompts/review/canon_user.md
```

## 产物契约

每次运行写入：

- `input.prompt.json`：本次 Agent 输入，包括 provider、模型标签、system/user messages、metadata 和环境变量名。
- `raw_output.md`：模型原始输出或 dry-run 输出。
- `parsed_output.json`：从原始输出中提取的 JSON。如果模型没有输出 JSON，则保留为 `not_json` 包装结构。
- `validation_report.md`：运行状态、解析状态、路径和后续处理提示。

## 边界

- Agent 输出不是 canon。
- Agent 输出即使是 JSON，也必须经过下一阶段的 schema 检查后才能被自动消费。
- `agent-run` 不写正稿、不改人物档案、不发布章节。
- `auto` / `http-chat` 从统一全局配置或环境变量读取模型配置，不接收命令行明文 key。

## 测试

新增 `tests/test_agent_provider.py`，覆盖：

- dry-run 写出四类可审计产物。
- `parsed_output.json` 可被自动读取。
- CLI `agent-run` 支持内联 prompt。
- `http-chat` 缺少模型环境变量时失败。
- CLI help 暴露 `agent-run`。

## 后续

Phase 28 会在本基础层之上增加 Agent 输出 JSON Schema 与修复循环，使后续审查、提示词生成和剧情决策能够用同一套结构化契约进入工作流。
