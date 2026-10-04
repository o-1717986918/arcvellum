"""Recomputable dependency-tree measurements; no neural imports or proxy parsing."""

from __future__ import annotations

from collections import Counter
import hashlib
import statistics

from .io import ContractError, digest

VERSION = "0.1.0"
METHODS = {
    "distance": "abs(dependent_id-head_id); exclude root and punctuation endpoints",
    "distance_without_punctuation": "abs(nonpunct_rank[dependent]-nonpunct_rank[head])",
    "hierarchical_distance": "number of original tree edges from dependent to real root (root=0)",
    "aggregation": "sum of eligible arc values / eligible arc count; not mean of sentence means",
    "direction": "head precedes/follows dependent in token order; divide by eligible arc count",
    "branching": "nonpunct children of each nonpunct node; include root and zero-child leaves",
    "sources": ["https://aclanthology.org/2025.quasy-1.7/",
                "https://aclanthology.org/W13-3710/"],
    "adaptation": "formulas applied to saved annotation scheme; no SUD conversion or Czech corpus filters",
}


def compact(text: str) -> str:
    return "".join(character for character in text if not character.isspace())


def seal_parse(value: dict) -> dict:
    result = {**value, "schema": "style-dependency-parse/v1", "parse_version": VERSION}
    result["text_sha256"] = hashlib.sha256(result["text"].encode("utf-8")).hexdigest()
    result.pop("parse_hash", None)
    result["parse_hash"] = digest(result)
    return result


def _validate_document(value: dict) -> None:
    if value.get("schema") != "style-dependency-parse/v1" or value.get("parse_version") != VERSION:
        raise ContractError("unsupported dependency parse contract/version")
    unsigned = {key: item for key, item in value.items() if key != "parse_hash"}
    if value.get("parse_hash") != digest(unsigned):
        raise ContractError("dependency parse hash mismatch")
    text = value.get("text")
    rows, scheme = value.get("sentences"), value.get("annotation_scheme")
    if not isinstance(text, str) or not compact(text) or not isinstance(rows, list) or not rows:
        raise ContractError("dependency parse must contain nonempty text and sentences")
    if value.get("text_sha256") != hashlib.sha256(text.encode("utf-8")).hexdigest():
        raise ContractError("dependency source text hash mismatch")
    if not isinstance(scheme, dict) or not isinstance(scheme.get("name"), str):
        raise ContractError("missing dependency annotation scheme")
    for key in ("punctuation_pos", "punctuation_relations"):
        labels = scheme.get(key)
        if not isinstance(labels, list) or not labels or any(not isinstance(x, str) or not x for x in labels):
            raise ContractError(f"missing/invalid dependency {key}")
    end = 0
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] != index:
            raise ContractError("sentence ids must be consecutive from 1")
        start, stop = row.get("start"), row.get("end")
        if type(start) is not int or type(stop) is not int or not end <= start < stop <= len(text):
            raise ContractError("invalid/overlapping dependency sentence offsets")
        if compact(text[end:start]) or text[start:stop] != row.get("text"):
            raise ContractError("dependency sentence spans do not cover original text")
        end = stop
    if compact(text[end:]):
        raise ContractError("unparsed dependency source suffix")


def _validate_tree(sentence: dict, scheme: dict) -> tuple[list[dict], set[int], dict[int, int]]:
    tokens = sentence.get("tokens")
    if not isinstance(tokens, list) or not tokens:
        raise ContractError(f"sentence {sentence['id']}: empty dependency tree")
    punctuation = set()
    for index, token in enumerate(tokens, 1):
        if not isinstance(token, dict) or type(token.get("id")) is not int or token["id"] != index:
            raise ContractError("token ids must be consecutive integers from 1")
        if any(not isinstance(token.get(key), str) or not token[key] for key in ("form", "pos", "relation")):
            raise ContractError("dependency token form/POS/relation must be nonempty strings")
        head = token.get("head")
        if type(head) is not int or not 0 <= head <= len(tokens) or head == index:
            raise ContractError("invalid/out-of-range/self dependency head")
        if token["pos"] in scheme["punctuation_pos"] or token["relation"] in scheme["punctuation_relations"]:
            punctuation.add(index)
    if compact("".join(token["form"] for token in tokens)) != compact(sentence["text"]):
        raise ContractError("dependency token coverage differs from source sentence")
    roots = [token["id"] for token in tokens if token["head"] == 0]
    if len(roots) != 1 or roots[0] in punctuation:
        raise ContractError("dependency tree requires one nonpunctuation root")
    depths = {roots[0]: 0}
    for token in tokens:
        path, current = [], token["id"]
        while current not in depths:
            if current in path:
                raise ContractError("cycle in dependency tree")
            path.append(current)
            current = tokens[current - 1]["head"]
        for node in reversed(path):
            depths[node] = depths[tokens[node - 1]["head"]] + 1
    for token in tokens:
        if token["id"] not in punctuation and token["head"] in punctuation:
            raise ContractError("lexical dependency has punctuation parent; cannot satisfy n-s denominator")
    return tokens, punctuation, depths


