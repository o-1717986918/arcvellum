"""Content-safe metrics for rendered Agent prompts."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import math
import re


_AUTHORIZED_FILE = re.compile(
    r"^-{5} BEGIN AUTHORIZED FILE: `(?P<path>[^`]+)` "
    r"\(sha256=(?P<digest>[0-9a-f]{64}), characters=(?P<characters>\d+)\) -{5}$",
    re.MULTILINE,
)
_AUTHORIZED_BLOCK = re.compile(
    r"^-{5} BEGIN AUTHORIZED FILE: `(?P<path>[^`]+)` "
    r"\(sha256=[0-9a-f]{64}, characters=\d+\) -{5}\n"
    r"(?P<body>.*?)"
    r"^-{5} END AUTHORIZED FILE: `(?P=path)` -{5}$",
    re.MULTILINE | re.DOTALL,
)
_CONSTRAINT_WORDS = ("必须", "不得", "禁止", "只允许", "不允许", "must", "forbidden")


@dataclass(frozen=True)
class PromptMetrics:
    schema: str
    total_characters: int
    estimated_input_tokens: int
    instruction_characters: int
    evidence_characters: int
    unique_source_count: int
    source_occurrence_count: int
    duplicate_path_count: int
    duplicate_digest_count: int
    duplicate_paragraph_characters: int
    nested_duplicate_characters: int
    duplicate_character_ratio: float
    constraint_count: int
    repeated_constraint_count: int
    constraint_repetition_ratio: float
    exact_on_demand_count: int
    prompt_sha256: str

    def safe_projection(self) -> dict[str, object]:
        return asdict(self)


def measure_prompt(text: str) -> PromptMetrics:
    """Measure a rendered prompt without retaining any prompt content."""

    normalized = text.replace("\r\n", "\n")
    sources = list(_AUTHORIZED_FILE.finditer(normalized))
    source_blocks = list(_AUTHORIZED_BLOCK.finditer(normalized))
    source_paths = [item.group("path") for item in sources]
    source_digests = [item.group("digest") for item in sources]
    evidence_characters = sum(len(item.group(0)) for item in source_blocks)
    duplicate_paragraph_characters = _duplicate_paragraph_characters(normalized)
    nested_duplicate_characters = _nested_duplicate_characters(source_blocks)
    duplicate_characters = min(
        len(normalized), duplicate_paragraph_characters + nested_duplicate_characters
    )
    constraint_lines = _constraint_lines(normalized)
    repeated_constraints = sum(count - 1 for count in Counter(constraint_lines).values() if count > 1)
    total_characters = len(normalized)
    return PromptMetrics(
        schema="arcvellum/prompt-metrics/v1",
        total_characters=total_characters,
        estimated_input_tokens=_estimate_tokens(normalized),
        instruction_characters=max(0, total_characters - evidence_characters),
        evidence_characters=evidence_characters,
        unique_source_count=len(set(source_paths)),
        source_occurrence_count=len(source_paths),
        duplicate_path_count=_duplicate_count(source_paths),
        duplicate_digest_count=_duplicate_count(source_digests),
        duplicate_paragraph_characters=duplicate_paragraph_characters,
        nested_duplicate_characters=nested_duplicate_characters,
        duplicate_character_ratio=_ratio(duplicate_characters, total_characters),
        constraint_count=len(constraint_lines),
        repeated_constraint_count=repeated_constraints,
        constraint_repetition_ratio=_ratio(repeated_constraints, len(constraint_lines)),
        exact_on_demand_count=_exact_on_demand_count(normalized),
        prompt_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )


def _estimate_tokens(text: str) -> int:
    # This is a stable comparison estimate, not a provider tokenizer claim.
    han = sum("\u4e00" <= character <= "\u9fff" for character in text)
    remaining = max(0, len(text) - han)
    return max(1, han + math.ceil(remaining / 4)) if text else 0


def _duplicate_count(values: list[str]) -> int:
    return sum(count - 1 for count in Counter(values).values() if count > 1)


def _duplicate_paragraph_characters(text: str) -> int:
    paragraphs = [_normalize_paragraph(value) for value in re.split(r"\n\s*\n", text)]
    eligible = [value for value in paragraphs if len(value) >= 80 and not value.startswith("-----")]
    return sum(len(value) * (count - 1) for value, count in Counter(eligible).items() if count > 1)


def _nested_duplicate_characters(source_blocks: list[re.Match[str]], window: int = 96) -> int:
    """Estimate content repeated across different authorized files.

    Whitespace-free rolling windows catch an exact source nested inside a
    context packet even when Markdown indentation differs. Matches within the
    same source are intentionally ignored.
    """

    seen_windows: set[str] = set()
    duplicated = 0
    for source in source_blocks:
        body = re.sub(r"\s+", "", source.group("body")).casefold()
        if len(body) < window:
            continue
        matched = bytearray(len(body))
        for index in range(len(body) - window + 1):
            fragment = body[index : index + window]
            if fragment in seen_windows:
                matched[index : index + window] = b"\x01" * window
        duplicated += sum(matched)
        seen_windows.update(
            body[index : index + window] for index in range(len(body) - window + 1)
        )
    return duplicated


def _normalize_paragraph(value: str) -> str:
    return " ".join(value.split()).strip().casefold()


def _constraint_lines(text: str) -> list[str]:
    rows: list[str] = []
    for line in text.splitlines():
        normalized = " ".join(line.split()).strip().casefold()
        if len(normalized) < 8:
            continue
        if any(word in normalized for word in _CONSTRAINT_WORDS):
            rows.append(normalized)
    return rows


def _exact_on_demand_count(text: str) -> int:
    match = re.search(
        r"^### Exact On Demand\s*$\n(?P<body>.*?)(?=^### |^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return 0
    return sum(line.lstrip().startswith("-") for line in match.group("body").splitlines())


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)
