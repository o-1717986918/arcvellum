"""Reusable pure-data fixtures for orchestration tests."""

from __future__ import annotations

from literary_engineering_studio.orchestration import CANDIDATE_SCHEMA


def scene_plan_candidate() -> dict:
    nodes = [
        _node("context", "context_preparation", []),
        _node("roleplay", "roleplay_simulation", ["context"]),
        _node("branches", "scene_branch_simulation", ["roleplay"]),
        _node("selection", "branch_selection", ["branches"]),
        _node("composition", "scene_composition", ["selection"]),
        _node(
            "prose",
            "formal_scene_prose",
            ["composition"],
            progress={
                "formal_artifact_delta": ["drafts/scenes/scene_0001.md@promoted"],
                "target_hanzi": 1800,
            },
        ),
        _node("review", "formal_scene_review", ["prose"]),
        _node(
            "state",
            "state_evolution",
            ["review"],
            progress={
                "expected_state_patch": "characters/state_patches/scene_0001_state_patch.json",
            },
        ),
    ]
    return {
        "schema": CANDIDATE_SCHEMA,
        "scope": {
            "kind": "chapter",
            "key": "chapter_01",
            "chapter_ids": ["chapter_01"],
            "scene_ids": ["scene_0001"],
        },
        "objective": "完成第一章首场并形成可验证的人物状态变化。",
        "interpretation": {
            "dramatic_problem": "主角必须在不完全信息下作出承诺。",
            "reader_effect": "让读者意识到这份承诺会带来后续代价。",
            "chapter_function": "建立主角的行动义务。",
            "assumptions": [
                {
                    "statement": "主角尚未知道对方的真实身份。",
                    "evidence_refs": ["canon/timeline.yaml"],
                }
            ],
            "uncertainties": ["对方是否会兑现交换条件。"],
        },
        "strategy": {
            "scene_inventory": [
                {
                    "scene_ref": "scene_0001",
                    "function": "commitment",
                    "pace": "slow_to_fast",
                    "roleplay_depth": "targeted",
                }
            ],
            "branch_count": 3,
            "revision_policy": "targeted_then_rewrite",
            "narrative_distance": "close_to_medium",
            "promise_policy": {"resolve": [], "defer": ["promise_0001"]},
        },
        "task_nodes": nodes,
        "replan_rules": [
            {
                "trigger": "review_failed",
                "threshold": 2,
                "action": "reconsider_branch_or_rewrite",
            }
        ],
        "freedom_request": freedom_budget(),
    }


def freedom_budget() -> dict:
    return {
        "max_added_tasks": 8,
        "max_replans_per_scope": 2,
        "max_parallel_read_tasks": 3,
        "max_branch_count": 5,
        "max_research_tasks": 2,
        "max_research_cost": 5.0,
        "max_analysis_to_production_ratio": 1.0,
        "max_plan_depth": 32,
        "max_plan_stall_cycles": 2,
    }


def _node(
    node_id: str,
    kind: str,
    depends_on: list[str],
    *,
    progress: dict | None = None,
) -> dict:
    progress_payload = {
        "formal_artifact_delta": [],
        "obligations_fulfilled": [],
        "obligations_deferred": [],
        "target_hanzi": 0,
        "word_tolerance": 0.08,
        "maximum_open_review_notes": 0,
        "expected_state_patch": "",
        **(progress or {}),
    }
    return {
        "node_id": node_id,
        "kind": kind,
        "scope_refs": ["scene_0001"],
        "depends_on": depends_on,
        "requested_capabilities": ["project.query"],
        "parameters": {},
        "contribution": {
            "kind": "formal" if kind == "formal_scene_prose" else "evidence",
            "description": f"{node_id} contributes a verified plan artifact.",
        },
        "progress_contract": progress_payload,
    }
