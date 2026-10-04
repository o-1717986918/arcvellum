"""User-visible stylometry use cases over analysis and persistence ports."""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4
from .stylometry_contracts import (
    CorpusTextSource, CreatorStyleSnapshot, StylometryAnalysisPort, StylometryRepositoryPort,
    StylometryProfile, StylometryVersion,
)


class StylometryError(ValueError):
    code = "stylometry_invalid_input"


class StylometryService:
    def __init__(self, analysis: StylometryAnalysisPort, repository: StylometryRepositoryPort):
        self.analysis, self.repository = analysis, repository

    def workbench(self, root: Path):
        _project(root)
        return {"schema": "arcvellum/stylometry-workbench/v1",
            "capabilities": _decode(self.analysis.capabilities().json_text),
            "profiles": [_profile_view(row) for row in self.repository.profiles(root)],
            "versions": [_version_view(row) for row in self.repository.versions(root)],
            "mount": self.repository.snapshot(root).to_dict()}

    def analyze(self, root: Path, sources: tuple[CorpusTextSource, ...], title: str):
        _project(root)
        result = self.analysis.analyze(sources, title)
        payload = _decode(result.json_text)
        if "profile" not in payload:
            return {"schema": "arcvellum/stylometry-analysis/v1", "kind": "single-text", "result": payload}
        record = StylometryProfile(str(uuid4()), title, _now(), result.json_text,
                                   json.dumps([asdict(row) for row in sources], ensure_ascii=False))
        self.repository.save_profile(root, record)
        return self.profile(root, record.profile_id)

    def profile(self, root: Path, profile_id: str):
        _project(root)
        record = self.repository.profile(root, profile_id)
        payload = _decode(record.document_json)
        return {"schema": "arcvellum/stylometry-profile/v1", **_profile_view(record),
                "profile_json": json.dumps(payload["profile"], ensure_ascii=False),
                "controls": payload["controls"], "inspection": payload.get("inspection", {})}

    def parameters(self, root: Path, profile_id: str, dependency_json: str = ""):
        record = self.profile(root, profile_id)
        return _decode(self.analysis.parameters(record["profile_json"], dependency_json).json_text)

    def compile(self, root: Path, profile_id: str, controls_json: str, *, title: str,
                intent: str = "", dependency_json: str = ""):
        profile = self.profile(root, profile_id)
        return _decode(self.analysis.compile(profile["profile_json"], controls_json, dependency_json,
                                             title, intent).json_text)

    def save_version(self, root: Path, profile_id: str, controls_json: str, *, title: str,
                     intent: str = "", dependency_json: str = "", fragment_override: str | None = None):
        compiled = self.compile(root, profile_id, controls_json, title=title, intent=intent,
                                dependency_json=dependency_json)
        fragment = compiled["fragment_text"] if fragment_override is None else fragment_override.strip()
        if not fragment or len(fragment) > 32_000:
            raise StylometryError("文风片段需包含文字，且不超过 32000 字符。")
        record = StylometryVersion(str(uuid4()), profile_id, title, intent, _now(), controls_json,
            dependency_json, json.dumps(compiled, ensure_ascii=False), fragment,
            sha256(fragment.encode("utf-8")).hexdigest(), fragment != compiled["fragment_text"])
        self.repository.save_version(root, record)
        return self.version(root, record.version_id)

    def version(self, root: Path, version_id: str):
        _project(root)
        record = self.repository.version(root, version_id)
        return {"schema": "arcvellum/stylometry-version/v1", **asdict(record)}

    def mount(self, root: Path, version_id: str, *, enabled: bool, combine: str,
              usage: str, expected_revision: int):
        _project(root)
        if type(enabled) is not bool or combine not in {"append", "replace"} or usage not in {"guide", "observe"}:
            raise StylometryError("请选择有效挂载状态、文风组合方式和用途。")
        if not enabled:
            snapshot = CreatorStyleSnapshot()
        else:
            record = self.repository.version(root, version_id)
            compiled = _decode(record.compiled_json)
            snapshot = CreatorStyleSnapshot(True, 0, version_id, record.profile_id, combine, usage,
                record.fragment_text, record.content_sha256, compiled["compiler_version"],
                compiled["profile_sha256"], compiled["controls_sha256"])
        return self.repository.set_mount(root, snapshot, expected_revision).to_dict()

    def measure(self, root: Path, text: str, *, version_id: str = "", candidate_json: str = ""):
        _project(root)
        if not version_id:
            return _decode(self.analysis.measure(text, candidate_json=candidate_json).json_text)
        version = self.repository.version(root, version_id)
        profile = self.profile(root, version.profile_id)
        return _decode(self.analysis.measure(text, profile["profile_json"], version.controls_json,
                                            version.dependency_json, candidate_json).json_text)


def _project(root):
    if not (root.expanduser().resolve() / "project.yaml").is_file():
        raise StylometryError("请选择已有作品。")


def _decode(text):
    return json.loads(text)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _profile_view(record):
    return {"profile_id": record.profile_id, "title": record.title, "created_at": record.created_at}


def _version_view(record):
    return {key: getattr(record, key) for key in (
        "version_id", "profile_id", "title", "created_at", "content_sha256", "user_edited")}

