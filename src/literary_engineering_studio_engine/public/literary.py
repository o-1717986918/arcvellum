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
from ..literary.assets.character_identity import (
    character_field_value,
    character_slug,
    read_character_text,
)
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
from ..literary.planning.contracts import load_word_budget_summary, word_budget_adherence_for_body
from ..literary.planning.materializer import (
    longform_materialization_status,
    materialize_lean_window,
    scene_inventory_contract_issues,
)
from ..literary.planning.lean_plan import (
    PLAN_SCHEMA,
    chapter_obligations,
    normalize_initial_plan,
    normalize_scene_window,
    rebalance_lean_budget,
    render_outline,
)
from ..literary.planning.service import calculate_word_budget
from ..literary.planning.length_repair import target_length_repair_pending
from ..literary.planning.chapter_inventory import (
    formal_chapter_ids,
    formal_scene_ids_for_chapter,
)
from ..literary.planning.rhythm_plan import load_rhythm_plan, save_rhythm_plan
from ..literary.planning.narrative_rhythm import analyze_narrative_rhythm_sequence
from ..literary.review.creative_quality import (
    creative_quality_migration_preview,
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
from ..literary.scene.facts import SceneFacts, load_scene_facts, load_scene_mapping
from ..literary.scene.composition.creative_plan import project_brief_expression_context
from ..literary.scene.roleplay.actor_personas import actor_personas_for_participants, list_actor_personas, save_actor_persona
from ..literary.scene.roleplay.performance import (
    render_performance_plan_prompt,
    parse_performance_plan,
    render_actor_prompt,
    render_actor_initialization_prompt,
    render_actor_scene_prompt,
    parse_actor_material,
    parse_actor_scene_material,
    render_environment_prompt,
    parse_environment_material,
    render_performance_materials,
)
from ..literary.scene.roleplay.interaction import (
    parse_interaction_direction,
    parse_scene_material_requests,
    render_actor_interaction_prompt,
    render_interaction_direction_prompt,
    render_interaction_materials,
)
from ..literary.scene.roleplay.relay_plan import parse_relay_plan, render_relay_plan_prompt
from ..literary.scene.roleplay.relay_scene_check import parse_relay_scene_check, render_relay_scene_check_prompt
from ..literary.scene.roleplay.relay_materials import render_relay_materials
from ..literary.style.reference_projection import (
    recent_formal_reference_ids,
    render_style_reference_selection,
    select_active_style_references,
)
from ..literary.scene.transaction import (
    ChangeProposal,
    CreativeResult,
    IssueSeverity,
    LengthTarget,
    ReviewDecision,
    ReviewResult,
    RhythmDirective,
    SceneBrief,
    SceneCommitPlan,
    SceneDelta,
    SceneExecutionMode,
    ScenePolicy,
    SceneRisk,
    SceneRiskLevel,
    SceneTransactionStatus,
    StyleMountRef,
    VerificationIssue,
    VerificationReport,
    CONTINUITY_PROJECTION_SCHEMA,
    build_scene_brief,
    build_scene_commit_plan,
    derive_scene_policy,
    scene_brief_issues,
    verify_creative_result,
    project_committed_scene_delta,
)
from ..literary.scene.promotion.generation_gate import (
    candidate_generation_gate,
    candidate_language_gate,
)
from ..literary.scene.promotion.historical import validate_historical_promotion
from ..literary.scene.promotion.historical_readiness import lean_scene_readiness
from ..literary.scene.promotion.revision_contract import (
    revision_manifest_errors,
    revision_source_requires_anti_evasion_rows,
)
from ..literary.style.anti_ai import style_lint_gate
from ..literary.style.defaults import ensure_default_style_mount, refresh_default_style_mount
from ..literary.style.lab import (
    active_project_style,
    create_author_project,
    create_author_work,
    default_style_library_root,
    ensure_style_library,
    import_work_source,
    list_author_projects,
    list_style_skills,
    mount_style_skill,
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
    active_style_evidence_paths,
    active_style_mount_snapshot_payload,
    active_style_prompt_text,
    artifact_style_mount_snapshot,
    read_artifact_style_mount_snapshot,
    style_version_mount_snapshot,
)
from ..literary.style.version import (
    inspect_style_profile_version,
    inspect_style_version_directory,
    plan_style_profile_version,
)

__all__ = sorted([
    "PLAN_SCHEMA",
    "ASSET_CANDIDATE_DIRS",
    "ASSET_SCHEMA_NAMES",
    "CanonPatchCandidateIssue",
    "ChangeProposal",
    "CONTINUITY_PROJECTION_SCHEMA",
    "CreativeResult",
    "DOMAIN_REVIEW_SCHEMA",
    "IDENTITY_RESOLUTION_SCHEMA",
    "ProjectReviewTargetIssue",
    "RECONSTRUCTION_CANDIDATE_SCHEMA",
    "REQUIRED_FIELDS",
    "SCENE_LIFECYCLE_VALUES",
    "SceneLifecycleStatus",
    "SceneBrief",
    "SceneCommitPlan",
    "SceneDelta",
    "SceneExecutionMode",
    "SceneFacts",
    "ScenePolicy",
    "SceneRisk",
    "SceneRiskLevel",
    "SceneTransactionStatus",
    "calculate_word_budget",
    "chapter_obligations",
    "longform_materialization_status",
    "materialize_lean_window",
    "normalize_initial_plan",
    "normalize_scene_window",
    "rebalance_lean_budget",
    "render_outline",
    "StyleMountPriority",
    "StyleMountRef",
    "StyleMountScope",
    "StyleSessionConflictError",
    "StyleSessionError",
    "StyleSessionResult",
    "StyleSourceSelection",
    "StyleVersionMountConflictError",
    "StyleVersionMountError",
    "IssueSeverity",
    "LengthTarget",
    "ReviewDecision",
    "ReviewResult",
    "RhythmDirective",
    "VerificationIssue",
    "VerificationReport",
    "active_project_style",
    "active_style_evidence_paths",
    "active_style_mount_snapshot_payload",
    "active_style_prompt_text",
    "artifact_style_mount_snapshot",
    "analyze_narrative_rhythm_sequence",
    "branch_proposal_contract",
    "candidate_generation_gate",
    "candidate_language_gate",
    "character_field_value",
    "character_slug",
    "canon_patch_candidate_issues",
    "canonical_digest",
    "chapter_obligation_contract_issues",
    "context_trace_status",
    "continuity_ledger_status",
    "create_author_project",
    "create_author_work",
    "build_scene_brief",
    "build_scene_commit_plan",
    "creative_quality_profile_exists",
    "creative_quality_profile_path",
    "creative_quality_migration_preview",
    "default_style_library_root",
    "ensure_default_style_mount",
    "refresh_default_style_mount",
    "ensure_style_library",
    "export_markdown_to_docx",
    "file_sha256",
    "final_body_from_draft_path",
    "formal_chapter_ids",
    "formal_scene_ids_for_chapter",
    "formal_style_profile_dirs",
    "import_work_source",
    "inspect_active_style_mount",
    "inspect_style_profile_version",
    "inspect_style_version_directory",
    "latest_approval",
    "lean_scene_readiness",
    "lint_punctuation",
    "list_author_projects",
    "list_style_skills",
    "load_creative_quality_profile",
    "load_word_budget_summary",
    "load_scene_facts",
    "load_scene_mapping",
    "load_rhythm_plan",
    "load_style_session",
    "mount_style_profile_version",
    "mount_style_skill",
    "plan_style_profile_version",
    "prepare_style_engineering_session",
    "project_review_repair_target_issues",
    "promotion_eligibility_errors",
    "promotion_output_paths",
    "read_artifact_style_mount_snapshot",
    "read_chunk_extraction",
    "read_character_text",
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
    "scene_brief_issues",
    "source_content_digest",
    "style_lint_gate",
    "style_prompt_quality_report",
    "style_review_machine_values",
    "style_version_mount_snapshot",
    "target_length_repair_pending",
    "derive_scene_policy",
    "validate_chunk_extraction",
    "validate_domain_review",
    "validate_historical_promotion",
    "validate_identity_resolution",
    "validate_reconstruction_candidate",
    "word_budget_adherence_for_body",
    "verify_creative_result",
    "project_committed_scene_delta",
    "select_active_style_references",
    "recent_formal_reference_ids",
    "render_style_reference_selection",
    "project_brief_expression_context",
    "parse_interaction_direction",
    "render_actor_interaction_prompt",
    "render_interaction_direction_prompt",
    "render_interaction_materials",
    "actor_personas_for_participants",
    "list_actor_personas",
    "save_actor_persona",
    "parse_relay_plan",
    "parse_relay_scene_check",
    "render_relay_plan_prompt",
    "render_relay_scene_check_prompt",
    "render_relay_materials",
])
