from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.archaeology import (
    canonicalize_archaeology_metadata,
    validate_archaeology_reconstruction_output,
)
from literary_engineering_studio.sandbox import SandboxManifest
from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.asset_workshop import _dry_payload
from literary_engineering_studio_engine.literary.assets.promotion import (
    promotion_eligibility_errors,
)
from literary_engineering_studio_engine.literary.ingest import (
    CHUNK_EXTRACTION_SCHEMA,
    DOMAIN_REVIEW_SCHEMA,
    IDENTITY_RESOLUTION_SCHEMA,
    RECONSTRUCTION_CANDIDATE_SCHEMA,
    aggregate_source_import,
    archaeology_candidate_provenance_errors,
    materialize_archaeology_candidates,
    reconstruction_paths,
)
from literary_engineering_studio_engine.literary.ingest.evidence import canonical_digest
from literary_engineering_studio_engine.projects.source_ingest import ingest_existing_work
from literary_engineering_studio_engine.source_ingest_route import build_task_payload
from literary_engineering_studio_engine.workflow.state_assets import asset_candidate_states
from literary_engineering_studio_engine.workflow_state import build_workflow_state


class ProjectArchaeologyReconstructionTests(unittest.TestCase):
    def test_reviewed_reconstruction_materializes_into_existing_archive_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest, aggregate = _ready_import(Path(temporary), mode="continuation")
            paths = reconstruction_paths("sources/imports/source-work")

            self.assertEqual(_source_state(root)["current_step"], "archaeology-resolution-agent-task")
            task = build_task_payload(
                root,
                "source-ingest",
                {
                    "work_id": "source-work",
                    "import_dir": "sources/imports/source-work",
                    "current_step": "archaeology-resolution-agent-task",
                },
            )
            self.assertEqual(task["prompt_asset_id"], "route.source-ingest.resolve-identities.v1")
            self.assertNotIn(paths["resolution_task"], task["agent_source_paths"])

            resolution = _write_resolution(root, manifest, aggregate, paths)
            self.assertEqual(_source_state(root)["current_step"], "archaeology-reconstruction-agent-task")
            candidate = _write_candidate(
                root,
                manifest,
                aggregate,
                resolution,
                paths,
                recommendation="promote",
            )
            self.assertEqual(_source_state(root)["current_step"], "archaeology-domain-review-agent-task")
            review = _write_domain_review(
                root,
                manifest,
                candidate,
                paths,
                decision="promote",
            )
            self.assertEqual(review["status"], "pass")
            self.assertEqual(_source_state(root)["current_step"], "archaeology-materialize")

            output, errors = materialize_archaeology_candidates(root, "source-work")
            self.assertEqual(errors, [])
            first_bytes = output.read_bytes()
            candidate_path = root / "canon/candidates/world_rules/source-world.json"
            self.assertTrue(candidate_path.is_file())
            self.assertTrue(candidate_path.with_suffix(".agent_tasks.md").is_file())
            self.assertTrue(candidate_path.with_suffix(".agent_completion.json").is_file())
            states = {
                str(item["candidate_id"]): item
                for item in asset_candidate_states(root)
            }
            self.assertEqual(states["source-world"]["current_step"], "asset-review-task-file")
            self.assertEqual(_source_state(root)["status"], "ready")

            rerun, rerun_errors = materialize_archaeology_candidates(root, "source-work")
            self.assertEqual(rerun_errors, [])
            self.assertEqual(rerun.read_bytes(), first_bytes)

            resolution["notes"] = ["changed after candidate materialization"]
            resolution["revision"] = canonical_digest(resolution)
            _write_json(root / paths["resolution"], resolution)
            payload = _json(candidate_path)
            stale = archaeology_candidate_provenance_errors(root, payload)
            self.assertTrue(any("resolution_revision changed" in item for item in stale))
            promotion_errors = promotion_eligibility_errors(
                root,
                candidate_path,
                asset_type="world",
                approval_run_id="archaeology-source-world",
                allow_unapproved=True,
            )
            self.assertTrue(
                any("resolution_revision changed" in item for item in promotion_errors)
            )

    def test_worker_preflight_owns_resolution_metadata_and_rejects_bad_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root, manifest, aggregate = _ready_import(
                temporary_root,
                mode="continuation",
            )
            paths = reconstruction_paths("sources/imports/source-work")
            payload = build_task_payload(
                root,
                "source-ingest",
                {
                    "work_id": "source-work",
                    "import_dir": "sources/imports/source-work",
                    "current_step": "archaeology-resolution-agent-task",
                },
            )
            task = TaskPackage(
                project_root=root,
                task_json_path=root / "workflow/tasks/archaeology-resolution.json",
                task_markdown_path=root / "workflow/tasks/archaeology-resolution.md",
                payload=payload,
            )
            workspace = temporary_root / "sandbox"
            shutil.copytree(root, workspace)
            resolution = _write_resolution(workspace, manifest, aggregate, paths)
            resolution["schema"] = "agent-guessed-schema"
            resolution["aggregate_revision"] = "agent-guessed-revision"
            resolution["revision"] = "agent-guessed-content-digest"
            _write_json(workspace / paths["resolution"], resolution)
            sandbox = SandboxManifest(
                run_id="archaeology-preflight",
                run_root=temporary_root,
                workspace=workspace,
                prompt_path=temporary_root / "prompt.md",
                manifest_path=temporary_root / "manifest.json",
                baseline_path=temporary_root / "baseline.json",
                expected_outputs=task.expected_outputs,
            )

            changes = canonicalize_archaeology_metadata(task, sandbox)
            self.assertTrue(changes)
            normalized = _json(workspace / paths["resolution"])
            self.assertEqual(normalized["schema"], IDENTITY_RESOLUTION_SCHEMA)
            self.assertEqual(normalized["aggregate_revision"], aggregate["revision"])
            issues = []
            validate_archaeology_reconstruction_output(task, sandbox, issues)
            self.assertEqual(issues, [])

            normalized["entity_groups"][0]["occurrence_refs"] = []
            normalized["revision"] = canonical_digest(normalized)
            _write_json(workspace / paths["resolution"], normalized)
            issues = []
            validate_archaeology_reconstruction_output(task, sandbox, issues)
            self.assertTrue(
                any("occurrence_refs must be non-empty" in item.message for item in issues)
            )

    def test_analysis_mode_finishes_without_creating_promotable_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, manifest, aggregate = _ready_import(Path(temporary), mode="analysis")
            paths = reconstruction_paths("sources/imports/source-work")
            resolution = _write_resolution(root, manifest, aggregate, paths)
            candidate = _write_candidate(
                root,
                manifest,
                aggregate,
                resolution,
                paths,
                recommendation="analysis_only",
            )
            _write_domain_review(
                root,
                manifest,
                candidate,
                paths,
                decision="analysis_only",
            )

            state = _source_state(root)
            self.assertEqual(state["status"], "ready")
            self.assertFalse((root / "canon/candidates/world_rules/source-world.json").exists())
            _output, errors = materialize_archaeology_candidates(root, "source-work")
            self.assertIn("analysis mode cannot materialize promotable Archive candidates", errors)


