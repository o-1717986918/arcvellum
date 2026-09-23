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
    parse_relay_plan,
    parse_relay_scene_check,
    render_actor_scene_prompt,
    render_environment_prompt,
    render_performance_materials,
    render_performance_plan_prompt,
    render_relay_materials,
    render_relay_plan_prompt,
    render_relay_scene_check_prompt,
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
        return _capacity_fallback(policy, participants, emit)
    cache_root.mkdir(parents=True, exist_ok=True)
    digest = _digest(brief, expression, sources, style_reference, config)
    if policy["mode"] == "relay":
        try:
            return _relay_materials(brief, expression, sources, style_reference, participants, cache_root, digest, invoke, emit)
        except (ValueError, RuntimeError, TimeoutError) as exc:
            _notify(emit, "scene.performance.relay.failed", {"reason": str(exc)[:300]})
            raise RuntimeError("scene performance relay could not provide complete first-level character material") from exc
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
    environment_beats = plan["beats"]
    try:
        environment = _cached_payload(env_path, lambda: _answer_payload(invoke(
                render_environment_prompt(brief, environment_beats, style_reference, sources, plan["unknown_slots"]), "environment-writer",
            )), lambda payload: parse_environment_material(payload, brief, environment_beats))
        _notify(emit, "scene.performance.environment", {"passages": len(environment["passages"])})
    except (ValueError, RuntimeError, TimeoutError) as exc:
        _notify(emit, "scene.performance.skipped", {"stage": "environment", "reason": str(exc)[:300]})

    if environment is not None and not environment["passages"]:
        environment = None
    if not actors and not environment:
        return ""
    try:
        return render_performance_materials(plan, actors, environment, viewpoint=str(brief.get("viewpoint") or ""))
    except ValueError as exc:
        _notify(emit, "scene.performance.fallback", {"stage": "material-budget", "reason": str(exc)})
        return ""


