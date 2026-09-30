# v2 文学提示词草稿与可观测评审台

## Packet A：按实际合同设计剩余文案

~~~yaml
module_change_packet:
  objective: "依据当前主创、取材、审读合同设计剩余 18 位文学提示词草稿"
  primary_module: "Engine prompting"
  public_entry: "public.prompting 的 scene.v2.* 与 project_agent.creator_persona.v2"
  variation_point: "作品主创人格、场景目的与委托内容"
  inputs: ["现有文学提示词", "SceneBrief", "CreativeIntentV1", "SceneMaterialRequestV3", "CreativeResult", "ReviewResult"]
  outputs: ["20 位完整草稿，其中 18 位首次设计", "阶段设计说明"]
  invariants: ["主创独写正文与 SceneDelta", "原正式 Gate 和写回保留", "每次挂载独立", "仅主创自由读档案", "新链路不自动启用"]
  allowed_dependencies: ["Engine public prompting/literary", "只读核对 Studio runtime adapter"]
  forbidden_dependencies: ["Provider 调用", "正式档案写入", "新工具能力", "旧全局自定义稿自动迁移"]
  tests: ["完整注册与合同验证", "冻结与旧交易兼容回归", "完整架构检查"]
  rollback_unit: "v2 文学提示词完整草稿"
  documentation: ["本记录", "审阅包设计说明"]
~~~

## 设计顺序

1. 固定权限、委托和候选交付合同：使结构与实际 parser、工具权限一致。
2. 作品人格、主创身份和开场信息：保留作品意图、连续性、上场正文与 SceneDelta 的职责。
3. 构思、委托、候选取舍及返修：主创自行作文学选择，首轮选定必用类别并完成实际调用。
4. 四类描写／叙述器：给出有视角、质感、空间和信息分寸的文学候选，与角色卡系统模板配合。
5. 独立审读：审查当前成稿与随任务提供的证据，不虚构未提供的档案检索或候选读取能力。

所有文案是待用户评审的草稿。去掉占位并不自动启用 v2；现有启用开关保持关闭，文学场景对照尚待进行。

## Packet B：全文观察、修改和通过

~~~yaml
module_change_packet:
  objective: "用户在当前独立填写前端查看新旧全文、修改及直接通过可用旧稿"
  primary_module: "Studio tools/prompt-design-desk"
  public_entry: "独立 HTML 与 arcvellum/prompt-design-submission 导出文件"
  variation_point: "源提示词版本与用户审阅决定"
  inputs: ["Engine public prompting 内置快照", "浏览器已有草稿", "v1/v2 导入稿"]
  outputs: ["26 位评审台", "含通过决定及旧稿来源的结构化导出"]
  invariants: ["保留原浏览器草稿", "不静默覆盖", "不直接改项目运行配置", "来源文字仅作为文本显示", "修改通过稿后需重新评审"]
  allowed_dependencies: ["只读 Engine public prompting", "本地浏览器存储与文件导出"]
  forbidden_dependencies: ["Provider", "项目档案 mutation", "浏览器联网依赖", "通用 API transport"]
  tests: ["新旧全文显示", "旧稿单选和组合通过", "修改取消通过", "导入迁移与来源追溯"]
  rollback_unit: "提示词评审台源码与静态输出"
  documentation: ["本记录", "tools/prompt-design-desk/README.md"]
~~~

前端保留 20 个 v2 位，并加入 6 个旧顶层复审位。人审通过记录用户对文案的选择，导出后由装载流程保持 v2 的权限和结构合同。此工具由用户明确要求作为独立简易页面，不新增 Studio 产品 API。

## Packet C：修复现有提示词目录的 v2 分类缺项

~~~yaml
module_change_packet:
  objective: "现有 Studio 提示词目录可继续加载，并准确定位新增 v2 文案"
  primary_module: "Studio application prompt_flow"
  public_entry: "PromptWorkbenchService.catalog 与 /prompts/catalog"
  variation_point: "注册提示词的创作流程位置"
  inputs: ["公开提示词层目录"]
  outputs: ["既有 flow_tree 中 v2 提示词的唯一位置"]
  invariants: ["不改变文案、运行启用或编辑权限", "未知场景提示词继续报错", "现有七个顶层分组保留"]
  allowed_dependencies: ["application prompt catalog", "Engine public prompting"]
  forbidden_dependencies: ["Runtime 启用配置", "通用兜底分组", "正式档案写入"]
  tests: ["test_prompt_workbench", "v2 全位的精确分组与唯一性"]
  rollback_unit: "v2 提示词目录分类修复"
  documentation: ["本记录"]
~~~

全量回归发现此前已登记的 v2 位没有 prompt_flow 分类，导致 /prompts/catalog 返回 400。修复采用明确的 v2 位映射，保留未知项报错，不弱化目录约束。

## 实施事实与验收记录（2026-10-01）

- 剩余 18 位由占位变为初稿，资产版本升为 2；角色系统模板与强风格化填卡任务保持原版本 2。本轮共 20 位完整 v2 初稿。
- 内置稿全文快照含 26 个评审位、63 个来源。旧稿单份／组合采用保持原文，记录每份版本与摘要；修改正文后取消通过，导入兼容 v1／v2，保留未涉及位。
- 导出合同为 arcvellum/prompt-design-submission/v2，通过文字快照与来源决定可追溯；旧 v1 的 ready 标记不自动升格为本次人审通过。
- 查询实际应用配置，scene_creator_v2.enabled 为 false。本轮未更改该配置、正式档案初始化、写回或 Gate。既有交易继续用冻结快照。
- Python 全量：1685 项，1 项跳过，0 失败；提示词工作台目录曾失败，经精确分类修复后全量复跑通过。
- 客户端：76 文件／247 项通过；初次并行矩阵有一项路由超时，定向与全量复跑均通过。client:build 成功。
- Pi Worker：13 文件／121 项通过，pi-worker:check 成功。
- 新页面 DOM 验证覆盖全文、旧稿单份及组合通过、撤销、编辑取消通过、长文本、旧存储与导入迁移、来源追溯、文本隔离。快照 Python 验证通过，HTML 与 26 份提示词的内容一致，ZIP 可读。
- 架构检查：16 个历史文件债务、76 个函数债务，0 新循环／违规依赖；模块图、提示词注册表、compileall 与 git diff --check 通过。
- doctor 的嵌入 Engine 为 ready，CLI --help 正常。

Engine 文案提交 ecc7e91；应用目录修复提交 4aecf4e。评审台为独立源码工具与静态产物。

### 尚未完成的验收

20 位文字仍是待用户评审的初稿，真实模型的冲突、日常、空间调度和设定揭示场景对照尚未运行。浏览器工具策略此前拒绝打开本地页面；AGENTS.md 要求的桌面／移动截图与实际布局重叠、横向溢出检查尚未完成，DOM 测试没有被记作视觉验收。
