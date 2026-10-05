"""Translate Lab exports into validated creator controls without new measurements."""
import json

from stylometric_prompt_lab.creator_fragment import default_creator_controls, compile_creator_fragment
from stylometric_prompt_lab.io import digest


def import_parameters(profile_json, parameters_json, dependency_json, title, intent):
    profile = _object(profile_json)
    parameters = _object(parameters_json) if parameters_json.strip() else {}
    tree = _object(dependency_json) if dependency_json.strip() else None
    controls = _controls(profile, parameters, tree)
    name = title or parameters.get("title") or profile.get("label") or "导入计量文风"
    direction = intent or parameters.get("intent", "")
    compiled = compile_creator_fragment(profile, controls, title=name, intent=direction, dependency_parse=tree)
    return {"schema": "arcvellum/stylometry-import/v1", "title": name, "intent": direction,
        "profile": profile, "controls": controls, "dependency_json": dependency_json,
        "inspection": {"kind": "imported-lab", "profile_sha256": profile["profile_sha256"],
            "parameter_schema": parameters.get("schema", "default-creator-controls"),
            "parameters_sha256": digest(parameters)},
        "import_source": {"profile_json": profile_json, "parameters_json": parameters_json,
                          "dependency_json": dependency_json}, "compiled": compiled}


def _object(text):
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("计量导出内容应为 JSON 对象。")
    return value


def _controls(profile, parameters, tree):
    defaults = default_creator_controls(profile, tree)
    if not parameters:
        return defaults
    if parameters.get("profile_sha256") != profile["profile_sha256"]:
        raise ValueError("参数与画像摘要不一致，请导入对应的 profile.json。")
    schema = parameters.get("schema")
    if schema == "stylometric-creator-controls/v1":
        return parameters
    if schema == "style-controls/v1":
        selected = _legacy_controls(parameters)
        bound = parameters.get("dependency_parse_hash")
    elif schema == "style-parameter-card/v1":
        if parameters.get("card_sha256") != digest({k: v for k, v in parameters.items() if k != "card_sha256"}):
            raise ValueError("参数卡摘要与内容不一致。")
        selected = _card_controls(parameters)
        bound = (parameters.get("dependency_reference") or {}).get("source_parse_hash")
    else:
        raise ValueError("请选择 Lab controls.json、参数卡 JSON 或主创参数 JSON。")
    if bound is not None:
        defaults["dependency_parse_hash"] = bound
    # Unselected measured axes remain visible as disabled observations.
    known = {row["id"] for row in defaults["targets"]}
    if set(selected) - known:
        raise ValueError("导出参数包含当前画像或依存参考中未测量的指标。")
    defaults["targets"] = [selected.get(row["id"], {**row, "enabled": False}) for row in defaults["targets"]]
    return defaults


def _legacy_controls(parameters):
    rows = {}
    for group, prefix in (("axes", ""), ("secondary_axes", ""), ("dependency_axes", "dep:")):
        values = parameters.get(group, {})
        if not isinstance(values, dict):
            raise ValueError("计量参数组应为 JSON 对象。")
        for key, band in values.items():
            _add(rows, prefix + key, band)
    for row in parameters.get("lexical_targets", []):
        if not isinstance(row, dict) or not isinstance(row.get("word"), str):
            raise ValueError("语法词参数需包含词语及目标区间。")
        _add(rows, "word:" + row["word"], row)
    return rows


def _card_controls(parameters):
    rows = {}
    for group, prefix in (("axes", ""), ("secondary_axes", ""), ("dependency_axes", "dep:")):
        values = parameters.get(group, [])
        if not isinstance(values, list) or any(not isinstance(row, dict) for row in values):
            raise ValueError("参数卡指标组应为 JSON 对象列表。")
        for row in values:
            if row.get("target") is not None:
                if not isinstance(row.get("id"), str):
                    raise ValueError("参数卡指标需包含名称。")
                _add(rows, prefix + row["id"], row["target"])
    for row in parameters.get("lexical_targets", []):
        if not isinstance(row, dict) or not isinstance(row.get("word"), str):
            raise ValueError("语法词参数需包含词语及目标区间。")
        _add(rows, "word:" + row["word"], row)
    return rows


def _add(rows, key, band):
    if key in rows or not isinstance(band, dict):
        raise ValueError("计量导出指标重复或目标区间格式错误。")
    rows[key] = {"id": key, "unit": band.get("unit"), "min": band.get("min"),
                 "max": band.get("max"), "enabled": True}
