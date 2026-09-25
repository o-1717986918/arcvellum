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

from .pi_scene_payload import _answer_payload
from .scene_interaction import (
    continue_scene_actor, load_scene_session, new_scene_session,
    perform_scene_interaction, save_scene_session,
)


def scene_performance_materials(
    *,
    brief: dict[str, Any],
    expression: dict[str, Any],
    sources: str,
    style_reference: str,
    cache_root: Path,
    config: dict[str, Any],
    invoke: Callable[[str, str], str],
    invoke_actor_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]] | None = None,
    emit: Callable[[str, dict[str, Any]], None] | None = None,
    project_root: Path | None = None,
) -> str:
    """Return non-authoritative material for the main writer, or empty on model failure."""

    policy = _policy(config)
    if not policy["enabled"]:
        return ""
    participants = list(brief.get("participants") or ())
    if len(participants) > policy["max_actor_calls"]:
        return _capacity_fallback(policy, participants, emit)
    cache_root.mkdir(parents=True, exist_ok=True)
    digest = _digest(brief, expression, sources, style_reference, config)
    plan_path = cache_root / f"performance-plan-{digest}.json"
    try:
        plan = _cached_payload(plan_path, lambda: _generate_performance_plan(brief, expression, sources, invoke),
                               lambda payload: parse_performance_plan(payload, brief))
    except (ValueError, RuntimeError, TimeoutError) as exc:
        _notify(emit, "scene.performance.fallback", {"stage": "plan", "reason": str(exc)[:300]})
        return ""
    _notify(emit, "scene.performance.plan", {"beats": len(plan["beats"]), "digest": digest})

    environment = _environment_material(brief, plan, style_reference, sources, cache_root, digest, invoke, emit)
    interaction = _try_interaction(brief, expression, plan, participants, sources, environment,
                                   cache_root, digest, invoke, invoke_actor_turn, emit, project_root)
    return interaction


def _environment_material(
    brief: dict[str, Any], plan: dict[str, Any], style_reference: str, sources: str,
    cache_root: Path, digest: str, invoke: Callable[[str, str], str],
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> dict[str, Any] | None:
    env_path = cache_root / f"performance-environment-{digest}.json"
    beats = plan["beats"]
    prompt = _environment_conversation_prompt(plan["environment_initialization"],
                                              render_environment_prompt(brief, beats, style_reference, sources, plan["unknown_slots"]))
    try:
        environment = _cached_payload(env_path, lambda: _answer_payload(invoke(
            prompt, "environment-writer",
        )), lambda payload: parse_environment_material(payload, brief, beats))
        _notify(emit, "scene.performance.environment", {"passages": len(environment["passages"])})
        return environment if environment["passages"] else None
    except (ValueError, RuntimeError, TimeoutError) as exc:
        _notify(emit, "scene.performance.skipped", {"stage": "environment", "reason": str(exc)[:300]})
        return None


def _try_interaction(
    brief: dict[str, Any], expression: dict[str, Any], plan: dict[str, Any], participants: list[str],
    sources: str, environment: dict[str, Any] | None,
    cache_root: Path, digest: str, invoke: Callable[[str, str], str],
    invoke_actor_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]] | None,
    emit: Callable[[str, dict[str, Any]], None] | None,
    project_root: Path | None = None,
) -> str:
    if not participants or invoke_actor_turn is None:
        if environment:
            return render_interaction_materials(plan, [], [], environment,
                                                viewpoint=str(brief.get("viewpoint") or ""))
        _notify(emit, "scene.performance.fallback", {"stage": "interaction", "reason": "actor turn continuation unavailable"})
        return ""
    try:
        result = perform_scene_interaction(brief, expression, plan, sources, environment, cache_root, digest,
                                           invoke, invoke_actor_turn, _cached_payload, emit, project_root)
        if not result:
            _notify(emit, "scene.performance.fallback", {"stage": "interaction", "reason": "no actor entries"})
        return result
    except (ValueError, RuntimeError, TimeoutError) as exc:
        _notify(emit, "scene.performance.fallback", {"stage": "interaction", "reason": str(exc)[:300]})
        state = load_scene_session(cache_root, digest, brief["scene_id"])
        if state and (state.get("actor_entries") or state.get("environment")):
            return render_interaction_materials(
                plan, state["directions"], state["actor_entries"], state.get("environment"),
                viewpoint=str(brief.get("viewpoint") or ""),
            )
        return (render_interaction_materials(plan, [], [], environment,
                                             viewpoint=str(brief.get("viewpoint") or ""))
                if environment else "")


