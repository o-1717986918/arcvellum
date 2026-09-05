# ArcVellum 任务协议 v2 与兼容层收敛实施方案

状态：执行中  
建立日期：2026-09-05  
适用仓库：`literary-engineering-studio-v099-work`  
当前分支：`feat/v099-modular-e2e`  
起始提交：`11a423f`  

## 1. 目标

本轮工作的目标是减轻 ArcVellum 在任务协议、运行时调用、历史命名和兼容 facade 上的技术债，同时保持已经验证的文学工程 Gate、旧项目可读性和 Pi Worker 正式路径不退化。

目标架构为：

```text
Route Domain
  -> Typed Task Blueprint
  -> Immutable TaskSpec v2
  -> EngineOperation Registry
  -> Studio Runtime
  -> Pi Worker
  -> TaskLifecycle Record
```

程序间调用最终使用结构化操作；字符串 CLI 只保留为人类可读投影和兼容入口。任务定义与任务运行状态分离，旧 schema 由集中式迁移层读取，新项目只写 ArcVellum v2 身份。

## 2. 当前事实

本方案基于 2026-09-05 的实际源码审查：

- `protocol/schemas/agent_task.v1.json` 同时容纳不可变任务定义和可变生命周期字段；
- `required_reading`、`source_paths`、`expected_outputs` 仍是无类型字符串列表；
- `command`、`submission_command`、`completion_command` 仍是字符串协议；
- Studio 的 `TaskPackage` 仍包装 `dict[str, Any]`，执行路径仍使用 `shlex.split`；
- Route blueprint 中存在大量重复命令和任务信封构造；
- `literary-engineering-workbench/*` 与 `platform-agent-*` 同时包含历史持久化身份、兼容别名和当前内部名称，不能全局替换；
- Engine 与 Studio 顶层仍有大量薄兼容 facade，测试也继续依赖部分旧入口；
- `compatibility_manifest.json` 仍声明 `release_line: 0.97` 和默认 `opencode`，与当前 v0.99.4/Pi Worker 路线不一致；
- 正式 parser 仍注册已经被 policy 禁用的 Dify、LangGraph、旧 Director 和 Provider 命令；
- 安装资源仍携带较多 Skill-host 历史文档；
- 当前架构审计无循环依赖、无 Studio 反向流入 Engine，但仍有 16 个超大 Python 文件和 104 个复杂函数债务。

已经实现并须保留的能力：

- 显式 `execution_policy`、`agent_role`、`human_gate`、runtime capability 和 output contract；
- expected-output-only 沙箱写回；
- context、RP、branch、composition、word budget、prose、review、promotion、state evolution 与 export Gate；
- Pi Worker 正式创作路径；
- v1 历史项目和已有任务包可继续打开；
- 路线审计、Prompt Registry 和端到端测试证据。

## 3. 约束

### 3.1 必须遵守

1. 每批修改前重新阅读本文件和相关模块边界。
2. 每批只解决一个协议层问题，并建立对应测试。
3. 每批完成后更新“执行记录”，执行定向测试并提交 Git。
4. v2 完成前，v1 的磁盘格式和现有 Route 行为保持不变。
5. 文学 Gate、任务顺序、角色分工和正式写回权限不得弱化。
6. 新抽象必须减少重复或隔离变化；不为单实现纯函数建立空接口。
7. 旧项目迁移必须可预览、可备份、幂等，且默认不破坏原文件。

### 3.2 禁止事项

- 禁止对 `literary-engineering-workbench`、`platform-agent` 或 `opencode` 做全局替换；
- 禁止一边修改协议，一边大规模删除兼容层；
- 禁止把另一套 workflow 状态机引入 Studio；
- 禁止让 Runtime 或 Agent 直接写正式项目文件；
- 禁止用单元测试替代连续场景或真实 Provider 验证；
- 禁止在兼容层退场前删除仍被外部项目或测试使用的 schema alias。

## 4. 目标合同

### 4.1 `TaskSpec`

`TaskSpec` 是不可变任务定义，包含：

- `identity`：task id、route、scene id、contract revision；
- `intent`：当前状态、任务类型、Prompt asset；
- `execution_contract`：policy、agent role、human gate、capabilities；
- `resources`：带 URI、用途、来源、必需性和摘要的资源引用；
- `operations`：prepare、submit、complete 的结构化操作；
- `outputs`：owner、kind、schema、writeback policy；
- `gates`：验证条件与禁止捷径；
- `extensions`：路由专用字段。

### 4.2 `EngineOperation`

```json
{
  "operation_id": "scene.compose.prepare",
  "arguments": {
    "project": "project://",
    "scene_id": "scene_0001"
  }
}
```

