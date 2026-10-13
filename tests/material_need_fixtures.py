"""Explicit source-author need records for the new natural delegation contract."""
from copy import deepcopy


def with_need(request, *, reviewed=None, excerpts=None):
    result = deepcopy(request)
    result["need_evidence"] = {
        "gap": "尚缺此次处境中的直接观察与回应。",
        "why_existing_insufficient": "现有材料未呈现本次刺激中的声音和动作。",
        "expected_use": "用于本段的声音、动作及人物理解。",
        "reviewed_candidate_ids": reviewed or [],
        "existing_material_evidence": excerpts or {},
        "mount_reasons": {f"{kind}:{index}": "以此来源校准本次邀请的处境。"
                         for kind, key in (("archive", "archive_attachments"), ("material", "material_attachments"))
                         for index, _ in enumerate(result.get(key) or [])},
    }
    return result
