"""Shared controlled-Agent fixtures for formal scene lifecycle tests."""

from __future__ import annotations

import json
from pathlib import Path

from literary_engineering_studio_engine.agent_tasks import (
    write_agent_completion_marker,
    write_agent_tasks,
)
from literary_engineering_studio_engine.creative_quality import (
    load_creative_quality_profile,
)
from literary_engineering_studio_engine.platform_agent_tasks import (
    write_platform_scene_review_task,
)
from literary_engineering_studio_engine.projects.demo import build_demo_project


def prepare_promotable_candidate(root: Path) -> tuple[Path, Path]:
    """Build a demo project with one controlled, independently reviewed candidate."""

    build_demo_project(root, title="晋升端到端回归", run_agent_workflow=False)
    scene = root / "scenes" / "scene_0001.yaml"
    context = root / "memory" / "context_packets" / "scene_0001.md"
    context_trace = root / "memory" / "context_packets" / "scene_0001.trace.json"
    candidate = root / "drafts" / "candidates" / "scene_0001-platform-agent.md"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(
        candidate_text(
            "林舟把手电压低，等巡逻灯从街口滑过去，才推开旧楼的门。"
            "门轴没有响，楼道里却有一截电流声。"
        ),
        encoding="utf-8",
    )
    profile = load_creative_quality_profile(root)
    prompt_manifest = candidate.with_suffix(".prompt.json")
    prompt_manifest.write_text(
        json.dumps(
            {
                "context": context.relative_to(root).as_posix(),
                "context_trace": context_trace.relative_to(root).as_posix(),
                "generation_standards": {
                    "creative_quality_profile_digest": profile["digest"],
                    "narrative_rhythm_contract": {
                        "status": "defaulted",
                        "plan_digest": "",
                    },
                    "reader_experience_contract": {"status": "not_required"},
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    generation_task = candidate.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        generation_task,
        title="确定性晋升测试：正文候选",
        root=root,
        source_paths=[scene, context, prompt_manifest],
        tasks=[("正文候选", "写入候选正文和候选 manifest；不要绕过审查。")],
    )
    write_agent_completion_marker(
        generation_task,
        root=root,
        handled_by="deterministic-writer-fixture",
    )
    candidate_manifest = {
        "schema": "literary-engineering-workbench/scene-candidate/v1",
        "formal_contract_revision": "2026-07-23.3",
        "generated_by": "platform-agent",
        "provider": "tool-layer-agent",
        "candidate": candidate.relative_to(root).as_posix(),
        "writer_session_id": "writer-e2e",
        "prompt_manifest": prompt_manifest.relative_to(root).as_posix(),
        "style_generation_standard_applied": True,
        "hard_constraints_applied": True,
        "anti_evasion_protocol_applied": True,
        "narrative_rhythm_standard_applied": True,
        "word_budget_standard_applied": False,
        "pass_with_notes_actions_applied": False,
        "creative_quality_profile_digest": profile["digest"],
        "canon_writeback": {
            "canon_change": False,
            "no_canon_change_reason": "本场仅推进已登记的旧楼线索，没有新增正式世界规则。",
        },
        "new_character_register": new_character_register("existing_only"),
    }
    candidate.with_suffix(".json").write_text(
        json.dumps(candidate_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    review_result = write_platform_scene_review_task(
        root,
        scene_path=scene,
        draft_path=candidate,
        materialization_scope="scene",
    )
    review = review_result.expected_json_path
    review_task = review_result.task_path
    review_payload = {
        "schema": "literary-engineering-workbench/scene-review-agent/v1",
        "scene_id": "scene_0001",
        "candidate": candidate.relative_to(root).as_posix(),
        "candidate_sha256": _sha256(candidate),
        "conclusion": "pass",
        "summary": "候选正文与当前场景目标、节奏和已知人物状态一致。",
        "blocking_issues": [],
        "warnings": [],
        "revision_actions": [],
        "character_logic": [],
        "canon_risks": [],
        "style_notes": [],
        "style_adherence": {
            "status": "pass",
            "deviations": [],
            "revision_actions": [],
        },
        "word_budget_adherence": {
            "status": "not_required",
            "narrative_load_satisfied": True,
        },
        "reader_experience_adherence": {
            "status": "not_required",
            "reader_promise_satisfied": True,
        },
        "narrative_rhythm_adherence": {
            "status": "not_applicable",
            "rhythm_executed": True,
            "bridge_executed": True,
        },
        "canon_writeback": {
            "status": "not_required",
            "canon_change": False,
            "no_canon_change_reason": "本场不确认新的世界规则。",
        },
        "new_character_register": new_character_register("existing_only"),
        "revision_integrity": {
            "status": "not_applicable",
            "anti_evasion_checked": True,
            "evasion_risks_unresolved": [],
        },
        "source_paths": [candidate.relative_to(root).as_posix()],
        "creative_quality_profile": {"digest": profile["digest"]},
        "reviewer_session_id": "reviewer-e2e",
    }
    review.write_text(
        json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    review.with_suffix(".md").write_text(
        "# 独立审查\n\n结论：通过。\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(
        review_task,
        root=root,
        handled_by="deterministic-reviewer-fixture",
    )
    return root, candidate


def candidate_text(body: str) -> str:
    return (
        "# scene_0001 候选正文\n\n"
        "## 正文候选\n\n"
        f"{body}\n\n"
        "### 新增事实候选\n\n- 无。\n\n"
        "### 人物状态变化\n\n- 林舟决定进入旧楼。\n\n"
        "### 关系变化\n\n- 无。\n\n"
        "### 伏笔变化\n\n- 楼道电流声成为待查线索。\n\n"
        "### 需要人工确认\n\n- 无。\n"
    )


def new_character_register(status: str) -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/new-character-register/v0.1",
        "status": status,
        "introduced": [],
        "ephemeral_waivers": [],
        "blocking_issues": [],
    }


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