执行器只接受注册操作和已声明参数。CLI 命令文本由同一操作投影生成，不再作为 Studio 调 Engine 的权威协议。

### 4.3 `TaskResourceRef`

资源使用受控 URI：

- `project://...`：作品项目中的正式资源；
- `engine://...`：Engine 自带 schema、Prompt 和规范；
- `run://...`：当前运行的临时证据；
- `sandbox://...`：Agent 沙箱中的候选产物。

每个资源至少声明 `uri`、`purpose`、`required`；高风险输入增加 `sha256` 或 provenance。

### 4.4 `TaskLifecycle`

任务生命周期独立保存：

- issued/opened/submitted/blocked/completed 状态；
- 时间戳、run id、submission id；
- validation、completion evidence、失败分类；
- 指向不可变 `TaskSpec` fingerprint 的引用。

## 5. 分批实施

### TD-0：冻结兼容基线

目标：为后续重构建立不可争议的行为基线。

任务：

- 为七条正式 Route 各保存一份最小 v1 TaskPackage golden fixture；
- 覆盖旧项目加载、两场景衔接、Pi Worker、schema 迁移；
- 记录 facade 数量、旧命名引用和架构债务基线；
- 增加协议 round-trip 与 task fingerprint 回归测试。

验收：v1 产物字段、Gate 顺序和可执行行为均有测试保护。

### TD-1：引入内部强类型 Task IR

目标：先建立类型边界，不改变磁盘格式和用户行为。

任务：

- 新增 `TaskIdentity`、`TaskIntent`、`TaskResourceRef`、`EngineOperation`、`OutputContract`、`TaskLifecycle`、`TaskSpec`；
- 提供 `parse_task_document()` 与 `TaskSpec.to_v1_payload()`；
- 让 Studio `TaskPackage` 从类型对象投影公开属性，同时保留兼容 raw payload；
- 在 Route builder 边界逐步接入类型 IR；
- 增加不可变性、规范化、round-trip 和错误定位测试。

验收：现有 v1 JSON 字节语义等价，Runtime 与 API 行为不变。

### TD-2：移除程序间字符串命令执行

目标：消除引号、Shell 语法、Python 模块名和跨平台解析造成的阻断。

任务：

- 新建 Engine Operation Registry；
- 为 prepare/submit/complete 定义 operation id 和类型参数；
- CLI 与 Studio Runtime 调用同一 handler；
- TaskPackage 同时投影 operation 与兼容命令文本；
- Studio 正式任务停止依赖 `shlex`，未知 operation fail closed。

验收：正式任务全部通过结构化 operation 执行；Windows/macOS 参数行为一致；字符串命令仅供展示和 v1 兼容。

### TD-3：发布任务协议 v2

目标：形成严格、可迁移、可扩展的 ArcVellum 原生协议。

任务：

- 新增 `arcvellum/task/v2` schema；
- 核心字段 `additionalProperties: false`，路由扩展集中在 `extensions`；
- TaskSpec 与 TaskLifecycle 分离；
- 资源、操作、输出和 Gate 全部类型化；
- 保留 v1 reader 与 v1-to-v2 adapter。

验收：新任务写 v2，旧任务可读；迁移前后 fingerprint 与文学语义可核对。

### TD-4：Route Builder 收敛

目标：去除任务信封、提交、完成、输出合同的重复构造。

任务：

- 建立共享 `TaskBuilder`；
- Route blueprint 只表达文学语义、输入、输出和 Gate；
- 共用 submission/completion/output contract builder；
- 拆分 `routes/scene/blueprints.py`、`tasking/protocol.py`、`prompting/platform_tasks.py` 的职责热点。

验收：七条 Route 无行为差异；重复构造显著下降；大文件/复杂函数指标不增加。

### TD-5：兼容 facade 收敛

目标：缩小公共表面，保留明确的迁移窗口。

任务：

- 将内部和测试 import 迁到 canonical/public 路径；
- 架构审计禁止新增旧 facade 依赖；
- 删除无调用 facade；
- 外部仍可能使用的 alias 保留一个发布周期并发出弃用提示；
- 修正 compatibility manifest，分离当前默认值与历史兼容声明。

验收：兼容 facade 数量单调下降；旧项目仍可读取；Pi Worker 是当前默认 Runtime。

### TD-6：历史产品路径清理

目标：正式安装包只暴露当前产品能力。

任务：

- 从正式 parser 移除被 policy 禁用的 Dify、LangGraph、旧 Director 和旧 Provider 命令；
- 清理 Studio 正式任务中的 Skill-host 与旧 platform-agent 文案；
- 改为安装资源 allowlist；
- 历史设计文档留在源码仓库，不进入运行时包。

验收：正式 help 无死命令；安装资源中无无效操作指南；开发文档仍可追溯。

### TD-7：Schema 与项目迁移

