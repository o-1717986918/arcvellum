"""Atomic project-private immutable profiles, versions and revisioned mounts."""
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from uuid import UUID

from ..application.style.stylometry_contracts import CreatorStyleSnapshot, StylometryProfile, StylometryVersion, StylometryJob
from ..project_agent.scope import work_id_for_root
from .stylometry_lock import mount_lock


_LOCK = RLock()


class FileStylometryRepository:
    def __init__(self, data_root: Path):
        self.root = data_root.resolve()

    def _directory(self, root):
        return self.root / "stylometry" / work_id_for_root(root.resolve())

    def _path(self, root, kind, identifier):
        if str(UUID(identifier)) != identifier:
            raise ValueError("无效统计版本标识。")
        return self._directory(root) / kind / (identifier + ".json")

    def profiles(self, root):
        return tuple(self.profile(root, path.stem) for path in sorted(self._directory(root).glob("profiles/*.json")))

    def profile(self, root, profile_id):
        return StylometryProfile(**_read(self._path(root, "profiles", profile_id), root))

    def save_profile(self, root, record):
        self._save(root, "profiles", record.profile_id, record)

    def versions(self, root):
        return tuple(self.version(root, path.stem) for path in sorted(self._directory(root).glob("versions/*.json")))

    def version(self, root, version_id):
        record = StylometryVersion(**_read(self._path(root, "versions", version_id), root))
        if sha256(record.fragment_text.encode("utf-8")).hexdigest() != record.content_sha256:
            raise ValueError("文风版本正文摘要校验失败。")
        return record

    def save_version(self, root, record):
        self.profile(root, record.profile_id)
        self._save(root, "versions", record.version_id, record)

    def _save(self, root, kind, identifier, record):
        path = self._path(root, kind, identifier)
        with _LOCK:
            if path.exists():
                raise ValueError("统计档案与参数版本均为不可变记录。")
            _write(path, root, asdict(record))

    def snapshot(self, root):
        path = self._directory(root) / "mount.json"
        if not path.exists():
            return CreatorStyleSnapshot()
        snapshot = CreatorStyleSnapshot(**_read(path, root))
        if snapshot.enabled:
            record = self.version(root, snapshot.version_id)
            if (record.content_sha256, record.fragment_text, record.profile_id) != (
                snapshot.content_sha256, snapshot.fragment_text, snapshot.profile_id):
                raise ValueError("挂载快照与不可变版本不一致。")
        return snapshot

    def set_mount(self, root, snapshot, expected_revision):
        with _LOCK, mount_lock(self._directory(root) / "mount.lock"):
            current = self.snapshot(root)
            if type(expected_revision) is not int or current.revision != expected_revision:
                raise ValueError("挂载状态已更新，请刷新后重新选择。")
            updated = replace(snapshot, revision=current.revision + 1)
            _write(self._directory(root) / "mount.json", root, asdict(updated))
            return updated

    def jobs(self, root):
        return tuple(self.job(root, path.stem) for path in sorted(self._directory(root).glob("jobs/*.json")))

    def job(self, root, job_id):
        return StylometryJob(**_read(self._path(root, "jobs", job_id), root))

    def save_job(self, root, record):
        with _LOCK:
            _write(self._path(root, "jobs", record.job_id), root, asdict(record))


def _read(path, root):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError("统计档案或版本不存在。") from error
    payload = data["payload"]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if data.get("project_root") != str(root.resolve()) or data.get("sha256") != sha256(canonical.encode()).hexdigest():
        raise ValueError("统计记录来源或摘要校验失败。")
    return payload


def _write(path, root, payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    data = {"schema": "arcvellum/private-stylometry-record/v1", "project_root": str(root.resolve()),
        "sha256": sha256(canonical.encode()).hexdigest(), "payload": payload}
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
