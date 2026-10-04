"""Stable DTOs and ports for experimental, project-scoped stylometry."""
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CorpusTextSource:
    source_id: str
    work_id: str
    text: str
    split: str = "train"
    topic: str = "unknown"
    genre: str = "narrative"
    markdown: bool = False


@dataclass(frozen=True)
class LabDocument:
    schema: str
    json_text: str


@dataclass(frozen=True)
class StylometryProfile:
    profile_id: str
    title: str
    created_at: str
    document_json: str
    sources_json: str


@dataclass(frozen=True)
class StylometryVersion:
    version_id: str
    profile_id: str
    title: str
    intent: str
    created_at: str
    controls_json: str
    dependency_json: str
    compiled_json: str
    fragment_text: str
    content_sha256: str
    user_edited: bool


@dataclass(frozen=True)
class CreatorStyleSnapshot:
    enabled: bool = False
    revision: int = 0
    version_id: str = ""
    profile_id: str = ""
    combine: str = "append"
    usage: str = "guide"
    fragment_text: str = ""
    content_sha256: str = ""
    compiler_version: str = ""
    profile_sha256: str = ""
    controls_sha256: str = ""

    def to_dict(self):
        return {"schema": "arcvellum/creator-stylometry-snapshot/v1", **asdict(self)}


@dataclass(frozen=True)
class StylometryJob:
    job_id: str
    title: str
    sources_json: str
    status: str = "queued"
    phase: str = "等待计算"
    attempt: int = 1
    result_json: str = ""
    error: str = ""


class StylometryAnalysisPort(Protocol):
    def capabilities(self) -> LabDocument: ...
    def analyze(self, sources: tuple[CorpusTextSource, ...], label: str) -> LabDocument: ...
    def compile(self, profile_json: str, controls_json: str, dependency_json: str,
                title: str, intent: str) -> LabDocument: ...
    def measure(self, text: str, profile_json: str = "", controls_json: str = "",
                reference_json: str = "", candidate_json: str = "") -> LabDocument: ...
    def parameters(self, profile_json: str, dependency_json: str) -> LabDocument: ...


class StylometryRepositoryPort(Protocol):
    def profiles(self, root: Path) -> tuple[StylometryProfile, ...]: ...
    def profile(self, root: Path, profile_id: str) -> StylometryProfile: ...
    def save_profile(self, root: Path, record: StylometryProfile) -> None: ...
    def versions(self, root: Path) -> tuple[StylometryVersion, ...]: ...
    def version(self, root: Path, version_id: str) -> StylometryVersion: ...
    def save_version(self, root: Path, record: StylometryVersion) -> None: ...
    def snapshot(self, root: Path) -> CreatorStyleSnapshot: ...
    def set_mount(self, root: Path, snapshot: CreatorStyleSnapshot, expected_revision: int) -> CreatorStyleSnapshot: ...
    def jobs(self, root: Path) -> tuple[StylometryJob, ...]: ...
    def job(self, root: Path, job_id: str) -> StylometryJob: ...
    def save_job(self, root: Path, record: StylometryJob) -> None: ...

