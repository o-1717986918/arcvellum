# 提示词流程树与退役核查

2026-09-28。工作台只列可在现行创作或正式 Agent 路径中形成模型输入的提示词，以及这些路径使用的固定结构模板。用户已明确不需要旧作品提示模板兼容；旧兼容入口列入删除范围。正式任务的任务元数据注册表与提示词编辑目录分开处理。

## 逐项判定

| 条目 | 证据 | 处理 |
| --- | --- | --- |
| `scene.interaction.direction`、`scene.length.legacy` | 新场景交易改由主创按需请求素材，软字数交审读；两个层没有消费点。 | 从注册、随包资源和工作台移除。 |
| `scene.interaction.direction-repair.protocol`、`scene.ownership.repair.{action,dialogue}.protocol` | 只有注册声明；对应自动导演及归属修复提示已退役。 | 从注册与随包资源移除。 |
| `scene.sources`、`scene.repair.json` | 仅在注册声明出现；前者是动态事实资料，后者不在实际 JSON 修复路径中。 | 从提示词注册移除；场景资料继续由 SceneBrief/来源投影注入。 |
| `scene.interaction.direction.protocol` | 只由未调用的旧自动导演提示渲染函数使用。 | 删除旧渲染入口、注册及资源；保留规划 `opening_direction` 的解析合同。 |
| `scene.actor.interaction.protocol` | 当前按需角色请求仍通过 `scene_interaction` 渲染本层。 | 保留并更正用途说明，列入角色取材步骤。 |
| `legacy.template.*` 十项 | 旧 Engine 直连模板；其中 `scene_generation_{system,user}` 由旧项目 PromptPack 从项目文件读取。Studio 正式场景路径不消费。 | 从统一注册及工作台、旧项目提示编辑 API 移除；独立旧直连 Provider/CLI/HTTP 路径与其资源列入后续模块删除计划，不在本批顺带改写任务状态机。 |
| `formal.asset.*` 中 `deterministic-cli`、`human-approval-boundary` | 任务执行为确定性命令或人工关口，不调用模型。 | 保留 Engine `PromptAsset` 任务元数据，禁止作为可编辑模型提示展示或覆盖。现存覆盖文件不删除，但不会读取。 |
| 其余 `formal.asset.*`、活动文学层及固定协议 | 由正式 PromptProgram、场景交易、顾问、项目总编或 Worker 消费。 | 进入流程树；固定协议完整展示正文和占位结构，保持只读。 |

旧作品兼容入口删除计划：`prompt_workbench` 的旧项目模板分支先随本次清理移除；Engine `prompting.pack`、`literary.assets.workshop`、`director` 的直连模型路径、旧场景生成 Provider 及相应 CLI/HTTP 适配按 `docs/architecture/reviews/full-repository-cleanup-inventory-2026-09-27.md` 的 C21–C31、C37 另批退役。届时先核对当前公开入口和任务路由，相关旧模板资源随其最后消费点删除。

| 后续删除批次 | 代码落点与验收门槛 |
| --- | --- |
| 旧场景预演 | Studio `scene_performance_materials` / `perform_scene_interaction`、Engine 旧逐轮导演及 `public.literary` 导出；把人格续演、权限断言迁到按需取材测试，再删整条旧路径。 |
| 旧作品直连生成 | Engine `prompting.pack`、`literary.scene.generation_provider`、`projects.init` 复制的 `scene_generation_{system,user}.md`；先确认正式场景 TaskPackage 不读取这两个文件，再删模板及初始化输出。 |
| 旧资产与导演直连 | Engine `literary.assets.workshop` 的直连 Provider 分支、`director` 的模型调用、旧 HTTP adapter；逐个核对仍在用的确定性资产服务和项目总编工具，保留正式资产合同。 |
| 旧 CLI/公开别名 | `command_line/commands/legacy.py`、禁用命令列表与旧顶层转发；删之前迁移或撤销相应公开导出和专属测试，执行 CLI/route/打包合同矩阵。 |

## Module Change Packet A：Engine 活动层目录

