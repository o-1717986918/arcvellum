from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path


ENGINE_PACKAGE = "literary_engineering_studio_engine"
MANIFEST_SCHEMA = "arcvellum/compatibility-manifest/v2"
COMPATIBILITY_TEST_FILES = {
    "tests/test_compatibility_manifest.py",
    "tests/test_engine_api_route_surface.py",
    "tests/test_engine_cli_surface.py",
}
PYTHON_SCAN_DIRS = ("src", "tests", "scripts", "benchmarks")


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
    manifest_path = root / "src" / "literary_engineering_studio" / "application" / "compatibility_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"manifest cannot be read: {exc}"]

    errors: list[str] = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("manifest schema is invalid")
    current = _mapping(manifest.get("current_release"))
    defaults = _mapping(current.get("defaults"))
    compatibility = _mapping(manifest.get("compatibility"))
    if current.get("version") != _project_version(root):
        errors.append("compatibility manifest release version does not match pyproject.toml")
    if defaults.get("agent_runtime") != "pi-worker":
        errors.append("agent runtime default is not pi-worker")
    if defaults.get("model_invocation") != "runner-managed":
        errors.append("model invocation default is not runner-managed")
    if defaults.get("scene_generation") != "arcvellum-worker-task":
        errors.append("scene generation default is not arcvellum-worker-task")
    errors.extend(_runtime_default_errors(root))
    errors.extend(_history_errors(manifest))

    aliases = _records(compatibility.get("deprecated_aliases"))
    entrypoints = _records(compatibility.get("supported_entrypoints"))
    declared = {
        str(item.get("module") or "")
        for item in [*aliases, *entrypoints]
        if str(item.get("module") or "")
    }
    surfaces = _discover_facade_modules(root)
    missing = sorted(declared - set(surfaces))
    undeclared = sorted(set(surfaces) - declared)
    if missing:
        errors.append(f"declared compatibility modules are missing: {', '.join(missing)}")
    if undeclared:
        errors.append(f"undeclared compatibility modules remain: {', '.join(undeclared)}")

    budget = _mapping(compatibility.get("facade_budget"))
    maximum = _positive_int(budget.get("maximum_current_count"))
    previous = _positive_int(budget.get("previous_release_count"))
    if maximum is None or len(surfaces) > maximum:
        errors.append(f"compatibility facade budget exceeded: {len(surfaces)} > {maximum or 0}")
    if previous is None or len(surfaces) >= previous:
        errors.append("compatibility facade count did not decrease from the previous release")

    for item in [*aliases, *entrypoints]:
        module = str(item.get("module") or "")
        canonical = str(item.get("canonical_module") or "")
        if not canonical or not _module_exists(root, canonical):
            errors.append(f"canonical module is missing for {module or '<empty>'}: {canonical or '<empty>'}")
    for item in aliases:
        module = str(item.get("module") or "")
        path = surfaces.get(module)
        if item.get("status") != "deprecated" or not item.get("remove_not_before"):
            errors.append(f"deprecated alias lacks a bounded removal window: {module or '<empty>'}")
        if path is not None and "DeprecationWarning" not in path.read_text(encoding="utf-8"):
            errors.append(f"deprecated alias does not emit a warning: {module}")

    errors.extend(_facade_import_errors(root, set(surfaces)))
    errors.extend(_missing_engine_import_errors(root))
    errors.extend(_dynamic_engine_submodule_import_errors(root))
    errors.extend(_formal_scene_command_errors(root))
    package_config = (root / "pyproject.toml").read_text(encoding="utf-8")
    if '"application/*.json"' not in package_config:
        errors.append("compatibility manifest is not included in package data")
    return errors


def _discover_facade_modules(root: Path) -> dict[str, Path]:
    package = root / "src" / ENGINE_PACKAGE
    surfaces: dict[str, Path] = {}
    for path in package.glob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        docstring = (ast.get_docstring(tree) or "").lower()
        if "compatibility" in docstring or "facade" in docstring:
            surfaces[f"{ENGINE_PACKAGE}.{path.stem}"] = path
    return surfaces


