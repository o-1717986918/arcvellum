# Prompt v3 Final A/B Gate

日期：2026-08-11

## 结论

Prompt v3 的 `structured-world-foundation` 与 `review-scene-candidate` 通过当前阶段门禁，可用于 Pi Worker 的精确路线、精确状态灰度。自适应推理预算仍不得改为产品级 enforced；prose、planning 和其他 creative 状态也不得据此批量开启。

## 编译结果

| 任务 | v2 字符 | v3 字符 | 降幅 | 重复率 | 结论 |
|---|---:|---:|---:|---:|---|
| Structured world foundation | 16,972 | 9,406 | 44.58% | 0% | 通过 |
| Scene candidate review | 23,883 | 14,317 | 40.05% | 0% | 通过 |

## 真实调用

每类 3 对交错 A/B，使用同一模型族、Pi Worker、独立项目与独立沙箱。12 个样本全部首次通过 preflight，v2/v3 repair 均为 0。

| 任务 | 版本 | 中位耗时 | 非缓存输入 | 总 token | 中位费用 |
|---|---|---:|---:|---:|---:|
| Structured | v2 | 62.0 s | 13,761 | 53,358 | $0.003617 |
| Structured | v3 | 55.8 s | 8,299 | 38,373 | $0.002806 |
| Review | v2 | 73.3 s | 18,668 | 72,617 | $0.005123 |
| Review | v3 | 77.3 s | 13,646 | 56,455 | $0.005062 |

Structured 的非缓存输入下降 39.69%，费用下降 22.42%，耗时下降 10.06%。Review 的非缓存输入下降 26.90%，总 token 下降 22.26%，但中位耗时上升 5.50%，费用只下降 1.19%。

## 匿名质量

在揭示 v2/v3 映射前，按 1-5 分对产物评分：

- Structured：具体性、因果可用性、内部一致性、范围纪律、下游可执行性。
- Review：判断准确性、义务覆盖、证据锚定、校准、修订可执行性、结构合法性。

结果：Structured v2/v3 中位分分别为 4.32/4.40；Review 分别为 4.77/4.80。v3 未发生匿名质量退化。全部 6 份 review 都识别出测试正文缺失“守钟人害怕指控盟友”的内部冲突，并给出 `revise_required`。新 `object_shapes` 合同下，3 份 v3 review 的 `canon_writeback` 与 `new_character_register` 均一次输出为合法对象。

## 决策

1. Prompt v3：structured/review 满足定向灰度条件。
2. Prompt v3 扩展：prose、planning 和其他 creative 任务继续 hold，逐类独立 A/B。
3. ReasoningBudget：继续 shadow。当前数据未满足总费用下降 20% 与总耗时下降 15% 的双门禁。
4. v2 fallback：保留至少一个版本周期。Review v3 的字符门槛余量仍小，不应再向首轮 Prompt 添加重复说明。

机器可读证据见 `prompt-v3-final-ab-gate-2026-08-11.json`；单次样本见 `prompt-ab-final-*-2026-08-11.json`。
