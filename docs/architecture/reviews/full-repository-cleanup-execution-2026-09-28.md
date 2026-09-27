# 全仓清理执行记录（v0.99.12）

本记录逐项关闭 [37 项候选](full-repository-cleanup-inventory-2026-09-27.md)。判断以生产入口、动态注册、公开 API、旧项目读取和回归为准。**保留**表示这轮安全删除门槛未满足，不等于遗漏。清理不触碰用户作品或未跟踪的 `docs/video/`、`hw10/`、`onetake-film/`、`work/`。

| 项 | 处理结果 | 安全边界或复核说明 |
| --- | --- | --- |
| C01 | 删除旧补长模块和只验证旧提示的测试 | 软字数由现行场景审读处理；旧提示在目录中标作只读历史层。 |
| C02 | 删除 Studio 预先全套对演入口、旧逐轮导演和专属测试 | 按需 `fulfill_scene_material_requests` 留存；人格优先级、续演和候选边界转入现行测试。Engine 已公开的旧导演渲染函数暂作兼容保留。 |
| C03 | 删除未挂载 Advisor feature client、harness 和专属测试 | `/advisor/*` HTTP 与 Project Agent 共享的会话表保留。 |
| C04 | 删除 `autopilot.py`、`whole_book_release.py` 两个 Studio 根转发 | 内部测试导入及 patch 已迁移规范模块。 |
| C05 | 删除断开的策略前端 feature 及其专属测试 | `/strategy` 重定向和后端策略合同保留。 |
| C06 | 删除断开的 Agent 观测视图及其专属测试 | `/observatory` 重定向和现行创作现场观测 API 保留。 |
| C07 | 删除旧 Orrery Dock、测试及仅供它使用的 CSS | 现行星仪导航未改变。 |
| C08 | 删除无调用背景加载器和独占 WebP | 旧 `mineral` 偏好读取和归一化保留。 |
| C09 | 删除未调用的顺序角色会话适配器 | 现行逐轮角色与描写器续演保留。 |
| C10 | 删除未调用的归属修复提示包装 | 实际归属审计及修订循环保留；两份旧提示标为只读历史。 |
| C11 | 删除未连接的两个自定义 Provider 请求 DTO | 当前供应商配置 HTTP 合同不变。 |
| C12 | 删除 Canon changelog 的未调用包装 | 现行原子写回仍调用 `_render_changelog_entry`。 |
| C13 | 删除未调用的多次风格评测聚合 | 当前风格评测门槛与引用读取不变。 |
| C14 | 删除未调用的 warning 构造包装 | `WARNING` 严重度合同保留。 |
| C15 | 删除未调用的 v4 SSE 转换包装 | v4 仍直接走参数化转换，v3 测试入口保留。 |
| C16 | 删除未调用的回执分组函数 | `change_group_id` 生成与回执存储不变。 |
| C17 | 删除未调用的事件持久化布尔包装 | 统一事件分类器保留。 |
| C18 | `api_server.py` 生产导入改为规范子模块；根转发保留 | 其他根路径仍被测试 patch 和可能的外部 Python 使用，未建立安全移除窗口。 |
| C19 | Engine 包内 v1 Schema 定为规范源，对齐 `protocol/schemas` 镜像并增加一致性测试 | 两个已发布位置都保留，旧任务身份与字段不变；后续漂移会在测试中失败。 |
| C20 | 删除 C05/C06 的孤立 CSS 选择器 | 仅删除模板不可达的类，保留当前页面及演示启动样式。 |
| C21 | 保留禁用的旧 Engine CLI handler | 顶层别名有 `remove_not_before: 1.0.0`；提前删除会破坏公开兼容。 |
| C22 | 保留只被 C21 调用的 Dify/LangGraph 适配 | 与受保护的旧 CLI handler 同一退役单元。 |
| C23 | 删除独立直连 Provider 的旧文风生成、评测与若干孤岛 | 旧 Engine HTTP 的资产/导演调用仍需独立兼容评估；目录将退役层标作历史，正式 PromptProgram 继续使用。 |
| C24 | 删除 Orrery feature client 中无调用的 v2 请求和流方法 | 旧 HTTP v2/v3 路由及 v4 内部投影构建保留。 |
| C25 | 删除 `run_author_style_learning` 直连路径和专属结果类型 | 正式 `run_author_style_learning_platform_task` 保留，重复语料准备随直连路径消失。 |
| C26 | 删除旧文风 Agent 提示和直连评测模块及旧路径测试 | `style_prompt.md` 的正式生成、挂载、质量检查和历史读取保留。 |
| C27 | 删除无调用的 Agent JSON patch 规划模块 | 正式 Task 与其他 schema 校验保留。 |
| C28 | 删除无调用的 Agent run 修复入口和结果 DTO | `validate_agent_run` 保留。 |
| C29 | 删除无调用的直连审查委员会模块 | 正式 Worker 委员会任务及现行审查 Gate 保留。 |
| C30 | 删除无调用的直连 Canon Agent 审查模块 | Canon lint、正式审查和旧结果读取保留。 |
| C31 | 删除无调用的批量项目种子包装 | 单项候选能力仍供旧 HTTP/导演使用。 |
| C32 | 保留写死历史实验的 spike 脚本 | 研究记录仍引用它；冻结输入未随仓库发布，删除或参数化不能提高当前产品安全性。 |
| C33 | 删除无引用的能力登记 dataclass | handler 登记和解析行为不变。 |
| C34 | 删除无调用的旧 CLI prompt 文件参数 helper | 当前 CLI 正式提示和命令仍在。 |
| C35 | 保留 v0.2 runtime 状态别名 | 尚未公布外部 Python 移除窗口。 |
| C36 | 将生成的 `desktop/dist/index.html` 移出版本控制 | `client:build`、桌面开发/打包和 CI 都先生成并同步它；整个 `desktop/dist` 现由 `.gitignore` 排除。 |
| C37 | 保留旧场景 Provider 与顶层别名 | 兼容清单明确规定 1.0.0 前不可移除；正式场景路径不调用它。 |

清理后的现行边界：`lean-v2` 按主创意图选择素材，角色和描写器只提供候选；`strict-v1`、历史 Schema/项目读者、正式事实写回和第三方许可证继续可用。旧 HTTP、Engine 公开别名与根转发需要 1.0.0 外部消费者审计，不能用仓库内零引用代替迁移证据。

## 验证

Python 全量运行 1666 项（1665 通过、1 跳过）；Vue 全量 247 项、Pi Worker 114 项通过，客户端生产构建通过。Prompt Registry 59 个资产与 73 个任务 ID、确定性提示评估 17 项、兼容表面、v1 Schema 镜像测试、OpenAPI、模块地图、架构审计与七处版本同步均通过。设置页桌面及移动浏览器用例通过。并行负载下曾有一项旧路由测试触及 5 秒超时；单项和独立全套复跑均通过。发布工作流与附件结果见[发布验证](../../releases/v0.99.12-verification.md)；执行变更见 [Change Packets](v09912-cleanup-change-packets.md)。
