"""Replay frozen actor task sheets with only the initialization voice changed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from literary_engineering_studio.application.config import load_config
from literary_engineering_studio.runtime.role_conversation import RoleConversationGateway


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "build/scene-performance-e2e/role-init-creative-test-20260924"
OUTPUT = ROOT / "build/scene-performance-e2e/role-init-archetype-task-sheet-rerun-20260924"
ACTORS = {
    "周岑": (
        "run-1790250818927",
        "把情绪压进流程句，语速稳而偏慢；越逼近核心越断在半句，用设备操作和技术确认替自己说完。",
        "人物气质：严肃、傲娇、冷幽默、执拗。",
    ),
    "许遥": (
        "run-1790250839005",
        "像念检查单一样条理清楚，压力一上来句子被动作切碎；把关系问题折算成航程与条件，真动摇时反而更慢、更短。",
        "人物气质：御姐、泼辣、嘴毒幽默、重情。",
    ),
}


def baseline_answer(run_dir: Path) -> dict:
    for line in reversed((run_dir / "runtime.events.jsonl").read_text(encoding="utf-8").splitlines()):
        event = json.loads(line)
        if event.get("event") == "runner.worker.result":
            return json.loads(event["answer"])
    raise ValueError(f"baseline answer missing: {run_dir}")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=False)
    gateway = RoleConversationGateway(load_config(), data_root=OUTPUT / "studio-data")
    comparison = {"schema": "arcvellum/actor-task-sheet-spike/v1", "actors": {}}
    materials = ["# 原任务单 × 人物类型词候选", "", "任务单沿用原测试；下列台词和行为均为角色 Agent 原始候选。", ""]
    for speaker, (run_id, old_style, new_style) in ACTORS.items():
        run_dir = SOURCE / "studio-data/actor-only/character-actor/runs" / run_id
        frozen = json.loads((run_dir / "conversation.prompt.md").read_text(encoding="utf-8"))
        assert frozen["schema"] == "arcvellum/actor-conversation/v1"
        original_init, task_sheet = frozen["messages"]
        assert original_init.count(old_style) == 1
        initialization = original_init.replace(old_style, new_style, 1)
        task_digest = hashlib.sha256(task_sheet.encode("utf-8")).hexdigest()
        response = gateway.run_sequence(
            SOURCE, (initialization, task_sheet), role="character-actor", timeout=600,
        )
        answer = json.loads(response.answer)
        assert answer["scene_id"] == "scene_0001" and answer["speaker"] == speaker
        assert isinstance(answer.get("entries"), list)
        prior = baseline_answer(run_dir)
        comparison["actors"][speaker] = {
            "model": response.model,
            "run_id": response.run_id,
            "task_sheet_sha256": task_digest,
            "original_initialization": original_init,
            "new_initialization": initialization,
            "task_sheet_verbatim": task_sheet,
            "baseline_answer": prior,
            "new_answer": answer,
        }
        materials.extend((f"## {speaker}", "", f"任务单 SHA-256：{task_digest}", ""))
        for entry in answer["entries"]:
            materials.extend((
                f"### {entry.get('beat_id', '')}", "",
                f"动作：{entry.get('first_person_action', '')}", "",
                f"台词：{entry.get('spoken', '')}", "",
            ))
        print(f"{speaker}: {len(answer['entries'])} entries, {response.model}, run {response.run_id}", flush=True)
    (OUTPUT / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "materials.md").write_text("\n".join(materials), encoding="utf-8")
    print(f"RESULT {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
