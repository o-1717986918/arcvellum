"""Explicit experimental targets over saved trees; historical artifacts stay unchanged."""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import math

from .dependency_metrics import analyze_dependencies
from .io import ContractError, digest

AXES = {
    "mdd": ("依存距离 · 原位置", "original_token_positions/arc", 1, 511),
    "mdd_without_punctuation": ("依存距离 · 去标点", "nonpunct_token_positions/arc", 1, 511),
    "mhd": ("平均树深", "tree_edges/arc", 1, 511),
    "head_precedes_share": ("父词在前比例", "fraction", 0, 1),
    "adjacent_arc_share": ("相邻依存比例", "fraction", 0, 1),
    "mean_nonleaf_branching": ("非叶节点平均分支", "children/nonleaf", 1, 511),
    "leaf_share": ("叶节点比例", "fraction", 0, 1),
}
DEFINITIONS = {
    "mdd": "父词和依赖词原始编号差的绝对值之和/有效依存边数；排除根与标点边，保留标点占位。",
    "mdd_without_punctuation": "删除标点后重编号，再计算父词与依赖词距离/有效边数。",
    "mhd": "依赖词到真实根的边数之和/有效依存边数；根深度为0。",
    "head_precedes_share": "父词编号小于依赖词编号的有效边数/全部有效边数。",
    "adjacent_arc_share": "原始编号距离恰为1的有效边数/全部有效边数。",
    "mean_nonleaf_branching": "非标点依存边数/至少有一个非标点子节点的非标点节点数。",
    "leaf_share": "没有非标点子节点的非标点节点数/全部非标点节点数。",
}
GUIDANCE = {
    "mdd": ("让主语与谓语、动词与宾语紧邻，修饰语贴近被修饰对象。",
            "用必要的时间、方位或限定语分隔部分主干关系，保留清晰的修饰归属。"),
    "mdd_without_punctuation": ("压缩主干关系之间的词语距离，保持主谓、动宾相邻。",
                                "在部分主干关系之间展开必要修饰；标点增加不算词距离增加。"),
    "mhd": ("多用以谓语为中心的直接主谓、动宾关系，少用修饰语再带修饰语的链。",
            "使用自然的连续修饰和补充关系，让部分词通过中间词连接到主干，避免长而含混的修饰链。"),
    "head_precedes_share": ("适度用前置主语、前置限定语，保留自然汉语语序。",
                            "适度展开谓语之后的宾语、补语及宾语内部修饰，保留必要前置主语。"),
    "adjacent_arc_share": ("让部分依存关系跨过必要修饰或补充成分，避免所有关系都挤在相邻词上。",
                           "让修饰、主谓和动宾尽量贴近，减少主干之间的插入成分。"),
    "mean_nonleaf_branching": ("将必要信息分配到几个中间节点，避免所有成分直接挂在同一中心词上。",
                               "以清晰中心词组织若干直接修饰或论元，减少层层转接。"),
    "leaf_share": ("允许部分修饰词继续带必要补充，减少全部信息都直接终止在主干上的结构。",
                   "用更多直接修饰和直接宾语承载信息，减少修饰语继续展开的链。"),
}


def reference_view(parsed: dict) -> dict:
    result = analyze_dependencies(parsed)
    metrics = result["summary"]["metrics"]
    return {"schema": "style-dependency-reference/v1", "source_parse_hash": parsed["parse_hash"],
            "analysis_hash": result["analysis_hash"], "annotation_scheme": parsed["annotation_scheme"],
            "model_manifest_hash": (parsed.get("annotator") or {}).get("model_manifest_hash"),
            "annotator": parsed.get("annotator"), "summary": result["summary"],
            "axes": [{"id": key, "label": label, "unit": unit, "definition": DEFINITIONS[key],
                      "observed": metrics[key], "floor": floor, "ceiling": ceiling,
                      "initial_target": {"min": round(max(floor, metrics[key]["value"] * .85), 6),
                                         "max": round(min(ceiling, metrics[key]["value"] * 1.15), 6), "unit": unit}
                      if metrics[key]["value"] is not None else None,
                      "generation_control_status": "unverified"}
                     for key, (label, unit, floor, ceiling) in AXES.items()],
            "sentences": parsed["sentences"], "sentence_analysis": result["sentences"],
            "evidence_scope": "independently_selected_single_text",
            "warnings": ["单篇句法参考与训练画像独立选择；不是跨作品稳定性证据。",
                         "方向/相邻、距离/树深及分支/叶比例有关联，不能视为独立旋钮。",
                         "句法目标是实验假设；小说标注准确率和文学质量尚未验证。"]}


