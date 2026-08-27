# ArcVellum v0.99.1 模块化开发就绪审计

审计日期：2026-08-27

## 结论

ArcVellum 已经具备**面向接口、按主模块收敛开发**的正式准备，可以把常规开发循环稳定地执行为：

```text
需求或故障
  -> 在模块目录中定位唯一主模块
  -> 读取公开合同、一个真实 adapter 与定向测试
  -> 在模块内部实现
  -> 运行模块测试、架构棘轮与必要 E2E
  -> 独立 Git 提交
```

这里的“模块化”是：开发者无需加载无关模块的实现代码，不复制业务真相，通过稳定接口完成局部修改。它不等于“任何修改都只读一个文件”，也不等于“合同改变后调用方永远不需要迁移”。后两种承诺既不真实，也会制造隐藏耦合。

## 已完成的准备

| 能力 | 事实证据 | 状态 |
|---|---|---|
| 需求归属 | `module-catalog.md` 给出 Engine、Studio、Runtime、API、Persistence、Vue、Desktop 的唯一所有权和入口 | 完成 |
| 最小读取协议 | `agent-interface-development-standard.md` 固定“目录 -> public contract -> test -> adapter”的读取次序 | 完成 |
| 变更闭环 | Module Change Packet 要求唯一主模块、输入输出、依赖、禁区、测试和回滚提交 | 完成 |
| Engine 边界 | Studio 只经 `literary_engineering_studio_engine/public/` 消费文学真相 | 完成 |
| 应用组合根 | `application/container.py` 与 `infrastructure/composition.py` 是唯一正式装配位置 | 完成 |
| Runtime 扩展 | Agent Runner 通过 `AgentRuntimePort`、descriptor、registry 和 adapter 接入 | 完成 |
| Persistence 扩展 | application ports 拥有合同，SQLite/内存实现位于 adapter 层 | 完成 |
| API 边界 | versioned router 只做 HTTP/SSE 适配，投影与业务实现位于所属模块 | 完成 |
| 前端边界 | Feature 使用自己的 client；跨 Feature 工作台由中立 composition registry 装配 | 完成 |
| 自动防回退 | Architecture Audit、generated module map、版本同步、Prompt Registry 与定向合同测试组成棘轮 | 完成 |
| 发布可追溯 | 版本、sidecar、Pi Worker、桌面资源、Updater 与 Release 进入统一发布验证 | 完成 |

## 本轮实际验证

- Architecture Audit：16 个受控历史大文件、110 个受控历史复杂函数、0 新违规、0 import cycle、0 Studio 对 Engine internal 的导入；
- Engine 到 Studio 的反向依赖为 0；
- v4 投影、API 路由、星仪布局与工作台装配均已按所有权拆分，且没有放宽架构 baseline；
- Vue 65 个测试文件、200 项测试通过；Pi Worker 75 项测试通过；
- Playwright 8 项视觉验收通过，包含 100、300、1000 场景规模；
- Prompt Registry 57 个资产、72 个任务提示词 ID 校验通过。

## 仍需诚实保留的边界

1. **历史复杂度尚未清零。** 16 个大文件与 110 个复杂函数是只减不增的历史债务，不影响模块定位机制成立，但其中任一文件被修改时仍需先局部拆分评估。
2. **公共合同变更不是单模块事件。** 改 DTO、HTTP schema、TaskPackage 或 Engine public API 时，应先提交合同，再分别迁移 adapter 和调用方；不能以“模块化”为由让两端悄悄不一致。
3. **组合与端到端行为仍需跨层验收。** Runtime、写回、Autopilot、SSE、桌面打包等功能可以局部开发，但发布前必须经过集成门禁。
4. **星仪大规模首帧仍有性能债务。** 1000 场景投影 API 约 0.37 秒，浏览器完整首帧约 30 至 45 秒；所属模块已经明确为 Orrery projection/layout/rendering，不应通过放宽文学内核或隐藏节点解决。
5. **前端 bundle 仍有一个较大星仪 chunk。** 它是加载性能债务，不是模块所有权缺失；后续应在 Orrery feature 内进行按工作台和渲染器的懒加载优化。

## 后续 Agent 的强制开发入口

1. 先查阅 `docs/architecture/module-catalog.md`，给需求选择一个 `primary_module`；
2. 填写 Module Change Packet；
3. 只读取公开入口、合同测试与一个 adapter；
4. 只有实现被阻断时才展开模块内部；
5. 合同不变时不得读取或修改调用方实现；
6. 合同必须变化时拆成“合同、adapter、调用方”三个可回滚批次；
7. 结束前运行定向测试、Architecture Audit、module map check 与 `git diff --check`；
8. 不通过修改 baseline、复制 Gate、增加兼容分支或扩大万能 DTO 来换取局部便利。

## 最终判定

**面向接口的模块化开发准备：通过。**

**完全零上下文、零跨模块迁移：不作为目标，也不应对外承诺。** ArcVellum 当前达到的是更有工程意义的标准：提出需求后可以先精确定位唯一主模块，在稳定接口内局部实现；只有公开合同确需改变时，才显式、分批触及依赖模块。
