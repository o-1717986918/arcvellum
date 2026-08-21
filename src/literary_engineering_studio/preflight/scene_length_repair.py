"""Deterministic preflight for a target-length scene revision."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .scene_manifest_metadata import scene_revision_paths


def target_length_revision_errors(
    task: TaskPackage,
    sandbox: SandboxManifest,
    candidate_rel: str,
    candidate: Path,
) -> list[tuple[str, str, str]]:
    if task.current_state != "target-length-revision" or not candidate.is_file():
        return []
    prompt_rel = scene_revision_paths(task)[2]
    contract = _repair_contract(sandbox.workspace / Path(prompt_rel))
    if contract is None:
        return [(
            prompt_rel,
            "目标长度修订缺少可验证的 prompt manifest。",
            "重新领取 target-length-revision，使用当前 repair plan 生成正式修订任务。",
        )]
    minimum = int(contract.get("minimum_scene_chars") or 0)
    if minimum <= 0:
        return [(
            prompt_rel,
            "目标长度修订未绑定当前场景的最低正文字符数。",
            "重新生成 repair plan 与 revise-scene task；不得由模型猜测长度目标。",
        )]
    actual = _candidate_chars(candidate)
    if actual >= minimum:
        return []
    return [(
        candidate_rel,
        f"目标长度修订仍不足：清洁正文 {actual}，最低要求 {minimum}。",
        "保留完整正文并增加承担因果、关系、信息或余波功能的有效内容；不得以重复、工作流文本或 Markdown 注水。",
    )]


def _repair_contract(prompt_path: Path) -> dict[str, object] | None:
    try:
        prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    standards = prompt.get("generation_standards")
    if not isinstance(standards, dict):
        return None
    contract = standards.get("target_length_repair")
    return contract if isinstance(contract, dict) else None


def _candidate_chars(candidate: Path) -> int:
    from literary_engineering_studio_engine.public.projections import (
        count_delivery_chinese_content_chars,
        final_body_from_workbench_text,
    )

    body = final_body_from_workbench_text(
        candidate.read_text(encoding="utf-8", errors="ignore")
    )
    return count_delivery_chinese_content_chars(body)


__all__ = ["target_length_revision_errors"]
