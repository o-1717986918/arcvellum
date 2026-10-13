"""Freeze source-backed attachments and render a readable material invitation."""

from __future__ import annotations

from hashlib import sha256
from dataclasses import replace
from typing import Any, Mapping


def freeze_material_candidate(ref, candidates: Mapping[str, Mapping[str, Any]], *, visible_only=False) -> dict[str, Any]:
    candidate_id = str(ref.candidate_id)
    candidate = candidates.get(candidate_id)
    if candidate is None:
        raise ValueError(f"selected scene material is unavailable in this transaction: {candidate_id}")
    source = str(candidate.get("text") or "")
    start, end = ref.start_char, ref.end_char
    if start is None:
        selected, char_range = source, None
    else:
        if end is None or end > len(source):
            raise ValueError(f"selected material range exceeds candidate text: {candidate_id}")
        selected, char_range = source[start:end], [start, end]
    if not selected:
        raise ValueError(f"selected material range is empty: {candidate_id}")
    selected = _project_actor_selection(selected, candidate, source, start, end, visible_only)
    basis = str(candidate.get("basis") or "").strip()
    status = basis if basis in {"confirmed", "attributed", "proposed"} else "candidate"
    return {
        "candidate_id": candidate_id,
        "kind": str(candidate.get("kind") or ""),
        "target": str(candidate.get("target") or ""),
        "status": status,
        "focus": str(candidate.get("focus") or ""),
        "source_note": str(candidate.get("source_note") or ""),
        "char_range": char_range,
        "content": selected,
        "content_sha256": sha256(selected.encode("utf-8")).hexdigest(),
    }


def freeze_material_selections(refs,candidates,*,actor_target=None):
    groups = {}
    for ref in refs:
        candidate = candidates.get(ref.candidate_id,{})
        visible = bool(actor_target and candidate.get("kind")=="actor" and candidate.get("target")!=actor_target)
        freeze_material_candidate(ref,candidates,visible_only=visible)
        groups.setdefault((ref.candidate_id,visible),[]).append(ref)
    result = []
    for (_,visible),rows in groups.items():
        for ref,originals in _merge_reference_group(rows):
            value = freeze_material_candidate(ref,candidates,visible_only=visible)
            value["original_selectors"] = [row.to_dict() for row in originals]
            result.append(value)
    return result


def _merge_reference_group(rows):
    whole = next((row for row in rows if row.start_char is None),None)
    if whole:
        return [(whole,rows)]
    merged = []
    for row in sorted(rows,key=lambda ref:ref.start_char):
        if merged and row.start_char <= merged[-1][0].end_char:
            prior,originals = merged[-1]
            merged[-1] = (replace(prior,end_char=max(prior.end_char,row.end_char)),[*originals,row])
        else:
            merged.append((row,[row]))
    return merged


def _project_actor_selection(selected, candidate, source, start, end, visible_only):
    if not visible_only or candidate.get('source_delivery') != 'original-v2':
        return selected
    result = _visible_actor_selection(candidate, source, start, end)
    if not result:
        raise ValueError('selected actor material has no visible expression in this range')
    return result


def _visible_actor_selection(candidate, source, start, end):
    lower, upper = start or 0, len(source) if end is None else end
    spans = candidate.get('annotation_spans')
    if spans is not None:
        visible = [source[max(lower, span['start']):min(upper, span['end'])] for span in spans
                   if span['kind'] in ('spoken', 'first_person_action')
                   and max(lower, span['start']) < min(upper, span['end'])]
        return '\n'.join(visible)
    if start is not None:
        raise ValueError('actor material excerpt needs visible source annotations')
    return '\n'.join(str(candidate.get(key) or '') for key in ('first_person_action', 'spoken')
                     if candidate.get(key))


def validate_material_context_budget(request, archives, selected_materials) -> None:
    context = str(getattr(request, "working_context", "") or "")
    total = len(context) + sum(len(item["content"]) for item in archives)
    total += sum(len(item["content"]) for item in selected_materials)
    if total > 32_000:
        raise ValueError("selected context exceeds 32000 characters; choose narrower archive or material excerpts")


def natural_material_invitation(task: Mapping[str, Any], *, actor_turn_template="") -> str:
    parts, details, actor = _invitation_frame(task, actor_turn_template)
    invitation = str(task.get("author_prompt") or "")
    lines = [f"{label}：{value}" for label, value in details if value and str(value) not in invitation]
    if lines:
        parts.append("【此刻的场景】\n" + "\n".join(lines))
    context = str(task.get("working_context") or "").strip()
    if context and context not in invitation:
        parts.append(("【此刻的上下文】\n" if actor else "【主创的工作札记】\n") + context)
    _append_invitation_sources(parts, task)
    if not actor and task.get('kind') in {'character-description', 'event-narration', 'environment'}:
        parts.append('【事实与想象的来源】\n已提供的Canon、前文与人物档案约束持续事实。'
                     '可见姿态和文学联想可以发展，未提供的生平、习惯来历、数量与制度不能因比喻好看而当作已知事实。'
                     '必要的新设想标为 proposed；人物说法标明 attributed；已有来源注明路径或对应原句，供主创取舍。')
    return "\n\n".join(parts)


def _invitation_frame(task, actor_turn_template):
    actor = task.get('kind') == 'actor' and bool(actor_turn_template)
    parts = ([actor_turn_template.replace('{{ACTOR_NAME}}', str(task['target'])),
              "【你此刻收到的来话与情境】\n" + str(task['author_prompt'])] if actor
             else ["【创作邀请】\n" + str(task["author_prompt"])])
    details = (("你所在的时刻", task.get('scene_moment')),
               ("眼前发生的事", task.get('cue')),
               ("已经历的变化", task.get('scene_change'))) if actor else (
        ("本场对象", task.get("target")),
        ("希望读者感受到", task.get("purpose")),
        ("进入的时刻", task.get("scene_moment")),
        ("眼前线索", task.get("cue")),
        ("逐轮经历", task.get("scene_change")),
    )
    return parts, details, actor


def _append_invitation_sources(parts, task):
    for key, title in (
        ("role_known_archive", "人物亲历或确实听闻的资料"),
        ("director_reference_archive", "供表演校准的参考资料"),
        ("other_archive", "本次选入的作品档案"),
    ):
        archive = task.get(key) or []
        if archive:
            parts.append("【" + title + "】\n" + "\n\n".join(render_archive(item) for item in archive))
    materials = task.get("selected_materials") or []
    if materials:
        parts.append("【主创选入的前序素材】\n" + "\n\n".join(
            render_selected_material(item) for item in materials))


def render_archive(item: Mapping[str, Any]) -> str:
    source = str(item.get("path") or "作品档案")
    line_range = item.get("line_range")
    if line_range:
        source += f"（第 {line_range[0]}–{line_range[1]} 行）"
    status = str(item.get("status") or "参考")
    return f"来源：{source}；状态：{status}\n{item.get('content') or ''}"


def render_selected_material(item: Mapping[str, Any]) -> str:
    heading = "／".join(str(item.get(key) or "") for key in ("kind", "target") if item.get(key))
    heading += f"；候选编号：{item.get('candidate_id') or '未知'}；来源状态：{item.get('status') or 'candidate'}"
    if item.get("char_range"):
        heading += f"；所选字符：{item['char_range'][0]}–{item['char_range'][1]}"
    return f"{heading}\n{item.get('content') or ''}"


__all__ = [
    "freeze_material_candidate", "natural_material_invitation",
    "validate_material_context_budget",
]
