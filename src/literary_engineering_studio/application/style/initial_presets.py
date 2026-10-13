"""Compute initial narrative profiles from declared, complete reference texts."""
import json
import re
from .stylometry_contracts import CorpusTextSource, StylePresetV1, StylePresetCollectionV1
from literary_engineering_studio_engine.public.literary import active_style_reference_catalog

PRESETS = (
    ("world-narration", "世界与风俗", "以丰盛、好奇而有讲述趣味的声音展开世界、奇异风俗、生活反复与时间来历。"),
    ("character-scene", "人物现场", "让有鲜明性情的人物带着兴趣、欲望和荒唐信念相遇，发展声音、喜剧、热情与处境变化。"),
    ("lyric-interior", "抒情与内心", "舒展感觉、记忆、思想、联想与情感，发展富有音乐性和想象力的句群与段落。"),
    ("ensemble-legend", "群像与传奇", "以群体经验、空间声势、生活复调与长时段讲述发展世界的规模、历史感和类型趣味。"),
)


def initialize_style_presets(service, root):
    stored = service.repository.presets(root)
    if stored.presets:
        return service.preset_catalog(root)
    references = active_style_reference_catalog(root)["references"]
    presets = []
    for ident, title, intent in PRESETS:
        presets.append(_measure_preset(service, root, references, ident, title, intent))
    service.save_presets(root, StylePresetCollectionV1(0, True, "world-narration", tuple(presets)), stored.revision)
    return service.preset_catalog(root)


def _measure_preset(service, root, references, ident, title, intent):
    rows = [row for row in references if ident in (row.get("narrative_modes") or [])]
    verified = [row for row in rows if row.get("source_kind") == "verified_literary_original"]
    if len(rows) < 3 or not verified:
        raise ValueError("initial presets require complete mode-labelled references and verified holdout sources")
    holdout = verified[-1]["unit_id"]
    supplied = [row for row in rows if row.get("source_kind") == "user_supplied_example"]
    sources = [CorpusTextSource("user-" + ident, "user-supplied-examples", "\n\n".join(row["text"] for row in supplied),
        topic=ident, genre=ident, origin="用户完整样段：" + ",".join(row["unit_id"] for row in supplied),
        revision=";".join(row["source_digest"] for row in supplied))]
    sources.extend(_verified_sources(verified, holdout, ident))
    sources = tuple(sources)
    profile = service.analyze(root, sources, title)
    version = service.save_version(root, profile["profile_id"], json.dumps(profile["controls"], ensure_ascii=False),
                                   title=title, intent=intent)
    return StylePresetV1(ident, title, intent, (ident,), tuple(row["unit_id"] for row in rows), version["version_id"])


def _verified_sources(verified, holdout, ident):
    return (CorpusTextSource(row["unit_id"].lower(), "verified-" + row["original_sha256"][:16], _measurement_text(row),
        split="holdout" if row["unit_id"] == holdout else "train", topic=ident, genre=ident,
        origin=row["source_title"] + " · " + row["source_url"], revision=row["source_digest"] + (";gutenberg-hardwrap-reflow/v1" if "老殘遊記" in row["source_title"] else "")) for row in verified)


def _measurement_text(row):
    text = row["text"]
    if row.get("source_kind") != "verified_literary_original" or "老殘遊記" not in row["source_title"]:
        return text
    # Source references remain verbatim. Only print-width wraps in this verified
    # Gutenberg edition are joined for measurement; blank paragraph gaps remain.
    return re.sub(r"(?<=[^\s])\r?\n(?=[^\s])", "", text)
