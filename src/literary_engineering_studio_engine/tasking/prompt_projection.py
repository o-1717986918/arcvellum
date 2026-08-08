"""Project shared prompt assets into Studio's semantic-only Agent boundary."""

from __future__ import annotations

import re

from .markdown_renderer import AGENT_OUTPUT_CONTRACT


PROMPT_METADATA_LIST_FIELDS = (
    "required_inputs",
    "optional_inputs",
    "context_groups",
    "hard_constraints",
    "style_constraints",
    "output_contract",
    "review_requirements",
    "forbidden_shortcuts",
)
_INSTRUCTION_FIELDS = {
    "hard_constraints",
    "style_constraints",
    "output_contract",
    "review_requirements",
    "forbidden_shortcuts",
}
_LIFECYCLE_OBJECT = re.compile(
    r"(?:completion(?: marker| evidence| receipt| json)?|agent_completion|完成(?:标记|回执))",
    re.IGNORECASE,
)
_LIFECYCLE_MUTATION = re.compile(
    r"(?:write|create|complete|reset|invalidate|process|edit|modify|生成|创建|写入|重置)",
    re.IGNORECASE,
)
_LIFECYCLE_GUARD = re.compile(
    r"(?:worker[- ]owned|studio worker|do not|never|不得|不要|禁止)",
    re.IGNORECASE,
)


def project_prompt_asset(preview, requested_id: str) -> dict[str, object]:
    """Keep semantic instructions while making lifecycle ownership unambiguous."""

    asset = preview.asset
    prompt: dict[str, object] = {
        "requested_id": requested_id,
        "resolved_id": asset.prompt_asset_id,
        "exact": preview.exact,
        "match": asset.match,
        "version": asset.version,
        "route": asset.route,
        "task_type": str(asset.metadata.get("task_type") or ""),
        "title": asset.title,
        "body": _project_body(asset.body),
    }
    for field in PROMPT_METADATA_LIST_FIELDS:
        values = [str(item) for item in asset.metadata.get(field) or []]
        prompt[field] = _project_instructions(values) if field in _INSTRUCTION_FIELDS else values
    prompt["output_contract"] = [AGENT_OUTPUT_CONTRACT]
    return prompt


def _project_instructions(values: list[str]) -> list[str]:
    return [value for value in values if not _is_agent_lifecycle_mutation(value)]


def _project_body(value: str) -> str:
    sentences = re.split(r"(?<=[.!?。！？])\s+", str(value or "").strip())
    return " ".join(
        sentence.strip()
        for sentence in sentences
        if sentence.strip() and not _is_agent_lifecycle_mutation(sentence)
    )


def _is_agent_lifecycle_mutation(value: str) -> bool:
    if not _LIFECYCLE_OBJECT.search(value) or _LIFECYCLE_GUARD.search(value):
        return False
    return bool(_LIFECYCLE_MUTATION.search(value))