def validate_dependency_controls(controls: dict, parsed: dict | None) -> tuple[dict, dict | None]:
    selected = controls.get("dependency_axes")
    bound = controls.get("dependency_parse_hash")
    if parsed is None:
        if selected is not None or bound is not None:
            raise ContractError("dependency controls require an explicit dependency parse reference")
        return {}, None
    view = reference_view(parsed)
    if bound != view["source_parse_hash"]:
        raise ContractError("dependency controls belong to a different/missing parse reference")
    if not isinstance(selected, dict) or set(selected) - set(AXES):
        raise ContractError("dependency_axes must be an object containing only supported measured axes")
    clean = {}
    for key, band in selected.items():
        _, unit, floor, ceiling = AXES[key]
        if not isinstance(band, dict) or band.get("unit") != unit:
            raise ContractError(f"dependency axis {key} has a wrong unit")
        if any(type(band.get(name)) not in (int, float) or not math.isfinite(band[name]) for name in ("min", "max")):
            raise ContractError(f"dependency axis {key} bounds must be finite numbers")
        if not floor <= band["min"] <= band["max"] <= ceiling:
            raise ContractError(f"dependency axis {key} bounds must lie in {floor}..{ceiling}")
        if view["summary"]["metrics"][key]["value"] is None:
            raise ContractError(f"dependency axis {key} is unmeasured in this reference")
        clean[key] = {"min": band["min"], "max": band["max"], "unit": unit}
    if "mdd" in clean and "mdd_without_punctuation" in clean:
        if clean["mdd"]["max"] < clean["mdd_without_punctuation"]["min"]:
            raise ContractError("original-position MDD cannot be smaller than punctuation-compressed MDD")
    return clean, view


def card_extension(controls: dict, parsed: dict | None) -> dict:
    targets, view = validate_dependency_controls(controls, parsed)
    if view is None:
        return {}
    return {"card_version": "1.3.0", "dependency_reference": {
                key: value for key, value in view.items() if key not in ("sentences", "sentence_analysis", "axes")},
            "dependency_axes": [{**row, "target": targets.get(row["id"])} for row in view["axes"]]}


def dependency_lines(targets: dict, view: dict) -> list[str]:
    lines = ["", "## 真实依存句法的实验目标", "",
             "统计全文语言分布，不要求每句套同一种结构。以下指导是待检验假设；保留任务事实、因果和自然表达。",
             "依存词元由指定标注器决定，含汉字、拉丁及数字；与jieba纯汉字词元目标分别计量。"]
    for key, band in targets.items():
        observed = view["summary"]["metrics"][key]["value"]
        center = (band["min"] + band["max"]) / 2
        direction = 1 if center > observed else 0
        lines.append(f"- {AXES[key][0]}：参考{observed:.6f}，目标{band['min']:g}–{band['max']:g} {band['unit']}。"
                     f"{DEFINITIONS[key]}{GUIDANCE[key][direction]}")
    lines += ["句法层次、依存距离与句长会联动；避免靠堆字、删事实或机械重复追求数字。",
              "只交付文学正文，不在正文中输出统计表、依存树或自评。", ""]
    return lines


