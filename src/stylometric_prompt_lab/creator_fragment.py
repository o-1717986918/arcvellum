"""Positive creator fragments compiled from selected, source-bound measurements."""
from __future__ import annotations
import math
from .io import ContractError, digest
from .metrics import AXES
from .extended_metrics import SECONDARY_AXES, secondary_summary_key
from .dependency_targets import AXES as DEPENDENCY_AXES, reference_view

PRIMARY = {
    "sentence_length_han": ("句群节奏", "以完整动作、感知和判断组织句子，让长短变化承接人物当下的注意力。"),
    "paragraph_length_han": ("段落呼吸", "随视线、动作、发言与认识的转折换段，让每段具有内在的进展。"),
    "dialogue_share": ("对白显现", "让人物的发言带着自己的声音，承接回应、关系变化和当下意图。"),
    "punctuation_per_1000_han": ("停顿密度", "以逗号、句号及场景所需的其他标点安排声音、停顿与句群流动。"),
}
SECONDARY = {
    "short_sentence_share_le20_han": ("短句占比", "用短句呈现清楚的动作、感知或判断。"),
    "long_sentence_share_gt30_han": ("长句占比", "在连续感知、复合动作和因果层次中展开长句。"),
    "clause_segments_per_sentence_proxy": ("标点分句", "让句内的各个片段沿同一注意力或因果关系展开。"),
    "quote_spans_per_1000_han": ("引语密度", "在发言的推进与回应中安排引语，让每轮话语形成自己的节奏。"),
    "word_length_mean_han": ("平均词长", "用具体、贴合人物经验的词语呈现动作与事物。"),
    "word_mattr_50": ("词汇多样性", "让词语的变化来自观察和经验的变化，保持人物与物件称呼清楚。"),
    "activity_v_over_v_plus_a": ("动词比", "让动作和状态共同显现人物的处境。"),
    "nominality_n_over_n_plus_v": ("名词比", "让人物、物件与动作在句中形成可感的关系。"),
    "function_pos_share_proxy": ("功能词性", "用时间、方位、修饰和因果关系组织语言的衔接。"),
}
DEPENDENCY_GUIDANCE = {
    "mdd": "按当下观察安排主干关系与修饰成分的距离。",
    "mdd_without_punctuation": "沿词语之间的真实关系组织主干与补充成分。",
    "mhd": "以适合此刻经验的层次展开连续修饰和补充关系。",
    "head_precedes_share": "让前置限定与后续宾语、补语共同形成自然语序。",
    "adjacent_arc_share": "随信息关系安排紧邻结构和展开结构。",
    "mean_nonleaf_branching": "让中心词和中间成分各自承担合适的信息。",
    "leaf_share": "按经验的深浅选择直接呈现或继续展开的修饰关系。",
}
RATIOS = {"dialogue_share", "short_sentence_share_le20_han", "long_sentence_share_gt30_han",
          "word_mattr_50", "activity_v_over_v_plus_a", "nominality_n_over_n_plus_v",
          "function_pos_share_proxy"}


def _profile(profile):
    if profile.get("schema") != "stylometric-profile/v1" or profile.get("profile_sha256") != digest(
            {key: value for key, value in profile.items() if key != "profile_sha256"}):
        raise ContractError("profile hash/schema mismatch")


def metric_catalog(profile, dependency_parse=None):
    _profile(profile)
    rows = []
    for key, unit in AXES.items():
        rows.append(_row(key, PRIMARY[key][0], unit, "primary", profile["axes"][key], 1 if key in {"sentence_length_han", "paragraph_length_han"} else 0,
                         1 if key in RATIOS else None))
    for key, unit in SECONDARY_AXES.items():
        summary = (profile.get("extended_window_summary") or {}).get(secondary_summary_key(key)) or {}
        rows.append(_row(key, SECONDARY[key][0], unit, "secondary", summary,
                         1 if key in {"word_length_mean_han", "clause_segments_per_sentence_proxy"} else 0,
                         1 if key in RATIOS else None))
    for value in (profile.get("extended_diagnostics") or {}).get("grammar", {}).get("function_word_top", []):
        observed = value["per_1000_words"]
        rows.append(_row("word:" + value["word"], "语法词「" + value["word"] + "」", "次/千词元",
                         "lexical", {"median": observed, "p25": observed, "p75": observed, "window_count": 1}, 0, 1000))
    if dependency_parse is not None:
        view = reference_view(dependency_parse)
        for key, (label, unit, floor, ceiling) in DEPENDENCY_AXES.items():
            observed = view["summary"]["metrics"][key]["value"]
            rows.append(_row("dep:" + key, label, unit, "dependency",
                {"median": observed, "p25": observed, "p75": observed, "window_count": int(observed is not None)},
                floor, ceiling))
    return rows


