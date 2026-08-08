"""Compact, deterministic prose obligations compiled from a composition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_SCHEMA = "literary-engineering-workbench/prose-execution-contract/v0.1"
OBLIGATION_KEYS = (
    "goal",
    "turn",
    "incoming_bridge",
    "outgoing_hook",
    "cost",
    "reader_effect",
    "word_target_hanzi",
)
BEAT_KEYS = (
    "beat_id",
    "function",
    "visible_action",
    "causal_change",
    "pace",
    "detail_level",
    "serves",
)


def build_prose_execution_contract(composition: dict[str, Any]) -> dict[str, Any]:
    """Project one composition into the exact obligations prose must execute."""

    branch = _mapping(composition.get("branch"))
    provenance = _mapping(composition.get("formal_cli_provenance"))
    scene_facts = _mapping(composition.get("scene_facts"))
    contract = {
        "schema": CONTRACT_SCHEMA,
        "scene_id": str(composition.get("scene_id") or ""),
        "selection": {
            "selected_branch": str(composition.get("selected_branch") or ""),
            "selection_source": str(composition.get("selection_source") or ""),
            "branch_origin": str(branch.get("branch_origin") or ""),
            "fallback_reason": str(branch.get("fallback_reason") or ""),
            "title": str(branch.get("title") or ""),
            "strategy": str(branch.get("strategy") or ""),
            "causal_premise": str(branch.get("causal_premise") or branch.get("premise") or ""),
            "action_chain": _string_list(branch.get("action_chain")),
        },
        "beats": [_beat_projection(item) for item in _mapping_list(composition.get("beats"))],
        "obligations": {
            key: _contract_value(_mapping(composition.get("composition_obligations")).get(key))
            for key in OBLIGATION_KEYS
        },
        "writeback_candidates": _mapping(composition.get("writeback_candidates")),
        "viewpoint": str(scene_facts.get("viewpoint") or ""),
        "input_contract_digest": str(provenance.get("input_contract_digest") or ""),
    }
    errors = prose_execution_contract_errors(contract)
    contract["status"] = "pass" if not errors else "incomplete"
    contract["errors"] = errors
    return contract


def prose_execution_contract_errors(contract: dict[str, Any]) -> list[str]:
    selection = _mapping(contract.get("selection"))
    obligations = _mapping(contract.get("obligations"))
    errors: list[str] = []
    for key in ("scene_id", "input_contract_digest"):
        if not str(contract.get(key) or "").strip():
            errors.append(f"missing {key}")
    errors.extend(_selection_errors(selection))
    errors.extend(_beat_errors(contract.get("beats")))
    errors.extend(
        f"missing obligations.{key}"
        for key in OBLIGATION_KEYS
        if not _meaningful(obligations.get(key))
    )
    return errors


def _selection_errors(selection: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("selected_branch", "selection_source", "branch_origin", "causal_premise"):
        if not str(selection.get(key) or "").strip():
            errors.append(f"missing selection.{key}")
    if selection.get("selection_source") != "selection":
        errors.append("selection.selection_source must be selection")
    if selection.get("branch_origin") == "deterministic-fallback" and not str(selection.get("fallback_reason") or "").strip():
        errors.append("selection.fallback_reason is required for deterministic fallback")
    if not _string_list(selection.get("action_chain")):
        errors.append("selection.action_chain must not be empty")
    return errors


def _beat_errors(value: Any) -> list[str]:
    beats = value if isinstance(value, list) else []
    if not isinstance(beats, list) or not 2 <= len(beats) <= 8:
        return ["beats must contain 2-8 items"]
    errors: list[str] = []
    covered: set[str] = set()
    for index, beat in enumerate(beats):
        item = _mapping(beat)
        errors.extend(
            f"beats[{index}].{key} is missing"
            for key in BEAT_KEYS
            if not _meaningful(item.get(key))
        )
        covered.update(_string_list(item.get("serves")))
    errors.extend(f"beats do not serve {key}" for key in OBLIGATION_KEYS[:-1] if key not in covered)
    return errors


def load_prose_execution_contract(path: Path) -> dict[str, Any]:
    """Load an exact composition contract and reject legacy/incomplete packets."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid composition execution contract source: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"composition must be a JSON object: {path}")
    contract = payload.get("prose_execution_contract")
    if not isinstance(contract, dict):
        raise ValueError(f"composition lacks prose_execution_contract; rerun compose-scene: {path}")
    errors = prose_execution_contract_errors(contract)
    if errors or contract.get("status") != "pass":
        detail = "; ".join(errors or _string_list(contract.get("errors")))
        raise ValueError(f"composition prose_execution_contract is incomplete: {detail}")
    return contract


def render_prose_execution_contract(contract: dict[str, Any]) -> str:
    """Render the compact machine contract without re-summarizing its content."""

    return "## 正文执行契约（由 composition JSON 确定性投影）\n\n```json\n" + json.dumps(
        contract,
        ensure_ascii=False,
        indent=2,
    ) + "\n```\n"


def _beat_projection(beat: dict[str, Any]) -> dict[str, Any]:
    return {key: _contract_value(beat.get(key)) for key in BEAT_KEYS}


def _contract_value(value: Any) -> Any:
    if isinstance(value, list):
        return _string_list(value)
    return value if isinstance(value, (int, float, bool)) else str(value or "")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _meaningful(value: Any) -> bool:
    if isinstance(value, list):
        return bool(_string_list(value))
    if isinstance(value, (int, float)):
        return value > 0
    return bool(str(value or "").strip())
