"""Consumer-side validation for Literary Engineering task packages."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any


TASK_SCHEMA = "literary-engineering-workbench/agent-task/v1"
EXECUTION_CONTRACT_SCHEMA = "literary-engineering-studio/task-execution/v0.3"
HUMAN_GATE_TOKENS = (
    "human-choice",
    "human_approval",
    "approval",
    "canon-apply",
    "state-apply",
    "release-approval",
    "publish-approval",
)

HIGH_IMPACT_PREFIXES = (
    "canon/",
    "characters/",
    "drafts/scenes/",
    "manuscript/",
    "releases/",
    "state/",
)

CREATIVE_TASK_TOKENS = (
    "prose",
    "compose",
    "roleplay",
    "branch",
    "style",
    "extract",
    "review",
    "canon",
    "character",
    "world",
)
EXPLICIT_EXECUTION_FIELDS = {
    "execution_policy",
    "agent_role",
    "human_gate",
    "runtime_capabilities_required",
    "output_contracts",
}
PROMPT_ASSET_LIST_FIELDS = (
    "required_inputs",
    "optional_inputs",
    "context_groups",
    "hard_constraints",
    "style_constraints",
    "output_contract",
    "review_requirements",
    "forbidden_shortcuts",
)


@dataclass(frozen=True)
class HumanGate:
    required: bool
    reasons: tuple[str, ...]
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {"required": self.required, "reasons": list(self.reasons), "source": self.source}


@dataclass(frozen=True)
class OutputContract:
    path: str
    kind: str
    writeback_policy: str

    def as_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "kind": self.kind,
            "writeback_policy": self.writeback_policy,
        }


@dataclass(frozen=True)
class TaskExecutionContract:
    execution_policy: str
    agent_role: str
    human_gate: HumanGate
    runtime_capabilities_required: tuple[str, ...]
    outputs: tuple[OutputContract, ...]
    compatibility_derived: bool

    @property
    def writeback_policy(self) -> str:
        policies = {item.writeback_policy for item in self.outputs}
        if "approval-required" in policies:
            return "approval-required"
        if "preview-required" in policies:
            return "preview-required"
        if "automatic" in policies:
            return "automatic"
        return "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_CONTRACT_SCHEMA,
            "execution_policy": self.execution_policy,
            "agent_role": self.agent_role,
            "human_gate": self.human_gate.as_dict(),
            "runtime_capabilities_required": list(self.runtime_capabilities_required),
            "outputs": [item.as_dict() for item in self.outputs],
            "writeback_policy": self.writeback_policy,
            "compatibility_derived": self.compatibility_derived,
        }


@dataclass(frozen=True)
class TaskPackage:
    project_root: Path
    task_json_path: Path
    task_markdown_path: Path
    payload: dict[str, Any]

    @property
    def task_id(self) -> str:
        return str(self.payload["task_id"])

    @property
    def route(self) -> str:
        return str(self.payload.get("route") or "")

    @property
    def current_state(self) -> str:
        return str(self.payload.get("current_state") or "")

    @property
    def task_type(self) -> str:
        return str(self.payload.get("task_type") or "").strip()

    @property
    def command(self) -> str:
        return str(self.payload.get("command") or "").strip()

    @property
    def source_paths(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.payload.get("source_paths") or [])

    @property
    def required_reading(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.payload.get("required_reading") or [])

    @property
    def expected_outputs(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.payload.get("expected_outputs") or [])

    @property
    def core_managed_outputs(self) -> tuple[str, ...]:
        """Outputs created by the deterministic command, never by the Agent."""

        declared = {str(item) for item in self.expected_outputs}
        return tuple(
            str(item)
            for item in self.payload.get("core_managed_outputs") or []
            if str(item) in declared
        )

    @property
    def human_gate(self) -> HumanGate:
        explicit = self.payload.get("human_gate")
        if isinstance(explicit, dict) and isinstance(explicit.get("required"), bool):
            reasons = tuple(str(item) for item in explicit.get("reasons") or [] if str(item).strip())
            source = str(explicit.get("source") or "task-package")
            return HumanGate(bool(explicit["required"]), reasons, source)
        haystack = " ".join(
            [
                self.current_state,
                str(self.payload.get("task_type") or ""),
                str(self.payload.get("prompt_asset_id") or ""),
            ]
        ).lower()
        reasons = tuple(token for token in HUMAN_GATE_TOKENS if token in haystack)
        return HumanGate(bool(reasons), reasons, "compatibility-inference")

    @property
    def human_gate_reasons(self) -> tuple[str, ...]:
        return self.human_gate.reasons

    @property
    def execution_contract(self) -> TaskExecutionContract:
        explicit_policy = str(self.payload.get("execution_policy") or "").strip()
        explicit_role = str(self.payload.get("agent_role") or "").strip()
        explicit_capabilities = self.payload.get("runtime_capabilities_required")
        explicit_outputs = self.payload.get("output_contracts")
        compatibility_derived = not (
            explicit_policy
            and explicit_role
            and isinstance(explicit_capabilities, list)
            and isinstance(explicit_outputs, list)
            and isinstance(self.payload.get("human_gate"), dict)
        )
        policy = explicit_policy or _derive_execution_policy(self.payload, self.human_gate)
        role = explicit_role or _derive_agent_role(self.payload, policy)
        capabilities = (
            tuple(str(item) for item in explicit_capabilities if str(item).strip())
            if isinstance(explicit_capabilities, list)
            else _derive_capabilities(policy, self.expected_outputs)
        )
        outputs = (
            _parse_output_contracts(explicit_outputs)
            if isinstance(explicit_outputs, list)
            else tuple(_derive_output_contract(path, policy) for path in self.expected_outputs)
        )
        return TaskExecutionContract(
            execution_policy=policy,
            agent_role=role,
            human_gate=self.human_gate,
            runtime_capabilities_required=capabilities,
            outputs=outputs,
            compatibility_derived=compatibility_derived,
        )

    def resolve_project_path(self, relative: str) -> Path:
        normalized = normalize_relative_path(relative)
        target = (self.project_root / Path(*normalized.parts)).resolve()
        if not target.is_relative_to(self.project_root):
            raise ValueError(f"task path escapes project root: {relative}")
        return target


def load_task_package(project_root: Path, task_json_path: Path) -> TaskPackage:
    root = project_root.resolve()
    path = task_json_path.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"task JSON must be inside the work project: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid task JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"task JSON must be an object: {path}")
    _validate_task_payload(payload)
    markdown_rel = str(payload.get("task_markdown") or "")
    if not markdown_rel:
        markdown_rel = f"workflow/tasks/{payload['task_id']}.agent_tasks.md"
    markdown_path = (root / Path(*normalize_relative_path(markdown_rel).parts)).resolve()
    if not markdown_path.exists():
        raise FileNotFoundError(f"task Markdown not found: {markdown_path}")
    return TaskPackage(root, path, markdown_path, payload)


def normalize_relative_path(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("task path must not be empty")
    path = PurePosixPath(text)
    if path.is_absolute() or ":" in path.parts[0] or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"task path must be a normalized project-relative path: {value}")
    return path


def _validate_task_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema") != TASK_SCHEMA:
        raise ValueError(f"unsupported task schema: {payload.get('schema')}")
    for field in ("task_id", "route", "current_state", "task_type"):
        if not str(payload.get(field) or "").strip():
            raise ValueError(f"task package missing {field}")
    for field in ("required_reading", "source_paths", "expected_outputs"):
        values = payload.get(field)
        if not isinstance(values, list):
            raise ValueError(f"task package field must be a list: {field}")
        for value in values:
            normalize_relative_path(str(value))
    for field in ("validation_gates", "forbidden_shortcuts"):
        if not isinstance(payload.get(field), list):
            raise ValueError(f"task package field must be a list: {field}")
    _validate_optional_execution_contract(payload)


def _validate_optional_execution_contract(payload: dict[str, Any]) -> None:
    present = EXPLICIT_EXECUTION_FIELDS & set(payload)
    if present and present != EXPLICIT_EXECUTION_FIELDS:
        missing = ", ".join(sorted(EXPLICIT_EXECUTION_FIELDS - present))
        raise ValueError(f"partial explicit execution contract; missing: {missing}")
    if "execution_policy" in payload and payload["execution_policy"] not in {
        "deterministic",
        "agent-required",
        "human-required",
    }:
        raise ValueError("task package execution_policy is invalid")
    if "agent_role" in payload and not str(payload["agent_role"] or "").strip():
        raise ValueError("task package agent_role must not be empty")
    if "human_gate" in payload:
        gate = payload["human_gate"]
        if not isinstance(gate, dict) or not isinstance(gate.get("required"), bool):
            raise ValueError("task package human_gate must contain a boolean required field")
        if not isinstance(gate.get("reasons", []), list):
            raise ValueError("task package human_gate.reasons must be a list")
    for field in ("runtime_capabilities_required", "output_contracts"):
        if field in payload and not isinstance(payload[field], list):
            raise ValueError(f"task package field must be a list: {field}")
    if "output_contracts" in payload:
        _parse_output_contracts(payload["output_contracts"])
    prompt_asset = payload.get("prompt_asset")
    if prompt_asset is not None:
        if not isinstance(prompt_asset, dict):
            raise ValueError("task package prompt_asset must be an object")
        for field in ("requested_id", "resolved_id", "version", "body"):
            if not str(prompt_asset.get(field) or "").strip():
                raise ValueError(f"task package prompt_asset.{field} must not be empty")
        for field in PROMPT_ASSET_LIST_FIELDS:
            if not isinstance(prompt_asset.get(field), list):
                raise ValueError(f"task package prompt_asset.{field} must be a list")


def _derive_execution_policy(payload: dict[str, Any], human_gate: HumanGate) -> str:
    if human_gate.required:
        return "human-required"
    task_type = str(payload.get("task_type") or "").lower()
    prompt_id = str(payload.get("prompt_asset_id") or "").lower()
    if task_type == "deterministic-cli":
        return "deterministic"
    if "deterministic-cli-plus-platform-review" in task_type:
        return "agent-required"
    if "platform-agent" in task_type or prompt_id:
        return "agent-required"
    if str(payload.get("command") or "").strip():
        return "deterministic"
    return "agent-required"


def _derive_agent_role(payload: dict[str, Any], policy: str) -> str:
    if policy == "human-required":
        return "human-decision"
    if policy == "deterministic":
        return "deterministic-engine"
    haystack = " ".join(
        [
            str(payload.get("task_type") or ""),
            str(payload.get("prompt_asset_id") or ""),
            str(payload.get("current_state") or ""),
        ]
    ).lower()
    if "review" in haystack or "audit" in haystack:
        return "main-review-agent"
    if any(token in haystack for token in CREATIVE_TASK_TOKENS):
        return "main-creative-agent"
    return "main-agent"


def _derive_capabilities(policy: str, outputs: tuple[str, ...]) -> tuple[str, ...]:
    if policy == "human-required":
        return ()
    if policy == "deterministic":
        return ("deterministic-command",)
    values = ["read-task-sources"]
    if outputs:
        values.append("write-expected-outputs")
    return tuple(values)


def _derive_output_contract(path: str, execution_policy: str) -> OutputContract:
    normalized = str(normalize_relative_path(path))
    lower = normalized.lower()
    if lower.endswith("agent_completion.json") or ".agent_completion." in lower:
        kind = "completion-evidence"
        policy = "automatic"
    elif "approval" in lower or lower.startswith("decisions/"):
        kind = "human-approval"
        policy = "approval-required"
    elif execution_policy == "deterministic":
        kind = "deterministic"
        policy = "automatic"
    else:
        kind = "agent-authored"
        policy = "approval-required" if lower.startswith(HIGH_IMPACT_PREFIXES) else "preview-required"
    return OutputContract(normalized, kind, policy)


def _parse_output_contracts(values: list[Any]) -> tuple[OutputContract, ...]:
    parsed: list[OutputContract] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("task package output_contracts entries must be objects")
        path = str(value.get("path") or "").strip()
        kind = str(value.get("kind") or "").strip()
        policy = str(value.get("writeback_policy") or "").strip()
        if not path or not kind or policy not in {"automatic", "preview-required", "approval-required", "none"}:
            raise ValueError("invalid task package output contract")
        parsed.append(OutputContract(str(normalize_relative_path(path)), kind, policy))
    return tuple(parsed)
