"""Creator selects literary references before material commissioning and freeze."""
import json

from ..application.style.transaction_bundle import TransactionStyleBundleV1, bundle_digest
from ..application.creator_persona import CreatorPersonaStore
from .scene_creator_briefing import scene_creator_style
from .scene_natural_output import creator_style, render_style
from .style_choice_prompt import style_choice_prompt
from literary_engineering_studio_engine.public.literary import character_field_value, read_character_text


class TransactionStyleSelectionMixin:
    def _prepare_transaction_style_bundle(self, transaction_id, brief):
        path = self._cache_path(transaction_id, "transaction_style_bundle.json")
        if path.is_file():
            return self._publish_style_bundle(TransactionStyleBundleV1.validate(_read(path)))
        provider = getattr(self, "_style_preset_catalog_provider", None)
        if not provider or not self._uses_creator_v2(transaction_id):
            return None
        if (self._cache_path(transaction_id, "prompt_assembly_v2.json").is_file()
                and not self._cache_path(transaction_id, "style_selection/catalog.json").is_file()):
            return None  # Existing transactions retain their initial loading contract.
        catalog_path = self._cache_path(transaction_id, "style_selection/catalog.json")
        if catalog_path.is_file():
            catalog = _read(catalog_path)
        else:
            catalog = provider(self._project_root)
            if not catalog.get("enabled") or not catalog.get("presets"):
                return None
            catalog["base_style"] = scene_creator_style(self._project_root)
            catalog["tone_enabled"] = self._config.get("application", {}).get("less_ai_tone_experiment", {}).get("enabled") is True
            _save(catalog_path, catalog)
        selection = self._select_transaction_style(transaction_id, brief, catalog)
        preset = next(row for row in catalog["presets"] if row["preset_id"] == selection["preset_id"])
        style, mount = _selected_style(catalog, selection, preset)
        bundle = TransactionStyleBundleV1(transaction_id, catalog["revision"], selection, style, mount,
            catalog["tone_enabled"], _work_material_scope(self._project_root)).to_dict()
        _save(path, bundle)
        self._style_event("scene.style-bundle.frozen", transaction_id,
                          {"digest": bundle["digest"], "preset_id": selection["preset_id"]})
        return self._publish_style_bundle(bundle)

    def _select_transaction_style(self, transaction_id, brief, catalog):
        path = self._cache_path(transaction_id, "style_selection/choice.json")
        if path.is_file():
            return _read(path)
        layers = self._v2_prompt_snapshot(transaction_id)["texts"]
        persona = CreatorPersonaStore(self._data_root).read(self._project_root).get("versions") or []
        if not persona or not CreatorPersonaStore(self._data_root).read_current(self._project_root)["active"]:
            raise ValueError("style selection requires the work-level creator persona")
        style = catalog["base_style"]
        system = render_style(layers["scene.v2.creator.identity"], creator_style(style_briefing(style)))
        prompt = style_choice_prompt(brief, catalog)
        original = self._cache_path(transaction_id, "style_selection/original.md")
        if original.is_file():
            answer = original.read_text(encoding="utf-8")
        else:
            answer = self._tone_invoke(transaction_id, system + "\n\n" + persona[-1]["text"], prompt,purpose="style-choice")
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_text(answer, encoding="utf-8")
        choice = self._natural_processor(transaction_id, layers).process(answer, kind="style-choice",
            context={"preset_ids": [row["preset_id"] for row in catalog["presets"] if row["active"]],
                     "reference_ids": [row["unit_id"] for row in catalog.get("reference_catalog", {}).get("references", [])]})
        _save(path, choice)
        return choice

    def _publish_style_bundle(self, bundle):
        for name, value in (("creator_stylometry_snapshot.json", bundle["measurement"]),
                            ("creator_style_briefing.json", bundle["style"])):
            path = self._cache_path(bundle["transaction_id"], name)
            if path.is_file() and _read(path) != value:
                raise ValueError("frozen style projection disagrees with transaction bundle")
            _save(path, value)
        return bundle



def _selected_style(catalog, selection, preset):
    style = catalog["base_style"]
    style["preset_direction"] = {"content": "【本次文学用途】\n" + preset.get("literary_intent", "")}
    style["selected_strategy"] = {"content": "【主创的开场文学判断】\n" + selection["literary_mode"] + "\n" + selection["reason"]}
    refs = catalog.get("reference_catalog", {}).get("references", [])
    chosen = [next(row for row in refs if row["unit_id"] == ident) for ident in selection["reference_ids"]]
    style["references"] = {"content": "\n\n".join(
        f"### {row['unit_id']} · {row.get('source_title', '')}\n{row['text']}" for row in chosen),
        "items": chosen, "selection_reason": selection["reason"], "complete": True}
    mount = preset["snapshot"]
    if mount["usage"] == "guide":
        style["stylometry"] = {"content": mount["fragment_text"], "combine": mount["combine"],
                                "version_id": mount["version_id"], "content_sha256": mount["content_sha256"]}
    style["preset"] = {key: value for key, value in preset.items() if key != "snapshot"}
    style["assembled"] = {"content": creator_style(style_briefing(style)), "complete": True}
    style["assembled"]["sha256"] = bundle_digest(style["assembled"]["content"])
    return style, mount

def style_briefing(style):
    return {"style": style}


def _work_material_scope(root):
    paths = [path for path in sorted((root / "characters").glob("*.yaml")) if not path.name.startswith("_")]
    return {"version": "work-v1", "actor_targets": [character_field_value(read_character_text(path), "name") or path.stem for path in paths],
            "sources": [path.relative_to(root).as_posix() for path in paths],
            "actor_refs": {character_field_value(read_character_text(path), "name") or path.stem: path.relative_to(root).as_posix() for path in paths}}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
