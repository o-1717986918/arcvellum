from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".md"}
SENTENCE_END = "。！？!?；;"
PUNCTUATION = "，。！？；：、,.!?;:\"'“”‘’（）()《》——…"
SENSORY_LEXICON = {
    "视觉": ["光", "影", "黑", "白", "红", "青", "暗", "亮", "月", "灯", "眼", "看", "颜色"],
    "听觉": ["声", "响", "听", "喊", "叫", "风", "雨", "钟", "脚步", "沉默"],
    "触觉": ["冷", "热", "湿", "疼", "痛", "软", "硬", "手", "皮肤"],
    "嗅味": ["香", "臭", "腥", "苦", "甜", "酒", "烟", "气味"],
    "空间": ["门", "窗", "街", "屋", "城", "路", "桥", "河", "院", "房", "墙"],
}
THOUGHT_WORDS = ["想", "觉得", "知道", "明白", "记得", "忘", "怕", "希望", "相信", "怀疑"]
DIALOGUE_MARKS = ["“", "”", "\"", "："]


@dataclass(frozen=True)
class StyleCompileOptions:
    corpus: Path
    output_dir: Path
    name: str
    author: str = ""
    mode: str = "public_domain_or_authorized"
    source_note: str = ""


@dataclass(frozen=True)
class StyleCompileResult:
    output_dir: Path
    profile_path: Path
    metrics_path: Path
    corpus_manifest_path: Path
    evaluation_dir: Path
    source_count: int


def _iter_text_files(corpus: Path) -> list[Path]:
    root = corpus.resolve()
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise FileNotFoundError(f"corpus not found: {root}")
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS)


def _read_sources(files: list[Path]) -> list[tuple[Path, str]]:
    sources = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if text:
            sources.append((path, text))
    return sources


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])", text)
    return [p.strip() for p in parts if p.strip()]


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _cjk_chars(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]", text)


def _bigrams(chars: list[str]) -> list[str]:
    return [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]


def _avg(nums: list[int]) -> float:
    return round(sum(nums) / len(nums), 2) if nums else 0.0


def _sentence_bucket(length: int) -> str:
    if length <= 10:
        return "short_1_10"
    if length <= 20:
        return "medium_11_20"
    if length <= 40:
        return "long_21_40"
    return "very_long_41_plus"


def _top(counter: Counter, limit: int = 20) -> list[dict]:
    return [{"item": item, "count": count} for item, count in counter.most_common(limit)]


def _lexicon_counts(text: str, lexicon: dict[str, list[str]]) -> dict[str, int]:
    result = {}
    for label, words in lexicon.items():
        result[label] = sum(text.count(word) for word in words)
    return result


def analyze_style(corpus: Path) -> dict:
    files = _iter_text_files(corpus)
    sources = _read_sources(files)
    if not sources:
        raise ValueError(f"no readable text sources found in: {corpus}")

    full_text = "\n\n".join(text for _, text in sources)
    sentences = _sentences(full_text)
    paragraphs = _paragraphs(full_text)
    chars = _cjk_chars(full_text)
    sentence_lengths = [len(_cjk_chars(sentence)) for sentence in sentences]
    paragraph_lengths = [len(_cjk_chars(paragraph)) for paragraph in paragraphs]
    punctuation_counts = Counter(ch for ch in full_text if ch in PUNCTUATION)
    char_counts = Counter(chars)
    bigram_counts = Counter(_bigrams(chars))
    sentence_buckets = Counter(_sentence_bucket(length) for length in sentence_lengths)
    sensory_counts = _lexicon_counts(full_text, SENSORY_LEXICON)
    thought_count = sum(full_text.count(word) for word in THOUGHT_WORDS)
    dialogue_mark_count = sum(full_text.count(mark) for mark in DIALOGUE_MARKS)

    return {
        "source_count": len(sources),
        "sources": [{"path": str(path), "chars": len(_cjk_chars(text))} for path, text in sources],
        "char_count": len(chars),
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "avg_sentence_chars": _avg(sentence_lengths),
        "avg_paragraph_chars": _avg(paragraph_lengths),
        "sentence_length_distribution": dict(sentence_buckets),
        "punctuation_top": _top(punctuation_counts, 30),
        "top_chars": _top(char_counts, 30),
        "top_bigrams": _top(bigram_counts, 30),
        "sensory_counts": sensory_counts,
        "thought_word_count": thought_count,
        "dialogue_mark_count": dialogue_mark_count,
        "dialogue_density": round(dialogue_mark_count / max(len(sentences), 1), 3),
        "thought_density": round(thought_count / max(len(sentences), 1), 3),
    }


def _format_top(items: list[dict], limit: int = 12) -> str:
    if not items:
        return "无"
    return "、".join(f"{item['item']}({item['count']})" for item in items[:limit])