def fulfill_scene_material_requests(
    *, brief: dict[str, Any], expression: dict[str, Any], sources: str, style_reference: str,
    payload: dict[str, Any], cache_root: Path, config: dict[str, Any],
    invoke: Callable[[str, str], str],
    invoke_actor_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]] | None,
    emit: Callable[[str, dict[str, Any]], None] | None = None,
    project_root: Path | None = None,
) -> str:
    """Return refreshed first-level candidates after the main creator asks for them."""

    if not _policy(config)["enabled"]:
        raise RuntimeError("scene performance agents are disabled")
    digest = _digest(brief, expression, sources, style_reference, config)
    plan_path = cache_root / f"performance-plan-{digest}.json"
    plan = _cached_payload(plan_path, lambda: _generate_performance_plan(brief, expression, sources, invoke),
                           lambda item: parse_performance_plan(item, brief))
    state = load_scene_session(cache_root, digest, brief["scene_id"])
    requests = parse_scene_material_requests(
        payload, brief, plan, actor_entries=state.get("actor_entries") if state else None,
    )
    if state is None:
        state = new_scene_session(brief, expression, plan, None)
    for request in requests:
        if request["kind"] == "actor":
            if invoke_actor_turn is None:
                raise RuntimeError("actor continuation is unavailable")
            continue_scene_actor(brief, plan, request, state, cache_root, digest, invoke_actor_turn, _cached_payload,
                                 emit, project_root)
            _notify(emit, "scene.performance.request.actor", {"speaker": request["speaker"], "beat_id": request["beat_id"]})
            continue
        beat = next(item for item in plan["beats"] if item["beat_id"] == request["beat_id"])
        task = render_environment_prompt(
            brief, [beat], style_reference, sources, plan["unknown_slots"],
            public_log=state["public_log"], creator_cue=request["cue"],
        )
        prompt = _environment_conversation_prompt(plan["environment_initialization"], task)
        key = hashlib.sha256(prompt.encode()).hexdigest()[:12]
        path = cache_root / f"performance-request-environment-{digest}-{key}.json"
        material = _cached_payload(path, lambda: _answer_payload(invoke(prompt, "environment-writer")),
                                   lambda payload: parse_environment_material(payload, brief, [beat]))
        existing = state["environment"] or {"scene_id": brief["scene_id"], "passages": []}
        state["environment"] = {**existing, "passages": [*existing["passages"], *material["passages"]]}
        save_scene_session(cache_root, digest, state)
        _notify(emit, "scene.performance.request.environment", {"beat_id": request["beat_id"],
                                                                   "passages": len(material["passages"])})
    return render_interaction_materials(plan, state["directions"], state["actor_entries"],
                                        state["environment"], viewpoint=str(brief.get("viewpoint") or ""))


def _capacity_fallback(
    policy: dict[str, Any], participants: list[str],
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> str:
    _notify(emit, "scene.performance.fallback", {"stage": "actor-capacity", "participants": len(participants)})
    return ""


def _environment_conversation_prompt(initialization: str, prompt: str) -> str:
    return json.dumps({"schema": "arcvellum/environment-conversation/v1",
                       "initialization": initialization, "prompt": prompt}, ensure_ascii=False)


def _generate_performance_plan(
    brief: dict[str, Any], expression: dict[str, Any], sources: str,
    invoke: Callable[[str, str], str],
) -> dict[str, Any]:
    prompt = render_performance_plan_prompt(brief, expression, sources)
    for attempt in range(2):
        try:
            return parse_performance_plan(_answer_payload(invoke(prompt, "worker")), brief)
        except ValueError:
            if attempt:
                raise
            prompt += "\n\n上一条未形成完整、可解析且字段齐全的 JSON。请重新输出唯一一个完整 JSON 对象。"
    raise AssertionError("unreachable performance plan retry")


def scene_creative_cache_digest(
    projection_digest: str, brief: dict[str, Any], sources: str, config: dict[str, Any],
) -> str:
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    runners = config.get("agent_runners") if isinstance(config.get("agent_runners"), dict) else {}
    raw_settings = application.get("scene_performance_agents")
    settings = raw_settings if isinstance(raw_settings, dict) else {}
    enabled = settings.get("enabled") is True
    version = "performance-v40-author-requests" if enabled else "performance-v11"
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
    version = "performance-v40"
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


__all__ = ["scene_performance_materials", "fulfill_scene_material_requests", "scene_creative_cache_digest", "scene_expression_snapshot"]
