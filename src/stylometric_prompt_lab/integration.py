"""Versioned host integration over the lab's existing measurement algorithms."""
from __future__ import annotations
import hashlib
from pathlib import Path
from . import __version__
from .io import ContractError, digest
from .corpus import load_corpus
from .metrics import build_profile, measure, diagnostics
from .extended_metrics import extended_statistics, scalar_values, secondary_summary_key
from .creator_fragment import default_creator_controls, compile_creator_fragment, validate_creator_controls
from .dependency_targets import reference_view

API_VERSION = "stylometric-host/v1"


def analyze_corpus(manifest_path: str | Path):
    corpus = load_corpus(Path(manifest_path))
    profile, _ = build_profile(corpus)
    return {"schema": API_VERSION, "lab_version": __version__, "inspection": corpus.public(),
            "profile": profile, "controls": default_creator_controls(profile)}


def analyze_text(text: str, *, dependency_parse=None):
    if not isinstance(text, str) or not text.strip():
        raise ContractError("analysis requires nonempty text")
    base, extended = measure(text), extended_statistics(text)
    dependency = None
    if dependency_parse is not None:
        if dependency_parse.get("text_sha256") != hashlib.sha256(text.encode("utf-8")).hexdigest():
            raise ContractError("dependency tree belongs to a different text")
        dependency = reference_view(dependency_parse)
    result = {"schema": API_VERSION, "lab_version": __version__,
              "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
              "measurement": base, "extended": extended, "diagnostics": diagnostics(text),
              "dependency": dependency, "dependency_status": "measured" if dependency else "not-measured"}
    result["analysis_sha256"] = digest(result)
    return result


def evaluate_text(text, profile, controls, *, reference_parse=None, candidate_parse=None):
    targets = validate_creator_controls(profile, controls, reference_parse)
    if candidate_parse and reference_parse:
        for key in ("annotation_scheme", "annotator"):
            if candidate_parse.get(key) != reference_parse.get(key):
                raise ContractError("candidate dependency model/scheme differs from reference")
    report = analyze_text(text, dependency_parse=candidate_parse)
    scalars = scalar_values(report["extended"])
    counts = report["extended"]["grammar"]["function_word_counts"]
    token_count = report["extended"]["sample"]["word_token_count"]
    rows = []
    for target in targets:
        key = target["id"]
        if key in report["measurement"]["axes"]:
            value = report["measurement"]["axes"][key]
        elif key.startswith("word:"):
            value = round(counts.get(key[5:], 0) * 1000 / token_count, 4) if token_count else None
        elif key.startswith("dep:"):
            value = report["dependency"]["summary"]["metrics"][key[4:]]["value"] if report["dependency"] else None
        else:
            value = scalars.get(secondary_summary_key(key))
        distance = max(target["min"] - value, value - target["max"], 0) if value is not None else None
        rows.append({"id": key, "label": target["label"], "unit": target["unit"], "enabled": target["enabled"],
                     "observed": value, "min": target["min"], "max": target["max"], "distance": distance,
                     "in_range": distance == 0 if distance is not None else None})
    report["targets"] = rows
    report["analysis_sha256"] = digest({key: value for key, value in report.items() if key != "analysis_sha256"})
    return report

