# 修复说明：设置页模型目录从“2 → 1”回退

- 日期：2026-09-01
- 仓库：`arcvellum`
- 修复提交：`471b57a fix(settings): use OpenCode model control endpoints`
- 影响模块：`client/src/features/settings`
- 用户可见结果：连接 OpenCode Zen 后，“已连接服务”和“可用模型”不再被旧目录覆盖，页面会稳定显示 OpenCode 的真实连接状态。

## 1. 现象

在设置页通过“自定义兼容接口”连接 OpenCode Zen 后：

1. 连接刚成功时，顶部短暂显示为：
   - 已连接服务：`2`
   - 可用模型：`11`
2. 随后很快回退成：
   - 已连接服务：`1`
   - 可用模型：`2`

看起来像是 OpenCode Zen 连接被丢掉，但实际后端凭证和 OpenCode 连接并没有丢失。

## 2. 根因

问题不在后端连接，而在前端设置模块读取了错误边界。

连接 OpenCode Zen 时，`connectProvider()` 会先应用自定义接口返回的 OpenCode 目录，所以页面短暂显示正确的 `2 / 11`。但紧接着：

```ts
store.applyModelCatalog(result);
await store.loadModelCatalog();
```

而当时 `settingsClient.modelCatalog()` 却请求的是 Pi Worker 的目录：

```ts
"/model-connections/pi-worker/catalog"
```

两个目录的后端状态不同：

| 接口 | 已连接服务 | 可用模型 | 说明 |
| --- | ---: | ---: | --- |
| `GET /model-connections/opencode/catalog` | `2` | `11` | OpenCode 边界，能看到 `opencode` 和 `opencode-zen` |
| `GET /model-connections/pi-worker/catalog` | `1` | `2` | Pi Worker 边界，不是本次 OpenCode 连接的真实目录 |

因此流程变成：

```text
连接成功返回 OpenCode 目录
    ↓
UI 短暂显示 2 / 11
    ↓
loadModelCatalog() 请求 Pi Worker 目录
    ↓
UI 被旧边界数据覆盖为 1 / 2
```

同理，页面加载时 Bootstrap 快照先带出 OpenCode 目录，但设置页挂载后又会调用 `loadModelCatalog()` 重新拉取错误目录，所以新开页面也可能看到同样的回退。

## 3. 修复方案

将设置页的模型控制操作统一切换到 OpenCode 边界：

- 模型目录：`GET /model-connections/opencode/catalog`
- 连接已有 provider：`PUT /model-connections/opencode/credential`
- 自定义兼容接口：保持使用 `PUT /model-connections/opencode/custom`
- 选择模型：`PUT /model-connections/opencode/model`
- 断开连接：`DELETE /model-connections/opencode/credential/{provider_id}`

这样设置页的读取、连接、选择、断开都使用同一套模型边界，避免不同 runner 的目录互相覆盖。

## 4. 代码变更

### 4.1 主修复文件

文件：`client/src/features/settings/services/settingsClient.ts`

修改前：

```ts
modelCatalog: () =>
  transport.request<ModelCatalog & { ok: boolean }>(
    "/model-connections/pi-worker/catalog",
  ),

saveProviderCredential: (payload) =>
  transport.request<any>(
    "/model-connections/pi-worker/credential",
    { method: "PUT", body: JSON.stringify(payload) },
  ),

selectModel: (model, role) =>
  transport.request<any>(
    "/model-connections/pi-worker/model",
    { method: "PUT", body: JSON.stringify({ model, role }) },
  ),

disconnectProvider: (providerId) =>
  transport.request(
    `/model-connections/pi-worker/credential/${encodeURIComponent(providerId)}`,
    { method: "DELETE" },
  ),
```

修改后：

