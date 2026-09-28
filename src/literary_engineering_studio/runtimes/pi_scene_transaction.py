"""Pi Worker adapter for lean scene create and conditional review calls."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from literary_engineering_studio_engine.public.prompting import (
    list_prompt_layer_specs, prompt_assembly_manifest, resolve_prompt_layer,
)
from literary_engineering_studio_engine.public.literary import (
    CreativeResult,
    ReviewResult,
    SceneBrief,
    VerificationReport,
    select_active_style_references,
    recent_formal_reference_ids,
    active_style_mount_snapshot_payload,
    active_style_prompt_text,
    render_style_reference_selection,
)
from ..runtime.role_conversation import RoleConversationGateway
from ..application.style.owner_directive import read_owner_style_directive
from ..infrastructure.project_scene_transactions import known_scene_refs
from .scene_conversation_invocation import invoke_actor_turn, invoke_initialized_role_turn, invoke_role
from .pi_scene_payload import _answer_payload, creative_result_from_payload, review_result_from_payload
from .pi_scene_author_prompt import render_scene_create_prompt, render_scene_revision_prompt
from .pi_scene_style_history import projection_digest as _projection_digest, recent_lean_reference_ids, scene_reference_context
from .scene_performance import (
    fulfill_scene_material_requests, scene_creative_cache_digest,
    scene_expression_snapshot,
)
from .scene_performance_ownership import has_actor_entries
from .scene_creator_memory import SceneCreatorMemoryV1
from .scene_creator_material_policy import repair_material_choice
from .scene_material_library import SceneMaterialLibrary
from ..runtime.prompt_recipes import lean_scene_prompt_recipe
from .scene_source_evidence import scene_source_evidence
from .pi_scene_review_prompt import render_scene_review_prompt

@dataclass(frozen=True)
class PiSceneRuntimeMetrics:
    provider_calls: int
    cache_hits: int

class PiSceneTransactionRuntime:
    """Use the embedded Pi conversation transport behind K2 runtime ports."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        project_root: Path,
        data_root: Path,
        gateway: RoleConversationGateway | None = None,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        timeout: int = 900,
        prompt_snapshot_provider: Callable[[tuple[str, ...], Path], dict[str, Any]] | None = None,
    ):
        self._config = config
        self._project_root = project_root.resolve()
        self._data_root = data_root.resolve()
        self._gateway = gateway or RoleConversationGateway(
            config,
            data_root=self._data_root / "pi-conversations",
        )
        self._event_sink = event_sink
        self._timeout = max(30, min(900, int(timeout)))
        self._prompt_snapshot_provider = prompt_snapshot_provider
        self._provider_calls = 0
        self._cache_hits = 0

    @property
    def metrics(self) -> PiSceneRuntimeMetrics:
        return PiSceneRuntimeMetrics(self._provider_calls, self._cache_hits)

    def create_scene(self, transaction_id: str, brief: SceneBrief) -> CreativeResult:
        prompt_layers = self._prompt_snapshot(transaction_id)
        selection = self._style_projection(brief, transaction_id)
        expression = self._expression_projection(brief, transaction_id)
        projection_digest = self._creative_projection_digest(selection, expression, prompt_layers["digest"])
        initial_sources = self._source_evidence(brief, purpose="create")
        style_reference = self._style_reference(selection)
        author_style = self._author_style_reference(style_reference)
        creative_digest = scene_creative_cache_digest(projection_digest, brief.to_dict(), initial_sources, self._config)
        cache = self._cache_path(transaction_id, f"creative_result_{creative_digest}.json")
        materials_cache = self._cache_path(transaction_id, f"performance_materials_{creative_digest}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return creative_result_from_payload(cached)
        if self._event_sink is not None:
            self._event_sink("style.projection.selected", {
                "scene_transaction_id": transaction_id,
                "scene_id": brief.scene_id,
                "style_version_id": selection.get("style_mount_snapshot", {}).get("version_id", ""),
                "selection_status": selection.get("status", ""),
                "selector_version": selection.get("selector_version", ""),
                "selection_digest": selection.get("digest", ""),
                "reference_ids": [item["unit_id"] for item in selection.get("references", [])],
                "technique_axes": [axis for item in selection.get("references", []) for axis in item["technique_axes"]],
                "expression_plan_digest": hashlib.sha256(json.dumps(expression.get("expression_plan"), ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                "voice_digest": hashlib.sha256(json.dumps(expression.get("dialogue_intents"), ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                "message": "本场文风参考与表达策略已确定。",
            })
        saved_materials = _read_json(materials_cache)
        materials = str(saved_materials.get("materials") or "") if saved_materials else ""
        if saved_materials is None:
            _atomic_json(materials_cache, {"materials": ""})
        else:
            self._cache_hits += 1
        memory = self._creator_memory(transaction_id, brief)
        if materials:
            memory.record_materials(materials)
        expression_context = _expression_context_for_prompt(expression, actor_owned=has_actor_entries(materials))
        result, materials = self._ask_creator_with_materials(
            transaction_id, brief, expression, initial_sources, style_reference, materials_cache, materials,
            lambda current, intent, context: render_scene_create_prompt(
                brief, source_evidence=self._source_evidence(
                    brief, purpose="create", reserve_chars=len(current) + len(author_style) + len(context)),
                allowed_refs=known_scene_refs(brief), style_reference_block=author_style,
                expression_context_block=expression_context,
                performance_material_block=current,
                allow_material_requests=_scene_performance_enabled(self._config),
                creative_intent_block=intent, creator_memory_block=context,
                literary_guidance="\n\n".join(prompt_layers["texts"][key] for key in
                    ("scene.creator.identity", "scene.creator.create")),
            ),
        )
        _atomic_json(cache, result.to_dict())
        return result

    def review_scene(
        self,
        transaction_id: str,
        brief: SceneBrief,
        result: CreativeResult,
        verification: VerificationReport,
    ) -> ReviewResult:
        prompt_layers = self._prompt_snapshot(transaction_id)
        selection = self._style_projection(brief, transaction_id)
        expression = self._expression_projection(brief, transaction_id)
        projection_digest = self._creative_projection_digest(selection, expression, prompt_layers["digest"])
        candidate_digest = hashlib.sha256(result.prose.encode("utf-8")).hexdigest()[:16]
        initial_sources = self._source_evidence(brief, purpose="create")
        creative_digest = scene_creative_cache_digest(projection_digest, brief.to_dict(), initial_sources, self._config)
        _, material_record = _original_performance_materials(
            self._cache_path(transaction_id, f"performance_materials_{creative_digest}.json"))
        if _scene_performance_enabled(self._config) and material_record is None:
            raise RuntimeError("scene review requires the original first-level performance materials")
        materials = str(material_record.get("materials") or "") if material_record else ""
        materials_digest = hashlib.sha256(materials.encode("utf-8")).hexdigest()[:10]
        memory = self._creator_memory(transaction_id, brief)
        cache = self._cache_path(transaction_id, f"review_result_v4_{candidate_digest}_{projection_digest}_{materials_digest}_{memory.digest()}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return review_result_from_payload(cached)
        revision_attempts = len(tuple(cache.parent.glob(f"revision_result_*_{projection_digest}_*.json")))
        expression_context = _expression_context_for_prompt(expression, review=True, actor_owned=has_actor_entries(materials))
        material_index = self._material_prompt(transaction_id, materials)
        empty_sources = "无额外资料。"
        base_prompt = render_scene_review_prompt(
            brief, result, verification, source_evidence=empty_sources,
            revision_attempts=revision_attempts, expression_context_block=expression_context,
            performance_material_block=material_index,
            creative_intent_block=memory.render_context(),
            literary_guidance=prompt_layers["texts"]["scene.review"],
        )
        source_budget = max(0, lean_scene_prompt_recipe("review").soft_character_limit
                            - len(base_prompt) + len(empty_sources) - 256)
        prompt = render_scene_review_prompt(
            brief, result, verification,
            source_evidence=self._source_evidence(brief, purpose="review", max_chars=source_budget),
            revision_attempts=revision_attempts, expression_context_block=expression_context,
            performance_material_block=material_index,
            creative_intent_block=memory.render_context(),
            literary_guidance=prompt_layers["texts"]["scene.review"],
        )
        answer = self._run(prompt, role="reviewer", transaction_id=transaction_id)
        review = review_result_from_payload(_answer_payload(answer))
        _atomic_json(
            cache,
            {
                "decision": review.decision.value,
                "summary": review.summary,
                "revision_instructions": list(review.revision_instructions),
                "evidence": list(review.evidence),
            },
        )
        return review

    def revise_scene(
        self,
        transaction_id: str,
        brief: SceneBrief,
        result: CreativeResult,
        verification: VerificationReport,
        review: ReviewResult | None,
        *,
        attempt: int,
    ) -> CreativeResult:
        prompt_layers = self._prompt_snapshot(transaction_id)
        selection = self._style_projection(brief, transaction_id)
        expression = self._expression_projection(brief, transaction_id)
        projection_digest = self._creative_projection_digest(selection, expression, prompt_layers["digest"])
        initial_sources = self._source_evidence(brief, purpose="create")
        creative_digest = scene_creative_cache_digest(projection_digest, brief.to_dict(), initial_sources, self._config)
        materials_cache, material_record = _original_performance_materials(
            self._cache_path(transaction_id, f"performance_materials_{creative_digest}.json"))
        if _scene_performance_enabled(self._config) and material_record is None:
            raise RuntimeError("scene revision requires the original first-level performance materials")
        materials = str(material_record.get("materials") or "") if material_record else ""
        memory = self._creator_memory(transaction_id, brief)
        ownership_tag = "_director_v1" if materials else "_prompt_v5"
        cache = self._cache_path(transaction_id, f"revision_result_{attempt}{ownership_tag}_{projection_digest}_{memory.digest()}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return creative_result_from_payload(cached)
        style_reference = self._style_reference(selection)
        author_style = self._author_style_reference(style_reference)
        expression_context = _expression_context_for_prompt(expression, actor_owned=has_actor_entries(materials))
        revised, materials = self._ask_creator_with_materials(
            transaction_id, brief, expression, initial_sources, style_reference, materials_cache, materials,
            lambda current, intent, context: render_scene_revision_prompt(
                brief, result, verification, review,
                source_evidence=self._source_evidence(
                    brief, purpose="revise", reserve_chars=len(current) + len(author_style) + len(context)),
                allowed_refs=known_scene_refs(brief), style_reference_block=author_style,
                expression_context_block=expression_context,
                performance_material_block=current,
                allow_material_requests=_scene_performance_enabled(self._config),
                creative_intent_block=intent, creator_memory_block=context,
                literary_guidance="\n\n".join(prompt_layers["texts"][key] for key in
                    ("scene.creator.identity", "scene.creator.revise")),
            ),
        )
        _atomic_json(cache, revised.to_dict())
        return revised

    def _ask_creator_with_materials(
        self, transaction_id: str, brief: SceneBrief, expression: dict[str, Any], sources: str,
        style_reference: str, materials_cache: Path, materials: str,
        render_prompt: Callable[[str, str, str], str],
    ) -> tuple[CreativeResult, str]:
        memory_path = self._cache_path(transaction_id, "scene_creator_memory.json")
        memory = SceneCreatorMemoryV1.load(memory_path, brief.scene_id)
        for _ in range(16):
            if memory.pending_request is None:
                intent = json.dumps(memory.intent.to_dict(), ensure_ascii=False) if memory.intent else ""
                prompt = render_prompt(self._material_prompt(transaction_id, materials),
                                       intent, memory.render_context())
                payload = _answer_payload(self._run(prompt, role="worker", transaction_id=transaction_id))
                if _scene_performance_enabled(self._config):
                    payload, prompt = repair_material_choice(
                        payload, prompt, phase=memory.phase, candidate_ids=memory.candidate_ids,
                        prior_decisions=memory.material_decisions,
                        invoke=lambda current: _answer_payload(self._run(
                            current, role="worker", transaction_id=transaction_id)),
                    )
                memory.record_creator(payload, brief, prompt=prompt)
                memory.save(memory_path)
                if memory.pending_request is None:
                    return creative_result_from_payload(payload), materials
            assert memory.pending_request is not None
            updated = fulfill_scene_material_requests(
                brief=brief.to_dict(), expression=expression, sources=sources,
                style_reference=style_reference, payload=memory.pending_request, cache_root=materials_cache.parent,
                config=self._config, project_root=self._project_root,
                invoke=lambda prompt, role: self._run(prompt, role=role, transaction_id=transaction_id),
                invoke_actor_turn=lambda initialization, initialization_answer, history, prompt: self._run_actor_turn(
                    initialization, initialization_answer, history, prompt, transaction_id=transaction_id),
                invoke_role_turn=lambda role, initialization, history, prompt: self._run_initialized_role_turn(
                    role, initialization, history, prompt, transaction_id=transaction_id),
                creative_intent=json.dumps(memory.intent.to_dict(), ensure_ascii=False) if memory.intent else "",
                prompt_layers=self._prompt_snapshot(transaction_id)["texts"],
                request_batch_id=memory.prompt_digest,
                emit=(lambda event, data: self._event_sink(event, {**data, "scene_transaction_id": transaction_id}))
                if self._event_sink is not None else None,
            )
            materials = updated
            self._material_prompt(transaction_id, materials)
            _atomic_json(materials_cache, {"materials": materials})
            memory.record_materials(materials)
            memory.save(memory_path)
        raise RuntimeError("scene creator continued requesting materials without completing prose")

    def _run(self, prompt: str, *, role: str, transaction_id: str) -> str:
        self._provider_calls += 2 if role == "environment-writer" else 1
        if role == "worker" and prompt.startswith(("# Scene Create", "# Scene Revision")):
            prompt = json.dumps({
                "schema": "arcvellum/scene-creator/v1",
                "system_prompt": self._prompt_snapshot(transaction_id)["texts"]["scene.creator.identity"],
                "material_root": str(self._cache_path(transaction_id, "materials")),
                "prompt": prompt,
            }, ensure_ascii=False)
        return invoke_role(self._gateway, self._project_root, self._timeout, self._event_sink,
                           transaction_id, prompt, role)

    def _material_prompt(self, transaction_id: str, materials: str) -> str:
        library = SceneMaterialLibrary(self._cache_path(transaction_id, "materials"))
        if not materials:
            library.write("")
            return ""
        index = library.write(materials)
        guidance = self._prompt_snapshot(transaction_id)["texts"]["scene.material.selection"]
        return guidance + "\n" + index

    def _run_actor_turn(
        self, initialization: str, initialization_answer: str,
        history: tuple[tuple[str, str], ...], prompt: str, *, transaction_id: str,
    ) -> tuple[str, str]:
        self._provider_calls += 1 if history else 2
        return invoke_actor_turn(self._gateway, self._project_root, self._timeout, self._event_sink,
                                 transaction_id, initialization, initialization_answer, history, prompt)

    def _run_initialized_role_turn(
        self, role: str, initialization: str, history: tuple[tuple[str, str], ...],
        prompt: str, *, transaction_id: str,
    ) -> tuple[str, str]:
        self._provider_calls += 1
        return invoke_initialized_role_turn(
            self._gateway, self._project_root, self._timeout, self._event_sink,
            transaction_id, role, initialization, history, prompt,
        )

    def _cache_path(self, transaction_id: str, name: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", transaction_id).strip("._")
        if not safe_id:
            raise ValueError("transaction_id cannot be normalized for runtime storage")
        return self._data_root / "scene-transactions" / safe_id / name

    def _prompt_snapshot(self, transaction_id: str) -> dict[str, Any]:
        path = self._cache_path(transaction_id, "prompt_assembly_v1.json")
        scene_specs = tuple(spec for spec in list_prompt_layer_specs()
                            if spec.layer_id.startswith("scene."))
        ids = tuple(spec.layer_id for spec in scene_specs)
        saved = _validated_prompt_assembly(path)
        if saved is not None and set(ids).issubset(saved["texts"]):
            return saved
        if self._prompt_snapshot_provider is not None:
            snapshot = self._prompt_snapshot_provider(ids, self._project_root)
        else:
            layers = [resolve_prompt_layer(spec) for spec in scene_specs]
            snapshot = {**prompt_assembly_manifest(layers),
                        "texts": {layer.layer_id: layer.text for layer in layers}}
        if saved is not None:
            snapshot = _migrate_prompt_assembly(saved, snapshot)
        _atomic_json(path, snapshot)
        return snapshot

    def _creator_memory(self, transaction_id: str, brief: SceneBrief) -> SceneCreatorMemoryV1:
        return SceneCreatorMemoryV1.load(self._cache_path(transaction_id, "scene_creator_memory.json"), brief.scene_id)

    def _style_projection(self, brief: SceneBrief, transaction_id: str = "") -> dict[str, Any]:
        scene_text = scene_reference_context(self._project_root, brief.scene_id, brief.to_dict())
        brief_digest = hashlib.sha256(scene_text.encode("utf-8")).hexdigest()
        mount = active_style_mount_snapshot_payload(self._project_root)
        if transaction_id:
            cache = self._cache_path(transaction_id, "style_selection.json")
            saved = _read_json(cache)
            if saved and saved.get("brief_digest") == brief_digest and saved.get("style_mount_snapshot") == mount:
                return saved["selection"]
        recent = (*recent_formal_reference_ids(self._project_root, exclude_scene_id=brief.scene_id),
                  *recent_lean_reference_ids(self._data_root, brief.scene_id, mount))
        selection = select_active_style_references(self._project_root, scene_text, recent_unit_ids=recent)
        if transaction_id:
            _atomic_json(cache, {"scene_id": brief.scene_id, "brief_digest": brief_digest,
                                 "style_mount_snapshot": mount, "selection": selection})
        return selection

    def _expression_projection(self, brief: SceneBrief, transaction_id: str) -> dict[str, Any]:
        return scene_expression_snapshot(self._cache_path(transaction_id, "expression_projection.json"),
                                         self._project_root, brief.to_dict())

    def _creative_projection_digest(self, selection: dict[str, Any], expression: dict[str, Any], prompt_digest: str = "") -> str:
        owner = read_owner_style_directive(self._project_root)
        basis = _projection_digest(selection, expression) + str(owner["revision"]) + prompt_digest
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]

    def _style_reference(self, selection: dict[str, Any]) -> str:
        owner = read_owner_style_directive(self._project_root)
        prefix = (
            "## 作者自写文风指令（表达层，沿用项目事实与正式审查）\n" + str(owner["content"]) + "\n\n"
            if owner["active"] else ""
        )
        return prefix + render_style_reference_selection(selection)

    def _author_style_reference(self, selected_reference: str) -> str:
        mounted = active_style_prompt_text(self._project_root)
        if not mounted:
            return selected_reference
        return (
            "### 项目已挂载文风（约束 prose 表达；交付格式由本场 Output 决定）\n"
            + mounted + "\n\n" + selected_reference
        )

    def _source_evidence(self, brief: SceneBrief, *, purpose: str, reserve_chars: int = 0,
                         max_chars: int | None = None) -> str:
        indexed_style = self._style_projection(brief).get("status") in {"selected", "no-scene-match"}
        return scene_source_evidence(
            self._project_root, brief, purpose=purpose,
            indexed_style=indexed_style, reserve_chars=reserve_chars, max_chars=max_chars,
        )


def _expression_context_for_prompt(
    expression: dict[str, Any], *, review: bool = False, actor_owned: bool = False,
) -> str:
    """Pass voice decisions without repeating complete character dossiers in every model call."""

    voices = []
    for item in expression.get("dialogue_intents") or []:
        if not isinstance(item, dict):
            continue
        keys = (("speaker", "wants", "avoids") if actor_owned else
                ("speaker", "wants", "speech_strategy") if review else
                ("speaker", "wants", "avoids", "speech_strategy", "stable_voice"))
        voices.append({key: item[key] for key in keys if key in item})
    compact = {"expression_plan": expression.get("expression_plan") or {}, "voices": voices}
    return json.dumps(compact, ensure_ascii=False, separators=(",", ":"))


def _original_performance_materials(expected: Path) -> tuple[Path, dict[str, Any] | None]:
    """Keep a scene's original rehearsal attached when prompt inputs change mid-transaction."""

    record = _read_json(expected)
    if record is not None:
        return expected, record
    alternatives = [path for path in expected.parent.glob("performance_materials_*.json")
                    if (expected.parent / path.name.replace("performance_materials_", "creative_result_", 1)).is_file()]
    if len(alternatives) == 1:
        return alternatives[0], _read_json(alternatives[0])
    return expected, None


def _scene_performance_enabled(config: dict[str, Any]) -> bool:
    application = config.get("application")
    settings = application.get("scene_performance_agents") if isinstance(application, dict) else None
    return isinstance(settings, dict) and settings.get("enabled") is True


def _validated_prompt_assembly(path: Path) -> dict[str, Any] | None:
    saved = _read_json(path)
    if saved is not None and (
        saved.get("schema") != "arcvellum/prompt-assembly/v1"
        or not isinstance(saved.get("texts"), dict)
    ):
        raise ValueError("scene prompt assembly cache is invalid")
    return saved


def _migrate_prompt_assembly(saved: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    old_layers = {entry["layer_id"]: entry for entry in saved.get("layers", [])
                  if isinstance(entry, dict) and isinstance(entry.get("layer_id"), str)}
    for entry in current["layers"]:
        old = old_layers.get(entry["layer_id"])
        if old and old.get("source") in {"global", "project"}:
            entry.update(old)
            current["texts"][entry["layer_id"]] = saved["texts"][entry["layer_id"]]
    current["digest"] = hashlib.sha256(
        json.dumps(current["layers"], sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    current["migration"] = "scene-layers-expanded-v2"
    return current


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid Pi scene cache: {path.name}")
    return value


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


__all__ = [
    "PiSceneRuntimeMetrics",
    "PiSceneTransactionRuntime",
    "creative_result_from_payload",
    "render_scene_create_prompt",
    "render_scene_revision_prompt",
    "render_scene_review_prompt",
    "review_result_from_payload",
]
