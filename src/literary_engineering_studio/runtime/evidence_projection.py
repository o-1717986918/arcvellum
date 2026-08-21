"""Loss-preserving structured projections for Prompt v3 evidence."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import PurePosixPath

from ruamel.yaml import YAML

from .evidence_projection_common import prune_empty
from .evidence_projection_literary import (
    creative_quality,
    project_identity,
    prose_chapter_obligation,
    prose_scene,
    prose_word_budget,
)
from .evidence_projection_review import (
    committee_longform_audit,
    review_context,
    revision_review,
)
from .evidence_projection_writeback import (
    canon_scene_review,
    composition_review,
    continuity_prose,
    continuity_scene,
    prose_composition,
    prose_context_packet,
    state_character,
    state_composition,
    state_patch,
    state_scene,
)


_JSON_PROJECTIONS = {
    "prose-composition": prose_composition,
    "composition-review": composition_review,
    "prose-chapter-obligation": prose_chapter_obligation,
    "revision-review": revision_review,
    "committee-longform-audit": committee_longform_audit,
    "state-patch": state_patch,
    "state-composition": state_composition,
    "canon-scene-review": canon_scene_review,
    "canon-state-boundary": state_patch,
}
_YAML_PROJECTIONS = {
    "prose-scene": prose_scene,
    "project-identity": project_identity,
    "continuity-scene": continuity_scene,
    "state-character": state_character,
    "state-scene": state_scene,
    "canon-scene": state_scene,
}


def project_evidence_body(
    path: str,
    body: str,
    *,
    fidelity: str,
    projection: str = "default",
    scene_id: str = "",
    chapter_id: str = "",
) -> str:
    """Project one evidence body while preserving the public compiler contract."""

    if projection == "prose-context-packet":
        return prose_context_packet(body)
    if projection in {"continuity-prose", "state-prose", "canon-prose"}:
        return continuity_prose(body)
    if fidelity != "structured" and projection not in {
        "state-patch", "state-character", "canon-state-boundary",
    }:
        return body
    suffix = PurePosixPath(path).suffix.casefold()
    try:
        if suffix == ".json":
            payload = _project_json(path, body, projection, scene_id, chapter_id)
            return json.dumps(prune_empty(payload), ensure_ascii=False, separators=(",", ":"))
        if suffix in {".yaml", ".yml"}:
            payload = YAML(typ="safe").load(body)
            projector = _YAML_PROJECTIONS.get(projection)
            if projector is not None:
                payload = projector(payload)
            stream = StringIO()
            writer = YAML()
            writer.default_flow_style = False
            writer.allow_unicode = True
            writer.dump(prune_empty(payload), stream)
            return stream.getvalue().rstrip()
    except (ValueError, TypeError, OSError):
        return body
    return body


def _project_json(
    path: str,
    body: str,
    projection: str,
    scene_id: str,
    chapter_id: str,
) -> object:
    payload = json.loads(body)
    if projection == "prose-word-budget":
        return prose_word_budget(payload, scene_id=scene_id, chapter_id=chapter_id)
    projector = _JSON_PROJECTIONS.get(projection)
    if projector is not None:
        return projector(payload)
    if path.endswith("scene_review.context.json"):
        return review_context(payload)
    if path == "style/creative_quality_profile.json":
        return creative_quality(payload)
    return payload


__all__ = ["project_evidence_body"]
