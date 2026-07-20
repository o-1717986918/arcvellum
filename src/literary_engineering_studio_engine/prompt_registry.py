"""File-backed prompt asset registry for CLI-mediated platform-agent tasks."""

from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import json
from pathlib import Path
import re

from .resources import engine_root


PROMPT_ASSET_SCHEMA = "literary-engineering-workbench/prompt-asset/v1"
REQUIRED_FIELDS = {
    "schema",
    "prompt_asset_id",
    "version",
    "route",
    "task_type",
    "required_inputs",
    "context_groups",
    "hard_constraints",
    "output_contract",
    "review_requirements",
    "forbidden_shortcuts",
}
LIST_FIELDS = {
    "required_inputs",
    "optional_inputs",
    "context_groups",
    "hard_constraints",
    "style_constraints",
    "output_contract",
    "review_requirements",
    "forbidden_shortcuts",
}


@dataclass(frozen=True)
class PromptAsset:
    path: Path
    metadata: dict[str, object]
    body: str

    @property
    def prompt_asset_id(self) -> str:
        return str(self.metadata.get("prompt_asset_id") or "")

    @property
    def match(self) -> str:
        return str(self.metadata.get("match") or self.prompt_asset_id)

    @property
    def route(self) -> str:
        return str(self.metadata.get("route") or "")

    @property
    def version(self) -> str:
        return str(self.metadata.get("version") or "")

    @property
    def title(self) -> str:
        title = str(self.metadata.get("title") or "")
        if title:
            return title
        first_heading = next((line[2:].strip() for line in self.body.splitlines() if line.startswith("# ")), "")
        return first_heading or self.prompt_asset_id

    @property
    def is_wildcard(self) -> bool:
        return "*" in self.match or "?" in self.match

    def to_dict(self, skill_root: Path) -> dict[str, object]:
        payload = dict(self.metadata)
        payload["path"] = _rel(self.path, skill_root)
        payload["title"] = self.title
        payload["body_chars"] = len(self.body.strip())
        payload["wildcard"] = self.is_wildcard
        return payload


@dataclass(frozen=True)
class PromptRegistryValidation:
    skill_root: Path
    assets: list[PromptAsset]
    task_prompt_ids: list[str]
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class PromptPreview:
    requested_id: str
    asset: PromptAsset | None
    skill_root: Path
    exact: bool
    message: str


def resolve_skill_root(skill_root: Path | str | None = None) -> Path:
    """Resolve the skill root that owns templates/prompt_assets."""

    if skill_root:
        root = Path(skill_root).resolve()
        if (root / "templates" / "prompt_assets").exists():
            return root
        raise FileNotFoundError(f"prompt asset directory not found under: {root}")

    root = engine_root()
    if (root / "templates" / "prompt_assets").exists():
        return root
    raise FileNotFoundError("embedded templates/prompt_assets are missing")


def list_prompt_assets(skill_root: Path | str | None = None) -> list[PromptAsset]:
    root = resolve_skill_root(skill_root)
    assets_dir = root / "templates" / "prompt_assets"
    assets = [_load_prompt_asset(path) for path in sorted(assets_dir.glob("*.md"))]
    return sorted(assets, key=lambda item: (item.route, item.prompt_asset_id, item.match))


def resolve_prompt_asset(prompt_asset_id: str, skill_root: Path | str | None = None) -> PromptPreview:
    root = resolve_skill_root(skill_root)
    assets = list_prompt_assets(root)
    exact = next((asset for asset in assets if asset.prompt_asset_id == prompt_asset_id and not asset.is_wildcard), None)
    if exact:
        return PromptPreview(prompt_asset_id, exact, root, True, "exact prompt asset")

    matches = [asset for asset in assets if fnmatch.fnmatchcase(prompt_asset_id, asset.match)]
    if matches:
        matches.sort(key=lambda asset: len(asset.match.replace("*", "")), reverse=True)
        return PromptPreview(prompt_asset_id, matches[0], root, False, f"matched wildcard {matches[0].match}")

    return PromptPreview(prompt_asset_id, None, root, False, "missing prompt asset")


