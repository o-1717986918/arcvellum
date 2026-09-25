"""Director-led scene rehearsal with one preserved transcript per actor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from literary_engineering_studio_engine.public.literary import (
    parse_actor_scene_material,
    parse_interaction_direction,
    render_actor_initialization_prompt,
    render_actor_interaction_prompt,
    render_interaction_direction_prompt,
    render_interaction_materials,
)

from .pi_scene_payload import _answer_payload


def perform_scene_interaction(
    brief: dict[str, Any], expression: dict[str, Any], plan: dict[str, Any],
    sources: str, environment: dict[str, Any] | None, cache_root: Path, digest: str,
    invoke: Callable[[str, str], str],
    invoke_actor_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]],
    cached_payload: Callable[..., dict[str, Any]],
    emit: Callable[[str, dict[str, Any]], None] | None,
    project_root: Path | None = None,
) -> str:
    participants = list(brief.get("participants") or ())
    if not participants:
        return ""
    state = load_scene_session(cache_root, digest, brief["scene_id"]) or new_scene_session(
        brief, expression, plan, environment)
    if environment and not state.get("environment"):
        state["environment"] = environment
    initializations = state["initializations"]
    histories = state["histories"]
    initialization_answers = state["initialization_answers"]
    public_log = state["public_log"]
    actor_entries = state["actor_entries"]
    directions = state["directions"]
    max_turns = min(12, max(4, len(participants) * 3))
    for turn in range(len(directions), max_turns):
        direction = plan["opening_direction"] if turn == 0 else _next_direction(
            brief, plan, public_log, turn, sources, cache_root, digest, invoke, cached_payload)
        if direction["finish"]:
            break
        speaker = direction["next_speaker"]
        actor_prompt, turn_record, entries = _respond(
            brief, plan, direction, public_log, environment, turn,
            initializations[speaker], initialization_answers[speaker], histories[speaker],
            cache_root, digest, invoke_actor_turn, cached_payload,
            character_context=_character_context(project_root, speaker) if not histories[speaker] else "",
        )
        initialization_answers[speaker] = turn_record["initialization_answer"]
        histories[speaker].append((actor_prompt, turn_record["answer"]))
        entry_ids = []
        for number, entry in enumerate(entries, 1):
            entry_id = f"t{turn + 1}:{number}"
            actor_entries.append({**entry, "entry_id": entry_id, "speaker": speaker})
            public_log.append({"speaker": speaker, "spoken": entry["spoken"],
                               "first_person_action": entry["first_person_action"]})
            entry_ids.append(entry_id)
        directions.append({**direction, "turn": turn + 1, "entry_ids": entry_ids})
        save_scene_session(cache_root, digest, state)
        if emit is not None:
            emit("scene.performance.interaction.turn", _turn_event(brief, direction, turn + 1, entries, entry_ids))
    save_scene_session(cache_root, digest, state)
    if not actor_entries and not environment:
        return ""
    return render_interaction_materials(plan, directions, actor_entries, environment,
                                        viewpoint=str(brief.get("viewpoint") or ""))


def new_scene_session(
    brief: dict[str, Any], expression: dict[str, Any], plan: dict[str, Any], environment: dict[str, Any] | None,
) -> dict[str, Any]:
    participants = list(brief.get("participants") or ())
    return {
        "scene_id": brief["scene_id"],
        "initializations": {speaker: render_actor_initialization_prompt({
            "name": speaker, "roleplay_direction": plan["actor_prompts"][speaker],
        }) for speaker in participants},
        "initialization_answers": {speaker: "" for speaker in participants},
        "histories": {speaker: [] for speaker in participants},
        "public_log": [], "actor_entries": [], "directions": [], "environment": environment,
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
) -> None:
    speaker = request["speaker"]
    turn = len(state["directions"])
    direction = {"finish": False, "next_speaker": speaker, "beat_id": request["beat_id"],
                 "scene_change": request.get("scene_change", ""), "cue": request["cue"],
                 "director_note": "主创按需续演"}
    prompt, record, entries = _respond(
        brief, plan, direction, state["public_log"], state["environment"], turn,
        state["initializations"][speaker], state["initialization_answers"][speaker],
        state["histories"][speaker], cache_root, digest, invoke_actor_turn, cached_payload,
        character_context=_character_context(project_root, speaker) if not state["histories"][speaker] else "",
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
) -> tuple[str, dict[str, Any], list[dict[str, str]]]:
    cue = _environment_cue(environment, direction["beat_id"])
    prompt = render_actor_interaction_prompt(brief, plan, direction, public_log, cue, character_context)
    record = _actor_turn(brief, plan, direction, turn, prompt, initialization,
                         initialization_answer, history, cache_root, digest, invoke_actor_turn, cached_payload)
    beat = next(item for item in plan["beats"] if item["beat_id"] == direction["beat_id"])
    material = parse_actor_scene_material(_current_turn_payload(record["response"], beat["beat_id"]),
                                          brief, [beat], direction["next_speaker"], max_entries=4)
    return prompt, record, material["entries"]


def _next_direction(
    brief: dict[str, Any], plan: dict[str, Any], public_log: list[dict[str, str]], turn: int,
    sources: str, cache_root: Path, digest: str, invoke: Callable[[str, str], str], cached_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    prompt = render_interaction_direction_prompt(brief, plan, public_log, turn, sources)
    key = hashlib.sha256(prompt.encode()).hexdigest()[:12]
    path = cache_root / f"performance-interaction-direction-{digest}-{turn + 1}-{key}.json"
    return cached_payload(path, lambda: _generate_direction(prompt, brief, plan, invoke),
                          lambda payload: parse_interaction_direction(payload, brief, plan))


def _generate_direction(
    prompt: str, brief: dict[str, Any], plan: dict[str, Any], invoke: Callable[[str, str], str],
) -> dict[str, Any]:
    for attempt in range(2):
        candidate_prompt = prompt if attempt == 0 else (
            prompt + "\n\n上一条未形成完整、有效的 JSON。请只返回一个字段齐全的 JSON 对象。"
        )
        try:
            payload = _answer_payload(invoke(candidate_prompt, "worker"))
            parse_interaction_direction(payload, brief, plan)
            return payload
        except ValueError:
            if attempt:
                raise
    raise AssertionError("unreachable direction retry")


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
                actor_prompt = (
                    prompt + "\n\n上一轮回答的 JSON 结构或转义无法解析。请保留你刚才的人物选择与话语，"
                    "仅把它重新写成一份完整、有效的 JSON 对象。上一轮回答：\n" + answer[-8_000:]
                )
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


__all__ = ["perform_scene_interaction", "new_scene_session", "load_scene_session", "save_scene_session", "continue_scene_actor"]
