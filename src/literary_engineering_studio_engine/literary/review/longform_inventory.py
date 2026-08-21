"""Read-only project inventory collection for long-form audits."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from ...draft_text import count_delivery_chars, count_delivery_chinese_content_chars, final_body_from_draft_text
from ...narrative_rhythm import narrative_rhythm_contract
from ...scene_readiness import agent_review_gate_state, scene_flow_gate_issues, scene_readiness_status
from ..scene.promotion.historical_readiness import historical_scene_readiness
from .longform_analysis import scene_identity
from .longform_models import LongformSceneRecord


def scan_scenes(root: Path) -> list[LongformSceneRecord]:
    scene_dir = root / "scenes"
    if not scene_dir.exists():
        return []
    return [
        _scan_scene(root, path)
        for path in sorted(scene_dir.glob("*.yaml"))
        if not path.name.startswith("_")
    ]


def scan_characters(root: Path) -> list[dict[str, object]]:
    char_dir = root / "characters"
    if not char_dir.exists():
        return []
    characters = []
    for path in sorted(char_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = read_text(path)
        role = scalar(text, "role")
        characters.append(
            {
                "character_id": scalar(text, "character_id") or path.stem,
                "name": scalar(text, "name") or path.stem,
                "role": role,
                "role_label": re.split(r"(?:——|—|–|--|：|:)", role, maxsplit=1)[0].strip(),
                "aliases": list_after(text, "aliases"),
                "path": rel_str(path, root),
            }
        )
    return characters


def scan_foreshadowing(root: Path) -> list[dict[str, str]]:
    path = root / "plot" / "foreshadowing.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}
        for row in rows
    ]


def _scan_scene(root: Path, scene_path: Path) -> LongformSceneRecord:
    text = read_text(scene_path)
    identity = scene_identity(text, scene_path)
    paths = _scene_paths(root, identity[0])
    draft_text = read_text(paths["draft"])
    body = final_body_from_draft_text(draft_text) if draft_text else ""
    conclusion = review_conclusion(read_text(paths["review"]))
    historical = historical_scene_readiness(root, identity[0])
    flow_issues = () if historical is not None else scene_flow_gate_issues(root, identity[0])
    agent_state = agent_review_gate_state(root, paths["agent_json"], paths["draft"])
    if historical is not None:
        status, readiness_issues = historical
    else:
        status, readiness_issues = scene_readiness_status(
            root,
            draft_path=paths["draft"],
            review_path=paths["review"],
            agent_review_json_path=paths["agent_json"],
            body=body,
            static_review_conclusion=conclusion,
            flow_gate_issues=flow_issues,
            agent_review_state=agent_state,
        )
    rhythm = narrative_rhythm_contract(root, scene_path, paths["composition"])
    return _scene_record(
        root, scene_path, text, identity, paths, body, conclusion,
        flow_issues, agent_state, status, readiness_issues, rhythm,
    )


def _scene_record(
    root: Path,
    scene_path: Path,
    text: str,
    identity: tuple[str, str, str, str],
    paths: dict[str, Path],
    body: str,
    conclusion: str,
    flow_issues: tuple[str, ...],
    agent_state: dict[str, object],
    status: str,
    readiness_issues: tuple[str, ...],
    rhythm: dict[str, object],
) -> LongformSceneRecord:
    rhythm_payload = rhythm.get("narrative_rhythm") if isinstance(rhythm.get("narrative_rhythm"), dict) else {}
    bridge = rhythm.get("scene_bridge") if isinstance(rhythm.get("scene_bridge"), dict) else {}
    scene_id, volume_id, chapter_id, viewpoint = identity
    return LongformSceneRecord(
        scene_id=scene_id, volume_id=volume_id, chapter_id=chapter_id,
        scene_path=rel_str(scene_path, root), location=scalar(text, "location"),
        participants=tuple(list_after(text, "participants")), viewpoint=viewpoint,
        scene_goal=scalar(text, "scene_goal"), draft_path=existing_rel(paths["draft"], root),
        review_path=existing_rel(paths["review"], root), review_conclusion=conclusion,
        agent_review_path=existing_rel(paths["agent_md"], root),
        agent_review_json=existing_rel(paths["agent_json"], root),
        agent_review_conclusion=str(agent_state.get("conclusion") or ""),
        agent_review_schema_status=str(agent_state.get("schema_status") or ""),
        agent_review_source_match=bool(agent_state.get("source_match")),
        agent_review_unresolved_notes=tuple(str(item) for item in agent_state.get("unresolved_notes", [])),
        style_adherence_status=str(agent_state.get("style_adherence_status") or ""),
        word_budget_adherence_status=str(agent_state.get("word_budget_adherence_status") or ""),
        reader_experience_adherence_status=str(agent_state.get("reader_experience_adherence_status") or ""),
        reader_promise_satisfied=bool(agent_state.get("reader_promise_satisfied")),
        narrative_rhythm_status=str(rhythm.get("status") or ""),
        rhythm_role=str(rhythm_payload.get("rhythm_role") or ""), pace=str(rhythm_payload.get("pace") or ""),
        tension_curve=rhythm_payload.get("tension_curve"),
        scene_function=tuple(string_list(rhythm_payload.get("scene_function"))),
        scene_turn=str(rhythm_payload.get("scene_turn") or ""),
        reader_effect=str(rhythm_payload.get("reader_effect") or ""),
        incoming_pressure=str(bridge.get("incoming_pressure") or ""), outgoing_hook=outgoing_hook_text(bridge),
        flow_gate_issues=flow_issues, readiness_issues=readiness_issues,
        draft_chars=count_delivery_chinese_content_chars(body),
        draft_machine_chars=count_delivery_chars(body), status=status,
    )


def _scene_paths(root: Path, scene_id: str) -> dict[str, Path]:
    return {
        "draft": root / "drafts" / "scenes" / f"{scene_id}.md",
        "review": root / "reviews" / f"{scene_id}-review.md",
        "agent_md": root / "reviews" / "agent" / f"{scene_id}_scene_review.md",
        "agent_json": root / "reviews" / "agent" / f"{scene_id}_scene_review.json",
        "composition": root / "drafts" / "compositions" / f"{scene_id}_composition.json",
    }


def review_conclusion(text: str) -> str:
    match = re.search(r"(?m)^-\s*结论：\s*(\S+)\s*$", text)
    return match.group(1).strip() if match else ""


def scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    return match.group(1).strip().strip("\"'") if match else ""


def list_after(text: str, key: str) -> list[str]:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return []
    inline = match.group(1).strip()
    if inline.startswith("[") and inline.endswith("]"):
        return [item.strip().strip("\"'") for item in inline.strip("[]").split(",") if item.strip()]
    return _block_list(text[match.end() :])


def _block_list(text: str) -> list[str]:
    values = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            values.append(stripped.strip("- ").strip("\"'"))
        elif re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
            break
    return values


def string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def outgoing_hook_text(bridge: dict[str, object]) -> str:
    direct = str(bridge.get("outgoing_hook") or "").strip()
    if direct:
        return direct
    hooks = bridge.get("outgoing_hooks")
    if not isinstance(hooks, list):
        return ""
    parts = [
        str(item.get("content") or item.get("summary") or "").strip() if isinstance(item, dict) else str(item).strip()
        for item in hooks
    ]
    return "；".join(item for item in parts if item)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def existing_rel(path: Path, root: Path) -> str:
    return rel_str(path, root) if path.exists() else ""


__all__ = ["rel_str", "scan_characters", "scan_foreshadowing", "scan_scenes"]