def _profile_markdown(options: StyleCompileOptions, metrics: dict) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    sensory = metrics["sensory_counts"]
    dominant_sensory = sorted(sensory.items(), key=lambda item: item[1], reverse=True)
    return f"""# {options.name} 风格 Profile

生成时间：{generated_at}

## 基本信息

- 风格名称：{options.name}
- 作者/来源：{options.author or "未指定"}
- 工作模式：{options.mode}
- 来源说明：{options.source_note or "未填写"}
- 语料文件数：{metrics["source_count"]}
- 总汉字数：{metrics["char_count"]}

## 表层风格指纹

- 段落数：{metrics["paragraph_count"]}
- 句子数：{metrics["sentence_count"]}
- 平均句长：{metrics["avg_sentence_chars"]} 汉字
- 平均段落长度：{metrics["avg_paragraph_chars"]} 汉字
- 对话标记密度：{metrics["dialogue_density"]}
- 心理词密度：{metrics["thought_density"]}

### 句长分布

```json
{json.dumps(metrics["sentence_length_distribution"], ensure_ascii=False, indent=2)}
```

### 高频标点

{_format_top(metrics["punctuation_top"])}

### 高频汉字

{_format_top(metrics["top_chars"])}

### 高频二字组合

{_format_top(metrics["top_bigrams"])}

## 意象和感官倾向

{chr(10).join(f"- {name}：{count}" for name, count in dominant_sensory)}

## 初步风格判断

- 若平均句长偏低，生成时应控制短句、断句和节奏推进。
- 若平均句长偏高，生成时应允许复合句、铺陈和更长心理/景物段落。
- 对话标记密度高时，正文生成应保留人物交锋和口语节奏。
- 心理词密度高时，应增加内心判断、记忆、迟疑和自我辩驳。
- 感官倾向最高的类别应进入意象调度器，作为场景描写的首选感官通道。

## 生成规则草案

### 必须保持

- 句长分布应接近当前 profile。
- 高频标点节奏应作为风格约束，而不是机械复制。
- 意象和感官倾向应按主题服务，不作随机装饰。

### 可以变化

- 人物、时代、世界观和事件必须服务原创项目。
- 高频词组可转化为抽象节奏或意象逻辑，不要求逐字复用。

### 禁止倾向

- 不直接复刻原文段落。
- 不只模仿几个显眼词语。
- 不因追求相似而破坏原创 canon 和人物逻辑。

## 评测方法

- 回译评测：见 `evaluation_cases/back_translation.md`。
- 大纲扩写评测：见 `evaluation_cases/outline_expansion.md`。
- 盲评归属：见 `evaluation_cases/blind_review.md`。
"""


def _manifest(options: StyleCompileOptions, metrics: dict) -> str:
    sources = "\n".join(
        f"  - path: {json.dumps(src['path'], ensure_ascii=False)}\n    chars: {src['chars']}"
        for src in metrics["sources"]
    )
    return f"""schema: lew-corpus-manifest/v0.1
name: {json.dumps(options.name, ensure_ascii=False)}
author: {json.dumps(options.author, ensure_ascii=False)}
mode: {options.mode}
source_note: {json.dumps(options.source_note, ensure_ascii=False)}
created_at: {json.dumps(datetime.now(timezone.utc).isoformat())}
source_count: {metrics["source_count"]}
sources:
{sources}
"""


def _write_evaluation_cases(output_dir: Path, options: StyleCompileOptions) -> Path:
    eval_dir = output_dir / "evaluation_cases"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "back_translation.md").write_text(
        f"""# 回译评测

## 目标

测试 `{options.name}` profile 对表层风格、句法节奏和叙述口吻的复现能力。

## 流程

1. 选取语料中的一段公版/授权原文。
2. 将其翻译为英文。
3. 在未读取原文的独立 Agent 中，只提供英文和本 profile。
4. 要求 Agent 回译为中文。
5. 比较回译文本与原文的句法、节奏、意象和叙述距离。

## 评分

- 句法节奏：0-25
- 叙述距离：0-25
- 意象和感官：0-20
- 人物/心理呈现：0-15
- 原创性边界：0-15
""",
        encoding="utf-8",
    )
    (eval_dir / "outline_expansion.md").write_text(
        f"""# 大纲扩写评测

## 目标

测试 `{options.name}` profile 能否从纯大纲恢复相近的叙述结构和文体机制。

## 流程

1. 将一段原文压缩为只含事件、人物和情绪转折的大纲。
2. 在独立 Agent 中提供大纲和本 profile。
3. 要求扩写到与原文相近字数。
4. 比较结构节奏、叙事视角、心理描写和意象调度。

## 注意

评测目标是风格机制，不是逐字复刻。
""",
        encoding="utf-8",
    )
    (eval_dir / "blind_review.md").write_text(
        f"""# 盲评归属

## 目标

测试 `{options.name}` profile 生成文本是否能被独立评审识别出目标风格特征。

## 流程

1. 准备目标 profile 生成文本。
2. 准备其他风格 profile 生成文本。
3. 隐去来源，让评审 Agent 判断每段更接近哪类风格。
4. 要求评审必须给出证据：句法、标点、意象、叙述距离、人物心理。

## 输出

- 归属判断。
- 证据列表。
- 相似但不原创的风险。
- 改进建议。
""",
        encoding="utf-8",
    )
    return eval_dir


def compile_style_profile(options: StyleCompileOptions) -> StyleCompileResult:
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = analyze_style(options.corpus)

    metrics_path = output_dir / "style_metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    profile_path = output_dir / "style-profile.md"
    profile_path.write_text(_profile_markdown(options, metrics), encoding="utf-8")

    manifest_path = output_dir / "corpus_manifest.yaml"
    manifest_path.write_text(_manifest(options, metrics), encoding="utf-8")

    eval_dir = _write_evaluation_cases(output_dir, options)

    return StyleCompileResult(
        output_dir=output_dir,
        profile_path=profile_path,
        metrics_path=metrics_path,
        corpus_manifest_path=manifest_path,
        evaluation_dir=eval_dir,
        source_count=metrics["source_count"],
    )
