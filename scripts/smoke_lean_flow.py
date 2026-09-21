"""Run a bounded real-Pi lean literary smoke in a disposable work project."""

from __future__ import annotations

import argparse
from pathlib import Path

from literary_engineering_studio.application.config import load_config
from literary_engineering_studio.application.lean_book_audit import audit_lean_book
from literary_engineering_studio.application.lean_longform_planning import LeanLongformPlanningService
from literary_engineering_studio.infrastructure.lean_scene_runtime import build_lean_scene_runtime
from literary_engineering_studio.persistence.scene_transactions import (
    SCENE_TRANSACTION_SCHEMA_SQL, SceneTransactionRepository,
)
from literary_engineering_studio.persistence.sqlite_uow import SqliteUnitOfWork
from literary_engineering_studio.projections.whole_book_release import LeanWholeBookReleaseCoordinator
from literary_engineering_studio_engine.public.literary import SceneExecutionMode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--max-steps", type=int, default=60)
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    if not (root / "project.yaml").is_file():
        parser.error("project.yaml is required")
    config = load_config()
    data_root = root / "studio-data"
    config["application"]["data_root"] = str(data_root)
    planning = LeanLongformPlanningService(config, data_root=data_root)
    planning.ensure_initial(root)
    uow = SqliteUnitOfWork(data_root / "scene-transactions.sqlite3")
    with uow.write() as connection:
        connection.executescript(SCENE_TRANSACTION_SCHEMA_SQL)
    repository = SceneTransactionRepository(uow)
    bundle = build_lean_scene_runtime(
        config, project_root=root, data_root=data_root,
        repository=repository, planning=planning,
    )
    for index in range(args.max_steps):
        step = bundle.coordinator.advance_one(
            mode=SceneExecutionMode.STANDARD, steward_approved=True,
        )
        print(index + 1, step.action, step.scene_id, step.message[:180], flush=True)
        if step.blocked or step.waiting_human:
            return 2
        if step.route_ready:
            audit = audit_lean_book(root, data_root)
            release = LeanWholeBookReleaseCoordinator(config).release(
                root, approved_by="smoke-test",
            )
            print("RELEASE", release["manifest_path"], audit["scene_count"], flush=True)
            return 0
    print("STEP_LIMIT_REACHED", args.max_steps, flush=True)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
