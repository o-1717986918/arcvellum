# 计量文风接入与运行修复

2026-10-05。用户授权实施。保留既有未提交规划改动；去 AI 味保持独立、默认关闭的实验。

## Module Change Packet：自然交付与恢复

- objective: 主创委托来自自然原文，交付失败可恢复，新增回归进入标准测试。
- primary_module: Studio runtimes。
- public_entry: PiSceneTransactionRuntime / NaturalOutputProcessor。
- variation_point: 逐字来源校验与自然回答尝试记录。
- inputs: 冻结资料、自然回答、已有候选。
- outputs: 已校验 DTO、原文与失败记录。
- invariants: 文学正文主创独写、实际必用调用、旧交易、档案冻结、Gate 与正式写回。
- allowed_dependencies: Engine public、现有 gateway、Studio 文件缓存。
- forbidden_dependencies: 新模型客户端、修改 Canon、伪造素材或 Gate。
- tests: 委托／文风改写拒绝、有效来源、失败后新回答、角色中断恢复、标准收集。
- rollback_unit: runtime 修复独立提交；测试收集单独提交。
- documentation: 本文件。
## Module Change Packet：宿主文风用例合同

- objective: 用户可统计语料、保存参数版本并选择主创实验挂载。
- primary_module: application/style。
- public_entry: StylometryService、版本化文档 DTO、分析与存储 ports。
- variation_point: 独立 lab 计算后端及 Studio data root 存储。
- inputs: 作品、上传文本、画像、参数、可选依存原树。
- outputs: 分析结果、不可变版本、挂载快照与逐项测量。
- invariants: 正式文风版本和 Gate、默认未挂载、角色上下文、实验开关相互独立。
- allowed_dependencies: 标准库、application ports、作品标识。
- forbidden_dependencies: Lab 内部计算、FastAPI、Provider、正式作品写入。
- tests: 用例、版本切换、过期挂载、源哈希、缺测与恢复。
- rollback_unit: application 合同与用例独立提交。
- documentation: 本文件。

## Module Change Packet：固定计算包与 adapter

- objective: 安装后的宿主可脱离研究 checkout 运行统计。
- primary_module: infrastructure。
- public_entry: StylometryAnalysisPort / StylometryRepositoryPort。
- variation_point: 固定 wheel 的分析模块与文件 adapter。
- inputs: typed sources 和原始 JSON 合同。
- outputs: typed versioned documents。
- invariants: Lab 原始计算与版本／文件摘要；无模型客户端。
- allowed_dependencies: lab 安装包、标准库、application DTO。
- forbidden_dependencies: Engine internal、正式项目写回。
- tests: 计算一致、来源封装与 wheel 脱离目录运行。
- rollback_unit: 固定计算包与 adapter 独立提交。
- documentation: 本文件、third_party provenance。

## 实施记录

## Module Change Packet：计量文风前端

- objective: 用户能直接统计、调参、修改片段并选择主创挂载，看到实际版本与缺测。
- primary_module: client/style-atelier。
- public_entry: 文风工坊中的计量文风工作台。
- variation_point: feature-owned stylometry client。
- inputs: 当前作品、导入语料或正式档案、指标范围、用户片段。
- outputs: 版本、挂载、结构化导出及测量展示。
- invariants: 原正式文风流程、当前作品隔离、用户自由编辑、实验状态可见。
- allowed_dependencies: feature client、现有 archive read client、Vue。
- forbidden_dependencies: 组件直调通用 transport、前端重新计算统计。
- tests: feature contract、实际统计/调参/挂载/卸载/导出、桌面和移动布局。
- rollback_unit: feature types/client 与界面分批。
- documentation: 本文件。

## Module Change Packet：长统计任务与缓存

- objective: 长统计可离页继续，显示阶段、取消并恢复；计算按来源及方法复用。
- primary_module: application/style。
- public_entry: StylometryJobsService / typed job repository port。
- variation_point: 后台 executor、原有统计 port、文件 job adapter。
- inputs: 上传文本与来源声明。
- outputs: 持久任务、阶段、分析结果或原因。
- invariants: 取消后计算段完成即停止交付；统计不自动挂载；恢复使用保存的输入。
- allowed_dependencies: application DTO、标准 executor；adapter 拥有文件与缓存。
- forbidden_dependencies: 新模型或 Provider、正式文学状态修改。
- tests: 成功、取消、失败恢复、重启中断、缓存一致。
- rollback_unit: 长分析合同、adapter 与 API 独立提交。
- documentation: 本文件。

