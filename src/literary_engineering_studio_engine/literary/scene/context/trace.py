"""Provenance trace builder for one materialized scene context packet."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from ....memory_index import trust_tier_for_relative_path
from ...style.snapshot import (
    active_style_evidence_paths,
    active_style_mount_snapshot_payload,
)


@dataclass(frozen=True)
class TraceEvidence:
    project: list[str]
    canon: list[str]
    plot: list[str]
    style: list[str]
    style_snapshot: dict[str, str]
    word_budget: list[str]
    characters: list[str]
    excluded_characters: list[str]
    summarized: list[str]


def build_context_trace_payload(
    *,
    root: Path,
    scene_path: Path,
    scene_id: str,
    context_path: Path,
    top_k: int,
    query: str,
    content: str,
    hits: Iterable[Any],
    loaded_character_ids: set[str],
    character_context_required: bool,
    handoff_ok: bool,
    handoff_message: str,
    handoff_payload: dict[str, object],
) -> dict[str, object]:
    hit_rows = list(hits)
    evidence = _collect_evidence(root, loaded_character_ids, hit_rows)
    scene_rel = relative_path(scene_path, root)
    handoff_path = _handoff_path(root, handoff_payload)
    groups = _context_groups(
        evidence,
        scene_rel=scene_rel,
        scene_exists=scene_path.exists(),
        character_required=character_context_required,
        handoff_ok=handoff_ok,
        handoff_path=handoff_path,
        handoff_message=handoff_message,
    )
    loaded_files = _loaded_files(evidence, scene_rel, handoff_path, root)
    source_records = _source_records(
        root,
        loaded_files,
        _source_roles(groups),
        groups,
    )
    retrieval_rows = _retrieval_rows(hit_rows)
    missing = [
        str(group["name"])
        for group in groups
        if group["required"] and not group["loaded"]
    ]
    if not handoff_ok:
        missing.append("previous_handoff")
    return _trace_payload(
        root=root,
        scene_id=scene_id,
        context_path=context_path,
        scene_rel=scene_rel,
        evidence=evidence,
        groups=groups,
        loaded_files=loaded_files,
        source_records=source_records,
        retrieval_rows=retrieval_rows,
        missing_required=missing,
        top_k=top_k,
        query=query,
        content=content,
        handoff_message=handoff_message,
        handoff_payload=handoff_payload,
    )


def _collect_evidence(
    root: Path,
    loaded_character_ids: set[str],
    hits: list[Any],
) -> TraceEvidence:
    style, style_snapshot = _style_evidence(root)
    return TraceEvidence(
        project=_existing_paths(root, ["project.yaml"]),
        canon=_existing_paths(
            root,
            [
                "canon/world_rules.yaml",
                "canon/timeline.yaml",
                "canon/facts.json",
                "canon/forbidden_changes.yaml",
            ],
        ),
        plot=_existing_paths(
            root,
            [
                "plot/outline.md",
                "plot/foreshadowing.csv",
                "plot/conflict_matrix.md",
                "plot/reader_questions/ledger.json",
                "plot/promises/ledger.json",
            ],
        ),
        style=style,
        style_snapshot=style_snapshot,
        word_budget=_existing_paths(
            root,
            ["plot/word_budget/word_budget.json", "plot/word_budget/word_budget.md"],
        ),
        characters=_loaded_character_paths(root, loaded_character_ids),
        excluded_characters=_excluded_character_paths(root, loaded_character_ids),
        summarized=sorted(
            {
                str(getattr(hit, "source", ""))
                for hit in hits
                if str(getattr(hit, "source", "")).strip()
            }
        ),
    )


def _context_groups(
    evidence: TraceEvidence,
    *,
    scene_rel: str,
    scene_exists: bool,
    character_required: bool,
    handoff_ok: bool,
    handoff_path: str,
    handoff_message: str,
) -> list[dict[str, object]]:
    return [
        _group("project", True, evidence.project, "Project identity and global targets."),
        _group("scene", True, [scene_rel] if scene_exists else [], "Formal scene contract."),
        _group("canon", bool(evidence.canon), evidence.canon, "Hard Canon constraints."),
        _group("characters", character_required, evidence.characters, "Major and scene-referenced characters."),
        _group("plot", False, evidence.plot, "Outline, foreshadowing, conflict, and reader ledgers."),
        _group("style", bool(evidence.style), evidence.style, "Mounted Style Skill or profile."),
        _group("word_budget", bool(evidence.word_budget), evidence.word_budget, "Scene length and narrative load."),
        _group("previous_handoff", not handoff_ok, [handoff_path] if handoff_path else [], handoff_message),
        _group("retrieval", False, evidence.summarized, "Soft memory; never overrides Canon."),
    ]


def _loaded_files(
    evidence: TraceEvidence,
    scene_rel: str,
    handoff_path: str,
    root: Path,
) -> list[str]:
    paths = {
        *evidence.project,
        scene_rel,
        *evidence.canon,
        *evidence.plot,
        *evidence.style,
        *evidence.word_budget,
        *evidence.characters,
        *evidence.summarized,
    }
    if handoff_path and (root / handoff_path).is_file():
        paths.add(handoff_path)
    return sorted(paths)


def _trace_payload(**values: Any) -> dict[str, object]:
    root: Path = values["root"]
    evidence: TraceEvidence = values["evidence"]
    handoff = values["handoff_payload"]
    source_records = values["source_records"]
    retrieval_rows = values["retrieval_rows"]
    return {
        "route": "scene-development",
        "scene_id": values["scene_id"],
        "context_packet": relative_path(values["context_path"], root),
        "scene_file": values["scene_rel"],
        "required_context_groups": values["groups"],
        "loaded_files": values["loaded_files"],
        "loaded_sources": source_records,
        "summarized_files": evidence.summarized,
        "excluded_files": evidence.excluded_characters,
        "style_mounts": evidence.style,
        "style_mount_snapshot": evidence.style_snapshot,
        "word_budget_source": evidence.word_budget[0] if evidence.word_budget else "",
        "character_files": evidence.characters,
        "canon_files": evidence.canon,
        "previous_scene_tail": values["handoff_message"],
        "previous_promoted_scene_sha": str(handoff.get("promoted_draft_sha256") or ""),
        "state_revision": _manifest_digest(root / "characters" / "state_patches"),
        "canon_revision": _manifest_digest(root / "canon" / "patches"),
        "style_mount_revision": _digest_paths(root, evidence.style),
        "word_budget_revision": _digest_paths(root, evidence.word_budget),
        "rhythm_plan_revision": _manifest_digest(root / "plot" / "rhythm_plan.json"),
        "retrieval_digest": _digest_value(retrieval_rows),
        "project_revision": _digest_value(source_records),
        "retrieval_evidence": retrieval_rows,
        "token_or_length_budget": {
            "top_k": values["top_k"],
            "query": values["query"],
            "retrieval_count": len(retrieval_rows),
            "context_chars": len(values["content"]),
        },
        "missing_required_context": values["missing_required"],
    }


def _handoff_path(root: Path, payload: dict[str, object]) -> str:
    path = str(payload.get("_path") or "")
    if not path and payload:
        previous = str(payload.get("scene_id") or "")
        path = f"workflow/handoffs/{previous}.json" if previous else ""
    return path if path and (root / path).is_file() else path


def _retrieval_rows(hits: list[Any]) -> list[dict[str, object]]:
    return [
        {
            "path": str(getattr(hit, "source", "")),
            "tier": str(getattr(hit, "trust_tier", "candidate")),
            "score": float(getattr(hit, "score", 0.0)),
            "adopted_reason": "Retrieval matched the scene query; formal sources retain priority.",
        }
        for hit in hits
    ]


def _source_roles(groups: list[dict[str, object]]) -> dict[str, tuple[str, bool]]:
    result: dict[str, tuple[str, bool]] = {}
    for group in groups:
        role = str(group.get("name") or "context")
        required = bool(group.get("required"))
        files = group.get("files") if isinstance(group.get("files"), list) else []
        for item in files:
            result[str(item)] = (role, required)
    return result


def _source_records(
    root: Path,
    paths: list[str],
    roles: dict[str, tuple[str, bool]],
    groups: list[dict[str, object]],
) -> list[dict[str, object]]:
    required_by_role = {
        str(group.get("name") or ""): bool(group.get("required"))
        for group in groups
    }
    rows: list[dict[str, object]] = []
    for relative in sorted(dict.fromkeys(paths)):
        path = root / relative
        if not path.is_file():
            continue
        role, required = roles.get(
            relative,
            ("retrieval", required_by_role.get("retrieval", False)),
        )
        rows.append(
            {
                "relative_path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "role": role,
                "trust_tier": trust_tier_for_relative_path(relative),
                "required": required,
                "loaded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return rows


def _digest_paths(root: Path, relatives: list[str]) -> str:
    return _digest_value(
        [
            {
                "path": relative,
                "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest(),
            }
            for relative in sorted(dict.fromkeys(relatives))
            if (root / relative).is_file()
        ]
    )


def _manifest_digest(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if path.is_dir():
        return _digest_value(
            [
                {"path": item.name, "sha256": hashlib.sha256(item.read_bytes()).hexdigest()}
                for item in sorted(path.glob("*.json"))
                if item.is_file()
            ]
        )
    return ""


def _digest_value(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _group(
    name: str,
    required: bool,
    files: list[str],
    notes: str,
) -> dict[str, object]:
    return {
        "name": name,
        "required": required,
        "loaded": bool(files),
        "files": sorted(dict.fromkeys(files)),
        "notes": notes,
    }


def _existing_paths(root: Path, relatives: list[str]) -> list[str]:
    return [relative for relative in relatives if _path_has_content(root / relative)]


def _path_has_content(path: Path) -> bool:
    if path.is_dir():
        return True
    if not path.is_file():
        return False
    try:
        return bool(path.read_text(encoding="utf-8", errors="ignore").strip())
    except OSError:
        return False


def _style_evidence(root: Path) -> tuple[list[str], dict[str, str]]:
    mounted = [relative_path(path, root) for path in active_style_evidence_paths(root)]
    files = mounted or _existing_paths(
        root,
        ["style/style-profile.md", "style/style_prompt.md"],
    )
    return files, active_style_mount_snapshot_payload(root)


def _loaded_character_paths(root: Path, character_ids: set[str]) -> list[str]:
    paths: list[str] = []
    for character_id in sorted(character_ids):
        for suffix in (".yaml", ".yml"):
            path = root / "characters" / f"{character_id}{suffix}"
            if path.exists():
                paths.append(relative_path(path, root))
                break
    return paths


def _excluded_character_paths(root: Path, loaded_ids: set[str]) -> list[str]:
    chars_dir = root / "characters"
    if not chars_dir.exists():
        return []
    return [
        relative_path(path, root)
        for path in sorted(chars_dir.glob("*.y*ml"))
        if not path.name.startswith("_") and path.stem not in loaded_ids
    ]


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


__all__ = ["build_context_trace_payload", "relative_path"]