目标：新身份统一，历史身份可控读取。

任务：

- 建立 `SchemaAliasRegistry`；
- 接受旧 `literary-engineering-workbench/*` 身份；
- 新项目写 ArcVellum v2 身份；
- 提供 preview/backup/apply 迁移命令；
- 迁移重复执行不产生额外变化。

验收：旧项目无损加载，新项目无旧品牌 schema，新旧项目可以共同测试。

### TD-8：OpenCode 独立退场

目标：在 Pi Worker 能力覆盖后移除历史 OpenCode 产品依赖，同时保留通用 Runtime SPI。

任务：

- 核验 creator/reviewer/advisor/style/archaeology 的 Pi 等价能力；
- 移除 UI、配置、facade、vendor 资源和专用测试；
- 必要时将 OpenCode adapter 移到独立可选包；
- 更新打包清单和第三方许可。

验收：普通安装不包含 OpenCode；Pi Worker 完成正式端到端闭环；Runtime SPI 可接其他执行器。

## 6. 测试矩阵

每批至少执行：

1. 新增模块定向单元测试；
2. `tests/test_task_contract_transport.py`；
3. `tests/test_task_contract_audit.py`；
4. `tests/test_task_completion_contract.py`；
5. `tests/test_task_preflight.py`；
6. `tests/test_task_lifecycle_facade.py`；
7. `scripts/architecture_audit.py --json`；
8. `git diff --check`。

阶段 Gate：

- TD-2 后执行两场景连续 fixture E2E；
- TD-4 后执行全量 Python 测试；
- TD-7 后执行旧项目迁移 E2E；
- TD-8 后执行真实 Pi Worker E2E、生产构建和安装包验证。

## 7. 完成交付标准

- 旧项目可打开、可迁移、可继续创作；
- 七条正式 Route 的 Gate、顺序和文学语义不变；
- Studio 与 Engine 的程序协议不再依赖 Shell 命令字符串；
- 新 TaskPackage 不携带 Skill-host 指令和旧 platform-agent 身份；
- 正式 parser 不再暴露禁用命令；
- 全量测试、两场景连续 E2E、Pi Worker E2E 和安装包构建通过；
- 架构债务只降不升，首轮目标降至不超过 12 个大文件、80 个复杂函数；
- release 文档清楚列出兼容范围、迁移方式和剩余限制。

## 8. 执行顺序与回滚点

严格顺序：`TD-0 -> TD-1 -> TD-2 -> TD-3 -> TD-4 -> TD-5 -> TD-6 -> TD-7 -> TD-8`。

每个 TD 单独提交。TD-0、TD-2、TD-4、TD-7 后建立明确回滚点。任何一批若导致文学 Gate、旧项目读取或 Pi Worker 路径回归，立即停止后续清理，先修复当前批次。

## 9. 执行记录

### 2026-09-05：路线建立

- [x] 审查 v1 schema、Studio TaskPackage、Engine bridge、task package enrichment；
- [x] 盘点旧命名、兼容 facade、禁用命令和打包资源风险；
- [x] 确认任务协议已具有显式 execution/output contract，避免重复建设；
- [x] 确定先做 TD-0、TD-1，再改程序执行协议；
- [x] TD-0 兼容基线；
- [x] TD-1 内部强类型 Task IR；
- [x] TD-2 结构化 Engine Operation。

### 2026-09-05：TD-0 完成

- [x] 为七条正式 Route 建立 v1 协议外壳 golden fixture；
- [x] 冻结 execution policy、Agent role、capability、human gate、output policy、completion receipt 与 fingerprint；
- [x] 验证可变 lifecycle 字段不会改变 TaskSpec fingerprint；
- [x] 使用 scripts/run_tests.ps1 强制源码 checkout，排除同级旧 editable install 污染；
- [x] 兼容面校验通过；
- [x] 架构审计通过，冻结基线为 16 个超大 Python 文件、104 个复杂函数、0 循环依赖、0 反向依赖。

验证：

- test_task_protocol_v1_golden.py：3 项通过；
- test_task_contract_transport.py：44 项通过；
- task audit/completion/preflight/lifecycle 定向测试：46 项通过；
- verify_compatibility_surface.py：通过；
- verify_checkout_import.py：通过。

### 2026-09-05：TD-1 完成

- [x] 新增不可变 `TaskSpec`、`TaskLifecycle`、`TaskDocument`、`TaskIdentity`、`TaskIntent`、`TaskResourceRef` 与 `EngineOperation`；
- [x] 将协议规范、可变生命周期、资源引用和执行操作在内存模型中分离；
- [x] 通过 `parse_task_document()` 读取 v1 字典，并保留无损 `to_v1_payload()` 回写；
- [x] Studio `TaskPackage` 通过 typed IR 投影正式属性，同时兼容现有测试中的 payload 生命周期更新；
- [x] 将 Studio 与 Engine 共用的执行契约类型集中到 Engine 公共 tasking 接口，删除重复推导实现；
- [x] 拆分模型、v1 适配和稳定导出面，避免引入新的大文件、复杂函数与循环依赖。

