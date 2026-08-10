# P5 Pi RPC 工程与价值评估

> 日期：2026-08-10
> Pi 固定提交：`936aff00918de1187f085f123c2812d8f2d67745`
> 结论：RPC 适配工程价值已证实；创作吞吐、成本与质量价值证据不足，不进入 P6。

## 1. 实际交付

- 按 Pi 根 workspace 的真实依赖闭包物化 sparse checkout，并使用 lockfile 安装。
- 在不改上游源码的前提下完成 `0.84.1` 构建；可复现信息见 `pi-rpc-build-receipt-2026-08-10.json`。
- 新增严格 UTF-8、LF-only JSONL framing；主动拒绝 BOM，避免 Windows PowerShell 管道污染协议。
- 新增 request-id correlation、事件分流、`get_state`、`get_session_stats`、`abort`、EOF、超时和进程回收。
- 新增短生命周期 `PiRpcRuntime`，复用现有 `TaskPackage -> sandbox -> preflight -> writeback` 主链。
- Runtime Registry 现在区分 `registered`、`enabled` 和 `probed`。`pi-rpc` 默认禁用，健康检查不会启动或探测它。
- 普通 `task-run`、`agent-worker-once`、Studio 设置和安装包均未开放 Pi；只有开发 benchmark 脚本可以在双重显式确认后注入非持久 `experiment_authorized` 并临时启用。

## 2. 无模型 RPC 证据

真实构建产物完成以下调用：

- `--version` 返回 `0.84.1`；
- `get_state` 返回带 request id 的成功响应；
- `get_session_stats` 返回零消息、零 token 的临时会话统计；
- `abort` 成功响应；
- 关闭 stdin 后进程以退出码 `0` 回收；
- 5 次短生命周期“启动 + get_state”样本为 `1330.808 / 1285.644 / 1325.974 / 1321.012 / 1336.492 ms`；P50 为 `1325.974 ms`，当前样本观测最大值为 `1336.492 ms`。

这证明 Pi RPC 可以被 Studio 可靠托管，也说明首版没有必要提前建立进程池：约 1.3 秒启动成本需要与真实模型推理总时长一起评估，不能单独推导常驻收益。

## 3. 安全边界

`PiRpcRuntime` 如实报告：

- `read_control=false`；
- `edit_control=false`；
- `shell_control=false`；
- `external_directory_control=false`；
- `stop=true`、`cancellation=true`。

原因不是 Pi 没有 read/edit/bash 工具，而是 P5 没有证据证明 Studio 能在操作系统层限制这些工具只访问沙箱。当前能够保证的是：

1. Pi 的 cwd 是 ArcVellum 隔离 workspace；
2. 正式写回仍由现有 expected-output、diff、preflight 和事务写回控制；
3. 沙箱外部读取隔离不成立，因此 P5 只允许脱敏 fixture；
4. Pi 不进入普通项目、默认 Runtime 或安装包。

## 4. 同模型 A/B 门禁

Pi 真实 RPC 的 `get_available_models` 返回 0 个可用模型；`pi auth check --provider opencode --no-refresh --json` 返回：

```json
{"status":"not_ready","provider":"opencode","reason":"credentials_not_configured"}
```

因此当前不能让 Pi 与 OpenCode 基线 `opencode/deepseek-v4-flash-free` 在同 Provider、同模型、同任务下比较。按计划的证据纪律：

- 不运行不可归因的异模型 A/B；
- 不复制或读取 OpenCode 凭证；
- 不建立 Studio Provider/凭证层；
- 不把协议冒烟解释为速度、成本或文学质量提升；
- 不进入 P6 专用 Pi Worker。

## 5. 价值判断

### 已证实

- Pi 的 RPC 协议比解析终端文本更适合嵌入；请求、事件、会话、统计和取消具有明确机器合同。
- 独立协议模块与 Runtime Adapter 可以在不改变现有文学状态机的情况下接入。
- 默认禁用与实验入口足以让后续同模型测试可回滚、无产品残留。

### 未证实

- 首个真实活动是否比 OpenCode 快 25%；
- 总时长或成本是否改善 20%；
- preflight 首次通过率是否不低于 OpenCode；
- 文学盲评是否非劣；
- Pi Agent Core 专用工具面是否值得建设。

## 6. 回滚

P5 没有修改默认 Runtime、安装包或用户配置页面。回滚只需移除 `pi-rpc` 注册项、默认禁用配置、`runtimes/pi_rpc.py`、`integrations/pi_rpc/` 和实验 benchmark 参数；OpenCode 主链、P0-P4 benchmark 与文学工程内核不受影响。

## 7. 验证结果

- Pi 定向协议、取消、回收、隐私与 Runtime 合同测试：通过；
- 全量 Python：`973 passed, 1 skipped`；
- Vue/Vitest：`159 passed`；
- `python scripts/architecture_audit.py --json`：`ok: true`，无新增函数、文件或依赖债务；
- 版本同步与 compatibility surface：通过；
- 新增文件凭证与绝对用户路径扫描：通过；
- `git diff --check`：通过。

Pi 对沙箱的适用证据由两部分组成：Pi fixture 验证进程始终以隔离 workspace 为 cwd；既有沙箱回归验证 source 修改、额外文件、陈旧目标和中途写回失败都不能污染正式项目。该组合证明正式写回边界可复用，但不把它误述为 OS 级读取隔离。
