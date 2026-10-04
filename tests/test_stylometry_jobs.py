from dataclasses import replace
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.style.stylometry_jobs import StylometryJobsService
from literary_engineering_studio.application.style.stylometry_contracts import CorpusTextSource
from literary_engineering_studio.infrastructure.stylometry_analysis import LabStylometryAnalysis
from tests import test_stylometry_service as fixtures


class StylometryJobsTests(unittest.TestCase):
    setUp = fixtures.StylometryServiceTests.setUp

    def test_cancel_then_resume_preserves_input_and_reuses_successful_analysis(self):
        jobs = StylometryJobsService(self.service)
        started, released = Event(), Event()
        original = self.service.analysis.analyze
        def blocked(*args):
            started.set()
            self.assertTrue(released.wait(3))
            return original(*args)
        sources = (CorpusTextSource("text-one", "work-one", "雨停了。窗子开着。"),)
        with patch.object(self.service.analysis, "analyze", side_effect=blocked):
            row = jobs.launch(self.root, sources, "片段")
            self.assertTrue(started.wait(3))
            self.assertEqual(jobs.cancel(self.root, row["job_id"])["status"], "cancelling")
            released.set()
            jobs.shutdown()
        self.assertEqual(jobs.read(self.root, row["job_id"])["status"], "cancelled")
        restarted = StylometryJobsService(self.service)
        restarted.resume(self.root, row["job_id"])
        restarted.shutdown()
        result = restarted.read(self.root, row["job_id"])
        self.assertEqual((result["status"], result["attempt"]), ("completed", 2))
        self.assertEqual(result["result"]["kind"], "single-text")

    def test_failed_and_interrupted_attempts_are_recoverable(self):
        jobs = StylometryJobsService(self.service)
        with patch.object(self.service.analysis, "analyze", side_effect=ValueError("broken input")):
            row = jobs.launch(self.root, (CorpusTextSource("text-one", "work-one", "雪落下来。"),), "片段")
            jobs.shutdown()
        self.assertIn("broken input", jobs.read(self.root, row["job_id"])["error"])
        stored = self.repository.job(self.root, row["job_id"])
        self.repository.save_job(self.root, replace(stored, status="running"))
        restarted = StylometryJobsService(self.service)
        self.assertEqual(restarted.read(self.root, row["job_id"])["status"], "interrupted")
        restarted.resume(self.root, row["job_id"])
        restarted.shutdown()
        self.assertEqual(restarted.read(self.root, row["job_id"])["status"], "completed")

    def test_analysis_cache_uses_content_and_method_and_rejects_tampering(self):
        analyzer = LabStylometryAnalysis(Path(self.folder.name) / "cache")
        sources = (CorpusTextSource("text-one", "work-one", "雪落下来。"),)
        result = analyzer.analyze(sources, "片段")
        with patch.object(analyzer, "_analyze", side_effect=AssertionError("cache missed")):
            self.assertEqual(analyzer.analyze(sources, "片段"), result)
        cache = next((Path(self.folder.name) / "cache").glob("*.json"))
        cache.write_text('{"json_text": "tampered", "sha256": "invalid"}')
        self.assertEqual(analyzer.analyze(sources, "片段"), result)
        changed = analyzer.analyze((replace(sources[0], text="门打开了。"),), "片段")
        self.assertNotEqual(result, changed)
