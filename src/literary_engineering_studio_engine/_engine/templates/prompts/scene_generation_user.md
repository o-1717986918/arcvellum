# 场景生成请求：{scene_id}

生成时间：{generated_at}

## 本场表达执行

若已挂载完整参考语料，先在内部为本场选择一篇表达主参照；再结合人物目标、scene turn 与相邻场景确定叙述声音：何处舒展，何处收紧，何处因信息或关系变化而变调，何处留白。让句法、段落、对白和意象一起完成这种变化；不要输出风格分析，也不要把清晰误写成通篇同速的动作说明。

## 当前场景 YAML

```yaml
{scene_text}
```

## 场景上下文包

{context_text}

## 场景创作编排包

{composition_text}

## 文风约束提示词 / Profile

{style_profile}

## 文风生成标准

{style_generation_standard}

## 标点规范约束

{punctuation_standard}

## 降低 AI 腔约束

{anti_ai_style}

## AgentReview 小修约束

{review_notes_standard}

## 生成前最终硬约束摘要

{generation_constraint_brief}

## 输出契约

{output_contract}
