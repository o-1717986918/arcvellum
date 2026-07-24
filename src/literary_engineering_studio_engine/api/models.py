"""Pydantic request contracts for the legacy Engine HTTP adapter."""

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - optional HTTP dependency
    BaseModel = object


class RunWorkflowRequest(BaseModel):
    project_root: str
    mode: str = "full-cycle"
    scene: str = "scenes/scene_0001.yaml"
    chapter_id: str = "chapter_0001"
    target_length: int = 100000
    include_blocked: bool = False
    overwrite_draft: bool = False
    generate_candidate: bool = False
    promote_candidate: bool = False
    agent_review: bool = False
    agent_tasks: bool = False
    provider: str = "auto"
    run_id: str = ""
    resume_run_id: str = ""
    overwrite_run: bool = False


class ApprovalRequest(BaseModel):
    project_root: str
    run_id: str
    decision: str
    actor: str = "human"
    notes: str = ""


class DisplayFieldRequest(BaseModel):
    project_root: str
    target_type: str
    target_id: str
    field: str
    value: object = ""
    actor: str = "user-ui"


class UiNoteRequest(BaseModel):
    project_root: str
    target_type: str
    target_id: str
    note: str
    actor: str = "user-ui"


class HumanChoiceRequest(BaseModel):
    project_root: str
    choice_id: str = ""
    route: str = ""
    task_id: str = ""
    decision_type: str = "general_project_choice"
    target: dict = {}
    options: list = []
    selected: str
    rationale: str = ""
    actor: str = "user-ui"
    materialize: bool = True


class RunAgentRequest(BaseModel):
    project_root: str
    agent_id: str
    task: str
    system_prompt: str
    user_prompt: str
    provider: str = "auto"
    out_dir: str = ""


class SaveConfigRequest(BaseModel):
    active_profile: str = "deepseek"
    profiles: dict = {}
    defaults: dict = {}


class InitProjectRequest(BaseModel):
    target: str
    title: str
    premise: str = ""
    genre: str = ""
    work_type: str = "novel"
    target_length: int = 30000
    language: str = "zh-CN"


class DemoProjectRequest(BaseModel):
    target: str
    title: str = "文学工程 Demo"
    run_agent_workflow: bool = True


class AssistantChatRequest(BaseModel):
    project_root: str = ""
    message: str


class DirectorChatRequest(BaseModel):
    project_root: str = ""
    message: str
    provider: str = "auto"
    auto_execute: bool = True
    agent_tasks: bool = False
    create_project_if_missing: bool = True
    project_parent: str = ""
    project_title: str = ""


class AssetCreateRequest(BaseModel):
    project_root: str
    asset_type: str = "character"
    brief: str = ""
    target_id: str = ""
    source: str = ""
    provider: str = "auto"


class AssetReviewRequest(BaseModel):
    project_root: str
    candidate: str
    provider: str = "auto"


class AssetPromoteRequest(BaseModel):
    project_root: str
    candidate: str
    group: str = ""
    approval_run_id: str = ""
    allow_unapproved: bool = False


class CanonApplyRequest(BaseModel):
    project_root: str
    patch: str = ""
    approval_run_id: str = ""
    allow_unapproved: bool = False


class StyleAuthorRequest(BaseModel):
    style_library_root: str = ""
    name: str
    author_id: str = ""
    mode: str = "public_domain_or_authorized"
    source_note: str = ""


class StyleWorkRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    title: str
    work_id: str = ""
    year: str = ""
    notes: str = ""


class StyleSourceImportRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    work_id: str
    text: str
    filename: str = ""
    chunk_chars: int = 4000


class StyleCompileRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    profile_id: str = "default"
    provider: str = "auto"


class StyleSkillBuildRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    profile_id: str = "default"
    style_id: str = ""


class StyleEvalRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    profile_id: str = "default"
    reference_text: str
    task_input_text: str
    mode: str = "back-translation"
    provider: str = "auto"


class StyleMountRequest(BaseModel):
    project_root: str
    style_library_root: str = ""
    style_id: str
    allow_unreviewed: bool = False
