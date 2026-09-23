"""Freeze a prose baseline and prepare reproducible blinded A-E reading packets.

This measures supplied texts. It does not call a model or write to a project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random


ARMS = ("A", "B", "C", "D", "E")
FIXTURE = Path(__file__).with_name("prose_style_cases.json")
FROZEN_BASELINE = Path(__file__).with_name("baselines") / "prose-style-v09910" / "baseline.json"


def build_baseline(project: Path, fixture: dict[str, object]) -> dict[str, object]:
    scenes = []
    for case in fixture["cases"]:
        scene_id = case["scene_id"]
        path = project / "drafts" / "scenes" / f"{scene_id}.md"
        body = path.read_text(encoding="utf-8")
        if not body.strip():
            raise ValueError(f"empty baseline scene: {scene_id}")
        scenes.append({
            **case,
            "relative_path": path.relative_to(project).as_posix(),
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "characters": len(body),
        })
    return {
        "schema": "arcvellum/prose-style-baseline/v1",
        "baseline_revision": fixture["baseline_revision"],
        "baseline_version": fixture["baseline_version"],
        "scenes": scenes,
        "adjacent_groups": fixture["adjacent_groups"],
        "reader_ratings": "not-collected",
    }


def validate_frozen_baseline(actual: dict[str, object], frozen: dict[str, object]) -> None:
    expected = {row["scene_id"]: row["sha256"] for row in frozen["scenes"]}
    observed = {row["scene_id"]: row["sha256"] for row in actual["scenes"]}
    if observed != expected or actual["baseline_revision"] != frozen["baseline_revision"]:
        raise ValueError("baseline prose differs from the frozen v0.99.10 evidence")


def _validate_prompt_manifest(path: Path, arm: str, scene_id: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if Path(str(payload.get("scene") or "")).stem != scene_id:
        raise ValueError(f"prompt manifest scene mismatch: {arm}/{scene_id}")
    required = ("expression_plan_digest",) if arm == "B" else (
        "expression_plan_digest", "style_reference_selection",
    ) if arm == "C" else ("expression_plan_digest", "style_reference_selection", "voice_digest")
    if any(not payload.get(field) for field in required):
        raise ValueError(f"prompt manifest lacks {arm}-arm provenance: {arm}/{scene_id}")


def build_blind_packet(
    project: Path, candidates: Path, fixture: dict[str, object], *, seed: int,
) -> tuple[str, dict[str, object]]:
    rng = random.Random(seed)
    lines = ["# 文风 A—E 盲评包", "", "先独立评分，再查看揭盲密钥。不得凭版本、模型或 Prompt 线索评分。"]
    key: dict[str, object] = {"schema": "arcvellum/prose-style-blind-key/v1", "seed": seed, "cases": {}}
    for case in fixture["cases"]:
        scene_id = case["scene_id"]
        items = []
        for arm in ARMS:
            path = (project / "drafts" / "scenes" / f"{scene_id}.md") if arm == "A" else (candidates / arm / f"{scene_id}.md")
            body = path.read_text(encoding="utf-8").strip()
            if not body:
                raise ValueError(f"empty candidate: {arm}/{scene_id}")
            if arm != "A" and not (candidates / arm / f"{scene_id}.prompt.json").is_file():
                raise FileNotFoundError(f"missing prompt manifest: {arm}/{scene_id}")
            if arm != "A":
                _validate_prompt_manifest(candidates / arm / f"{scene_id}.prompt.json", arm, scene_id)
            items.append((arm, body, hashlib.sha256(body.encode("utf-8")).hexdigest()))
        rng.shuffle(items)
        lines.extend(["", f"## {scene_id} · {case['family']}", "", str(case["question"]), ""])
        key["cases"][scene_id] = []
        for number, (arm, body, digest) in enumerate(items, 1):
            label = f"候选 {number}"
            lines.extend([f"### {label}", "", body, ""])
            key["cases"][scene_id].append({"label": label, "arm": arm, "sha256": digest})
    lines.extend(["## 独立评分表", "", "每位读者记录：首选版本、语言起伏、去名对白可辨识度、修辞是否有根、证据后解释、重复收尾和近似复写风险，并引用具体句段。"])
    return "\n".join(lines) + "\n", key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-project", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--seed", type=int, default=99010)
    args = parser.parse_args()
    project = args.baseline_project.resolve()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    baseline = build_baseline(project, fixture)
    validate_frozen_baseline(baseline, json.loads(FROZEN_BASELINE.read_text(encoding="utf-8")))
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "baseline.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.candidate_root:
        packet, key = build_blind_packet(project, args.candidate_root.resolve(), fixture, seed=args.seed)
        (output / "blind-packet.md").write_text(packet, encoding="utf-8")
        (output / "blind-key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
