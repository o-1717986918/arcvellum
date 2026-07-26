"""Platform-Agent sidecars for whole-work archaeology reconstruction."""

from __future__ import annotations

from pathlib import Path

from ...agent_tasks import write_agent_tasks
from .reconstruction_contracts import ARCHAEOLOGY_DOMAINS, reconstruction_paths


MODE_EMPHASIS = {
    "continuation": (
        "Prioritize current Canon candidates, unresolved promises, end-state character "
        "conditions, relationship pressure, and credible future story space."
    ),
    "rewrite": (
        "Prioritize structural problems, replaceable events, preservation obligations, "
        "causal repairs, and character logic that should survive a rewrite."
    ),
    "adaptation": (
        "Prioritize sceneability, medium conversion, visual action, compressible events, "
        "character merge hypotheses, and adaptation costs."
    ),
    "analysis": (
        "Produce analysis-only observations. Every asset recommendation and review "
        "decision must be analysis_only; no promotable Archive candidate may be created."
    ),
}


def write_reconstruction_tasks(
    *,
    root: Path,
    import_dir: Path,
    manifest: dict[str, object],
    logical_import_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    identity_dir = logical_import_dir or import_dir
    relative_import = identity_dir.relative_to(root)
    paths = reconstruction_paths(relative_import)
    work_id = str(manifest.get("work_id") or import_dir.name)
    mode = str(manifest.get("mode") or "continuation")
    evidence = manifest.get("evidence_index")
    evidence_path = (
        str(evidence.get("path") or "")
        if isinstance(evidence, dict)
        else ""
    )
    archaeology = manifest.get("archaeology")
    aggregate_path = (
        str(archaeology.get("aggregate_path") or "")
        if isinstance(archaeology, dict)
        else ""
    )
    manifest_path = identity_dir / "source_manifest.json"
    aggregate = root / aggregate_path
    resolution_task = import_dir / "reconstruction/identity_resolution.agent_tasks.md"
    candidate_task = import_dir / "reconstruction/candidate_project.agent_tasks.md"
    review_task = import_dir / "reconstruction/domain_review.agent_tasks.md"
    _write_resolution_task(
        root=root,
        task=resolution_task,
        identity_task=root / paths["resolution_task"],
        work_id=work_id,
        manifest=manifest_path,
        evidence=root / evidence_path,
        aggregate=aggregate,
        output=root / paths["resolution"],
        report=root / paths["resolution_report"],
    )
    _write_candidate_task(
        root=root,
        task=candidate_task,
        identity_task=root / paths["candidate_task"],
        work_id=work_id,
        mode=mode,
        manifest=manifest_path,
        evidence=root / evidence_path,
        aggregate=aggregate,
        resolution=root / paths["resolution"],
        output=root / paths["candidate"],
        report=root / paths["candidate_report"],
    )
    _write_review_task(
        root=root,
        task=review_task,
        identity_task=root / paths["review_task"],
        work_id=work_id,
        mode=mode,
        manifest=manifest_path,
        evidence=root / evidence_path,
        aggregate=aggregate,
        resolution=root / paths["resolution"],
        candidate=root / paths["candidate"],
        output=root / paths["review"],
        report=root / paths["review_report"],
    )
    return resolution_task, candidate_task, review_task


def _write_resolution_task(
    *,
    root: Path,
    task: Path,
    identity_task: Path,
    work_id: str,
    manifest: Path,
    evidence: Path,
    aggregate: Path,
    output: Path,
    report: Path,
) -> None:
    write_agent_tasks(
        task,
        title=f"archaeology identity and conflict resolution {work_id}",
        root=root,
        source_paths=[manifest, evidence, aggregate],
        notes=[
            "Aggregate occurrences are evidence, not Canon.",
            "Every entity occurrence and every aggregate conflict must be accounted for exactly once.",
            "Unresolved is a valid result; majority wording is not proof.",
        ],
        tasks=[
            (
                "复核别名与共指",
                f"创建 `{_rel(output, root)}` 和 `{_rel(report, root)}`。"
                "把每个 entity occurrence 分配到一个稳定 entity_group；只有证据足够时才 merge，"
                "同名不同人、代称漂移、身份伪装和叙述误导必须允许 keep_distinct、partial 或 unresolved。",
            ),
            (
                "逐项处置冲突",
                "按 aggregate conflicts 的零基索引逐项写 conflict_reviews。"
                "每项必须给 disposition、evidence_refs、confidence、rationale 和 unknowns；"
                "不得删除矛盾或只保留多数解释。",
            ),
        ],
        identity_path=identity_task,
    )


def _write_candidate_task(
    *,
    root: Path,
    task: Path,
    identity_task: Path,
    work_id: str,
    mode: str,
    manifest: Path,
    evidence: Path,
    aggregate: Path,
    resolution: Path,
    output: Path,
    report: Path,
) -> None:
    write_agent_tasks(
        task,
        title=f"archaeology candidate project reconstruction {work_id}",
        root=root,
        source_paths=[manifest, evidence, aggregate, resolution],
        notes=[
            MODE_EMPHASIS.get(mode, MODE_EMPHASIS["continuation"]),
            "Archive-compatible assets may be proposed only through registered candidate schemas.",
            "Style and promise findings remain evidence-bound domain observations unless another formal route promotes them.",
        ],
        tasks=[
            (
                "重建候选项目",
                f"创建 `{_rel(output, root)}` 和 `{_rel(report, root)}`。"
                "输出 project_summary、Archive-compatible assets 与 domain_observations；"
                "人物、世界、情节、文风和承诺必须分域，不把假说写成事实。",
            ),
            (
                "维护晋升边界",
                "每个 asset 必须包含 candidate_id、asset_type、完整 schema-compatible payload、"
                "evidence_refs、confidence、unresolved_refs 和 promotion_recommendation。"
                "模式为 analysis 时所有 recommendation 必须是 analysis_only。",
            ),
        ],
        identity_path=identity_task,
    )


def _write_review_task(
    *,
    root: Path,
    task: Path,
    identity_task: Path,
    work_id: str,
    mode: str,
    manifest: Path,
    evidence: Path,
    aggregate: Path,
    resolution: Path,
    candidate: Path,
    output: Path,
    report: Path,
) -> None:
    write_agent_tasks(
        task,
        title=f"archaeology domain review {work_id}",
        root=root,
        source_paths=[manifest, evidence, aggregate, resolution, candidate],
        notes=[
            f"Review all domains: {', '.join(ARCHAEOLOGY_DOMAINS)}.",
            MODE_EMPHASIS.get(mode, MODE_EMPHASIS["continuation"]),
            "This review authorizes deterministic candidate materialization only; it is not Archive promotion approval.",
        ],
        tasks=[
            (
                "执行分领域独立复核",
                f"创建 `{_rel(output, root)}` 和 `{_rel(report, root)}`。"
                "分别审查 character、world、plot、style、promise 的证据覆盖、逻辑完整性、"
                "冲突保留、未知项和模式适配；每个域都要有独立 status、blocking_issues 与 warnings。",
            ),
            (
                "裁定候选物化",
                "为 candidate_project 中每个 asset 精确写一条 asset_decision："
                "promote、hold、reject 或 analysis_only。不得在存在 blocking_issues 时 promote；"
                "analysis 模式只能 analysis_only。",
            ),
        ],
        identity_path=identity_task,
    )


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
