"""Additional observable Chinese style statistics, kept separate from controls.

The measurements are descriptive. POS tags and word boundaries are automatic
annotations, and punctuation/quotation features are surface proxies.
"""

from __future__ import annotations

from collections import Counter
from math import sqrt
from statistics import mean
from typing import Any

import jieba
import jieba.posseg as pseg

from .corpus import HAN


# The 35 characters in Table 1 of "Function Words for Chinese Authorship
# Attribution" (2012). We count characters per 1000 Han, not per 1000 words.
FUNCTION_CHARS = tuple("的是不了在有这为地也得就那以着之可么而然没于还只无又如但其此与把全被却")
PRONOUNS = {
    "first": frozenset({"我", "我们", "咱", "咱们", "俺", "俺们"}),
    "second": frozenset({"你", "你们", "您", "您们"}),
    "third": frozenset({"他", "他们", "她", "她们", "它", "它们", "其"}),
}
FINAL_PARTICLES = frozenset("吗呢吧啊呀嘛")
POS_KEYS = ("n", "v", "a", "d", "p", "c", "u", "r", "m", "q", "i", "o", "other")
FUNCTION_POS = frozenset({"d", "p", "c", "u", "o"})
SECONDARY_AXES = {
    "short_sentence_share_le20_han": "≤20汉字句/全部句",
    "long_sentence_share_gt30_han": ">30汉字句/全部句",
    "clause_segments_per_sentence_proxy": "片段/句",
    "quote_spans_per_1000_han": "引号片段/千汉字",
    "word_length_mean_han": "汉字/词",
    "word_mattr_50": "50词窗类型/词元",
    "activity_v_over_v_plus_a": "动词/(动词+形容词)",
    "nominality_n_over_n_plus_v": "名词/(名词+动词)",
    "function_pos_share_proxy": "功能类词性词元/全部词元",
}
SECONDARY_GROUP = {
    "word_length_mean_han": "lexical",
    "word_mattr_50": "lexical",
    "activity_v_over_v_plus_a": "grammar",
    "nominality_n_over_n_plus_v": "grammar",
    "function_pos_share_proxy": "grammar",
}


def secondary_summary_key(key: str) -> str:
    return SECONDARY_GROUP.get(key, "rhythm") + "." + key
SCALAR_PATHS = {
    **{key: ("rhythm", key) for key in (
        "short_sentence_share_le20_han", "long_sentence_share_gt30_han",
        "sentence_length_cv", "paragraph_length_cv", "clause_segments_per_sentence_proxy",
        "question_sentence_share", "exclamation_sentence_share",
        "sentence_final_particle_share_proxy", "quote_spans_per_1000_han",
        "quote_length_mean_han")},
    **{key: ("lexical", key) for key in (
        "word_length_mean_han", "word_mattr_50", "word_mattr_100",
        "word_mattr_150", "char_mattr_100")},
    **{f"word_length_share_{key}": ("lexical", "word_length_shares", key)
       for key in ("1", "2", "3", "4_plus")},
    **{f"pos_share_{key}": ("grammar", "pos_shares", key) for key in POS_KEYS},
    "function_pos_share_proxy": ("grammar", "function_pos_share_proxy"),
    "activity_v_over_v_plus_a": ("grammar", "activity_v_over_v_plus_a"),
    "descriptivity_a_over_v_plus_a": ("grammar", "descriptivity_a_over_v_plus_a"),
    "nominality_n_over_n_plus_v": ("grammar", "nominality_n_over_n_plus_v"),
    **{f"pronoun_per_1000_words_{key}": ("grammar", "pronoun_per_1000_words", key)
       for key in ("first", "second", "third")},
    **{f"function_char_per_1000_han_{key}": ("grammar", "function_character_per_1000_han", key)
       for key in FUNCTION_CHARS},
}


def scalar_values(row: dict[str, Any]) -> dict[str, float | None]:
    """Comparable, normalized scalar values; raw counts and top lists stay separate."""
    result: dict[str, float | None] = {}
    for key, path in SCALAR_PATHS.items():
        value: Any = row
        for part in path:
            value = value[part]
        result[key] = float(value) if value is not None else None
    return result


def _rate(count: int, denominator: int, scale: int = 1) -> float | None:
    return round(count * scale / denominator, 4) if denominator else None


def _cv(lengths: list[int]) -> float | None:
    if not lengths:
        return None
    center = mean(lengths)
    return round(sqrt(sum((value - center) ** 2 for value in lengths) / len(lengths)) / center, 4) if center else None


