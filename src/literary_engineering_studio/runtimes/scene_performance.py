"""Execute isolated actor and environment material calls for a lean scene."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import (
    parse_actor_scene_material,
    parse_environment_material,
    parse_performance_plan,
    render_actor_scene_prompt,
    render_environment_prompt,
    render_performance_materials,
    render_performance_plan_prompt,
)

from .pi_scene_payload import _answer_payload


def scene_performance_materials(
    *,
    brief: dict[str, Any],
    expression: dict[str, Any],
    sources: str,
    style_reference: str,
    cache_root: Path,
    config: dict[str, Any],
    invoke: Callable[[str, str], str],
    emit: Callable[[str, dict[str, Any]], None] | None = None,
) -> str:
    """Return non-authoritative material for the main writer, or empty on model failure."""

    policy = _policy(config)
    if not policy["enabled"]:
        return ""
    participants = list(brief.get("participants") or ())
    if len(participants) > policy["max_actor_calls"]:
        _notify(emit, "scene.performance.fallback", {"stage": "actor-capacity", "participants": len(participants)})
        return ""
    cache_root.mkdir(parents=True, exist_ok=True)
    digest = _digest(brief, expression, sources, style_reference, config)
    plan_path = cache_root / f"performance-plan-{digest}.json"
    try:
        plan = _cached_payload(plan_path, lambda: _answer_payload(invoke(
                render_performance_plan_prompt(brief, expression, sources), "worker",
            )), lambda payload: parse_performance_plan(payload, brief))
    except (ValueError, RuntimeError, TimeoutError) as exc:
        _notify(emit, "scene.performance.fallback", {"stage": "plan", "reason": str(exc)[:300]})
        return ""
    _notify(emit, "scene.performance.plan", {"beats": len(plan["beats"]), "digest": digest})

    try:
        actors = _actor_materials(brief, expression, plan, participants, cache_root, digest, invoke, emit)
    except (ValueError, RuntimeError, TimeoutError) as exc:
        _notify(emit, "scene.performance.fallback", {"stage": "actor", "reason": str(exc)[:300]})
        return ""

    environment: dict[str, Any] | None = None
    env_path = cache_root / f"performance-environment-{digest}.json"
    environment_task = plan["environment_task"]
    environment_beats = [beat for beat in plan["beats"] if beat["beat_id"] in environment_task["focus_beats"]]
    try:
        environment = _cached_payload(env_path, lambda: _answer_payload(invoke(
                render_environment_prompt(brief, environment_beats, style_reference, sources, environment_task), "environment-writer",
            )), lambda payload: parse_environment_material(payload, brief, environment_beats))
        _notify(emit, "scene.performance.environment", {"passages": len(environment["passages"])})
    except (ValueError, RuntimeError, TimeoutError) as exc:
        _notify(emit, "scene.performance.skipped", {"stage": "environment", "reason": str(exc)[:300]})

    if environment is not None and not environment["passages"]:
        environment = None
    if not actors and not environment:
        return ""
    try:
        return render_performance_materials(plan, actors, environment)
    except ValueError as exc:
        _notify(emit, "scene.performance.fallback", {"stage": "material-budget", "reason": str(exc)})
        return ""


def _actor_materials(
    brief: dict[str, Any], expression: dict[str, Any], plan: dict[str, Any], participants: list[str],
    cache_root: Path, digest: str, invoke: Callable[[str, str], str],
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> list[dict[str, Any]]:
    intents = expression.get("dialogue_intents") if isinstance(expression.get("dialogue_intents"), list) else []
    actor_tasks = {task["speaker"]: task for task in plan["actor_tasks"]}
    beats = plan["beats"]
    beat_digest = hashlib.sha256(json.dumps(beats, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]
    actors = []
    for speaker in participants:
        voice = next((item for item in intents if _matches_voice(item, speaker)), {})
        speaker_digest = hashlib.sha256(speaker.encode()).hexdigest()[:10]
        actor_path = cache_root / f"performance-actor-{digest}-{speaker_digest}-{beat_digest}.json"
        payload = _cached_payload(actor_path, lambda voice=voice, speaker=speaker: _answer_payload(invoke(
                render_actor_scene_prompt(brief, beats, voice, actor_tasks[speaker]), "character-actor",
            )), lambda payload, speaker=speaker: parse_actor_scene_material(payload, brief, beats, speaker))
        materials = parse_actor_scene_material(payload, brief, beats, speaker)
        actors.append(materials)
        _notify(emit, "scene.performance.actor", {"speaker": speaker, "entries": len(materials["entries"])})
    return actors


def scene_creative_cache_digest(
    projection_digest: str, brief: dict[str, Any], sources: str, config: dict[str, Any],
) -> str:
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    runners = config.get("agent_runners") if isinstance(config.get("agent_runners"), dict) else {}
    settings = application.get("scene_performance_agents", {})
    version = "performance-v13" if isinstance(settings, dict) and settings.get("enabled") is True else "performance-v9"
    payload = [version, projection_digest, brief, sources, settings, runners.get("pi-worker", {})]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:20]


def _policy(config: dict[str, Any]) -> dict[str, Any]:
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    value = application.get("scene_performance_agents")
    settings = value if isinstance(value, dict) else {}
    raw_limit = settings.get("max_actor_calls", 4)
    try:
        limit = int(raw_limit)
    except (ValueError, TypeError):
        limit = 4
    return {"enabled": settings.get("enabled") is True, "max_actor_calls": max(0, min(4, limit))}


def _digest(brief: dict[str, Any], expression: dict[str, Any], sources: str, style: str, config: dict[str, Any]) -> str:
    pi = config.get("agent_runners", {}).get("pi-worker", {}) if isinstance(config.get("agent_runners"), dict) else {}
    payload = ["performance-v12", brief, expression, sources, style, pi.get("models"), pi.get("model"), pi.get("thinking")]
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


def _matches_voice(item: Any, speaker: str) -> bool:
    if not isinstance(item, dict):
        return False
    return speaker in {str(item.get("speaker") or ""), str(item.get("character_id") or "")} or speaker.rsplit("/", 1)[-1] in {
        str(item.get("character_id") or ""), str(item.get("speaker") or ""),
    }


def _notify(emit: Callable[[str, dict[str, Any]], None] | None, event: str, data: dict[str, Any]) -> None:
    if emit is not None:
        emit(event, data)


__all__ = ["scene_performance_materials", "scene_creative_cache_digest"]
