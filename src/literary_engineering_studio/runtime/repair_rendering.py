"""Bounded excerpts and prompts for one deterministic repair turn."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Mapping

from literary_engineering_studio_engine.public.prompting import render_prompt_template


MAX_EXCERPT_CHARACTERS = 1_200
MAX_TOTAL_EXCERPT_CHARACTERS = 6_000


def bounded_output_excerpt(
    path: Path,
    selectors: tuple[str, ...],
    limit: int,
) -> str:
    if limit <= 0 or not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    selected = _selected_json_excerpt(text, selectors)
    if selected:
        return _head_tail(selected, limit)
    if selectors:
        lowered = text.casefold()
        for selector in selectors:
            position = lowered.find(selector.casefold())
            if position >= 0:
                start = max(0, position - limit // 3)
                return _head_tail(text[start : start + limit], limit)
    return _head_tail(text, limit)


def render_repair_prompt(payload: Mapping[str, object]) -> str:
    issue_rows = _rows(payload.get("issues"))
    invalid_rows = _rows(payload.get("invalid_outputs"))
    protected_rows = _rows(payload.get("protected_outputs"))
    issue_text = "\n".join(
        (
            f"{index}. [{row.get('issue_id')}] "
            f"{row.get('code')} @ `{row.get('path')}`\n"
            f"   问题：{row.get('message')}\n"
            f"   修复要求：{row.get('repair')}"
        )
        for index, row in enumerate(issue_rows, start=1)
    )
    invalid_text = "\n".join(
        _render_invalid_output(row) for row in invalid_rows
    ) or render_prompt_template("formal.repair.invalid-empty.protocol", ()).strip()
    protected_text = "\n".join(
        (
            f"- `{row.get('path')}` "
            f"sha256={row.get('sha256') or 'missing'} "
            f"bytes={row.get('bytes') or 0}"
        )
        for row in protected_rows
    ) or "- 无。"
    targets = payload.get("repair_targets")
    target_rows = targets if isinstance(targets, list) else []
    target_text = "\n".join(
        f"- `{item}`" for item in target_rows
    ) or render_prompt_template("formal.repair.targets-empty.protocol", ()).strip()
    reasoning_text = _reasoning_budget_text(payload)
    quantitative_repair_text = _quantitative_repair_text(issue_rows, payload)
    regression_guard_text = _regression_guard_text(payload)
    stagnation_text = _stagnation_text(payload)
    semantic_contract_text = _semantic_contract_text(payload)
    session_layer = ("formal.repair.session-same.protocol" if payload.get("repair_session") == "same-session"
                     else "formal.repair.session-independent.protocol")
    session_text = render_prompt_template(session_layer, ()).strip()
    return render_prompt_template("formal.incremental-repair.protocol", (
        payload.get('attempt'),
        payload.get('maximum_attempts'),
        payload.get('context_digest'),
        session_text,
        target_text,
        payload.get('write_scope_mode'),
        issue_text,
        semantic_contract_text,
        reasoning_text,
        quantitative_repair_text,
        regression_guard_text,
        stagnation_text,
        invalid_text,
        protected_text,
    ))


def _semantic_contract_text(payload: Mapping[str, object]) -> str:
    raw = payload.get("semantic_output_contract")
    if not isinstance(raw, Mapping) or not raw:
        return ""
    return render_prompt_template("formal.repair.semantic-contract.protocol", (
        json.dumps(dict(raw), ensure_ascii=False, indent=2, sort_keys=True),
    ))


def _stagnation_text(payload: Mapping[str, object]) -> str:
    raw = payload.get("stagnation")
    stagnation = raw if isinstance(raw, Mapping) else {}
    if stagnation.get("active") is not True:
        return ""
    return render_prompt_template("formal.repair.stagnation.protocol", ())


def _quantitative_repair_text(
    issue_rows: list[Mapping[str, object]],
    payload: Mapping[str, object],
) -> str:
    length_issue = _length_shortfall(issue_rows)
    guard = payload.get("regression_guard")
    guard_row = guard if isinstance(guard, Mapping) else {}
    if length_issue is None:
        overage = _length_overage(issue_rows)
        if overage is None:
            return ""
        current, maximum = overage
        target = int(guard_row.get("word_count_target") or 0)
        minimum = int(guard_row.get("word_count_min") or 0)
        lower = max(minimum, target - 60) if target else minimum
        upper = min(maximum, target + 60) if target else max(0, maximum - 40)
        if upper < lower:
            lower, upper = minimum, maximum
        required_cut = max(1, current - upper)
        return render_prompt_template("formal.repair.quantitative-reduce.protocol", (
            current, maximum, required_cut, lower, upper,
        ))
    current, minimum = length_issue
    maximum = int(guard_row.get("word_count_max") or 0)
    gap = max(0, minimum - current)
    safe_gain = max(120, gap + 80)
    if maximum > current:
        safe_gain = min(safe_gain, max(gap, maximum - current - 20))
    safe_minimum = current + safe_gain
    return render_prompt_template("formal.repair.quantitative-increase.protocol", (
        current, minimum, gap, safe_gain, safe_minimum,
    ))


def _regression_guard_text(payload: Mapping[str, object]) -> str:
    raw = payload.get("regression_guard")
    guard = raw if isinstance(raw, Mapping) else {}
    if guard.get("active") is not True:
        return ""
    target = int(guard.get("word_count_target") or 0)
    minimum = int(guard.get("word_count_min") or 0)
    maximum = int(guard.get("word_count_max") or 0)
    range_text = (render_prompt_template("formal.repair.regression-range.protocol", (
        minimum, maximum, target,
    )).strip() if minimum and maximum else
        render_prompt_template("formal.repair.regression-budget.protocol", ()).strip())
    rules = guard.get("style_rules")
    rule_rows = rules if isinstance(rules, list) else []
    issues = _rows(payload.get("issues"))
    policy_layer = ("formal.repair.regression-increase.protocol" if _length_shortfall(issues) is not None
                    else "formal.repair.regression-replace.protocol")
    revision_policy = render_prompt_template(policy_layer, ()).strip()
    return render_prompt_template("formal.repair.regression-guard.protocol", (
        range_text, "；".join(str(item) for item in rule_rows), revision_policy,
    ))


def _length_shortfall(
    issue_rows: list[Mapping[str, object]],
) -> tuple[int, int] | None:
    length_codes = {"candidate-word-budget-invalid", "scene-revision-invalid"}
    patterns = (
        re.compile(r"清洁正文\s*(\d+)\D+最低要求\s*(\d+)"),
        re.compile(
            r"cleaned body has\s*(\d+)\s*Chinese content chars,\s*"
            r"below min_chinese_chars=(\d+)",
            re.IGNORECASE,
        ),
    )
    for row in issue_rows:
        if str(row.get("code") or "") not in length_codes:
            continue
        message = str(row.get("message") or "")
        for pattern in patterns:
            match = pattern.search(message)
            if match:
                current, minimum = (int(value) for value in match.groups())
                return current, minimum
    return None


def _length_overage(
    issue_rows: list[Mapping[str, object]],
) -> tuple[int, int] | None:
    length_codes = {"candidate-word-budget-invalid", "scene-revision-invalid"}
    patterns = (
        re.compile(r"清洁正文\s*(\d+)\D+最高要求\s*(\d+)"),
        re.compile(
            r"cleaned body has\s*(\d+)\s*Chinese content chars,\s*"
            r"above max_chinese_chars=(\d+)",
            re.IGNORECASE,
        ),
    )
    for row in issue_rows:
        if str(row.get("code") or "") not in length_codes:
            continue
        message = str(row.get("message") or "")
        for pattern in patterns:
            match = pattern.search(message)
            if match:
                current, maximum = (int(value) for value in match.groups())
                return current, maximum
    return None


def _reasoning_budget_text(payload: Mapping[str, object]) -> str:
    budgets = payload.get("budgets")
    budget_rows = budgets if isinstance(budgets, Mapping) else {}
    reasoning = budget_rows.get("reasoning")
    row = reasoning if isinstance(reasoning, Mapping) else {}
    return render_prompt_template("formal.repair.reasoning-budget.protocol", (
        row.get("action") or "keep", row.get("level") or "unchanged",
        row.get("maximum_level") or "unavailable", row.get("reason") or "unavailable",
    ))


def _selected_json_excerpt(
    text: str,
    selectors: tuple[str, ...],
) -> str:
    if not selectors:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    selected: dict[str, object] = {}
    for selector in selectors:
        found, value = _select_value(payload, selector)
        if found:
            selected[selector] = value
    if not selected:
        return ""
    return json.dumps(
        selected,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _select_value(
    payload: object,
    selector: str,
) -> tuple[bool, object]:
    current = payload
    segments = _selector_segments(selector)
    for segment in segments:
        if isinstance(segment, int) and isinstance(current, list):
            if segment < 0 or segment >= len(current):
                return False, None
            current = current[segment]
            continue
        if isinstance(segment, str) and isinstance(current, Mapping) and segment in current:
            current = current[segment]
            continue
        return False, None
    return True, current


def _selector_segments(selector: str) -> list[str | int]:
    normalized = selector.replace("/", ".")
    segments: list[str | int] = []
    for key, index in re.findall(r"(?:^|\.)([^.\[\]]+)|\[(\d+)\]", normalized):
        segments.append(int(index) if index else key)
    return segments


def _head_tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    marker = "\n...[bounded repair excerpt]...\n"
    usable = max(0, limit - len(marker))
    head = max(1, usable * 2 // 3)
    tail = max(0, usable - head)
    return text[:head] + marker + (text[-tail:] if tail else "")


def _rows(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _render_invalid_output(row: Mapping[str, object]) -> str:
    excerpt = str(row.get("excerpt") or "")
    return (
        f"- `{row.get('path')}` status={row.get('status')} "
        f"sha256={row.get('sha256') or 'missing'} "
        f"selectors={json.dumps(row.get('selectors') or [], ensure_ascii=False)}\n"
        f"  excerpt_json={json.dumps(excerpt, ensure_ascii=False)}"
    )


__all__ = [
    "MAX_EXCERPT_CHARACTERS",
    "MAX_TOTAL_EXCERPT_CHARACTERS",
    "bounded_output_excerpt",
    "render_repair_prompt",
]