def mattr_components(tokens: list[str], width: int) -> tuple[int, int] | None:
    """Sum of distinct types and count of complete fixed-width windows."""
    if len(tokens) < width:
        return None
    counts = Counter(tokens[:width])
    distinct_total = len(counts)
    windows = 1
    for index in range(width, len(tokens)):
        outgoing = tokens[index - width]
        counts[outgoing] -= 1
        if counts[outgoing] == 0:
            del counts[outgoing]
        incoming = tokens[index]
        counts[incoming] += 1
        distinct_total += len(counts)
        windows += 1
    return distinct_total, windows


def mattr(tokens: list[str], width: int) -> float | None:
    """Moving average type/token ratio for full windows of a fixed width."""
    components = mattr_components(tokens, width)
    return round(components[0] / (components[1] * width), 4) if components else None


def extended_statistics(text: str) -> dict[str, Any]:
    # Import at call time so metrics.py can own the existing sentence rules.
    from .metrics import QUOTED, paragraphs, sentences

    chars = HAN.findall(text)
    han_total = len(chars)
    sentence_rows = sentences(text)
    sentence_lengths = [len(HAN.findall(row)) for row in sentence_rows]
    paragraph_lengths = [len(HAN.findall(row)) for row in paragraphs(text)]
    tagged = [(token.word, token.flag) for token in pseg.cut(text, HMM=False)
              if token.word and all(HAN.fullmatch(char) for char in token.word)]
    words = [word for word, _ in tagged]
    token_total = len(words)
    mattr_50_parts = mattr_components(words, 50)
    word_lengths = Counter(min(len(word), 4) for word in words)
    pos_counts = Counter()
    for _, tag in tagged:
        coarse = tag[0] if tag and tag[0] in POS_KEYS else "other"
        pos_counts[coarse] += 1
    pos_bigrams = Counter()
    for sentence in sentence_rows:
        tags = [token.flag[0] if token.flag and token.flag[0] in POS_KEYS else "other"
                for token in pseg.cut(sentence, HMM=False)
                if token.word and all(HAN.fullmatch(char) for char in token.word)]
        pos_bigrams.update(zip(tags, tags[1:]))
    pos_bigram_total = sum(pos_bigrams.values())
    function_counts = Counter(char for char in chars if char in FUNCTION_CHARS)
    function_word_counts = Counter(word for word, tag in tagged
                                   if tag and tag[0] in FUNCTION_POS)
    pronoun_counts = {person: sum(word in forms for word in words)
                      for person, forms in PRONOUNS.items()}
    quote_lengths = [len(HAN.findall(match.group(0))) for match in QUOTED.finditer(text)]
    final_particle_count = sum(
        bool(next((char for char in reversed(row) if HAN.fullmatch(char)), "") in FINAL_PARTICLES)
        for row in sentence_rows
    )
    question_count = sum(row.rstrip().endswith(("？", "?")) for row in sentence_rows)
    exclamation_count = sum(row.rstrip().endswith(("！", "!")) for row in sentence_rows)
    clause_boundaries = sum(row.count(mark) for row in sentence_rows for mark in ("，", ",", "；", ";", "：", ":"))
    return {
        "schema": "extended-style-statistics/v1",
        "tokenizer": {"name": "jieba.posseg", "version": jieba.__version__, "HMM": False},
        "sample": {"han_count": han_total, "word_token_count": token_total,
                   "sentence_count": len(sentence_rows), "paragraph_count": len(paragraph_lengths)},
        "rhythm": {
            "short_sentence_count_le20_han": sum(length <= 20 for length in sentence_lengths),
            "long_sentence_count_gt30_han": sum(length > 30 for length in sentence_lengths),
            "clause_segment_count_proxy": clause_boundaries + len(sentence_rows),
            "short_sentence_share_le20_han": _rate(sum(length <= 20 for length in sentence_lengths), len(sentence_lengths)),
            "long_sentence_share_gt30_han": _rate(sum(length > 30 for length in sentence_lengths), len(sentence_lengths)),
            "sentence_length_cv": _cv(sentence_lengths),
            "paragraph_length_cv": _cv(paragraph_lengths),
            "clause_segments_per_sentence_proxy": _rate(clause_boundaries + len(sentence_rows), len(sentence_rows)),
            "question_sentence_share": _rate(question_count, len(sentence_rows)),
            "exclamation_sentence_share": _rate(exclamation_count, len(sentence_rows)),
            "sentence_final_particle_share_proxy": _rate(final_particle_count, len(sentence_rows)),
            "quote_span_count": len(quote_lengths),
            "quote_spans_per_1000_han": _rate(len(quote_lengths), han_total, 1000),
            "quote_length_mean_han": round(mean(quote_lengths), 4) if quote_lengths else None,
        },
        "lexical": {
            "word_han_count": sum(map(len, words)),
            "word_mattr_50_window_count": mattr_50_parts[1] if mattr_50_parts else 0,
            "word_mattr_50_distinct_type_sum": mattr_50_parts[0] if mattr_50_parts else None,
            "word_length_counts": {"1": word_lengths[1], "2": word_lengths[2],
                                   "3": word_lengths[3], "4_plus": word_lengths[4]},
            "word_length_shares": {"1": _rate(word_lengths[1], token_total),
                                   "2": _rate(word_lengths[2], token_total),
                                   "3": _rate(word_lengths[3], token_total),
                                   "4_plus": _rate(word_lengths[4], token_total)},
            "word_length_mean_han": round(mean(map(len, words)), 4) if words else None,
            "word_mattr_50": round(mattr_50_parts[0] / (mattr_50_parts[1] * 50), 4)
            if mattr_50_parts else None,
            "word_mattr_100": mattr(words, 100),
            "word_mattr_150": mattr(words, 150),
            "char_mattr_100": mattr(chars, 100),
        },
        "grammar": {
            "pos_counts": {key: pos_counts[key] for key in POS_KEYS},
            "pos_shares": {key: _rate(pos_counts[key], token_total) for key in POS_KEYS},
            "pos_bigram_count": pos_bigram_total,
            "pos_bigram_top": [
                {"pair": f"{left}>{right}", "count": count,
                 "per_1000_pairs": _rate(count, pos_bigram_total, 1000)}
                for (left, right), count in sorted(pos_bigrams.items(),
                                                  key=lambda item: (-item[1], item[0]))[:12]
            ],
            "function_pos_share_proxy": _rate(sum(pos_counts[key] for key in FUNCTION_POS), token_total),
            "function_word_top": [
                {"word": word, "count": count,
                 "per_1000_words": _rate(count, token_total, 1000)}
                for word, count in sorted(function_word_counts.items(),
                                          key=lambda item: (-item[1], item[0]))[:12]
            ],
            "function_word_counts": dict(sorted(function_word_counts.items())),
            "activity_v_over_v_plus_a": _rate(pos_counts["v"], pos_counts["v"] + pos_counts["a"]),
            "descriptivity_a_over_v_plus_a": _rate(pos_counts["a"], pos_counts["v"] + pos_counts["a"]),
            "nominality_n_over_n_plus_v": _rate(pos_counts["n"], pos_counts["n"] + pos_counts["v"]),
            "function_character_counts": {char: function_counts[char] for char in FUNCTION_CHARS},
            "function_character_per_1000_han": {
                char: _rate(function_counts[char], han_total, 1000) for char in FUNCTION_CHARS
            },
            "pronoun_counts": pronoun_counts,
            "pronoun_per_1000_words": {
                person: _rate(count, token_total, 1000) for person, count in pronoun_counts.items()
            },
        },
        "measurement_notes": [
            "词与词性由固定版本 jieba 自动标注；短句在此定义为不超过 20 汉字，与 CAT-LLM 的汉字/拉丁/数字口径不同。",
            "词性二元组在句内计算，不跨句连接；自动词性标签不等于依存句法关系。",
            "MATTR 使用完整滑动词窗；不足窗口长度返回 null，不把短文本 TTR 充作同一指标。",
            "分句片段只按逗号、分号、冒号加一计数，不是依存句法树深度。",
            "引号范围可能包含引文，句末语气词与人称代词只是表层代理，不判定对白或叙事视角。",
            "Activity=V/(V+A)，Descriptivity=A/(V+A)，Nominality=N/(N+V)；公式与 Hu 和 He (2022) 一致，但本项目的中文自动词性标注器为 jieba.posseg，并非论文的 TreeTagger；分母为零返回 null。",
        ],
    }


def summarize_windows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Show window variation without treating windows as independent works."""
    from .metrics import percentile

    flattened = [scalar_values(row) for row in rows]
    summaries = {}
    for key, path in SCALAR_PATHS.items():
        values = [row[key] for row in flattened if row[key] is not None]
        family_key = ".".join(path) if len(path) == 2 else key
        summaries[family_key] = {
            "window_count": len(values),
            "p25": percentile(values, .25) if values else None,
            "median": percentile(values, .5) if values else None,
            "p75": percentile(values, .75) if values else None,
        }
    return summaries


def summarize_works(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe between-work variation; no interval or significance claim."""
    from .metrics import percentile

    summary = {}
    for key in SCALAR_PATHS:
        values = [row["features"][key] for row in rows if row["features"][key] is not None]
        summary[key] = {
            "work_count": len(values),
            "min": min(values) if values else None,
            "p25": percentile(values, .25) if values else None,
            "median": percentile(values, .5) if values else None,
            "p75": percentile(values, .75) if values else None,
            "max": max(values) if values else None,
        }
    return summary