```ts
modelCatalog: () =>
  transport.request<ModelCatalog & { ok: boolean }>(
    "/model-connections/opencode/catalog",
  ),

saveProviderCredential: (payload) =>
  transport.request<any>(
    "/model-connections/opencode/credential",
    { method: "PUT", body: JSON.stringify(payload) },
  ),

selectModel: (model, role) =>
  transport.request<any>(
    "/model-connections/opencode/model",
    { method: "PUT", body: JSON.stringify({ model, role }) },
  ),

disconnectProvider: (providerId) =>
  transport.request(
    `/model-connections/opencode/credential/${encodeURIComponent(providerId)}`,
    { method: "DELETE" },
  ),
```

说明：`saveCustomProvider()` 原本已经使用 `/model-connections/opencode/custom`，这次保持不变。

### 4.2 测试同步

文件：`client/src/stores/app.spec.ts`

- 将“启动流不能覆盖设置页模型目录”的测试 mock 从 Pi Worker 目录改为 OpenCode 目录。

文件：`client/src/features/settings/SettingsView.spec.ts`

- 设置页测试改为等待 `/model-connections/opencode/catalog`。
- 模型选择测试改为断言调用 `/model-connections/opencode/model`。

文件：`client/src/testing/featureClients.contract.spec.ts`

- 新增 / 调整合同测试：`keeps settings model controls on the OpenCode boundary`。
- 明确验证以下调用都落在 OpenCode 边界：

```text
GET    /model-connections/opencode/catalog
PUT    /model-connections/opencode/credential
PUT    /model-connections/opencode/model
DELETE /model-connections/opencode/credential/deepseek
```

### 4.3 构建产物

文件：`desktop/dist/index.html`

- 前端构建后同步更新了产物 hash。
- 该文件不是本次行为修复的核心，只是 `npm run client:build` 的同步结果。

## 5. 验证

### 5.1 自动化验证

通过以下验证：

```bash
NODE_OPTIONS=--localstorage-file=/tmp/arcvellum-vitest/localstorage.json npm run client:test
npm run client:build
python scripts/architecture_audit.py
python scripts/generate_module_map.py --check
git diff --check
```

结果：

- 前端测试：`68` 个测试文件、`203` 个测试全部通过。
- 前端构建：通过。
- 架构审计：通过。
- 模块地图检查：通过。
- Git diff 检查：通过。

### 5.2 实际 UI 验证

修复后重新打开设置页，前端请求从：

```text
GET /api/model-connections/pi-worker/catalog
```

变为：

```text
GET /api/model-connections/opencode/catalog
```

页面显示：

```text
可用模型：11
已连接服务：2
正文模型：opencode/big-pickle
```

与后端 OpenCode 目录一致。

## 6. 为什么会出现两个 “OpenCode Zen”

后端目录里当时有两个 connected provider：

- `opencode`
  - 名称显示为 `OpenCode Zen`
  - 是 OpenCode 内置 / Starter 目录
  - 包含 6 个模型
- `opencode-zen`
  - 名称也显示为 `OpenCode Zen`
  - 是用户手动添加的自定义兼容接口
  - 包含 5 个模型

因此 `2 / 11` 是正确状态。界面回退到 `1 / 2` 只是设置页读取了 Pi Worker 目录，不是 OpenCode 凭证丢失。

## 7. 影响范围

- 修复的是前端设置模块的模型边界选择。
- 不改变 Engine 的文学路线、任务合同、Gate 或写回规则。
- 不引入新的模型 Provider 抽象、API key 存储、直接 HTTP LLM client 或隐藏 fallback。
- 不影响 Pi Worker 自身能力；只是设置页当前模型控制流程应使用 OpenCode 边界。

## 8. 后续使用建议

如果需要使用 OpenCode Zen 免费模型：

1. 打开设置页。
2. 点击“刷新连接”。
3. 在模型列表中选择带 `opencode/` 前缀的模型，例如：
   - `opencode/big-pickle`
   - `opencode/mimo-v2.5-free`
   - `opencode/nemotron-3-ultra-free`
4. 如果只想保留自定义兼容接口，可以断开内置的 `opencode` 连接；如果只想使用内置目录，可以断开 `opencode-zen` 自定义连接。

注意：列表中可能出现同名模型，但前缀不同。`opencode/...` 和 `opencode-zen/...` 是两个不同的 provider/model 组合。
