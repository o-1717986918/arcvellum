"""Executable task-package contract shared by every formal route.

Route blueprints live in :mod:`task_registry`; this module deliberately owns
only the cross-route envelope, prompt projection, output policy, and readable
task rendering.  That separation lets routes evolve independently without
duplicating the formal Agent/Worker contract.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .context_contract import CONTEXT_CONTRACT_FINGERPRINT_FIELDS, normalize_context_contract as _normalize_context_contract
from .markdown_renderer import render_task_markdown
from .prompt_projection import project_prompt_asset
from ..prompt_registry import resolve_prompt_asset
TASK_CONTRACT_REVISION = "2026-08-20.33"
COMPLETION_SCHEMA = "literary-engineering-workbench/agent-task-completion/v1"
RECHECK_REQUIRED_STATES = {
    "asset-review-pass",
    "asset-approval-revision",
    "canon-review-pass",
    "committee-pass",
}
TASK_TYPE_EXECUTION = {
    "deterministic-cli": ("deterministic", "deterministic-engine"),
    "deterministic-review": ("deterministic", "deterministic-engine"),
    "deterministic-cli-plus-platform-review": ("agent-required", "main-agent"),
    "deterministic-cli-or-repair": ("agent-required", "main-agent"),
    "manual-route-repair": ("agent-required", "main-agent"),
    "human-approval-boundary": ("human-required", "human-decision"),
    "main-platform-agent-prose": ("agent-required", "main-creative-agent"),
    "main-platform-agent-prose-revision": ("agent-required", "main-creative-agent"),
    "platform-agent-asset-creation": ("agent-required", "main-creative-agent"),
    "platform-agent-extraction": ("agent-required", "main-creative-agent"),
    "platform-agent-archaeology-resolution": ("agent-required", "main-review-agent"),
    "platform-agent-archaeology-reconstruction": ("agent-required", "main-creative-agent"),
    "platform-agent-archaeology-domain-review": ("agent-required", "main-review-agent"),
    "platform-agent-revision": ("agent-required", "main-creative-agent"),
    "platform-agent-style-prompt": ("agent-required", "main-creative-agent"),
    "platform-agent-asset-review": ("agent-required", "main-review-agent"),
    "platform-agent-evaluation": ("agent-required", "main-review-agent"),
    "platform-agent-judgment": ("agent-required", "main-review-agent"),
    "platform-agent-review": ("agent-required", "main-review-agent"),
    # Historical task packages can be reopened and upgraded in place.
    "deterministic-command": ("deterministic", "deterministic-engine"),
    "human-choice": ("human-required", "human-decision"),
    "platform-agent": ("agent-required", "main-agent"),
    "platform-agent-creative": ("agent-required", "main-creative-agent"),
    "platform-agent-prose": ("agent-required", "main-creative-agent"),
}

HIGH_IMPACT_OUTPUT_PREFIXES = (
    "canon/",
    "characters/",
    "drafts/scenes/",
    "manuscript/",
    "releases/",
    "state/",
)
EXPLICIT_TASK_CONTRACT_FIELDS = {
    "execution_policy",
    "agent_role",
    "human_gate",
    "runtime_capabilities_required",
    "output_contracts",
}


def normalize_relative(value: str | Path) -> str:
    return Path(str(value)).as_posix()


def task_contract_fingerprint(task: dict[str, object]) -> str:
    """Hash the executable task contract, excluding lifecycle metadata."""

    fields = {
        key: task.get(key)
        for key in (
            "schema",
            "task_contract_revision",
            "task_id",
            "route",
            "scene_id",
            "current_state",
            "task_type",
            "prompt_asset_id",
            "command",
            "required_reading",
            "source_paths",
            "agent_source_paths",
            *CONTEXT_CONTRACT_FINGERPRINT_FIELDS,
            "expected_outputs",
            "repair_targets",
            "repair_target_sha256",
            "hard_constraints",
            "style_constraints",
            "validation_gates",
            "forbidden_shortcuts",
            "execution_policy",
            "agent_role",
            "human_gate",
            "runtime_capabilities_required",
            "output_contracts",
            "semantic_artifact",
            "system_owned_fields",
            "core_managed_outputs",
            "scene_character_assets",
        )
    }
    encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def enrich_task_payload(task: dict[str, object]) -> dict[str, object]:
    """Add the authoritative execution and prompt contracts to a task."""
    enriched = dict(task)
    enriched["task_contract_revision"] = TASK_CONTRACT_REVISION
    prompt_id = str(enriched.get("prompt_asset_id") or "").strip()
    if not prompt_id:
        raise ValueError("formal task is missing prompt_asset_id")
    preview = resolve_prompt_asset(prompt_id)
    if preview.asset is None:
        raise ValueError(f"formal task prompt asset is not registered: {prompt_id}")
    enriched["prompt_asset"] = project_prompt_asset(preview, prompt_id)
    expected_outputs = [str(item) for item in enriched.get("expected_outputs") or []]
    enriched["core_managed_outputs"], core_managed_outputs = _core_output_contract(
        enriched, expected_outputs
    )
    _normalize_context_contract(enriched)
    semantic = enriched.get("semantic_artifact") if isinstance(enriched.get("semantic_artifact"), dict) else None
    if semantic is not None:
        semantic_path = normalize_relative(str(semantic.get("path") or ""))
        if semantic_path not in expected_outputs:
            raise ValueError("semantic artifact must be declared in expected_outputs")
        if not str(semantic.get("schema_name") or "").strip() or not str(semantic.get("consumed_by") or "").strip():
            raise ValueError("semantic artifact requires schema_name and consumed_by")
        enriched["semantic_artifact"] = {
            "path": semantic_path,
            "kind": str(semantic.get("kind") or "semantic-artifact"),
            "schema_name": str(semantic["schema_name"]),
            "consumed_by": str(semantic["consumed_by"]),
            "writeback_policy": str(semantic.get("writeback_policy") or "preview-required"),
        }

    # Agents author creative reasoning, not lifecycle bookkeeping.  Keep every
    # deterministic identity/path/enum contract in the task package so the
    # Worker can materialize it after the substantive outputs exist.
    enriched["system_owned_fields"] = _merge_system_owned_fields(
        enriched.get("system_owned_fields"),
        _system_owned_fields(enriched, expected_outputs, semantic),
    )

    present_contract_fields = EXPLICIT_TASK_CONTRACT_FIELDS & set(enriched)
    if present_contract_fields == EXPLICIT_TASK_CONTRACT_FIELDS:
        if str(enriched.get("execution_policy") or "") == "human-required":
            enriched["submission_command"] = ""
            enriched["completion_command"] = ""
        return enriched
    if present_contract_fields:
        missing = ", ".join(sorted(EXPLICIT_TASK_CONTRACT_FIELDS - present_contract_fields))
        raise ValueError(f"formal task has a partial explicit execution contract; missing: {missing}")

    task_type = str(enriched.get("task_type") or "").strip()
    try:
        execution_policy, agent_role = TASK_TYPE_EXECUTION[task_type]
    except KeyError as exc:
        raise ValueError(f"formal task has no explicit execution contract for task_type: {task_type}") from exc
    human_required = execution_policy == "human-required"
    human_reasons = [str(enriched.get("current_state") or "human-decision")] if human_required else []
    if execution_policy == "deterministic":
        capabilities = ["deterministic-command"]
    elif human_required:
        capabilities = []
    else:
        capabilities = ["read-task-sources"]
        if expected_outputs:
            capabilities.append("write-expected-outputs")

    enriched.update(
        {
            "execution_policy": execution_policy,
            "agent_role": agent_role,
            "human_gate": {
                "required": human_required,
                "reasons": human_reasons,
                "source": "task-registry",
            },
            "runtime_capabilities_required": capabilities,
            "output_contracts": [
                output_contract(
                    item,
                    execution_policy,
                    core_managed=item in core_managed_outputs,
                    semantic=semantic if semantic and item == semantic["path"] else None,
                )
                for item in expected_outputs
            ],
        }
    )
    if human_required:
        enriched["submission_command"] = ""
        enriched["completion_command"] = ""
        enriched["forbidden_shortcuts"] = [
            item
            for item in enriched.get("forbidden_shortcuts") or []
            if "task-submit and task-complete" not in str(item)
        ]
        enriched["forbidden_shortcuts"].extend(
            [
                "Do not treat the Agent or a delegated runtime as the decision maker for this boundary.",
                "Do not create an agent completion marker or a substitute approval file; use the Studio decision interface.",
            ]
        )
    return enriched


def _core_output_contract(
    task: dict[str, object],
    expected_outputs: list[str],
) -> tuple[list[str], set[str]]:
    """Return CLI-owned outputs, including every executable Agent sidecar."""

    protected = {str(item) for item in task.get("core_managed_outputs") or []}
    protected.update(
        item for item in expected_outputs if item.endswith(".agent_tasks.md")
    )
    return [item for item in expected_outputs if item in protected], protected


def _system_owned_fields(
    task: dict[str, object],
    expected_outputs: list[str],
    semantic: dict[str, object] | None,
) -> dict[str, object]:
    """Build the cross-route machine-owned part of an Agent task contract."""

    task_id = str(task.get("task_id") or "")
    route = str(task.get("route") or "")
    state = str(task.get("current_state") or "")
    policy = TASK_TYPE_EXECUTION.get(str(task.get("task_type") or ""), ("", ""))[0]
    receipts: list[dict[str, object]] = []
    if policy == "agent-required":
        status = "recheck_required" if state in RECHECK_REQUIRED_STATES else "complete"
        checked = status == "complete"
        for item in expected_outputs:
            normalized = normalize_relative(item)
            if not normalized.endswith(".agent_completion.json"):
                continue
            base = normalized[: -len(".agent_completion.json")]
            source_task = base + (".md" if base.endswith(".agent_tasks") else ".agent_tasks.md")
            receipts.append(
                {
                    "path": normalized,
                    "schema": COMPLETION_SCHEMA,
                    "source_task": source_task,
                    "status": status,
                    "expected_artifacts_checked": checked,
                }
            )
    lifecycle: dict[str, object] = {
        "task_identity": {"task_id": task_id, "route": route, "current_state": state},
        "completion_receipts": receipts,
        "allowed_status_values": ["complete", "recheck_required"],
    }
    result: dict[str, object] = {"lifecycle": lifecycle}
    if semantic is not None:
        result["semantic"] = {
            "path": str(semantic.get("path") or ""),
            "kind": str(semantic.get("kind") or ""),
            "schema_name": str(semantic.get("schema_name") or ""),
            "scene_id": str(task.get("scene_id") or ""),
            "consumed_by": str(semantic.get("consumed_by") or ""),
            "status_values": ["complete"],
        }
    return result


def _merge_system_owned_fields(existing: object, generated: dict[str, object]) -> dict[str, object]:
    """Merge route-specific ownership with the required cross-route envelope."""

    merged = dict(existing) if isinstance(existing, dict) else {}
    for key, value in generated.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def output_contract(
    path: str,
    execution_policy: str,
    *,
    core_managed: bool = False,
    semantic: dict[str, object] | None = None,
) -> dict[str, str]:
    """Describe ownership and writeback policy for a declared output."""

    normalized = normalize_relative(path)
    lower = normalized.lower()
    if core_managed:
        kind = "deterministic"
        policy = "automatic"
    elif lower.endswith("agent_completion.json") or ".agent_completion." in lower:
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
        policy = "approval-required" if lower.startswith(HIGH_IMPACT_OUTPUT_PREFIXES) else "preview-required"
    result = {"path": normalized, "kind": kind, "writeback_policy": policy}
    if semantic is not None:
        result.update(
            {
                "kind": str(semantic.get("kind") or "semantic-artifact"),
                "schema_name": str(semantic.get("schema_name") or ""),
                "consumed_by": str(semantic.get("consumed_by") or ""),
            }
        )
    return result
