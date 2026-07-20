# Phase 22：场景创作编排器

## 状态

已在 `v0.22.0` 实现 `compose-scene`。

## 目标

把上下文包、上下文来源证明、人物 BDI / `background_story`、多分支剧情推演和场景 YAML 组合成一个可直接指导正文生成的创作编排包。它解决的是“已经知道场景要发生什么，但还不知道怎样写得稳、怎样让人物动机进入文字”的中间层问题。

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench compose-scene work/demo-work --scene scenes/scene_0001.yaml --rebuild-context
```

可选参数：

- `--context`：复用已有上下文包；正式链路中必须存在相邻 context trace。
- `--query`：补充检索查询。
- `--branch-manifest`：指定 `branch_manifest.json`。
- `--branch-selection`：指定 `branch_selection.md`。
- `--out`：指定 Markdown 输出。
- `--json-out`：指定 JSON 输出。
- `--agent-tasks`：生成 `drafts/compositions/{scene_id}_composition.agent_tasks.md`，不污染 composition Markdown / JSON。

## 输入

- `scenes/{scene_id}.yaml`
- `memory/context_packets/{scene_id}.md`
- `memory/context_packets/{scene_id}.trace.json`
- `characters/*.yaml`
- `branches/{scene_id}/branch_manifest.json`
- `branches/{scene_id}/branch_selection.md`

正式链路中，如果缺少分支 manifest，`compose-scene` 会阻塞，而不是退回保守模式。先运行 `simulate-scene --agent` 与 `branch-simulate --agent`，再由平台 Agent 在 `branch_selection.md` 中记录正式选择。只有内部实验可以显式使用 `--allow-missing-branch` 生成 fallback composition，该产物不能进入正式 `generate-scene`、state writeback 或发布链路。

如果已经存在 `branch_manifest.json`，正式流程必须先由平台 agent 或用户在 `branch_selection.md` 中写入 `decision: selected` 和 `selected_branch`。默认不会再把 `recommended_branch` 自动带入 composition；`--allow-recommended-branch` 只用于内部实验，生成的 composition 会标记为 `selection_source: recommended`，不能直接进入 `generate-scene`。

## 输出

- `drafts/compositions/{scene_id}_composition.md`
- `drafts/compositions/{scene_id}_composition.json`
- `drafts/compositions/{scene_id}_composition.agent_tasks.md`（可选）

Markdown 面向作者和 agent 阅读，JSON 面向后续 LangGraph / Dify / provider 编排。
由于 composition Markdown 可能进入 `generate-scene` prompt pack，`[AGENT_TASK: ...]` 只写入 sidecar，不写入 composition Markdown。

## 产物结构

JSON 包含：

- `scene_facts`：场景目标、冲突、参与者、伏笔和下一场景输入。
- `characters`：参与人物的 BDI、道德边界、语言习惯和背景故事元数据。
- `branch`：选用分支、来源、行动链、评分和写回候选。
- `beats`：五段式场景节拍。
- `subtext_map`：人物表层行动、隐性压力、背景故事的间接影响方式。
- `dialogue_intents`：每个角色的对白目标、回避内容和表达禁区。
- `sensory_palette`：地点锚点、意象、声音、触感、光线和风格过滤。
- `prose_seed`：可改写正文种子，不是正稿。
- `revision_targets`：进入真实正文生成前的改写目标。
- `guardrails`：canon、人物和发布边界。

## 背景故事规则

`background_story` 只能影响：

- 角色做出或回避某个选择。
- 对危险、关系、物件或旧线索的误判。
- 话语节奏、停顿、避词、沉默。
- 行动中的克制、拖延或过度确认。

它不能在正稿中变成解释性设定段落。`compose-scene` 可以在内部编排文档里显式记录背景影响，但正文种子和后续 provider 都必须遵守“隐性驱动”规则。

## 工作流位置

推荐顺序：

1. `context`
2. `simulate-scene`
3. `branch-simulate`
4. `compose-scene`
5. `generate-scene` 或人工扩写
6. `draft-scene`
7. `review-scene`
8. `chapter-workspace`
9. `export-package`
10. `publish-chapter`

`run-workflow --mode scene-loop` 已接入 `branch_simulation` 和 `scene_composition` 节点，会在同一次运行中留下分支 manifest、人工选择记录和场景创作编排包。

## 验收

- 能读取 branch manifest 并采用推荐分支或人工选择分支。
- 能在缺少 branch manifest 时生成 fallback 编排。
- 输出包含节拍、潜台词、对白意图、感官意象、正文种子和写回候选。
- 人物背景故事进入隐性行为因果，不直接变成正稿解释。
- 单元测试覆盖 manifest 模式、fallback 模式和 CLI 入口。
