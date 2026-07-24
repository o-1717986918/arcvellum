"""Workflow platform blueprint generation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_PLATFORMS = (
    "langgraph",
    "dify",
    "llamaindex-workflows",
    "crewai",
    "microsoft-agent-framework",
)


@dataclass(frozen=True)
class PlatformProfile:
    key: str
    name: str
    role: str
    best_for: tuple[str, ...]
    weak_for: tuple[str, ...]
    adoption: str
    source: str


@dataclass(frozen=True)
class WorkflowNode:
    node_id: str
    purpose: str
    current_cli: str
    primary_engine: str
    dify_mapping: str
    human_gate: str
    persistent_artifact: str


@dataclass(frozen=True)
class BlueprintResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    platform_count: int
    node_count: int


PLATFORM_PROFILES: dict[str, PlatformProfile] = {
    "langgraph": PlatformProfile(
        key="langgraph",
        name="LangGraph",
        role="core_state_machine",
        best_for=(
            "long-running stateful agent orchestration",
            "human-in-the-loop checkpoints",
            "resume, rollback, and traceable chapter pipelines",
        ),
        weak_for=(
            "non-technical visual editing by itself",
            "rapid no-code reviewer forms",
        ),
        adoption="Recommended core runtime after the local CLI contract is stable.",
        source="https://docs.langchain.com/oss/python/langgraph/overview",
    ),
    "dify": PlatformProfile(
        key="dify",
        name="Dify Workflow / Chatflow",
        role="visual_review_and_prototype_layer",
        best_for=(
            "visual workflow prototypes",
            "knowledge retrieval demos",
            "human review forms for branch approval and draft revision",
            "web app or service API surface for non-developer reviewers",
        ),
        weak_for=(
            "owning the canonical repository state directly",
            "large-scale Git-style writeback without a backend adapter",
            "complex cross-chapter deterministic state transitions",
        ),
        adoption="Use as a review console and prototype canvas, backed by local project files or an API adapter.",
        source="https://docs.dify.ai/en/cloud/use-dify/nodes/start",
    ),
    "llamaindex-workflows": PlatformProfile(
        key="llamaindex-workflows",
        name="LlamaIndex Workflows",
        role="rag_and_event_subflow",
        best_for=(
            "RAG ingestion and querying subflows",
            "typed event-driven retrieval pipelines",
            "knowledge evaluation loops",
        ),
        weak_for=(
            "visual product UI by itself",
            "full editorial project governance by itself",
        ),
        adoption="Use for retrieval-heavy subsystems when the knowledge layer grows beyond the lightweight index.",
        source="https://docs.llamaindex.ai/en/stable/understanding/workflows/",
    ),
    "crewai": PlatformProfile(
        key="crewai",
        name="CrewAI Flows / Crews",
        role="role_team_simulation_layer",
        best_for=(
            "role-based agent teams",
            "fast prototypes of character, director, and reviewer crews",
            "structured flow experiments with state",
        ),
        weak_for=(
            "strict canon writeback governance by itself",
            "large repository-oriented source-of-truth management by itself",
        ),
        adoption="Use for optional experiments around roleplay teams; keep canon and review CI in the workbench.",
        source="https://docs.crewai.com/en/concepts/flows",
    ),
    "microsoft-agent-framework": PlatformProfile(
        key="microsoft-agent-framework",
        name="Microsoft Agent Framework",
        role="enterprise_azure_option",
        best_for=(
            "Azure and Microsoft Foundry deployments",
            "type-safe graph workflows",
            "enterprise observability and governance",
        ),
        weak_for=(
            "lightweight local-first experimentation",
            "non-Azure personal prototype projects",
        ),
        adoption="Consider later if the project moves into Azure enterprise deployment.",
        source="https://learn.microsoft.com/en-us/agent-framework/overview/",
    ),
}


WORKFLOW_NODES: tuple[WorkflowNode, ...] = (
    WorkflowNode(
        node_id="load_project_state",
        purpose="Read project.yaml, canon, characters, plot, style, and scene metadata.",
        current_cli="init / file read",
        primary_engine="LangGraph",
        dify_mapping="Start node with project, scene, and task fields; backend API loads files.",
        human_gate="none",
        persistent_artifact="project.yaml and source folders",
    ),
    WorkflowNode(
        node_id="retrieve_memory",
        purpose="Retrieve hard context and soft memory for the current scene or chapter.",
        current_cli="index / search",
        primary_engine="LlamaIndex Workflows + Qdrant later",
        dify_mapping="Knowledge Retrieval node for prototype; backend adapter for canonical retrieval logs.",
        human_gate="none",
        persistent_artifact="memory/index.json and retrieval logs",
    ),
    WorkflowNode(
        node_id="build_context_packet",
        purpose="Build the compact context packet used by downstream agents.",
        current_cli="context",
        primary_engine="LangGraph",
        dify_mapping="Template node or HTTP Request node calling the workbench CLI/API.",
        human_gate="optional context inspection",
        persistent_artifact="memory/context_packets/{scene_id}.md plus memory/context_packets/{scene_id}.trace.json",
    ),
    WorkflowNode(
        node_id="character_simulation",
        purpose="Let character agents propose plausible actions from belief, desire, intention, fear, and secret.",
        current_cli="simulate-scene",
        primary_engine="CrewAI optional, LangGraph core",
        dify_mapping="Iteration or Loop node over characters, each using LLM or Agent node.",
        human_gate="none before branch proposal",
        persistent_artifact="branches/{scene_id}/roleplay_simulation.md",
    ),
    WorkflowNode(
        node_id="world_consequence",
        purpose="Evaluate causal consequences against world rules, location state, and timeline.",
        current_cli="simulate-scene",
        primary_engine="LangGraph",
        dify_mapping="LLM node plus Code node for deterministic checks.",
        human_gate="none",
        persistent_artifact="branches/{scene_id}/roleplay_simulation.md",
    ),
    WorkflowNode(
        node_id="director_selection",
        purpose="Score branches by character logic, canon safety, drama, literary value, and future potential.",
        current_cli="simulate-scene",
        primary_engine="LangGraph",
        dify_mapping="Variable Aggregator plus LLM node and If-Else routing.",
        human_gate="branch selection required",
        persistent_artifact="branches/{scene_id}/roleplay_simulation.md",
    ),
    WorkflowNode(
        node_id="draft_workspace",
        purpose="Create the drafting workspace from the selected branch and context packet.",
        current_cli="draft-scene",
        primary_engine="LangGraph",
        dify_mapping="HTTP Request node calls workbench; Human Input node can edit selected branch notes.",
        human_gate="branch approval before draft",
        persistent_artifact="drafts/scenes/{scene_id}.md",
    ),
    WorkflowNode(
        node_id="review_ci",
        purpose="Review draft against canon, scene purpose, required sections, and writeback candidates.",
        current_cli="review-scene",
        primary_engine="LangGraph",
        dify_mapping="LLM review nodes, Code node for required fields, If-Else node for pass/revise/reject.",
        human_gate="approval required before canon writeback",
        persistent_artifact="reviews/scenes/{scene_id}-review.md",
    ),
    WorkflowNode(
        node_id="state_writeback",
        purpose="Write approved facts, character changes, relation changes, and foreshadowing updates.",
        current_cli="planned",
        primary_engine="LangGraph",
        dify_mapping="Human Input decision followed by HTTP Request to backend writeback endpoint.",
        human_gate="required",
        persistent_artifact="canon, characters, plot, memory writeback logs",
    ),
    WorkflowNode(
        node_id="chapter_export",
        purpose="Assemble scenes into chapter output after all scene reviews pass.",
        current_cli="planned",
        primary_engine="LangGraph",
        dify_mapping="Output node for preview; backend owns final file export.",
        human_gate="required before final export",
        persistent_artifact="exports/chapters/{chapter_id}.md",
    ),
)


def build_orchestration_blueprint(
    project_root: Path,
    platforms: Iterable[str] | None = None,
    output: Path | None = None,
    json_output: Path | None = None,
) -> BlueprintResult:
    project_root = project_root.resolve()
    selected = _select_platforms(platforms)
    project_label = _project_label(project_root)

    default_dir = project_root / "prompts" / "orchestration"
    markdown_path = (output or default_dir / "agent_orchestration_blueprint.md").resolve()
    json_path = (json_output or default_dir / "agent_orchestration_blueprint.json").resolve()
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "literary-engineering-workbench/orchestration-blueprint/v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "project_label": project_label,
        "recommendation": {
            "core": "LangGraph",
            "visual_review": "Dify",
            "knowledge_subflows": "LlamaIndex Workflows",
            "roleplay_experiments": "CrewAI",
            "enterprise_option": "Microsoft Agent Framework",
        },
        "platforms": [asdict(profile) for profile in selected],
        "nodes": [asdict(node) for node in WORKFLOW_NODES],
        "boundaries": [
            "Dify 可以展示内容并收集决策，但 canon 写回必须经过 workbench 后端。",
            "向量或知识库检索结果只是上下文，不等于 canon 事实。",
            "剧情分支选择和 canon 写回必须经过明确人工确认。",
            "任何框架适配器都必须保留现有文件产物，确保项目可审计、可回滚。",
        ],
    }

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")

    return BlueprintResult(
        project_root=project_root,
        markdown_path=markdown_path,
        json_path=json_path,
        platform_count=len(selected),
        node_count=len(WORKFLOW_NODES),
    )


def _select_platforms(platforms: Iterable[str] | None) -> tuple[PlatformProfile, ...]:
    if platforms is None:
        keys = DEFAULT_PLATFORMS
    else:
        keys = tuple(_normalize_key(item) for item in platforms if item.strip())
        if not keys:
            keys = DEFAULT_PLATFORMS

    unknown = [key for key in keys if key not in PLATFORM_PROFILES]
    if unknown:
        valid = ", ".join(sorted(PLATFORM_PROFILES))
        raise ValueError(f"unknown platform(s): {', '.join(unknown)}. valid: {valid}")

    return tuple(PLATFORM_PROFILES[key] for key in dict.fromkeys(keys))


def _normalize_key(value: str) -> str:
    value = value.strip().lower().replace("_", "-")
    aliases = {
        "dify-ai": "dify",
        "llamaindex": "llamaindex-workflows",
        "llama-index": "llamaindex-workflows",
        "llamaindex-workflow": "llamaindex-workflows",
        "crew": "crewai",
        "crew-ai": "crewai",
        "ms-agent-framework": "microsoft-agent-framework",
        "agent-framework": "microsoft-agent-framework",
    }
    return aliases.get(value, value)


def _project_label(project_root: Path) -> str:
    project_yaml = project_root / "project.yaml"
    if not project_yaml.exists():
        return project_root.name
    for line in project_yaml.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("cn_name:"):
            return stripped.split(":", 1)[1].strip() or project_root.name
    return project_root.name


def _render_markdown(payload: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Agent 编排平台蓝图：{payload['project_label']}")
    lines.append("")
    lines.append(f"生成时间：{payload['generated_at']}")
    lines.append("")
    lines.append("## 推荐结论")
    lines.append("")
    lines.append("- 核心状态机：LangGraph，负责可回滚、可暂停、可审计的长流程。")
    lines.append("- 可视化审稿台：Dify，负责展示草稿、分支、审查结果并收集人工决策。")
    lines.append("- 知识库子流程：LlamaIndex Workflows，负责后期复杂 RAG 摄取、检索、重排和评测。")
    lines.append("- 角色实验层：CrewAI，可用于快速试验人物、导演、审查员等角色团队。")
    lines.append("- 企业部署备选：Microsoft Agent Framework，适合未来走 Azure / Foundry / 企业治理路线。")
    lines.append("")
    lines.append("## 平台对比")
    lines.append("")
    lines.append("| 平台 | 建议角色 | 适合 | 不适合 | 采用建议 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for profile in payload["platforms"]:
        lines.append(
            "| {name} | {role} | {best_for} | {weak_for} | {adoption} |".format(
                name=profile["name"],
                role=profile["role"],
                best_for="<br>".join(profile["best_for"]),
                weak_for="<br>".join(profile["weak_for"]),
                adoption=profile["adoption"],
            )
        )
    lines.append("")
    lines.append("## 节点映射")
    lines.append("")
    lines.append("| 节点 | 目的 | 当前 CLI | 主引擎 | Dify 映射 | 人工门禁 | 产物 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for node in payload["nodes"]:
        lines.append(
            "| {node_id} | {purpose} | `{current_cli}` | {primary_engine} | {dify_mapping} | {human_gate} | `{persistent_artifact}` |".format(
                **node
            )
        )
    lines.append("")
    lines.append("## Dify 适配方案")
    lines.append("")
    lines.append("Dify 不直接持有作品项目源状态，而是作为可视化编排和人工确认层：")
    lines.append("")
    lines.append("1. User Input 收集 `project_root`、`scene_id`、任务类型和人工备注。")
    lines.append("2. Knowledge Retrieval 可用于演示式检索，但正式写作仍优先调用本地 workbench 检索。")
    lines.append("3. HTTP Request 调用本地/内网 workbench API，生成 context、simulation、draft、review。")
    lines.append("4. Human Input 展示分支、草稿、审查报告，收集 Approve / Revise / Reject。")
    lines.append("5. 只有 Approve 分支允许触发写回；写回必须经过 workbench 后端，避免 Dify 直接改仓库文件。")
    lines.append("")
    lines.append("## 边界")
    lines.append("")
    for boundary in payload["boundaries"]:
        lines.append(f"- {boundary}")
    lines.append("")
    lines.append("## 官方资料")
    lines.append("")
    for profile in payload["platforms"]:
        lines.append(f"- {profile['name']}：{profile['source']}")
    lines.append("")
    return "\n".join(lines)
