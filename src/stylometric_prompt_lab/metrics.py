"""Interpretable measurements for modern Chinese narrative prose."""

from __future__ import annotations

from collections import Counter
import math
import re
from statistics import mean
from typing import Any

import jieba

from .corpus import Corpus, HAN
from .io import digest


WINDOW_HAN = 1200
MIN_TAIL_HAN = 500
AXES = {
    "sentence_length_han": "汉字/句",
    "paragraph_length_han": "汉字/段",
    "dialogue_share": "对白汉字/全部汉字",
    "punctuation_per_1000_han": "处/千汉字",
}
PUNCTUATION = {
    "，": "，", ",": "，", "。": "。", ".": "。", "！": "！", "!": "！",
    "？": "？", "?": "？", "；": "；", ";": "；", "：": "：", ":": "：",
    "、": "、", "—": "—", "…": "…", "“": "引号", "”": "引号",
    '"': "引号", "「": "引号", "」": "引号", "『": "引号", "』": "引号",
}
SENTENCE_END = re.compile(r"(?<=[。！？!?；;])|(?<=\.)(?!\d)")
QUOTED = re.compile(r"“([^”]+)”|「([^」]+)」|『([^』]+)』|\"([^\"]+)\"", re.S)


def han_count(text: str) -> int:
    return len(HAN.findall(text))


def percentile(values: list[float] | list[int], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 4)


def sentences(text: str) -> list[str]:
    return [part.strip() for paragraph in paragraphs(text)
            for part in SENTENCE_END.split(paragraph) if part.strip() and han_count(part)]


def paragraphs(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and han_count(line)]


def windows(text: str) -> list[str]:
    units: list[str] = []
    for para in paragraphs(text):
        parts = sentences(para)
        units.extend(part + ("\n" if index == len(parts) - 1 else "") for index, part in enumerate(parts))
    result: list[str] = []
    pending: list[str] = []
    size = 0
    for unit in units:
        if han_count(unit) > WINDOW_HAN * 2:
            chunks = [unit[start:start + WINDOW_HAN] for start in range(0, len(unit), WINDOW_HAN)]
        else:
            chunks = [unit]
        for chunk in chunks:
            pending.append(chunk)
            size += han_count(chunk)
            if size >= WINDOW_HAN:
                result.append("".join(pending).strip())
                pending, size = [], 0
    if pending:
        tail = "".join(pending).strip()
        if result and size < MIN_TAIL_HAN:
            result[-1] += "\n" + tail
        else:
            result.append(tail)
    return result


def measure(text: str) -> dict[str, Any]:
    total = han_count(text)
    sentence_lengths = [han_count(item) for item in sentences(text)]
    paragraph_lengths = [han_count(item) for item in paragraphs(text)]
    dialogue_chars = sum(han_count(match.group(0)) for match in QUOTED.finditer(text))
    punctuation = Counter(
        PUNCTUATION[char] for index, char in enumerate(text)
        if char in PUNCTUATION
        and not (char in {".", ","} and 0 < index < len(text) - 1
                 and text[index - 1].isdigit() and text[index + 1].isdigit())
    )
    punctuation_total = sum(punctuation.values())
    return {
        "han_count": total,
        "sentence_count": len(sentence_lengths),
        "paragraph_count": len(paragraph_lengths),
        "dialogue_han_count": dialogue_chars,
        "punctuation_count": punctuation_total,
        "sentence_length_distribution": _distribution(sentence_lengths),
        "paragraph_length_distribution": _distribution(paragraph_lengths),
        "axes": {
            "sentence_length_han": round(mean(sentence_lengths), 4) if sentence_lengths else 0.0,
            "paragraph_length_han": round(mean(paragraph_lengths), 4) if paragraph_lengths else 0.0,
            "dialogue_share": round(dialogue_chars / total, 4) if total else 0.0,
            "punctuation_per_1000_han": round(1000 * punctuation_total / total, 4) if total else 0.0,
        },
        "punctuation_counts": dict(sorted(punctuation.items())),
        "punctuation_per_1000_han_by_mark": {
            mark: round(count * 1000 / total, 4) for mark, count in sorted(punctuation.items())
        } if total else {},
    }


def _distribution(values: list[int]) -> dict[str, float]:
    return {"p25": percentile(values, 0.25), "median": percentile(values, 0.5),
            "p75": percentile(values, 0.75), "mean": round(mean(values), 4) if values else 0.0}


