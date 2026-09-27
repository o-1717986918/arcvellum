"""Execute isolated actor and environment material calls for a lean scene."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import (
    parse_environment_material,
    parse_performance_plan,
    parse_scene_material_requests,
    render_environment_prompt,
    render_interaction_materials,
    render_performance_plan_prompt,
    project_brief_expression_context,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec, scene_prompt_fallback

from .pi_scene_payload import _answer_payload
from .scene_interaction import (
    continue_scene_actor, load_scene_session, new_scene_session,
    save_scene_session,
)
from .scene_describers import continue_scene_describer


def fulfill_scene_material_requests(
    *, brief: dict[str, Any], expression: dict[str, Any], sources: str, style_reference: str,
    payload: dict[str, Any], cache_root: Path, config: dict[str, Any],
    invoke: Callable[[str, str], str],
    invoke_actor_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]] | None,
    invoke_role_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]] | None = None,
    emit: Callable[[str, dict[str, Any]], None] | None = None,
    project_root: Path | None = None,
    creative_intent: str = "",
    prompt_layers: dict[str, str] | None = None,
    request_batch_id: str = "",
) -> str:
    """Return refreshed first-level candidates after the main creator asks for them."""

    if not _policy(config)["enabled"]:
        raise RuntimeError("scene performance agents are disabled")
    cache_root.mkdir(parents=True, exist_ok=True)
    digest = _digest(brief, expression, sources, style_reference, config)
    layers = prompt_layers or {}
    plan = _plan_for_requests(brief, expression, sources, payload, cache_root, digest,
                              invoke, creative_intent, layers)
    if layers.get("scene.environment.identity") and "environment_initialization" in plan:
        plan = {**plan, "environment_initialization": plan["environment_initialization"] + "\n\n" + layers["scene.environment.identity"]}
    state = load_scene_session(cache_root, digest, brief["scene_id"])
    requests = parse_scene_material_requests(
        payload, brief, plan, actor_entries=state.get("actor_entries") if state else None,
    )
    state = _session_for_requests(state, brief, expression, plan, layers)
    for index, request in enumerate(requests):
        request_id = _request_id(request_batch_id, index)
        if request_id and request_id in state.get("fulfilled_requests", []):
            continue
        if request["kind"] in {"character-description", "object-description", "scene-description"}:
            if invoke_role_turn is None:
                raise RuntimeError("initialized describer continuation is unavailable")
            candidates = continue_scene_describer(
                brief=brief, request=request, state=state, style_reference=style_reference,
                sources=sources, cache_root=cache_root, digest=digest,
                invoke_role_turn=invoke_role_turn, cached_payload=_cached_payload, prompt_layers=layers,
                request_id=request_id,
            )
            save_scene_session(cache_root, digest, state)
            _notify(emit, "scene.performance.request.description", {
                "kind": request["kind"], "candidates": len(candidates),
            })
            continue
        if request["kind"] == "actor":
            _continue_or_limit_actor_request(
                brief, plan, request, state, cache_root, digest, config,
                invoke_actor_turn, emit, project_root, request_id,
            )
            continue
        _continue_environment_request(brief, plan, request, state, cache_root, digest,
                                      style_reference, sources, invoke, invoke_role_turn,
                                      layers, request_id, emit)
    return render_interaction_materials(plan, state["directions"], state["actor_entries"],
                                        state["environment"], viewpoint=str(brief.get("viewpoint") or ""),
                                        description_candidates=state.get("description_candidates") or [],
                                        material_notices=state.get("material_notices") or [],
                                        literary_guidance=layers.get("scene.material.selection", ""))


def _continue_or_limit_actor_request(
    brief: dict[str, Any], plan: dict[str, Any], request: dict[str, str], state: dict[str, Any],
    cache_root: Path, digest: str, config: dict[str, Any],
    invoke_actor_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]] | None,
    emit: Callable[[str, dict[str, Any]], None] | None, project_root: Path | None, request_id: str,
) -> None:
    if len(state["directions"]) >= _policy(config)["max_actor_calls"]:
        state.setdefault("material_notices", []).append({
            "request_id": request_id, "kind": "actor",
            "reason": scene_prompt_fallback("actor.limit"),
        })
        if request_id:
            state.setdefault("fulfilled_requests", []).append(request_id)
        save_scene_session(cache_root, digest, state)
        _notify(emit, "scene.performance.request.limit", {"kind": "actor"})
        return
    if invoke_actor_turn is None:
        raise RuntimeError("actor continuation is unavailable")
    continue_scene_actor(brief, plan, request, state, cache_root, digest, invoke_actor_turn, _cached_payload,
                         emit, project_root, request_id)
    _notify(emit, "scene.performance.request.actor", {"speaker": request["speaker"], "beat_id": request["beat_id"]})


def _continue_environment_request(
    brief: dict[str, Any], plan: dict[str, Any], request: dict[str, str], state: dict[str, Any],
    cache_root: Path, digest: str, style_reference: str, sources: str,
    invoke: Callable[[str, str], str],
    invoke_role_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]] | None,
    layers: dict[str, str], request_id: str,
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> None:
    beat = next(item for item in plan["beats"] if item["beat_id"] == request["beat_id"])
    task = render_environment_prompt(brief, [beat], style_reference, sources, plan["unknown_slots"],
                                     public_log=state["public_log"], creator_cue=request["cue"],
                                     literary_guidance=layers.get("scene.environment.turn", ""))
    initialization = plan["environment_initialization"]
    history = tuple((str(row[0]), str(row[1])) for row in state.get("environment_history", [])[-12:])
    key = hashlib.sha256(json.dumps([initialization, history, task], ensure_ascii=False).encode()).hexdigest()[:12]
    path = cache_root / f"performance-request-environment-{digest}-{key}.json"
    if invoke_role_turn is not None:
        def produce() -> dict[str, Any]:
            answer, _ = invoke_role_turn("environment-writer", initialization, history, task)
            return {"answer": answer, "payload": _answer_payload(answer)}

        def validate(record: dict[str, Any]) -> dict[str, Any]:
            if not isinstance(record.get("answer"), str) or not isinstance(record.get("payload"), dict):
                raise ValueError("environment conversation record is incomplete")
            parse_environment_material(record["payload"], brief, [beat])
            return record

        record = _cached_payload(path, produce, validate)
        material = parse_environment_material(record["payload"], brief, [beat])
        state["environment_history"] = [*state.get("environment_history", []), [task, record["answer"]]][-12:]
    else:
        prompt = _environment_conversation_prompt(initialization, task)
        material = _cached_payload(path, lambda: _answer_payload(invoke(prompt, "environment-writer")),
                                   lambda payload: parse_environment_material(payload, brief, [beat]))
    existing = state["environment"] or {"scene_id": brief["scene_id"], "passages": []}
    next_index = len(existing["passages"])
    passages = [{**passage, "candidate_id": f"environment:{next_index + number}"}
                for number, passage in enumerate(material["passages"], 1)]
    state["environment"] = {**existing, "passages": [*existing["passages"], *passages]}
    if request_id:
        state.setdefault("fulfilled_requests", []).append(request_id)
    save_scene_session(cache_root, digest, state)
    _notify(emit, "scene.performance.request.environment", {"beat_id": request["beat_id"],
                                                               "passages": len(material["passages"])})


def _plan_for_requests(
    brief: dict[str, Any], expression: dict[str, Any], sources: str, payload: dict[str, Any],
    cache_root: Path, digest: str, invoke: Callable[[str, str], str],
    creative_intent: str, layers: dict[str, str],
) -> dict[str, Any]:
    path = cache_root / f"performance-plan-{digest}.json"
    requests = payload.get("material_requests")
    description_kinds = {"character-description", "object-description", "scene-description"}
    if not path.is_file() and isinstance(requests, list) and requests and all(
        isinstance(item, dict) and item.get("kind") in description_kinds for item in requests
    ):
        return {"scene_id": brief["scene_id"], "beats": [{"beat_id": "b1", "event": brief.get("objective") or "本场观察"}],
                "actor_prompts": {}, "unknown_slots": []}
    return _cached_payload(path, lambda: _generate_performance_plan(
        brief, expression, sources, invoke, creative_intent, layers.get("scene.performance.plan", "")),
                           lambda item: parse_performance_plan(item, brief))


def _session_for_requests(
    state: dict[str, Any] | None, brief: dict[str, Any], expression: dict[str, Any],
    plan: dict[str, Any], layers: dict[str, str],
) -> dict[str, Any]:
    actors = plan.get("actor_prompts") or {}
    if state is None:
        if actors:
            return new_scene_session(brief, expression, plan, None, prompt_layers=layers)
        return {"scene_id": brief["scene_id"], "initializations": {}, "initialization_answers": {},
                "histories": {}, "public_log": [], "actor_entries": [], "directions": [],
                "environment": None, "prompt_layers": {"scene.actor.turn": layers.get("scene.actor.turn", "")}}
    if actors:
        initialized = new_scene_session(brief, expression, plan, None, prompt_layers=layers)
        for key in ("initializations", "initialization_answers", "histories"):
            for speaker, value in initialized[key].items():
                state.setdefault(key, {}).setdefault(speaker, value)
    return state


def _request_id(batch_id: str, index: int) -> str:
    return f"{batch_id}:{index}" if batch_id else ""


def _environment_conversation_prompt(initialization: str, prompt: str) -> str:
    return json.dumps({"schema": "arcvellum/environment-conversation/v1",
                       "initialization": initialization, "prompt": prompt}, ensure_ascii=False)


def _generate_performance_plan(
    brief: dict[str, Any], expression: dict[str, Any], sources: str,
    invoke: Callable[[str, str], str], creative_intent: str = "", literary_guidance: str = "",
) -> dict[str, Any]:
    prompt = render_performance_plan_prompt(brief, expression, sources, creative_intent, literary_guidance)
    for attempt in range(2):
        try:
            return parse_performance_plan(_answer_payload(invoke(prompt, "worker")), brief)
        except ValueError:
            if attempt:
                raise
            prompt += "\n\n" + prompt_layer_spec("scene.performance.plan-repair.protocol").default_text
    raise AssertionError("unreachable performance plan retry")


def scene_creative_cache_digest(
    projection_digest: str, brief: dict[str, Any], sources: str, config: dict[str, Any],
) -> str:
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    runners = config.get("agent_runners") if isinstance(config.get("agent_runners"), dict) else {}
    raw_settings = application.get("scene_performance_agents")
    settings = raw_settings if isinstance(raw_settings, dict) else {}
    enabled = settings.get("enabled") is True
    version = "performance-v41-intent-selective" if enabled else "performance-v12-intent"
    payload = [version, projection_digest, brief, sources, settings, runners.get("pi-worker", {})]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:20]


def scene_expression_snapshot(cache: Path, project_root: Path, brief: dict[str, Any]) -> dict[str, Any]:
    """Hold voice/persona inputs constant throughout one scene transaction."""

    cache.parent.mkdir(parents=True, exist_ok=True)
    return _cached_payload(cache, lambda: project_brief_expression_context(project_root, brief), lambda payload: payload)


def _policy(config: dict[str, Any]) -> dict[str, Any]:
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    value = application.get("scene_performance_agents")
    settings = value if isinstance(value, dict) else {}
    raw_limit = settings.get("max_actor_calls", 12)
    try:
        limit = int(raw_limit)
    except (ValueError, TypeError):
        limit = 12
    return {"enabled": settings.get("enabled") is True, "max_actor_calls": max(0, min(12, limit))}


def _digest(brief: dict[str, Any], expression: dict[str, Any], sources: str, style: str, config: dict[str, Any]) -> str:
    pi = config.get("agent_runners", {}).get("pi-worker", {}) if isinstance(config.get("agent_runners"), dict) else {}
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    performance = application.get("scene_performance_agents") if isinstance(application.get("scene_performance_agents"), dict) else {}
    version = "performance-v41"
    payload = [version, brief, expression, sources, style, pi.get("models"), pi.get("model"), pi.get("thinking")]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:20]


def _cached_payload(
    path: Path,
    produce: Callable[[], dict[str, Any]],
    validate: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return validate(payload)
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    payload = produce()
    if not isinstance(payload, dict):
        raise ValueError("performance reply must be a JSON object")
    normalized = validate(payload)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return normalized


def _notify(emit: Callable[[str, dict[str, Any]], None] | None, event: str, data: dict[str, Any]) -> None:
    if emit is not None:
        emit(event, data)


__all__ = ["fulfill_scene_material_requests", "scene_creative_cache_digest", "scene_expression_snapshot"]