def _actor_materials(
    brief: dict[str, Any], expression: dict[str, Any], plan: dict[str, Any], participants: list[str],
    cache_root: Path, digest: str, invoke: Callable[[str, str], str],
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> list[dict[str, Any]]:
    intents = expression.get("dialogue_intents") if isinstance(expression.get("dialogue_intents"), list) else []
    beats = plan["beats"]
    beat_digest = hashlib.sha256(json.dumps(beats, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]
    actors = []
    for speaker in participants:
        voice = next((item for item in intents if _matches_voice(item, speaker)), {})
        speaker_digest = hashlib.sha256(speaker.encode()).hexdigest()[:10]
        actor_path = cache_root / f"performance-actor-{digest}-{speaker_digest}-{beat_digest}.json"
        payload = _cached_payload(actor_path, lambda voice=voice, speaker=speaker: _answer_payload(invoke(
                render_actor_scene_prompt(brief, beats, {**voice, "speaker": speaker}, plan["unknown_slots"]), "character-actor",
            )), lambda payload, speaker=speaker: parse_actor_scene_material(payload, brief, beats, speaker))
        materials = parse_actor_scene_material(payload, brief, beats, speaker)
        actors.append(materials)
        _notify(emit, "scene.performance.actor", {"speaker": speaker, "entries": len(materials["entries"])})
    return actors


def _capacity_fallback(
    policy: dict[str, Any], participants: list[str],
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> str:
    _notify(emit, "scene.performance.fallback", {"stage": "actor-capacity", "participants": len(participants)})
    if policy["mode"] == "relay":
        raise RuntimeError("scene performance relay requires capacity for every scene participant")
    return ""


def _relay_materials(
    brief: dict[str, Any], expression: dict[str, Any], sources: str, style_reference: str,
    participants: list[str], cache_root: Path, digest: str, invoke: Callable[[str, str], str],
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> str:
    plan_path = cache_root / f"performance-relay-plan-{digest}.json"
    plan_prompt = render_relay_plan_prompt(brief)
    plan = _cached_payload(plan_path, lambda: _repaired_relay_payload(
        plan_prompt, "worker", invoke, lambda payload: parse_relay_plan(payload, brief),
        "只列出来源中逐字存在、长度合规且确实描述情节变化的完整事实分句；"
        "不要把关系状态摘要拆成额外里程碑，不要更改角色归属或补造事实。",
    ), lambda payload: parse_relay_plan(payload, brief))
    _notify(emit, "scene.performance.relay.plan", {"milestones": len(plan["milestones"])})
    voices = expression.get("dialogue_intents") if isinstance(expression.get("dialogue_intents"), list) else []
    knowledge = {item["speaker"]: item["quotes"] for item in plan["actor_knowledge"]}
    actor_entries: list[dict[str, Any]] = []
    public_log: list[dict[str, Any]] = []
    turn = 0
    for speaker in participants:
        turn += 1
        _relay_actor_turn(brief, plan, voices, knowledge, speaker, None, turn,
                          actor_entries, public_log, cache_root, digest, invoke, emit)
    check = _relay_check(plan, actor_entries, cache_root, digest, invoke, emit)
    limit = _relay_turn_limit(len(participants), len(plan["milestones"]))
    while _first_unmet(plan, check) is not None and turn < limit and len(actor_entries) < 24:
        milestone = _first_unmet(plan, check)
        speaker = milestone["speaker"]
        turn += 1
        _relay_actor_turn(brief, plan, voices, knowledge, speaker, milestone["source_quote"], turn,
                          actor_entries, public_log, cache_root, digest, invoke, emit)
        if len(participants) > 1 and turn < limit and len(actor_entries) < 24:
            counterpart = participants[(participants.index(speaker) + 1) % len(participants)]
            turn += 1
            _relay_actor_turn(brief, plan, voices, knowledge, counterpart, milestone["source_quote"], turn,
                              actor_entries, public_log, cache_root, digest, invoke, emit)
        check = _relay_check(plan, actor_entries, cache_root, digest, invoke, emit)
    if _first_unmet(plan, check) is not None:
        raise RuntimeError("locked scene outcomes remain unsupported by first-level actors")
    for speaker in participants:
        if turn >= limit or len(actor_entries) >= 24:
            break
        turn += 1
        _relay_actor_turn(brief, plan, voices, knowledge, speaker, None, turn,
                          actor_entries, public_log, cache_root, digest, invoke, emit)
    environment = _relay_environment(brief, plan, style_reference, sources, public_log, cache_root, digest, invoke, emit)
    return render_relay_materials(plan, actor_entries, environment, check,
                                  viewpoint=str(brief.get("viewpoint") or ""))


def _relay_actor_turn(
    brief: dict[str, Any], plan: dict[str, Any], voices: list[Any], knowledge: dict[str, list[str]],
    speaker: str, outcome: str | None, turn: int, actor_entries: list[dict[str, Any]],
    public_log: list[dict[str, Any]], cache_root: Path, digest: str,
    invoke: Callable[[str, str], str], emit: Callable[[str, dict[str, Any]], None] | None,
) -> None:
    beat = {"beat_id": f"b{turn}", "event": "当前互动继续；只有公共日志里的言行已经发生。"}
    voice = next((item for item in voices if _matches_voice(item, speaker)), {})
    entry_capacity = min(2, 24 - len(actor_entries))
    prompt = render_actor_scene_prompt(
        brief, [beat], {**voice, "speaker": speaker}, plan["unknown_slots"],
        public_log=public_log, pending_outcome=outcome,
        knowledge_quotes=knowledge[speaker], opening_situation=plan["opening_situation"], max_entries=entry_capacity,
    )
    prompt_digest = hashlib.sha256(prompt.encode()).hexdigest()[:12]
    path = cache_root / f"performance-relay-actor-{digest}-t{turn}-{prompt_digest}.json"
    validate = lambda payload: parse_actor_scene_material(payload, brief, [beat], speaker, max_entries=entry_capacity)
    material = _cached_payload(path, lambda: _repaired_relay_payload(
        prompt, "character-actor", invoke, validate,
        f"只返回零至 {entry_capacity} 条属于自己的条目；保留人物当下自主性，勿压缩成机械交差，也勿替对手说话。",
    ), validate)
    for number, entry in enumerate(material["entries"], 1):
        actor_entries.append({**entry, "speaker": speaker, "entry_id": f"t{turn}:{number}"})
        public_log.append({"speaker": speaker, "spoken": entry["spoken"],
                           "first_person_action": entry["first_person_action"]})
    _notify(emit, "scene.performance.relay.actor", {"speaker": speaker, "turn": turn, "entries": len(material["entries"])})


def _relay_check(
    plan: dict[str, Any], actor_entries: list[dict[str, Any]], cache_root: Path, digest: str,
    invoke: Callable[[str, str], str], emit: Callable[[str, dict[str, Any]], None] | None,
) -> dict[str, Any]:
    prompt = render_relay_scene_check_prompt(plan, actor_entries)
    prompt_digest = hashlib.sha256(prompt.encode()).hexdigest()[:12]
    path = cache_root / f"performance-relay-check-{digest}-{prompt_digest}.json"
    def produce() -> dict[str, Any]:
        payload = _answer_payload(invoke(prompt, "worker"))
        try:
            parse_relay_scene_check(payload, plan, actor_entries)
        except ValueError as exc:
            retry = (f"{prompt}\n\n上一份核对不符合格式或来源合同：{exc}。"
                     "请重新核对同一批条目；每项最多引用四个证据 ID，missing 不引用证据，"
                     "fulfilled 必须有归属角色的明确外显证据。仍不确定就标 uncertain，不要为修复格式虚报结果。")
            return _answer_payload(invoke(retry, "worker"))
        return payload
    check = _cached_payload(path, produce, lambda payload: parse_relay_scene_check(payload, plan, actor_entries))
    _notify(emit, "scene.performance.relay.check", {"statuses": [item["status"] for item in check["results"]]})
    return check


def _repaired_relay_payload(
    prompt: str, role: str, invoke: Callable[[str, str], str],
    validate: Callable[[dict[str, Any]], dict[str, Any]], guidance: str,
) -> dict[str, Any]:
    payload = _answer_payload(invoke(prompt, role))
    try:
        validate(payload)
    except ValueError as exc:
        previous = json.dumps(payload, ensure_ascii=False)[:6000]
        retry = (f"{prompt}\n\n上一份输出：{previous}\n"
                 f"这份输出不符合结构或来源合同：{exc}。请重新完成同一任务。{guidance}")
        repaired = _answer_payload(invoke(retry, role))
        validate(repaired)
        return repaired
    return payload


def _first_unmet(plan: dict[str, Any], check: dict[str, Any]) -> dict[str, str] | None:
    return next((milestone for milestone, result in zip(plan["milestones"], check["results"], strict=True)
                 if result["status"] != "fulfilled"), None)


def _relay_turn_limit(participant_count: int, milestone_count: int) -> int:
    return min(24, participant_count + 6 * milestone_count)


def _relay_environment(
    brief: dict[str, Any], plan: dict[str, Any], style_reference: str, sources: str,
    public_log: list[dict[str, Any]], cache_root: Path, digest: str,
    invoke: Callable[[str, str], str], emit: Callable[[str, dict[str, Any]], None] | None,
) -> dict[str, Any]:
    beats = [{"beat_id": "b1", "event": plan["opening_situation"]}]
    prompt = render_environment_prompt(brief, beats, style_reference, sources, plan["unknown_slots"],
                                       public_log=public_log)
    prompt_digest = hashlib.sha256(prompt.encode()).hexdigest()[:12]
    path = cache_root / f"performance-relay-environment-{digest}-{prompt_digest}.json"
    material = _cached_payload(path, lambda: _answer_payload(invoke(prompt, "environment-writer")),
                               lambda payload: parse_environment_material(payload, brief, beats))
    _notify(emit, "scene.performance.relay.environment", {"passages": len(material["passages"])})
    return material


def scene_creative_cache_digest(
    projection_digest: str, brief: dict[str, Any], sources: str, config: dict[str, Any],
) -> str:
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    runners = config.get("agent_runners") if isinstance(config.get("agent_runners"), dict) else {}
    raw_settings = application.get("scene_performance_agents")
    settings = raw_settings if isinstance(raw_settings, dict) else {}
    enabled = settings.get("enabled") is True
    version = ("performance-relay-v9" if settings.get("mode") == "relay" else "performance-v19") if enabled else "performance-v9"
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
    return {"enabled": settings.get("enabled") is True, "max_actor_calls": max(0, min(4, limit)),
            "mode": "relay" if settings.get("mode") == "relay" else "batch"}


def _digest(brief: dict[str, Any], expression: dict[str, Any], sources: str, style: str, config: dict[str, Any]) -> str:
    pi = config.get("agent_runners", {}).get("pi-worker", {}) if isinstance(config.get("agent_runners"), dict) else {}
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    performance = application.get("scene_performance_agents") if isinstance(application.get("scene_performance_agents"), dict) else {}
    version = "performance-relay-v9" if performance.get("mode") == "relay" else "performance-v19"
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
