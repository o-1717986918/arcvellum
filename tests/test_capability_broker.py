from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.runtime.capabilities import (
    CapabilityBroker,
    CapabilityContext,
    CapabilityId,
    CapabilityRequest,
    build_capability_manifest,
)
from literary_engineering_studio_engine.task_registry import _enrich_task_payload


class CapabilityBrokerTests(unittest.TestCase):
    def _task(
        self,
        root: Path,
        *,
        route: str = "source-ingest",
        current_state: str = "chunk-extraction-agent-task",
        task_type: str = "platform-agent-extraction",
        capability_policy: dict[str, object] | None = None,
    ):
        (root / "project.yaml").write_text(
            "title: Capability Demo\nlanguage: zh-CN\ntarget_word_count: 500000\nprivate_note: do-not-project\n",
            encoding="utf-8",
        )
        source = root / "sources" / "evidence.jsonl"
        source.parent.mkdir(parents=True)
        source.write_text(
            '{"evidence_id":"ev-001","text":"港口在雨夜关闭。"}\n'
            '{"evidence_id":"ev-002","text":"守门人改了口供。"}\n',
            encoding="utf-8",
        )
        reference = root / "references" / "domain.md"
        reference.parent.mkdir(parents=True)
        reference.write_text("港口规则：午夜以后不得通行。\n", encoding="utf-8")
        task_dir = root / "workflow" / "tasks"
        task_dir.mkdir(parents=True)
        markdown = task_dir / "capability-demo.agent_tasks.md"
        markdown.write_text("# Capability demo\n", encoding="utf-8")
        payload = {
            "schema": "literary-engineering-workbench/agent-task/v1",
            "task_id": "capability-demo",
            "status": "opened",
            "route": route,
            "current_state": current_state,
            "task_type": task_type,
            "prompt_asset_id": "route.source-ingest.chunk.extract.execute.v1",
            "required_reading": ["references/domain.md", "SKILL.md"],
            "source_paths": ["sources/evidence.jsonl", "references/domain.md"],
            "agent_source_paths": ["sources/evidence.jsonl", "references/domain.md"],
            "expected_outputs": ["analysis/candidate.md"],
            "submission_command": "lew task-submit",
            "completion_command": "lew task-complete",
            "validation_gates": [],
            "forbidden_shortcuts": [],
            "task_markdown": "workflow/tasks/capability-demo.agent_tasks.md",
        }
        if capability_policy is not None:
            payload["capability_policy"] = capability_policy
        enriched = _enrich_task_payload(payload)
        if isinstance(enriched.get("prompt_asset"), dict):
            enriched["prompt_asset"]["exact"] = True
        task_json = task_dir / "capability-demo.task.json"
        task_json.write_text(json.dumps(enriched, ensure_ascii=False), encoding="utf-8")
        return load_task_package(root, task_json)

    def _context(self, task, run_root: Path, *, workspace: Path | None = None, fetcher=None):
        return CapabilityContext(
            task=task,
            manifest=build_capability_manifest(task),
            run_root=run_root,
            workspace_root=workspace,
            web_fetcher=fetcher,
        )

    def test_manifest_is_role_and_route_scoped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "SKILL.md").write_text("host manual", encoding="utf-8")
            extraction = self._task(root)
            manifest = build_capability_manifest(extraction)
            self.assertIn(CapabilityId.CITATION_LOOKUP.value, manifest.allowed_capability_ids)
            self.assertNotIn(CapabilityId.ASSET_DIFF.value, manifest.allowed_capability_ids)
            self.assertNotIn(CapabilityId.RESEARCH_WEB.value, manifest.allowed_capability_ids)
            self.assertNotIn("SKILL.md", manifest.readable_paths)
            self.assertEqual(len(manifest.digest), 64)

            payload = json.loads(extraction.task_json_path.read_text(encoding="utf-8"))
            payload["route"] = "scene-development"
            payload["current_state"] = "agent-review-task"
            payload["task_type"] = "platform-agent-review"
            payload["prompt_asset_id"] = "route.scene-development.agent-review.v1"
            extraction.task_json_path.write_text(json.dumps(_enrich_task_payload(payload)), encoding="utf-8")
            review = load_task_package(root, extraction.task_json_path)
            self.assertIn(CapabilityId.ASSET_DIFF.value, build_capability_manifest(review).allowed_capability_ids)

    def test_core_handlers_complete_with_bounded_task_sources(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as run:
            root = Path(temporary)
            (root / "SKILL.md").write_text("host manual", encoding="utf-8")
            task = self._task(root)
            context = self._context(task, Path(run))
            broker = CapabilityBroker()

            overview = broker.invoke(
                context,
                CapabilityRequest("req-overview", task.task_id, CapabilityId.PROJECT_QUERY.value, {"query": "overview"}),
            )
            self.assertEqual(overview.status, "completed")
            self.assertEqual(overview.data["title"], "Capability Demo")
            self.assertNotIn("private_note", overview.data)

            stats = broker.invoke(
                context,
                CapabilityRequest(
                    "req-statistics",
                    task.task_id,
                    CapabilityId.TEXT_STATISTICS.value,
                    {"path": "sources/evidence.jsonl"},
                ),
            )
            self.assertGreater(stats.data["han_characters"], 10)

            search = broker.invoke(
                context,
                CapabilityRequest(
                    "req-search",
                    task.task_id,
                    CapabilityId.REFERENCE_SEARCH.value,
                    {"query": "午夜", "paths": ["references/domain.md"]},
                ),
            )
            self.assertEqual(len(search.data["matches"]), 1)

            citation = broker.invoke(
                context,
                CapabilityRequest(
                    "req-citation",
                    task.task_id,
                    CapabilityId.CITATION_LOOKUP.value,
                    {"citation_id": "ev-002", "paths": ["sources/evidence.jsonl"]},
                ),
            )
            self.assertEqual(citation.data["matches"][0]["line"], 2)

            schema = broker.invoke(
                context,
                CapabilityRequest(
                    "req-schema",
                    task.task_id,
                    CapabilityId.SCHEMA_INSPECT.value,
                    {"schema_name": "scene_review.v1"},
                ),
            )
            self.assertEqual(schema.status, "completed")
            self.assertIn("conclusion", schema.data["required"])

    def test_unauthorized_and_escaping_paths_are_deterministically_denied(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as run:
            root = Path(temporary)
            (root / "SKILL.md").write_text("host manual", encoding="utf-8")
            task = self._task(root)
            context = self._context(task, Path(run))
            broker = CapabilityBroker()

            unauthorized = broker.invoke(
                context,
                CapabilityRequest(
                    "req-diff-denied",
                    task.task_id,
                    CapabilityId.ASSET_DIFF.value,
                    {"before_path": "sources/evidence.jsonl", "after_path": "analysis/candidate.md"},
                ),
            )
            self.assertEqual(unauthorized.status, "denied")
            self.assertEqual(unauthorized.error_code, "capability-not-authorized")

            escaping = broker.invoke(
                context,
                CapabilityRequest(
                    "req-escape-denied",
                    task.task_id,
                    CapabilityId.TEXT_STATISTICS.value,
                    {"path": "../outside.txt"},
                ),
            )
            self.assertEqual(escaping.status, "denied")
            self.assertEqual(escaping.error_code, "path-invalid")

            undeclared = broker.invoke(
                context,
                CapabilityRequest(
                    "req-path-denied",
                    task.task_id,
                    CapabilityId.TEXT_STATISTICS.value,
                    {"path": "canon/secret.yaml"},
                ),
            )
            self.assertEqual(undeclared.status, "denied")
            self.assertEqual(undeclared.error_code, "path-not-authorized")

    def test_asset_diff_reads_project_before_and_workspace_after(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as run:
            root = Path(temporary)
            (root / "SKILL.md").write_text("host manual", encoding="utf-8")
            task = self._task(
                root,
                route="scene-development",
                current_state="agent-review-task",
                task_type="platform-agent-review",
            )
            target = root / "analysis" / "candidate.md"
            target.parent.mkdir()
            target.write_text("旧版本。\n", encoding="utf-8")
            workspace = Path(run) / "workspace"
            workspace_target = workspace / "analysis" / "candidate.md"
            workspace_target.parent.mkdir(parents=True)
            workspace_target.write_text("新版本。\n", encoding="utf-8")
            context = self._context(task, Path(run), workspace=workspace)
            result = CapabilityBroker().invoke(
                context,
                CapabilityRequest(
                    "req-asset-diff",
                    task.task_id,
                    CapabilityId.ASSET_DIFF.value,
                    {
                        "before_path": "analysis/candidate.md",
                        "after_path": "analysis/candidate.md",
                        "before_scope": "project",
                        "after_scope": "workspace",
                    },
                ),
            )
            self.assertEqual(result.status, "completed")
            self.assertIn("-旧版本。", result.data["diff"])
            self.assertIn("+新版本。", result.data["diff"])

    def test_oversized_result_uses_artifact_and_audit_omits_query_body(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as run:
            root = Path(temporary)
            (root / "SKILL.md").write_text("host manual", encoding="utf-8")
            secret_query = "super-secret-story-fragment"
            long_source = root / "references" / "domain.md"
            task = self._task(
                root,
                capability_policy={"max_result_chars": 1000},
            )
            long_source.write_text(
                "\n".join(f"{secret_query} 第{i}条：" + "内容" * 40 for i in range(50)),
                encoding="utf-8",
            )
            context = self._context(task, Path(run))
            result = CapabilityBroker().invoke(
                context,
                CapabilityRequest(
                    "req-large-search",
                    task.task_id,
                    CapabilityId.REFERENCE_SEARCH.value,
                    {"query": secret_query, "paths": ["references/domain.md"], "max_results": 50},
                ),
            )
            self.assertTrue(result.truncated)
            self.assertTrue((Path(run) / result.artifact).is_file())
            audit = (Path(run) / "capabilities" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertNotIn(secret_query, audit)
            self.assertIn(result.result_digest, audit)

    def test_web_is_explicit_and_revalidates_final_domain(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as run:
            root = Path(temporary)
            (root / "SKILL.md").write_text("host manual", encoding="utf-8")
            task = self._task(
                root,
                capability_policy={
                    "allow": ["research.web"],
                    "network_domains": ["research.example"],
                },
            )

            def allowed_fetcher(url: str, *, max_bytes: int):
                return url, "text/html", "<p>可核验的研究候选。</p>"

            context = self._context(task, Path(run), fetcher=allowed_fetcher)
            broker = CapabilityBroker()
            denied = broker.invoke(
                context,
                CapabilityRequest(
                    "req-web-domain",
                    task.task_id,
                    CapabilityId.RESEARCH_WEB.value,
                    {"url": "https://other.example/source"},
                ),
            )
            self.assertEqual(denied.status, "denied")
            self.assertEqual(denied.error_code, "network-domain-not-authorized")

            completed = broker.invoke(
                context,
                CapabilityRequest(
                    "req-web-allowed",
                    task.task_id,
                    CapabilityId.RESEARCH_WEB.value,
                    {"url": "https://research.example/source"},
                ),
            )
            self.assertEqual(completed.status, "completed")
            self.assertEqual(completed.data["canonical_status"], "unverified-research-candidate")

            def redirected_fetcher(_url: str, *, max_bytes: int):
                return "https://other.example/redirected", "text/plain", "redirected"

            redirected_context = self._context(task, Path(run), fetcher=redirected_fetcher)
            redirected = broker.invoke(
                redirected_context,
                CapabilityRequest(
                    "req-web-redirect",
                    task.task_id,
                    CapabilityId.RESEARCH_WEB.value,
                    {"url": "https://research.example/source"},
                ),
            )
            self.assertEqual(redirected.status, "failed")

    def test_events_and_audit_expose_status_but_not_sensitive_arguments(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as run:
            root = Path(temporary)
            (root / "SKILL.md").write_text("host manual", encoding="utf-8")
            task = self._task(root)
            events: list[tuple[str, dict[str, object]]] = []
            broker = CapabilityBroker(event_sink=lambda event, data: events.append((event, data)))
            result = broker.invoke(
                self._context(task, Path(run)),
                CapabilityRequest(
                    "req-event-denied",
                    task.task_id,
                    CapabilityId.RESEARCH_WEB.value,
                    {"url": "https://private.example/", "api_key": "never-persist-this"},
                ),
            )
            self.assertEqual(result.status, "denied")
            self.assertEqual(events[0][0], "capability.denied")
            serialized_event = json.dumps(events, ensure_ascii=False)
            serialized_audit = (Path(run) / "capabilities" / "audit.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("never-persist-this", serialized_event)
            self.assertNotIn("never-persist-this", serialized_audit)
            self.assertIn("api_key", serialized_audit)


if __name__ == "__main__":
    unittest.main()
