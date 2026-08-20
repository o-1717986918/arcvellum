# ArcVellum Agent 面向接口开发标准

> 状态：v0.99 M7 强制开发标准
> 目标：让一个不了解全仓库的代码 Agent，在不扩大读取面、不复制业务逻辑、不削弱文学 Gate 的前提下，完成单模块高质量交付。

## 1. 总原则

ArcVellum 不是“找到文件就修改”的项目。正式开发循环是：

```text
需求 -> 唯一主模块 -> 稳定接口/合同 -> 最小实现面 -> 模块测试
     -> 架构棘轮 -> 必要的跨模块/E2E -> 文档事实 -> 独立 Git 提交
```

Agent 可以自由设计模块内部实现，但不能自行改变模块所有权、正式文学真相、TaskPackage 生命周期或 Gate 语义。目录可见不等于路径可直接写，Python 可 import 不等于稳定 API。

## 2. 开始前必须生成 Module Change Packet

每批修改前，把以下内容写入执行日志、Issue 或 PR 描述。无法填写时先读[模块目录](module-catalog.md)，不要全仓漫游。

```yaml
module_change_packet:
  objective: "用户可观察的单一结果"
  primary_module: "唯一拥有此行为的模块"
  public_entry: "调用方应使用的函数、Protocol、DTO 或 feature client"
  variation_point: "需要隔离的真实变化点；没有则写 none"
  inputs: ["稳定输入 DTO/文件合同"]
  outputs: ["稳定输出 DTO/事件/产物"]
  invariants: ["不可改变的 Gate、权限、顺序、兼容语义"]
  allowed_dependencies: ["本批允许读取/调用的模块"]
  forbidden_dependencies: ["不得 import、不得写入或不得拥有的职责"]
  tests: ["定向合同测试", "必要集成/E2E"]
  rollback_unit: "本批独立 Git 提交"
  documentation: ["需要同步的事实文档"]
```

一个批次只有一个 `primary_module`。确有跨模块合同变更时，先提交合同，再分别迁移 adapter 和调用方；不要一批同时重写 Engine、Runtime、API 和 Vue。

## 3. 最小上下文读取协议

Agent 按下列顺序读取，不凭文件名猜架构：

1. 本标准；
2. [module-catalog.md](module-catalog.md) 中对应模块的一行；
3. 对应稳定入口或 Protocol；
4. 该接口的合同测试和一个真实 adapter；
5. 只有实现受阻时，才读取拥有该行为的内部模块；
6. 只有合同确需改变时，才读取调用方。

默认不读取：整个 `docs/roadmap/`、全部 routes、全部前端、完整工作项目、模型 transcript、无关历史兼容 facade。正式文学 Agent 的运行资料仍由 TaskPackage/Context Broker 决定，本标准不能代替创作任务包。

## 4. 需求定位规则

| 需求信号 | 主模块 | 不应先改 |
|---|---|---|
| 新/改文学 Gate、Canon、正文、规划、文风、审查 | Engine `literary/` 或对应 `routes/` | Studio Worker、API |
| 任务顺序、TaskPackage、completion、route audit | Engine `tasking/`/`workflow/`/`routes/` | 前端按钮、Runtime adapter |
| Agent 执行、sandbox、上下文、写回、repair | Studio `runtime/` | Engine 文学规则 |
| 新 Runner/CLI/SDK | Studio `runtimes/` + `integrations/` | Worker 子类、route 分支 |
| 自动推进、授权、恢复 | Studio `automation/` | Engine task lifecycle 副本 |
| 自适应计划 | Studio `orchestration/` + Engine 只读 catalog | 直接签发任务、写 Canon |
| 数据库存储、lease、event | application persistence port + `persistence/` adapter | application service 内 SQL |
| HTTP/SSE | `api/routers/` | router 内业务逻辑 |
| UI 功能 | 对应 Vue feature client + view/component | generic API 直连、跨 feature 组件 import |
| 桌面启动、资源、更新 | `desktop/`/`packaging/` | 文学 Engine |

