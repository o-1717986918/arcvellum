import { describe, expect, it } from "vitest";
import { applyRehearsalTurn, rehearsalSpeakerSide, rehearsalTurnFromEvent } from "./sceneRehearsalProjection";
import type { CreativeLiveEvent, SceneRehearsalDetail } from "./types";

const scene: SceneRehearsalDetail = {
  transaction_id: "tx-one", scene_id: "scene_0001", status: "creating", objective: "取回旧信",
  turn_count: 0, updated_at: "", turns: [], environment: [],
};

function event(turn: number): CreativeLiveEvent {
  return {
    schema: "v1", event_id: `event-${turn}`, sequence: turn, event: "scene.performance.interaction.turn",
    channel: "activity", visibility: "user", durability: "durable", at: "2026-09-25T00:00:00Z",
    project_id: "project", run_id: "", session_id: "", task_id: "", route: "", attempt_id: "", artifact: null,
    data: { scene_transaction_id: "tx-one", turn, speaker: turn === 1 ? "许遥" : "程野", beat_id: "b1",
            turn_entries: [{ entry_id: `t${turn}:1`, spoken: "信呢？", first_person_action: "我伸出手。" }] },
  };
}

describe("scene rehearsal projection", () => {
  it("adds one complete public actor turn and deduplicates replay", () => {
    const first = applyRehearsalTurn(scene, event(1));
    const second = applyRehearsalTurn(first, event(2));
    expect(second.turns).toHaveLength(2);
    expect(applyRehearsalTurn(second, event(2)).turns).toHaveLength(2);
    expect(rehearsalSpeakerSide(second.turns, "许遥")).toBe("right");
    expect(rehearsalSpeakerSide(second.turns, "程野")).toBe("left");
    expect(JSON.stringify(second)).not.toContain("private_impulse");
    expect(rehearsalTurnFromEvent({ ...event(1), event: "agent.message.delta" })).toBeNull();
  });
});