def ratio(numerator: int | float, denominator: int, unit: str) -> dict:
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None, "unit": unit}


def _histogram(counter: Counter) -> list[dict]:
    return [{"value": key, "count": count} for key, count in sorted(counter.items())]


def _arc_rows(tokens: list[dict], punctuation: set[int], depths: dict[int, int]) -> list[dict]:
    ranks = {token["id"]: rank for rank, token in
             enumerate((token for token in tokens if token["id"] not in punctuation), 1)}
    return [{"dependent": token["id"], "head": token["head"], "relation": token["relation"],
             "dependent_pos": token["pos"], "head_pos": tokens[token["head"] - 1]["pos"],
             "distance": abs(token["id"] - token["head"]),
             "distance_without_punctuation": abs(ranks[token["id"]] - ranks[token["head"]]),
             "hierarchical_distance": depths[token["id"]],
             "head_precedes": token["head"] < token["id"]}
            for token in tokens if token["head"] and token["id"] not in punctuation]


def _arc_metrics(arcs: list[dict]) -> dict:
    count = len(arcs)
    return {
        "mdd": ratio(sum(arc["distance"] for arc in arcs), count, "original_token_positions/arc"),
        "mdd_without_punctuation": ratio(sum(arc["distance_without_punctuation"] for arc in arcs),
                                          count, "nonpunct_token_positions/arc"),
        "mhd": ratio(sum(arc["hierarchical_distance"] for arc in arcs), count, "tree_edges/arc"),
        "head_precedes_share": ratio(sum(arc["head_precedes"] for arc in arcs), count, "fraction"),
        "head_follows_share": ratio(sum(not arc["head_precedes"] for arc in arcs), count, "fraction"),
        "adjacent_arc_share": ratio(sum(arc["distance"] == 1 for arc in arcs), count, "fraction"),
        "adjacent_arc_share_without_punctuation": ratio(
            sum(arc["distance_without_punctuation"] == 1 for arc in arcs), count, "fraction"),
        "max_dependency_distance": max((arc["distance"] for arc in arcs), default=None),
        "max_tree_depth": max((arc["hierarchical_distance"] for arc in arcs), default=0),
    }


def _relation_rows(arcs: list[dict]) -> list[dict]:
    relations = sorted({arc["relation"] for arc in arcs})
    return [{"relation": relation, "frequency": ratio(len(group), len(arcs), "fraction"),
             "mdd": ratio(sum(arc["distance"] for arc in group), len(group), "original_token_positions/arc"),
             "mhd": ratio(sum(arc["hierarchical_distance"] for arc in group), len(group), "tree_edges/arc")}
            for relation in relations for group in [[arc for arc in arcs if arc["relation"] == relation]]]


def _branching(tokens: list[dict], punctuation: set[int], arcs: list[dict]) -> Counter:
    children = Counter(arc["head"] for arc in arcs)
    return Counter(children[token["id"]] for token in tokens if token["id"] not in punctuation)


def _sentence_analysis(sentence: dict, scheme: dict) -> dict:
    tokens, punctuation, depths = _validate_tree(sentence, scheme)
    arcs = _arc_rows(tokens, punctuation, depths)
    branching = _branching(tokens, punctuation, arcs)
    return {"sentence_id": sentence["id"], "text": sentence["text"],
            "token_count": len(tokens), "punctuation_count": len(punctuation),
            "nonpunct_token_count": len(tokens) - len(punctuation), "eligible_arc_count": len(arcs),
            "root_id": next(token["id"] for token in tokens if not token["head"]),
            "metrics": _arc_metrics(arcs), "arcs": arcs,
            "tree_depths": [{"id": token["id"], "depth": depths[token["id"]],
                             "punctuation": token["id"] in punctuation} for token in tokens],
            "branching_histogram": _histogram(branching),
            "pos_counts": _histogram(Counter(token["pos"] for token in tokens if token["id"] not in punctuation))}


def _dispersion(values: list[float]) -> dict:
    if not values:
        return {"sentence_count": 0, "mean": None, "sd_population": None, "min": None, "max": None}
    return {"sentence_count": len(values), "mean": statistics.mean(values),
            "sd_population": statistics.pstdev(values), "min": min(values), "max": max(values)}


