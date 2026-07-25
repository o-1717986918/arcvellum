from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from literary_engineering_studio_engine.projects.source_ingest import ingest_existing_work
from literary_engineering_studio_engine.source_ingest_route import (
    build_task_payload,
    manifest_gate_errors,
)


class ProjectArchaeologyIngestTests(unittest.TestCase):
    def test_text_and_markdown_import_preserves_sources_ranges_and_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _project(Path(temporary))
            source_dir = root / "incoming"
            source_dir.mkdir()
            (source_dir / "01-preface.txt").write_text(
                "序章\n第一段。\n",
                encoding="utf-8",
            )
            (source_dir / "02-story.md").write_text(
                "# 第一章 起点\n\n第二段。\n\n## 现场\n\n第三段。\n",
                encoding="utf-8",
            )

            result = ingest_existing_work(
                root,
                source=source_dir,
                work_id="known-work",
                rights_declaration="User supplied the work for authorized analysis.",
                chunk_size=200,
            )

            manifest = _json(result.manifest_path)
            evidence = _json(result.import_dir / "evidence_index.json")
            serialized = result.manifest_path.read_text(encoding="utf-8")
            self.assertEqual(manifest["schema"], "literary-engineering-workbench/source-ingest/v2")
            self.assertEqual(manifest["source_count"], 2)
            self.assertEqual(manifest["segment_count"], evidence["segment_count"])
            self.assertEqual(manifest["rights_declaration"], "User supplied the work for authorized analysis.")
            self.assertNotIn(str(root), serialized)
            self.assertTrue(all(item["bounds"] for item in manifest["source_documents"]))
            self.assertTrue(all(item["evidence_refs"] for item in manifest["chunks"]))
            self.assertIn("chapter", {item["kind"] for item in evidence["segments"]})
            self.assertEqual(manifest_gate_errors(root, result.import_dir), [])
            task_text = result.task_path.read_text(encoding="utf-8")
            self.assertIn("sources/imports/known-work/evidence_index.json", task_text)
            self.assertNotIn(".known-work.importing", task_text)
            task = build_task_payload(
                root,
                "source-ingest",
                {
                    "work_id": "known-work",
                    "import_dir": "sources/imports/known-work",
                    "current_step": "extraction-agent-task",
                },
            )
            self.assertIn("project.yaml", task["source_paths"])
            self.assertIn(
                "sources/imports/known-work/evidence_index.json",
                task["source_paths"],
            )

    def test_docx_reader_keeps_heading_body_table_and_footnote_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _project(Path(temporary))
            source = root / "source.docx"
            _write_docx(source)

            result = ingest_existing_work(
                root,
                source=source,
                work_id="docx-work",
                rights_declaration="Public-domain source.",
            )

            manifest = _json(result.manifest_path)
            document = manifest["source_documents"][0]
            raw = (root / document["raw_path"]).read_text(encoding="utf-8")
            bounds = document["bounds"]
            self.assertLess(raw.index("第一章 起点"), raw.index("正文第一段。"))
            self.assertLess(raw.index("正文第一段。"), raw.index("表格中的文字。"))
            self.assertLess(raw.index("表格中的文字。"), raw.index("脚注 2：脚注内容。"))
            self.assertIn("〔脚注2〕", raw)
            self.assertEqual(bounds[0]["kind"], "heading")
            self.assertEqual(bounds[0]["heading_level"], 1)
            self.assertEqual(bounds[-1]["kind"], "footnote")
            self.assertEqual(bounds[-1]["footnote_id"], "2")
            self.assertNotIn("separator", raw)
            self.assertEqual(manifest_gate_errors(root, result.import_dir), [])

    def test_failed_overwrite_restores_previous_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _project(Path(temporary))
            good = root / "good.txt"
            good.write_text("第一章\n原始内容。\n", encoding="utf-8")
            first = ingest_existing_work(root, source=good, work_id="stable")
            original_manifest = first.manifest_path.read_bytes()
            broken = root / "broken.docx"
            broken.write_bytes(b"not-a-docx")

            with self.assertRaises(ValueError):
                ingest_existing_work(
                    root,
                    source=broken,
                    work_id="stable",
                    overwrite=True,
                )

            self.assertEqual(first.manifest_path.read_bytes(), original_manifest)
            self.assertFalse((root / "sources/imports/.stable.importing").exists())
            self.assertFalse((root / "sources/imports/.stable.backup").exists())

    def test_gate_rejects_tampered_source_and_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = _project(Path(temporary))
            source = root / "source.txt"
            source.write_text("第一章\n不可变正文。\n", encoding="utf-8")
            result = ingest_existing_work(root, source=source, work_id="tamper")
            manifest = _json(result.manifest_path)
            raw = root / manifest["source_documents"][0]["raw_path"]
            raw.write_text("被改写。\n", encoding="utf-8")
            evidence_path = result.import_dir / "evidence_index.json"
            evidence = _json(evidence_path)
            evidence["segments"][0]["kind"] = "tampered"
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest["source_documents"][0]["bounds"][0]["char_end"] = 999
            result.manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            errors = manifest_gate_errors(root, result.import_dir)
            self.assertTrue(any("extracted text hash mismatch" in item for item in errors))
            self.assertTrue(any("evidence index revision" in item for item in errors))
            self.assertTrue(any("does not match source range char_end" in item for item in errors))


def _project(root: Path) -> Path:
    (root / "project.yaml").write_text("schema: test-project\n", encoding="utf-8")
    return root


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_docx(path: Path) -> None:
    document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>第一章 起点</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>正文第一段。</w:t></w:r><w:r><w:footnoteReference w:id="2"/></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>表格中的文字。</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    <w:sectPr/>
  </w:body>
</w:document>
"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr>
  </w:style>
</w:styles>
"""
    footnotes = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="-1"><w:p><w:r><w:t>separator</w:t></w:r></w:p></w:footnote>
  <w:footnote w:id="0"><w:p><w:r><w:t>continuation separator</w:t></w:r></w:p></w:footnote>
  <w:footnote w:id="2"><w:p><w:r><w:t>脚注内容。</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""
    with ZipFile(path, "w", ZIP_DEFLATED) as package:
        package.writestr("word/document.xml", document)
        package.writestr("word/styles.xml", styles)
        package.writestr("word/footnotes.xml", footnotes)


if __name__ == "__main__":
    unittest.main()
