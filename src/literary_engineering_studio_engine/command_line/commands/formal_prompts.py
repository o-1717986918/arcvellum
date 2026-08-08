"""Formal Prompt Registry command handlers."""

from __future__ import annotations

import json
from pathlib import Path

from ...prompt_registry import (
    list_prompt_assets,
    render_prompt_preview,
    render_prompt_registry_list,
    render_prompt_registry_validation,
    resolve_prompt_asset,
    resolve_skill_root,
    validate_prompt_registry,
)


def handle_prompt_registry_list(args, parser) -> int:
    try:
        skill_root = Path(args.skill_root) if args.skill_root else None
        if args.json:
            root = resolve_skill_root(skill_root)
            assets = list_prompt_assets(root)
            print(
                json.dumps(
                    [asset.to_dict(root) for asset in assets],
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(render_prompt_registry_list(skill_root), end="")
    except FileNotFoundError as exc:
        parser.error(str(exc))
    return 0


def handle_prompt_registry_validate(args, parser) -> int:
    try:
        skill_root = Path(args.skill_root) if args.skill_root else None
        result = validate_prompt_registry(
            skill_root,
            include_task_registry=not args.no_task_registry,
        )
        if args.json:
            print(json.dumps(_validation_payload(result), ensure_ascii=False, indent=2))
        else:
            print(render_prompt_registry_validation(result), end="")
        return 0 if result.ok else 1
    except FileNotFoundError as exc:
        parser.error(str(exc))


def _validation_payload(result) -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/prompt-registry-validation/v0.1",
        "skill_root": str(result.skill_root),
        "status": "pass" if result.ok else "fail",
        "asset_count": len(result.assets),
        "task_prompt_id_count": len(result.task_prompt_ids),
        "errors": result.errors,
        "warnings": result.warnings,
    }


def handle_prompt_preview(args, parser) -> int:
    try:
        skill_root = Path(args.skill_root) if args.skill_root else None
        result = resolve_prompt_asset(args.prompt_asset_id, skill_root)
        if args.json:
            print(json.dumps(_preview_payload(result), ensure_ascii=False, indent=2))
        else:
            print(render_prompt_preview(result), end="")
        return 0 if result.asset is not None else 1
    except FileNotFoundError as exc:
        parser.error(str(exc))


def _preview_payload(result) -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/prompt-preview/v0.1",
        "requested_id": result.requested_id,
        "status": result.message,
        "exact": result.exact,
        "asset": result.asset.to_dict(result.skill_root) if result.asset else None,
        "body": result.asset.body if result.asset else "",
    }


HANDLERS = {
    "prompt-registry-list": handle_prompt_registry_list,
    "prompt-registry-validate": handle_prompt_registry_validate,
    "prompt-preview": handle_prompt_preview,
}