```yaml
module_change_packet:
  objective: "活动提示词注册不再包含无消费、动态资料和旧作品模板"
  primary_module: "Engine prompting.layers"
  public_entry: "public.prompting.list_prompt_layer_specs / prompt_layer_spec"
  variation_point: "none"
  inputs: ["静态层 ID", "随包模板资源"]
  outputs: ["只含活动提示词及固定结构的 PromptLayerSpec"]
  invariants: ["当前角色按需取材协议仍可渲染", "人格初始化保留", "正式 PromptAsset 任务注册不变"]
  allowed_dependencies: ["Engine foundation.resources", "Engine public.prompting 调用方"]
  forbidden_dependencies: ["Studio 持久化", "Provider SDK"]
  tests: ["注册资源一一对应", "按需角色协议渲染", "旧层查询拒绝"]
  rollback_unit: "Engine 提示层注册与旧导演导出"
  documentation: ["本文件", "04-prompt-inventory.md"]
```

旧事务快照中多出的旧层键继续随缓存读取；新事务只冻结活动层。旧 ID 的有效覆盖文件不做自动迁移或删除。

## Module Change Packet B：Studio 工作台目录

```yaml
module_change_packet:
  objective: "仅暴露模型可消费的提示资产，按创作顺序返回完整流程树"
  primary_module: "Studio application.prompt_workbench"
  public_entry: "PromptWorkbenchService.catalog / resolve / snapshot"
  variation_point: "PromptAsset 的任务类型是否调用模型"
  inputs: ["活动 PromptLayerSpec", "PromptAsset metadata", "作用域与历史版本"]
  outputs: ["prompt-workbench/v2 层清单与 flow_tree", "有效正文与组装预览"]
  invariants: ["全局/作品版本优先级", "固定协议只读", "未知或非模型资产编辑拒绝", "已开始任务的提示快照不变"]
  allowed_dependencies: ["Engine public.prompting", "PromptLayerRepositoryPort"]
  forbidden_dependencies: ["直接改 Engine 任务注册表", "FastAPI Request", "Vue 组件"]
  tests: ["目录与树叶一一对应", "正式非模型资产拒绝编辑", "固定模板完整可见", "版本保存和回退"]
  rollback_unit: "Studio 目录及流程映射"
  documentation: ["本文件", "04-prompt-inventory.md"]
```

流程按“作品方向 → 来源/人物/文风 → 长篇规划 → 场景意图/取材/成稿/审读/修订/交接 → 审计 → 交付”排列；跨步骤的正式任务执行结构单列在末尾。每个叶子保留稳定层 ID，流程节点只负责导航，不承载另一套提示正文。

## Module Change Packet C：设置页流程树

```yaml
module_change_packet:
  objective: "用户可逐级展开创作流程，查看全部固定结构并编辑可写提示词"
  primary_module: "client/src/features/settings/PromptWorkbench.vue"
  public_entry: "settingsClient.promptCatalog / promptHistory / savePromptLayer / previewPromptLayers"
  variation_point: "流程节点的展开状态与搜索结果"
  inputs: ["catalog.flow_tree", "catalog.layers", "当前作品范围"]
  outputs: ["分级树", "只读结构正文", "可编辑正文及版本历史"]
  invariants: ["选择固定模板不能保存", "切换范围重载有效正文", "搜索不丢失树路径", "移动端无横向溢出"]
  allowed_dependencies: ["settings feature client", "Vue", "现有样式变量"]
  forbidden_dependencies: ["组件直接调用 generic transport", "前端自行推断任务权限"]
  tests: ["展开/筛选/编辑/只读 UI", "桌面与移动端截图和溢出检查"]
  rollback_unit: "前端设置页树形导航"
  documentation: ["本文件", "04-prompt-inventory.md"]
```

## 本批验收记录

- 活动目录：111 个静态层（22 可编辑、89 固定）与 48 个模型 Agent 正式资产；树的每个叶子与目录层 ID 一一对应，7 个主枝依次排列。
- Engine 原 59 项 PromptAsset 的任务元数据注册与验证保留；11 项确定性／人工任务资产从可编辑目录与编辑 API 中剥离。
- `tests.test_prompt_layers`、`tests.test_prompt_workbench`、场景交互及 PromptProgram 定向测试通过；完整 Python 测试 1667 项通过、1 项因 Windows 无法创建符号链接而跳过。
- Vue 测试 76 个文件、247 项通过；Pi Worker 11 个文件、114 项通过。浏览器桌面及 390px 手机截图验收通过，树与编辑器无水平溢出。
- 架构审计、模块图检查、Engine PromptAsset 注册校验通过。截图在 `build/creative-kernel/screenshots/prompt-workbench-{desktop,fixed-template,mobile,mobile-editor}.png`。
