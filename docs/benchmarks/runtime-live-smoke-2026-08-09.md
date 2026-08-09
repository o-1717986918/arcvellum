# ArcVellum OpenCode Live Smoke Baseline

- 日期：2026-08-09
- case：`analysis-scene-roleplay`
- 任务类别：analysis / creative
- Runner：OpenCode `1.18.3`
- 模型：`opencode/deepseek-v4-flash-free`
- 最终状态：`waiting_writeback`
- 内容边界：报告不含 prompt、正文、reasoning 文本、路径、凭证或工具载荷

| 阶段 | 耗时 |
|---|---:|
| 进程就绪 | 1,224 ms |
| 会话建立 | 1,398 ms |
| Prompt 提交 | 1,578 ms |
| 首个 reasoning 活性 | 12,013 ms |
| 首个公开事件 / 工具调用 | 174,787 ms |
| 首个有效输出 | 210,151 ms |
| 总耗时 | 232,568 ms |

## 结论

OpenCode 进程启动不是本样本的主要瓶颈。模型在 12 秒左右已经产生 reasoning 活性，但现有公开活性要等到约 175 秒后的工具调用；这会让 UI 和 watchdog 长时间表现为“没有活动”。任务最终通过执行与预检并进入写回审批，因此本样本不是失败或空转。

本次 prepared context 为 40,303 字符，生产模式仍是 `shadow`，prepared-context cache 仍为 `disabled`。P3 应先让内容安全的 reasoning activity 进入活性判定和瞬时事件流；P4 再分别验证 bounded context 与 cache，避免同时启用后无法归因。

机器可读证据见 `runtime-live-smoke-2026-08-09.json`。
