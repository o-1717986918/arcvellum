# 计量参数拖动与导入挂载

2026-10-05。依据 Stylometric Prompt Lab 的实际四主轴、九个次级目标、高频语法词和七个依存指标扩展 ArcVellum。

## Module Change Packet：导出参数导入

- objective: 计量台导出的画像、controls 或参数卡可在当前作品中恢复为可编译和挂载的参数。
- primary_module: application/style。
- public_entry: StylometryService.import_parameters、StylometryAnalysisPort.import_parameters。
- variation_point: 既有 Lab adapter 转译研究导出格式，仍使用固定计算包验证和编译。
- inputs: profile JSON、参数 JSON、可选原始依存树、标题与文风意图。
- outputs: 作品作用域的不可变导入画像、标准 creator controls 和原始来源记录。
- invariants: 原参数数值及单位、画像摘要、依存树绑定、正式文风与 Gate、场景冻结、角色隔离。
- allowed_dependencies: 既有 analysis/repository ports；adapter 可调用固定 Lab 包。
- forbidden_dependencies: 模型调用、前端重新计算统计、正式档案写入、凭空补造语料。
- tests: controls/card/宿主导出格式、指标映射、错误摘要/单位/范围、依存缺失、原档案保持、HTTP。
- rollback_unit: 应用合同、adapter、API 分别提交。
- documentation: 本文件、OpenAPI。

## Module Change Packet：拖动与实时挂载

### 导入 adapter 和 HTTP 迁移

- adapter owner/public entry: infrastructure 的 LabStylometryAnalysis.import_parameters；输入为应用 port 中的 JSON 字符串，输出为验证后的 LabDocument。
- implementation: 同一画像摘要下转译 controls/card 的原始目标，通过现有 creator compiler 校验；保存原始导出及摘要，失败保持未写入。
- API owner/public entry: api/routers/stylometry 的 POST /stylometry/import。
- HTTP contract: 有界 JSON 字符串与作品作用域，HTTP 层只调用上述 service，不参与指标映射。
- invariants/dependencies: 沿用固定 Lab、application ports 和既有 HTTP helper；正式档案、模型、Gate 保留。
- tests/rollback: 导出映射及应用端到端合同测试；API 新鲜作品导入；两个独立提交。
- documentation: 本文件、生成 OpenAPI。

- objective: 用区间滑块调整各测量指标，实时查看参数要求，保存并挂载，按用户选择自动挂载后续调整。
- primary_module: client/style-atelier。
- public_entry: stylometryClient 与计量文风工作台。
- variation_point: 指标目录驱动的滑块和 feature 内的预览/发布调度。
- inputs: 同源指标目录、标准 controls、用户拖动、导入文件、文风意图。
- outputs: 最新编译预览、命名版本、挂载状态、结构化导出。
- invariants: 数值和单位可追溯、旧交易保持冻结、手写片段保留、旧回复不覆盖新选择、自动挂载可停止、CAS 冲突明示。
- allowed_dependencies: Vue、feature client、已有文件读取工具。
- forbidden_dependencies: 组件直调 transport、在浏览器计算语料统计、改变正式文学审读。
- tests: 拖动/键盘/精确数值、全指标与上下界、迟到回复、手写片段、导入、自动挂载、真实 HTTP 与桌面/移动布局。
- rollback_unit: 前端控件、导入和发布调度作为同一 feature 的完整行为提交；后端合同、adapter 和 HTTP 独立提交。
- documentation: 本文件。

## 界面方向

沿用现有文风工坊的矿物灰、苔绿强调色及数据字体。参数按句段、词汇和句法分组，区间轨道同时展示目标范围和语料实测位置；右侧保留实际提示词和挂载入口。窄屏改为单列，滑块可用键盘操作。拖动范围是操作尺度，精确数值输入保留原计量域。

## 挂载约定

拖动后合并短时间的连续调整，并编译最新参数。手写片段与参数生成预览分别显示，由用户选择实际采用的片段。保存并挂载通过既有版本和挂载服务；自动挂载按明确开关启用。每次发布绑定确切参数、片段与作品，新场景使用新挂载，已开始的交易继续读取冻结版本。

## 已实现与使用

入口：作品的「文风成果」→「计量文风工作台」。

1. 导入 Lab 的 `profile.json` 与 `controls.json`／`style-parameter-card/v1` 参数卡；也支持 `stylometric-host/v1` 和本工作台的结构化导出。已选择对应画像时，可单独导入参数。
2. 四主轴、九项次级目标、高频语法词和七项依存目标均由 Lab 指标目录驱动。依存目标需要对应的原始参考树。分组展开后，可逐项启用，并拖动独立的上下界滑块。
3. 绿色区间展示目标，竖线展示语料实测。滑块支持键盘；精确输入保留导出中的原始小数。无上限的指标可扩大拖动范围，其测量单位保持原定义。
4. 连续调整合并约 350 ms 后，通过后端 Lab compiler 更新实际提示词。自由文风意图与参数共同编译。标题、意图、目标或依存内容改变时，迟到的预览回复会被忽略。
5. 「应用参数并挂载」保存不可变版本并挂载。勾选「拖动后自动挂载参数要求」后，后续稳定调整自动发布；取消勾选停止后续自动发布。可选补充／替换当前文风，以及加入主创／仅观测。
6. 手动改写提示词会保留实际片段、停止自动挂载，并在旁边展示最新参数预览；「采用最新参数预览」可切回参数生成内容。

导入以原始 JSON 保存画像、参数与参考树，保留摘要计算所需的 `0.0` 等数值记法。摘要不一致、单位或范围错误、缺少依存证据、同批存在不同画像／参数时明确报错。导入画像保存来源声明，不凭空生成原始语料。

正式档案初始化、场景写回、文学审读 Gate、主创专属挂载和既有场景冻结链路继续沿用。去 AI 味编辑仍由独立的实验开关控制。

## 验证记录

- ArcVellum 标准 `.venv`：计量 service、import、jobs、API 共 14 项通过；主创动态挂载、旧场景冻结、仅观测及取材 Agent 隔离 4 项通过。
- 前端：84 个文件、270 项测试通过；增加滑块精度与区间交叉、导出原始数值记法、导入冲突、预览竞态、手写片段和自动发布停止测试。
- Playwright 真实 HTTP 两条流程通过：语料统计→手写→保存→挂载→测量→导出；Lab 目标导入→实际鼠标拖动→自动挂载→API 核对精确目标→停止自动发布。
- 桌面 1440×900、手机 390×844 的滑块和挂载界面已截图并人工检查，卡片无重叠、页面无横向溢出。验收等待启动画面退场与移动导航收起后进行指针操作及截图。
- `client:build` 通过，155 个前端资源同步桌面；Pi worker check 通过，121 项测试通过。
- Architecture audit：16 个既有文件债务、76 个既有函数债务，循环及 Studio 对 Engine internal 依赖为 0；module map、compileall、59 个提示词资产／73 个任务绑定校验通过。

浏览器证据：`build/orrery-visual/results/stylometry-workbench-impor-577e7-ly-mount-exact-requirements/` 下的 `stylometry-sliders-desktop.png`、`stylometry-sliders-mobile.png` 和 `stylometry-mount-mobile.png`。运行日志保存在 `work/dev-runtime/stylometry-sliders-*.log`。

此轮验证了参数导入、要求编译、保存挂载及统计合同；具体文学效果仍需用正文测量和实际文学审读评估。