## Module Change Packet：计量工作台 HTTP

- objective: 前端可经宿主接口统计、编辑、保存及挂载计量文风。
- primary_module: api。
- public_entry: /stylometry 版本化 endpoints。
- variation_point: application service 注入。
- inputs: 作品、文本来源、参数 JSON、文风片段、挂载修订。
- outputs: 画像、版本、编译结果、测量与挂载快照。
- invariants: API 只转译 HTTP；不直接计算或写正式内容。
- allowed_dependencies: application service、Pydantic、HTTP helpers。
- forbidden_dependencies: Lab 内部、Provider、Engine internal。
- tests: fresh project health/projects/runtime/read model/SSE、统计至卸载、错误参数。
- rollback_unit: API 与生成合同提交。
- documentation: 本文件、OpenAPI。

## Module Change Packet：主创动态消费

- objective: 项目所选计量文风经现有主创接口消费，场景交易冻结并记录输出统计。
- primary_module: runtimes。
- public_entry: PiSceneTransactionRuntime、既有 lean runtime composition。
- variation_point: typed snapshot provider 与只读 measurement provider。
- inputs: 不可变版本快照、主创交付正文。
- outputs: 文风快照、源摘要及测量文件。
- invariants: 旧交易保持关闭；五类取材和独立角色聊天沿用原委托；文风与去 AI 味独立；Gate 与写回。
- allowed_dependencies: application DTO、现有 gateway、已注入 ports。
- forbidden_dependencies: Lab 计算、模型客户端、正式档案写入。
- tests: 新旧交易、冻结与版本切换、文风组合、主创独占、输出统计。
- rollback_unit: composition 和 runtime adapter 提交。
- documentation: 本文件。

自然委托／文风逐字校验及来源范围完成；失败原文与原因保留，最多两次即时修正，外部重试使用新反馈继续；有效素材和角色卡保持复用。角色恢复测试已迁移到自然交付，移除没有真实来源的 DIRECTOR_ONLY 占位断言。31 项运行时测试通过；架构债务维持 16 文件／76 函数／0 cycle，diff 检查通过。

## Module Change Packet：标准测试收集

- objective: 新运行时合同进入既有本地命令与 CI。
- primary_module: tests。
- public_entry: unittest discover -s tests。
- variation_point: none。
- inputs: runtimes 测试包。
- outputs: 完整测试收集。
- invariants: 既有用例与历史交易兼容覆盖。
- allowed_dependencies: unittest。
- forbidden_dependencies: 生产设置与秘密。
- tests: 标准发现 1727 项，其中 runtimes 31 项；显式 31 项通过。
- rollback_unit: 测试包入口独立提交。
- documentation: 本文件。

## 使用入口

开发版的「文风工作台」中打开「计量文风工作台」。选择作品后：

1. 导入 TXT／Markdown、粘贴文本，或选择作品档案；核对作品编号与训练／留出用途。
2. 一篇可直接统计；多篇通过后台任务建立画像，保存来源声明与文本摘要。任务可取消、恢复，离页后继续计算。
3. 修改指标启用项与上下界，填写自由文风意图，编译片段。实际片段可直接编辑并保存命名版本。
4. 选择「补充当前文风／替换当前文风内容」及「加入主创文风／仅观测」，查看组合预览后挂载。
5. 粘贴正文测量目标、实测与距离；结构化导出保留画像、参数、编译结果、自由修改、保存版本和挂载记录。

作者自由文风指示持续保留。版本切换用于后续新场景；已开始的场景交易冻结原版本。正在执行的交易中途换版和自动多轮计量改稿列入后续版本合同。

## 数据与加载

