"""Generate the reviewable ArcVellum module ownership map."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModuleBoundary:
    path: str
    owner: str
    public_entry: str
    may_depend_on: str
    must_not_own: str


BOUNDARIES = (
    ModuleBoundary("src/literary_engineering_studio_engine/foundation", "Engine foundation", "package exports", "standard library", "Studio runtime or UI"),
    ModuleBoundary("src/literary_engineering_studio_engine/tasking", "Formal task contracts", "tasking/__init__.py", "Engine foundation", "Agent execution"),
    ModuleBoundary("src/literary_engineering_studio_engine/routes", "Formal route catalog", "routes/catalog.py", "tasking and literary services", "Studio lifecycle"),
    ModuleBoundary("src/literary_engineering_studio_engine/workflow", "Workflow projections", "workflow_state facade", "tasking and routes", "Runtime adapters"),
    ModuleBoundary("src/literary_engineering_studio_engine/literary", "Literary domain", "domain package exports", "foundation and task contracts", "FastAPI or Provider SDKs"),
    ModuleBoundary("src/literary_engineering_studio_engine/prompting", "Prompt programs", "prompt registry/compiler", "literary contracts", "Provider transport"),
    ModuleBoundary("src/literary_engineering_studio_engine/orchestration", "Read-only orchestration catalog", "orchestration/__init__.py", "task and Gate catalogs", "Planner execution"),
    ModuleBoundary("src/literary_engineering_studio_engine/projections", "Engine read projections", "projection facades", "formal project facts", "promotion/writeback"),
    ModuleBoundary("src/literary_engineering_studio_engine/command_line", "Engine CLI adapter", "command_line/main.py", "Engine public services", "literary business rules"),
    ModuleBoundary("src/literary_engineering_studio/application", "Studio use cases", "application services", "ports and Engine contracts", "API/framework adapters"),
    ModuleBoundary("src/literary_engineering_studio/automation", "Campaign control", "automation/controller.py", "application/runtime ports", "Engine route implementations"),
    ModuleBoundary("src/literary_engineering_studio/orchestration", "Adaptive plan domain", "orchestration services", "Engine catalog and ports", "API or task lifecycle"),
    ModuleBoundary("src/literary_engineering_studio/runtime", "Controlled execution", "runtime worker/bundle ports", "contracts and infrastructure ports", "literary route policy"),
    ModuleBoundary("src/literary_engineering_studio/runtimes", "Agent adapters", "runtimes registry", "Runtime SPI and external SDKs", "Engine route implementations"),
    ModuleBoundary("src/literary_engineering_studio/persistence", "Durable adapters", "repository facades", "SQLite and file storage", "literary decisions"),
    ModuleBoundary("src/literary_engineering_studio/projections", "Studio read models", "projection services", "read ports and Engine facts", "promotion/writeback"),
    ModuleBoundary("src/literary_engineering_studio/preflight", "Writeback validation", "task_preflight facade", "contracts and deterministic validators", "Agent creativity"),
    ModuleBoundary("src/literary_engineering_studio/observability", "Events and telemetry", "observability projections", "event contracts", "task mutation"),
    ModuleBoundary("src/literary_engineering_studio/integrations", "External integrations", "integration-specific facades", "external SDKs and ports", "literary policy"),
    ModuleBoundary("src/literary_engineering_studio/api", "HTTP/SSE adapters", "router factories", "application use cases", "direct project mutation"),
    ModuleBoundary("src/literary_engineering_studio/advisor", "Read-only advisor", "advisor service", "read models and Runtime port", "formal project writeback"),
    ModuleBoundary("workers/pi-worker/src", "Bounded Pi Worker", "main.ts / worker.ts", "Pi SDK and task contract", "formal project access"),
    ModuleBoundary("desktop/src-tauri/src", "Desktop host", "main.rs", "Tauri commands and sidecar protocol", "literary logic"),
)


def render_module_map(root: Path) -> str:
    root = root.resolve()
    tracked_sources = _git_tracked_source_paths(root)

    def source_file_count(path: Path) -> int:
        return _source_file_count(path, repository_root=root, tracked_sources=tracked_sources)

    lines = [
        "# ArcVellum 模块所有权图",
        "",
        "> 本文件由 `python scripts/generate_module_map.py` 生成。它描述模块所有权与依赖边界，",
        "> 不描述创作 Agent 的操作流程，也不替代正式 TaskPackage。",
        "",
        "| 路径 | 文件数 | 所有者 | 公开入口 | 可依赖 | 不得拥有 |",
        "|---|---:|---|---|---|---|",
    ]
    for item in BOUNDARIES:
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{item.path}`",
                    str(source_file_count(root / item.path)),
                    item.owner,
                    f"`{item.public_entry}`",
                    item.may_depend_on,
                    item.must_not_own,
                )
            )
            + " |"
        )
    lines.extend(("", "## Vue Feature 所有权", ""))
    lines.extend(("| Feature | 文件数 | 规则 |", "|---|---:|---|"))
    features = root / "client" / "src" / "features"
    for feature_name in _feature_names(features, root, tracked_sources):
        path = features / feature_name
        lines.append(
            f"| `{feature_name}` | {source_file_count(path)} | 只通过 feature client、共享只读合同或命令总线跨域协作 |"
        )
    lines.extend(
        (
            "",
            "## 机器检查",
            "",
            "- `python scripts/architecture_audit.py`：依赖方向、债务棘轮、循环和复杂度；",
            "- `python scripts/generate_module_map.py --check`：本图是否与目录同步；",
            "- `python -m unittest tests.test_architecture_audit tests.test_module_dependency_direction -v`：边界行为。",
            "",
        )
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the ArcVellum module ownership map.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = (args.output or root / "docs" / "architecture" / "generated-module-map.md").resolve()
    rendered = render_module_map(root)
    if args.check:
        try:
            with output.open("r", encoding="utf-8", newline="") as stream:
                current = stream.read()
        except FileNotFoundError:
            print(f"module map is missing: {output}")
            return 1
        if current != rendered:
            print(f"module map is stale: {output}")
            return 1
        print(f"module map is current: {output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"module map written: {output}")
    return 0


def _git_tracked_source_paths(root: Path) -> tuple[str, ...] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    suffixes = {".py", ".ts", ".vue", ".rs"}
    return tuple(
        path
        for path in result.stdout.split("\0")
        if path and Path(path).suffix in suffixes
    )


def _feature_names(
    features: Path,
    repository_root: Path,
    tracked_sources: tuple[str, ...] | None,
) -> tuple[str, ...]:
    if tracked_sources is None:
        if not features.is_dir():
            return ()
        return tuple(
            sorted(
                path.name
                for path in features.iterdir()
                if path.is_dir() and _source_file_count(path) > 0
            )
        )
    prefix = features.relative_to(repository_root).as_posix().rstrip("/") + "/"
    return tuple(
        sorted(
            {
                path[len(prefix) :].split("/", 1)[0]
                for path in tracked_sources
                if path.startswith(prefix) and "/" in path[len(prefix) :]
            }
        )
    )


def _source_file_count(
    root: Path,
    *,
    repository_root: Path | None = None,
    tracked_sources: tuple[str, ...] | None = None,
) -> int:
    if tracked_sources is not None and repository_root is not None:
        prefix = root.relative_to(repository_root).as_posix().rstrip("/") + "/"
        return sum(1 for path in tracked_sources if path.startswith(prefix))
    if not root.is_dir():
        return 0
    suffixes = {".py", ".ts", ".vue", ".rs"}
    return sum(1 for path in root.rglob("*") if path.is_file() and path.suffix in suffixes)


if __name__ == "__main__":
    raise SystemExit(main())
