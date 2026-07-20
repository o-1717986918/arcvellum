"""Style evaluation reports for back-translation and outline expansion tests."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .style_compiler import analyze_style


STYLE_EVAL_MODES = {"back-translation", "outline-expansion", "blind-review"}


@dataclass(frozen=True)
class StyleEvalOptions:
    profile_dir: Path
    reference: Path
    candidate: Path
    mode: str = "back-translation"
    out_dir: Path | None = None


@dataclass(frozen=True)
class StyleEvalResult:
    report_path: Path
    metrics_path: Path
    mode: str
    overall_score: float
    risk_level: str


def evaluate_style(options: StyleEvalOptions) -> StyleEvalResult:
    if options.mode not in STYLE_EVAL_MODES:
        raise ValueError(f"unknown style eval mode: {options.mode}. valid: {', '.join(sorted(STYLE_EVAL_MODES))}")

    profile_dir = options.profile_dir.resolve()
    reference = options.reference.resolve()
    candidate = options.candidate.resolve()
    if not profile_dir.is_dir():
        raise FileNotFoundError(f"profile dir not found: {profile_dir}")
    if not reference.is_file():
        raise FileNotFoundError(f"reference text not found: {reference}")
    if not candidate.is_file():
        raise FileNotFoundError(f"candidate text not found: {candidate}")

    profile_metrics = _load_profile_metrics(profile_dir)
    reference_metrics = analyze_style(reference)
    candidate_metrics = analyze_style(candidate)
    reference_text = reference.read_text(encoding="utf-8", errors="ignore")
    candidate_text = candidate.read_text(encoding="utf-8", errors="ignore")

    scores = _score_style_match(profile_metrics, reference_metrics, candidate_metrics, reference_text, candidate_text)
    risk_level = _risk_level(scores["originality_boundary"]["risk_ratio"], scores["overall"])

    out_dir = options.out_dir or profile_dir / "evaluation_results" / options.mode
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    metrics_path = out_dir / f"style_eval_{stamp}.json"
    report_path = out_dir / f"style_eval_{stamp}.md"

    payload = {
        "schema": "literary-engineering-workbench/style-eval/v0.1",
        "mode": options.mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile_dir": str(profile_dir),
        "reference": str(reference),
        "candidate": str(candidate),
        "overall_score": scores["overall"],
        "risk_level": risk_level,
        "scores": scores,
    }
    metrics_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(payload, profile_metrics, reference_metrics, candidate_metrics), encoding="utf-8")
    return StyleEvalResult(
        report_path=report_path,
        metrics_path=metrics_path,
        mode=options.mode,
        overall_score=scores["overall"],
        risk_level=risk_level,
    )


def _load_profile_metrics(profile_dir: Path) -> dict:
    path = profile_dir / "style_metrics.json"
    if not path.exists():
        raise FileNotFoundError(f"style metrics not found: {path}. run style-profile first")
    return json.loads(path.read_text(encoding="utf-8"))


def _score_style_match(
    profile: dict,
    reference: dict,
    candidate: dict,
    reference_text: str,
    candidate_text: str,
) -> dict[str, object]:
    rhythm = _rhythm_score(profile, reference, candidate)
    punctuation = _counter_similarity_score(profile.get("punctuation_top", []), candidate.get("punctuation_top", []))
    lexical = _weighted_overlap_score(reference.get("top_bigrams", []), candidate.get("top_bigrams", []))
    sensory = _dict_vector_score(profile.get("sensory_counts", {}), candidate.get("sensory_counts", {}))
    narrative = _density_score(profile, reference, candidate)
    structure = _structure_score(reference, candidate)
    originality = _originality_score(reference_text, candidate_text)

    overall = round(
        rhythm * 0.20
        + punctuation * 0.15
        + lexical * 0.15
        + sensory * 0.15
        + narrative * 0.15
        + structure * 0.10
        + originality["score"] * 0.10,
        2,
    )
    return {
        "overall": overall,
        "rhythm": {"score": rhythm, "weight": 20},
        "punctuation": {"score": punctuation, "weight": 15},
        "lexical_bigrams": {"score": lexical, "weight": 15},
        "sensory_profile": {"score": sensory, "weight": 15},
        "narrative_distance": {"score": narrative, "weight": 15},
        "structure_length": {"score": structure, "weight": 10},
        "originality_boundary": originality | {"weight": 10},
    }


def _rhythm_score(profile: dict, reference: dict, candidate: dict) -> float:
    profile_sentence = float(profile.get("avg_sentence_chars", 0))
    reference_sentence = float(reference.get("avg_sentence_chars", 0))
    candidate_sentence = float(candidate.get("avg_sentence_chars", 0))
    target = (profile_sentence + reference_sentence) / 2 if profile_sentence and reference_sentence else profile_sentence or reference_sentence
    sentence_score = _ratio_score(target, candidate_sentence)
    profile_para = float(profile.get("avg_paragraph_chars", 0))
    reference_para = float(reference.get("avg_paragraph_chars", 0))
    candidate_para = float(candidate.get("avg_paragraph_chars", 0))
    para_target = (profile_para + reference_para) / 2 if profile_para and reference_para else profile_para or reference_para
    para_score = _ratio_score(para_target, candidate_para)
    bucket_score = _dict_vector_score(
        profile.get("sentence_length_distribution", {}),
        candidate.get("sentence_length_distribution", {}),
    )
    return round(sentence_score * 0.45 + para_score * 0.25 + bucket_score * 0.30, 2)


def _density_score(profile: dict, reference: dict, candidate: dict) -> float:
    thought_target = _avg_float(profile.get("thought_density", 0), reference.get("thought_density", 0))
    dialogue_target = _avg_float(profile.get("dialogue_density", 0), reference.get("dialogue_density", 0))
    thought = _ratio_score(thought_target, float(candidate.get("thought_density", 0)))
    dialogue = _ratio_score(dialogue_target, float(candidate.get("dialogue_density", 0)))
    return round(thought * 0.5 + dialogue * 0.5, 2)


def _structure_score(reference: dict, candidate: dict) -> float:
    char_score = _ratio_score(float(reference.get("char_count", 0)), float(candidate.get("char_count", 0)))
    sentence_score = _ratio_score(float(reference.get("sentence_count", 0)), float(candidate.get("sentence_count", 0)))
    para_score = _ratio_score(float(reference.get("paragraph_count", 0)), float(candidate.get("paragraph_count", 0)))
    return round(char_score * 0.5 + sentence_score * 0.3 + para_score * 0.2, 2)


def _originality_score(reference_text: str, candidate_text: str) -> dict[str, object]:
    reference_windows = set(_cjk_windows(reference_text, size=12))
    candidate_windows = set(_cjk_windows(candidate_text, size=12))
    if not reference_windows or not candidate_windows:
        return {"score": 100.0, "risk_ratio": 0.0, "overlap_windows": 0}
    overlap = reference_windows & candidate_windows
    risk_ratio = round(len(overlap) / max(len(candidate_windows), 1), 4)
    score = round(max(0.0, 100.0 - risk_ratio * 220), 2)
    return {"score": score, "risk_ratio": risk_ratio, "overlap_windows": len(overlap)}


def _ratio_score(target: float, actual: float) -> float:
    if target <= 0 and actual <= 0:
        return 100.0
    if target <= 0 or actual <= 0:
        return 0.0
    ratio = min(target, actual) / max(target, actual)
    return round(ratio * 100, 2)


def _counter_similarity_score(left_items: list[dict], right_items: list[dict]) -> float:
    left = Counter({str(item.get("item", "")): int(item.get("count", 0)) for item in left_items})
    right = Counter({str(item.get("item", "")): int(item.get("count", 0)) for item in right_items})
    return _counter_cosine(left, right)


def _weighted_overlap_score(left_items: list[dict], right_items: list[dict]) -> float:
    left = {str(item.get("item", "")) for item in left_items[:30] if item.get("item")}
    right = {str(item.get("item", "")) for item in right_items[:30] if item.get("item")}
    if not left and not right:
        return 100.0
    if not left or not right:
        return 0.0
    return round(len(left & right) / len(left | right) * 100, 2)


def _dict_vector_score(left: dict, right: dict) -> float:
    return _counter_cosine(Counter({str(k): int(v) for k, v in left.items()}), Counter({str(k): int(v) for k, v in right.items()}))


def _counter_cosine(left: Counter, right: Counter) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 100.0
    dot = sum(left[key] * right[key] for key in keys)
    left_norm = math.sqrt(sum(left[key] ** 2 for key in keys))
    right_norm = math.sqrt(sum(right[key] ** 2 for key in keys))
    if not left_norm or not right_norm:
        return 0.0
    return round(dot / (left_norm * right_norm) * 100, 2)


def _avg_float(left: object, right: object) -> float:
    values = [float(value) for value in [left, right] if float(value or 0) > 0]
    return sum(values) / len(values) if values else 0.0


def _cjk_windows(text: str, size: int) -> list[str]:
    chars = re.findall(r"[\u4e00-\u9fff]", text)
    return ["".join(chars[i : i + size]) for i in range(0, max(len(chars) - size + 1, 0))]


def _risk_level(risk_ratio: float, overall_score: float) -> str:
    if risk_ratio >= 0.18:
        return "high_copy_risk"
    if risk_ratio >= 0.08:
        return "medium_copy_risk"
    if overall_score < 45:
        return "low_similarity"
    return "normal"


def _render_report(payload: dict, profile: dict, reference: dict, candidate: dict) -> str:
    scores = payload["scores"]
    lines = [
        f"# Style Evaluation：{payload['mode']}",
        "",
        f"- 生成时间：{payload['created_at']}",
        f"- 总分：{payload['overall_score']}",
        f"- 风险等级：`{payload['risk_level']}`",
        f"- Profile：`{payload['profile_dir']}`",
        f"- Reference：`{payload['reference']}`",
        f"- Candidate：`{payload['candidate']}`",
        "",
        "## 分项评分",
        "",
        "| 维度 | 分数 | 权重 |",
        "| --- | ---: | ---: |",
    ]
    for key in [
        "rhythm",
        "punctuation",
        "lexical_bigrams",
        "sensory_profile",
        "narrative_distance",
        "structure_length",
        "originality_boundary",
    ]:
        item = scores[key]
        lines.append(f"| `{key}` | {item['score']} | {item['weight']} |")

    lines.extend(
        [
            "",
            "## 对照指标",
            "",
            "| 指标 | Profile | Reference | Candidate |",
            "| --- | ---: | ---: | ---: |",
            f"| 汉字数 | {profile.get('char_count', 0)} | {reference.get('char_count', 0)} | {candidate.get('char_count', 0)} |",
            f"| 平均句长 | {profile.get('avg_sentence_chars', 0)} | {reference.get('avg_sentence_chars', 0)} | {candidate.get('avg_sentence_chars', 0)} |",
            f"| 平均段长 | {profile.get('avg_paragraph_chars', 0)} | {reference.get('avg_paragraph_chars', 0)} | {candidate.get('avg_paragraph_chars', 0)} |",
            f"| 对话密度 | {profile.get('dialogue_density', 0)} | {reference.get('dialogue_density', 0)} | {candidate.get('dialogue_density', 0)} |",
            f"| 心理词密度 | {profile.get('thought_density', 0)} | {reference.get('thought_density', 0)} | {candidate.get('thought_density', 0)} |",
            "",
            "## 原创性边界",
            "",
            f"- 重叠窗口数：{scores['originality_boundary']['overlap_windows']}",
            f"- 重叠风险比例：{scores['originality_boundary']['risk_ratio']}",
            "",
            "## 评审建议",
            "",
        ]
    )
    if payload["risk_level"] == "high_copy_risk":
        lines.append("- 候选文本与参考文本连续片段重合偏高，应降低逐字相似度，改为复现叙事机制。")
    elif payload["risk_level"] == "low_similarity":
        lines.append("- 候选文本与目标风格距离较大，应优先调整句长、感官分布和叙述距离。")
    else:
        lines.append("- 候选文本可进入人工盲评；继续检查人物逻辑和 canon 边界。")
    lines.extend(
        [
            "- 分数只说明风格机制相似度，不代表内容可直接发布。",
            "- 公版/授权语料可做精确复现评测；其他语料仅可做高层技法抽象。",
        ]
    )
    return "\n".join(lines) + "\n"
