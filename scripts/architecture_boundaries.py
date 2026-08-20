"""Layer-boundary scanners used by the architecture debt ratchet."""

from __future__ import annotations

import ast
from pathlib import Path
import re
from typing import Any, Iterable


STUDIO_PACKAGE = "literary_engineering_studio"
ENGINE_PACKAGE = "literary_engineering_studio_engine"
_CLIENT_IMPORT = re.compile(
    r"(?:\bfrom\s+|\bimport\s*\()\s*[\"'](?P<target>[^\"']+)[\"']"
)
_WRITE_APPLICATION_SEGMENTS = frozenset({"editing", "promotion", "transactions", "writeback"})


def imported_module_bases(source: str, tree: ast.AST) -> set[str]:
    """Return imported module paths without treating imported symbols as modules."""

    imports: set[str] = set()
    package = source.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            keep = max(0, len(package) - node.level + 1)
            prefix = package[:keep]
            if node.module:
                imports.add(".".join([*prefix, node.module]))
            else:
                imports.update(
                    ".".join([*prefix, alias.name])
                    for alias in node.names
                    if alias.name != "*"
                )
        elif node.module:
            imports.add(node.module)
    return {item for item in imports if item}


def boundary_dependency_reason(source: str, target: str) -> str:
    """Return a zero-tolerance layered-dependency violation, if any."""

    if source.startswith(f"{STUDIO_PACKAGE}.projections.") and target.startswith(
        f"{STUDIO_PACKAGE}.application."
    ):
        segments = set(target.split("."))
        if segments & _WRITE_APPLICATION_SEGMENTS:
            return "projections must not import application write services"
    if source.startswith((f"{STUDIO_PACKAGE}.runtime.", f"{STUDIO_PACKAGE}.runtimes.")) and target.startswith(
        f"{ENGINE_PACKAGE}.routes."
    ):
        return "Runtime adapters must not import Engine route implementations"
    return ""


def application_adapter_dependencies(
    root: Path,
    parsed: dict[Path, ast.AST],
) -> dict[str, list[str]]:
    """Record application-to-interface/concrete-adapter debt pending M1."""

    source_root = root / "src"
    result: dict[str, list[str]] = {}
    for path, tree in sorted(parsed.items()):
        if not path.is_relative_to(source_root):
            continue
        source = _module_name(path, source_root)
        if not source.startswith(f"{STUDIO_PACKAGE}.application."):
            continue
        dependencies = sorted(
            target
            for target in imported_module_bases(source, tree)
            if _is_application_adapter_target(target)
        )
        if dependencies:
            result[path.relative_to(root).as_posix()] = dependencies
    return result


def studio_engine_dependencies(
    root: Path,
    parsed: dict[Path, ast.AST],
) -> dict[str, list[str]]:
    """Record Studio imports that bypass the Engine public API."""

    source_root = root / "src"
    result: dict[str, list[str]] = {}
    for path, tree in sorted(parsed.items()):
        if not path.is_relative_to(source_root):
            continue
        source = _module_name(path, source_root)
        if not source.startswith(f"{STUDIO_PACKAGE}."):
            continue
        dependencies = sorted(
            target
            for target in imported_module_bases(source, tree)
            if _is_engine_internal_target(target)
        )
        if dependencies:
            result[path.relative_to(root).as_posix()] = dependencies
    return result


def _is_engine_internal_target(target: str) -> bool:
    if not (target == ENGINE_PACKAGE or target.startswith(f"{ENGINE_PACKAGE}.")):
        return False
    return not (
        target == f"{ENGINE_PACKAGE}.public"
        or target.startswith(f"{ENGINE_PACKAGE}.public.")
    )


def projection_application_dependencies(
    root: Path,
    parsed: dict[Path, ast.AST],
) -> dict[str, list[str]]:
    """Record projection-to-application coupling pending read-port migration."""

    source_root = root / "src"
    result: dict[str, list[str]] = {}
    for path, tree in sorted(parsed.items()):
        if not path.is_relative_to(source_root):
            continue
        source = _module_name(path, source_root)
        if not source.startswith(f"{STUDIO_PACKAGE}.projections."):
            continue
        dependencies = sorted(
            target
            for target in imported_module_bases(source, tree)
            if target.startswith(f"{STUDIO_PACKAGE}.application.")
        )
        if dependencies:
            result[path.relative_to(root).as_posix()] = dependencies
    return result


def client_cross_feature_component_dependencies(root: Path) -> dict[str, list[str]]:
    """Record Vue component imports that cross frontend feature ownership."""

    features_root = root / "client" / "src" / "features"
    if not features_root.is_dir():
        return {}
    result: dict[str, list[str]] = {}
    paths = [*features_root.rglob("*.ts"), *features_root.rglob("*.vue")]
    for path in sorted(set(paths)):
        relative = path.relative_to(features_root)
        if len(relative.parts) < 2:
            continue
        owner = relative.parts[0]
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        dependencies: set[str] = set()
        for match in _CLIENT_IMPORT.finditer(source):
            target = match.group("target")
            if not target.endswith(".vue"):
                continue
            target_owner = _client_feature_owner(path, features_root, target)
            if target_owner and target_owner != owner:
                dependencies.add(target)
        if dependencies:
            result[path.relative_to(root).as_posix()] = sorted(dependencies)
    return result


def compare_dependency_map(
    label: str,
    current: dict[str, list[str]],
    allowed: dict[str, list[str]],
) -> list[str]:
    """Reject new paths or targets while allowing existing debt to shrink."""

    violations: list[str] = []
    for owner, dependencies in current.items():
        new_dependencies = sorted(set(dependencies) - set(allowed.get(owner) or []))
        if new_dependencies:
            violations.append(f"{label}: {owner}: {', '.join(new_dependencies)}")
    return violations


def _client_feature_owner(path: Path, features_root: Path, target: str) -> str:
    if target.startswith("@/features/"):
        parts = target.removeprefix("@/features/").split("/")
        return parts[0] if parts else ""
    if not target.startswith("."):
        return ""
    resolved = (path.parent / target).resolve()
    try:
        relative = resolved.relative_to(features_root.resolve())
    except ValueError:
        return ""
    return relative.parts[0] if relative.parts else ""


def _is_application_adapter_target(target: str) -> bool:
    if (
        target == f"{STUDIO_PACKAGE}.api"
        or target.startswith(f"{STUDIO_PACKAGE}.api.")
        or target == f"{STUDIO_PACKAGE}.api_server"
    ):
        return True
    return target.startswith(f"{STUDIO_PACKAGE}.runtimes.")


def _module_name(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


__all__ = [
    "application_adapter_dependencies",
    "boundary_dependency_reason",
    "client_cross_feature_component_dependencies",
    "compare_dependency_map",
    "imported_module_bases",
    "projection_application_dependencies",
    "studio_engine_dependencies",
]
