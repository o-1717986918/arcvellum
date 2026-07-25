"""Real-project performance gate for the complete narrative read model."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable

from literary_engineering_studio.projections.narrative_projection_v3 import build_narrative_projection_v3
from literary_engineering_studio_engine.project_library import build_narrative_evidence

from .narrative_visual_fixture import materialize_narrative_visual_fixture


SCENE_SCALES = (100, 300, 1000)
MAX_PAYLOAD_BYTES_PER_SCENE = 5_000
MAX_1000_EVIDENCE_MS = 8_000
MAX_1000_PROJECTION_MS = 8_000


def benchmark_materialized_narrative(scene_counts: Iterable[int] = SCENE_SCALES) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="arcvellum-visual-benchmark-") as temporary:
        base = Path(temporary)
        for count in (int(value) for value in scene_counts):
            samples.append(_measure(base / f"scenes-{count}", count))
    return {
        "schema": "arcvellum/materialized-narrative-performance/v1",
        "samples": samples,
        "violations": validate_materialized_narrative(samples),
    }


def validate_materialized_narrative(samples: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for sample in samples:
        count = int(sample.get("scene_count") or 0)
        if int(sample.get("evidence_scene_count") or 0) != count:
            violations.append(f"{count}: complete evidence lost scenes")
        if int(sample.get("projection_scene_count") or 0) != count:
            violations.append(f"{count}: projection lost scenes")
        if int(sample.get("unresolved_character_refs") or 0):
            violations.append(f"{count}: fixture produced unresolved character references")
        if int(sample.get("payload_bytes") or 0) > max(500_000, count * MAX_PAYLOAD_BYTES_PER_SCENE):
            violations.append(f"{count}: payload growth is not bounded")
        if count >= 1000 and float(sample.get("evidence_ms") or 0) > MAX_1000_EVIDENCE_MS:
            violations.append(f"{count}: complete evidence read exceeded {MAX_1000_EVIDENCE_MS} ms")
        if count >= 1000 and float(sample.get("projection_ms") or 0) > MAX_1000_PROJECTION_MS:
            violations.append(f"{count}: projection exceeded {MAX_1000_PROJECTION_MS} ms")
    return violations


def _measure(root: Path, scene_count: int) -> dict[str, Any]:
    started = perf_counter()
    materialize_narrative_visual_fixture(root, scene_count)
    materialize_ms = _elapsed_ms(started)
    started = perf_counter()
    cold_evidence = build_narrative_evidence(root)
    cold_evidence_ms = _elapsed_ms(started)
    started = perf_counter()
    _project(root, scene_count, cold_evidence)
    cold_projection_ms = _elapsed_ms(started)
    started = perf_counter()
    evidence = build_narrative_evidence(root)
    evidence_ms = _elapsed_ms(started)
    started = perf_counter()
    projection = _project(root, scene_count, evidence)
    projection_ms = _elapsed_ms(started)
    encoded = json.dumps(projection, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    references = projection.get("character_references") if isinstance(projection.get("character_references"), list) else []
    summary = projection.get("summary") if isinstance(projection.get("summary"), dict) else {}
    sections = evidence.get("sections") if isinstance(evidence.get("sections"), dict) else {}
    return {
        "scene_count": scene_count,
        "evidence_scene_count": len(sections.get("scenes") or []),
        "projection_scene_count": int(summary.get("scene_count") or 0),
        "node_count": len(projection.get("nodes") or []),
        "edge_count": len(projection.get("edges") or []),
        "unresolved_character_refs": sum(
            1 for item in references if isinstance(item, dict) and item.get("resolution") == "unresolved"
        ),
        "materialize_ms": materialize_ms,
        "cold_evidence_ms": cold_evidence_ms,
        "cold_projection_ms": cold_projection_ms,
        "evidence_ms": evidence_ms,
        "projection_ms": projection_ms,
        "payload_bytes": len(encoded),
    }


def _project(root: Path, scene_count: int, evidence: dict[str, Any]) -> dict[str, Any]:
    return build_narrative_projection_v3(
        {},
        root,
        level="scene",
        focus=f"scene_{max(1, scene_count // 2):04d}",
        grammar="story-river",
        dashboard_payload={"ok": True},
        library_payload={"ok": True, **evidence},
    )


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
