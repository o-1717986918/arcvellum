"""Freeze existing architecture debt while rejecting new or expanded debt."""

from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "arcvellum/architecture-quality-baseline/v1"
PYTHON_FILE_LINE_BUDGET = 500
CLIENT_FILE_LINE_BUDGET = 500
FUNCTION_LINE_BUDGET = 80
FUNCTION_COMPLEXITY_BUDGET = 15
SOURCE_DIRS = ("src/literary_engineering_studio", "src/literary_engineering_studio_engine")


def audit_repository(repository_root: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    python_files = _python_files(root)
    modules = {
        _module_name(path, root / "src"): path
        for path in python_files
        if path.is_relative_to(root / "src")
    }
    parsed, parse_errors = _parse_python_files(python_files, root)
    imports = {
        module: _module_imports(module, tree)
        for module, path in modules.items()
        if (tree := parsed.get(path)) is not None
    }
    report = {
        "schema": SCHEMA,
        "budgets": _budgets(),
        "oversized_files": _oversized_files(root),
        "oversized_functions": _oversized_functions(root, parsed),
        "import_cycles": _import_cycles(modules, imports),
        "facade_dependencies": _facade_dependencies(modules, parsed, imports),
        "duplicate_routes": _duplicate_routes(root, parsed),
        "dependency_violations": scan_dependency_violations(root, parsed=parsed),
        "parse_errors": parse_errors,
    }
    return report


def scan_dependency_violations(
    repository_root: Path,
    *,
    parsed: dict[Path, ast.AST] | None = None,
) -> list[str]:
    root = repository_root.resolve()
    source_root = root / "src"
    python_files = _python_files(root)
    if parsed is None:
        parsed, _ = _parse_python_files(python_files, root)
    violations: dict[tuple[str, str], str] = {}
    for path in python_files:
        tree = parsed.get(path)
        if tree is None or not path.is_relative_to(source_root):
            continue
        source = _module_name(path, source_root)
        for target in _module_imports(source, tree):
            reason = _forbidden_dependency(source, target)
            if reason:
                relative = path.relative_to(root).as_posix()
                key = (relative, reason)
                current = violations.get(key)
                message = f"{relative}: {reason}: {source} -> {target}"
                if current is None or len(message) < len(current):
                    violations[key] = message
    return sorted(violations.values())


def compare_with_baseline(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    if baseline.get("schema") != SCHEMA:
        return [f"unsupported architecture baseline schema: {baseline.get('schema')}"]
    violations = list(report.get("dependency_violations") or [])
    violations.extend(str(item) for item in report.get("parse_errors") or [])
    violations.extend(_compare_file_debt(report, baseline))
    violations.extend(_compare_function_debt(report, baseline))
    violations.extend(
        _new_collection_items(
            "new import cycle",
            report.get("import_cycles") or [],
            baseline.get("import_cycles") or [],
        )
    )
    violations.extend(_compare_facades(report, baseline))
    violations.extend(_compare_duplicate_routes(report, baseline))
    return sorted(set(violations))


def load_baseline(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"architecture baseline not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid architecture baseline: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"architecture baseline must be an object: {path}")
    return payload


def baseline_from_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "budgets": report["budgets"],
        "oversized_files": report["oversized_files"],
        "oversized_functions": report["oversized_functions"],
        "import_cycles": report["import_cycles"],
        "facade_dependencies": report["facade_dependencies"],
        "duplicate_routes": report["duplicate_routes"],
    }


def _budgets() -> dict[str, int]:
    return {
        "python_file_lines": PYTHON_FILE_LINE_BUDGET,
        "client_file_lines": CLIENT_FILE_LINE_BUDGET,
        "function_lines": FUNCTION_LINE_BUDGET,
        "function_complexity": FUNCTION_COMPLEXITY_BUDGET,
    }


def _python_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for relative in SOURCE_DIRS:
        directory = root / relative
        if directory.is_dir():
            paths.extend(directory.rglob("*.py"))
    return sorted(set(paths))


def _parse_python_files(
    paths: Iterable[Path],
    root: Path,
) -> tuple[dict[Path, ast.AST], list[str]]:
    parsed: dict[Path, ast.AST] = {}
    errors: list[str] = []
    for path in paths:
        try:
            parsed[path] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as exc:
            relative = path.relative_to(root).as_posix()
            errors.append(f"{relative}: {exc}")
    return parsed, sorted(errors)


def _module_name(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_imports(source: str, tree: ast.AST) -> set[str]:
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
                base = ".".join([*prefix, node.module])
                imports.add(base)
                imports.update(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")
            else:
                imports.update(".".join([*prefix, alias.name]) for alias in node.names if alias.name != "*")
        elif node.module:
            imports.add(node.module)
            imports.update(f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*")
    return {item for item in imports if item}


def _forbidden_dependency(source: str, target: str) -> str:
    if source.startswith("literary_engineering_studio_engine") and (
        target == "literary_engineering_studio"
        or target.startswith("literary_engineering_studio.")
    ):
        return "Engine must not import Studio"
    if source.startswith("literary_engineering_studio.projections."):
        segments = set(target.split("."))
        if {"writeback", "promotion"} & segments:
            return "projections must not import writeback/promotion"
    if source.startswith("literary_engineering_studio.orchestration.") and (
        target == "literary_engineering_studio.api"
        or target.startswith("literary_engineering_studio.api.")
        or target == "literary_engineering_studio.api_server"
    ):
        return "orchestration must not import API"
    if source.startswith("literary_engineering_studio.automation.") and target.startswith(
        "literary_engineering_studio_engine.routes."
    ):
        return "automation must not import Engine route implementations"
    return ""


def _oversized_files(root: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    candidates = [*_python_files(root)]
    client_root = root / "client" / "src"
    if client_root.is_dir():
        candidates.extend(client_root.rglob("*.ts"))
        candidates.extend(client_root.rglob("*.vue"))
    for path in sorted(set(candidates)):
        try:
            lines = len(path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError):
            continue
        budget = PYTHON_FILE_LINE_BUDGET if path.suffix == ".py" else CLIENT_FILE_LINE_BUDGET
        if lines > budget:
            result[path.relative_to(root).as_posix()] = lines
    return result


def _oversized_functions(
    root: Path,
    parsed: dict[Path, ast.AST],
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for path, tree in parsed.items():
        for qualname, node in _function_nodes(tree):
            lines = max(1, int(getattr(node, "end_lineno", node.lineno)) - node.lineno + 1)
            complexity = _function_complexity(node)
            if lines > FUNCTION_LINE_BUDGET or complexity > FUNCTION_COMPLEXITY_BUDGET:
                key = f"{path.relative_to(root).as_posix()}::{qualname}"
                result[key] = {"lines": lines, "complexity": complexity}
    return result


def _function_nodes(tree: ast.AST) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            found.append((".".join([*self.scope, node.name]), node))
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

    Visitor().visit(tree)
    return found


def _function_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    class ComplexityVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.score = 1

        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            return

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_Lambda = visit_FunctionDef

        def generic_visit(self, child: ast.AST) -> None:
            if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp)):
                self.score += 1
            elif isinstance(child, ast.BoolOp):
                self.score += max(1, len(child.values) - 1)
            elif isinstance(child, ast.comprehension):
                self.score += 1 + len(child.ifs)
            elif isinstance(child, ast.Match):
                self.score += max(1, len(child.cases))
            super().generic_visit(child)

    visitor = ComplexityVisitor()
    for statement in node.body:
        visitor.visit(statement)
    return visitor.score


def _import_cycles(
    modules: dict[str, Path],
    imports: dict[str, set[str]],
) -> list[list[str]]:
    names = set(modules)
    graph = {
        source: {
            target
            for imported in targets
            if (target := _closest_module(imported, names)) and target != source
        }
        for source, targets in imports.items()
    }
    return sorted(
        [sorted(component) for component in _strongly_connected_components(graph) if len(component) > 1]
    )


def _closest_module(target: str, modules: set[str]) -> str:
    candidate = target
    while candidate:
        if candidate in modules:
            return candidate
        candidate = candidate.rpartition(".")[0]
    return ""


def _strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    stacked: set[str] = set()
    components: list[list[str]] = []

    def connect(node: str) -> None:
        nonlocal index
        indices[node] = lowlinks[node] = index
        index += 1
        stack.append(node)
        stacked.add(node)
        for target in graph.get(node, set()):
            if target not in indices:
                connect(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in stacked:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] != indices[node]:
            return
        component: list[str] = []
        while stack:
            member = stack.pop()
            stacked.remove(member)
            component.append(member)
            if member == node:
                break
        components.append(component)

    for node in sorted(graph):
        if node not in indices:
            connect(node)
    return components


def _facade_dependencies(
    modules: dict[str, Path],
    parsed: dict[Path, ast.AST],
    imports: dict[str, set[str]],
) -> dict[str, list[str]]:
    names = set(modules)
    result: dict[str, list[str]] = {}
    for module, path in modules.items():
        tree = parsed.get(path)
        if tree is None or not _is_facade(tree):
            continue
        dependencies = {
            resolved
            for imported in imports.get(module, set())
            if (resolved := _closest_module(imported, names)) and resolved != module
        }
        result[module] = sorted(dependencies)
    return result


def _is_facade(tree: ast.AST) -> bool:
    docstring = (ast.get_docstring(tree) or "").lower()
    if "compatibility" in docstring or "facade" in docstring:
        return True
    return any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Subscript) for target in node.targets)
        and "sys.modules" in ast.unparse(node)
        for node in getattr(tree, "body", [])
    )


def _duplicate_routes(root: Path, parsed: dict[Path, ast.AST]) -> dict[str, list[str]]:
    occurrences: dict[str, list[str]] = defaultdict(list)
    scopes = {
        "studio": root / "src" / "literary_engineering_studio" / "api" / "routers",
        "engine": root / "src" / "literary_engineering_studio_engine" / "api" / "routers",
    }
    for scope, directory in scopes.items():
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.py")):
            tree = parsed.get(path)
            if tree is None:
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                except (OSError, SyntaxError, UnicodeError):
                    continue
            prefix = _router_prefix(tree)
            for method, route_path in _route_decorators(tree):
                key = f"{scope}:{method}:{prefix}{route_path}"
                occurrences[key].append(path.relative_to(root).as_posix())
    return {
        key: paths
        for key, paths in sorted(occurrences.items())
        if len(paths) > 1
    }


def _router_prefix(tree: ast.AST) -> str:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else ""
        if name != "APIRouter":
            continue
        for keyword in node.keywords:
            if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value or "")
    return ""


def _route_decorators(tree: ast.AST) -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            method = decorator.func.attr.lower()
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                routes.append((method.upper(), str(decorator.args[0].value or "")))
    return routes


def _compare_file_debt(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    allowed = baseline.get("oversized_files") or {}
    return [
        f"file exceeds architecture budget/baseline: {path} ({lines} > {allowed.get(path, PYTHON_FILE_LINE_BUDGET)})"
        for path, lines in (report.get("oversized_files") or {}).items()
        if int(lines) > int(allowed.get(path, PYTHON_FILE_LINE_BUDGET))
    ]


def _compare_function_debt(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    allowed = baseline.get("oversized_functions") or {}
    violations: list[str] = []
    for key, metrics in (report.get("oversized_functions") or {}).items():
        prior = allowed.get(key) or {}
        allowed_lines = int(prior.get("lines", FUNCTION_LINE_BUDGET))
        allowed_complexity = int(prior.get("complexity", FUNCTION_COMPLEXITY_BUDGET))
        if int(metrics["lines"]) > allowed_lines or int(metrics["complexity"]) > allowed_complexity:
            violations.append(
                f"function exceeds architecture budget/baseline: {key} "
                f"(lines={metrics['lines']}/{allowed_lines}, complexity={metrics['complexity']}/{allowed_complexity})"
            )
    return violations


def _new_collection_items(
    label: str,
    current: list[Any],
    allowed: list[Any],
) -> list[str]:
    allowed_keys = {json.dumps(item, ensure_ascii=False, sort_keys=True) for item in allowed}
    return [
        f"{label}: {json.dumps(item, ensure_ascii=False)}"
        for item in current
        if json.dumps(item, ensure_ascii=False, sort_keys=True) not in allowed_keys
    ]


def _compare_facades(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    allowed = baseline.get("facade_dependencies") or {}
    violations: list[str] = []
    for module, dependencies in (report.get("facade_dependencies") or {}).items():
        new_dependencies = sorted(set(dependencies) - set(allowed.get(module) or []))
        if new_dependencies:
            violations.append(f"compatibility facade gained dependencies: {module}: {', '.join(new_dependencies)}")
    return violations


def _compare_duplicate_routes(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    allowed = baseline.get("duplicate_routes") or {}
    violations: list[str] = []
    for route, paths in (report.get("duplicate_routes") or {}).items():
        if sorted(paths) != sorted(allowed.get(route) or []):
            violations.append(f"duplicate API route registration: {route}: {', '.join(paths)}")
    return violations
