# Phase 36：全局配置与本地前端控制台

## 目标

本阶段把模型接入、默认项目根目录、API 控制台和对话式工作流入口收束到统一配置层，避免 CLI、FastAPI、LangGraph、Dify 和前端各自维护一套变量。

## 已实现能力

- `src/literary_engineering_workbench/model_config.py`：统一读取、创建、保存全局配置。
- 默认配置文件：`%USERPROFILE%\.lew\config.json`，可用 `LEW_CONFIG_PATH` 改写位置。
- 默认模型 profile：`deepseek`，使用 `https://api.deepseek.com`、`deepseek-v4-flash` 和 `DEEPSEEK_API_KEY`。
- Provider 读取链路：`agent_provider.py`、`generation_provider.py`、`style_prompt.py`、`style_prompt_eval.py` 均通过 `get_model_settings()` 读取配置。
- CLI 配置命令：
  - `config-show`
  - `config-init`
  - `config-set-profile`
- FastAPI 配置接口：
  - `GET /config`
  - `POST /config`
  - `POST /config/default`
  - `GET /config/env`
- 本地前端控制台：`frontend/index.html`、`frontend/styles.css`、`frontend/app.js`，由 `serve-api` 的 `/` 和 `/ui/*` 提供。
- 对话控制接口：`POST /assistant/chat`，支持查看配置、读取项目摘要、测试模型连接、运行工作流和触发 Agent 审查。

## 配置原则

全局配置文件只保存密钥环境变量名，不保存 API Key 明文。实际密钥仍从 `DEEPSEEK_API_KEY` 或 `LEW_MODEL_API_KEY` 读取。

环境变量仍可覆盖全局配置：

- `LEW_MODEL_API_BASE`
- `LEW_MODEL_NAME`
- `LEW_MODEL_API_KEY`
- `LEW_MODEL_TEMPERATURE`
- `LEW_MODEL_MAX_TOKENS`
- `LEW_MODEL_TIMEOUT`

## 推荐启动方式

```powershell
$env:PYTHONPATH = "src"
$env:DEEPSEEK_API_KEY = "your-api-key"
python -m literary_engineering_workbench config-init
python -m literary_engineering_workbench serve-api --host 127.0.0.1 --port 8765 --allowed-root work
```

浏览器打开：

```text
http://127.0.0.1:8765/
```

如果启用 token：

```powershell
python -m literary_engineering_workbench serve-api --host 127.0.0.1 --port 8765 --allowed-root work --api-token "your-token"
```

然后在控制台左侧 `API Token` 输入同一个 token。

## CLI 配置示例

```powershell
python -m literary_engineering_workbench config-set-profile `
  --name deepseek `
  --api-base "https://api.deepseek.com" `
  --model "deepseek-v4-flash" `
  --api-key-env "DEEPSEEK_API_KEY" `
  --temperature 0.4 `
  --max-tokens 4000 `
  --timeout 120 `
  --activate
```

## 与外部编排的关系

Dify、LangGraph 和未来前端都应调用同一套 API 和配置层。外部系统只传任务参数，不再重复携带模型 provider 的长期配置。需要临时实验时使用环境变量覆盖，不改全局配置。

## 验证

新增测试覆盖：

- `tests/test_model_config.py`
- `tests/test_api_server.py` 中的前端和配置接口测试

运行：

```powershell
python -m unittest discover -s tests -v
```
