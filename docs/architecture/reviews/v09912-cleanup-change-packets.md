# v0.99.12 安全清理与发布 Change Packets

依据 [全仓候选清单](full-repository-cleanup-inventory-2026-09-27.md) 逐项处理。每项须经调用、动态注册、公开兼容、持久化读者和专属测试复核；发现未满足删除门槛时保留并记入最终清单。既有未提交创作内核改动属于本次待验证版本，`docs/video/`、`hw10/`、`onetake-film/`、`work/` 等未跟踪材料不纳入发布。

## P1：客户端断开表面

```yaml
module_change_packet:
  objective: "移除不可从 Vue 入口到达的旧视图、客户端、资源和专属样式"
  primary_module: "client/src/features（各 feature 独立回滚）"
  public_entry: "router.ts、当前 Project Agent、当前 Orrery feature client"
  variation_point: "none"
  inputs: ["当前路由映射", "持久化 Orrery 偏好"]
  outputs: ["现行视图与 API 行为相同", "较小的构建图"]
  invariants: ["旧 URL 重定向继续", "后端 Advisor/策略/观测兼容 API 继续", "旧矿物偏好值继续读取"]
  allowed_dependencies: ["本 feature 的组件和测试", "选择器级 CSS"]
  forbidden_dependencies: ["持久化表", "后端兼容路由", "现行 Orrery 投影"]
  tests: ["client:test", "client:build", "桌面及移动视觉检查"]
  rollback_unit: "每个断开 feature 的独立提交"
  documentation: ["清理结果表", "README"]
```

## P2：Studio 私有死路径

```yaml
module_change_packet:
  objective: "移除场景事务已替代的补长/预演路径和私有无调用包装"
  primary_module: "src/literary_engineering_studio/runtimes（再按所属模块独立处理其他私有函数）"
  public_entry: "pi_scene_transaction、fulfill_scene_material_requests、现行事件分类器"
  variation_point: "none"
  inputs: ["CreativeIntentV1", "MaterialRequestV2", "现行场景上下文"]
  outputs: ["按需候选", "软字数交审读", "既有事件与回执"]
  invariants: ["角色人格初始化", "候选无正式写权", "导演判断交接", "正式事实边界", "strict-v1"]
  allowed_dependencies: ["runtimes", "相应 Studio 私有模块与定向测试"]
  forbidden_dependencies: ["改变 Engine Gate", "删除公开兼容 facade", "删旧项目读者"]
  tests: ["场景事务、角色会话和素材测试", "Python 全套", "兼容审计"]
  rollback_unit: "场景路径和每个独立私有模块分别提交"
  documentation: ["清理结果表"]
```

## P3：Engine 私有孤岛与 schema

```yaml
module_change_packet:
  objective: "删除无调用且无兼容承诺的 Engine 私有旧函数，解决双份 v1 Schema 漂移"
  primary_module: "src/literary_engineering_studio_engine（按子模块独立回滚）"
  public_entry: "public.*、正式任务与 _engine/schemas"
  variation_point: "v1 schema 镜像或单一源的构建方式"
  inputs: ["正式任务 Schema", "旧任务读者"]
  outputs: ["同一份权威 v1 Schema", "不变的旧任务读取能力"]
  invariants: ["public.* 稳定", "1.0.0 前保留受保护别名", "正式 Gate 与 strict-v1 不变"]
  allowed_dependencies: ["Engine 子模块", "schema 合同测试"]
  forbidden_dependencies: ["Studio internal", "Provider 替代调用", "静默改变旧 Schema 身份"]
  tests: ["Engine 公开 API 与 Schema 合同", "prompt-registry-validate", "兼容审计"]
  rollback_unit: "每个 Engine 子模块及 Schema 独立提交"
  documentation: ["清理结果表", "schema 来源说明"]
```

## P4：版本与发布

```yaml
module_change_packet:
  objective: "把已验证的创作内核、分层提示词工作台及安全清理发布为 v0.99.12"
  primary_module: "发布元数据与 .github/workflows/release.yml"
  public_entry: "v0.99.12 Git tag 和 GitHub Release"
  variation_point: "版本号及构建附件"
  inputs: ["受控提交", "同步版本声明", "发行说明"]
  outputs: ["Windows 安装包和更新清单", "macOS 预览包", "发行说明与验证记录"]
  invariants: ["版本一致", "发布工作树不混入用户材料", "签名仅在 CI Secret 中", "未通过不得标称通过"]
  allowed_dependencies: ["发布工作流", "版本同步脚本", "构建/测试"]
  forbidden_dependencies: ["手动替换签名二进制", "复用旧 tag", "未验证的发行成功声明"]
  tests: ["完整确定性矩阵", "版本同步", "Actions 发布状态与附件哈希"]
  rollback_unit: "发布元数据提交与 v0.99.12 tag"
  documentation: ["README", "CHANGELOG", "docs/releases/v0.99.12*.md", "清理结果表"]
```

## P5：Linux CI 的正式任务路径规范化

```yaml
module_change_packet:
  objective: "在 Windows 与 POSIX 上把旧任务蓝图的反斜杠路径归一为同一斜杠形式"
  primary_module: "Engine tasking/paths.py"
  public_entry: "normalize_relative_path，经 TaskBuilder.normalized_unique 使用"
  variation_point: "不同宿主系统对反斜杠是否视作路径分隔符"
  inputs: ["drafts\\candidate.md", "drafts/candidate.md"]
  outputs: ["drafts/candidate.md"]
  invariants: ["正式任务路径身份一致", "不改外部绝对路径读取策略", "v1/v2 Schema 不变"]
  allowed_dependencies: ["tasking/paths.py", "现有 test_task_builder"]
  forbidden_dependencies: ["Studio 路径适配器", "放宽任务资源边界"]
  tests: ["Windows 定向任务构建测试", "Linux CI 全量任务合同"]
  rollback_unit: "路径规范化修复提交"
  documentation: ["发布验证中的 CI 记录"]
```

## P6：生成式桌面资源的 CI 顺序

```yaml
module_change_packet:
  objective: "移出版本控制的 desktop/dist 在 Windows desktop-shell 检查前由正式前端构建生成"
  primary_module: ".github/workflows/ci.yml"
  public_entry: "desktop-shell job 的 cargo check --locked"
  variation_point: "Vue/Windows/macOS 作业各有独立 checkout，不能共享生成资源"
  inputs: ["clean checkout", "npm lockfile", "client build"]
  outputs: ["desktop/dist/index.html", "Tauri 前端资源"]
  invariants: ["不重新跟踪生成文件", "发布工作流已有的构建顺序不变", "前端构建失败阻断桌面壳检查"]
  allowed_dependencies: ["desktop-shell job", "既有 client:build 脚本"]
  forbidden_dependencies: ["提交生成 index.html", "依赖另一个 job 的本地磁盘"]
  tests: ["本地 client:build", "Windows desktop-shell CI"]
  rollback_unit: "Windows CI 生成资源修复提交"
  documentation: ["发布验证中的 CI 记录"]
```
