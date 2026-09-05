"""Scene-development audit coordination and downstream waiting projection."""
from __future__ import annotations

from pathlib import Path
import re

from ...route_audit_common import _read_json, _read_text
from ...route_audit_evidence import _review_needs_revision
from ..historical_truth import preserve_current_historical_style_gates
from ..scene_scope import started_scene_ids as _started_scene_ids
from .scene_candidate import add_scene_candidate_gates
from .scene_completion import add_scene_completion_gates
from .scene_planning import add_scene_planning_gates


_SCENE_GATE_PHASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("上下文", ("context-",)),
    ("角色推演", ("roleplay-",)),
    ("分支决策", ("branch-",)),
    ("编剧准备", ("scene-word-budget-", "reader-experience-", "narrative-rhythm-", "composition-")),
    ("候选生成", ("prose-candidate", "candidate-generation-", "generation-agent-task-", "style-lint-", "candidate-word-budget")),
    ("候选审查", ("agent-review-", "candidate-review-", "revision-evasion-", "style-adherence-review")),
    ("晋升", ("promotion-", "promoted-draft")),
    ("静态审查", ("static-review-",)),
    ("状态写回", ("state-", "canon-writeback", "continuity-ledger-", "scene-handoff")),
)


def _scene_gate_phase(key: str) -> tuple[int, str]:
    """Return the formal scene stage for one route-audit gate."""

    label = key.split(":", 1)[-1]
    for index, (name, prefixes) in enumerate(_SCENE_GATE_PHASES):
        if label.startswith(prefixes):
            return index, name
    return len(_SCENE_GATE_PHASES), "后续步骤"


def _mark_waiting_scene_gates(gates: list[dict[str, str]]) -> None:
    """Demote unreachable downstream failures to an informational wait."""

    failed_phases = [
        _scene_gate_phase(str(gate["key"]))[0]
        for gate in gates
        if gate.get("status") == "fail" and gate.get("severity") == "blocking"
    ]
    if not failed_phases:
        return
    active_phase = min(failed_phases)
    active_phase_name = (
        _SCENE_GATE_PHASES[active_phase][0]
        if active_phase < len(_SCENE_GATE_PHASES)
        else "后续步骤"
    )
    for gate in gates:
        phase, _ = _scene_gate_phase(str(gate["key"]))
        if phase <= active_phase or gate.get("status") != "fail" or gate.get("severity") != "blocking":
            continue
        original_message = str(gate.get("message") or "")
        gate["status"] = "waiting"
        gate["severity"] = "info"
        gate["message"] = f"等待“{active_phase_name}”阶段的阻塞门禁先解决，尚未到达本步骤。原检查：{original_message}"


def _scene_files(root: Path) -> list[Path]:
    scenes = root / "scenes"
    if not scenes.exists():
        return []
    return sorted(path for path in scenes.glob("*.yaml") if not path.name.startswith("_"))


def _scene_audit_scope(root: Path) -> dict[str, int]:
    scene_files = _scene_files(root)
    started_ids = _started_scene_ids(root)
    started = sum(1 for scene_path in scene_files if _scene_id(scene_path) in started_ids)
    return {
        "total_scene_count": len(scene_files),
        "started_scene_count": started,
        "planned_scene_count": len(scene_files) - started,
    }


def _add_scene_development_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_path: Path,
) -> None:
    """Project one scene through the established gate order."""

    first_scene_gate = len(gates)
    scene_id = _scene_id(scene_path)
    add_scene_planning_gates(gates, root, scene_path, scene_id)
    review_payload = add_scene_candidate_gates(gates, root, scene_id)
    add_scene_completion_gates(gates, root, scene_id, review_payload)
    scene_gates = gates[first_scene_gate:]
    preserve_current_historical_style_gates(root, scene_id, scene_gates)
    _mark_waiting_scene_gates(scene_gates)


def _scene_id(scene_path: Path) -> str:
    text = _read_text(scene_path)
    match = re.search(r"(?m)^\s*scene_id:\s*['\"]?([^'\"\n#]+)", text)
    scene_id = match.group(1).strip() if match else ""
    return scene_id or scene_path.stem


def _unresolved_scene_review_count(root: Path) -> int:
    review_dir = root / "reviews" / "agent"
    if not review_dir.exists():
        return 0
    unresolved = 0
    for path in sorted(review_dir.glob("*_scene_review.json")):
        payload = _read_json(path)
        scene_id = path.name[: -len("_scene_review.json")]
        if not _review_needs_revision(payload):
            continue
        report = root / "drafts" / "revisions" / f"{scene_id}_revision_report.md"
        manifest = root / "drafts" / "revisions" / f"{scene_id}_revision.json"
        if not (report.exists() and manifest.exists()):
            unresolved += 1
    return unresolved
