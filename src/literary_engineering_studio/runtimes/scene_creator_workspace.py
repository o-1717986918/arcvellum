"""Read-only work archives and a separate persistent scene-creator scratch area."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any, Mapping

from ..project_agent.scope import work_id_for_root


_PRIVATE_NAMES = {".git", ".env", ".codex", ".agent", "auth.json", "secrets.json"}
_MAX_ARCHIVE_BYTES = 8_000_000
_MAX_SCRATCH_BYTES = 1_000_000
_MAX_READ_CHARS = 16_000


def _relative(value: str, *, allow_empty: bool = False) -> PurePosixPath:
    normalized = value.replace("\\", "/").strip()
    if not normalized and allow_empty:
        return PurePosixPath(".")
    path = PurePosixPath(normalized)
    if (not normalized or path.is_absolute() or ":" in normalized or
            any(part in {"", ".", ".."} or part.casefold() in _PRIVATE_NAMES
                or part.startswith(".") for part in path.parts)):
        raise ValueError("path is outside the work archive or uses a private name")
    return path


def _safe_path(root: Path, relative: PurePosixPath, *, require_file: bool = False) -> Path:
    root = root.resolve()
    current = root
    for part in relative.parts:
        if part == ".":
            continue
        current = current / part
        if current.is_symlink():
            raise ValueError("symbolic links are not available to the scene creator")
    resolved = current.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("path escapes the work boundary")
    if require_file and not resolved.is_file():
        raise FileNotFoundError(relative.as_posix())
    return resolved


def _archive_status(path: str) -> str:
    if path.startswith("canon/"):
        return "canon"
    if path.startswith("drafts/scenes/"):
        return "scene_prose"
    if path.startswith("workflow/scene_deltas/") or path == "workflow/continuity/current.json":
        return "mixed_continuity"
    if path == "workflow/studio/user_directions.md":
        return "user_direction"
    if path.startswith("characters/"):
        return "character_archive"
    if path.startswith("plot/") or path.startswith("scenes/"):
        return "planning"
    return "archive_reference"


class SceneCreatorWorkspace:
    """Expose creative archive evidence without granting a work-project write path."""

    def __init__(self, project_root: Path, data_root: Path):
        self.archive_root = project_root.expanduser().resolve()
        self.scratch_root = (data_root.expanduser().resolve() / "scene-creator-sandbox" /
                             work_id_for_root(self.archive_root))
        if not (self.archive_root / "project.yaml").is_file():
            raise ValueError("scene creator requires a work project")

    def _archive_files(self) -> list[str]:
        files: list[str] = []
        for directory, dirs, names in os.walk(self.archive_root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name.casefold() not in _PRIVATE_NAMES
                             and not name.startswith(".") and not (Path(directory) / name).is_symlink())
            for name in sorted(names):
                if name.casefold() in _PRIVATE_NAMES or name.startswith("."):
                    continue
                path = Path(directory) / name
                if path.is_file() and not path.is_symlink():
                    files.append(path.relative_to(self.archive_root).as_posix())
        return sorted(files)

    def list_archive(self, *, prefix: str = "", cursor: int = 0, limit: int = 100) -> dict[str, Any]:
        selected = _relative(prefix, allow_empty=True)
        prefix_text = "" if selected == PurePosixPath(".") else selected.as_posix()
        paths = [path for path in self._archive_files() if not prefix_text or
                 path == prefix_text or path.startswith(prefix_text.rstrip("/") + "/")]
        start, count = max(0, cursor), max(1, min(limit, 200))
        return {"entries": [{"path": path, "status": _archive_status(path)}
                            for path in paths[start:start + count]],
                "next_cursor": start + count if start + count < len(paths) else None,
                "total": len(paths)}

    def search_archive(self, query: str, *, cursor: int = 0, limit: int = 50) -> dict[str, Any]:
        term = query.strip().casefold()
        if not term or len(term) > 200:
            raise ValueError("archive search needs a short query")
        matches: list[dict[str, Any]] = []
        for relative in self._archive_files():
            path = _safe_path(self.archive_root, _relative(relative), require_file=True)
            if term in relative.casefold():
                matches.append({"path": relative, "line": 0, "preview": relative[:200]})
            if path.stat().st_size > _MAX_ARCHIVE_BYTES:
                continue
            try:
                with path.open("r", encoding="utf-8") as stream:
                    for number, line in enumerate(stream, 1):
                        if term in line.casefold():
                            matches.append({"path": relative, "line": number,
                                            "preview": line.strip()[:200]})
                            if len(matches) >= 5000:
                                break
            except (UnicodeError, OSError):
                continue
            if len(matches) >= 5000:
                break
        start, count = max(0, cursor), max(1, min(limit, 100))
        return {"matches": matches[start:start + count],
                "next_cursor": start + count if start + count < len(matches) else None}

    def read_archive(self, path: str, *, start_line: int = 1, end_line: int | None = None,
                     offset: int = 0, max_chars: int = _MAX_READ_CHARS) -> dict[str, Any]:
        relative = _relative(path)
        file = _safe_path(self.archive_root, relative, require_file=True)
        if file.stat().st_size > _MAX_ARCHIVE_BYTES:
            raise ValueError("archive entry exceeds the readable file limit")
        try:
            body = file.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise ValueError("archive entry is not UTF-8 text") from exc
        lines = body.splitlines(keepends=True)
        if start_line < 1 or offset < 0 or (end_line is not None and end_line < start_line):
            raise ValueError("invalid archive line range")
        finish = len(lines) if end_line is None else min(end_line, len(lines))
        selected = "".join(lines[start_line - 1:finish])
        cap = max(1, min(max_chars, _MAX_READ_CHARS))
        page = selected[offset:offset + cap]
        return {"path": relative.as_posix(), "start_line": start_line,
                "end_line": finish, "total_lines": len(lines), "content": page,
                "complete": offset + len(page) >= len(selected),
                "next_offset": offset + len(page) if offset + len(page) < len(selected) else None,
                "status": _archive_status(relative.as_posix()),
                "file_sha256": sha256(body.encode("utf-8")).hexdigest()}

    def freeze_attachments(self, attachments: list[Mapping[str, Any]], *,
                           kind: str, budget_chars: int = 24_000) -> list[dict[str, Any]]:
        if len(attachments) > 20:
            raise ValueError("too many archive attachments")
        total = 0
        frozen: list[dict[str, Any]] = []
        for item in attachments:
            entry = self._freeze_one_attachment(item, kind)
            total += len(entry["content"])
            if total > budget_chars:
                raise ValueError("archive attachments exceed context budget; select smaller fragments")
            frozen.append(entry)
        return frozen

    def _freeze_one_attachment(self, item: Mapping[str, Any], kind: str) -> dict[str, Any]:
        relative = _relative(str(item.get("path") or ""))
        file = _safe_path(self.archive_root, relative, require_file=True)
        if file.stat().st_size > _MAX_ARCHIVE_BYTES:
            raise ValueError(f"archive attachment is too large: {relative}")
        try:
            body = file.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise ValueError(f"archive attachment is not UTF-8 text: {relative}") from exc
        selected, line_range = _select_attachment_lines(body, item)
        knowledge = str(item.get("knowledge") or "").strip()
        _validate_attachment_knowledge(kind, knowledge)
        return {"path": relative.as_posix(), "line_range": line_range,
                "status": _archive_status(relative.as_posix()),
                "knowledge": knowledge or None, "content": selected,
                "file_sha256": sha256(body.encode("utf-8")).hexdigest(),
                "content_sha256": sha256(selected.encode("utf-8")).hexdigest()}

    def _scratch_path(self, path: str, *, require_file: bool = False) -> Path:
        self.scratch_root.mkdir(parents=True, exist_ok=True)
        return _safe_path(self.scratch_root, _relative(path), require_file=require_file)

    def list_scratch(self, prefix: str = "") -> list[str]:
        self.scratch_root.mkdir(parents=True, exist_ok=True)
        relative = _relative(prefix, allow_empty=True)
        directory = _safe_path(self.scratch_root, relative)
        if not directory.exists():
            return []
        if not directory.is_dir():
            raise ValueError("scratch listing requires a directory")
        return sorted(path.relative_to(self.scratch_root).as_posix() for path in directory.rglob("*")
                      if path.is_file() and not path.is_symlink())[:500]

    def read_scratch(self, path: str) -> str:
        file = self._scratch_path(path, require_file=True)
        if file.stat().st_size > _MAX_SCRATCH_BYTES:
            raise ValueError("scratch file exceeds read limit")
        return file.read_text(encoding="utf-8")

    def write_scratch(self, path: str, content: str) -> None:
        if len(content.encode("utf-8")) > _MAX_SCRATCH_BYTES:
            raise ValueError("scratch file exceeds write limit")
        file = self._scratch_path(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=file.parent,
                                         prefix=".scratch-", delete=False) as stream:
            stream.write(content)
            temporary = Path(stream.name)
        try:
            temporary.replace(file)
        finally:
            temporary.unlink(missing_ok=True)

    def move_scratch(self, source: str, destination: str) -> None:
        old = self._scratch_path(source, require_file=True)
        new = self._scratch_path(destination)
        new.parent.mkdir(parents=True, exist_ok=True)
        if new.exists():
            raise FileExistsError(destination)
        old.replace(new)

    def delete_scratch(self, path: str) -> None:
        self._scratch_path(path, require_file=True).unlink()


def _select_attachment_lines(body: str, item: Mapping[str, Any]) -> tuple[str, list[int] | None]:
    start, end = item.get("start_line"), item.get("end_line")
    if (start is None) != (end is None):
        raise ValueError("attachment line range needs both endpoints")
    if start is None:
        return body, None
    lines = body.splitlines(keepends=True)
    if not isinstance(start, int) or isinstance(start, bool):
        raise ValueError("attachment line range is invalid")
    if not isinstance(end, int) or isinstance(end, bool) or start < 1 or end < start or end > len(lines):
        raise ValueError("attachment line range is invalid")
    return "".join(lines[start - 1:end]), [start, end]


def _validate_attachment_knowledge(kind: str, knowledge: str) -> None:
    if kind == "actor" and knowledge not in {"known", "reference"}:
        raise ValueError("actor attachment needs known or reference knowledge")
    if kind != "actor" and knowledge:
        raise ValueError("knowledge partition only applies to actor attachments")


__all__ = ["SceneCreatorWorkspace"]
