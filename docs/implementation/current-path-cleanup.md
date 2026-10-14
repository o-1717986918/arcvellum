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
