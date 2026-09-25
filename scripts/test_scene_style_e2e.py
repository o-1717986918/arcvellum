"""Run one isolated real-Pi lean scene through commit for style regression evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from literary_engineering_studio.application.config import load_config
from literary_engineering_studio.application.lean_longform_planning import LeanLongformPlanningService
from literary_engineering_studio.application.lean_assets import ensure_lean_planning_assets
from literary_engineering_studio.application.lean_asset_enrichment import enrich_lean_planning_assets
from literary_engineering_studio.infrastructure.lean_scene_runtime import build_lean_scene_runtime
from literary_engineering_studio.persistence.scene_transactions import (
    SCENE_TRANSACTION_SCHEMA_SQL, SceneTransactionRepository,
)
from literary_engineering_studio.persistence.sqlite_uow import SqliteUnitOfWork
from literary_engineering_studio.runtime.role_conversation import RoleConversationGateway
from literary_engineering_studio_engine.public.literary import SceneExecutionMode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--prepare", action="store_true", help="run planning and asset initialization before the scene")
    args = parser.parse_args()
    project = args.project.resolve()
    if not (project / "project.yaml").is_file():
        parser.error("project.yaml is required")
    config = load_config()
    data_root = project / "studio-data"
    data_root.mkdir(parents=True, exist_ok=True)
    config["application"]["data_root"] = str(data_root)
    print("PREFERENCES", json.dumps(config["application"]["scene_performance_agents"], ensure_ascii=False), flush=True)
    if args.prepare:
        gateway = RoleConversationGateway(config, data_root=data_root / "pi-conversations")
        plan = LeanLongformPlanningService(config, data_root=data_root, gateway=gateway).ensure_initial(project)
        print("PLAN", json.dumps({"chapters": len(plan["chapters"]), "scenes": len(plan["scenes"]),
                                  "narrative_design": plan.get("narrative_design", {})}, ensure_ascii=False), flush=True)
        created = ensure_lean_planning_assets(project)
        enriched = enrich_lean_planning_assets(project, gateway)
        print("ASSETS", json.dumps({"created": created, "enriched": enriched}, ensure_ascii=False), flush=True)
    uow = SqliteUnitOfWork(data_root / "scene-transactions.sqlite3")
    with uow.write() as connection:
        connection.executescript(SCENE_TRANSACTION_SCHEMA_SQL)
    repository = SceneTransactionRepository(uow)
    bundle = build_lean_scene_runtime(
        config, project_root=project, data_root=data_root, repository=repository,
        event_sink=lambda event, payload: print("EVENT", event, json.dumps(payload, ensure_ascii=False)[:500], flush=True)
        if event.startswith(("scene.", "style.")) else None,
    )
    for index in range(args.max_steps):
        step = bundle.coordinator.advance_one(mode=SceneExecutionMode.STANDARD, steward_approved=True)
        print("STEP", index + 1, step.action, step.scene_id, step.transaction_status, step.message[:500], flush=True)
        if step.transaction_id:
            transaction = repository.load(step.transaction_id)
            if transaction.verification is not None:
                print("VERIFY", json.dumps(transaction.verification.to_dict(), ensure_ascii=False)[:3000], flush=True)
            if transaction.review is not None:
                print("REVIEW", transaction.review.decision.value, transaction.review.summary[:600], flush=True)
        if step.committed:
            print("RESULT committed", step.transaction_id, bundle.runtime.metrics, flush=True)
            return 0
        if step.blocked or step.waiting_human:
            print("RESULT blocked", step.transaction_id, step.message, flush=True)
            return 2
    print("RESULT step-limit", args.max_steps, flush=True)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
