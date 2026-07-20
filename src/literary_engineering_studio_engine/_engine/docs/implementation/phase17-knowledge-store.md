# Phase 17：知识库后端抽象

## 目标

在不引入第三方服务的前提下，把轻量记忆索引升级为可替换知识库协议，为后续 Qdrant、LlamaIndex、图谱和检索评测留出稳定接口。

## 新增命令

构建 JSON 后端：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench knowledge-build work/demo-work
```

搜索知识库：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench knowledge-search work/demo-work "林舟 档案" --kind characters --canon-status confirmed
```

## 文件协议

默认输出：

```text
memory/knowledge_store.json
```

每个 item 包含：

- `id`
- `source`
- `kind`
- `chunk_index`
- `char_count`
- `terms`
- `text`
- `metadata`

`metadata` 至少包含：

- `source`
- `kind`
- `canon_status`
- `scene_id`
- `chapter_id`
- `character_id`
- `authority`

## Canon 状态

- `confirmed`：`canon/`、`characters/`
- `planned`：`plot/`、`style/`、`scenes/`、项目根配置
- `candidate`：`drafts/`、`branches/`、`reviews/`、`prompts/`、`exports/`、`tests/`
- `working`：其他工作资料

## 边界

- `knowledge-build` 会复用并重建 `memory/index.json`，但不改变旧的 `index/search/context` 行为。
- 检索结果必须带来源和 canon 状态。
- 知识库检索不自动写回 canon。
- 当前后端为标准库 JSON；Qdrant/LlamaIndex 后续以同一接口接入。