def _row(key, label, unit, group, summary, floor, ceiling):
    observed = summary.get("median") if summary.get("window_count", 1) else None
    lower = max(floor, (summary.get("p25") or observed or floor) * .85)
    upper = max(lower, (summary.get("p75") or observed or floor) * 1.15)
    if ceiling is not None:
        lower, upper = min(lower, ceiling), min(upper, ceiling)
    return {"id": key, "label": label, "unit": unit, "group": group, "observed": observed,
            "source_range": {"p25": summary.get("p25"), "p75": summary.get("p75")},
            "floor": floor, "ceiling": ceiling, "available": observed is not None,
            "suggested": {"min": round(lower, 6), "max": round(upper, 6)}}


def default_creator_controls(profile, dependency_parse=None):
    return {"schema": "stylometric-creator-controls/v1", "profile_sha256": profile["profile_sha256"],
            "dependency_parse_hash": dependency_parse.get("parse_hash") if dependency_parse else None,
            "targets": [{**row["suggested"], "id": row["id"], "unit": row["unit"],
                         "enabled": row["group"] == "primary" and row["available"]}
                        for row in metric_catalog(profile, dependency_parse)]}


def validate_creator_controls(profile, controls, dependency_parse=None):
    if controls.get("schema") != "stylometric-creator-controls/v1" or controls.get("profile_sha256") != profile.get("profile_sha256"):
        raise ContractError("creator controls belong to a different profile/schema")
    if controls.get("dependency_parse_hash") != (dependency_parse.get("parse_hash") if dependency_parse else None):
        raise ContractError("creator dependency reference hash mismatch")
    catalog = {row["id"]: row for row in metric_catalog(profile, dependency_parse)}
    targets, seen, result = controls.get("targets"), set(), []
    if not isinstance(targets, list) or len(targets) > len(catalog):
        raise ContractError("creator targets must be a list of measured indicators")
    for target in targets:
        if not isinstance(target, dict) or target.get("id") not in catalog or target["id"] in seen:
            raise ContractError("unknown/duplicate creator indicator")
        meta = catalog[target["id"]]
        seen.add(target["id"])
        if target.get("unit") != meta["unit"] or type(target.get("enabled")) is not bool:
            raise ContractError("creator indicator unit/enabled mismatch")
        lower, upper = target.get("min"), target.get("max")
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in (lower, upper)):
            raise ContractError("creator bounds must be finite numbers")
        if not meta["floor"] <= lower <= upper or (meta["ceiling"] is not None and upper > meta["ceiling"]):
            raise ContractError("creator bounds outside the measurement domain")
        if target["enabled"] and not meta["available"]:
            raise ContractError("enabled creator indicator needs measured source evidence")
        result.append({**meta, **target})
    active = {row["id"]: row for row in result if row["enabled"]}
    if sum(active.get(key, {}).get("min", 0) for key in ("short_sentence_share_le20_han", "long_sentence_share_gt30_han")) > 1:
        raise ContractError("short/long minimum shares exceed one")
    return result


def compile_creator_fragment(profile, controls, *, title="计量文风", intent="", dependency_parse=None):
    rows = validate_creator_controls(profile, controls, dependency_parse)
    if not isinstance(title, str) or not title.strip() or len(title) > 80 or not isinstance(intent, str) or len(intent) > 8000:
        raise ContractError("creator title/intent is invalid")
    active = [row for row in rows if row["enabled"]]
    lines = ["【" + title.strip() + "】", intent.strip(),
             "让本场事件、人物声音与所选语言分布一同形成语感。"]
    for row in active:
        key = row["id"]
        guidance = (PRIMARY.get(key) or SECONDARY.get(key) or ("", ""))[1]
        if key.startswith("word:"):
            guidance = "在句义需要的时间、修饰和动作关系中使用「" + key[5:] + "」。"
        if key.startswith("dep:"):
            guidance = DEPENDENCY_GUIDANCE[key[4:]]
        lines.append(f"{row['label']}：整体取向 {row['min']:g}–{row['max']:g} {row['unit']}。{guidance}")
    text = "\n\n".join(line for line in lines if line)
    result = {"schema": "stylometric-creator-fragment/v1", "compiler_version": "creator-1.0",
              "profile_sha256": profile["profile_sha256"], "controls_sha256": digest(controls),
              "fragment_text": text, "fragment_sha256": digest(text), "targets": active,
              "generation_effect": "not-verified"}
    result["artifact_sha256"] = digest(result)
    return result

