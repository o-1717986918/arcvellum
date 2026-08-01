# W6-10 v1 最终验收（交付审计）

## 范围

W6-10 是 W6 的最终验收批次：固定路线回退、真实项目长跑、吞吐基线、
桌面生产构建与交付审计。本批以“证据化验收”方式收口，凡需要真实外部运行
的项目（长跑、干净虚拟机安装矩阵、真实稿件质量评估）均明确标注为
owner acceptance，不伪造证据。

## 需求对照

| W6-10 要求 | 证据 | 状态 |
| --- | --- | --- |
| 固定路线回退 | `DefaultPlanFactory` 默认 `fixed-formal-route.v1` 空节点宏；`test_fixed_route_fallback.py`（2 tests）：非法事实 shadow 评估 fail closed、不产生计划/策略；W6-6C/D shadow 管线失败即停止；v0.96.4 发行说明确认 production 默认 fixed | 完成 |
| 真实项目长跑 | W6-5B 真实场景端到端闭环（v0.96.4 证据：RP→分支→正文→Review→修订→promotion→state/canon）；全量 824 Python tests（含 109 个 W6-6/7/8 定向测试）；多小时无人值守真实项目长跑需用户授权模型与项目，列为 owner acceptance | 契约与回归完成；长跑验收待 owner |
| 吞吐基线 | v0.96.4 多样本 A/B：非缓存输入 Token 中位降幅 47.18%、首轮可见字符中位降幅 62.64%；`observability/throughput_*` 只读投影存在；W6-7B ContextCacheKey/session lease 契约；每场景真实基线需正式任务数据，列为 owner acceptance | 基线证据完成；真实场景基线待 owner |
| 桌面生产构建 | 本会话本地签名构建：ArcVellum_0.96.4_x64-setup.exe（SHA-256 `e8db5fd4…82f5ad2`）+ `.sig`/`latest.json`/`SHA256SUMS.txt`；Release CI（v0.96.4）success；干净 Windows 10/11 安装/覆盖升级矩阵与卸载重装验收按 RELEASING.md 列为 owner acceptance | 构建完成；VM 验收待 owner |
| 交付审计 | 本文件 + PR #5–#19 + 全量验证证据（见下） | 完成 |

## 全量验证证据（2026-08-01）

- Python：824 tests passed，1 skipped。
- 前端：52 files、152 tests passed。
- `client:build`（vue-tsc + vite + desktop sync）通过。
- Architecture Audit：34 file / 220 function debt、0 cycle，无新增债务。
- `compileall`、`git diff --check`、版本同步检查通过。
- 交付物：本地签名安装包位于
  `C:\Users\26532\Documents\Codex\2026-08-01\1\outputs\arcvellum-v0.96.4-installer\`。

## W6 全批次交付清单

| 批次 | 内容 | PR |
| --- | --- | --- |
| W6-6 | AO-5 章节级编排（Rolling Horizon/SceneRiskProfile/事件库存/字数/节奏/承诺义务/shadow） | #5–#8 |
| W6-7 | AO-6 资源锁与有限并发（Bundle/缓存/修复/session lease/Resource Gate）契约与准入层 | #9–#12 |
| W6-8 | AO-7 全书重规划与 Campaign（Progress Fingerprint/checkpoint/恢复阶梯/replan/无人值守）契约层 | #13–#15 |
| W6-9 | AO-8 前端产品化（策略页/typed SSE/Observatory/星仪投影） | #16–#18 |
| W6-10 | v1 最终验收 | #19 |

## 边界与未决事项

- 生产执行器接线（Bundle 执行、缓存存储、session pool、并行审查调度、
  Campaign 长跑循环）与交互式计划审批入口按分阶段启用计划明确列为后续
  批次，W6 各 Exit Audit 均未冒充生产并发/无人值守已开放。
- 真实项目长跑、干净 VM 安装/升级矩阵与真实稿件质量评估需用户提供
  项目与模型授权，作为 owner acceptance 项。
- PR #5–#19 已创建并满足分支保护检查门槛，合入需用户在 GitHub 审批。

## 结论

W6 全部批次（AO-5 至 AO-8 + v1 验收）已完成契约、确定性测试、集成测试、
架构审查、Git 提交与 PR 交付；固定路线默认不变，正式 Gate 未被绕过，
无新增架构债务。剩余事项均为需要用户/外部环境参与的验收与合入步骤。