def validate_prompt_registry(skill_root: Path | str | None = None, *, include_task_registry: bool = True) -> PromptRegistryValidation:
    root = resolve_skill_root(skill_root)
    assets = list_prompt_assets(root)
    errors: list[str] = []
    warnings: list[str] = []
    seen_exact: dict[str, Path] = {}

    for asset in assets:
        rel = _rel(asset.path, root)
        missing = sorted(REQUIRED_FIELDS - set(asset.metadata))
        if missing:
            errors.append(f"{rel}: missing fields: {', '.join(missing)}")
        if asset.metadata.get("schema") != PROMPT_ASSET_SCHEMA:
            errors.append(f"{rel}: schema must be {PROMPT_ASSET_SCHEMA}")
        if not asset.prompt_asset_id:
            errors.append(f"{rel}: prompt_asset_id is empty")
        elif not asset.is_wildcard:
            previous = seen_exact.get(asset.prompt_asset_id)
            if previous:
                errors.append(f"{rel}: duplicate exact prompt_asset_id already defined in {_rel(previous, root)}")
            seen_exact[asset.prompt_asset_id] = asset.path
        if not asset.body.strip():
            errors.append(f"{rel}: body is empty")
        for field in LIST_FIELDS:
            if field in asset.metadata and not isinstance(asset.metadata[field], list):
                errors.append(f"{rel}: {field} must be a list")
        if asset.version and not str(asset.version).startswith("v"):
            warnings.append(f"{rel}: version should use v-prefixed semantic form, got {asset.version}")

    task_ids = _task_registry_prompt_ids(root) if include_task_registry else []
    for prompt_id in task_ids:
        preview = resolve_prompt_asset(prompt_id, root)
        if preview.asset is None:
            errors.append(f"task_registry prompt_asset_id has no registered asset: {prompt_id}")

    return PromptRegistryValidation(root, assets, task_ids, errors, warnings)


def render_prompt_registry_list(skill_root: Path | str | None = None) -> str:
    root = resolve_skill_root(skill_root)
    assets = list_prompt_assets(root)
    lines = ["# Prompt Registry", "", f"- skill_root: `{root}`", f"- assets: `{len(assets)}`", ""]
    lines.append("| prompt_asset_id | match | route | version | path |")
    lines.append("| --- | --- | --- | --- | --- |")
    for asset in assets:
        lines.append(
            f"| `{asset.prompt_asset_id}` | `{asset.match}` | `{asset.route}` | `{asset.version}` | `{_rel(asset.path, root)}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_prompt_registry_validation(validation: PromptRegistryValidation) -> str:
    lines = [
        "# Prompt Registry Validation",
        "",
        f"- skill_root: `{validation.skill_root}`",
        f"- assets: `{len(validation.assets)}`",
        f"- task_prompt_ids: `{len(validation.task_prompt_ids)}`",
        f"- status: `{'pass' if validation.ok else 'fail'}`",
        "",
        "## Errors",
        "",
    ]
    if validation.errors:
        lines.extend(f"- {item}" for item in validation.errors)
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    if validation.warnings:
        lines.extend(f"- {item}" for item in validation.warnings)
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def render_prompt_preview(preview: PromptPreview) -> str:
    lines = ["# Prompt Asset Preview", "", f"- requested_id: `{preview.requested_id}`", f"- status: `{preview.message}`"]
    if preview.asset is None:
        lines.extend(["", "No registered prompt asset matched this id."])
        return "\n".join(lines).rstrip() + "\n"

    asset = preview.asset
    lines.extend(
        [
            f"- resolved_id: `{asset.prompt_asset_id}`",
            f"- match: `{asset.match}`",
            f"- exact: `{str(preview.exact).lower()}`",
            f"- route: `{asset.route}`",
            f"- version: `{asset.version}`",
            f"- path: `{_rel(asset.path, preview.skill_root)}`",
            "",
            "## Output Contract",
            "",
        ]
    )
    for item in asset.metadata.get("output_contract") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Prompt Body", "", asset.body.strip()])
    return "\n".join(lines).rstrip() + "\n"


def _load_prompt_asset(path: Path) -> PromptAsset:
    text = path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(text)
    return PromptAsset(path=path, metadata=metadata, body=body.strip())


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized
    end = normalized.find("\n---\n", 4)
    if end < 0:
        return {}, normalized
    raw_meta = normalized[4:end]
    body = normalized[end + len("\n---\n") :]
    return _parse_simple_yaml(raw_meta), body


def _parse_simple_yaml(raw: str) -> dict[str, object]:
    data: dict[str, object] = {}
    current_key = ""
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_key:
            value = _parse_scalar(stripped[2:].strip())
            current = data.setdefault(current_key, [])
            if isinstance(current, list):
                current.append(value)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if value:
            data[key] = _parse_scalar(value)
        else:
            data[key] = []
    return data


def _parse_scalar(value: str) -> object:
    value = value.strip()
    if not value:
        return ""
    if value[0:1] in {"'", '"'} and value[-1:] == value[0]:
        return value[1:-1]
    if value in {"true", "false"}:
        return value == "true"
    return value


def _task_registry_prompt_ids(root: Path) -> list[str]:
    candidates = [
        root / "src" / "literary_engineering_studio_engine" / "task_registry.py",
        root / "scripts" / "literary_engineering_studio_engine" / "task_registry.py",
        Path(__file__).resolve().parent / "task_registry.py",
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        return []
    text = path.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'"prompt_asset_id"\s*:\s*"([^"]+)"', text)))


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
