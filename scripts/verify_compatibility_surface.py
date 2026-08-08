from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


ALIAS_MARKERS = (
    "Compatibility alias",
    "Compatibility shim",
    "Compatibility wrapper",
)
ENGINE_PACKAGE = "literary_engineering_studio_engine"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ArcVellum compatibility and production defaults.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors = audit(root)
    if errors:
        for error in errors:
            print(f"compatibility surface: fail: {error}")
        return 1
    print("compatibility surface: pass")
    return 0


def audit(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "src" / "literary_engineering_studio" / "application" / "compatibility_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"manifest cannot be read: {exc}"]
    if manifest.get("schema") != "arcvellum/compatibility-manifest/v1":
        errors.append("manifest schema is invalid")
    defaults = manifest.get("runtime_defaults") or {}
    if defaults.get("model_invocation") != "runner-managed":
        errors.append("model invocation default is not runner-managed")
    if defaults.get("scene_generation") != "platform-agent-task":
        errors.append("scene generation default is not platform-agent-task")
    alias_modules = _discover_alias_modules(root)
    errors.extend(_studio_alias_import_errors(root, alias_modules))
    errors.extend(_formal_scene_command_errors(root))
    package_config = (root / "pyproject.toml").read_text(encoding="utf-8")
    if '"application/*.json"' not in package_config:
        errors.append("compatibility manifest is not included in package data")
    for item in manifest.get("deprecated_aliases") or []:
        canonical = str(item.get("canonical_module") or "")
        if not canonical or not _module_path(root, canonical).exists():
            errors.append(f"canonical module is missing: {canonical or '<empty>'}")
    return errors


def _discover_alias_modules(root: Path) -> set[str]:
    package = root / "src" / ENGINE_PACKAGE
    aliases: set[str] = set()
    for path in package.glob("*.py"):
        head = path.read_text(encoding="utf-8")[:240]
        if any(marker in head for marker in ALIAS_MARKERS):
            aliases.add(f"{ENGINE_PACKAGE}.{path.stem}")
    return aliases


def _studio_alias_import_errors(root: Path, aliases: set[str]) -> list[str]:
    source = root / "src" / "literary_engineering_studio"
    errors: list[str] = []
    for path in source.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            errors.append(f"cannot inspect {path.relative_to(root)}: {exc}")
            continue
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            for module in modules:
                if module in aliases:
                    errors.append(
                        f"Studio imports deprecated alias {module}: {path.relative_to(root)}:{node.lineno}"
                    )
    return errors


def _formal_scene_command_errors(root: Path) -> list[str]:
    path = root / "src" / ENGINE_PACKAGE / "command_line" / "commands" / "scene_prose.py"
    source = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if "write_platform_scene_generation_task" not in source:
        errors.append("formal scene command no longer writes a platform-agent task")
    if "generation_provider" in source or "HttpChatProvider" in source:
        errors.append("formal scene command imports the legacy direct generation provider")
    if 'provider="platform-agent"' not in source:
        errors.append("formal scene prompt manifest is not bound to platform-agent")
    return errors


def _module_path(root: Path, module: str) -> Path:
    parts = module.split(".")
    return root / "src" / Path(*parts).with_suffix(".py")


if __name__ == "__main__":
    raise SystemExit(main())
