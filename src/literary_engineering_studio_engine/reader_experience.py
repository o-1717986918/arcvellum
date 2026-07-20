"""Reader-experience and chapter-obligation contracts for long-form scenes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from .agent_tasks import agent_task_completion_status, write_agent_tasks
from .text_counts import CHINESE_CONTENT_COUNT_UNIT, MACHINE_NONSPACE_COUNT_UNIT


CHAPTER_OBLIGATION_SCHEMA = "literary-engineering-workbench/chapter-obligation-contract/v1"
READER_EXPERIENCE_SCHEMA = "literary-engineering-workbench/reader-experience-contract/v1"
REQUIRED_CHAPTER_FIELDS = (
    "chapter_function",
    "must_payoff",
    "must_setup",
    "must_change",
    "must_not_resolve",
    "inherited_hooks",
    "ending_hook",
    "inventory_sufficiency",
)
REQUIRED_READER_FIELDS = (
    "reader_question",
    "promised_reward",
    "withheld_information",
    "payoff_or_delay",
    "emotional_curve",
    "tension_source",
    "curiosity_hook",
    "freshness_requirement",
    "anti_summary_requirement",
    "reader_aftertaste",
)


@dataclass(frozen=True)
class ChapterObligationResult:
    project_root: Path
    chapter_id: str
    markdown_path: Path
    json_path: Path
    agent_tasks_path: Path
    status: str


def build_chapter_obligation_tasks(
    project_root: Path,
    *,
    chapter_id: str = "",
    output: Path | None = None,
    json_output: Path | None = None,
    agent_tasks_output: Path | None = None,
) -> ChapterObligationResult:
    """Create a platform-agent task sidecar for a chapter-level reader contract."""

    root = project_root.resolve()
    if not (root / "project.yaml").exists():
        raise FileNotFoundError(f"work project not found: {root}")
    resolved_chapter = chapter_id.strip() or _first_chapter_id(root) or "chapter_0001"
    obligation_dir = root / "plot" / "chapter_obligations"
    markdown_path = _resolve_output(root, output, obligation_dir, f"{resolved_chapter}.md")
    json_path = _resolve_output(root, json_output, obligation_dir, f"{resolved_chapter}.json")
    task_path = _resolve_output(root, agent_tasks_output, obligation_dir, f"{resolved_chapter}.agent_tasks.md")
    obligation_dir.mkdir(parents=True, exist_ok=True)

    existing = _read_json(json_path) if json_path.exists() else {}
    if existing.get("schema") == CHAPTER_OBLIGATION_SCHEMA and str(existing.get("chapter_id") or "") == resolved_chapter:
        payload = existing
    else:
        payload = _chapter_obligation_scaffold(root, resolved_chapter, json_path)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_obligation_markdown(root, payload, json_path), encoding="utf-8")
    _write_chapter_obligation_agent_tasks(root, resolved_chapter, markdown_path, json_path, task_path, payload)
    return ChapterObligationResult(
        project_root=root,
        chapter_id=resolved_chapter,
        markdown_path=markdown_path,
        json_path=json_path,
        agent_tasks_path=task_path,
        status=str(payload.get("status") or "needs_agent"),
    )


def chapter_obligation_path(root: Path, obligation_id: str) -> Path:
    return root.resolve() / "plot" / "chapter_obligations" / f"{obligation_id}.json"


def scene_chapter_obligation_id(root: Path, scene_path: Path) -> str:
    scene_path = scene_path if scene_path.is_absolute() else root / scene_path
    text = _read(scene_path)
    return _scalar(text, "chapter_obligation_id") or _scalar(text, "chapter_id") or "unassigned"


def chapter_obligation_contract(root: Path, scene_path: Path) -> dict[str, Any]:
    """Return the chapter-level promise/payoff contract that governs a scene."""

    root = root.resolve()
    scene_path = scene_path if scene_path.is_absolute() else root / scene_path
    scene_text = _read(scene_path)
    scene_id = _scalar(scene_text, "scene_id") or scene_path.stem
    chapter_id = _scalar(scene_text, "chapter_id") or "unassigned"
    obligation_id = _scalar(scene_text, "chapter_obligation_id") or chapter_id
    required = _reader_contract_required(root, scene_text)
    path = chapter_obligation_path(root, obligation_id)
    base: dict[str, Any] = {
        "schema": CHAPTER_OBLIGATION_SCHEMA,
        "scene_id": scene_id,
        "chapter_id": chapter_id,
        "chapter_obligation_id": obligation_id,
        "required": required,
        "path": _rel(path, root),
        "status": "not_required",
        "message": "chapter obligation contract is not required for this project scale",
        "count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "machine_count_unit": MACHINE_NONSPACE_COUNT_UNIT,
        "target_chinese_chars": 0,
        "scene_count_target": 0,
        "issues": [],
        "contract": {},
    }
    if not required:
        return base
    if chapter_id == "unassigned":
        base.update({"status": "missing_chapter", "message": "scene.yaml must have chapter_id before reader-experience contract"})
        return base
    if not path.exists():
        base.update({"status": "missing", "message": f"chapter obligation JSON missing: {_rel(path, root)}"})
        return base
    payload = _read_json(path)
    if not payload:
        base.update({"status": "invalid", "message": f"chapter obligation JSON is invalid: {_rel(path, root)}"})
        return base
    if payload.get("schema") != CHAPTER_OBLIGATION_SCHEMA:
        base.update({"status": "invalid", "message": f"chapter obligation schema mismatch: {payload.get('schema') or 'missing'}"})
        return base
    if str(payload.get("chapter_id") or "") != chapter_id:
        base.update({"status": "invalid", "message": f"chapter obligation chapter_id mismatch: expected {chapter_id}"})
        return base
    issues = _chapter_contract_issues(payload)
    task_path = path.with_suffix(".agent_tasks.md")
    completion = agent_task_completion_status(task_path, root=root)
    if completion.get("complete") is not True:
        issues.append(f"chapter obligation sidecar incomplete: {completion.get('message')}")
    status = str(payload.get("status") or "").strip().lower()
    if status not in {"pass", "ready"}:
        issues.append(f"chapter obligation status must be pass/ready, got {status or 'missing'}")
    base.update(
        {
            "status": "pass" if not issues else "incomplete",
            "message": "chapter obligation contract is ready" if not issues else "; ".join(issues),
            "target_chinese_chars": _to_int(payload.get("target_chinese_chars") or payload.get("target_words")),
            "scene_count_target": _to_int(payload.get("scene_count_target") or payload.get("target_scene_count")),
            "issues": issues,
            "contract": payload,
        }
    )
    return base


def reader_experience_contract(root: Path, scene_path: Path) -> dict[str, Any]:
    """Return the scene-level reader question, promise, tension, and payoff contract."""

    root = root.resolve()
    scene_path = scene_path if scene_path.is_absolute() else root / scene_path
    scene_text = _read(scene_path)
    scene_id = _scalar(scene_text, "scene_id") or scene_path.stem
    chapter_contract = chapter_obligation_contract(root, scene_path)
    if chapter_contract["status"] == "not_required":
        return {
            "schema": READER_EXPERIENCE_SCHEMA,
            "scene_id": scene_id,
            "status": "not_required",
            "message": "reader-experience contract is not required for this project scale",
            "required": False,
            "chapter_obligation": chapter_contract,
            "reader_experience": {},
            "issues": [],
        }
    if chapter_contract["status"] != "pass":
        return {
            "schema": READER_EXPERIENCE_SCHEMA,
            "scene_id": scene_id,
            "status": "blocked",
            "message": f"chapter obligation is not ready: {chapter_contract.get('message')}",
            "required": True,
            "chapter_obligation": chapter_contract,
            "reader_experience": {},
            "issues": [str(chapter_contract.get("message") or "chapter obligation not ready")],
        }
    payload = chapter_contract.get("contract") if isinstance(chapter_contract.get("contract"), dict) else {}
    scene_contract = _scene_reader_contract(payload, scene_id)
    if not scene_contract:
        scene_contract = _scene_yaml_reader_contract(scene_text)
    issues = _reader_contract_issues(scene_contract)
    return {
        "schema": READER_EXPERIENCE_SCHEMA,
        "scene_id": scene_id,
        "status": "pass" if not issues else "incomplete",
        "message": "reader-experience contract is ready" if not issues else "; ".join(issues),
        "required": True,
        "chapter_obligation": chapter_contract,
        "reader_experience": scene_contract,
        "issues": issues,
    }


def ensure_reader_experience_ready(root: Path, scene_path: Path) -> dict[str, Any]:
    contract = reader_experience_contract(root, scene_path)
    if contract.get("status") in {"pass", "not_required"}:
        return contract
    raise ValueError(
        "formal scene generation requires a ready reader-experience contract: "
        f"{contract.get('message')}. Run chapter-obligation, let the platform agent fill the chapter/scene promise-payoff contract, "
        "create its completion marker, then retry."
    )


def render_reader_experience_contract(root: Path, scene_path: Path) -> str:
    contract = reader_experience_contract(root, scene_path)
    status = str(contract.get("status") or "")
    if status == "not_required":
        return "本项目当前未达到强制读者体验契约规模；仍应让每场有明确读者问题、承诺、推进和余味。"
    if status != "pass":
        return f"本场景读者体验门禁未通过：{contract.get('message')}"
    chapter = contract.get("chapter_obligation") if isinstance(contract.get("chapter_obligation"), dict) else {}
    obligation = chapter.get("contract") if isinstance(chapter.get("contract"), dict) else {}
    reader = contract.get("reader_experience") if isinstance(contract.get("reader_experience"), dict) else {}
    lines = [
        f"- 场景：{contract.get('scene_id')}",
        f"- 章节义务：{chapter.get('path')}",
        f"- 章节功能：{obligation.get('chapter_function') or '未填写'}",
        f"- 章节目标中文内容字符：{obligation.get('target_chinese_chars') or chapter.get('target_chinese_chars') or 0}",
        f"- 本场读者问题：{reader.get('reader_question') or '未填写'}",
        f"- 本场承诺回报：{reader.get('promised_reward') or '未填写'}",
        f"- 暂扣信息：{_join(reader.get('withheld_information'))}",
        f"- 兑现或延迟：{reader.get('payoff_or_delay') or '未填写'}",
        f"- 情绪曲线：{_join(reader.get('emotional_curve'))}",
        f"- 张力来源：{reader.get('tension_source') or '未填写'}",
        f"- 好奇钩子：{reader.get('curiosity_hook') or '未填写'}",
        f"- 新鲜度要求：{reader.get('freshness_requirement') or '未填写'}",
        f"- 反摘要要求：{reader.get('anti_summary_requirement') or '未填写'}",
        f"- 读后余味：{reader.get('reader_aftertaste') or '未填写'}",
    ]
    return "\n".join(lines)


def reader_experience_adherence_for_body(root: Path, scene_path: Path, body: str) -> dict[str, Any]:
    """Return deterministic evidence for agent review; semantics remain platform-agent work."""

    contract = reader_experience_contract(root, scene_path)
    status = str(contract.get("status") or "")
    if status in {"not_required", "pass"}:
        return {
            "status": status,
            "message": contract.get("message", ""),
            "requires_platform_agent_semantic_review": status == "pass",
            "clean_body_present": bool(str(body or "").strip()),
            "contract": contract.get("reader_experience", {}),
            "chapter_obligation_path": (contract.get("chapter_obligation") or {}).get("path", "") if isinstance(contract.get("chapter_obligation"), dict) else "",
        }
    return {
        "status": "revise_required",
        "message": contract.get("message", ""),
        "requires_platform_agent_semantic_review": True,
        "clean_body_present": bool(str(body or "").strip()),
        "contract": {},
    }


def _chapter_obligation_scaffold(root: Path, chapter_id: str, json_path: Path) -> dict[str, Any]:
    budget = _read_json(root / "plot" / "word_budget" / "word_budget.json")
    row = _chapter_budget_row(budget, chapter_id)
    scenes = _scenes_for_chapter(root, chapter_id)
    target = _to_int(row.get("target_words"))
    scene_count = _to_int(row.get("target_scene_count") or row.get("scene_count")) or max(len(scenes), 1)
    avg_scene = _to_int(row.get("avg_scene_words")) or round(target / max(scene_count, 1)) if target else 0
    return {
        "schema": CHAPTER_OBLIGATION_SCHEMA,
        "generated_at": _now(),
        "chapter_id": chapter_id,
        "status": "needs_agent",
        "count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "machine_count_unit": MACHINE_NONSPACE_COUNT_UNIT,
        "target_chinese_chars": target,
        "scene_count_target": scene_count,
        "chapter_function": "",
        "must_payoff": [],
        "must_setup": [],
        "must_change": [],
        "must_not_resolve": [],
        "inherited_hooks": [],
        "ending_hook": "",
        "inventory_sufficiency": "",
        "expansion_needed": [],
        "reader_experience_by_scene": [
            {
                "scene_id": scene["scene_id"],
                "word_count_target": _to_int(scene.get("word_count_target")) or avg_scene,
                "word_count_min": _to_int(scene.get("word_count_min")) or (round(avg_scene * 0.85) if avg_scene else 0),
                "word_count_max": _to_int(scene.get("word_count_max")) or (round(avg_scene * 1.25) if avg_scene else 0),
                "reader_question": "",
                "promised_reward": "",
                "withheld_information": [],
                "payoff_or_delay": "",
                "emotional_curve": [],
                "tension_source": "",
                "curiosity_hook": "",
                "freshness_requirement": "",
                "anti_summary_requirement": "",
                "reader_aftertaste": "",
            }
            for scene in scenes
        ],
        "source_paths": [
            "project.yaml",
            "plot/word_budget/word_budget.json",
            "plot/outline.md",
            "scenes/",
        ],
        "output_path": _rel(json_path, root),
    }


def _write_chapter_obligation_agent_tasks(
    root: Path,
    chapter_id: str,
    markdown_path: Path,
    json_path: Path,
    task_path: Path,
    payload: dict[str, Any],
) -> None:
    source_paths = [root / "project.yaml", json_path, markdown_path, root / "plot" / "word_budget" / "word_budget.json", root / "plot" / "outline.md"]
    source_paths.extend(path for path in sorted((root / "scenes").glob("*.yaml")) if _scalar(_read(path), "chapter_id") == chapter_id)
    write_agent_tasks(
        task_path,
        title=f"chapter-obligation {chapter_id}",
        root=root,
        source_paths=[path for path in source_paths if path.exists()],
        notes=[
            "这是章节义务与读者体验门禁任务。",
            "CLI 只写脚手架和校验字段；章节功能、悬念承诺、兑现/延迟和读者余味必须由平台 agent 判断。",
            "本契约用于 compose-scene、generate-scene、AgentReview、route-audit 和 longform-audit，不是可选说明。",
        ],
        tasks=[
            (
                "填写章节义务契约",
                f"""读取 word_budget、outline、已有 scenes 和上下文，创建或覆盖 `{_rel(json_path, root)}`。将 status 改为 pass，并完整填写 chapter_function、must_payoff、must_setup、must_change、must_not_resolve、inherited_hooks、ending_hook、inventory_sufficiency、expansion_needed。目标字数口径必须是中文内容字符，机器非空白字符只能作诊断。""",
            ),
            (
                "填写逐场读者体验契约",
                """在 reader_experience_by_scene 中逐场填写 reader_question、promised_reward、withheld_information、payoff_or_delay、emotional_curve、tension_source、curiosity_hook、freshness_requirement、anti_summary_requirement、reader_aftertaste。每场都必须说明“读者为什么继续读”“本场兑现什么或延迟什么”“正文不能写成摘要的具体办法”。""",
            ),
            (
                "写入章节义务说明",
                f"""创建或覆盖 `{_rel(markdown_path, root)}`，用可读 Markdown 总结本章承诺、每场读者问题、兑现/延迟、字数-剧情量关系和需要用户确认的点。不要把本文件写成正文，也不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )


