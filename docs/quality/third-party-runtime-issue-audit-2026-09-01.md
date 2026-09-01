# 第三方运行问题事实审计与修复记录

> 日期：2026-09-01  
> 范围：第三方截图中的第 2-8 项；OpenCode 项按要求排除。  
> 方法：基于当前分支代码、正式 route、状态派生、运行沙箱和测试执行核验。

## 结论表

| 项 | 事实结论 | 归属 | 本轮处理 |
|---|---|---|---|
| 文风评估任务因只读 prompt 被改写而失败 | 真实 | Studio preflight + Engine style evidence | canonicalizer 排除只读 eval prompt；评估摘要改为绑定 holdout 文件事实 |
| 故事架构 `revise` 后循环 | 真实 | Engine longform route/workflow | 增加正式 revision 状态、候选变更证明、重新签发独立审查和 fresh digest Gate |
| steward/worker 模型运行中才暴露未配置 | 部分真实 | Studio runtime/autopilot | 自动创作启动与恢复前验证 worker；全自动模式额外验证 steward |
| 场景参与者含说明性括号 | 数据风险真实，当前合同已有防线 | Engine planning/scene assets | 保留 fail-closed；确认库存解析、preflight repair 指引、场景人物资产 Gate 三层覆盖 |
| 文风评估 completion 存在但状态再次签发 | 真实 | Engine style digest derivation | 删除对未来 `style_eval_current.json` 的循环依赖，直接校验 manifest 声明的 holdout 摘要 |
| 同秒运行目录冲突 | 真实 | Studio runtime sandbox | run id 改为微秒 UTC + 随机后缀；显式 run id 仍保持冲突拒绝 |
| 全量测试大量失败 | 截图数字已过时；当前 GitHub Python job 仅有一个平台假设错误 | packaging test | 测试显式声明 `windows-x64` fixture，不再从 Linux 宿主推导目标 |

## 横向闭环审查

当前正式路线中，以下高风险审查已具备显式修订闭环：

- 人物与世界资产：review verdict -> candidate revision -> independent recheck -> approval/promotion；
- 故事架构：exact-candidate review -> revision -> fresh review -> word budget；
- 字数预算、场景库存、章节义务：review -> declared repair target change -> fresh validation；
- 文风评估：deterministic score -> revision -> stale-score proof -> fresh score；
- 场景正文：AgentReview/static review -> revision candidate -> exact-candidate re-review -> promotion；
- Canon patch 与项目级审查：review/approval -> bounded revision -> recheck/apply。

本轮没有建立通用的“万能 review 基类”。各路线的终止判据、可修订产物和写回风险不同，强行抽象会弱化证据合同。共享能力继续限定在 TaskPackage 生命周期、摘要绑定、修订目标变更证明和 completion sidecar。

## 验证证据

- 文风定向测试：4 项通过；
- 故事架构定向测试：10 项通过；
- Runtime/Sandbox/Autopilot/Packaging 定向测试：68 项通过；
- 旧 participants 合同已有独立拒绝测试和 preflight 修复文本；
- Engine/Studio 完整 Python 回归：1318 项通过，1 项因当前 Windows 环境无法创建测试符号链接而跳过；
- 架构审计通过：没有新增依赖违规、循环依赖或 Studio 对 Engine 内部实现的越界导入；
- longform route 已拆为 `definition.py` 薄入口、`blueprints.py`、`gates.py` 与 `support.py`，避免以提高债务基线代替结构治理；
- 生成模块图与版本同步检查通过；Prompt Registry 共 57 个资产、72 个任务映射，零错误、零警告；
- Vue 客户端 203 项测试通过并完成生产构建；内置 Pi Worker 82 项测试通过。

## 后续开发入口

后续维护者先阅读：

1. `CONTRIBUTING.md`；
2. `docs/architecture/module-catalog.md`；
3. `docs/architecture/troubleshooting-module-index.md`；
4. `docs/architecture/agent-interface-development-standard.md`。
