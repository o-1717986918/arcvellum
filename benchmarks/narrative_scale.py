"""Synthetic narrative projection fixtures and measure-only benchmarks."""

from __future__ import annotations

import copy
import json
import platform
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable

from literary_engineering_studio.projections.narrative_projection_v3 import (
    build_narrative_projection_v3,
)
from literary_engineering_studio.projections.narrative.patches import (
    apply_projection_patch,
    build_projection_patch,
)
from literary_engineering_studio.projections.narrative_projection import (
    projection_delta,
    projection_motion_events,
)


SCENE_SCALES = (100, 300, 1000)
SCENES_PER_CHAPTER = 10


def build_scale_library(scene_count: int) -> dict[str, Any]:
    """Build stable literary evidence without touching a work project."""

    if scene_count < 1:
        raise ValueError("scene_count must be positive")
    character_count = max(4, min(24, scene_count // 20))
    characters = [
        {
            "id": f"character_{index + 1:03d}",
            "title": f"角色 {index + 1}",
            "status": "major" if index < 6 else "minor",
            "aliases": [f"代号 {index + 1}"],
            "path": f"characters/character_{index + 1:03d}.yaml",
        }
        for index in range(character_count)
    ]
    scenes = [_scene(index, character_count) for index in range(scene_count)]
    branches = [_branch(index) for index in range(0, scene_count, 7)]
    reviews = [_review(index) for index in range(0, scene_count, 5)]
    return {
        "sections": {
            "scenes": scenes,
            "characters": characters,
            "branches": branches,
            "reviews": reviews,
            "canon_patches": [],
        }
    }


def benchmark_narrative_projection(
    scene_counts: Iterable[int] = SCENE_SCALES,
    *,
    repetitions: int = 3,
) -> dict[str, Any]:
    """Measure book aggregation and detailed full-book projection."""

    repeat_count = max(1, int(repetitions))
    scales = tuple(int(value) for value in scene_counts)
    if not scales:
        raise ValueError("scene_counts must not be empty")
    samples: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="arcvellum-narrative-benchmark-") as temporary:
        root = Path(temporary)
        root.joinpath("project.yaml").write_text(
            "project:\n  title: Narrative Scale Benchmark\n",
            encoding="utf-8",
        )
        for scene_count in scales:
            library = build_scale_library(scene_count)
            samples.append(_measure_case(root, library, scene_count, "book", "", repeat_count))
            samples.append(
                _measure_case(
                    root,
                    library,
                    scene_count,
                    "scene",
                    f"scene_{max(1, scene_count // 2):04d}",
                    repeat_count,
                )
            )
        transition_sample = _measure_transition(root, max(scales))
    violations = validate_benchmark(samples)
    violations.extend(_validate_transition(transition_sample))
    return {
        "schema": "arcvellum/narrative-performance-baseline/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "executable": Path(sys.executable).name,
        },
        "method": {
            "repetitions": repeat_count,
            "warmups_per_case": 1,
            "source_scene_scales": list(scales),
        },
        "samples": samples,
        "transition_sample": transition_sample,
        "violations": violations,
    }


def validate_benchmark(samples: list[dict[str, Any]]) -> list[str]:
    """Check semantic completeness and broad trend health, not device speed."""

    violations: list[str] = []
    detailed: list[dict[str, Any]] = []
    for sample in samples:
        label = f"{sample.get('source_scene_count')}:{sample.get('level')}"
        if not sample.get("stable_revision"):
            violations.append(f"{label} projection revision is unstable")
        if int(sample.get("payload_bytes") or 0) <= 0:
            violations.append(f"{label} projection payload is empty")
        if sample.get("level") == "scene":
            detailed.append(sample)
            if int(sample.get("projected_node_count") or 0) < int(sample.get("source_scene_count") or 0):
                violations.append(f"{label} detailed projection lost source scenes")
    detailed.sort(key=lambda item: int(item["source_scene_count"]))
    if len(detailed) >= 2:
        smallest = max(float(detailed[0]["median_ms"]), 0.01)
        largest = float(detailed[-1]["median_ms"])
        source_ratio = int(detailed[-1]["source_scene_count"]) / int(detailed[0]["source_scene_count"])
        if largest / smallest > source_ratio * 4:
            violations.append("detailed projection growth exceeds the broad trend budget")
    return violations


