"""Agent-assisted JSON draft and patch-plan generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agent_provider import run_agent_task
from .agent_schema import minimal_payload, validate_agent_run


ALLOWED_PATCH_TARGET_PREFIXES = ("characters/", "scenes/", "plot/", "style/", "drafts/", "reviews/")


@dataclass(frozen=True)
class AgentJsonBuildResult:
    project_root: Path
    run_dir: Path
    validation_path: Path
    schema_name: str
    status: str


@dataclass(frozen=True)
class AgentPatchPlanResult:
    project_root: Path
    run_dir: Path
    report_path: Path
    json_path: Path
    validation_path: Path
    target: str
    status: str


def build_agent_json(
    project_root: Path,
    *,
    schema_name: str,
    agent_id: str,
    task: str,
    source: Path | None = None,
    target: str = "",
    provider: str = "auto",
    output_dir: Path | None = None,
) -> AgentJsonBuildResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    source_text = _read_source(root, source)
    dry_payload = minimal_payload(schema_name)
    if schema_name == "json_patch_plan.v1":
        dry_payload.update(_dry_patch_payload(target or "reviews/agent/manual_patch.json", source))
    run_result = run_agent_task(
        root,
        agent_id=agent_id,
        task=task,
        system_prompt="You generate JSON that conforms to the requested literary engineering schema. Output JSON only.",
        user_prompt=f"""Generate JSON for schema `{schema_name}`.

Target: {target or "n/a"}

Source:
```text
{source_text[:9000] or "No source file provided."}
```
""",
        provider=provider,
        output_dir=output_dir,
        metadata={"schema_name": schema_name, "target": target, "source": _rel_str(source, root) if source else ""},
        dry_run_output=dry_payload,
    )
    validation = validate_agent_run(root, run_dir=run_result.run_dir, schema_name=schema_name)
    return AgentJsonBuildResult(root, run_result.run_dir, validation.validation_path, schema_name, validation.status)


def plan_agent_patch(
    project_root: Path,
    *,
    target: str,
    source: Path | None = None,
    provider: str = "auto",
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentPatchPlanResult:
    root = project_root.resolve()
    _validate_patch_target(target)
    safe = _slug(target)
    run_dir = root / "agents" / "patch_plans" / f"{safe}-{_stamp()}"
    result = build_agent_json(
        root,
        schema_name="json_patch_plan.v1",
        agent_id="json-patch-planner",
        task="plan-controlled-writeback",
        source=source,
        target=target,
        provider=provider,
        output_dir=run_dir,
    )
    parsed = json.loads((result.run_dir / "parsed_output.json").read_text(encoding="utf-8"))
    parsed["agent_run_dir"] = _rel_str(result.run_dir, root)
    parsed["schema_validation"] = _rel_str(result.validation_path, root)
    report_path = _resolve_output(root, output, "agents", "patch_plans", f"{safe}_patch_plan.md")
    json_path = _resolve_output(root, json_output, "agents", "patch_plans", f"{safe}_patch_plan.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_patch_plan(parsed, result.status), encoding="utf-8")
    return AgentPatchPlanResult(root, result.run_dir, report_path, json_path, result.validation_path, target, result.status)


def _dry_patch_payload(target: str, source: Path | None) -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/json-patch-plan-agent/v1",
        "target": target,
        "operation": "patch_plan",
        "approval_required": True,
        "changes": [
            {
                "path": target,
                "action": "propose",
                "reason": "dry-run records a controlled writeback candidate without changing the target file.",
            }
        ],
        "risks": ["Agent JSON is a candidate; schema pass is not human approval."],
        "source_paths": [str(source) if source else "manual"],
        "rollback_notes": "Do not apply automatically. Convert to a reviewed patch first.",
    }


def _validate_patch_target(target: str) -> None:
    normalized = target.replace("\\", "/").lstrip("/")
    if ".." in normalized or not normalized:
        raise ValueError("target must be a safe relative path")
    if not normalized.startswith(ALLOWED_PATCH_TARGET_PREFIXES):
        raise ValueError(f"target must start with one of: {', '.join(ALLOWED_PATCH_TARGET_PREFIXES)}")
    if normalized.startswith("canon/"):
        raise ValueError("agent patch plans cannot target canon/ directly")


def _render_patch_plan(payload: dict[str, object], validation_status: str) -> str:
    lines = [
        f"# Agent Patch Plan：{payload.get('target', '')}",
        "",
        f"- Operation：`{payload.get('operation', '')}`",
        f"- Approval Required：`{str(payload.get('approval_required', '')).lower()}`",
        f"- Schema：`{validation_status}`",
        f"- Agent Run：`{payload.get('agent_run_dir', '')}`",
        "",
        "## Changes",
        "",
    ]
    for item in payload.get("changes", []) or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Risks", ""])
    for item in payload.get("risks", []) or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _read_source(root: Path, source: Path | None) -> str:
    if source is None:
        return ""
    path = source if source.is_absolute() else root / source
    if not path.exists():
        raise FileNotFoundError(f"source not found: {path}")
    return path.read_text(encoding="utf-8")


def _resolve_output(root: Path, value: Path | None, *default_parts: str) -> Path:
    if value is None:
        return root.joinpath(*default_parts)
    return value if value.is_absolute() else root / value


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value.replace("\\", "/")).strip("-")[:80] or "patch"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _rel_str(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
