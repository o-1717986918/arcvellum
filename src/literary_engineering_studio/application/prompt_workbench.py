"""Versioned, scoped literary prompt editing over application-owned persistence."""

from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path
import re
from string import Formatter
from typing import Any

from literary_engineering_studio_engine.public.prompting import (
    PromptLayerOverride, PromptLayerSpec, ResolvedPromptLayer, list_prompt_assets, list_prompt_layer_specs,
    prompt_assembly_manifest, prompt_layer_spec, render_prompt_template, resolve_prompt_layer,
)

from .persistence_ports import PromptLayerRepositoryPort


class PromptWorkbenchService:
    def __init__(self, repository: PromptLayerRepositoryPort):
        self._repository = repository

    def resolve(self, layer_id: str, project_root: Path | None = None):
        spec = _spec(layer_id)
        if _is_project_template(layer_id):
            return _project_template_resolution(spec, project_root)
        global_record = self._repository.active("global", None, layer_id) if spec.editable else None
        project_record = (self._repository.active("project", project_root, layer_id)
                          if spec.editable and project_root is not None else None)
        return resolve_prompt_layer(
            spec,
            global_override=_override(layer_id, "global", global_record),
            project_override=_override(layer_id, "project", project_record),
        )

    def catalog(self, project_root: Path | None = None) -> dict[str, Any]:
        layers = []
        for spec in list_prompt_layer_specs():
            resolved = self.resolve(spec.layer_id, project_root)
            layers.append({**resolved.manifest(), "editable": spec.editable and
                           (project_root is not None or not _is_project_template(spec.layer_id)),
                           "default_text": spec.default_text,
                           "effective_text": resolved.text, "owner": spec.owner,
                           "usage_status": _usage_status(spec.layer_id, spec.responsibility)})
        assets = [_formal_asset_row(asset, self.resolve(_formal_layer_id(asset), project_root))
                  for asset in _formal_assets()]
        layers.extend(assets)
        return {"schema": "arcvellum/prompt-workbench/v1", "layers": layers, "formal_assets": assets}

    def history(self, layer_id: str, *, scope: str, project_root: Path | None = None) -> dict[str, Any]:
        _editable_spec(layer_id)
        _require_project_template_scope(layer_id, scope)
        return {"layer_id": layer_id, "scope": scope,
                "versions": self._repository.history(scope, project_root, layer_id),
                "effective": self.resolve(layer_id, project_root).manifest()}

    def save(self, layer_id: str, text: str, *, scope: str, project_root: Path | None = None,
             expected_digest: str = "") -> dict[str, Any]:
        _editable_spec(layer_id)
        _require_project_template_scope(layer_id, scope)
        self._check_current(layer_id, project_root, expected_digest)
        if not isinstance(text, str) or not text.strip() or len(text) > 12_000:
            raise ValueError("prompt layer text must be nonempty and at most 12000 characters")
        if _is_project_template(layer_id):
            return self._save_project_template(layer_id, text.strip(), project_root)
        entry = self._repository.save(scope, project_root, layer_id, text.strip())
        return {"saved": entry, "effective": self.resolve(layer_id, project_root).manifest()}

    def activate(self, layer_id: str, version: int, *, scope: str, project_root: Path | None = None,
                 expected_digest: str = "") -> dict[str, Any]:
        _editable_spec(layer_id)
        _require_project_template_scope(layer_id, scope)
        self._check_current(layer_id, project_root, expected_digest)
        if _is_project_template(layer_id):
            self._seed_project_template(layer_id, project_root)
        entry = self._repository.activate(scope, project_root, layer_id, version)
        if _is_project_template(layer_id):
            _write_project_template(_project_template_path(layer_id, project_root), str(entry["text"]))
        return {"activated": entry, "effective": self.resolve(layer_id, project_root).manifest()}

    def reset(self, layer_id: str, *, scope: str, project_root: Path | None = None,
              expected_digest: str = "") -> dict[str, Any]:
        _editable_spec(layer_id)
        _require_project_template_scope(layer_id, scope)
        self._check_current(layer_id, project_root, expected_digest)
        if _is_project_template(layer_id):
            self._seed_project_template(layer_id, project_root)
        self._repository.reset(scope, project_root, layer_id)
        if _is_project_template(layer_id):
            _write_project_template(_project_template_path(layer_id, project_root), _spec(layer_id).default_text)
        return {"effective": self.resolve(layer_id, project_root).manifest()}

    def _check_current(self, layer_id: str, project_root: Path | None, expected_digest: str) -> None:
        if expected_digest and self.resolve(layer_id, project_root).digest != expected_digest:
            raise ValueError("prompt layer changed since it was loaded; refresh before editing")

    def _save_project_template(self, layer_id: str, body: str, project_root: Path | None) -> dict[str, Any]:
        default_fields = _template_fields(_spec(layer_id).default_text)
        if _template_fields(body) != default_fields:
            raise ValueError("project template must preserve its registered input fields")
        path = _project_template_path(layer_id, project_root)
        self._seed_project_template(layer_id, project_root)
        entry = self._repository.save("project", project_root, layer_id, body)
        _write_project_template(path, body)
        return {"saved": entry, "effective": self.resolve(layer_id, project_root).manifest()}

    def _seed_project_template(self, layer_id: str, project_root: Path | None) -> None:
        current = self.resolve(layer_id, project_root).text
        active = self._repository.active("project", project_root, layer_id)
        if active is None or str(active["text"]) != current:
            self._repository.save("project", project_root, layer_id, current)

    def snapshot(self, layer_ids: tuple[str, ...], project_root: Path | None = None) -> dict[str, Any]:
        primary = next((layer_id for layer_id in layer_ids if _spec(layer_id).editable), layer_ids[0])
        identifiers = dict.fromkeys((*layer_ids, *_assembly_dependencies(primary)))
        layers = [self.resolve(layer_id, project_root) for layer_id in identifiers]
        assembled = _assembly_template(primary, {layer.layer_id: layer.text for layer in layers})
        return {**prompt_assembly_manifest(layers),
                "texts": {layer.layer_id: layer.text for layer in layers},
                "assembled_template": assembled,
                "assembly_kind": "template-with-runtime-slots" if assembled is not None else "layers-only"}


