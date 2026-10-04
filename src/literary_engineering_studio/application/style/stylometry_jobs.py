"""Persistent long-analysis attempts; cancellation takes effect between compute phases."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import json
from threading import RLock
from uuid import uuid4

from .stylometry_contracts import CorpusTextSource, StylometryJob


class StylometryJobsService:
    def __init__(self, service):
        self.service = service
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stylometry")
        self.lock = RLock()
        self.active = {}

    def launch(self, root, sources, title):
        row = StylometryJob(str(uuid4()), title, json.dumps([asdict(item) for item in sources], ensure_ascii=False))
        self.service.repository.save_job(root, row)
        self._dispatch(root, row)
        return _public(row)

    def list(self, root):
        return {"schema": "arcvellum/stylometry-jobs/v1",
                "jobs": [self.read(root, row.job_id) for row in self.service.repository.jobs(root)]}

    def read(self, root, identifier):
        with self.lock:
            row = self.service.repository.job(root, identifier)
            if row.status in {"queued", "running", "cancelling"} and identifier not in self.active:
                row = replace(row, status="interrupted", phase="上次计算已中断，可恢复")
                self.service.repository.save_job(root, row)
            return _public(row)

    def cancel(self, root, identifier):
        with self.lock:
            row = self.service.repository.job(root, identifier)
            if row.status in {"queued", "running"}:
                row = replace(row, status="cancelling", phase="当前计算段完成后停止")
                self.service.repository.save_job(root, row)
            return _public(row)

    def resume(self, root, identifier):
        with self.lock:
            row = self.service.repository.job(root, identifier)
            if identifier in self.active or row.status == "completed":
                raise ValueError("当前统计正在运行或已完成，请选择可恢复的任务。")
            row = replace(row, status="queued", phase="等待计算", attempt=row.attempt + 1, error="")
            self.service.repository.save_job(root, row)
            self._dispatch(root, row)
            return _public(row)

    def _dispatch(self, root, row):
        with self.lock:
            self.active[row.job_id] = self.pool.submit(self._run, root, row.job_id)

    def _run(self, root, identifier):
        try:
            with self.lock:
                row = self.service.repository.job(root, identifier)
                if row.status == "cancelling":
                    return self._cancelled(root, row)
                row = replace(row, status="running", phase="计算句段、词性与语料分布")
                self.service.repository.save_job(root, row)
            sources = tuple(CorpusTextSource(**item) for item in json.loads(row.sources_json))
            result = self.service.analysis.analyze(sources, row.title)
            with self.lock:
                row = self.service.repository.job(root, identifier)
                if row.status == "cancelling":
                    return self._cancelled(root, row)
                payload = self.service.save_analysis(root, sources, row.title, result.json_text)
                self.service.repository.save_job(root, replace(row, status="completed", phase="统计完成",
                    result_json=json.dumps(payload, ensure_ascii=False)))
        except Exception as error:
            with self.lock:
                row = self.service.repository.job(root, identifier)
                self.service.repository.save_job(root, replace(row, status="failed", phase="计算失败，可恢复", error=str(error)))
        finally:
            with self.lock:
                self.active.pop(identifier, None)

    def _cancelled(self, root, row):
        self.service.repository.save_job(root, replace(row, status="cancelled", phase="已停止，可恢复"))

    def shutdown(self, *, wait=True):
        self.pool.shutdown(wait=wait)


def _public(row):
    data = asdict(row)
    data.pop("sources_json")
    data["result"] = json.loads(data.pop("result_json")) if row.result_json else None
    return {"schema": "arcvellum/stylometry-job/v1", **data}
