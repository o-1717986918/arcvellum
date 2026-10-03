"""Build an offline review folio from the Engine's public prompt registry."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile

from literary_engineering_studio_engine.public.prompting import list_prompt_layer_specs, prompt_layer_spec


TOOL = Path(__file__).resolve().parent


def include_actor_history(slots: list, sources: dict) -> str:
    """Keep the previous template readable and identify its exact retired prefix."""
    source_id = "scene.v2.material.actor@package-v2"
    text = (TOOL / "history/scene.v2.material.actor.v2.md").read_text(encoding="utf-8").strip()
    sources[source_id] = {
        "id": source_id, "text": text, "package_version": 2,
        "sha256": sha256(text.encode("utf-8")).hexdigest(),
        "purpose": "历史 v2 角色卡（含已删除的前置说明）",
        "editable": False, "owner": "Historical builtin snapshot",
    }
    next(slot for slot in slots if slot["id"] == "scene.v2.material.actor")["refs"].append(source_id)
    return text[:text.index("【PERSONA_LOAD】")]


def read_library() -> dict:
    slots = json.loads((TOOL / "slots.json").read_text(encoding="utf-8"))
    expected = {spec.layer_id for spec in list_prompt_layer_specs()
                if spec.layer_id.startswith(("scene.v2.", "project_agent.v2.")) or spec.layer_id == "project_agent.creator_persona.v2"}
    assert {slot["id"] for slot in slots if slot["scope"] == "v2"} == expected
    ids = dict.fromkeys(layer_id for slot in slots for layer_id in [slot["id"], *slot["refs"]]
                        if "@2026-10-03" not in layer_id)
    sources = {}
    for layer_id in ids:
        spec = prompt_layer_spec(layer_id)
        sources[layer_id] = {
            "id": layer_id, "text": spec.default_text, "package_version": spec.package_version,
            "sha256": sha256(spec.default_text.encode("utf-8")).hexdigest(),
            "purpose": spec.purpose, "editable": spec.editable, "owner": spec.owner,
        }
    assert all("[PENDING_PROMPT_DESIGN:" not in sources[layer_id]["text"] for layer_id in expected)
    include_rebuild_history(slots, sources)
    retired_intro = include_actor_history(slots, sources)
    return {
        "slots": slots, "sources": sources,
        "migrations": {"retired_actor_intro": retired_intro},
        "manifest": {
            "schema": "arcvellum/prompt-library-snapshot/v1", "scope": "builtin_assets_with_history",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "sources": [{key: source[key] for key in ("id", "package_version", "sha256")}
                        for source in sources.values()],
        },
    }


def include_rebuild_history(slots: list, sources: dict) -> None:
    manifest = json.loads((TOOL / "history/2026-10-03/manifest.json").read_text(encoding="utf-8"))
    for slot in slots:
        path = TOOL / "history/2026-10-03" / (slot["id"] + ".md")
        if not path.is_file():
            continue
        source_id = slot["id"] + "@2026-10-03"
        text = path.read_text(encoding="utf-8").strip()
        sources[source_id] = {"id": source_id, "text": text,
            "package_version": manifest["layers"][slot["id"]]["package_version"],
            "sha256": sha256(text.encode("utf-8")).hexdigest(), "purpose": "此次重写前的完整文案",
            "editable": False, "owner": "Historical builtin snapshot " + manifest["commit"]}


def render_html(library: dict) -> str:
    html = (TOOL / "index.template.html").read_text(encoding="utf-8")
    tokens = {
        "__DESK_CSS__": (TOOL / "desk.css").read_text(encoding="utf-8"),
        "__PROMPT_LIBRARY__": json.dumps(library, ensure_ascii=False).replace("<", "\\u003c"),
        "__DESK_STATE__": (TOOL / "state.js").read_text(encoding="utf-8"),
        "__DESK_REVIEW__": (TOOL / "review.js").read_text(encoding="utf-8"),
        "__DESK_FILES__": (TOOL / "files.js").read_text(encoding="utf-8"),
    }
    for token in tokens:
        assert html.count(token) == 1
    return re.sub("|".join(re.escape(token) for token in tokens),
                  lambda match: tokens[match.group()], html)


def draft_submission(library: dict) -> dict:
    rows = []
    for slot in library["slots"]:
        source = library["sources"][slot["id"]]
        rows.append({
            "id": slot["id"], "group": slot["group"], "title": slot["title"], "scope": slot["scope"],
            "slot_type": "retired" if slot.get("retired") else "transport" if "transport." in slot["id"] else "fixed_protocol" if slot["fixed"] else "literary_design",
            "runtime_loading": "retired" if slot.get("retired") else "proposed",
            "status": "draft", "content": source["text"], "design_note": "",
            "legacy_references": slot["refs"],
            "origin": {"type": "builtin_draft", "sources": [
                {key: source[key] for key in ("id", "package_version", "sha256")} | {"scope": "builtin_snapshot"}
            ]}, "review_decision": None,
        })
    return {
        "schema": "arcvellum/prompt-design-submission/v2",
        "exported_at": library["manifest"]["built_at"], "project_title": "场景主创 v2 提示词初稿",
        "general_notes": "正向文学初始化与自然交付；两位共同层已退出，技术整理单列；尚待人审与文学场景验收。",
        "slot_count": len(rows), "filled_count": len(rows), "approved_count": 0,
        "source_snapshot": library["manifest"], "runtime_activation": "unchanged", "slots": rows,
    }


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    package = output / "scene-prompt-review-package"
    package.mkdir(exist_ok=True)
    library = read_library()
    html = render_html(library)
    desk = output / "scene-prompt-design-desk.html"
    desk.write_text(html, encoding="utf-8")
    (package / desk.name).write_text(html, encoding="utf-8")
    write_json(package / "prompt-design-submission.json", draft_submission(library))
    write_json(package / "prompt-library-snapshot.json", library)
    for slot in library["slots"]:
        (package / (slot["id"] + ".md")).write_text(library["sources"][slot["id"]]["text"] + "\n", encoding="utf-8")
    (package / "README.md").write_text((TOOL / "README.md").read_text(encoding="utf-8"), encoding="utf-8")
    (package / "design-notes.md").write_text((TOOL / "design-notes.md").read_text(encoding="utf-8"), encoding="utf-8")
    archive = output / "scene-prompt-review-desk.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(package.iterdir()):
            if path.is_file():
                bundle.write(path, arcname=path.name)
    return {"desk": str(desk), "package": str(package), "zip": str(archive),
            "v2_draft_count": sum(slot["scope"] == "v2" and not slot.get("retired") for slot in library["slots"]),
            "source_count": len(library["sources"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Artifact output directory")
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
