from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.ingest import (
    CHUNK_EXTRACTION_SCHEMA,
    aggregate_source_import,
    aggregate_chunk_extractions,
    build_chunk_extraction_plan,
    validate_chunk_extraction,
)
from literary_engineering_studio_engine.agent_tasks import (
    write_agent_completion_marker,
)
from literary_engineering_studio_engine.projects.source_ingest import (
    ingest_existing_work,
)
from literary_engineering_studio_engine.workflow_state import build_workflow_state


class ProjectArchaeologyExtractionTests(unittest.TestCase):
    def test_chunk_contract_requires_exact_evidence_and_source_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest = _source_graph(Path(temporary), chunk_count=1)
            chunk = manifest["chunks"][0]
            payload = _chunk_payload(root, manifest, chunk)
            self.assertEqual(
                validate_chunk_extraction(
                    payload,
                    work_id="source-work",
                    chunk=chunk,
                    evidence_revision="evidence-r1",
                    root=root,
                ),
                [],
            )

            payload["entities"][0]["evidence_refs"] = ["evidence:invented"]
            payload["source_chunk_sha256"] = "0" * 64
            errors = validate_chunk_extraction(
                payload,
                work_id="source-work",
                chunk=chunk,
                evidence_revision="evidence-r1",
                root=root,
            )
            self.assertTrue(any("source_chunk_sha256" in item for item in errors))
            self.assertTrue(any("outside the source chunk" in item for item in errors))

    def test_relation_cannot_target_a_claim_and_attributes_need_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest = _source_graph(Path(temporary), chunk_count=1)
            chunk = manifest["chunks"][0]
            payload = _chunk_payload(root, manifest, chunk)
            entity_id = payload["entities"][0]["candidate_id"]
            payload["entities"][0]["attributes"] = [{"key": "age", "value": 20}]
            payload["relations"] = [
                {
                    "candidate_id": "relation-1",
                    "relation_type": "knows",
                    "source_entity_id": entity_id,
                    "target_entity_id": payload["claims"][0]["candidate_id"],
                    "evidence_refs": chunk["evidence_refs"],
                    "confidence": 0.7,
                    "unknowns": [],
                    "contradiction_notes": [],
                }
            ]

            errors = validate_chunk_extraction(
                payload,
                work_id="source-work",
                chunk=chunk,
                evidence_revision="evidence-r1",
                root=root,
            )

            self.assertTrue(any("attributes[0].evidence_refs" in item for item in errors))
            self.assertTrue(any("references unknown entity" in item for item in errors))

    def test_fan_in_blocks_missing_chunk_without_discarding_valid_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest = _source_graph(Path(temporary), chunk_count=2)
            plan = build_chunk_extraction_plan(
                manifest,
                import_dir="sources/imports/source-work",
            )
            first = manifest["chunks"][0]
            _write_json(root / plan[0]["expected_output"], _chunk_payload(root, manifest, first))

            aggregate, errors = aggregate_chunk_extractions(
                root,
                manifest,
                import_dir="sources/imports/source-work",
            )

            self.assertEqual(aggregate["fan_in"]["status"], "blocked")
            self.assertEqual(aggregate["fan_in"]["received_chunk_ids"], ["chunk-0001"])
            self.assertEqual(aggregate["fan_in"]["missing_chunk_ids"], ["chunk-0002"])
            self.assertEqual(len(aggregate["entity_occurrences"]), 1)
            self.assertTrue(errors)

    def test_alias_and_claim_conflicts_preserve_alternatives_without_merge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest = _source_graph(Path(temporary), chunk_count=2)
            plan = build_chunk_extraction_plan(
                manifest,
                import_dir="sources/imports/source-work",
            )
            first = _chunk_payload(root, manifest, manifest["chunks"][0])
            second = _chunk_payload(root, manifest, manifest["chunks"][1])
            first["entities"][0]["name"] = "林舟"
            second["entities"][0]["name"] = "林舟"
            first["claims"][0]["value"] = "二十岁"
            second["claims"][0]["value"] = "三十岁"
            _write_json(root / plan[0]["expected_output"], first)
            _write_json(root / plan[1]["expected_output"], second)

            aggregate, errors = aggregate_chunk_extractions(
                root,
                manifest,
                import_dir="sources/imports/source-work",
            )

            self.assertEqual(errors, [])
            self.assertEqual(aggregate["fan_in"]["status"], "ready")
            alias = next(
                item
                for item in aggregate["alias_groups"]
                if item["normalized_alias"] == "林舟"
            )
            self.assertEqual(alias["resolution"], "unresolved")
            self.assertFalse(alias["merge_applied"])
            kinds = {item["conflict_type"] for item in aggregate["conflicts"]}
            self.assertIn("alias_identity_ambiguity", kinds)
            self.assertIn("claim_value_conflict", kinds)
            claim_conflict = next(
                item
                for item in aggregate["conflicts"]
                if item["conflict_type"] == "claim_value_conflict"
            )
            self.assertEqual(
                {item["value"] for item in claim_conflict["alternatives"]},
                {"二十岁", "三十岁"},
            )

    def test_timeline_cycle_is_a_blocking_unresolved_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest = _source_graph(Path(temporary), chunk_count=1)
            plan = build_chunk_extraction_plan(
                manifest,
                import_dir="sources/imports/source-work",
            )
            payload = _chunk_payload(root, manifest, manifest["chunks"][0])
            evidence_ref = manifest["chunks"][0]["evidence_refs"][0]
            payload["events"] = [
                _event("event-a", "event-b", evidence_ref),
                _event("event-b", "event-a", evidence_ref),
            ]
            _write_json(root / plan[0]["expected_output"], payload)

            aggregate, errors = aggregate_chunk_extractions(
                root,
                manifest,
                import_dir="sources/imports/source-work",
            )

            self.assertEqual(errors, [])
            temporal = next(
                item
                for item in aggregate["conflicts"]
                if item["conflict_type"] == "temporal_cycle"
            )
            self.assertEqual(temporal["severity"], "blocking")
            self.assertEqual(temporal["resolution"], "unresolved")

    def test_workflow_requires_each_chunk_before_deterministic_fan_in(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text(
                "schema: test-project\n",
                encoding="utf-8",
            )
            source = root / "source.md"
            source.write_text(
                "# 第一章\n\n林舟抵达城门。\n\n# 第二章\n\n林舟离开城门。\n",
                encoding="utf-8",
            )
            result = ingest_existing_work(
                root,
                source=source,
                work_id="source-work",
                rights_declaration="Authorized test source.",
            )
            manifest = _read_json(result.manifest_path)
            plan = manifest["archaeology"]["chunk_tasks"]
            self.assertGreaterEqual(len(plan), 2)

            state = _source_state(root)
            self.assertEqual(state["current_step"], "chunk-extraction-agent-task")
            self.assertEqual(state["chunk_id"], plan[0]["chunk_id"])

            for index, item in enumerate(plan):
                chunk = next(
                    chunk
                    for chunk in manifest["chunks"]
                    if chunk["chunk_id"] == item["chunk_id"]
                )
                _write_json(
                    root / item["expected_output"],
                    _chunk_payload(root, manifest, chunk),
                )
                write_agent_completion_marker(
                    root / item["task_path"],
                    root=root,
                    handled_by="test-worker",
                )
                state = _source_state(root)
                if index + 1 < len(plan):
                    self.assertEqual(
                        state["current_step"],
                        "chunk-extraction-agent-task",
                    )
                    self.assertEqual(state["chunk_id"], plan[index + 1]["chunk_id"])

            self.assertEqual(state["current_step"], "archaeology-fan-in")
            aggregate_path, errors = aggregate_source_import(root, "source-work")
            self.assertEqual(errors, [])
            self.assertEqual(
                aggregate_path.relative_to(root).as_posix(),
                manifest["archaeology"]["aggregate_path"],
            )
            aggregate = _read_json(aggregate_path)
            self.assertEqual(aggregate["fan_in"]["status"], "ready")
            self.assertEqual(
                _source_state(root)["current_step"],
                "archaeology-resolution-agent-task",
            )


def _source_graph(root: Path, *, chunk_count: int) -> tuple[Path, dict[str, object]]:
    root.mkdir(parents=True, exist_ok=True)
    chunks: list[dict[str, object]] = []
    for index in range(1, chunk_count + 1):
        chunk_id = f"chunk-{index:04d}"
        relative = f"sources/imports/source-work/chunks/{chunk_id}.md"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"第 {index} 块源文本。", encoding="utf-8")
        chunks.append(
            {
                "chunk_id": chunk_id,
                "path": relative,
                "evidence_refs": [f"evidence:{chunk_id}"],
            }
        )
    return root, {
        "schema": "literary-engineering-workbench/source-ingest/v2",
        "work_id": "source-work",
        "import_revision": "import-r1",
        "evidence_index": {"revision": "evidence-r1"},
        "chunks": chunks,
    }