def _render_obligation_markdown(root: Path, payload: dict[str, Any], json_path: Path) -> str:
    lines = [
        f"# 章节义务与读者体验契约：{payload.get('chapter_id', '')}",
        "",
        f"- JSON：`{_rel(json_path, root)}`",
        f"- 状态：`{payload.get('status', '')}`",
        f"- 目标中文内容字符：{payload.get('target_chinese_chars', 0)}",
        f"- 目标场景数：{payload.get('scene_count_target', 0)}",
        "- 计数口径：中文内容字符，计入汉字和中文标点；机器非空白字符仅作诊断。",
        "",
        "## 平台 Agent 待完成",
        "",
        "- 填写章节功能、必须兑现、必须设置、必须变化、暂不解决、继承钩子和章末钩子。",
        "- 为每个场景写清读者问题、承诺回报、暂扣信息、兑现或延迟、情绪曲线、张力来源、新鲜度、反摘要要求和读后余味。",
        "- 完成后将 JSON `status` 改为 `pass`，并创建同名 `.agent_completion.json`。",
        "",
        "## 场景清单",
        "",
        "| 场景 | 目标中文内容字符 | 读者问题 | 兑现或延迟 |",
        "| --- | ---: | --- | --- |",
    ]
    for scene in payload.get("reader_experience_by_scene", []) if isinstance(payload.get("reader_experience_by_scene"), list) else []:
        if not isinstance(scene, dict):
            continue
        lines.append(
            "| {scene} | {target} | {question} | {payoff} |".format(
                scene=scene.get("scene_id", ""),
                target=scene.get("word_count_target", 0),
                question=scene.get("reader_question", "") or "待平台 Agent 填写",
                payoff=scene.get("payoff_or_delay", "") or "待平台 Agent 填写",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _reader_contract_required(root: Path, scene_text: str) -> bool:
    project_text = _read(root / "project.yaml")
    project_target = _to_int(_scalar(project_text, "target_length") or _scalar(project_text, "target_words"))
    budget = _read_json(root / "plot" / "word_budget" / "word_budget.json")
    target = budget.get("target") if isinstance(budget.get("target"), dict) else {}
    budget_target = _to_int(target.get("target_chinese_chars") or target.get("target_words"))
    return project_target >= 100000 or budget_target >= 100000 or bool(_scalar(scene_text, "chapter_obligation_id"))


def _chapter_contract_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for field in REQUIRED_CHAPTER_FIELDS:
        value = payload.get(field)
        if value in ("", None, [], {}):
            issues.append(f"chapter obligation field missing: {field}")
    scenes = payload.get("reader_experience_by_scene")
    if not isinstance(scenes, list) or not scenes:
        issues.append("reader_experience_by_scene must contain at least one scene contract")
    return issues


def _reader_contract_issues(payload: dict[str, Any]) -> list[str]:
    if not payload:
        return ["reader experience contract missing for scene"]
    issues = []
    for field in REQUIRED_READER_FIELDS:
        value = payload.get(field)
        if value in ("", None, [], {}):
            issues.append(f"reader experience field missing: {field}")
    return issues


def _scene_reader_contract(payload: dict[str, Any], scene_id: str) -> dict[str, Any]:
    rows = payload.get("reader_experience_by_scene")
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and str(row.get("scene_id") or "") == scene_id:
            return row
    return {}


def _scene_yaml_reader_contract(scene_text: str) -> dict[str, Any]:
    block = _mapping_block(scene_text, "reader_experience")
    if not block:
        return {}
    data: dict[str, Any] = {}
    for field in REQUIRED_READER_FIELDS:
        values = _nested_list(block, field)
        data[field] = values if values else _nested_scalar(block, field)
    return data


def _scenes_for_chapter(root: Path, chapter_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scene_dir = root / "scenes"
    if not scene_dir.exists():
        return rows
    for path in sorted(scene_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = _read(path)
        if (_scalar(text, "chapter_id") or "unassigned") != chapter_id:
            continue
        rows.append(
            {
                "scene_id": _scalar(text, "scene_id") or path.stem,
                "word_count_target": _to_int(_scalar(text, "word_count_target")),
                "word_count_min": _to_int(_scalar(text, "word_count_min")),
                "word_count_max": _to_int(_scalar(text, "word_count_max")),
            }
        )
    return rows


def _first_chapter_id(root: Path) -> str:
    scene_dir = root / "scenes"
    if scene_dir.exists():
        for path in sorted(scene_dir.glob("*.yaml")):
            text = _read(path)
            chapter_id = _scalar(text, "chapter_id")
            if chapter_id:
                return chapter_id
    return ""


def _chapter_budget_row(payload: dict[str, Any], chapter_id: str) -> dict[str, Any]:
    for key in ("scene_inventory_binding",):
        binding = payload.get(key) if isinstance(payload.get(key), dict) else {}
        rows = binding.get("chapter_rows") if isinstance(binding, dict) else []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and str(row.get("chapter_id") or "") == chapter_id:
                    return row
    rows = payload.get("chapter_budgets")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and str(row.get("chapter_id") or "") == chapter_id:
                return row
    return {}


def _mapping_block(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*\n", text)
    if not match:
        return ""
    lines: list[str] = []
    for raw in text[match.end() :].splitlines():
        if raw and not raw.startswith((" ", "\t")):
            break
        lines.append(raw)
    return "\n".join(lines)


def _nested_scalar(block: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]+{re.escape(key)}:[ \t]*(.*?)[ \t]*$", block)
    if not match:
        return ""
    value = match.group(1).strip().strip("\"'")
    return "" if value in {"", "null", "[]", "{}"} else value


def _nested_list(block: str, key: str) -> list[str]:
    value = _nested_scalar(block, key)
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("\"'") for item in value.strip("[]").split(",") if item.strip()]
    match = re.search(rf"(?m)^[ \t]+{re.escape(key)}:[ \t]*\n", block)
    if not match:
        return []
    values: list[str] = []
    for raw in block[match.end() :].splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if re.match(r"^[A-Za-z_][\w-]*:", stripped):
            break
        if stripped.startswith("-"):
            item = stripped[1:].strip().strip("\"'")
            if item:
                values.append(item)
    return values


def _resolve_output(root: Path, output: Path | None, *default_parts: str | Path) -> Path:
    if output:
        return output if output.is_absolute() else root / output
    path = root
    for part in default_parts:
        path = path / part
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return ""
    value = match.group(1).strip().strip("\"'")
    return "" if value in {"", "null", "[]", "{}"} else value


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _join(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value if str(item).strip()) or "未填写"
    return str(value or "未填写")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
