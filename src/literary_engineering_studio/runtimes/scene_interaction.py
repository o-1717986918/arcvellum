"""Preserve bounded actor and environment conversations across creator requests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from literary_engineering_studio_engine.public.literary import (
    parse_actor_scene_material,
    render_actor_initialization_prompt,
    render_actor_interaction_prompt,
)
from literary_engineering_studio_engine.public.prompting import render_prompt_template

from .pi_scene_payload import _answer_payload


def new_scene_session(
    brief: dict[str, Any], expression: dict[str, Any], plan: dict[str, Any], environment: dict[str, Any] | None,
    *, prompt_layers: dict[str, str] | None = None,
) -> dict[str, Any]:
    participants = list(brief.get("participants") or ())
    saved_personas = expression.get("actor_personas") if isinstance(expression.get("actor_personas"), dict) else {}
    identity_guidance = (prompt_layers or {}).get("scene.actor.identity", "")
    return {
        "scene_id": brief["scene_id"],
        "initializations": {speaker: render_actor_initialization_prompt({
            "name": speaker, "roleplay_direction": saved_personas.get(speaker) or plan["actor_prompts"][speaker],
        }) + ("\n\n" + identity_guidance if identity_guidance else "") for speaker in participants},
        "initialization_answers": {speaker: "" for speaker in participants},
        "histories": {speaker: [] for speaker in participants},
        "public_log": [], "actor_entries": [], "directions": [], "environment": environment,
        "prompt_layers": {"scene.actor.turn": (prompt_layers or {}).get("scene.actor.turn", "")},
    }


def load_scene_session(cache_root: Path, digest: str, scene_id: str) -> dict[str, Any] | None:
    path = cache_root / f"performance-interaction-session-{digest}.json"
    if not path.is_file():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("scene_id") != scene_id:
        raise ValueError("scene performance session does not match the scene")
    return state


def save_scene_session(cache_root: Path, digest: str, state: dict[str, Any]) -> None:
    path = cache_root / f"performance-interaction-session-{digest}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def continue_scene_actor(
    brief: dict[str, Any], plan: dict[str, Any], request: dict[str, str], state: dict[str, Any],
    cache_root: Path, digest: str,
    invoke_actor_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]],
    cached_payload: Callable[..., dict[str, Any]],
    emit: Callable[[str, dict[str, Any]], None] | None = None,
    project_root: Path | None = None,
    request_id: str = "",
) -> None:
    speaker = request["speaker"]
    turn = len(state["directions"])
    direction = {"finish": False, "next_speaker": speaker, "beat_id": request["beat_id"],
                 "scene_change": request.get("scene_change", ""), "cue": request["cue"],
                 "director_note": request.get("purpose") or "主创按需续演"}
    prompt, record, entries = _respond(
        brief, plan, direction, state["public_log"], state["environment"], turn,
        state["initializations"][speaker], state["initialization_answers"][speaker],
        state["histories"][speaker], cache_root, digest, invoke_actor_turn, cached_payload,
        character_context=_character_context(project_root, speaker) if not state["histories"][speaker] else "",
        turn_guidance=state.get("prompt_layers", {}).get("scene.actor.turn", ""),
    )
    state["initialization_answers"][speaker] = record["initialization_answer"]
    state["histories"][speaker].append([prompt, record["answer"]])
    entry_ids = []
    for number, entry in enumerate(entries, 1):
        entry_id = f"t{turn + 1}:{number}"
        state["actor_entries"].append({**entry, "entry_id": entry_id, "speaker": speaker})
        state["public_log"].append({"speaker": speaker, "spoken": entry["spoken"],
                                    "first_person_action": entry["first_person_action"]})
        entry_ids.append(entry_id)
    state["directions"].append({**direction, "turn": turn + 1, "entry_ids": entry_ids})
    if request_id:
        state.setdefault("fulfilled_requests", []).append(request_id)
    save_scene_session(cache_root, digest, state)
    if emit is not None:
        emit("scene.performance.interaction.turn", {
            **_turn_event(brief, direction, turn + 1, entries, entry_ids), "source": "creator-request",
        })


def _turn_event(
    brief: dict[str, Any], direction: dict[str, Any], turn: int,
    entries: list[dict[str, str]], entry_ids: list[str],
) -> dict[str, Any]:
    return {
        "scene_id": brief["scene_id"], "turn": turn, "speaker": direction["next_speaker"],
        "beat_id": direction["beat_id"], "entries": len(entry_ids),
        "turn_entries": [{"entry_id": entry_id, "spoken": item["spoken"],
                          "first_person_action": item["first_person_action"]}
                         for entry_id, item in zip(entry_ids, entries)],
    }


def _respond(
    brief: dict[str, Any], plan: dict[str, Any], direction: dict[str, Any],
    public_log: list[dict[str, str]], environment: dict[str, Any] | None, turn: int,
    initialization: str, initialization_answer: str, history: list[tuple[str, str]],
    cache_root: Path, digest: str,
    invoke_actor_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]],
    cached_payload: Callable[..., dict[str, Any]],
    character_context: str = "",
    turn_guidance: str = "",
) -> tuple[str, dict[str, Any], list[dict[str, str]]]:
    cue = _environment_cue(environment, direction["beat_id"])
    prompt = render_actor_interaction_prompt(
        brief, plan, direction, public_log, cue, character_context,
        literary_guidance=turn_guidance,
    )
    record = _actor_turn(brief, plan, direction, turn, prompt, initialization,
                         initialization_answer, history, cache_root, digest, invoke_actor_turn, cached_payload)
    beat = next(item for item in plan["beats"] if item["beat_id"] == direction["beat_id"])
    material = parse_actor_scene_material(_current_turn_payload(record["response"], beat["beat_id"]),
                                          brief, [beat], direction["next_speaker"], max_entries=4)
    return prompt, record, material["entries"]


def _actor_turn(
    brief: dict[str, Any], plan: dict[str, Any], direction: dict[str, Any], turn: int,
    prompt: str, initialization: str, initialization_answer: str, history: list[tuple[str, str]],
    cache_root: Path, digest: str,
    invoke_actor_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]],
    cached_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    speaker = direction["next_speaker"]
    key = hashlib.sha256(json.dumps([initialization, initialization_answer, history, prompt], ensure_ascii=False).encode()).hexdigest()[:12]
    path = cache_root / f"performance-interaction-actor-{digest}-{turn + 1}-{key}.json"
    beat = next(item for item in plan["beats"] if item["beat_id"] == direction["beat_id"])

    def produce() -> dict[str, Any]:
        actor_prompt = prompt
        for attempt in range(2):
            answer, init_answer = invoke_actor_turn(
                initialization, initialization_answer, tuple(history), actor_prompt,
            )
            try:
                response = _answer_payload(answer)
                parse_actor_scene_material(_current_turn_payload(response, beat["beat_id"]),
                                           brief, [beat], speaker, max_entries=4)
                return {"answer": answer, "initialization_answer": init_answer, "response": response}
            except ValueError:
                if attempt:
                    raise
                actor_prompt = prompt + "\n\n" + render_prompt_template(
                    "scene.actor.turn-repair.protocol", (answer[-8_000:],))
        raise AssertionError("unreachable actor repair")

    def validate(payload: dict[str, Any]) -> dict[str, Any]:
        if (not isinstance(payload.get("answer"), str) or not isinstance(payload.get("initialization_answer"), str)
                or not isinstance(payload.get("response"), dict)):
            raise ValueError("actor conversation record lacks preserved answers")
        parse_actor_scene_material(_current_turn_payload(payload["response"], beat["beat_id"]),
                                   brief, [beat], speaker, max_entries=4)
        return payload

    return cached_payload(path, produce, validate)


def _current_turn_payload(response: dict[str, Any], beat_id: str) -> dict[str, Any]:
    """Stage only replies to the present cue; a volunteered future beat has not happened."""

    entries = response.get("entries")
    if not isinstance(entries, list):
        return response
    return {**response, "entries": [item for item in entries
                                    if not isinstance(item, dict) or item.get("beat_id") == beat_id]}


def _environment_cue(environment: dict[str, Any] | None, beat_id: str) -> str:
    passages = environment.get("passages") if isinstance(environment, dict) else None
    if not isinstance(passages, list):
        return ""
    return "\n".join(str(item.get("description") or "") for item in passages
                     if isinstance(item, dict) and item.get("beat_id") == beat_id)[:900]


def _character_context(project_root: Path | None, speaker: str) -> str:
    """Give an actor its own life and relationships after the pure persona initialization."""

    if project_root is None:
        return ""
    characters = (project_root / "characters").resolve()
    path = (characters / f"{speaker}.yaml").resolve()
    if not path.is_relative_to(characters) or not path.is_file():
        return ""
    try:
        character = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, YAMLError):
        return ""
    if not isinstance(character, dict):
        return ""
    memory = {key: character[key] for key in (
        "role", "identity", "background_story", "bdi", "psychology", "relationships",
    ) if key in character}
    return json.dumps(memory, ensure_ascii=False, separators=(",", ":"))[:6_000]


__all__ = ["new_scene_session", "load_scene_session", "save_scene_session", "continue_scene_actor"]
