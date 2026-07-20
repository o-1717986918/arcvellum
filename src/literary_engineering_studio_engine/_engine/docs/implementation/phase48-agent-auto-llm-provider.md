# Phase 48：Agent 默认真实 LLM 接入

本阶段把“需要 LLM 的 Agent / 模型任务”从默认 `dry-run` 改为默认 `auto`。

## 目标

- 用户只和创作总监或前端工作台交互时，内部 Agent 默认调用真实模型。
- 角色设定、背景故事、世界观、大纲、候选审查、场景审查、canon 审查、JSON 修复、审稿委员会、文风提示词和场景候选生成都共享同一套 provider 规则。
- `dry-run` 继续保留，但只作为显式离线调试和回归测试选项。

## Provider 规则

统一支持：

- `auto`：默认值。读取全局配置和环境变量，配置完整时解析为 `http-chat`。
- `http-chat`：直接调用 chat-completions 兼容接口。
- `dry-run`：本地稳定模拟，不调用外部模型。

`auto` 需要：

- API Base
- Model
- API Key

读取优先级仍由 `model_config.py` 管理：

1. `LEW_MODEL_API_KEY`
2. active profile 指定的 `api_key_env`
3. active profile 中保存的 `api_key`

缺少配置时，系统会明确报错并提示用户在前端全局配置中填写 API Base、Model 和 API Key。

## 实现范围

- `model_config.py`
  - 新增 `MODEL_PROVIDER_CHOICES`。
  - 新增 `resolve_model_provider()`，统一把 `auto` 解析为具体 provider。
- `agent_provider.py`
  - `AGENT_PROVIDERS` 增加 `auto`。
  - `run_agent_task()` 默认 `provider="auto"`。
  - 运行产物记录解析后的 provider，并在 metadata 中保留 `requested_provider`。
- `generation_provider.py`
  - `generate_scene_candidate()` 默认 `provider="auto"`。
- `style_prompt.py` / `style_prompt_eval.py`
  - 文风约束提示词生成和提示词有效性评测默认 `auto`。
- Agent 包装层
  - 场景审查、canon 审查、JSON patch plan、JSON 修复、审稿委员会、Agent 风格提示词、候选资产生成和候选资产审查默认 `auto`。
- 顶层创作总监
  - `director-chat`、`/director/chat` 和前端“创作总监”默认 `auto`。
  - 总监解析 provider 后把同一 provider 传给内部工作流。
- 前端 / Dify / CLI
  - Provider 下拉默认 `auto`。
  - Dify Start 节点默认 `auto`。
  - CLI 不传 `--provider` 时进入 `auto`。

## 离线回归

`demo-project` 和测试仍显式使用 `provider="dry-run"`，保证无 API Key 环境下可重复验证工程链路。

## 测试

新增或更新覆盖：

- `auto` 在全局配置完整时解析为 `http-chat`。
- `run_agent_task()` 不传 provider 时会真实请求 chat 接口。
- `/director/chat` 默认 provider 在无 API Key 时返回可读错误。
- 前端和 Dify 默认选项包含 `auto`。
- 离线 demo 和测试显式使用 `dry-run`。
