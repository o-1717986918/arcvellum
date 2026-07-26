"""Task- and role-derived authorization for runtime capabilities."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from ...contracts import TaskPackage, normalize_relative_path
from .contracts import (
    CapabilityId,
    CapabilityManifest,
    CapabilityPolicyError,
    CapabilityRequest,
    bounded_result_limit,
)


BASE_AGENT_CAPABILITIES = (
    CapabilityId.PROJECT_QUERY.value,
    CapabilityId.SCHEMA_INSPECT.value,
    CapabilityId.TEXT_STATISTICS.value,
    CapabilityId.REFERENCE_SEARCH.value,
)
REVIEW_STATE_TOKENS = ("review", "audit", "revision", "resolve", "conflict")
EXTRACTION_STATE_TOKENS = ("extract", "ingest", "archaeology", "citation", "source")
PATH_ARGUMENTS: dict[str, tuple[str, ...]] = {
    CapabilityId.TEXT_STATISTICS.value: ("path",),
    CapabilityId.CITATION_LOOKUP.value: ("paths",),
    CapabilityId.REFERENCE_SEARCH.value: ("paths",),
    CapabilityId.ASSET_DIFF.value: ("before_path", "after_path"),
}


def build_capability_manifest(task: TaskPackage) -> CapabilityManifest:
    policy = task.payload.get("capability_policy")
    policy = policy if isinstance(policy, dict) else {}
    return CapabilityManifest(
        task_id=task.task_id,
        route=task.route,
        current_state=task.current_state,
        agent_role=task.execution_contract.agent_role,
        allowed_capability_ids=tuple(_allowed_capabilities(task, policy)),
        readable_paths=tuple(_readable_paths(task)),
        writable_paths=tuple(_normalized_paths(task.expected_outputs)),
        network_domains=tuple(_normalized_domains(policy.get("network_domains"))),
        max_result_chars=bounded_result_limit(policy.get("max_result_chars")),
    )


class CapabilityPolicy:
    def authorize(self, manifest: CapabilityManifest, request: CapabilityRequest) -> None:
        if request.task_id != manifest.task_id:
            raise CapabilityPolicyError("task-mismatch", "capability request does not belong to the active task")
        if request.capability_id not in manifest.allowed_capability_ids:
            raise CapabilityPolicyError("capability-not-authorized", f"capability is not authorized: {request.capability_id}")
        self._validate_paths(manifest, request)
        if request.capability_id == CapabilityId.RESEARCH_WEB.value:
            self._validate_network(manifest, request.arguments)

    def _validate_paths(self, manifest: CapabilityManifest, request: CapabilityRequest) -> None:
        allowed = {*manifest.readable_paths, *manifest.writable_paths}
        for field in PATH_ARGUMENTS.get(request.capability_id, ()):
            raw = request.arguments.get(field)
            values = raw if isinstance(raw, list) else [] if raw is None or raw == "" else [raw]
            if not values and field in {"path", "before_path", "after_path"}:
                raise CapabilityPolicyError("missing-path", f"capability argument is required: {field}")
            for value in values:
                try:
                    normalized = str(normalize_relative_path(str(value)))
                except ValueError as exc:
                    raise CapabilityPolicyError("path-invalid", str(exc)) from exc
                if not _covered_by(normalized, allowed):
                    raise CapabilityPolicyError("path-not-authorized", f"path is outside the task manifest: {normalized}")

    def _validate_network(self, manifest: CapabilityManifest, arguments: dict[str, Any]) -> None:
        raw_url = str(arguments.get("url") or "").strip()
        parsed = urlsplit(raw_url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host:
            raise CapabilityPolicyError("network-url-invalid", "research.web requires an HTTPS URL")
        if not any(host == domain or host.endswith("." + domain) for domain in manifest.network_domains):
            raise CapabilityPolicyError("network-domain-not-authorized", f"network domain is not allow-listed: {host}")


def _covered_by(relative: str, allowed: set[str]) -> bool:
    path = PurePosixPath(relative)
    for candidate in allowed:
        base = PurePosixPath(candidate)
        if path == base or base in path.parents:
            return True
    return False


def _allowed_capabilities(task: TaskPackage, policy: dict[str, Any]) -> list[str]:
    contract = task.execution_contract
    if contract.execution_policy != "agent-required" or contract.human_gate.required:
        return []
    allowed = list(BASE_AGENT_CAPABILITIES)
    haystack = _task_haystack(task)
    if task.route == "source-ingest" or any(token in haystack for token in EXTRACTION_STATE_TOKENS):
        allowed.append(CapabilityId.CITATION_LOOKUP.value)
    if contract.agent_role == "main-review-agent" or any(token in haystack for token in REVIEW_STATE_TOKENS):
        allowed.append(CapabilityId.ASSET_DIFF.value)
    if CapabilityId.RESEARCH_WEB.value in _strings(policy.get("allow")):
        allowed.append(CapabilityId.RESEARCH_WEB.value)
    denied = set(_strings(policy.get("deny")))
    return _unique([item for item in allowed if item not in denied])


def _readable_paths(task: TaskPackage) -> list[str]:
    from ..task_program import compact_task_references

    agent_sources = task.payload.get("agent_source_paths")
    readable = _strings(agent_sources) if isinstance(agent_sources, list) else list(task.source_paths)
    readable.extend(compact_task_references(task))
    readable.extend(task.core_managed_outputs)
    return _normalized_paths(readable)


def _task_haystack(task: TaskPackage) -> str:
    return " ".join(
        (
            task.route,
            task.current_state,
            task.task_type,
            str(task.payload.get("prompt_asset_id") or ""),
        )
    ).lower()


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalized_paths(values: object) -> list[str]:
    result: list[str] = []
    for value in values if isinstance(values, (list, tuple)) else []:
        normalized = str(normalize_relative_path(str(value)))
        if normalized not in result:
            result.append(normalized)
    return result


def _normalized_domains(value: object) -> list[str]:
    result: list[str] = []
    for item in value if isinstance(value, list) else []:
        domain = str(item).strip().lower().rstrip(".")
        if domain and "/" not in domain and ":" not in domain and domain not in result:
            result.append(domain)
    return result


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