def _top(counter: Counter[str], total: int, limit: int = 20) -> list[dict[str, Any]]:
    return [{"item": item, "count": count, "per_1000_han": round(1000 * count / total, 4)}
            for item, count in sorted(counter.items(), key=lambda row: (-row[1], row[0]))[:limit]]


def diagnostics(text: str) -> dict[str, Any]:
    chars = HAN.findall(text)
    total = len(chars)
    words = [word for word in jieba.cut(text, HMM=False) if len(word) >= 2 and all(HAN.fullmatch(char) for char in word)]
    bigrams = Counter(
        joined[index:index + 2]
        for sentence in sentences(text)
        for joined in ["".join(HAN.findall(sentence))]
        for index in range(len(joined) - 1)
    )
    return {
        "char_top": _top(Counter(chars), total),
        "word_top": _top(Counter(words), total),
        "char_bigram_top": _top(bigrams, total, 50),
        "tokenizer": {"name": "jieba", "version": jieba.__version__, "HMM": False},
        "warning": "字词和二元组可能反映题材；不作为单独的生成目标。",
    }


def _axis_summary(window_rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [float(row["axes"][key]) for row in window_rows]
    median = percentile(values, 0.5)
    return {
        "unit": AXES[key], "window_count": len(values),
        "p25": percentile(values, 0.25), "median": median,
        "p75": percentile(values, 0.75),
        "min": min(values), "max": max(values),
        "window_values": values,
    }


def _suggested_band(summary: dict[str, Any], key: str) -> dict[str, Any]:
    center = float(summary["median"])
    spread = max((float(summary["p75"]) - float(summary["p25"])) / 2,
                 center * 0.1, 0.02 if key == "dialogue_share" else 1.0)
    lower = max(1.0 if key in {"sentence_length_han", "paragraph_length_han"} else 0.0, center - spread)
    upper = center + spread
    if key == "dialogue_share":
        upper = min(1.0, upper)
    return {"min": round(lower, 3), "max": round(upper, 3), "unit": AXES[key]}


def build_profile(corpus: Corpus) -> tuple[dict[str, Any], dict[str, Any]]:
    from .extended_metrics import (SECONDARY_AXES, extended_statistics, scalar_values,
                                   secondary_summary_key,
                                   summarize_windows, summarize_works)
    from .keyword_metrics import content_keywords

    train = [source for source in corpus.sources if source.split == "train"]
    holdout = [source for source in corpus.sources if source.split == "holdout"]
    window_rows: list[dict[str, Any]] = []
    extended_windows: list[dict[str, Any]] = []
    for source in train:
        for index, text in enumerate(windows(source.text)):
            window_rows.append({"source_id": source.source_id, "window_index": index, **measure(text)})
            extended_windows.append(extended_statistics(text))
    combined = "\n".join(source.text for source in train)
    holdout_combined = "\n".join(source.text for source in holdout)
    combined_measure = measure(combined)
    by_work: dict[str, list[Any]] = {}
    for source in train:
        by_work.setdefault(source.work_id, []).append(source)
    work_estimates = []
    axis_work_estimates = []
    work_extended = []
    for work_id, work_sources in sorted(by_work.items()):
        work_text = "\n".join(source.text for source in work_sources)
        estimate = extended_statistics(work_text)
        work_measure = measure(work_text)
        work_extended.append(estimate)
        axis_work_estimates.append({
            "work_id": work_id, "topics": sorted({source.topic for source in work_sources}),
            "han_count": work_measure["han_count"], "axes": work_measure["axes"],
            "sentence_count": work_measure["sentence_count"],
            "paragraph_count": work_measure["paragraph_count"],
        })
        work_estimates.append({
            "work_id": work_id, "topics": sorted({source.topic for source in work_sources}),
            "han_count": estimate["sample"]["han_count"],
            "features": scalar_values(estimate),
        })
    train_diag = diagnostics(combined)
    holdout_diag = diagnostics(holdout_combined)
    extended = extended_statistics(combined)
    for key in ("word_mattr_50", "word_mattr_100", "word_mattr_150", "char_mattr_100"):
        values = [item["lexical"][key] for item in work_extended if item["lexical"][key] is not None]
        extended["lexical"][key] = round(mean(values), 4) if values else None
    extended["lexical"]["mattr_aggregation"] = "equal-work-mean; no window crosses work boundary"
    extended["lexical"]["mattr_valid_work_counts"] = {
        key: sum(item["lexical"][key] is not None for item in work_extended)
        for key in ("word_mattr_50", "word_mattr_100", "word_mattr_150", "char_mattr_100")
    }
    warnings = list(corpus.warnings)
    if len(window_rows) < 3:
        warnings.append("fewer than three training windows; target ranges have low stability")
    profile = {
        "schema": "stylometric-profile/v1", "analysis_version": "0.5.2",
        "label": corpus.label,
        "source_evidence": [item.public() for item in corpus.sources],
        "source_digest": digest([item.public() for item in corpus.sources]),
        "train_han_count": sum(item.han_count for item in train),
        "holdout_han_count": sum(item.han_count for item in holdout),
        "window_han_target": WINDOW_HAN, "window_count": len(window_rows),
        "axes": {key: _axis_summary(window_rows, key) for key in AXES},
        "axis_work_estimates": axis_work_estimates,
        "axis_work_summary": {
            key: {
                "unit": AXES[key], "work_count": len(axis_work_estimates),
                "min": min(row["axes"][key] for row in axis_work_estimates),
                "p25": percentile([row["axes"][key] for row in axis_work_estimates], .25),
                "median": percentile([row["axes"][key] for row in axis_work_estimates], .5),
                "p75": percentile([row["axes"][key] for row in axis_work_estimates], .75),
                "max": max(row["axes"][key] for row in axis_work_estimates),
                "aggregation": "equal-work descriptive distribution; no significance test",
            } for key in AXES
        },
        "sentence_count": combined_measure["sentence_count"],
        "paragraph_count": combined_measure["paragraph_count"],
        "sentence_length_distribution": combined_measure["sentence_length_distribution"],
        "paragraph_length_distribution": combined_measure["paragraph_length_distribution"],
        "punctuation_per_1000_han_by_mark": combined_measure["punctuation_per_1000_han_by_mark"],
        "diagnostics": train_diag,
        "extended_diagnostics": extended,
        "extended_window_summary": summarize_windows(extended_windows),
        "extended_work_estimates": work_estimates,
        "extended_work_summary": summarize_works(work_estimates),
        "content_keyword_diagnostics": content_keywords(corpus),
        "holdout_diagnostic": {
            "top50_char_bigram_cosine": _cosine(train_diag["char_bigram_top"], holdout_diag["char_bigram_top"]),
            "note": "只作跨作品/题材诊断，非生成文风质量分数。",
        },
        "warnings": warnings,
    }
    profile["profile_sha256"] = digest(profile)
    secondary_axes = {}
    for key, unit in SECONDARY_AXES.items():
        summary = profile["extended_window_summary"][secondary_summary_key(key)]
        if summary["window_count"] == 0:
            continue
        pad = .1 if key in {"short_sentence_share_le20_han", "long_sentence_share_gt30_han",
                             "word_mattr_50", "activity_v_over_v_plus_a",
                             "nominality_n_over_n_plus_v", "function_pos_share_proxy"} else (
            .3 if key == "clause_segments_per_sentence_proxy" else
            2.0 if key == "quote_spans_per_1000_han" else .15)
        floor = 1.0 if key in {"clause_segments_per_sentence_proxy", "word_length_mean_han"} else 0.0
        ceiling = 1.0 if key in {"short_sentence_share_le20_han", "long_sentence_share_gt30_han",
                                  "word_mattr_50", "activity_v_over_v_plus_a",
                                  "nominality_n_over_n_plus_v", "function_pos_share_proxy"} else float("inf")
        secondary_axes[key] = {
            "min": round(max(floor, float(summary["p25"]) - pad), 3),
            "max": round(min(ceiling, float(summary["p75"]) + pad), 3),
            "unit": unit,
        }
    controls = {
        "schema": "style-controls/v1", "profile_sha256": profile["profile_sha256"],
        "axes": {key: _suggested_band(profile["axes"][key], key) for key in AXES},
        "secondary_axes": secondary_axes if len(secondary_axes) == len(SECONDARY_AXES) else {},
        "lexical_targets": [
            {"word": row["word"], "min": round(row["per_1000_words"] * .65, 3),
             "max": round(row["per_1000_words"] * 1.35, 3), "unit": "次/千词元"}
            for row in extended["grammar"]["function_word_top"] if row["count"] >= 2
        ][:4],
    }
    return profile, controls


def _cosine(left_items: list[dict[str, Any]], right_items: list[dict[str, Any]]) -> float:
    left = {str(row["item"]): float(row["per_1000_han"]) for row in left_items}
    right = {str(row["item"]): float(row["per_1000_han"]) for row in right_items}
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    norm_left = math.sqrt(sum(value * value for value in left.values()))
    norm_right = math.sqrt(sum(value * value for value in right.values()))
    return round(dot / (norm_left * norm_right), 4) if norm_left and norm_right else 0.0