def _editable_spec(layer_id: str) -> None:
    if not _spec(layer_id).editable:
        raise ValueError("this prompt layer is fixed and cannot be edited")


def _formal_layer_id(asset: Any) -> str:
    return f"formal.asset.{asset.path.stem}"


@lru_cache(maxsize=1)
def _formal_assets() -> tuple[Any, ...]:
    return tuple(list_prompt_assets())


def _spec(layer_id: str) -> PromptLayerSpec:
    if layer_id.startswith("formal.asset."):
        asset = next((item for item in _formal_assets() if _formal_layer_id(item) == layer_id), None)
        if asset is None:
            raise ValueError(f"unknown prompt layer: {layer_id}")
        return PromptLayerSpec(layer_id, "formal-asset", asset.title, asset.body.strip(),
                               True, "Engine PromptAsset")
    return prompt_layer_spec(layer_id)


_PROJECT_TEMPLATES = frozenset({"legacy.template.scene_generation_system",
                                "legacy.template.scene_generation_user"})


def _is_project_template(layer_id: str) -> bool:
    return layer_id in _PROJECT_TEMPLATES


def _require_project_template_scope(layer_id: str, scope: str) -> None:
    if _is_project_template(layer_id) and scope != "project":
        raise ValueError("legacy project templates can only be edited within a work project")


def _project_template_path(layer_id: str, project_root: Path | None) -> Path:
    if not _is_project_template(layer_id) or project_root is None:
        raise ValueError("legacy project template needs a work project")
    root = project_root.resolve()
    if not root.is_dir() or not (root / "project.yaml").is_file():
        raise ValueError("legacy project template needs a valid work project")
    return root / "prompts" / f"{layer_id.removeprefix('legacy.template.')}.md"


def _project_template_resolution(spec: PromptLayerSpec, project_root: Path | None) -> ResolvedPromptLayer:
    if project_root is None:
        return resolve_prompt_layer(spec)
    path = _project_template_path(spec.layer_id, project_root)
    text = path.read_text(encoding="utf-8").strip() if path.is_file() else spec.default_text
    if not text or len(text) > 12_000:
        raise ValueError("legacy project template is empty or overlong")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source = "project-asset" if path.is_file() else "package"
    return ResolvedPromptLayer(spec.layer_id, spec.responsibility, spec.purpose, source,
                               digest[:12] if path.is_file() else str(spec.package_version),
                               text, digest, True)


def _template_fields(body: str) -> set[str]:
    try:
        return {field for _, field, _, _ in Formatter().parse(body) if field}
    except ValueError as exc:
        raise ValueError("project template has invalid format fields") from exc


def _write_project_template(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".prompt-tmp")
    temporary.write_text(body.rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)


def _override(layer_id: str, scope: str, record: dict[str, Any] | None) -> PromptLayerOverride | None:
    if record is None:
        return None
    return PromptLayerOverride(layer_id, scope, int(record["version"]), str(record["text"]))


def _formal_asset_row(asset: Any, resolved: Any) -> dict[str, Any]:
    return {**resolved.manifest(), "owner": "Engine PromptAsset", "path": str(asset.path),
            "prompt_asset_id": asset.prompt_asset_id,
            "default_text": asset.body.strip(), "effective_text": resolved.text,
            "usage_status": "formal-route"}


