# ArcVellum post-v0.9.4 空间可靠性验证

验证日期：2026-07-23

验证平台：Windows 11 x64

源码基线：`v0.9.4`

本文记录 `arcvellum-post-v0.9.4-spatial-reliability-execution-directive.md`
的实施结果。当前应用版本号仍为 `0.9.4`；本次生成的安装包用于验收，不代表已经创建新的
Git 标签或 GitHub Release。

## 实施结果

### 工作流可靠性

- 人工选择改为稳定 `choice_id`、幂等回执、正式效果落地和消费后移除的闭环。
- 自动创作持久化推进指纹、停滞轮次和恢复时间；假完成、依赖循环与恢复后无进展会被主动暂停。
- Agent 观测区分控制器、常驻服务、真实会话、正式任务和用户可见事件。
- Worker、Advisor 与 Steward 会话进入统一观测数据源。
- 规则仪表使用独立紧凑组件和共享质量配置逻辑。
- 档案正文改用安全 Markdown 渲染，继续经过净化并支持长表格滚动。

### 空间星仪

- 相机从受限 Euler 角改为四元数方向，支持中键连续旋转，不设人为角度上限。
- 平移、缩放、旋转和观测时间分离；观测窗口只影响强调、明暗和镜头，不删除全书节点。
- 主曲线公式提取为独立 profile，保留时间间距、章节簇和碰撞松弛。
- 完成、当前、规划和阻塞节点使用亮暗、轮廓与线型联合编码。
- 星簇构图改为多个真实感星族：每个星族包含开放螺旋、星云晕、微星核心、尘埃带和跨族连接。
- 舞台构图改为分幕舞台：每一幕包含弧形台口、舞台地板、侧幕、追光和脚灯，节点按前后景调度。
- 星簇与舞台均按章节分组并扩大局部间距，避免在场景粒度下堆叠成单一平面曲线。

## 客户路径故障

### 症状

Windows 安装版在推进长篇字数预算任务时报告：

```text
task JSON must be inside the work project:
C:\Users\<customer>\Documents\ArcVellum\Works\���...\workflow\tasks\
planning-longform-word-budget-file.task.json
```

路径属于客户机器，不是开发者机器；问题也不是客户把任务文件放到了项目外。

### 根因

冻结 sidecar 启动文学工程 CLI 时继承了 Windows 旧控制台代码页。CLI 将包含中文的绝对路径写到
stdout 后，Studio 又按 UTF-8 解码，无法解码的字节被替换为 `�`。Worker 随后拿这个已损坏的
字符串做项目边界检查，自然会判定它不位于真实项目目录内。

### 修复

1. Studio 启动所有核心 CLI 子进程时强制设置 `PYTHONUTF8=1` 和
   `PYTHONIOENCODING=utf-8`。
2. Worker 不再把 CLI 报告的绝对任务路径当成权限依据，而是根据已验证的
   `project_root + task_id` 重建
   `workflow/tasks/<task_id>.task.json`。
3. 只有真实存在且确认位于当前项目内的报告路径才可作为候选。
4. 修正恢复和写回路径的旧后缀回退：统一使用 `.task.json`。
5. 增加中文路径损坏回归测试和任务 ID 越界测试。

这同时修复了编码传输和信任边界：即使外部进程再次返回损坏路径，正式写回也不会逃出当前作品。

## 自动化验证

| 范围 | 结果 |
| --- | --- |
| Python | 253 tests passed |
| Vue/Vitest | 15 files、54 tests passed |
| 客户中文路径回归 | passed |
| 四元数相机与曲线测试 | passed |
| 客户端生产构建 | passed，2472 modules transformed |
| 桌面前端同步 | passed，111 assets、8 WebP |
| sidecar provenance | passed |
| Git whitespace | passed |

## 视觉验收

使用真实项目“你好，新世界”检查了空间星仪：

- `1366x768`：星簇场景粒度、节点间距、关系线和空间窗口无页面级溢出。
- `1920x1080`：全书星簇的多个星族可辨，章节簇和主线保持连续。
- `2560x1440`：舞台场景粒度保持台口、幕布、脚灯与分幕节点层次，未出现旧版巨型幕布遮挡。
- 星簇节点增加局部半径与纵向错位；舞台增加幕间步长和前后景深度，节点标签不再集中碰撞。
- 最终浏览器控制台没有错误或警告。

## 桌面构建与安装

正式脚本已完成：

1. Vue 生产构建与 Tauri 前端同步；
2. PyInstaller 重新冻结当前 Python sidecar；
3. 生成并验证 `build/sidecar-provenance.json`；
4. 捆绑 OpenCode 与许可证文件；
5. 生成 Tauri NSIS x64 安装包；
6. 生成 updater 签名、`latest.json` 与 SHA256 清单。

隔离 NSIS smoke test 结果：

- 静默安装退出码：`0`；
- 安装目录包含主程序、冻结 sidecar、OpenCode 和许可证资源；
- 冷启动后主程序存活，sidecar 在随机 `127.0.0.1` 端口监听；
- 使用隔离的用户数据目录创建 Studio 数据库；
- 静默卸载退出码：`0`，主程序和卸载器均被清理。

### 验收构建产物

| 文件 | 大小 | SHA256 |
| --- | ---: | --- |
| `ArcVellum_0.9.4_x64-setup.exe` | 75,857,007 bytes | `571c3c1cb65ec6d7ecf586dfc5c41eeebf47dc1785cad270450e964af7586178` |
| `ArcVellum_0.9.4_x64-setup.exe.sig` | 420 bytes | `9e3ba16dc5556124deb82afbf75bdef26cdf399175240469ee21ee0668ac44a9` |
| `latest.json` | 850 bytes | `85982d755efe15c7b9cbbb43bd35d1250aeee652a5b3a0305b15b5337fb4e96d` |

## 发布边界

- 当前产物证明源码、冻结 sidecar、安装器和更新签名链可以完整构建。
- updater minisign 不等于 Windows Authenticode 商业签名。
- 尚未为本轮改动提升版本号、创建 Git 标签或上传新的 GitHub Release。
- 发布下一版本前应更新版本与 release notes，并在干净 Windows 10/11 环境补做覆盖升级和 WebView2
  故障矩阵测试。
