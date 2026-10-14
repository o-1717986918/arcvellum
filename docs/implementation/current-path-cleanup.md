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