def _chunk_payload(
    root: Path,
    manifest: dict[str, object],
    chunk: dict[str, object],
) -> dict[str, object]:
    chunk_id = str(chunk["chunk_id"])
    source_path = root / str(chunk["path"])
    evidence_ref = str(chunk["evidence_refs"][0])
    entity_id = f"person-{chunk_id}"
    return {
        "schema": CHUNK_EXTRACTION_SCHEMA,
        "work_id": manifest["work_id"],
        "chunk_id": chunk_id,
        "source_chunk_path": chunk["path"],
        "source_chunk_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "evidence_revision": manifest["evidence_index"]["revision"],
        "status": "complete",
        "entities": [
            {
                "candidate_id": entity_id,
                "entity_type": "character",
                "name": f"人物 {chunk_id}",
                "aliases": [],
                "attributes": [],
                "evidence_refs": [evidence_ref],
                "confidence": 0.8,
                "unknowns": [],
                "contradiction_notes": [],
            }
        ],
        "events": [],
        "relations": [],
        "claims": [
            {
                "candidate_id": f"claim-{chunk_id}",
                "domain": "character",
                "subject_ref": entity_id,
                "predicate": "age",
                "value": "未知",
                "evidence_refs": [evidence_ref],
                "confidence": 0.6,
                "unknowns": [],
                "contradiction_notes": [],
            }
        ],
    }


def _event(
    candidate_id: str,
    target_event_id: str,
    evidence_ref: str,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "summary": candidate_id,
        "participant_refs": [],
        "temporal_constraints": [
            {
                "kind": "before",
                "target_event_id": target_event_id,
                "evidence_refs": [evidence_ref],
            }
        ],
        "causes": [],
        "effects": [],
        "evidence_refs": [evidence_ref],
        "confidence": 0.8,
        "unknowns": [],
        "contradiction_notes": [],
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _source_state(root: Path) -> dict[str, object]:
    result = build_workflow_state(root, route="source-ingest")
    return _read_json(result.json_path)["source_ingests"][0]


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
