"""Agent sidecars for evidence-bounded archaeology extraction units."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...agent_tasks import write_agent_tasks
from .entities import CHUNK_EXTRACTION_SCHEMA


def write_chunk_extraction_tasks(
    *,
    root: Path,
    staging_dir: Path,
    manifest: dict[str, Any],
) -> tuple[Path, ...]:
    plan = manifest.get("archaeology")
    tasks = plan.get("chunk_tasks") if isinstance(plan, dict) else []
    if not isinstance(tasks, list):
        return ()
    written: list[Path] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        written.append(
            _write_chunk_task(
                root=root,
                staging_dir=staging_dir,
                task=task,
            )
        )
    return tuple(written)


def _write_chunk_task(
    *,
    root: Path,
    staging_dir: Path,
    task: dict[str, Any],
) -> Path:
    chunk_id = str(task.get("chunk_id") or "")
    task_path = str(task.get("task_path") or "")
    expected_output = str(task.get("expected_output") or "")
    evidence_refs = [str(item) for item in task.get("source_evidence_refs") or []]
    logical_task = root / task_path
    staged_task = staging_dir / _inside_import(task_path)
    source_paths = [
        root / "project.yaml",
        root / "sources" / "imports" / str(task.get("work_id") or "") / "source_manifest.json",
        root / "sources" / "imports" / str(task.get("work_id") or "") / "evidence_index.json",
        root / str(task.get("source_chunk_path") or ""),
    ]
    write_agent_tasks(
        staged_task,
        title=f"Project Archaeology chunk extraction {chunk_id}",
        root=root,
        source_paths=source_paths,
        notes=[
            "本任务只分析一个不可变 source chunk；不得搜索或读取任务包之外的项目文件。",
            "所有实体、事件、关系、主张都只是候选证据，不是 Canon。",
            "同名不等于同一实体；只记录观察，不在块内臆断全书共指。",
            "未知、矛盾和不完整信息必须保留，不能以多数表述替代证据判断。",
        ],
        tasks=[
            (
                "提取块内候选",
                _chunk_contract_instruction(
                    chunk_id=chunk_id,
                    expected_output=expected_output,
                    evidence_revision=str(task.get("evidence_revision") or ""),
                    source_chunk_path=str(task.get("source_chunk_path") or ""),
                    evidence_refs=evidence_refs,
                ),
            )
        ],
        identity_path=logical_task,
    )
    return staged_task


def _chunk_contract_instruction(
    *,
    chunk_id: str,
    expected_output: str,
    evidence_revision: str,
    source_chunk_path: str,
    evidence_refs: list[str],
) -> str:
    refs = ", ".join(f'"{item}"' for item in evidence_refs)
    return f"""读取当前 chunk 及 evidence index，创建 `{expected_output}`。输出 UTF-8 JSON，不得使用 Markdown 围栏。

机器合同：
- `schema`、`work_id`、`chunk_id`、`source_chunk_path`、`source_chunk_sha256`、`evidence_revision` 和 `status` 是 Studio Worker 按当前任务包写入的机器身份；不得猜测、改写或用文学判断替代。
- 当前任务身份是 chunk `{chunk_id}`，source path `{source_chunk_path}`，evidence revision `{evidence_revision}`，schema `{CHUNK_EXTRACTION_SCHEMA}`。
- 根节点必须包含 `entities`、`events`、`relations`、`claims` 四个数组。
- 每个候选必须有块内唯一 `candidate_id`、0 到 1 的 `confidence`、非空 `evidence_refs`、`unknowns` 和 `contradiction_notes` 数组。
- 只可使用这些 evidence id：[{refs}]。
- 实体必须有 `entity_type`、`name`、`aliases`、`attributes`；属性本身也要有 `key`、`value`、`confidence`、`evidence_refs`。
- 事件必须有 `summary`、`participant_refs`、`temporal_constraints`、`causes`、`effects`。
- before/after/same_time 时间约束必须指向本块事件；absolute/relative/within 约束必须有 value；每条时间约束必须有 evidence_refs。
- 关系必须用 `source_entity_id` 和 `target_entity_id` 指向本块实体。
- 主张必须用 `subject_ref` 指向本块实体或事件，并写 `domain`、`predicate`、`value`。
- 没有可靠候选时保留空数组，不能编造填充。"""


def _inside_import(relative: str) -> Path:
    parts = Path(relative.replace("\\", "/")).parts
    try:
        index = parts.index("imports")
    except ValueError as exc:
        raise ValueError(f"chunk task path is outside source import: {relative}") from exc
    suffix = parts[index + 2 :]
    if not suffix or ".." in suffix:
        raise ValueError(f"invalid chunk task path: {relative}")
    return Path(*suffix)
