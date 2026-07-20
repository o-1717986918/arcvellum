# Phase 16：创作模型适配层

## 目标

建立可插拔的场景生成 provider 协议，让后续真实模型接入不破坏现有工程边界。

## 新增命令

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench generate-scene work/demo-work `
  --scene scenes/scene_0001.yaml `
  --rebuild-context `
  --provider dry-run
```

输出：

```text
drafts/candidates/{scene_id}-{provider}-{timestamp}.md
drafts/candidates/{scene_id}-{provider}-{timestamp}.json
```

## Provider

当前 provider：

- `dry-run`：无外部模型依赖，用于验证上下文注入、候选落盘、manifest 和审查链路。
- `http-chat`：通过 `LEW_MODEL_API_BASE`、`LEW_MODEL_NAME`、`LEW_MODEL_API_KEY` 调用 chat-completions 兼容 HTTP 接口。

后续 provider 应实现同一协议：

- 输入：项目根目录、场景文件、上下文包、上下文来源证明、provider 名称。
- 输出：候选正文 markdown 和 manifest JSON。
- 约束：只能写 `drafts/candidates/`，不能自动覆盖 `drafts/scenes/`，不能写 canon。

`v0.23.0` 起，每次生成还会写入 prompt manifest：

```text
drafts/candidates/{scene_id}-{provider}-{timestamp}.prompt.json
```

该文件记录 system/user messages、场景、上下文包、上下文来源证明、场景创作编排包和文风 profile 来源，但不记录 API key。

## 边界

- `generate-scene` 生成的是候选，不是正式草稿。
- 候选进入 `drafts/scenes/` 前必须经过人工选择、修订和 `review-scene`。
- 模型输出中的新增事实只能作为候选，必须等待人工确认。
- 无模型 key 时 dry-run 仍可完整测试工程链路。