_ASSEMBLY_TARGETS = {
    "scene.creator.create": ("scene.creator.create.protocol", 0),
    "scene.creator.revise": ("scene.creator.revise.protocol", 0),
    "scene.review": ("scene.review.protocol", 3),
    "scene.performance.plan": ("scene.performance.plan.protocol", 4),
    "scene.actor.turn": ("scene.actor.interaction.protocol", 8),
    "scene.environment.turn": ("scene.environment.turn.protocol", 8),
    "scene.description.turn": ("scene.describer.turn.protocol", 1),
    "scene.describer.character": ("scene.describer.initialization.protocol", 1),
    "scene.describer.object": ("scene.describer.initialization.protocol", 1),
    "scene.describer.scene": ("scene.describer.initialization.protocol", 1),
    "advisor.identity": ("advisor.conversation.protocol", 11),
    "project_agent.creative_direction": ("project_agent.system.write.protocol", 2),
    "steward.identity": ("steward.decision.protocol", 0),
}


def _assembly_dependencies(layer_id: str) -> tuple[str, ...]:
    if layer_id.startswith("formal.asset."):
        return ("formal.prompt_program.v3",)
    if layer_id.startswith("advisor.persona."):
        return ("advisor.identity", "advisor.conversation.protocol")
    if layer_id == "scene.actor.identity":
        return ("scene.actor.immersion.protocol",)
    if layer_id == "scene.creator.identity":
        return ("scene.creator.create", "scene.creator.create.protocol")
    if layer_id in {"scene.creator.create", "scene.creator.revise"}:
        return ("scene.creator.identity", _ASSEMBLY_TARGETS[layer_id][0])
    if layer_id.startswith("scene.describer.") and layer_id in _ASSEMBLY_TARGETS:
        return (layer_id + ".protocol", "scene.describer.initialization.protocol")
    target = _ASSEMBLY_TARGETS.get(layer_id)
    return (target[0],) if target else ()


def _assembly_template(layer_id: str, texts: dict[str, str]) -> str | None:
    identity_preview = _identity_assembly_template(layer_id, texts)
    if identity_preview is not None:
        return identity_preview
    if layer_id.startswith("formal.asset."):
        placeholders = tuple(("〈当前任务用户方向〉\n\n" + texts[layer_id]) if index == 2
                             else f"〈运行时资料 {index}〉" for index in range(10))
        return render_prompt_template("formal.prompt_program.v3", placeholders)
    target_id = "scene.creator.create" if layer_id == "scene.creator.identity" else layer_id
    target = _ASSEMBLY_TARGETS.get(target_id)
    if target is None:
        return None
    template_id, literary_slot = target
    if target_id.startswith("scene.creator."):
        guidance = "\n\n".join((texts["scene.creator.identity"], texts[target_id]))
    elif target_id.startswith("scene.describer."):
        guidance = texts[target_id] + "\n" + texts[target_id + ".protocol"]
    else:
        guidance = texts[target_id]
    fixed = prompt_layer_spec(template_id).default_text
    indexes = {int(value) for value in re.findall(r"\[\[ARCVELLUM_PROMPT_(\d+)\]\]", fixed)}
    placeholders = tuple(guidance if index == literary_slot else f"〈运行时资料 {index}〉"
                         for index in range(max(indexes, default=-1) + 1))
    return render_prompt_template(template_id, placeholders)


def _identity_assembly_template(layer_id: str, texts: dict[str, str]) -> str | None:
    if layer_id == "scene.actor.identity":
        return "〈运行时作品人设与语言标签〉\n\n" + texts["scene.actor.immersion.protocol"] + "\n\n" + texts[layer_id]
    if layer_id == "scene.environment.identity":
        return "〈导演生成的环境六区块人格初始化〉\n\n" + texts[layer_id]
    if layer_id.startswith("advisor.persona."):
        values = tuple(texts[layer_id] if index == 3 else texts["advisor.identity"] if index == 11
                       else f"〈运行时资料 {index}〉" for index in range(12))
        return render_prompt_template("advisor.conversation.protocol", values)
    return None


def _usage_status(layer_id: str, responsibility: str) -> str:
    if layer_id.startswith("legacy.template."):
        return "legacy-project" if _is_project_template(layer_id) else "legacy"
    if layer_id in {"scene.length.legacy", "scene.interaction.direction",
                    "scene.interaction.direction.protocol", "scene.interaction.direction-repair.protocol",
                    "scene.ownership.repair.action.protocol", "scene.ownership.repair.dialogue.protocol"}:
        return "legacy"
    return "dynamic" if responsibility == "dynamic" else "active"
