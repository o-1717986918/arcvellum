# Phase 18：文风评测增强

## 目标

把 `style-profile` 的评测样例推进为可执行命令，用于评估候选文本与目标风格 profile、参考文本之间的相似度和原创边界风险。

## 新增命令

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench style-eval work/demo-work/style/demo-author `
  --reference work/demo-work/eval/reference.txt `
  --candidate work/demo-work/eval/candidate.txt `
  --mode back-translation
```

支持模式：

- `back-translation`
- `outline-expansion`
- `blind-review`

## 输出

默认输出到：

```text
{profile_dir}/evaluation_results/{mode}/
```

包含：

- `style_eval_{timestamp}.json`
- `style_eval_{timestamp}.md`

## 评分维度

- 句长和段落节奏
- 高频标点相似度
- 高频二字组合重合度
- 感官/意象分布
- 叙述距离：心理词密度、对话密度
- 长度结构接近度
- 原创性边界：连续汉字窗口重叠风险

## 边界

- 分数是工程评测辅助，不代表可以直接发布。
- 公版/授权语料可用于精确风格复现评测。
- 非授权作者语料仅可做高层技法抽象。
- 高重合风险应优先改写为“机制相似、表达不同”。
