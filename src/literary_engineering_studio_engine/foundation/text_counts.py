"""Shared text-counting units for Chinese long-form prose contracts."""

from __future__ import annotations

import re

CHINESE_CONTENT_CHAR_RE = re.compile(
    "["
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uf900-\ufaff"
    "\U00020000-\U0002a6df"
    "\U0002a700-\U0002b73f"
    "\U0002b740-\U0002b81f"
    "\U0002b820-\U0002ceaf"
    "\U0002ceb0-\U0002ebef"
    "\u3001-\u303f"
    "\ufe10-\ufe1f"
    "\ufe30-\ufe4f"
    "\uff01-\uff0f"
    "\uff1a-\uff20"
    "\uff3b-\uff40"
    "\uff5b-\uff65"
    "\u2018-\u201d"
    "\u2014"
    "\u2026"
    "\u00b7"
    "]"
)

CHINESE_CONTENT_COUNT_UNIT = "chinese_content_chars_including_chinese_punctuation"
MACHINE_NONSPACE_COUNT_UNIT = "machine_nonspace_chars"


def count_chinese_content_chars(text: str) -> int:
    """Count Chinese prose characters: Han characters plus Chinese punctuation."""

    return len(CHINESE_CONTENT_CHAR_RE.findall(text or ""))


def count_nonspace_chars(text: str) -> int:
    """Count all non-whitespace characters as a machine diagnostic unit."""

    return len(re.sub(r"\s+", "", text or ""))


def chinese_machine_count_mapping(text: str, *, target_chinese_chars: int = 0) -> dict[str, object]:
    """Return a rough bridge between Chinese target counts and machine counts."""

    chinese_chars = count_chinese_content_chars(text)
    machine_chars = count_nonspace_chars(text)
    ratio = round(machine_chars / chinese_chars, 3) if chinese_chars else 0.0
    expected_machine_chars = round(target_chinese_chars * (ratio or 1.0)) if target_chinese_chars else 0
    expected_low = round(expected_machine_chars * 0.95) if target_chinese_chars else 0
    expected_high = round(expected_machine_chars * 1.05) if target_chinese_chars else 0
    expected_machine_range = [min(expected_low, expected_high), max(expected_low, expected_high)]
    baseline_machine_range = (
        [round(target_chinese_chars * 0.95), round(target_chinese_chars * 1.15)]
        if target_chinese_chars
        else [0, 0]
    )
    delta = machine_chars - chinese_chars
    warning = ""
    if chinese_chars and ratio >= 1.15:
        warning = "machine_count_inflated_by_non_chinese_or_workbench_content"
    elif chinese_chars and ratio <= 0.85:
        warning = "machine_count_lower_than_chinese_content_unusual"
    return {
        "target_unit": CHINESE_CONTENT_COUNT_UNIT,
        "machine_unit": MACHINE_NONSPACE_COUNT_UNIT,
        "chinese_content_chars": chinese_chars,
        "machine_nonspace_chars": machine_chars,
        "machine_to_chinese_ratio": ratio,
        "machine_minus_chinese_chars": delta,
        "diagnostic_warning": warning,
        "target_chinese_chars": int(target_chinese_chars or 0),
        "rough_expected_machine_chars": expected_machine_chars,
        "rough_expected_machine_chars_range": expected_machine_range,
        "baseline_machine_chars_1_to_1_range": baseline_machine_range,
        "mapping_basis": "current_text_observed_machine_to_chinese_ratio" if ratio else "baseline_1_to_1",
        "note": (
            "Formal gates compare Chinese content characters, including Chinese punctuation. "
            "Machine nonspace characters are diagnostic only. rough_expected_machine_chars is mapped "
            "from the current cleaned text ratio when text exists; baseline_machine_chars_1_to_1_range "
            "is a simple Chinese-prose baseline. Inspect large gaps for markdown traces, ASCII labels, "
            "paths, or mixed-language fragments."
        ),
    }