def _summary(rows: list[dict]) -> dict:
    arcs = [arc for row in rows for arc in row["arcs"]]
    branching, positions = Counter(), Counter()
    for row in rows:
        branching.update({entry["value"]: entry["count"] for entry in row["branching_histogram"]})
        positions.update({entry["value"]: entry["count"] for entry in row["pos_counts"]})
    lexical_count = sum(row["nonpunct_token_count"] for row in rows)
    metrics = _arc_metrics(arcs)
    metrics.update({"mean_sentence_words": ratio(lexical_count, len(rows), "nonpunct_tokens/sentence"),
                    "mean_nonleaf_branching": ratio(len(arcs), lexical_count - branching[0], "children/nonleaf"),
                    "leaf_share": ratio(branching[0], lexical_count, "fraction"),
                    "max_branching": max(branching, default=0)})
    arc_patterns = Counter((arc["head_pos"], arc["relation"], arc["dependent_pos"]) for arc in arcs)
    return {"sentence_count": len(rows), "token_count": sum(row["token_count"] for row in rows),
            "nonpunct_token_count": lexical_count,
            "punctuation_count": sum(row["punctuation_count"] for row in rows),
            "root_count": len(rows), "eligible_arc_count": len(arcs), "metrics": metrics,
            "relations": _relation_rows(arcs), "branching_histogram": _histogram(branching),
            "pos_frequencies": [{"pos": pos, "frequency": ratio(count, lexical_count, "fraction")}
                                for pos, count in sorted(positions.items())],
            "dependency_pos_patterns": [{"head_pos": key[0], "relation": key[1], "dependent_pos": key[2],
                                          "frequency": ratio(count, len(arcs), "fraction")}
                                         for key, count in sorted(arc_patterns.items())],
            "sentence_dispersion": {key: _dispersion([row["metrics"][key]["value"] for row in rows
                                                      if row["metrics"][key]["value"] is not None])
                                    for key in ("mdd", "mdd_without_punctuation", "mhd")}}


def analyze_dependencies(parsed: dict) -> dict:
    _validate_document(parsed)
    rows = [_sentence_analysis(sentence, parsed["annotation_scheme"]) for sentence in parsed["sentences"]]
    summary = _summary(rows)
    if summary["eligible_arc_count"] != summary["nonpunct_token_count"] - summary["sentence_count"]:
        raise ContractError("dependency n-s denominator invariant failed")
    result = {"schema": "style-dependency-analysis/v1", "analysis_version": VERSION,
              "source_parse_hash": parsed["parse_hash"], "text_sha256": parsed["text_sha256"],
              "annotation_scheme": parsed["annotation_scheme"], "annotator": parsed.get("annotator"),
              "methods": METHODS, "summary": summary, "sentences": rows,
              "validation": {"trees": "valid", "token_coverage": "complete_ignoring_whitespace",
                             "domain_annotation_accuracy": "not_validated",
                             "style_controllability": "not_validated", "literary_quality": "not_validated"}}
    result["analysis_hash"] = digest(result)
    return result


def render_dependencies(result: dict) -> str:
    summary, metrics = result["summary"], result["summary"]["metrics"]
    lines = ["# 依存句法统计", "", f"标注体系：{result['annotation_scheme']['name']}。",
             f"{summary['sentence_count']}句，{summary['nonpunct_token_count']}个非标点词元，"
             f"{summary['eligible_arc_count']}条有效依存边。", "",
             "| 指标 | 值 | 整数分子/实际分母 | 单位 |", "| --- | ---: | --- | --- |"]
    names = {"mdd": "平均依存距离（原位置）", "mdd_without_punctuation": "平均依存距离（去标点重编号）",
             "mhd": "平均树深（根为0）", "head_precedes_share": "父节点在前比例",
             "head_follows_share": "父节点在后比例", "adjacent_arc_share": "相邻边比例（原位置）",
             "mean_sentence_words": "句均非标点词元", "mean_nonleaf_branching": "非叶节点平均子节点数",
             "leaf_share": "叶节点比例"}
    for key, label in names.items():
        row = metrics[key]
        value = "缺测" if row["value"] is None else f"{row['value']:.6f}"
        lines.append(f"| {label} | {value} | {row['numerator']}/{row['denominator']} | {row['unit']} |")
    lines.extend(["", "根节点与标点不计入依存距离/树深分母；无边的单词句记缺测。",
                  "POS比例以LTP非标点词元为分母，不能替换历史jieba纯汉字词元目标。",
                  "逐句树、关系频率、分支分布和父词性—关系—子词性模式见JSON。",
                  "自动标注的域内准确率、感知文风、文学质量和生成可控性尚未验证。", "",
                  f"原始解析哈希：`{result['source_parse_hash']}`。", ""])
    return "\n".join(lines)
