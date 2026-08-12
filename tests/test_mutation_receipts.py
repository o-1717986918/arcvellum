from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_read_models import install_core_import_path
from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.persistence.mutation_receipts import (
    MutationReceiptRepository,
)
from literary_engineering_studio.persistence.schema import initialize_schema
from literary_engineering_studio.persistence.sqlite_uow import SqliteUnitOfWork
from literary_engineering_studio.observability.mutation_receipt_tracking import (
    persist_mutation_receipt_event,
)
from literary_engineering_studio.observability.mutation_receipts import (
    FormalEffect,
    MutationAction,
    build_mutation_receipt,
    parse_mutation_receipt,
)
from literary_engineering_studio.runtime.mutation_tracking import (
    load_worker_mutation_receipts,
)
from literary_engineering_studio.worker import AgentWorker


class MutationReceiptTests(unittest.TestCase):
    def test_observability_sink_failure_cannot_split_formal_writeback(self):
        with tempfile.TemporaryDirectory() as temporary:
            project, config = _project_and_config(Path(temporary))

            def unavailable_sink(event: str, data: dict) -> None:
                raise OSError("event projection unavailable")

            with patch(
                "literary_engineering_studio.worker.build_runtime",
                side_effect=AssertionError("deterministic task must not run an Agent"),
            ):
                result = AgentWorker(config, event_sink=unavailable_sink).run_once(
                    project,
                    route="longform-planning",
                    runtime_id="opencode",
                )

            self.assertEqual(result.status, "complete")
            assert result.run_root is not None
            self.assertTrue(load_worker_mutation_receipts(result.run_root))
            failures = [
                json.loads(line)
                for line in (result.run_root / "observability-errors.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            self.assertTrue(failures)
            self.assertTrue(
                all(item["error_type"] == "OSError" for item in failures)
            )
            self.assertTrue(all("data" not in item for item in failures))

    def test_repository_uses_explicit_unit_of_work_without_job_store_inheritance(self):
        with tempfile.TemporaryDirectory() as temporary:
            uow = SqliteUnitOfWork(Path(temporary) / "studio.sqlite3")
            with uow.write() as connection:
                initialize_schema(connection)
            repository = MutationReceiptRepository(uow)
            receipt = build_mutation_receipt(
                change_group_id="change-" + "a" * 24,
                project_key="work-a1b2c3d4e5",
                plan_id="fixed-route",
                plan_revision=0,
                node_id="task-one",
                task_id="task-one",
                run_id="run-one",
                session_id="worker-run:run-one",
                context_ledger_id="context-one",
                action=MutationAction.CANDIDATE_CREATED,
                target="plot/outline.md",
                base_sha256="",
                result_sha256="b" * 64,
                preflight_status="pending",
                writeback_status="pending",
                formal_effect=FormalEffect.NONE,
                created_at="2026-07-26T00:00:00+00:00",
            )

            first = repository.record_mutation_receipt("C:/work", receipt.as_dict())
            repeated = repository.record_mutation_receipt("C:/work", receipt.as_dict())

            self.assertEqual(first, repeated)
            self.assertEqual(repository.read_mutation_receipt(receipt.receipt_id), first)
            self.assertEqual(
                repository.list_mutation_receipts("C:/work", run_id="run-one"),
                [first],
            )
            self.assertNotIn("MutationReceiptStoreMixin", {base.__name__ for base in JobStore.__mro__})

    def test_contract_rejects_forged_identity_and_rollback_effect(self):
        receipt = build_mutation_receipt(
            change_group_id="change-" + "a" * 24,
            project_key="work-a1b2c3d4e5",
            plan_id="fixed-route",
            plan_revision=0,
            node_id="task-one",
            task_id="task-one",
            run_id="run-one",
            session_id="worker-run:run-one",
            context_ledger_id="context-one",
            action=MutationAction.WRITEBACK_ROLLED_BACK,
            target="plot/outline.md",
            base_sha256="a" * 64,
            result_sha256="b" * 64,
            preflight_status="pass",
            writeback_status="rolled_back",
            formal_effect=FormalEffect.NONE,
            created_at="2026-07-26T00:00:00+00:00",
        )
        self.assertEqual(parse_mutation_receipt(receipt.as_dict()), receipt)

        forged = receipt.as_dict()
        forged["receipt_id"] = "receipt-" + "f" * 24
        forged.pop("digest")
        with self.assertRaisesRegex(ValueError, "identity"):
            parse_mutation_receipt(forged)
        with self.assertRaisesRegex(ValueError, "formal_effect=none"):
            build_mutation_receipt(
                change_group_id="change-" + "a" * 24,
                project_key="work-a1b2c3d4e5",
                plan_id="fixed-route",
                plan_revision=0,
                node_id="task-one",
                task_id="task-one",
                run_id="run-one",
                session_id="worker-run:run-one",
                context_ledger_id="",
                action=MutationAction.WRITEBACK_ROLLED_BACK,
                target="plot/outline.md",
                base_sha256="a" * 64,
                result_sha256="b" * 64,
                preflight_status="pass",
                writeback_status="rolled_back",
                formal_effect=FormalEffect.FORMAL,
                created_at="2026-07-26T00:00:00+00:00",
            )

    def test_deterministic_worker_emits_and_persists_three_stage_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            project, config = _project_and_config(Path(temporary))
            store = JobStore(Path(temporary) / "studio.sqlite3")
            events: list[tuple[str, dict]] = []

            def emit(event: str, data: dict) -> None:
                events.append((event, data))
                persist_mutation_receipt_event(
                    store,
                    project_root=str(project),
                    event=event,
                    data=data,
                )

            with patch(
                "literary_engineering_studio.worker.build_runtime",
                side_effect=AssertionError("deterministic task must not run an Agent"),
            ):
                result = AgentWorker(config, event_sink=emit).run_once(
                    project,
                    route="longform-planning",
                    runtime_id="opencode",
                )

            self.assertEqual(result.status, "complete")
            assert result.run_root is not None and result.workspace is not None
            receipts = load_worker_mutation_receipts(result.run_root)
            actions = {item.action for item in receipts}
            self.assertTrue(
                {
                    MutationAction.CANDIDATE_CREATED,
                    MutationAction.WRITEBACK_PREVIEWED,
                    MutationAction.WRITEBACK_APPLIED,
                }.issubset(actions)
            )
            self.assertFalse((result.workspace / "mutation-receipts.jsonl").exists())
            self.assertNotIn(
                "mutation-receipts.jsonl",
                json.loads((result.run_root / "run.json").read_text(encoding="utf-8"))[
                    "expected_outputs"
                ],
            )
            stored = store.list_mutation_receipts(str(project), run_id=result.run_root.name)
            self.assertEqual(len(stored), len(receipts))
            self.assertTrue(all(item["authority"] == "studio-machine" for item in stored))
            self.assertTrue(all(item["plan_id"] == "fixed-route" for item in stored))
            self.assertEqual(
                len([event for event, _ in events if event == "mutation.receipt"]),
                len(receipts),
            )

    def test_core_gate_failure_records_rollback_with_no_formal_effect(self):
        with tempfile.TemporaryDirectory() as temporary:
            project, config = _project_and_config(Path(temporary))
            worker = AgentWorker(config)
            with (
                patch(
                    "literary_engineering_studio.worker.build_runtime",
                    side_effect=AssertionError("deterministic task must not run an Agent"),
                ),
                patch.object(
                    worker.bridge,
                    "task_complete",
                    side_effect=RuntimeError("forced core gate failure"),
                ),
            ):
                result = worker.run_once(
                    project,
                    route="longform-planning",
                    runtime_id="opencode",
                )

            self.assertEqual(result.status, "blocked_by_core_gate")
            self.assertEqual(result.failure_kind, "core_gate_contract")
            self.assertFalse(result.retryable)
            assert result.run_root is not None
            rolled_back = [
                item
                for item in load_worker_mutation_receipts(result.run_root)
                if item.action is MutationAction.WRITEBACK_ROLLED_BACK
            ]
            self.assertTrue(rolled_back)
            self.assertTrue(
                all(item.formal_effect is FormalEffect.NONE for item in rolled_back)
            )
            self.assertFalse(
                (project / "plot" / "story_architecture.candidate.json").exists()
            )


def _project_and_config(temporary: Path):
    config = default_config()
    install_core_import_path(config)
    from literary_engineering_studio_engine.init_project import InitOptions, init_work_project

    project = temporary / "work"
    init_work_project(
        InitOptions(
            target=project,
            title="Mutation Receipt Verification",
            target_length=30000,
        )
    )
    config["worker"]["runs_root"] = str(temporary / "runs")
    return project, config


if __name__ == "__main__":
    unittest.main()
