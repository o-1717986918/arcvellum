"""Idempotent materialization of reviewed longform planning artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from ...atomic_io import atomic_write_text
from .materialization_parser import (
    parse_chapter_obligations,
    parse_scene_inventory,
    scene_inventory_contract_issues,
)
from .materialization_rendering import (
    render_scene_yaml,
    repair_generated_rhythm_contracts,
)


MATERIALIZATION_SCHEMA = "literary-engineering-workbench/longform-materialization/v1"

# Compatibility names used by historical extension code.
_parse_scene_inventory = parse_scene_inventory
_parse_chapter_obligations = parse_chapter_obligations
_render_scene_yaml = render_scene_yaml


@dataclass(frozen=True)
class LongformMaterializationResult:
    project_root: Path
    manifest_path: Path
    outline_path: Path
    scene_paths: tuple[Path, ...]
    chapter_count: int


def materialize_longform_plan(project_root: Path) -> LongformMaterializationResult:
    root = project_root.expanduser().resolve()
    required = _required_inputs(root)
    missing = [_relative(path, root) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "missing reviewed longform planning inputs: " + ", ".join(missing)
        )
    inventory_text = required[0].read_text(encoding="utf-8", errors="ignore")
    obligation_text = required[1].read_text(encoding="utf-8", errors="ignore")
    scenes = parse_scene_inventory(inventory_text)
    obligations = parse_chapter_obligations(obligation_text)
    _validate_scene_count(_read_json(required[3]), inventory_text)
    source_digest = _source_digest(required)
    manifest_path = root / "workflow" / "longform_materialization.json"
    reused = _reuse_existing(root, manifest_path, source_digest, scenes, obligations)
    if reused is not None:
        return reused
    scene_paths = [root / "scenes" / f"{scene['scene_id']}.yaml" for scene in scenes]
    if any(path.is_file() and not _is_blank_scene_scaffold(path) for path in scene_paths):
        return _adopt_existing(
            root, manifest_path, required, source_digest, scene_paths, scenes
        )
    return _create_materialization(
        root,
        manifest_path,
        required,
        source_digest,
        inventory_text,
        scenes,
        obligations,
    )


def planned_longform_outputs(project_root: Path) -> list[str]:
    root = project_root.expanduser().resolve()
    inventory = root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"
    if not inventory.is_file():
        return ["plot/outline.md", "workflow/longform_materialization.json"]
    scenes = parse_scene_inventory(inventory.read_text(encoding="utf-8", errors="ignore"))
    return [
        "plot/outline.md",
        *[f"scenes/{scene['scene_id']}.yaml" for scene in scenes],
        "workflow/longform_materialization.json",
    ]


def longform_materialization_status(
    project_root: Path,
    *,
    scene_path: Path | str | None = None,
) -> tuple[bool, str]:
    root = project_root.expanduser().resolve()
    manifest_path = root / "workflow" / "longform_materialization.json"
    if not manifest_path.is_file():
        return False, "missing workflow/longform_materialization.json"
    payload = _read_json(manifest_path)
    if payload.get("schema") != MATERIALIZATION_SCHEMA or payload.get("status") != "materialized":
        return False, "longform materialization manifest is invalid"
    scene_relatives = [str(item).replace("\\", "/") for item in payload.get("scene_paths", [])]
    if not scene_relatives:
        return False, "longform materialization has no formal scenes"
    if scene_path is not None:
        return _scoped_status(root, payload, scene_relatives, scene_path)
    return _full_status(root, payload, scene_relatives)


def _required_inputs(root: Path) -> tuple[Path, ...]:
    return (
        root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md",
        root / "plot" / "candidates" / "chapters" / "chapter_obligation_plan.md",
        root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md",
        root / "plot" / "word_budget" / "word_budget.json",
    )


def _validate_scene_count(
    budget: dict[str, object], inventory_text: str
) -> None:
    issues = scene_inventory_contract_issues(inventory_text, budget=budget)
    if issues:
        raise ValueError("scene inventory budget contract: " + "; ".join(issues))


def _reuse_existing(
    root: Path,
    manifest_path: Path,
    source_digest: str,
    scenes: list[dict[str, object]],
    obligations: dict[str, dict[str, str]],
) -> LongformMaterializationResult | None:
    existing = _read_json(manifest_path)
    if existing.get("source_digest") != source_digest:
        return None
    paths = [root / str(item) for item in existing.get("scene_paths", [])]
    outline = root / str(existing.get("outline_path") or "plot/outline.md")
    if not paths or not all(path.is_file() for path in paths) or not outline.is_file():
        return None
    repair_generated_rhythm_contracts(paths, scenes)
    return LongformMaterializationResult(
        root, manifest_path, outline, tuple(paths), len(obligations)
    )


def _adopt_existing(
    root: Path,
    manifest_path: Path,
    required: tuple[Path, ...],
    source_digest: str,
    scene_paths: list[Path],
    scenes: list[dict[str, object]],
) -> LongformMaterializationResult:
    conflicts = _existing_formal_scene_conflicts(root, scenes, scene_paths)
    outline = root / "plot" / "outline.md"
    if not outline.is_file():
        conflicts.append("missing existing formal outline: plot/outline.md")
    if conflicts:
        raise ValueError(
            "refusing to overwrite non-scaffold formal scenes; manual reconciliation required: "
            + "; ".join(conflicts[:8])
        )
    manifest = _materialization_manifest(
        root, required, source_digest, outline, scene_paths, scenes, mode="adopted-existing"
    )
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return _result(root, manifest_path, outline, scene_paths, manifest)


def _create_materialization(
    root: Path,
    manifest_path: Path,
    required: tuple[Path, ...],
    source_digest: str,
    inventory_text: str,
    scenes: list[dict[str, object]],
    obligations: dict[str, dict[str, str]],
) -> LongformMaterializationResult:
    scene_dir = root / "scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    previous: dict[str, object] | None = None
    for scene in scenes:
        path = scene_dir / f"{scene['scene_id']}.yaml"
        if path.exists() and not _is_blank_scene_scaffold(path):
            raise ValueError(
                f"refusing to overwrite a non-scaffold formal scene: {_relative(path, root)}"
            )
        chapter = obligations.get(str(scene["chapter_id"]), {})
        atomic_write_text(path, render_scene_yaml(scene, chapter, previous))
        paths.append(path)
        previous = scene
    outline = root / "plot" / "outline.md"
    expansion = required[2].read_text(encoding="utf-8", errors="ignore")
    atomic_write_text(outline, _formal_outline(expansion, inventory_text))
    manifest = _materialization_manifest(
        root, required, source_digest, outline, paths, scenes
    )
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return _result(root, manifest_path, outline, paths, manifest)


def _scoped_status(
    root: Path,
    payload: dict[str, object],
    scene_relatives: list[str],
    scene_path: Path | str,
) -> tuple[bool, str]:
    requested = Path(scene_path)
    if requested.is_absolute():
        try:
            relative = requested.resolve().relative_to(root).as_posix()
        except ValueError:
            return False, "scoped scene is outside the materialization root"
    else:
        relative = requested.as_posix()
    if relative not in scene_relatives:
        return False, f"scoped scene is not registered by longform materialization: {relative}"
    if not (root / relative).is_file():
        return False, f"missing scoped materialized scene: {relative}"
    outline = str(payload.get("outline_path") or "plot/outline.md")
    if not (root / outline).is_file():
        return False, f"missing materialized {outline}"
    return True, f"materialized scoped scene {relative} within {len(scene_relatives)} formal scenes"


def _full_status(
    root: Path,
    payload: dict[str, object],
    scene_relatives: list[str],
) -> tuple[bool, str]:
    missing = [relative for relative in scene_relatives if not (root / relative).is_file()]
    if missing:
        return False, "missing materialized scenes: " + ", ".join(missing[:8])
    if not (root / str(payload.get("outline_path") or "plot/outline.md")).is_file():
        return False, "missing materialized plot/outline.md"
    required = _required_inputs(root)
    if not all(path.is_file() for path in required):
        return False, "reviewed longform planning inputs are missing"
    if payload.get("source_digest") != _source_digest(required):
        return False, "longform planning changed after materialization"
    return True, f"materialized {len(scene_relatives)} formal scenes"


def _formal_outline(expansion_text: str, inventory_text: str) -> str:
    cleaned = [
        line
        for line in expansion_text.splitlines()
        if not any(marker in line.strip() for marker in ("阅读回执", "未经审查", "候选材料"))
    ]
    body = "\n".join(cleaned).strip()
    return "# 正式长篇大纲\n\n" + (body if len(body) >= 200 else inventory_text.strip()) + "\n"


def _is_blank_scene_scaffold(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return bool(re.search(r'(?m)^scene_id:\s*["\']?\s*["\']?$', text)) and not any(
        (path.parent.parent / relative).exists()
        for relative in (
            f"drafts/scenes/{path.stem}.md",
            f"drafts/candidates/{path.stem}-platform-agent.md",
            f"reviews/agent/{path.stem}_scene_review.json",
        )
    )


def _existing_formal_scene_conflicts(
    root: Path,
    scenes: list[dict[str, object]],
    planned_paths: list[Path],
) -> list[str]:
    conflicts: list[str] = []
    planned = {path: scene for path, scene in zip(planned_paths, scenes)}
    for path, scene in planned.items():
        conflicts.extend(_scene_conflicts(root, path, scene))
    unexpected = sorted(
        _relative(path, root)
        for path in (root / "scenes").glob("scene_*.yaml")
        if path not in planned and not _is_blank_scene_scaffold(path)
    )
    if unexpected:
        conflicts.append(
            "formal scenes are absent from the reviewed inventory: "
            + ", ".join(unexpected[:5])
        )
    return conflicts


def _scene_conflicts(
    root: Path, path: Path, scene: dict[str, object]
) -> list[str]:
    relative = _relative(path, root)
    if not path.is_file():
        return [f"missing formal scene: {relative}"]
    if _is_blank_scene_scaffold(path):
        return [f"scene remains a blank scaffold: {relative}"]
    actual = _scene_contract_core(path)
    expected = {
        "scene_id": str(scene["scene_id"]),
        "chapter_id": str(scene["chapter_id"]),
        "volume_id": str(scene["volume_id"]),
        "title": str(scene["name"]),
        "word_count_target": str(int(scene["target_chars"])),
    }
    return [
        f"{relative} {key} differs ({actual.get(key) or '<missing>'!r} != {value!r})"
        for key, value in expected.items()
        if actual.get(key) != value
    ]


def _scene_contract_core(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    fields = ("scene_id", "chapter_id", "volume_id", "title", "word_count_target")
    return {field: _yaml_scalar(text, field) for field in fields}


def _yaml_scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.*?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    if value.startswith('"'):
        try:
            return str(json.loads(value)).strip()
        except json.JSONDecodeError:
            return value.strip('"').strip()
    return value.strip("' ")


def _materialization_manifest(
    root: Path,
    required: tuple[Path, ...],
    source_digest: str,
    outline: Path,
    scene_paths: list[Path],
    scenes: list[dict[str, object]],
    *,
    mode: str = "created",
) -> dict[str, object]:
    return {
        "schema": MATERIALIZATION_SCHEMA,
        "created_at": _now(),
        "source_digest": source_digest,
        "sources": [_relative(path, root) for path in required],
        "outline_path": _relative(outline, root),
        "scene_paths": [_relative(path, root) for path in scene_paths],
        "scene_count": len(scene_paths),
        "chapter_count": len({str(scene["chapter_id"]) for scene in scenes}),
        "status": "materialized",
        "materialization_mode": mode,
    }


def _result(
    root: Path,
    manifest_path: Path,
    outline: Path,
    scene_paths: list[Path],
    manifest: dict[str, object],
) -> LongformMaterializationResult:
    return LongformMaterializationResult(
        root, manifest_path, outline, tuple(scene_paths), int(manifest["chapter_count"])
    )


def _source_digest(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "LongformMaterializationResult",
    "longform_materialization_status",
    "materialize_longform_plan",
    "planned_longform_outputs",
    "scene_inventory_contract_issues",
]
