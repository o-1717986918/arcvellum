"""Stable literary-domain API consumed by Studio application services."""

from ..foundation.draft_text import final_body_from_draft_path
from ..literary.assets.continuity.architecture import REQUIRED_FIELDS
from ..literary.assets.continuity.ledger import continuity_ledger_status
from ..literary.assets.canon.contracts import (
    SCENE_LIFECYCLE_VALUES,
    CanonPatchCandidateIssue,
    SceneLifecycleStatus,
    canon_patch_candidate_issues,
)
from ..literary.assets.promotion import (
    file_sha256,
    latest_approval,
    promotion_eligibility_errors,
    promotion_output_paths,
)
from ..literary.assets.registry import ASSET_SCHEMA_NAMES
from ..literary.assets.workshop import ASSET_CANDIDATE_DIRS
from ..literary.export.docx import export_markdown_to_docx
from ..literary.ingest import (
    DOMAIN_REVIEW_SCHEMA,
    IDENTITY_RESOLUTION_SCHEMA,
    RECONSTRUCTION_CANDIDATE_SCHEMA,
    read_chunk_extraction,
    reconstruction_paths,
    validate_chunk_extraction,
    validate_domain_review,
    validate_identity_resolution,
    validate_reconstruction_candidate,
)
from ..literary.ingest.evidence import canonical_digest
from ..literary.planning.contracts import word_budget_adherence_for_body
from ..literary.planning.materializer import scene_inventory_contract_issues
from ..literary.planning.length_repair import target_length_repair_pending
from ..literary.planning.rhythm_plan import load_rhythm_plan, save_rhythm_plan
from ..literary.review.creative_quality import (
    creative_quality_profile_exists,
    creative_quality_profile_path,
    load_creative_quality_profile,
    save_creative_quality_profile,
)
from ..literary.review.reader_experience import (
    chapter_obligation_contract_issues,
    reader_experience_adherence_for_body,
)
from ..literary.review.project_targets import (
    ProjectReviewTargetIssue,
    project_review_repair_target_issues,
)
from ..literary.review.resolution import (
    review_new_character_issues,
    review_semantic_consistency_issues,
)
from ..literary.scene.branching.proposals import branch_proposal_contract
from ..literary.scene.context.broker import context_trace_status
from ..literary.scene.promotion.generation_gate import (
    candidate_generation_gate,
    candidate_language_gate,
)
from ..literary.scene.promotion.historical import validate_historical_promotion
from ..literary.scene.promotion.revision_contract import (
    revision_manifest_errors,
    revision_source_requires_anti_evasion_rows,
)
from ..literary.style.anti_ai import style_lint_gate
from ..literary.style.defaults import ensure_default_style_mount
from ..literary.style.lab import (
    active_project_style,
    create_author_project,
    create_author_work,
    default_style_library_root,
    ensure_style_library,
    import_work_source,
)
from ..literary.style.mount import (
    StyleMountPriority,
    StyleMountScope,
    StyleVersionMountConflictError,
    StyleVersionMountError,
    inspect_active_style_mount,
    mount_style_profile_version,
)
from ..literary.style.prompt import style_prompt_quality_report
from ..literary.style.punctuation import lint_punctuation
from ..literary.style.review import style_review_machine_values
from ..literary.style.session import (
    StyleSessionConflictError,
    StyleSessionError,
    StyleSessionResult,
    StyleSourceSelection,
    formal_style_profile_dirs,
    load_style_session,
    prepare_style_engineering_session,
    resolve_formal_style_profile,
    source_content_digest,
)
from ..literary.style.snapshot import (
    active_style_mount_snapshot_payload,
    artifact_style_mount_snapshot,
    read_artifact_style_mount_snapshot,
    style_version_mount_snapshot,
)
from ..literary.style.version import (
    inspect_style_profile_version,
    inspect_style_version_directory,
    plan_style_profile_version,
)

__all__ = [
    "ASSET_CANDIDATE_DIRS",
    "ASSET_SCHEMA_NAMES",
    "CanonPatchCandidateIssue",
    "DOMAIN_REVIEW_SCHEMA",
    "IDENTITY_RESOLUTION_SCHEMA",
    "ProjectReviewTargetIssue",
    "RECONSTRUCTION_CANDIDATE_SCHEMA",
    "REQUIRED_FIELDS",
    "SCENE_LIFECYCLE_VALUES",
    "SceneLifecycleStatus",
    "StyleMountPriority",
    "StyleMountScope",
    "StyleSessionConflictError",
    "StyleSessionError",
    "StyleSessionResult",
    "StyleSourceSelection",
    "StyleVersionMountConflictError",
    "StyleVersionMountError",
    "active_project_style",
    "active_style_mount_snapshot_payload",
    "artifact_style_mount_snapshot",
    "branch_proposal_contract",
    "candidate_generation_gate",
    "candidate_language_gate",
    "canon_patch_candidate_issues",
    "canonical_digest",
    "chapter_obligation_contract_issues",
    "context_trace_status",
    "continuity_ledger_status",
    "create_author_project",
    "create_author_work",
    "creative_quality_profile_exists",
    "creative_quality_profile_path",
    "default_style_library_root",
    "ensure_default_style_mount",
    "ensure_style_library",
    "export_markdown_to_docx",
    "file_sha256",
    "final_body_from_draft_path",
    "formal_style_profile_dirs",
    "import_work_source",
    "inspect_active_style_mount",
    "inspect_style_profile_version",
    "inspect_style_version_directory",
    "latest_approval",
    "lint_punctuation",
    "load_creative_quality_profile",
    "load_rhythm_plan",
    "load_style_session",
    "mount_style_profile_version",
    "plan_style_profile_version",
    "prepare_style_engineering_session",
    "project_review_repair_target_issues",
    "promotion_eligibility_errors",
    "promotion_output_paths",
    "read_artifact_style_mount_snapshot",
    "read_chunk_extraction",
    "reader_experience_adherence_for_body",
    "reconstruction_paths",
    "resolve_formal_style_profile",
    "review_new_character_issues",
    "review_semantic_consistency_issues",
    "revision_manifest_errors",
    "revision_source_requires_anti_evasion_rows",
    "save_creative_quality_profile",
    "save_rhythm_plan",
    "scene_inventory_contract_issues",
    "source_content_digest",
    "style_lint_gate",
    "style_prompt_quality_report",
    "style_review_machine_values",
    "style_version_mount_snapshot",
    "target_length_repair_pending",
    "validate_chunk_extraction",
    "validate_domain_review",
    "validate_historical_promotion",
    "validate_identity_resolution",
    "validate_reconstruction_candidate",
    "word_budget_adherence_for_body",
]