## 5. 接口引入七问

新建 Protocol、抽象类、Repository 或 SDK 前必须逐项回答：

1. 谁拥有接口？调用方拥有 port，adapter 不反向定义业务合同。
2. 哪个真实变化点需要隔离？只有实现会替换、外部系统会变化或测试替身有明确价值时才建 port。
3. 输入输出是否为稳定 DTO？跨层不得使用 `dict[str, Any]` 作为万能合同。
4. 错误语义是否结构化？调用方不得解析 SDK 文本来决定业务路线。
5. 是否至少有两个 adapter，或一个真实 adapter 加一个有价值的测试替身？
6. 接口是否隐藏路径、SQL、进程、Provider payload 和框架对象？
7. 是否制造第二套业务真相？接口不能复制 Gate、route state、Canon 或 task lifecycle。

任一问题答案不成立时，优先使用普通函数、不可变 dataclass、Enum 或模块级纯算法。继承只表达真正的可替换行为；不要为每个 Provider、任务类型或文学资产建子类。

## 6. 合同与实现纪律

### 6.1 DTO

- 跨层 DTO 必须版本化或具有明确兼容策略。
- 状态、任务类型、失败种类和 verdict 使用 Enum/受限字面值，不用散落字符串。
- DTO 不泄漏 FastAPI Request、SQLite Row、Pi/OpenCode SDK payload 或 Vue component。
- 机器拥有字段由确定性代码写；Agent 文学判断不得被 canonicalizer 补造。

### 6.2 Ports 与 adapters

- Port 位于调用方拥有的边界；adapter 实现它。
- 所有默认 adapter 在 `ApplicationContainer` 的 infrastructure composition 中选择。
- Runtime 通过 `AgentRuntimePort` + `RuntimeDescriptor` 注册；Worker 不感知 Provider 名称。
- Persistence 通过 `PersistencePorts` 进入；application service 不写 SQL。
- Vue feature 通过 feature client 调用；组件不直接使用 generic transport。

### 6.3 Facades

兼容 facade 只允许：重导出、参数适配、调用委托和弃用提示。不得：

- 保存另一份流程；
- 复制 Gate；
- 根据 Provider/route 增加业务分支；
- 形成新的全局可变状态。

## 7. 文学工程不可变宪法

任何代码优化、吞吐优化或 Agent 自适应都不能删除以下约束：

1. 正式工作由 Engine TaskPackage 签发；CLI/Worker 不能伪造完成。
2. 正文只能由正式主创 Agent 生成，subagent 只能做只读证据提取或机械分析。
3. Agent 只能写 isolated workspace 的 `expected_outputs`；写回前必须 deterministic preflight。
4. Context、RP、Branch、Composition、Prose、AgentReview、Promotion、State/Canon/Continuity 的正式依赖由 route 决定。
5. 字数、节奏、场景功能、衔接、文风和读者体验合同必须进入正文生成及复核链。
6. Agent 可以增加分析和提出计划，不能删除 mandatory Gate。
7. Canon、人物状态、正式正文、资产和发布必须以 patch/receipt/revision 绑定。
8. 修订必须绑定精确候选及 review evidence，不能用另一种表面表达规避 lint。
9. 人工改动可以拥有最高项目优先级，但必须形成明确 owner mutation/audit 事实；不能静默改写机器历史。
10. Debug waiver、`LEW_MAINTAINER_MODE` 和 unreview 路径不得出现在产品流程。

## 8. 实施闭环

### 8.1 计划

1. 回读当前路线与上一次执行记录。
2. 写 Module Change Packet 和完成标准。
3. 冻结当前输入、输出、错误、事件顺序和用户行为。
4. 先选择定向测试，再改代码。

### 8.2 实现