def _ready_import(
    temporary: Path,
    *,
    mode: str,
) -> tuple[Path, dict[str, object], dict[str, object]]:
    root = temporary / "work"
    root.mkdir()
    (root / "project.yaml").write_text(
        "schema: test-project\ntitle: Source Work\n",
        encoding="utf-8",
    )
    result = ingest_existing_work(
        root,
        text="# 第一章\n林昭抵达白塔。白塔保存被删改的旧档案。\n",
        work_id="source-work",
        mode=mode,
        rights_declaration="Authorized test source.",
        chunk_size=20000,
    )
    manifest = _json(result.manifest_path)
    chunks = {str(item["chunk_id"]): item for item in manifest["chunks"]}
    first = True
    for task in manifest["archaeology"]["chunk_tasks"]:
        chunk = chunks[str(task["chunk_id"])]
        source_path = root / str(task["source_chunk_path"])
        evidence_ref = str(chunk["evidence_refs"][0])
        entities = []
        claims = []
        if first:
            entities.append(
                {
                    "candidate_id": "lin-zhao",
                    "entity_type": "character",
                    "name": "林昭",
                    "aliases": [],
                    "attributes": [],
                    "evidence_refs": [evidence_ref],
                    "confidence": 0.9,
                    "unknowns": [],
                    "contradiction_notes": [],
                }
            )
            claims.append(
                {
                    "candidate_id": "white-tower-archive",
                    "domain": "world",
                    "subject_ref": "lin-zhao",
                    "predicate": "reaches_archive",
                    "value": "白塔",
                    "evidence_refs": [evidence_ref],
                    "confidence": 0.8,
                    "unknowns": [],
                    "contradiction_notes": [],
                }
            )
            first = False
        _write_json(
            root / str(task["expected_output"]),
            {
                "schema": CHUNK_EXTRACTION_SCHEMA,
                "work_id": "source-work",
                "chunk_id": task["chunk_id"],
                "source_chunk_path": task["source_chunk_path"],
                "source_chunk_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                "evidence_revision": manifest["evidence_index"]["revision"],
                "status": "complete",
                "entities": entities,
                "events": [],
                "relations": [],
                "claims": claims,
            },
        )
        write_agent_completion_marker(
            root / str(task["task_path"]),
            root=root,
            handled_by="test-agent",
        )
    aggregate_path, errors = aggregate_source_import(root, "source-work")
    if errors:
        raise AssertionError(errors)
    return root, manifest, _json(aggregate_path)


