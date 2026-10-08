"""Freeze source-backed attachments and render a readable material invitation."""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping


def freeze_material_candidate(ref, candidates: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
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


def validate_material_context_budget(request, archives, selected_materials) -> None:
    context = str(getattr(request, "working_context", "") or "")
    total = len(context) + sum(len(item["content"]) for item in archives)
    total += sum(len(item["content"]) for item in selected_materials)
    if total > 32_000:
        raise ValueError("selected context exceeds 32000 characters; choose narrower archive or material excerpts")


def natural_material_invitation(task: Mapping[str, Any]) -> str:
    parts = ["【创作邀请】\n" + str(task["author_prompt"])]
    details = (
        ("本场对象", task.get("target")),
        ("希望读者感受到", task.get("purpose")),
        ("进入的时刻", task.get("scene_moment")),
        ("眼前线索", task.get("cue")),
        ("逐轮经历", task.get("scene_change")),
    )
    lines = [f"{label}：{value}" for label, value in details if value]
    if lines:
        parts.append("【此刻的场景】\n" + "\n".join(lines))
    context = str(task.get("working_context") or "").strip()
    if context:
        parts.append("【主创的工作札记】\n" + context)
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
    return "\n\n".join(parts)


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