1. 先修改拥有合同的模块。
2. 通过组合根注入 adapter，不在调用方构造全局 service。
3. 纯算法与 I/O、协议与 transport、validation 与 repair 分离。
4. 保持一个 writer；并发只用于无读写冲突的只读/候选任务。
5. 不为降低行数机械拆出共享可变状态函数。

### 8.3 验证

最低矩阵：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest <本模块合同和回归测试> -v
python -m compileall -q src
python scripts/architecture_audit.py
python scripts/generate_module_map.py --check
python -m literary_engineering_studio_engine prompt-registry-validate --json
git diff --check
```

按影响追加：

- Runtime/Worker/Prompt/文学路线：sandbox + preflight + writeback integration、真实模型 opt-in benchmark、连续场景 E2E。
- API：`/health`、一个 mutation endpoint、一个 read model、一个 SSE endpoint。
- Vue：feature client contract、Vitest、build；布局变更增加 Playwright 桌面/移动截图、overflow 和 overlap 检查。
- Desktop/Packaging：sidecar/Pi bundle provenance、installer、干净用户目录启动。
- Version/Release：版本同步、自动更新 metadata、Release asset hash。

测试失败必须归属到主模块。不得在上层吞掉错误、放宽 Gate 或加入特殊字符串绕过。

### 8.4 Git 与记录

- 每个可回滚边界一个提交；合同、adapter 迁移、行为变更和发布元数据尽量分开。
- 提交前 `git diff --check`，提交后 `git show --check --stat HEAD`。
- 不修改架构 baseline 来容纳新增债务。
- 执行日志记录：计划、事实、测试、未验证项、真实外部阻断和下一步。
- 不把 Provider quota、网络失败或未运行的 E2E 写成“已通过”。

## 9. 复杂度与模块质量

- 新文件默认不超过 350 行；超过 450 行先写 ADR。
- 新函数默认不超过 60 行、复杂度不超过 12。
- M7 的 16 个超长文件和 120 个复杂函数是受控历史债务，只减不增。
- import cycle、forbidden dependency、duplicate route、parse error 必须始终为 0。
- Engine -> Studio 为 0；Studio -> Engine internal 为 0。
- application -> FastAPI/Tauri/Vue/Provider SDK 为 0。
- frontend feature -> 其他 feature concrete component 为 0。

若实现必须跨越这些阈值，先提交 ADR，解释为什么声明式规则表、生成文件或性能关键代码不宜拆分，以及如何阻止债务继续增长。

## 10. 失败与升级路径

遇到以下情况必须停止当前实现并重新计划：

- 找不到唯一主模块；
- 需要复制 Gate 或 task lifecycle 才能实现；
- 需要读取整个项目才能理解一个接口；
- adapter 需要知道文学 route 内部细节；
- UI 需要直接修改项目文件；
- 新功能只能靠 debug waiver 前进；
- 预检失败但 expected output 看似存在；
- 真实 Provider 出现 quota/auth/network 问题；
- 同一任务两次 repair 后无可验证进展；
- 需要修改 architecture baseline。

升级时给出：失败分类、所属模块、输入合同、实际输出、期望输出、最小复现、是否污染正式项目、建议的合同级修复。不要只添加针对某个文件名或错误文本的补丁。

## 11. 面向接口交付模板

完成后用以下摘要结束一个开发批次：

```yaml
delivery:
  module: "主模块"
  public_contract: "新增/保持的接口"
  behavior: "用户可见结果"
  adapters_changed: []
  gates_preserved: []
  tests_passed: []
  architecture:
    forbidden_dependencies: 0
    import_cycles: 0
    debt_delta: "只减不增"
  e2e_evidence: "路径/运行 ID，或未运行的真实原因"
  rollback_commit: "commit sha"
  remaining_risk: []
```

完成标准不是“代码已写”，而是调用方只依赖稳定接口、行为由测试保护、架构棘轮没有倒退、真实外部验证没有被伪造。
