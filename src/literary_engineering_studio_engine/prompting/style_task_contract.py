"""Style-version clauses for platform-agent scene tasks."""

from __future__ import annotations

import json
from pathlib import Path

from ..literary.style.snapshot import read_artifact_style_mount_snapshot


def scene_candidate_style_sources(candidate_path: Path) -> list[Path]:
    return [
        path
        for path in (
            candidate_path.with_suffix(".json"),
            candidate_path.with_suffix(".prompt.json"),
        )
        if path.is_file()
    ]


def scene_candidate_style_snapshot(candidate_path: Path) -> dict[str, object]:
    return read_artifact_style_mount_snapshot(
        candidate_path.with_suffix(".json"),
        candidate_path.with_suffix(".prompt.json"),
    )


def scene_review_style_materials(
    scene_path: Path,
    candidate_path: Path,
) -> tuple[list[Path], dict[str, object]]:
    return (
        [scene_path, candidate_path, *scene_candidate_style_sources(candidate_path)],
        scene_candidate_style_snapshot(candidate_path),
    )


def render_scene_review_style_task(snapshot: dict[str, object]) -> str:
    return f"""先核对候选 manifest 与 prompt manifest 的 `style_mount_snapshot` 完全一致，再只使用该 exact style_id/version_id/content_hash/prompt_sha256/digest 对应的文风版本审查，不得改读当前目录中另一个版本。将下列 machine-owned 快照原样复制到正式 review JSON：

{json.dumps(snapshot, ensure_ascii=False, indent=2)}

若项目存在 `style/active_style_skill.json` 或已挂载 style prompt/profile，必须正式判断文风是否已经塑造正文表达，而不是只作为参考材料出现。对照挂载文风审查叙述距离、视角稳定性、句法和段落节奏、意象/感官路由、心理呈现、对白语气、标点停顿节奏、AI 腔规避和禁止倾向。`style_adherence.status` 只能取 `pass`、`pass_with_notes`、`revise_required` 或 `not_applicable`；有挂载文风时不得使用 `not_applicable`。若正文基本忽略挂载文风，必须用 `revise_required` 并给出可执行重写动作。若快照缺失、冲突或与当前任务资料不一致，不得给出 clean pass。"""


__all__ = [
    "render_scene_review_style_task",
    "scene_candidate_style_snapshot",
    "scene_candidate_style_sources",
    "scene_review_style_materials",
]
