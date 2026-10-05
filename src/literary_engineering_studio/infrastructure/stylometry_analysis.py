"""Fixed Lab package adapter; measurement uses the original research algorithms."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from stylometric_prompt_lab import __version__
from stylometric_prompt_lab.integration import analyze_corpus, analyze_text, evaluate_text
from stylometric_prompt_lab.creator_fragment import (
    compile_creator_fragment, default_creator_controls, metric_catalog,
)
from stylometric_prompt_lab.corpus import normalize_source

from ..application.style.stylometry_contracts import LabDocument
from .stylometry_cache import StylometryCalculationCache
from .stylometry_import import import_parameters


class LabStylometryAnalysis:
    def __init__(self, cache_root: Path | None = None):
        self.cache = StylometryCalculationCache(cache_root)

    def capabilities(self):
        return _document({"schema": "arcvellum/stylometry-capabilities/v1", "lab_version": __version__,
            "basic": True, "lexical": True, "dependency": "saved-tree-import",
            "ltp_generation": False, "r_stylo": False, "max_characters": 2_000_000,
            "generation_effect": "not-verified"})

    def analyze(self, sources, label):
        key = self.cache.key(sources, label, __version__)
        cached = self.cache.read(key)
        if cached is not None:
            return cached
        result = self._analyze(sources, label)
        self.cache.save(key, result)
        return result

    def _analyze(self, sources, label):
        if not 1 <= len(sources) <= 64 or sum(len(row.text) for row in sources) > 2_000_000:
            raise ValueError("语料需为 1–64 篇，总计不超过 200 万字符。")
        if not label.strip() or len(label) > 80:
            raise ValueError("语料名称需为 1–80 字符。")
        if len(sources) == 1:
            return _document(analyze_text(normalize_source(sources[0].text, markdown=sources[0].markdown)))
        with TemporaryDirectory(prefix="arcvellum-stylometry-") as folder:
            directory, rows = Path(folder), []
            for index, source in enumerate(sources):
                filename = f"source-{index}.{'md' if source.markdown else 'txt'}"
                (directory / filename).write_text(source.text, encoding="utf-8", newline="\n")
                rows.append({"source_id": source.source_id, "work_id": source.work_id,
                    "path": filename, "split": source.split, "topic": source.topic, "genre": source.genre})
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({"schema": "corpus-manifest/v1", "label": label,
                "sources": rows}, ensure_ascii=False), encoding="utf-8")
            return _document(analyze_corpus(manifest))

    def parameters(self, profile_json, dependency_json):
        profile, tree = _object(profile_json), _optional(dependency_json)
        return _document({"schema": "arcvellum/stylometry-parameters/v1",
            "controls": default_creator_controls(profile, tree), "metrics": metric_catalog(profile, tree)})

    def import_parameters(self, profile_json, parameters_json, dependency_json, title, intent):
        try:
            return _document(import_parameters(profile_json, parameters_json, dependency_json, title, intent))
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("计量导出结构不完整，请重新导出画像、参数或参考树。") from error

    def compile(self, profile_json, controls_json, dependency_json, title, intent):
        return _document(compile_creator_fragment(_object(profile_json), _object(controls_json),
            title=title, intent=intent, dependency_parse=_optional(dependency_json)))

    def measure(self, text, profile_json="", controls_json="", reference_json="", candidate_json=""):
        if len(text) > 2_000_000:
            raise ValueError("测量文本不超过 200 万字符。")
        candidate = _optional(candidate_json)
        if not profile_json:
            return _document(analyze_text(text, dependency_parse=candidate))
        return _document(evaluate_text(text, _object(profile_json), _object(controls_json),
            reference_parse=_optional(reference_json), candidate_parse=candidate))


def _optional(text):
    return _object(text) if text.strip() else None


def _object(text):
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("统计合同需为 JSON 对象。")
    return value


def _document(value):
    return LabDocument(value["schema"], json.dumps(value, ensure_ascii=False, allow_nan=False))