def _measure_case(
    root: Path,
    library: dict[str, Any],
    scene_count: int,
    level: str,
    focus: str,
    repetitions: int,
) -> dict[str, Any]:
    _build_projection(root, library, level, focus)
    durations: list[float] = []
    projections: list[dict[str, Any]] = []
    for _ in range(repetitions):
        started = perf_counter()
        projection = _build_projection(root, library, level, focus)
        durations.append((perf_counter() - started) * 1000)
        projections.append(projection)
    payload = json.dumps(projections[-1], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    revisions = {str(item.get("revision") or "") for item in projections}
    return {
        "source_scene_count": scene_count,
        "level": level,
        "focus": focus,
        "projected_node_count": len(projections[-1].get("nodes") or []),
        "projected_edge_count": len(projections[-1].get("edges") or []),
        "payload_bytes": len(payload),
        "median_ms": round(statistics.median(durations), 3),
        "max_ms": round(max(durations), 3),
        "stable_revision": len(revisions) == 1 and bool(next(iter(revisions), "")),
    }


def _measure_transition(root: Path, scene_count: int) -> dict[str, Any]:
    library = build_scale_library(scene_count)
    changed = copy.deepcopy(library)
    changed_index = max(0, scene_count // 2 - 1)
    changed_scene = changed["sections"]["scenes"][changed_index]
    changed_scene["title"] = f"{changed_scene['title']}：语义更新"
    focus = str(changed_scene["id"])
    previous = _build_projection(root, library, "scene", focus)
    current = _build_projection(root, changed, "scene", focus)
    delta = projection_delta(previous, current)
    motion_events = projection_motion_events(previous, current, delta)
    patch = build_projection_patch(
        previous,
        current,
        sequence=2,
        delta=delta,
        motion_events=motion_events,
    )
    rebuilt = apply_projection_patch(previous, patch)
    full_bytes = _payload_size(current)
    patch_bytes = _payload_size(patch)
    return {
        "source_scene_count": scene_count,
        "level": "scene",
        "changed_scene_id": focus,
        "full_payload_bytes": full_bytes,
        "patch_payload_bytes": patch_bytes,
        "patch_ratio": round(patch_bytes / max(full_bytes, 1), 6),
        "upsert_node_count": len(patch["nodes"]["upsert"]),
        "upsert_edge_count": len(patch["edges"]["upsert"]),
        "changed_meta_keys": sorted(patch["meta"]),
        "exact_graph_rebuild": (
            rebuilt["projection_revision"] == current["projection_revision"]
            and rebuilt["nodes"] == current["nodes"]
            and rebuilt["edges"] == current["edges"]
        ),
    }


def _validate_transition(sample: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if float(sample.get("patch_ratio") or 1.0) >= 0.1:
        violations.append("single-node projection patch exceeds 10% of full payload")
    if int(sample.get("upsert_node_count") or 0) != 1:
        violations.append("single-node projection transition changed an unexpected node count")
    if not sample.get("exact_graph_rebuild"):
        violations.append("single-node projection patch does not rebuild the exact graph")
    return violations


def _payload_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _build_projection(
    root: Path,
    library: dict[str, Any],
    level: str,
    focus: str,
) -> dict[str, Any]:
    return build_narrative_projection_v3(
        {},
        root,
        level=level,
        focus=focus,
        grammar="spine",
        dashboard_payload={},
        library_payload=library,
    )


def _scene(index: int, character_count: int) -> dict[str, Any]:
    ordinal = index + 1
    scene_id = f"scene_{ordinal:04d}"
    chapter_id = f"chapter_{index // SCENES_PER_CHAPTER + 1:04d}"
    participants = [
        f"character_{index % character_count + 1:03d}",
        f"character_{(index + 3) % character_count + 1:03d}",
    ]
    facts = [
        {"label": "章节", "value": chapter_id},
        {"label": "参与者", "value": "、".join(participants)},
        {"label": "目标字数", "value": str(1200 + index % 5 * 160)},
    ]
    if ordinal % 6 == 0:
        facts.append({"label": "读者问题", "value": f"第 {ordinal} 场留下的问题如何改变后续选择？"})
    if ordinal % 9 == 0:
        facts.append({"label": "承诺回报", "value": f"第 {ordinal} 场的承诺必须在本卷内兑现或反转"})
    return {
        "id": scene_id,
        "title": f"场景 {ordinal}",
        "subtitle": chapter_id,
        "path": f"scenes/{scene_id}.yaml",
        "participants": participants,
        "participant_refs": participants,
        "facts": facts,
    }


def _branch(index: int) -> dict[str, Any]:
    scene_id = f"scene_{index + 1:04d}"
    return {
        "id": scene_id,
        "path": f"branches/{scene_id}/branch_manifest.json",
        "options": [
            {"id": "A", "label": "承担代价", "summary": "推进主线并保留关系压力", "selected": True},
            {"id": "B", "label": "延迟回应", "summary": "积累后续冲突", "selected": False},
        ],
    }


def _review(index: int) -> dict[str, Any]:
    scene_id = f"scene_{index + 1:04d}"
    return {
        "id": f"{scene_id}-review",
        "title": f"场景 {index + 1}审查",
        "path": f"reviews/{scene_id}_scene_review.json",
        "status": "pass" if index % 10 else "pass_with_notes",
    }