def _write_resolution(
    root: Path,
    manifest: dict[str, object],
    aggregate: dict[str, object],
    paths: dict[str, str],
) -> dict[str, object]:
    occurrence = aggregate["entity_occurrences"][0]
    payload: dict[str, object] = {
        "schema": IDENTITY_RESOLUTION_SCHEMA,
        "work_id": manifest["work_id"],
        "aggregate_revision": aggregate["revision"],
        "evidence_revision": manifest["evidence_index"]["revision"],
        "status": "complete",
        "entity_groups": [
            {
                "entity_id": "lin-zhao",
                "display_name": "林昭",
                "entity_type": "character",
                "aliases": [],
                "occurrence_refs": [occurrence["candidate_ref"]],
                "resolution": "single",
                "evidence_refs": occurrence["evidence_refs"],
                "confidence": 0.9,
                "rationale": "Only one bounded occurrence is present.",
                "unknowns": [],
            }
        ],
        "conflict_reviews": [],
        "notes": [],
    }
    payload["revision"] = canonical_digest(payload)
    _write_json(root / paths["resolution"], payload)
    _write_report(root / paths["resolution_report"])
    write_agent_completion_marker(root / paths["resolution_task"], root=root, handled_by="test-agent")
    return payload


def _write_candidate(
    root: Path,
    manifest: dict[str, object],
    aggregate: dict[str, object],
    resolution: dict[str, object],
    paths: dict[str, str],
    *,
    recommendation: str,
) -> dict[str, object]:
    evidence_ref = str(aggregate["entity_occurrences"][0]["evidence_refs"][0])
    world = _dry_payload("world", "source-world", root, "", "", None)
    world["source_paths"] = [paths["resolution"], str(manifest["evidence_index"]["path"])]
    payload: dict[str, object] = {
        "schema": RECONSTRUCTION_CANDIDATE_SCHEMA,
        "work_id": manifest["work_id"],
        "mode": manifest["mode"],
        "aggregate_revision": aggregate["revision"],
        "resolution_revision": resolution["revision"],
        "status": "candidate",
        "project_summary": {
            "title": "Source Work",
            "premise": "林昭调查白塔中被删改的档案。",
            "confidence": 0.8,
            "unknowns": ["删改者身份"],
        },
        "assets": [
            {
                "candidate_id": "source-world",
                "asset_type": "world",
                "payload": world,
                "evidence_refs": [evidence_ref],
                "confidence": 0.8,
                "unresolved_refs": [],
                "promotion_recommendation": recommendation,
            }
        ],
        "domain_observations": [
            {
                "domain": "promise",
                "summary": "读者期待得知档案删改者。",
                "evidence_refs": [evidence_ref],
                "confidence": 0.7,
            }
        ],
    }
    payload["revision"] = canonical_digest(payload)
    _write_json(root / paths["candidate"], payload)
    _write_report(root / paths["candidate_report"])
    write_agent_completion_marker(root / paths["candidate_task"], root=root, handled_by="test-agent")
    return payload


def _write_domain_review(
    root: Path,
    manifest: dict[str, object],
    candidate: dict[str, object],
    paths: dict[str, str],
    *,
    decision: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": DOMAIN_REVIEW_SCHEMA,
        "work_id": manifest["work_id"],
        "mode": manifest["mode"],
        "candidate_revision": candidate["revision"],
        "status": "pass",
        "domain_reviews": [
            {
                "domain": domain,
                "status": "pass",
                "blocking_issues": [],
                "warnings": [],
            }
            for domain in ("character", "world", "plot", "style", "promise")
        ],
        "asset_decisions": [
            {
                "candidate_id": "source-world",
                "decision": decision,
                "blocking_issues": [],
                "warnings": [],
                "rationale": "Evidence is sufficient for an Archive candidate.",
            }
        ],
    }
    payload["revision"] = canonical_digest(payload)
    _write_json(root / paths["review"], payload)
    _write_report(root / paths["review_report"])
    write_agent_completion_marker(root / paths["review_task"], root=root, handled_by="test-reviewer")
    return payload


def _source_state(root: Path) -> dict[str, object]:
    result = build_workflow_state(root, route="source-ingest")
    return _json(result.json_path)["source_ingests"][0]


def _write_report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Review artifact\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
