import { describe, expect, it } from "vitest";
import { projectPlanOverlay } from "./orreryPlanProjection";
import type { StrategyProjection, TypedPlanEvent } from "./types";

function strategy(activePlan: unknown): StrategyProjection {
  return {
    schema: "arcvellum/strategy-projection/v1",
    settings: { enabled: false, mode: "fixed", preset: "balanced" },
    active_plan: activePlan as never,
    rolling_horizon: null,
    capabilities: [],
  };
}

function event(id: string, type: string): TypedPlanEvent {
  return {
    event_id: id,
    event_type: type,
    plan_id: "plan-1",
    revision: 1,
    created_at: "2026-07-30T01:00:00+00:00",
  };
}

describe("projectPlanOverlay", () => {
  it("places the scope node first and event nodes after it", () => {
    const overlay = projectPlanOverlay(
      strategy({
        plan_id: "plan-1",
        revision: 3,
        status: "active",
        scope_kind: "chapter",
        scope_key: "chapter_01",
      }),
      [event("e1", "plan.candidate.completed"), event("e2", "plan.activated")],
    );

    expect(overlay.nodes[0]).toMatchObject({
      kind: "scope",
      label: "chapter_01",
      slot: 0,
    });
    expect(overlay.nodes.map((node) => node.id)).toEqual(["scope:chapter:chapter_01", "e1", "e2"]);
    expect(overlay.event_count).toBe(2);
  });

  it("caps the event strip at twelve nodes", () => {
    const events = Array.from({ length: 20 }, (_, index) =>
      event(`e${index}`, `event.${index}`),
    );
    const overlay = projectPlanOverlay(strategy(null), events);

    expect(overlay.nodes).toHaveLength(12);
    expect(overlay.nodes[0].label).toBe("event.8");
    expect(overlay.event_count).toBe(20);
  });

  it("returns an empty overlay when there is no plan and no events", () => {
    const overlay = projectPlanOverlay(null, []);

    expect(overlay.nodes).toEqual([]);
    expect(overlay.plan_id).toBeNull();
    expect(overlay.event_count).toBe(0);
  });
});
