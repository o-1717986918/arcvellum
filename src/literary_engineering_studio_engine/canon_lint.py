"""Project-level canon and plot consistency linting."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


SEVERITIES = {"blocking": 3, "warning": 2, "info": 1}


@dataclass(frozen=True)
class CanonLintIssue:
    check_id: str
    severity: str
    location: str
    message: str
    evidence: str = ""


@dataclass(frozen=True)
class CanonLintResult:
    project_root: Path
    report_path: Path
    json_path: Path
    issue_count: int
    blocking_count: int
    warning_count: int
    info_count: int
    status: str


def build_canon_lint(project_root: Path, output: Path | None = None, json_output: Path | None = None) -> CanonLintResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    issues: list[CanonLintIssue] = []
    _check_required_files(root, issues)
    facts = _check_facts(root, issues)
    character_ids, character_names = _check_characters(root, issues)
    scene_records = _check_scenes(root, issues, character_ids, character_names)
    _check_timeline(root, issues)
    _check_foreshadowing(root, issues, scene_records)
    _check_chapter_states(root, issues)
    _check_unconfirmed_candidates(root, issues, facts)

    issues.sort(key=lambda item: (-SEVERITIES.get(item.severity, 0), item.location, item.check_id))
    blocking_count = sum(1 for issue in issues if issue.severity == "blocking")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    info_count = sum(1 for issue in issues if issue.severity == "info")
    status = "blocked" if blocking_count else "pass_with_warnings" if warning_count else "pass"

    report_path = _resolve_output(root, output, "reviews", "canon_lint.md")
    json_path = _resolve_output(root, json_output, "reviews", "canon_lint.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/canon-lint/v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "status": status,
        "summary": {
            "issue_count": len(issues),
            "blocking_count": blocking_count,
            "warning_count": warning_count,
            "info_count": info_count,
        },
        "issues": [asdict(issue) for issue in issues],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(root, payload), encoding="utf-8")
    return CanonLintResult(
        project_root=root,
        report_path=report_path,
        json_path=json_path,
        issue_count=len(issues),
        blocking_count=blocking_count,
        warning_count=warning_count,
        info_count=info_count,
        status=status,
    )


def _check_required_files(root: Path, issues: list[CanonLintIssue]) -> None:
    required = [
        "project.yaml",
        "canon/world_rules.yaml",
        "canon/timeline.yaml",
        "canon/facts.json",
        "canon/locations.yaml",
        "canon/forbidden_changes.yaml",
        "plot/outline.md",
        "plot/foreshadowing.csv",
        "scenes/scene_0001.yaml",
    ]
    for rel in required:
        if not (root / rel).exists():
            _add(issues, "required-file", "blocking", rel, "缺少必需项目文件。")


def _check_facts(root: Path, issues: list[CanonLintIssue]) -> dict[str, object]:
    path = root / "canon" / "facts.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _add(issues, "facts-json", "blocking", "canon/facts.json", "canon facts JSON 无法解析。", str(exc))
        return {}
    conflicts = data.get("conflicts", [])
    candidates = data.get("candidates", [])
    if conflicts:
        _add(issues, "canon-conflicts", "blocking", "canon/facts.json", "存在未解决 canon conflicts。", str(len(conflicts)))
    if candidates:
        _add(issues, "canon-candidates", "warning", "canon/facts.json", "存在尚未人工确认的 canon candidates。", str(len(candidates)))
    if not isinstance(data.get("facts", []), list):
        _add(issues, "facts-shape", "blocking", "canon/facts.json", "`facts` 必须是数组。")
    return data


def _check_characters(root: Path, issues: list[CanonLintIssue]) -> tuple[set[str], set[str]]:
    chars_dir = root / "characters"
    character_ids: set[str] = set()
    character_names: set[str] = set()
    seen: dict[str, str] = {}
    files = sorted(path for path in chars_dir.glob("*.yaml") if not path.name.startswith("_")) if chars_dir.exists() else []
    if not files:
        _add(issues, "characters-empty", "warning", "characters/", "尚无正式人物档案。")
        return character_ids, character_names
    for path in files:
        rel = _rel(path, root)
        text = _read(path)
        cid = _scalar(text, "character_id")
        name = _scalar(text, "name")
        role = _scalar(text, "role")
        if not cid:
            _add(issues, "character-id-missing", "blocking", rel, "人物档案缺少 character_id。")
        else:
            if cid in seen:
                _add(issues, "character-id-duplicate", "blocking", rel, "人物 character_id 重复。", f"first={seen[cid]}")
            seen[cid] = rel
            character_ids.add(cid)
        if name:
            character_names.add(name)
        else:
            _add(issues, "character-name-missing", "warning", rel, "人物档案缺少 name。")
        if not role:
            _add(issues, "character-role-missing", "warning", rel, "人物档案缺少 role。")
        for key in ["belief", "desire", "intention"]:
            if not _nested_list_has_items(text, "bdi", key):
                _add(issues, f"character-bdi-{key}", "warning", rel, f"人物 BDI `{key}` 为空。", cid or name)
        if not _character_background_story_has_items(text):
            _add(issues, "character-background-story-missing", "warning", rel, "人物缺少 background_story 隐性背景故事。", cid or name)
    return character_ids, character_names


def _check_scenes(
    root: Path,
    issues: list[CanonLintIssue],
    character_ids: set[str],
    character_names: set[str],
) -> dict[str, dict[str, object]]:
    scene_dir = root / "scenes"
    records: dict[str, dict[str, object]] = {}
    files = sorted(path for path in scene_dir.glob("*.yaml") if not path.name.startswith("_")) if scene_dir.exists() else []
    if not files:
        _add(issues, "scenes-empty", "blocking", "scenes/", "未发现任何场景文件。")
        return records
    seen: dict[str, str] = {}
    for path in files:
        rel = _rel(path, root)
        text = _read(path)
        scene_id = _scalar(text, "scene_id") or path.stem
        chapter_id = _scalar(text, "chapter_id")
        status = _scalar(text, "status")
        location = _scalar(text, "location")
        participants = _list_after(text, "participants")
        records[scene_id] = {
            "path": rel,
            "chapter_id": chapter_id,
            "status": status,
            "participants": participants,
        }
        if scene_id in seen:
            _add(issues, "scene-id-duplicate", "blocking", rel, "场景 scene_id 重复。", f"first={seen[scene_id]}")
        seen[scene_id] = rel
        if not _scalar(text, "scene_id"):
            _add(issues, "scene-id-missing", "warning", rel, "场景缺少 scene_id，当前将使用文件名推断。")
        if not chapter_id:
            _add(issues, "scene-chapter-missing", "warning", rel, "场景缺少 chapter_id。", scene_id)
        if status not in {"planned", "drafting", "review", "ready", "blocked", "published"}:
            _add(issues, "scene-status-invalid", "warning", rel, "场景 status 未使用推荐状态。", status or "empty")
        if not location:
            _add(issues, "scene-location-missing", "warning", rel, "场景缺少 location。", scene_id)
        if not participants:
            _add(issues, "scene-participants-empty", "warning", rel, "场景 participants 为空。", scene_id)
        for participant in participants:
            if character_ids or character_names:
                if participant not in character_ids and participant not in character_names:
                    _add(issues, "scene-participant-unknown", "blocking", rel, "场景参与者未在人物档案中登记。", participant)
        if _list_after(text, "new_facts"):
            _add(issues, "scene-new-facts-candidate", "info", rel, "场景 output_state.new_facts 应进入人工确认候选。", scene_id)
    return records


def _check_timeline(root: Path, issues: list[CanonLintIssue]) -> None:
    path = root / "canon" / "timeline.yaml"
    if not path.exists():
        return
    text = _read(path)
    if re.search(r"(?m)^\s*events:\s*\[\s*\]\s*$", text) or not re.search(r"(?m)^\s*-\s+", text):
        _add(issues, "timeline-empty", "warning", "canon/timeline.yaml", "时间线 events 为空。")


def _check_foreshadowing(root: Path, issues: list[CanonLintIssue], scene_records: dict[str, dict[str, object]]) -> None:
    path = root / "plot" / "foreshadowing.csv"
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        _add(issues, "foreshadowing-empty", "info", "plot/foreshadowing.csv", "尚未登记伏笔。")
        return
    scene_ids = set(scene_records)
    for idx, row in enumerate(rows, 2):
        fid = (row.get("foreshadow_id") or "").strip()
        setup = (row.get("setup_scene") or "").strip()
        payoff = (row.get("expected_payoff") or "").strip()
        status = (row.get("status") or "").strip()
        location = f"plot/foreshadowing.csv:{idx}"
        if not fid:
            _add(issues, "foreshadow-id-missing", "blocking", location, "伏笔缺少 foreshadow_id。")
        if setup and scene_ids and setup not in scene_ids:
            _add(issues, "foreshadow-setup-missing", "warning", location, "伏笔 setup_scene 未匹配现有场景。", setup)
        if status not in {"", "planned", "active", "paid_off", "dropped"}:
            _add(issues, "foreshadow-status-invalid", "warning", location, "伏笔 status 不在推荐状态集合中。", status)
        if status == "paid_off" and not payoff:
            _add(issues, "foreshadow-payoff-missing", "warning", location, "已回收伏笔缺少 expected_payoff。", fid)


def _check_chapter_states(root: Path, issues: list[CanonLintIssue]) -> None:
    chapter_dir = root / "plot" / "chapters"
    if not chapter_dir.exists():
        return
    files = sorted(path for path in chapter_dir.glob("*.json"))
    if not files:
        _add(issues, "chapter-state-missing", "info", "plot/chapters/", "尚未生成章节状态 JSON。")
        return
    for path in files:
        rel = _rel(path, root)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            _add(issues, "chapter-json-invalid", "blocking", rel, "章节状态 JSON 无法解析。", str(exc))
            continue
        scenes = data.get("scenes", [])
        if not scenes:
            _add(issues, "chapter-scenes-empty", "warning", rel, "章节状态没有 scenes。")
        for scene in scenes:
            status = str(scene.get("status", ""))
            scene_id = str(scene.get("scene_id", ""))
            if status != "ready":
                _add(issues, "chapter-scene-not-ready", "warning", rel, "章节内存在未 ready 场景。", f"{scene_id}:{status}")


def _check_unconfirmed_candidates(root: Path, issues: list[CanonLintIssue], facts: dict[str, object]) -> None:
    confirmed_text = json.dumps(facts.get("facts", []), ensure_ascii=False)
    draft_dir = root / "drafts" / "scenes"
    if not draft_dir.exists():
        return
    for path in sorted(draft_dir.glob("*.md")):
        rel = _rel(path, root)
        candidates = _draft_candidates(_read(path))
        for candidate in candidates:
            if candidate and candidate in confirmed_text:
                _add(issues, "candidate-already-confirmed", "info", rel, "草稿候选事实疑似已在 canon facts 中确认。", candidate[:120])
            else:
                _add(issues, "draft-unconfirmed-candidate", "warning", rel, "草稿含尚未确认的写回候选。", candidate[:120])


def _draft_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for heading in ["### 新增事实候选", "### 人物状态变化", "### 关系变化", "### 伏笔变化", "### 需要人工确认"]:
        idx = text.find(heading)
        if idx < 0:
            continue
        next_idx = text.find("\n### ", idx + 1)
        if next_idx < 0:
            next_idx = text.find("\n## ", idx + 1)
        section = text[idx: next_idx if next_idx >= 0 else len(text)]
        for line in section.splitlines():
            stripped = line.strip()
            if stripped.startswith("-") and stripped.strip("- ").strip():
                candidates.append(stripped.strip("- ").strip())
    return candidates


def _render_report(root: Path, payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        "# Canon Lint Report",
        "",
        f"- 项目：`{root}`",
        f"- 生成时间：{payload['generated_at']}",
        f"- 状态：`{payload['status']}`",
        f"- 问题总数：{summary['issue_count']}",
        f"- Blocking：{summary['blocking_count']}",
        f"- Warning：{summary['warning_count']}",
        f"- Info：{summary['info_count']}",
        "",
        "## Issues",
        "",
    ]
    issues = payload["issues"]
    if not issues:
        lines.append("- 未发现问题。")
        return "\n".join(lines) + "\n"
    lines.extend(["| Severity | Check | Location | Message | Evidence |", "| --- | --- | --- | --- | --- |"])
    for issue in issues:
        lines.append(
            "| {severity} | `{check}` | `{location}` | {message} | {evidence} |".format(
                severity=issue["severity"],
                check=issue["check_id"],
                location=issue["location"],
                message=issue["message"],
                evidence=str(issue.get("evidence", "")).replace("|", "\\|"),
            )
        )
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 本报告只检查项目状态，不自动修改 canon。",
            "- Blocking 应在正式导出或发布前解决。",
            "- Warning 可进入人工审查队列，但不能被忽略。",
            "- Info 用于提醒仍需维护的工程事实。",
        ]
    )
    return "\n".join(lines) + "\n"


def _add(issues: list[CanonLintIssue], check_id: str, severity: str, location: str, message: str, evidence: str = "") -> None:
    issues.append(CanonLintIssue(check_id=check_id, severity=severity, location=location, message=message, evidence=evidence))


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return ""
    return match.group(1).strip().strip("\"'")


def _list_after(text: str, key: str) -> list[str]:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return []
    inline = match.group(1).strip()
    if inline.startswith("[") and inline.endswith("]"):
        return [item.strip().strip("\"'") for item in inline.strip("[]").split(",") if item.strip()]
    values: list[str] = []
    for line in text[match.end() :].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            values.append(stripped.strip("- ").strip("\"'"))
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
            break
    return values


def _nested_list_has_items(text: str, parent: str, key: str) -> bool:
    parent_match = re.search(rf"(?m)^[ \t]*{re.escape(parent)}:[ \t]*$", text)
    if not parent_match:
        return False
    section = text[parent_match.end() :]
    next_top = re.search(r"(?m)^[A-Za-z_][A-Za-z0-9_]*:", section)
    section = section[: next_top.start()] if next_top else section
    key_match = re.search(rf"(?m)^[ \t]+{re.escape(key)}:[ \t]*(.*?)[ \t]*$", section)
    if not key_match:
        return False
    inline = key_match.group(1).strip()
    if inline.startswith("[") and inline.endswith("]") and inline.strip("[] ").strip():
        return True
    for line in section[key_match.end() :].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-") and stripped.strip("- ").strip():
            return True
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
            break
    return False


def _character_background_story_has_items(text: str) -> bool:
    if _nested_scalar_has_value(text, "background_story", "summary"):
        return True
    for key in ["formative_events", "behavior_influences"]:
        if _nested_list_has_items(text, "background_story", key):
            return True
    return bool(_nested_scalar_has_value(text, "identity", "background"))


def _nested_scalar_has_value(text: str, parent: str, key: str) -> bool:
    parent_match = re.search(rf"(?m)^[ \t]*{re.escape(parent)}:[ \t]*$", text)
    if not parent_match:
        return False
    section = text[parent_match.end() :]
    next_top = re.search(r"(?m)^[A-Za-z_][A-Za-z0-9_]*:", section)
    section = section[: next_top.start()] if next_top else section
    key_match = re.search(rf"(?m)^[ \t]+{re.escape(key)}:[ \t]*(.*?)[ \t]*$", section)
    if not key_match:
        return False
    value = key_match.group(1).strip().strip("\"'")
    return value not in {"", "null", "[]", "{}"}
