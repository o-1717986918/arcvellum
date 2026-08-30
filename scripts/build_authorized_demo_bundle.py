from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from literary_engineering_studio.application.demo_distribution import (
    audit_demo_project,
    build_demo_bundle,
)
from literary_engineering_studio_engine.literary.ingest.authorized import DistributionScope
from literary_engineering_studio_engine.public.projects import (
    build_authorized_demo_project,
    load_authorized_work_manifest,
    seal_authorized_demo_project,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a versioned ArcVellum demo from a locally supplied authorized work.",
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "desktop" / "src-tauri" / "resources" / "demo-projects")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--github-release", action="store_true")
    args = parser.parse_args()

    source_root = args.source_root.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    try:
        manifest_path.relative_to(source_root)
    except ValueError as error:
        raise SystemExit("authorized manifest must be inside --source-root") from error
    manifest = load_authorized_work_manifest(manifest_path)
    scopes = [DistributionScope.DESKTOP_DEMO_BUNDLE]
    if args.github_release:
        scopes.append(DistributionScope.GITHUB_RELEASE_ASSET)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{manifest.work_id}-{args.version}.arcvellum-demo"
    project = args.workspace.expanduser().resolve()
    if not (project / "project.yaml").is_file():
        result = build_authorized_demo_project(
            project,
            source_root=source_root,
            manifest=manifest,
            required_scopes=scopes,
        )
        project = result.project_root
    report = audit_demo_project(project)
    if not report.ready:
        print(json.dumps(report.to_record(), ensure_ascii=False, indent=2))
        raise SystemExit(
            "Authorized project workspace was prepared but is not yet a complete demo. "
            "Run the formal source-ingest analysis, review and promotion workflow, then rerun this command."
        )
    seal_authorized_demo_project(project)
    build_demo_bundle(
        project,
        output,
        bundle_id=manifest.work_id,
        version=args.version,
        project_folder=f"{manifest.work_id}-demo",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output),
                "work_id": manifest.work_id,
                "manifest_digest": manifest.digest(),
                "scopes": [item.value for item in scopes],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
