# Prompt v3 Round 2 工具拒绝诊断

> 日期：2026-08-11  
> 状态：已定位并修复；失败样本保留，交错 A/B 尚未完成

## 结论

Round 2 的 structured v2 与 v3 都被记录为 `no_progress`，但事件序列表明它们不是相同故障，也不能归因于模型连接：

- v2 完成任务合同读取并生成了较长内容，随后 `write_expected_output` 被拒；旧 Worker 没有持久化安全错误原因，因此不能进一步断言具体参数错误。
- v3 完成任务合同与一份 recovery sidecar 的读取，随后第二次 `read_authorized_source` 被拒。模型可见文本表明它试图继续读取 sidecar 提及、但不在当前授权集中的 schema 资料。
- 两条运行都被旧 no-progress 摘要覆盖成同一句错误，妨碍归因。

对应的内容安全原始指标保存在：

- `prompt-ab-structured-r2-v2-2026-08-11.json`
- `prompt-ab-structured-r2-v3-2026-08-11.json`

## 修复

1. Pi Worker 的 `tool.denied` 增加清洗后的错误原因，不保存工具参数、作品正文、绝对路径或凭证。
2. 最近工具错误进入 progress digest。第一次新错误允许一次有界纠错；重复同一错误仍由 no-progress Gate 硬停止。
3. Engine 将资产 schema 名称、固定值、必填字段和字段类型写入机器合同，Prompt v3 不再要求模型从 sidecar 猜 schema。
4. 工具版 Prompt 过滤“读取 sidecar”和“完成 sidecar”这类 Studio 已接管的旧流程指令。
5. recovery sidecar 仍可按需读取，但明确标记为非权威恢复资料；其命令、路径和回执指令不能覆盖当前 Allowed Outputs。

## 验证

- Pi Worker：25 项测试通过，TypeScript 构建通过。
- Studio：62 项 Prompt、资产、任务合同与 Worker 定向测试通过。
- Studio 全量回归：首次 1008 项中 1 项后台 job 等待超时；该用例隔离运行通过，随后未修改代码的完整重跑 1008 项通过、1 项按设计跳过。未放宽生产 Gate 或测试超时。
- Prompt compile canary：structured 下降 45.95%，review 下降 40.0017%，两类均通过 Prompt Lint。
- Architecture Audit：32 个既有 file debts、200 个既有 function debts、0 循环、0 新违规。
- 变更文件凭证/绝对用户路径扫描为 0，`git diff --check` 通过。

## 门禁判断

本修复只恢复可归因性和合同一致性，不把失败样本改写为成功。P3/P4 仍需完成三轮交错 A/B 与文学盲评；在此之前 Prompt v3 保持实验性，P7 不得扩展到 prose/planning。