def _facade_import_errors(root: Path, surfaces: set[str]) -> list[str]:
    errors: list[str] = []
    source_root = root / "src"
    scan_roots = tuple(root / name for name in PYTHON_SCAN_DIRS if (root / name).is_dir())
    for scan_root in scan_roots:
        for path in scan_root.rglob("*.py"):
            relative = path.relative_to(root).as_posix()
            if relative in COMPATIBILITY_TEST_FILES:
                continue
            module = _module_name(path, source_root) if path.is_relative_to(source_root) else ""
            if module in surfaces:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError) as exc:
                errors.append(f"cannot inspect {relative}: {exc}")
                continue
            for node in ast.walk(tree):
                for imported in _node_imports(module, path.name == "__init__.py", node):
                    surface = _matching_surface(imported, surfaces)
                    if surface:
                        errors.append(f"internal code imports compatibility facade {surface}: {relative}:{node.lineno}")
    return sorted(set(errors))


def _node_imports(module: str, is_package: bool, node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {item.name for item in node.names}
    if not isinstance(node, ast.ImportFrom):
        return set()
    base = _resolve_import_from(module, is_package, node)
    imports = {base} if base else set()
    if base:
        imports.update(f"{base}.{item.name}" for item in node.names if item.name != "*")
    return imports


def _resolve_import_from(module: str, is_package: bool, node: ast.ImportFrom) -> str:
    if not node.level:
        return str(node.module or "")
    if not module:
        return ""
    package = module if is_package else module.rpartition(".")[0]
    parts = package.split(".") if package else []
    keep = len(parts) - node.level + 1
    if keep < 0:
        return ""
    prefix = parts[:keep]
    if node.module:
        prefix.extend(node.module.split("."))
    return ".".join(prefix)


def _matching_surface(module: str, surfaces: set[str]) -> str:
    for surface in surfaces:
        if module == surface or module.startswith(f"{surface}."):
            return surface
    return ""


def _dynamic_engine_submodule_import_errors(root: Path) -> list[str]:
    """Reject runtime-selected Engine modules that can silently revive aliases."""

    errors: list[str] = []
    for path in (root / "src").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function = node.func
            is_import_module = (
                isinstance(function, ast.Name) and function.id == "import_module"
            ) or (
                isinstance(function, ast.Attribute) and function.attr == "import_module"
            )
            if not is_import_module or not isinstance(node.args[0], ast.JoinedStr):
                continue
            literal = "".join(
                str(item.value)
                for item in node.args[0].values
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            )
            if f"{ENGINE_PACKAGE}." in literal:
                relative = path.relative_to(root).as_posix()
                errors.append(
                    f"dynamic Engine submodule import bypasses the public API: {relative}:{node.lineno}"
                )
    return errors


def _missing_engine_import_errors(root: Path) -> list[str]:
    """Catch imports of removed top-level facades across shipped Python code."""

    package = root / "src" / ENGINE_PACKAGE
    errors: list[str] = []
    for directory in PYTHON_SCAN_DIRS:
        scan_root = root / directory
        if not scan_root.is_dir():
            continue
        for path in scan_root.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                for name in names:
                    prefix = f"{ENGINE_PACKAGE}."
                    if not name.startswith(prefix):
                        continue
                    top_level = name[len(prefix) :].split(".", 1)[0]
                    if (package / f"{top_level}.py").is_file() or (package / top_level).is_dir():
                        continue
                    relative = path.relative_to(root).as_posix()
                    errors.append(
                        f"Python source imports removed Engine module {name}: {relative}:{node.lineno}"
                    )
    return sorted(set(errors))


def _runtime_default_errors(root: Path) -> list[str]:
    path = root / "src" / "literary_engineering_studio" / "runtime" / "runtime_selection.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [f"runtime default cannot be inspected: {exc}"]
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "DEFAULT_CREATIVE_RUNTIME" for target in node.targets):
            if isinstance(node.value, ast.Constant) and node.value.value == "pi-worker":
                return []
    return ["runtime_selection.DEFAULT_CREATIVE_RUNTIME is not pi-worker"]


def _history_errors(manifest: dict[str, object]) -> list[str]:
    history = _mapping(manifest.get("history"))
    records = _records(history.get("runtime_defaults"))
    if not any(item.get("agent_runtime") == "opencode" and item.get("status") == "retired-default" for item in records):
        return ["historical OpenCode default is not recorded as retired"]
    if any(item.get("status") == "current" for item in records):
        return ["historical defaults must not declare a current runtime"]
    return []


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


def _project_version(root: Path) -> str:
    source = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', source, flags=re.MULTILINE)
    return match.group(1) if match else ""


def _module_name(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_exists(root: Path, module: str) -> bool:
    base = root / "src" / Path(*module.split("."))
    return base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _records(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


if __name__ == "__main__":
    raise SystemExit(main())