- Lab 固定为 0.9.1（提交 `28e547511410ed9a18b9e830b07aaf744aff525a`）；10 个模块的计算依赖闭包以普通 Python 包随宿主分发，固定 wheel 和逐文件摘要留档于 `third_party/stylometric-prompt-lab/`。
- 固定 Lab wheel SHA-256：`e2e1f62885031225453e31e071aafb59ff3bfd57160189dc027028d7f7effbf0`。分发模块统一 LF，provenance 同时保存 wheel 原始字节摘要与分发摘要；旧 0.9.0 wheel 和 provenance 留档。
- 画像、原始语料、不可变版本、任务、缓存和作品挂载保存在 Studio data root。正式作品档案、原档案初始化和 SceneDelta 写回继续走原服务。
- `creator_stylometry_snapshot.json` 按交易保存最终片段、版本、组合方式和摘要；主创自然系统通过既有唯一文风接口消费。
- 五类取材仍按主创逐次委托加载；独立角色对话使用自己的上下文。
- 主创交付正文的测量位于交易 `stylometry/<正文摘要>.json`，与冻结版本绑定。统计失败保留原因，文学 Gate 沿用 Engine。
- 去 AI 味局部编辑继续是独立、默认关闭的实验开关。采用编辑后的正文进入原独立审读链；原稿、局部提案和 SceneDelta 审计继续保存。

## 真实模型暴露的恢复问题

### 补充变更合同：逐轮审读连续性

- owner/public entry: runtimes 的 NaturalCreatorMixin._review_natural。
- objective: 审读收到上轮原判断、证据与修订要求，持续核对同一场文学经验。
- input/output: 本交易已接受的审读缓存与修订结果 → 当前审读交接资料。
- invariants: 排除当前正文的审读缓存；保留原决定和证据；主创和正式 Gate 继续判断成稿。
- tests: 当前交易的真实 review 调用看到上一轮完整判断、修订次数及来源摘要。
- rollback: runtime 交接 helper 和回归独立提交。

### 补充变更合同：取材请求技术整理校验

- owner/public entry: runtimes 的 NaturalOutputProcessor。
- objective: 角色知识分区、角色卡和取材字段经 Engine public 合同验证后交主创记忆与调用。
- inputs/outputs: 当轮主创原文和参与者 → 已验证委托，或同源技术重试。
- invariants: 原文、主创知识分类与实际调用保留；首次必用计划在委托通过后冻结。
- tests: 原文已有分区但整理字段缺失时同源恢复；持续缺失时保留失败供主创修正。
- archive preflight: 在保存主创记忆及必用计划前读取并校验整组档案选择；不可读取或预算错误作为当轮交付反馈，正式调用仍按原规则冻结。
- rollback: 整理合同说明、runtime 校验和测试独立提交。

### 补充变更合同：自然交付阶段与测量归属

- owning modules: runtimes 的 NaturalOutputProcessor；style-atelier 的 useStylometry。
- objective: 整理器依据本次原文选择待调用邀请或完成正文；前端测量归属原有正文与保存版本。
- inputs/outputs: 保存的文学原文 → 同源技术重试；版本／正文切换 → 清空旧测量。
- invariants: 不自动删除委托、不改写正文；原始与整理失败均留档；实际必用调用和 Gate 保留。
- tests: 混合技术结果同源恢复、两次失败保留；版本／正文切换和迟到测量；前端全量与 runtime 专项。
- rollback: runtime 和前端两次独立提交。

自然创作文本保持原文；后置技术整理补齐以下兼容：

- 识别整理器返回的 `operation/task_contract` 容器，并继续完整来源校验。
- 只对唯一对应的 Markdown 引用标记差异恢复原始逐字委托，记录原文范围；文字变化仍交回修正。
- 角色委托标题中的明确人名可对应当前 SceneBrief 参与者，记录原标题和对应结果。
- 委托与记忆完整校验后保存首轮必用类别；同一类别计划的理由重述沿用首次记录。后续主创收到冻结计划。
- 失败反馈只交给主创；整理器收到本次原文。技术整理失败先按具体原因在同一原文上重试，两次整理结果与失败均留档。
- 完成正文附带旧委托回顾时，整理器依据当轮交付意图选择阶段；混合正文与待调用请求的技术结果先同源重试。系统维持成稿前的实际必用调用校验。
- Lab 的研究测试显式加载自己的工具目录，消除测试收集顺序依赖。
- 事件素材缺少来源说明时，以原文摘要标记为 `proposed` 并记录整理器原分类；文学文字保持逐字，确认仍由主创取舍与正式 Gate 完成。
- 次级测量直接按九个标量键读取，修复原来误用画像摘要路径导致的九项缺测；新增逐项真实测量回归。
- Windows 临时语料文件显式使用原始换行，修复 CRLF 被二次转换；宿主与 Lab 原生 CRLF 文件统计相同。
- 正文、画像或保存版本改变时清空旧测量，迟到的旧正文结果不写入当前视图及导出。
- 新审读继续收到上一轮原决定、证据和修订要求，并显示已经完成的审读／修订次数及原稿摘要；当前正文的缓存不会冒充上一轮资料。
- 主创委托的角色知识分类、角色卡及其他字段在技术整理阶段经 Engine public 合同校验，同源重试优先于文学重写。原文明确的 `character_known/creator_reference` 分区可转为标准分类；未明确的分类交回主创。
- 整组档案选择在保存主创记忆及首轮必用计划前预检；缺失条目和超预算选择转为可恢复的当轮反馈。正式取材调用仍按原机制冻结内容。

