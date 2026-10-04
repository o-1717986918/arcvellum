"""Recover literal source spans when transport omitted Markdown quote markers only."""
from hashlib import sha256
import re


def restore_commission_source(answer, payload):
    recoveries = []
    projected, offsets = _quote_projection(answer)
    for index, request in enumerate(payload.get("material_requests") or []):
        if not isinstance(request, dict):
            continue
        for field in ("author_prompt", "style_direction"):
            text = request.get(field)
            if not isinstance(text, str) or not text or text in answer:
                continue
            needle, _ = _quote_projection(text)
            start = projected.find(needle)
            if not needle or start < 0 or projected.find(needle, start + 1) >= 0:
                continue
            raw_start, raw_end = offsets[start], offsets[start + len(needle) - 1] + 1
            line_start = answer.rfind("\n", 0, raw_start) + 1
            if re.fullmatch(r"[ \t]*> ?", answer[line_start:raw_start]):
                raw_start = line_start
            original = answer[raw_start:raw_end]
            request[field] = original
            recoveries.append({"request_index": index, "field": field, "projection": "blockquote-markers-only",
                "extracted_sha256": sha256(text.encode()).hexdigest(), "start": raw_start, "end": raw_end})
    if recoveries:
        payload["commission_format_recovery"] = recoveries
    return payload


def _quote_projection(text):
    parts, offsets, position = [], [], 0
    for line in text.splitlines(keepends=True):
        prefix = re.match(r"[ \t]*> ?", line)
        count = prefix.end() if prefix else 0
        parts.append(line[count:])
        offsets.extend(range(position + count, position + len(line)))
        position += len(line)
    return "".join(parts), offsets
