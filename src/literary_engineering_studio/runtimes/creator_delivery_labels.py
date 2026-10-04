"""Resolve explicit participant names inside natural commission headings."""
import re

_LABEL = re.compile(
    r"(?:角色扮演器|角色扮演|扮演器|角色|人物描写器|人物描写|人物)"
    r"[（(](?:角色|人物)\s*[:：]\s*(?P<name>[^()（）]+)[）)]"
)


def resolve_creator_targets(payload, context):
    participants = (context.get("briefing") or {}).get("scene_brief", {}).get("participants", [])
    for index, request in enumerate(payload.get("material_requests") or []):
        if request.get("kind") not in {"actor", "character-description"}:
            continue
        original = request.get("target")
        match = _LABEL.fullmatch(original) if isinstance(original, str) else None
        if match and match["name"].strip() in participants:
            request["target"] = match["name"].strip()
            payload.setdefault("target_label_recovery", []).append({"request_index": index,
                "original": original, "participant": request["target"]})
    return payload
