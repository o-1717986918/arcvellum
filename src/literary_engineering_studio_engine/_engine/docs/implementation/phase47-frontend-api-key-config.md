# Phase 47：前端显式 API Key 配置

本阶段让本地前端控制台可以显式设置模型 `api_key`。

## 背景

此前全局配置只保存 `api_key_env`，真实密钥必须写入环境变量。现在本地单机使用时，可以直接在前端填写 API Key，并保存到 `%USERPROFILE%\.lew\config.json` 或 `LEW_CONFIG_PATH` 指向的全局配置文件。

## 实现

- `frontend/index.html`
  - 全局模型配置表单新增 `API Key` 密码输入框。
- `frontend/app.js`
  - 刷新配置时不回显明文密钥。
  - 若已保存密钥，输入框显示“已保存，留空则不修改”。
  - 保存配置时只在用户填写 `API Key` 时更新密钥。
- `model_config.py`
  - `get_model_settings()` 读取优先级：
    1. `LEW_MODEL_API_KEY`
    2. profile 指定的 `api_key_env`
    3. profile 中保存的 `api_key`
  - `redacted_effective_config()` 不返回明文，只返回 `api_key_available` 和 profile 级 `api_key_set`。
- `api_server.py`
  - `/config` 保存配置时，若传入空 `api_key`，保留既有密钥。
  - 响应仍只返回脱敏后的有效配置。

## 安全边界

- API Key 保存到本机全局配置文件，不写入作品项目目录。
- `/config` 和前端预览不会回显明文。
- 若用户更偏好环境变量，可继续只设置 `api_key_env`。
- 若要清除已保存密钥，可直接编辑全局配置文件删除 profile 下的 `api_key` 字段。

## 测试

新增覆盖：

- 配置文件中的 `api_key` 可被 provider 读取。
- `redacted_effective_config()` 不泄露明文。
- 前端/API 保存明文后响应不泄露。
- 再次保存空 `api_key` 不覆盖既有密钥。
