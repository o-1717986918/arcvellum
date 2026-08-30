from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.literary.ingest.authorized import (
    AuthorizationGrant,
    AuthorizedSourceFile,
    AuthorizedWorkManifest,
    DistributionScope,
    RightsBasis,
    verify_authorized_source_bundle,
)
from literary_engineering_studio_engine.public.projects import build_authorized_demo_project
from literary_engineering_studio_engine.public.projects import seal_authorized_demo_project
from literary_engineering_studio.projections.reader import (
    build_reader_manifest,
    read_reader_unit,
)
from literary_engineering_studio.application.demo_distribution import (
    audit_demo_project,
    build_demo_bundle,
    clone_demo_project,
    install_demo_bundle,
    verify_demo_bundle,
)
from literary_engineering_studio.runtime.worker_paths import validate_project


class AuthorizedSourceContractTests(unittest.TestCase):
    def test_verified_bundle_is_stable_and_distribution_scoped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source" / "primary.txt"
            evidence = root / "rights" / "authorization.txt"
            source.parent.mkdir()
            evidence.parent.mkdir()
            source.write_text("第一章\n这是一段测试原文。\n", encoding="utf-8")
            evidence.write_text("Rights holder authorizes this test distribution.", encoding="utf-8")
            manifest = _manifest(source, evidence)

            result = verify_authorized_source_bundle(
                manifest,
                root,
                required_scopes=(DistributionScope.DESKTOP_DEMO_BUNDLE,),
            )

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(
                result.verified_files,
                ("source/primary.txt", "rights/authorization.txt"),
            )
            self.assertEqual(len(result.manifest_digest), 64)
            self.assertEqual(
                AuthorizedWorkManifest.from_record(manifest.to_record()).digest(),
                manifest.digest(),
            )

    def test_public_release_requires_an_explicit_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            evidence = root / "authorization.txt"
            source.write_text("正文", encoding="utf-8")
            evidence.write_text("Authorization evidence for local testing.", encoding="utf-8")
            manifest = _manifest(source, evidence, nested=False)

            result = verify_authorized_source_bundle(
                manifest,
                root,
                required_scopes=(DistributionScope.GITHUB_RELEASE_ASSET,),
            )

            self.assertFalse(result.ok)
            self.assertTrue(any("github_release_asset" in item for item in result.errors))

    def test_private_research_accepts_self_attestation_without_evidence_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("仅供本机私人研究的用户输入文本。", encoding="utf-8")
            manifest = _private_research_manifest(source)

            result = verify_authorized_source_bundle(
                manifest,
                root,
                required_scopes=(DistributionScope.LOCAL_ANALYSIS,),
            )

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.verified_files, ("source.txt",))

    def test_private_research_cannot_be_promoted_to_desktop_distribution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("仅供本机私人研究的用户输入文本。", encoding="utf-8")
            manifest = _private_research_manifest(source)

            result = verify_authorized_source_bundle(
                manifest,
                root,
                required_scopes=(DistributionScope.DESKTOP_DEMO_BUNDLE,),
            )

            self.assertFalse(result.ok)
            self.assertTrue(any("desktop_demo_bundle" in item for item in result.errors))

    def test_tampered_source_and_placeholder_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            evidence = root / "TODO-authorization.txt"
            source.write_text("原始正文", encoding="utf-8")
            evidence.write_text("pending", encoding="utf-8")
            manifest = _manifest(source, evidence, nested=False)
            source.write_text("被修改的正文", encoding="utf-8")

            result = verify_authorized_source_bundle(manifest, root)

            self.assertFalse(result.ok)
            self.assertTrue(any("SHA-256 mismatch" in item for item in result.errors))
            self.assertTrue(any("placeholder" in item for item in result.errors))

    def test_unsafe_paths_and_duplicate_sources_are_rejected(self):
        grant = AuthorizationGrant(
            basis=RightsBasis.AUTHOR_PERMISSION,
            rights_holder="Author",
            licensee="ArcVellum Demo",
            declaration="Author permits a local authorized demonstration.",
            evidence_ref="../authorization.txt",
            evidence_sha256="a" * 64,
            scopes=(DistributionScope.LOCAL_ANALYSIS,),
        )
        duplicate = AuthorizedSourceFile(
            source_id="primary-text",
            filename="C:/private/source.txt",
            media_type="text/plain",
            sha256="b" * 64,
            byte_size=12,
        )
        manifest = AuthorizedWorkManifest(
            work_id="yu-hua-i-am-timid-as-a-mouse",
            title="我胆小如鼠",
            author="余华",
            edition="Authorized test edition",
            language="zh-CN",
            work_type="novella",
            source_files=(duplicate, duplicate),
            authorization=grant,
        )

        errors = manifest.validation_errors()

        self.assertTrue(any("source_id values must be unique" in item for item in errors))
        self.assertTrue(any("safe relative path" in item for item in errors))

    def test_authorized_demo_uses_source_ranges_without_fake_promotion(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            bundle = base / "bundle"
            source = bundle / "source" / "primary.txt"
            evidence = bundle / "rights" / "authorization.txt"
            source.parent.mkdir(parents=True)
            evidence.parent.mkdir(parents=True)
            source.write_text(
                "第一章 起点\n第一段测试正文。\n第二段仍是原文。\n\n第二章 转向\n第三段测试正文。\n",
                encoding="utf-8",
            )
            evidence.write_text(
                "Rights holder authorizes this test distribution.",
                encoding="utf-8",
            )
            project = base / "project"

            result = build_authorized_demo_project(
                project,
                source_root=bundle,
                manifest=_manifest(source, evidence),
                seal_reference=True,
            )
            authorized_reader = json.loads(result.reader_manifest_path.read_text(encoding="utf-8"))
            authorized_reader["units"][0]["chapter_id"] = "chapter_0001"
            authorized_reader["units"][0]["scene_id"] = "scene_0001"
            result.reader_manifest_path.write_text(
                json.dumps(authorized_reader, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            reader = build_reader_manifest(project)

            self.assertEqual(result.work_id, "yu-hua-i-am-timid-as-a-mouse")
            self.assertEqual(reader["unit_count"], 2)
            self.assertTrue(all(item["status"] == "authorized" for item in reader["units"]))
            self.assertTrue(all(item["source_kind"] == "authorized_source" for item in reader["units"]))
            self.assertEqual(reader["units"][0]["scene_id"], "scene_0001")
            self.assertEqual(reader["units"][0]["coverage"], ["scene_0001"])
            self.assertFalse((project / "drafts" / "scenes" / "scene_0001.md").exists())
            first = read_reader_unit(project, reader["units"][0]["unit_id"])
            self.assertIn("第一段测试正文", first["body"])
            self.assertNotIn("第二章 转向", first["body"])
            identity = (project / ".arcvellum-demo.json").read_text(encoding="utf-8")
            self.assertIn('"origin": "authorized_source"', identity)
            self.assertIn("status: reference", (project / "project.yaml").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "只读项目"):
                validate_project(project)

    def test_demo_bundle_installs_atomically_and_clones_as_editable(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            bundle_root = base / "authorized-input"
            source = bundle_root / "source" / "primary.txt"
            evidence = bundle_root / "rights" / "authorization.txt"
            source.parent.mkdir(parents=True)
            evidence.parent.mkdir(parents=True)
            source.write_text("第一章 起点\n一段用于测试的正文。\n", encoding="utf-8")
            evidence.write_text(
                "Rights holder authorizes this test distribution.",
                encoding="utf-8",
            )
            project = base / "built-project"
            build_authorized_demo_project(
                project,
                source_root=bundle_root,
                manifest=_manifest(source, evidence),
            )
            completeness = audit_demo_project(project)
            self.assertFalse(completeness.ready)
            self.assertTrue(any("正式晋升资产" in item for item in completeness.errors))
            with self.assertRaisesRegex(ValueError, "sealed read-only"):
                build_demo_bundle(
                    project,
                    base / "unsealed.arcvellum-demo",
                    bundle_id="yu-hua-i-am-timid-as-a-mouse",
                    version="1.0.0-test",
                )
            seal_authorized_demo_project(project)
            bundle = build_demo_bundle(
                project,
                base / "demo.arcvellum-demo",
                bundle_id="yu-hua-i-am-timid-as-a-mouse",
                version="1.0.0-test",
            )

            self.assertTrue(verify_demo_bundle(bundle).ok)
            installed = install_demo_bundle(bundle, base / "works")
            repeated = install_demo_bundle(bundle, base / "works")
            editable = clone_demo_project(
                installed.project_root,
                base / "works" / "my-editable-copy",
                title="我的可编辑副本",
            )

            self.assertEqual(installed.status, "installed")
            self.assertEqual(repeated.status, "already_installed")
            self.assertFalse((editable / ".arcvellum-demo.json").exists())
            self.assertTrue((editable / ".arcvellum-demo-copy.json").is_file())
            self.assertIn("status: planning", (editable / "project.yaml").read_text(encoding="utf-8"))
            self.assertIn("我的可编辑副本", (editable / "project.yaml").read_text(encoding="utf-8"))


def _manifest(source: Path, evidence: Path, *, nested: bool = True) -> AuthorizedWorkManifest:
    source_name = "source/primary.txt" if nested else source.name
    evidence_name = "rights/authorization.txt" if nested else evidence.name
    return AuthorizedWorkManifest(
        work_id="yu-hua-i-am-timid-as-a-mouse",
        title="我胆小如鼠",
        author="余华",
        edition="Authorized test edition",
        language="zh-CN",
        work_type="novella",
        source_files=(
            AuthorizedSourceFile(
                source_id="primary-text",
                filename=source_name,
                media_type="text/plain",
                sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                byte_size=source.stat().st_size,
            ),
        ),
        authorization=AuthorizationGrant(
            basis=RightsBasis.AUTHOR_PERMISSION,
            rights_holder="Author",
            licensee="ArcVellum Demo",
            declaration="The author permits this authorized local demonstration.",
            evidence_ref=evidence_name,
            evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
            scopes=(
                DistributionScope.LOCAL_ANALYSIS,
                DistributionScope.DESKTOP_DEMO_BUNDLE,
            ),
        ),
    )


def _private_research_manifest(source: Path) -> AuthorizedWorkManifest:
    return AuthorizedWorkManifest(
        work_id="private-research-work",
        title="私人研究文本",
        author="来源作者",
        edition="用户提供的本地版本",
        language="zh-CN",
        work_type="novella",
        source_files=(
            AuthorizedSourceFile(
                source_id="primary-text",
                filename=source.name,
                media_type="text/plain",
                sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                byte_size=source.stat().st_size,
            ),
        ),
        authorization=AuthorizationGrant(
            basis=RightsBasis.USER_ATTESTED_PRIVATE_RESEARCH,
            rights_holder="",
            licensee="",
            declaration="用户确认该文本仅用于本机私人研究，不由 ArcVellum 再分发。",
            evidence_ref="",
            evidence_sha256="",
            scopes=(DistributionScope.LOCAL_ANALYSIS,),
        ),
    )


if __name__ == "__main__":
    unittest.main()
