"""Build a truthful read-only demo project from an authorized source bundle."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from ..foundation.atomic_io import atomic_write_text
from ..foundation.display_cleaner import display_counts
from ..literary.ingest.authorized import (
    AuthorizedWorkManifest,
    DistributionScope,
    verify_authorized_source_bundle,
    write_authorized_reader_manifest,
)
from ..literary.ingest.readers import read_source_documents
from ..literary.style.defaults import ensure_default_style_mount
from .init import InitOptions, init_work_project
from .source_ingest import SourceIngestResult, ingest_existing_work


AUTHORIZED_DEMO_PROJECT_SCHEMA = "arcvellum/authorized-demo-project/v1"


@dataclass(frozen=True)
class AuthorizedDemoProjectResult:
    project_root: Path
    work_id: str
    authorized_manifest_path: Path
    source_ingest: SourceIngestResult
    reader_manifest_path: Path
    demo_identity_path: Path
    chinese_content_chars: int


def build_authorized_demo_project(
    target: Path | str,
    *,
    source_root: Path | str,
    manifest: AuthorizedWorkManifest,
    required_scopes: Iterable[DistributionScope] = (
        DistributionScope.DESKTOP_DEMO_BUNDLE,
    ),
    seal_reference: bool = False,
) -> AuthorizedDemoProjectResult:
    """Create an analysis workspace that can later be sealed as a reference."""

    bundle_root = Path(source_root).expanduser().resolve()
    verification = verify_authorized_source_bundle(
        manifest,
        bundle_root,
        required_scopes=required_scopes,
    ).require_valid()
    source_path, chinese_chars = _primary_source(bundle_root, manifest)
    root = Path(target).expanduser().resolve()
    source_ingest = _initialize_reference_project(root, manifest, source_path, chinese_chars)
    authorized_dir = root / "sources" / "authorized" / manifest.work_id
    authorized_manifest_path = authorized_dir / "authorized_work_manifest.json"
    atomic_write_text(
        authorized_manifest_path,
        json.dumps(manifest.to_record(), ensure_ascii=False, indent=2) + "\n",
    )
    reader_manifest_path = write_authorized_reader_manifest(
        root,
        work_id=manifest.work_id,
        title=manifest.title,
        author=manifest.author,
        edition=manifest.edition,
        authorized_manifest_digest=verification.manifest_digest,
        ingest_manifest_path=source_ingest.manifest_path,
    )
    demo_identity_path = root / ".arcvellum-demo.json"
    atomic_write_text(
        demo_identity_path,
        json.dumps(
            _demo_identity(
                root,
                manifest,
                verification.manifest_digest,
                source_ingest,
                reader_manifest_path,
                chinese_chars,
                sealed=seal_reference,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    if seal_reference:
        _mark_project_as_reference(root)
    return AuthorizedDemoProjectResult(
        project_root=root,
        work_id=manifest.work_id,
        authorized_manifest_path=authorized_manifest_path,
        source_ingest=source_ingest,
        reader_manifest_path=reader_manifest_path,
        demo_identity_path=demo_identity_path,
        chinese_content_chars=chinese_chars,
    )


def _primary_source(
    bundle_root: Path,
    manifest: AuthorizedWorkManifest,
) -> tuple[Path, int]:
    if len(manifest.source_files) != 1:
        raise ValueError(
            "authorized demo project v1 requires exactly one primary source file; "
            "combine edition parts before building"
        )
    source_path = (bundle_root / manifest.source_files[0].filename).resolve()
    documents = read_source_documents(
        source_path,
        text="",
        title=manifest.title,
        rights_declaration=manifest.authorization.declaration,
    )
    extracted = "\n\n".join(document.text.rstrip() for document in documents).strip() + "\n"
    counts = display_counts(extracted)
    return source_path, max(1, int(counts["chinese_content_chars"]))


def _initialize_reference_project(
    root: Path,
    manifest: AuthorizedWorkManifest,
    source_path: Path,
    chinese_chars: int,
) -> SourceIngestResult:
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"authorized demo project target is not empty: {root}")
    init_work_project(
        InitOptions(
            target=root,
            title=manifest.title,
            work_type=manifest.work_type,
            target_length=max(1000, chinese_chars),
            language=manifest.language,
            premise=f"经授权导入的{manifest.author}作品《{manifest.title}》文学工程演示。",
            genre="授权文学作品 / 工程演示",
            style_mode="authorized_source",
        )
    )
    ensure_default_style_mount(root)
    return ingest_existing_work(
        root,
        source=source_path,
        title=manifest.title,
        work_id=manifest.work_id,
        mode="analysis",
        rights_declaration=manifest.authorization.declaration,
    )


def _demo_identity(
    root: Path,
    manifest: AuthorizedWorkManifest,
    manifest_digest: str,
    source_ingest: SourceIngestResult,
    reader_manifest_path: Path,
    chinese_chars: int,
    *,
    sealed: bool,
) -> dict[str, object]:
    return {
        "schema": AUTHORIZED_DEMO_PROJECT_SCHEMA,
        "work_id": manifest.work_id,
        "title": manifest.title,
        "author": manifest.author,
        "edition": manifest.edition,
        "manifest_digest": manifest_digest,
        "source_ingest_manifest": source_ingest.manifest_path.relative_to(root).as_posix(),
        "reader_manifest": reader_manifest_path.relative_to(root).as_posix(),
        "authorization_basis": manifest.authorization.basis.value,
        "authorization_scopes": [item.value for item in manifest.authorization.scopes],
        "authorization_evidence_sha256": manifest.authorization.evidence_sha256,
        "authorization_evidence_embedded": False,
        "build_status": "sealed" if sealed else "analysis_workspace",
        "read_only_reference": sealed,
        "editable_copy_required": True,
        "origin": "authorized_source",
        "chinese_content_chars": chinese_chars,
        "provenance_note": "正文来自已校验授权源；本项目没有把原作伪装为 Agent 生成、审查或晋升产物。",
    }


def seal_authorized_demo_project(project_root: Path | str) -> Path:
    """Seal a fully audited workspace as an immutable demo mother project."""

    root = Path(project_root).expanduser().resolve()
    identity_path = root / ".arcvellum-demo.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if not isinstance(identity, dict) or identity.get("schema") != AUTHORIZED_DEMO_PROJECT_SCHEMA:
        raise ValueError("authorized demo identity is missing or invalid")
    identity["build_status"] = "sealed"
    identity["read_only_reference"] = True
    atomic_write_text(identity_path, json.dumps(identity, ensure_ascii=False, indent=2) + "\n")
    _mark_project_as_reference(root)
    return identity_path


def load_authorized_work_manifest(path: Path | str) -> AuthorizedWorkManifest:
    manifest_path = Path(path).expanduser().resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("authorized work manifest must contain a JSON object")
    return AuthorizedWorkManifest.from_record(payload)


def is_authorized_demo_reference(project_root: Path | str) -> bool:
    path = Path(project_root).expanduser().resolve() / ".arcvellum-demo.json"
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        isinstance(payload, dict)
        and payload.get("schema") == AUTHORIZED_DEMO_PROJECT_SCHEMA
        and payload.get("read_only_reference") is True
    )


def _mark_project_as_reference(root: Path) -> None:
    path = root / "project.yaml"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("  status:"):
            lines[index] = "  status: reference"
            break
    text = "\n".join(lines) + "\n"
    atomic_write_text(path, text)
