import { describe, expect, it } from "vitest";
import { applyCreativeEvent } from "./projection";
import type { CreativeLiveEvent, CreativeLiveSnapshot } from "./types";

function snapshot(): CreativeLiveSnapshot {
  return {
    ok: true,
    schema: "arcvellum/creative-live-snapshot/v1",
    project_id: "project",
    revision: "r1",
    status: "active",
    controller: null,
    active_task: { task_id: "scene-1" },
    artifacts: [],
    sessions: [],
    activity: [],
    reviews: [],
    usage: { total_tokens: 0, cost_usd: 0, updates: 0 },
    events: [],
    cursor: 0,
  };
}

function event(overrides: Partial<CreativeLiveEvent> = {}): CreativeLiveEvent {
  return {
    schema: "arcvellum/creative-live-event/v1",
    event_id: "event-1",
    sequence: 1,
    event: "artifact.preview.delta",
    channel: "artifact",
    visibility: "user",
    durability: "ephemeral",
    at: "2026-08-31T01:00:00Z",
    project_id: "project",
    run_id: "run-1",
    session_id: "session-1",
    task_id: "scene-1",
    route: "scene-development",
    attempt_id: "attempt-1",
    artifact: {
      artifact_id: "artifact-1",
      path: "drafts/scene_0001.md",
      kind: "prose",
      format: "markdown",
      identity: "streaming_preview",
      revision: 1,
      digest: "",
      characters: 2,
    },
    data: { delta: "开篇" },
    ...overrides,
  };
}

describe("Creative Live projection", () => {
  it("assembles prose deltas and advances candidate identity without duplicating events", () => {
    const first = applyCreativeEvent(snapshot(), event());
    const second = applyCreativeEvent(first, event({
      event_id: "event-2",
      sequence: 2,
      data: { delta: "继续" },
      artifact: { ...event().artifact!, characters: 4 },
    }));
    const promoted = applyCreativeEvent(second, event({
      event_id: "event-3",
      sequence: 3,
      event: "mutation.receipt",
      durability: "durable",
      artifact: { ...event().artifact!, identity: "promoted", characters: 4 },
      data: { title: "正文已晋升", message: "正式正文可阅读。" },
    }));

    expect(promoted.artifacts[0].content).toBe("开篇继续");
    expect(promoted.artifacts[0].identity).toBe("promoted");
    expect(applyCreativeEvent(promoted, promoted.events[0])).toBe(promoted);
  });

  it("collects visible transcript, tools and usage independently", () => {
    let value = applyCreativeEvent(snapshot(), event({
      event_id: "message",
      event: "agent.message.delta",
      channel: "transcript",
      artifact: null,
      data: { text: "我正在检查人物选择。" },
    }));
    value = applyCreativeEvent(value, event({
      event_id: "tool",
      sequence: 2,
      event: "tool.started",
      channel: "transcript",
      artifact: null,
      data: { tool: "read_task_source" },
    }));
    value = applyCreativeEvent(value, event({
      event_id: "usage",
      sequence: 3,
      event: "usage.updated",
      channel: "usage",
      artifact: null,
      data: { usage: { total_tokens: 900 }, cost_usd: 0.02 },
    }));

    expect(value.sessions[0].transcript).toContain("人物选择");
    expect(value.sessions[0].tools[0].tool).toBe("read_task_source");
    expect(value.usage).toEqual({ total_tokens: 900, cost_usd: 0.02, updates: 1 });
  });

  it("keeps a thirty-thousand-character prose stream readable while bounding event history", () => {
    const chunk = "潮声落在舷窗外。".repeat(75);
    let value = snapshot();
    for (let index = 1; index <= 50; index += 1) {
      value = applyCreativeEvent(value, event({
        event_id: `long-${index}`,
        sequence: index,
        data: { delta: chunk },
        artifact: { ...event().artifact!, characters: chunk.length * index },
      }));
    }

    expect(value.artifacts[0].content).toHaveLength(30_000);
    expect(value.artifacts[0].truncated).toBe(false);
    expect(value.events).toHaveLength(50);
    expect(value.cursor).toBe(50);
  });
});
