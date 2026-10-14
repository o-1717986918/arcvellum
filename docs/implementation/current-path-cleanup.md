# 当前路径清理记录

本次清理在两场正式单元实测通过、v0.99.13 发布后进行。发布标签保持不变；旧项目兼容不作为保留理由。删除前完成 1,896 个已跟踪代码文件的语法树或文本遍历，并保存逐文件覆盖与候选清单。

## Studio 导入转发层

Module Change Packet：

- objective：调用方直接使用所属模块，移除 22 个无业务行为的根目录转发模块。
- primary_module：Studio 模块入口。
- public_entry：application、runtime、persistence、projections、observability 等所属入口。
- variation_point：none。
- inputs / outputs：原有接口、返回值与错误不变。
- invariants：文学 Gate、Canon 审批、权限和写回顺序不变；不改已发布标签。
- allowed_dependencies：原转发目标模块及现有调用方。
- forbidden_dependencies：Engine 内部跨包导入、额外模型调用。
- tests：完整 Python 回归、构建资源后的安装发现与前端服务测试、架构检查、模块地图。
- rollback_unit：独立的 Studio 转发层清理提交。

22 个旧模块仅向 sys.modules 注册所属模块，没有独立实现。迁移包括内部导入、测试替身路径和现行文档；架构基线只删除相应已清偿的债务，不放宽预算。首轮完整 Python 回归发现两个隔离工作树缺少构建资源的问题，分别为前端资源与 Pi Worker 安装发现；补建资源后复核。

前端与 Pi Worker 导入图中的无导入项均为启动入口和测试夹具，予以保留。前端启用未使用变量/参数检查后通过。事件处理器按字符串注册后动态调用，不能作为静态无引用代码删除。

补建前端与 Worker 后，两项失败均复核通过；首轮其余 Python 测试通过，架构检查无新增债务。Studio 转发层独立提交为 b46207f3。

## Engine 旧集成路径

Module Change Packet：objective 为移除当前产品入口不可达的旧 HTTP、直连 Provider 与 Director 子系统；primary_module 为 Engine 集成边界；public_entry 为 Engine public API、command_line.entry 和 Studio 所属 API / Pi Worker。输入输出继续使用现有 TaskPackage、候选记录和审批回执。允许依赖现有平台任务、资产注册和晋升；禁止额外模型调用、Studio 越过 Engine public 边界。现有正式 Gate、Canon、独立审读与原子晋升逻辑不变。测试覆盖 CLI、sidecar、旧入口不可导入、资产审批、文风快照失效和全套 Python；独立提交可回退。

已核实旧 HTTP、Director、Provider 的生产调用仅在旧子系统内，旧 CLI handler 未注册。资产列表和审批晋升仍被当前路径使用，保留原实现；构造假文学内容的 helper 移至测试目录，不随 Engine 分发。文风快照链测试改用现有平台任务包及测试拥有的交付夹具，保留挂载变更必须失效的断言。CLI 和 sidecar 直接调用所属入口，撤销旧模块保留窗口并禁止重新加入已退役模块。

## 未接入的 Runtime 合同与私有包装

Module Change Packet：primary_module 为 Studio runtime；objective 为移除没有生产、脚本或打包调用方的未来合同和诊断包装。当前 Pi Worker 会话恢复、缓存绑定、正式修复与 preflight 保留。删除的 SessionLease / OutputRepair DTO 不是当前实现，关联独立测试随旧合同移除；混合测试保留仍在使用的缓存键及 ContractViolation 覆盖。旧 lifecycle 构造适配器移除，测试向当前应用生命周期显式注入 ports。定向和完整 Python 回归验证；独立提交可回退。

另外按 automation、creative_live、persistence、Engine composition / workflow 和 narrative projection 各自所有权记录私有 helper 清理 packet：只删除已核实无调用的定义及导入。叙事图公开 projection_motion_events 导出保留。场景范围测试原先 mock 已不调用的全扫描函数，现改为观察实际场景状态构建次数，确认只处理指定场景。动态注册的吞吐事件处理器保留。

Engine command-line packet：移除十处没有 handler 消费的 `--provider` 兼容参数；当前命令直接准备 Worker 任务，桥接入口拒绝旧参数的分离与等号两种写法。验证 parser、桥接安全及平台任务准备，文学行为和正式 Gate 不变。

## 完成验证

本轮共删除 73 个源模块和 5 个只覆盖退役实现的测试文件，净减少约 7,970 行。32 个静态无生产导入候选及 25 个私有定义候选均已保存逐项处置。14 个动态事件处理器保留。没有新增付费模型调用。

最终 Python 回归运行 2,065 项，1 项跳过，其余通过。前端未使用变量/参数检查及前端、Pi Worker 构建通过；架构、版本同步、模块地图、提示词注册表和 OpenAPI 合同检查通过。架构债务收紧至 15 项文件、68 项函数，原预算不变，循环依赖及 Studio 越界 Engine 导入均为零。

234 个变更文件经身份核对后同步至共享工作树，无冲突、无暂存区变动，保留备份；共享工作树另行通过 20 项入口、生命周期、文风快照及桥接测试。模块地图各自依据其工作树的已跟踪文件生成。清理代码在 refactor/current-path-cleanup 分支；v0.99.13 发布标签及安装包保持发布时的实测版本，不将之后的清理误称为已装入该安装包。
