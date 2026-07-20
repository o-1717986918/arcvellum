# Phase 13：API Token 鉴权

## 目标

给 `serve-api` 增加可选 API token 鉴权，让 Dify、前端或外部 Agent 调用工作流接口时具备最小安全边界。

## 使用方式

命令行传入：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench serve-api `
  --host 127.0.0.1 `
  --port 8765 `
  --allowed-root "C:\path\to\workspaces" `
  --api-token "your-token"
```

或使用环境变量：

```powershell
$env:LEW_API_TOKEN = "your-token"
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench serve-api --allowed-root "C:\path\to\workspaces"
```

## 客户端 Header

推荐：

```text
Authorization: Bearer your-token
```

兼容：

```text
X-LEW-API-Token: your-token
```

## 保护范围

配置 token 后，以下接口需要授权：

- `POST /workflow/run`
- `GET /workflow/runs/{run_id}`
- `GET /workflow/artifact`
- `POST /workflow/approve`

`GET /health` 保持无需授权，用于本地探活，但会返回：

```json
{"auth_required": true}
```

## 边界

- 不配置 token 时保持旧行为，方便本地离线开发。
- token 不写入 workflow state、log、approval、Dify DSL。
- token 不是公网部署的完整安全方案；公网部署仍应使用反向代理、TLS 和更严格的访问控制。