验证：

- test_task_spec.py：5 项通过；
- test_contracts.py：13 项通过；
- test_task_contract_transport.py：44 项通过；
- test_task_preflight.py：37 项通过；
- test_prompt_program_v3.py：37 项通过；
- scripts/architecture_audit.py：通过，债务基线未增加；
- git diff --check：通过。

### 2026-09-06：TD-2 完成

- [x] 新增 Engine Operation Registry，登记正式 prepare 操作与 task submit/complete 生命周期操作；
- [x] 新发 v1 TaskPackage 同时携带结构化 `operations` 和兼容显示命令；
- [x] Studio Worker 直接解析 typed operation 并将参数向量交给 Engine，不再用 `shlex` 反解析正式任务；
- [x] 旧 v1 command 只在 Engine 兼容适配器中升级，未知 operation、绕过参数和 Shell 控制符均 fail closed；
- [x] 自适应场景编排在追加 RP 深度或分支数量时同步更新 prepare operation；
- [x] Worker task context 投影当前 prepare operation，为 v2 去除程序命令字符串建立消费端基础；
- [x] 新增中文路径双场景跨进程 E2E，连续执行两个 context Operation 并验证独立上下文与 trace。

验证：

- 全量 Python：1353 项通过，1 项跳过；
- test_engine_operations.py：6 项通过；
- test_engine_operation_e2e.py：1 项通过；
- 七条 Route 的 v1 golden 指纹已按 `2026-09-05.36` 执行契约升级显式更新；
- scripts/architecture_audit.py：通过，未增加大文件、复杂函数、循环依赖或边界违规；
- git diff --check：通过。

### 2026-09-06：TD-3 完成

- [x] 新增严格的 `arcvellum/task/v2` schema，并将规范主体、可变生命周期与 Route 扩展分区；
- [x] 核心对象全面采用 `additionalProperties: false`，Route 私有字段只能进入 `spec.extensions`；
- [x] 资源、操作、预期输出、验证规则与生命周期均由 typed IR 表达；
- [x] 新建任务默认写入 v2，既有 v1 任务更新时保持原协议，不制造隐式迁移；
- [x] 保留 v1 与缺失 schema 的历史读取路径，未知协议版本 fail closed；
- [x] Studio、Engine、任务审计、活动观测与文学规划读取统一经过版本感知存储层；
- [x] 建立 v1-to-v2 适配器与语义 fingerprint，七条正式 Route 迁移前后语义一致；
- [x] 生命周期更新只改变 `lifecycle`，不改写不可变 `spec`。

验证：

- test_task_protocol_v2.py：5 项通过；
- 七条 Route 的 v1 fixture 全部完成 v2 无损投影与 fingerprint 核对；
- 全量 Python：1359 项通过，1 项跳过；
- verify_compatibility_surface.py：通过；
- agent_task.v2.json：JSON 解析通过；
- scripts/architecture_audit.py：通过，未增加大文件、复杂函数、循环依赖或边界违规；
- git diff --check：通过。

### 2026-09-06：TD-4 完成

- [x] 新增 Route-neutral `TaskBuilder` 与 `WordCountContract`，统一任务身份、路径归一化、字数、提交/完成命令和 blueprint 公共附件；
- [x] scene、longform、source-ingest、style、assets、review、export 七条正式 Route 全部改用共享构造器；
- [x] Route 模块只保留自身文学语义、专有上下文、系统字段、Gate 和审批边界；
- [x] repair target 摘要、agent source、core-managed output 与 system-owned field 投影由共享构造器统一处理；
- [x] `routes/scene/blueprints.py` 的文件系统证据推导拆到 `blueprint_support.py`，主状态表聚焦场景文学流程；
- [x] `tasking/protocol.py` 拆出协议值对象与 Markdown/JSON 渲染职责；
- [x] `prompting/platform_tasks.py` 拆出共享结果类型、路径、文风资料与资产标识工具；
- [x] 七条 Route 内重复的 task schema、issued lifecycle、submission/completion command 构造归零。

验证：

- test_task_builder.py：2 项通过；
- Route、TaskPackage、协议、文风、资产与审查定向测试：101 项通过；
- 全量 Python：1361 项通过，1 项跳过；
- verify_compatibility_surface.py：通过；
- scripts/architecture_audit.py：通过，保持 16 个既有大文件、104 个既有复杂函数、0 新增违规；
- git diff --check：通过。