## 验证记录

### 补充变更合同：Windows sidecar 关闭

- owner/public entry: runtime 的 ProcessManager.stop。
- objective: 关闭受管理的 Python 启动器及其子进程，释放日志文件。
- inputs/outputs: 当前存活的受管理 PID → 已退出进程树和关闭记录。
- invariants: 只关闭当前 manager 持有的进程；POSIX 关闭合同和正式文学路线保留；关闭失败明示。
- allowed dependencies: subprocess、操作系统自带 taskkill；不引入模型或项目写入。
- evidence: Windows venv Python 在关闭父进程后仍占用日志，三个不同启动等待时间均复现。
- tests: 子进程已启动的真实 Windows sidecar 关闭及日志重命名；生命周期测试、全量回归和架构棘轮。
- rollback: 进程管理器及独立回归提交。

- ArcVellum 最终全量 Python：1,754 项，1 项跳过，347.959 秒通过；运行时专项 48 项通过，Windows 子进程关闭回归进入标准发现。
- 前端：全量 259 项通过；计量工作台组件专项 5 项通过，生产构建和桌面资源同步通过。
- Pi Worker：13 文件、121 项通过。架构审计维持 16 文件／76 函数债务、0 cycle、0 Studio 内部 Engine 导入。
- Lab：196 项通过，2 项可选能力测试跳过。
- 真实 HTTP 页面：完整统计至卸载链路通过，桌面及 390 px 移动截图，工作台横向溢出检查通过。
- 当前开发版 API 确认加载 Lab 0.9.1；最新实际页面验收耗时 9.8 秒，无页面脚本错误，导出及卸载成功。
- 固定宿主 0.99.12 wheel 已安装到独立目录，以 Python `-I -S` 运行：Lab 0.9.1 的 10 个模块摘要一致，jieba 字典存在，实际统计／画像／编译通过。当前验证覆盖 Python 包，尚未新建整套桌面安装器。
- 最后一次验收 wheel SHA-256：`73c1e4bf1d682dcdae94fd53e2287c2ecfa11e984cc15e3f791964a63b501fb6`，产物位于 `build/stylometry-acceptance/wheels-release-check/`；独立安装中的进程管理器与源文件摘要一致。
- Windows Python 启动器的子进程占用日志问题已修复；真实子进程初始化后关闭及日志释放回归、原有四项生命周期测试通过。
- 连续场景真实模型验收记录在隔离验收目录；最终结果以实际交易、审读与正式写回为准。

## 连续场景真实验收状态

- `scene_0001`：四类实际取材、候选取舍、自然交付、正文测量、修订、独立审读和正式写回完成。交易 `scene-tx-912a0dd7c54d4887bb5f2817def0f3f3` 已为 `committed`，共 10 次修订；记录展示了计量取向与文学判断发生冲突时的实际成本。
- 第一场冻结版本 `a130f59e-7920-41d1-b633-baad60751bfb`，使用 append；旧快照持续保留。
- `scene_0002`：已冻结新版本 `8a8c3366-d3e6-4164-b560-eba907380672`，使用 replace，已收到第一场正文、SceneDelta 与连续性记录。交易 `scene-tx-f2e3c1d6abb84221ba41b3f71af7c734` 仍在 creating，尚未正式写回。
- 第二场先暴露角色分区整理问题，上述技术校验与同源重试已修复并通过回归；后续真实续跑被配置的模型服务 HTTP 402 `Insufficient Balance` 中断。当前记录保留在 `build/stylometry-acceptance/runtime-1791137118/acceptance.json`，可以从原交易继续。
- A—E 实现完成，F 的独立打包与第一场真实链路通过；两场连续正式写回的验收尚未完成。当前配置模型保持原选择，v2 产品默认开关继续关闭。

LTP 标注与 R 在宿主尚未配置；已保存依存原树可导入核验。指标联合命中和文学提升仍属实验观察。