def attach_prompt(prompt: dict, controls: dict, parsed: dict | None) -> dict:
    targets, view = validate_dependency_controls(controls, parsed)
    if not targets:
        return prompt
    result = {key: value for key, value in prompt.items() if key != "prompt_artifact_sha256"}
    markdown = prompt["prompt_markdown"] + "\n".join(dependency_lines(targets, view))
    result.update({"compiler_version": "0.15.0", "base_compiler_version": prompt["compiler_version"],
                   "dependency_compiler_version": "0.1.0", "dependency_targets": targets,
                   "dependency_measurement": {"reference_parse_hash": view["source_parse_hash"],
                                              "reference_analysis_hash": view["analysis_hash"],
                                              "annotation_scheme": view["annotation_scheme"],
                                              "model_manifest_hash": view["model_manifest_hash"]},
                   "prompt_markdown": markdown,
                   "prompt_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest()})
    result["warnings"] = [*prompt["warnings"], *view["warnings"]]
    result["prompt_artifact_sha256"] = digest(result)
    return result


def render_card_extension(card: dict) -> str:
    reference = card.get("dependency_reference")
    if reference is None:
        return ""
    summary = reference["summary"]
    lines = ["", "## 单篇句法参考与实验参数", "",
             f"{summary['sentence_count']}句、{summary['nonpunct_token_count']}非标点词元、"
             f"{summary['eligible_arc_count']}有效边；与训练画像独立选择。", "",
             "| 参数 | 参考值（分子/分母） | 本次目标 | 单位 |", "| --- | --- | --- | --- |"]
    for row in card["dependency_axes"]:
        observed, target = row["observed"], row["target"]
        measured = "缺测" if observed["value"] is None else f"{observed['value']:.6f}"
        band = f"{target['min']:g}–{target['max']:g}" if target else "未选为目标"
        lines.append(f"| {row['label']} | {measured}（{observed['numerator']}/{observed['denominator']}） | {band} | {row['unit']} |")
    lines += ["", "测量与可控性分别验证。自动小说标注准确率、文风效度、文学质量尚未验证。",
              f"依存参考哈希：`{reference['source_parse_hash']}`。", ""]
    return "\n".join(lines)


def _target_result(observed: dict, band: dict) -> dict:
    numerator, denominator = observed["numerator"], observed["denominator"]
    low, high = Decimal(str(band["min"])), Decimal(str(band["max"]))
    value = Decimal(numerator) / denominator if denominator else None
    distance = max(low - value, value - high, Decimal(0)) if value is not None else None
    integers = {"min": int((low * denominator).to_integral_value(rounding=ROUND_CEILING)),
                "max": int((high * denominator).to_integral_value(rounding=ROUND_FLOOR))} if denominator else None
    return {"observed": observed, "target": band,
            "distance": float(distance) if distance is not None else None,
            "in_range": distance == 0 if distance is not None else None,
            "target_integer_numerator_at_actual_denominator": integers if integers and integers["min"] <= integers["max"] else None,
            "integer_range_feasible_at_actual_denominator": integers["min"] <= integers["max"] if integers else None}


def evaluate_targets(prompt: dict, answer: str, parsed: dict | None) -> dict:
    targets = prompt.get("dependency_targets") or {}
    if parsed is None:
        return {"status": "not_measured", "reason": "missing real candidate dependency parse",
                "targets": {key: {"observed": None, "target": band, "distance": None, "in_range": None}
                            for key, band in targets.items()}}
    result = analyze_dependencies(parsed)
    if parsed["text_sha256"] != hashlib.sha256(answer.encode("utf-8")).hexdigest():
        raise ContractError("candidate dependency parse belongs to another answer")
    expected = prompt["dependency_measurement"]
    if parsed["annotation_scheme"] != expected["annotation_scheme"] or (
            (parsed.get("annotator") or {}).get("model_manifest_hash") != expected["model_manifest_hash"]):
        raise ContractError("candidate dependency annotation scheme/model differs from prompt reference")
    return {"status": "measured", "parse_hash": parsed["parse_hash"], "analysis_hash": result["analysis_hash"],
            "sample": {key: result["summary"][key] for key in
                       ("sentence_count", "nonpunct_token_count", "eligible_arc_count")},
            "targets": {key: _target_result(result["summary"]["metrics"][key], band)
                        for key, band in targets.items()}}


def attach_evaluations(experiment: dict, prompt: dict, rows: list[dict]) -> None:
    if not prompt.get("dependency_targets"):
        return
    sources = {row["blind_id"]: row for row in experiment["runs"]}
    for row in rows:
        if row["status"] == "completed":
            source = sources[row["blind_id"]]
            row["dependency_evaluation"] = evaluate_targets(prompt, source["answer"], source.get("dependency_parse"))


def attach_report(report: dict, prompt: dict) -> dict:
    if not prompt.get("dependency_targets"):
        return report
    rows = [row for row in report["runs"] if row["status"] == "completed"]
    measured = [row for row in rows if row["dependency_evaluation"]["status"] == "measured"]
    report["dependency_axes"] = {key: {"target_range": band, "measured_count": len(values),
                                       "in_range_count": sum(value["in_range"] is True for value in values),
                                       "mean_distance": sum(value["distance"] for value in values) / len(values) if values else None}
                                  for key, band in prompt["dependency_targets"].items()
                                  for values in [[row["dependency_evaluation"]["targets"][key] for row in measured
                                                  if row["dependency_evaluation"]["targets"][key]["distance"] is not None]]}
    report["dependency_evaluation_status"] = "measured" if rows and len(measured) == len(rows) else "incomplete"
    if report.get("experiment_design") == "target_only":
        old_joint = report["target_attainment"]["all_targets_joint_count"]
        joint = sum(all(value["in_range"] is True for value in row["dependency_evaluation"]["targets"].values())
                    and all(value == 0 for field in ("target_distance", "secondary_target_distance", "lexical_target_distance")
                            for value in row[field].values()) for row in measured)
        report["target_attainment"].update({"legacy_targets_joint_count": old_joint, "all_targets_joint_count": joint})
        complete = (report["acceptance"]["all_planned_outputs_measured"] and len(measured) == len(rows)
                    and all(row["measured_count"] == len(rows) for row in report["dependency_axes"].values()))
        report["acceptance"].update({"dependency_all_measured": complete,
                                    "all_planned_outputs_measured": complete,
                                    "all_targets_in_range": complete and joint == len(rows)})
        if not complete:
            report["acceptance"]["status"] = "not-evaluable"
        elif joint != len(rows):
            report["acceptance"]["status"] = "fail"
    elif len(measured) != len(rows) and report.get("acceptance"):
        report["acceptance"]["status"] = "not-evaluable"
    return report


def require_legacy_targets(prompt: dict, operation: str) -> None:
    if prompt.get("dependency_targets"):
        raise ContractError(f"{operation} cannot accept dependency targets without freshly parsed candidates; "
                            "use report with saved dependency_parse for every candidate")


def attach_audit(audit: dict, report: dict, prompt: dict, minimum: int) -> None:
    targets = prompt.get("dependency_targets")
    if not targets:
        return
    rows = [row for row in report["runs"] if row.get("arm") == "target" and row["status"] == "completed"]
    def readings(row):
        return (row.get("dependency_evaluation") or {}).get("targets") or {}
    audit["dependency_axes"] = {key: {
        "target_in_range": sum(readings(row).get(key, {}).get("in_range") is True for row in rows),
        "target_measured": sum(readings(row).get(key, {}).get("distance") is not None for row in rows)} for key in targets}
    audit["target_all_measured_joint"] = sum(
        all(value == 0 for field in ("target_distance", "secondary_target_distance", "lexical_target_distance")
            for value in row[field].values()) and
        all(readings(row).get(key, {}).get("in_range") is True for key in targets) for row in rows)
    audit["metric_checks"]["each_dependency"] = all(
        row["target_in_range"] >= audit["required_target_hits_per_metric"] for row in audit["dependency_axes"].values())
    if report.get("experiment_design") == "target_only":
        audit["metric_checks"]["all_targets_joint"] = audit["target_all_measured_joint"] >= audit["required_target_hits_per_metric"]
    incomplete = any(row["target_measured"] != len(rows) for row in audit["dependency_axes"].values())
    if len(rows) < minimum or incomplete:
        audit["metric_status"] = "not-evaluable"
    elif not all(audit["metric_checks"].values()):
        audit["metric_status"] = "fail"
    audit["overall_status"] = ("fail" if audit["metric_status"] == "fail" or any(
        value is False for value in audit["human_checks"].values()) else "pass" if audit["metric_status"] == "pass" and
        all(value is True for value in audit["human_checks"].values()) else "not-evaluable")
    audit["note"] = "句法依存与标点/词性代理分别计量；自动小说标注及文学质量未验证。"


def render_report_extension(report: dict) -> str:
    if not report.get("dependency_axes"):
        return ""
    lines = ["", "## 真实依存目标", "", f"测量状态：{report['dependency_evaluation_status']}。",
             "缺少真实候选树时记缺测；按各篇实际边数与节点数判断，不按要求篇幅换算。", "",
             "| 指标 | 目标范围 | 命中/可测 | 平均距离 |", "| --- | --- | --- | --- |"]
    for key, row in report["dependency_axes"].items():
        band = row["target_range"]
        lines.append(f"| {AXES[key][0]} | {band['min']:g}–{band['max']:g} {band['unit']} | "
                     f"{row['in_range_count']}/{row['measured_count']} | {row['mean_distance']} |")
    lines += ["", "完整计数、实际分母与可达整数范围见逐篇JSON。句法达标不证明文学质量。", ""]
    return "\n".join(lines)
